#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import grp

from twisted.python import log
from twisted.internet import reactor, protocol

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *

class PreferencesManager(LinuxSessionManager):
    
    _capabilities = []
    _groups = []
    
    def __init__(self):
      for group_id in os.getgroups():
         self._groups.append(grp.getgrgid(group_id).gr_name)
      
      if 'admin' in self._groups:
         self._capabilities = [
            'autologin',
            'guestmode'
         ]
    
    def capabilities(self, request, handler):
        return self._capabilities
    
    def autologin(self, request, handler, action='status'):
        if 'admin' not in self._groups:
            return handler.failed(request) # TODO: Permission denied
        
        if action not in ['status', 'enable', 'disable']:
            return handler.failed(request) # TODO: Wrong params
        
        args = [action.encode('utf-8')]
        if action == 'enable':
            args.append(os.getlogin())
        
        class GetProcessOutput(protocol.ProcessProtocol):
            out = ''
            def outReceived(self, data):
                self.out += data
            def errReceived(self, data):
                log.msg("[utils/autologin] [stderr] %s" % data)
            def processEnded(self, status_object):
                if status_object.value.exitCode != 0:
                    return handler.failed(request)
                if action == 'status':
                    handler.send_data(request, self.out.strip())
                handler.success(request)
        reactor.spawnProcess(
            GetProcessOutput(),
            '/usr/bin/pkexec',
            ['pkexec', '/usr/lib/jolicloud-pkg-daemon/utils/autologin'] + args,
            env=os.environ
        )
    
    def guestmode(self, request, handler, action='status'):
        if 'admin' not in self._groups:
            return handler.failed(request) # TODO: Permission denied
        
        if action not in ['status', 'enable', 'disable']:
            return handler.failed(request) # TODO: Wrong params
        
        args = [action.encode('utf-8')]
#        if action == 'enable':
#            args.append(os.getlogin())
        
        class GetProcessOutput(protocol.ProcessProtocol):
            out = ''
            def outReceived(self, data):
                self.out += data
            def errReceived(self, data):
                log.msg("[utils/autologin] [stderr] %s" % data)
            def processEnded(self, status_object):
                if status_object.value.exitCode != 0:
                    return handler.failed(request)
                if action == 'status':
                    handler.send_data(request, self.out.strip())
                handler.success(request)
        reactor.spawnProcess(
            GetProcessOutput(),
            '/usr/bin/pkexec',
            ['pkexec', '/usr/lib/jolicloud-pkg-daemon/utils/guestmode'] + args,
            env=os.environ
        )

preferencesManager = PreferencesManager()
