#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import sys
import time
import re

# XXX: try to use cjson which is much faster
try:
    import json
except ImportError:
    import simplejson as json

# We try to import D-Bus if present
dbus_imported = False
try:
    import dbus
    
    # Init reactor with glib support
    from twisted.internet import glib2reactor # for non-GUI apps
    glib2reactor.install()
    
    # We get the system and session buses
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    dbus_imported = True
except ImportError:
    pass

from twisted.internet import reactor
from twisted.python import log
from twisted.internet.protocol import Protocol, Factory
from twisted.web import resource
from twisted.web.static import File
from twisted.plugin import getPlugins

from jolicloud_pkg_daemon.websocket import WebSocketRequest, WebSocketHandler, WebSocketSite
from jolicloud_pkg_daemon.jolidaemon import ijolidaemon
from jolicloud_pkg_daemon.enums import *
from jolicloud_pkg_daemon import managers

TRUSTED_URI = (
    # re.compile(".*"),
    re.compile("https?://my\.jolicloud\.com"),
    re.compile("https?://.*\.dev\.jolicloud\.org"),
    re.compile("http://localhost")
)

class JolicloudRequest(object):
    def __init__(self, frame):
        self._data = json.loads(frame)
        
    def __getattr__(self, attr):
        return self._data[attr]
        
    def __hasattr__(self, attr):
        return attr in self._data

class JolicloudWSRequest(WebSocketRequest):
    def process(self):
        def finish():
            self.channel.transport.loseConnection()
        origin = self.requestHeaders.getRawHeaders('origin', [])
        if len(origin) != 1:
            log.msg('Refusing connection because no origin is set.')
            return finish()
        origin = origin[0].strip()
        accepted = False
        for uri in TRUSTED_URI:
            if uri.match(origin):
                accepted = True
                break
        if accepted:
            log.msg('Accepting connection from [%s]' % origin)
        else:
            log.msg('Refusing connection from [%s]' % origin)
            return finish()
        WebSocketRequest.process(self)

class JolicloudWSSite(WebSocketSite):

    requestFactory = JolicloudWSRequest
    
    def __init__(self, resource, logPath=None, timeout=60*60*12,
                 supportedProtocols=None, dbus_session=None, 
                 dbus_system=None):
        if dbus_session: self.dbus_session = dbus_session
        if dbus_system: self.dbus_system = dbus_system
        WebSocketSite.__init__(self, resource, logPath, timeout)

class JolicloudWSHandler(WebSocketHandler):
    def __init__(self, transport, factory):
        WebSocketHandler.__init__(self, transport, factory)

    # THIS SUCKS.
    def send_meta(self, type, request=None, message=None):
        response = type
        if hasattr(request, 'meta_handler'):
            response['method'] = request.meta_handler
        if message:
            response['params']['message'] += " %s" % message
        self.transport.write(json.dumps(response))
        
    def send_data(self, request, params):
        response = {
            'params' : params,
            'method' : request.handler
        }
        self.transport.write(json.dumps(response))
        
    def success(self, request):
        self.send_meta(OPERATION_SUCCESSFUL, request)
        
    def failed(self, request):
        self.send_meta(OPERATION_FAILED, request)
    
    def frameReceived(self, frame):
        print 'I/O < %s' % frame
        # Try and parse request json
        try:
            request = JolicloudRequest(frame)
        except ValueError, e:
            self.send_meta(SYNTAX_ERROR)
            return
        # Make sure request has handlers
        for handler in ('handler', 'meta_handler'):
            if not hasattr(request, handler):
                self.send_meta(SYNTAX_ERROR, request, "Request is missing %s" % handler)
                return
        # Try and parse the request namespace/method
        if request.method == 'apps/install':
            request.method = 'packages/install'
        if request.method == 'apps/remove':
            request.method = 'packages/remove'
        try:
            (manager_name, method_name) = request.method.split('/')
            if not (manager_name and method_name): raise ValueError
        except ValueError:
            self.send_meta(SYNTAX_ERROR, request, "Not a valid namespace/method")
            return
        # Make sure params is actually a dictionary
        if hasattr(request, 'params') and not type(request.params) is dict:
            self.send_meta(SYNTAX_ERROR, request, "'params' must be a dictionary")
            return
        # XXX: Find a better way to route the events request to the corresponding manager
        if manager_name == 'events':
            manager_name = request.params['event'].split('/')[0]
            method_name = 'event_register'
        plugin_name = '%sManager' % manager_name.capitalize()
        plugin_found = False
        for plugin in getPlugins(ijolidaemon.IManager, managers):
            if plugin_name == plugin.__class__.__name__:
                plugin_found = True
                if hasattr(plugin, '%s_' % method_name):
                    method_name = '%s_' % method_name
                if hasattr(plugin, method_name):
                    self.send_meta(OPERATION_IN_PROGRESS, request)
                    try:
                        kwargs = {}
                        if hasattr(request, 'params'):
                            for key, val in request.params.iteritems():
                                kwargs[str(key)] = val
                        log.msg('Calling %s.%s(%s): ' % (
                            plugin.__class__.__name__,
                            method_name,
                            request.params if hasattr(request, 'params') else ''
                        ))
                        getattr(plugin, method_name)(request, self, **kwargs)
                    except Exception, e:
                        log.err(e)
                        self.send_meta(OPERATION_FAILED, request)
                else:
                    self.send_meta(NOT_IMPLEMENTED, request)
                break
        if plugin_found == False:
            self.send_meta(NOT_IMPLEMENTED, request)
    
    def connectionLost(self, reason):
        log.msg('Connection lost')

def start():
    log.startLogging(sys.stdout)
    
    # Websocket server
    kwargs = { 'resource': File(os.environ['JPD_HTDOCS_PATH']) }
    if dbus_imported:
        kwargs.update({
            'dbus_system': dbus.SystemBus(),
            'dbus_session': dbus.SessionBus(),
        })
    site = JolicloudWSSite(**kwargs)
    site.addHandler('/jolicloud/', JolicloudWSHandler)
    
    reactor.listenTCP(8005, site) # interface = "127.0.0.1"
    reactor.run()

if __name__ == "__main__":
    start()
