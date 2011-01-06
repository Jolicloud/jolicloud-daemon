#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import commands
from ConfigParser import SafeConfigParser

from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.plugin import getPlugins

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *
from jolicloud_pkg_daemon import managers

class InfoManager(LinuxSessionManager):
    _OEM_USER_ID = 29999
    _OEM_USER_LOGNAME = 'oem'
    _OEM_CONF_FILE = '/etc/jolicloud-oem.conf'
    
    def all(self, request, handler):
        names = {
            'disk': None,
            'oem': None,
            'uuid': None,
            'introspection': None
        }
        retval = {}
        class FakeHandler(object):
            def __init__(self, name):
                self.name = name
                self.manager_interface = handler.manager_interface
            def send_data(self, request, val):
                retval.update(val)
                for name in names:
                    if name is None:
                        return
                handler.send_data(request, retval)
        for n in names:
            v = None
            v = getattr(self, n)(request, FakeHandler(n))
            if v is not None:
                retval.update(v)
        for name in names:
            if name is None:
                return
        return retval
    
    def disk(self, request, handler):
        mount_point = '/'
        disk = os.statvfs(mount_point)
        return {
            'disk': {
                'size' : disk.f_bsize * disk.f_blocks,
                'size_free' : disk.f_bsize * disk.f_bavail,
                'mount_point' : mount_point
            }
        }
    
    def oem(self, request, handler):
        """Get the machine oem information"""
        retval = {}
        try:
            cp = SafeConfigParser()
            cp.read(self._OEM_CONF_FILE)
            for name, val in cp.items('device'):
                if 'oem' in retval:
                    retval['oem'][name] = val
                else:
                    retval['oem'] = {name: val}
        except Exception:
            pass
        return retval
    
    def introspection(self, request, handler):
        retval = {}
        for plugin in getPlugins(handler.manager_interface, managers):
            manager = plugin.__class__.__name__.replace('Manager', '').lower()
            retval[manager] = {}
            for method in dir(plugin):
                if hasattr(getattr(plugin, method), 'func_code') and not method.startswith('_'):
                    print manager, method
                    varnames = getattr(plugin, method).func_code.co_varnames
                    argcount = getattr(plugin, method).func_code.co_argcount
                    retval[manager][method.rstrip('_')] = varnames[3:argcount]
        return {'introspection': retval}
    
    def uuid(self, request, handler):
        """Get the machine uuid information"""
        retval = {}
        # We don't want to generate a uuid when running form the OEM ISO
        if not (os.getuid() == self._OEM_USER_ID and os.getlogin() == self._OEM_USER_LOGNAME):
            retval = {}
            class GetUuid(protocol.ProcessProtocol):
                out = ''
                def outReceived(self, data):
                    self.out += data
                
                def errReceived(self, data):
                    log.msg("[GetUuid] [stderr] %s" % data)
                
                def processEnded(self, status_object):
                    try:
                        uuid, password = self.out.split('\n')
                        retval['uuid'] = uuid.strip()
                        retval['password'] = password.strip()
                    except ValueError:
                        pass
                    handler.send_data(request, retval)
            reactor.spawnProcess(GetUuid(), '/usr/lib/jolicloud-daemon/utils/get_uuid', ['get_uuid'])
        else:
            return retval

infoManager = InfoManager()
