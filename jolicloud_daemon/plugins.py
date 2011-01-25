from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.python import log

from jolicloud_daemon.enums import *

from jolidaemon.ijolidaemon import ISessionManager, ISystemManager


class Manager(object):
    _events = {} # internal table of attached events handler
    
    def register(self, request, handler, event):
        event_name = event.split('/')[1]
        if event_name not in self.events:
            return handler.send_meta(EVENT_UNAVAILABLE, request)

        handler_name = request.handler
        
        if event_name not in self._events:
            self._events[event_name] = {}
        
        self._events[event_name][handler_name] = {
            'request': request,
            'handler': handler
        }
    
    def unregister(self, request, handler, event):
        event_name = event.split('/')[1]
        if event_name not in self.events:
            return handler.send_meta(EVENT_UNAVAILABLE, request)

        handler_name = request.handler
        
        if event_name in self._events and handler_name in self._events[event_name]:
            del self._events[event_name][handler_name]
    
    def emit(self, event, data):
        if event in self._events:
            handlers_to_delete = []
            for handler_name in self._events[event]:
                try:
                    self._events[event][handler_name]['handler'].send_data(self._events[event][handler_name]['request'], data)
                    log.msg('Sending event: [%s] %s' % (event, data))
                except AttributeError, e:
                    log.msg('Emit Exception. Client is disconnected? %s' % e)
                    handlers_to_delete.append(handler_name)
            for handler_to_delete in handlers_to_delete:
                self._events[event].pop(handler_to_delete)
        else:
            return False

class SystemManager(Manager):
    """
    Base class for all system plugins
    """
    implements(IPlugin, ISystemManager)

class LinuxSystemManager(SystemManager):
    pass

class MacOSXSystemnManager(SystemManager):
    pass

class WindowsSystemManager(SystemManager):
    pass


class SessionManager(Manager):
    """
    Base class for all session plugins
    """
    implements(IPlugin, ISessionManager)

class LinuxSessionManager(SessionManager):
    pass

class MacOSXSessionManager(SessionManager):
    pass

class WindowsSessionManager(SessionManager):
    pass
