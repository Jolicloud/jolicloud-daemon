#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import grp
import gconf

from twisted.python import log
from twisted.internet import reactor, protocol

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

class PreferencesManager(LinuxSessionManager):
    
    _capabilities = []
    _groups = []
    
    def __init__(self):
        self.gconf_client = gconf.client_get_default()
        for group_id in os.getgroups():
            self._groups.append(grp.getgrgid(group_id).gr_name)
        
        if 'admin' in self._groups:
            self._capabilities = [
                'autologin',
                'guestmode',
                'suspend_lock',
                'hibernate_lock'
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
            args.append(os.getenv('LOGNAME')) # See http://docs.python.org/library/os.html#os.getlogin
        
        gconf_client = self.gconf_client
        
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
                elif action == 'enable':
                    gconf_client.set_bool('/apps/gnome-power-manager/lock/suspend', False)
                    gconf_client.set_bool('/apps/gnome-power-manager/lock/hibernate', False)
                elif action == 'disable':
                    gconf_client.set_bool('/apps/gnome-power-manager/lock/suspend', True)
                    gconf_client.set_bool('/apps/gnome-power-manager/lock/hibernate', True)
                handler.success(request)
        reactor.spawnProcess(
            GetProcessOutput(),
            '/usr/bin/pkexec',
            ['pkexec', '/usr/lib/jolicloud-daemon/utils/autologin'] + args,
            env=os.environ
        )
    
    def guestmode(self, request, handler, action='status'):
        if 'admin' not in self._groups:
            return handler.failed(request) # TODO: Permission denied
        
        if action not in ['status', 'enable', 'disable']:
            return handler.failed(request) # TODO: Wrong params
        
        args = [action.encode('utf-8')]
        if action == 'enable':
            reactor.spawnProcess(
                protocol.ProcessProtocol(),
                '/usr/bin/pkexec',
                ['pkexec', '/usr/lib/jolicloud-daemon/utils/migrate-nm-connections'],
                env=os.environ
            )
        
        class GetProcessOutput(protocol.ProcessProtocol):
            out = ''
            def outReceived(self, data):
                self.out += data
            def errReceived(self, data):
                log.msg("[utils/guestmode] [stderr] %s" % data)
            def processEnded(self, status_object):
                if status_object.value.exitCode != 0:
                    return handler.failed(request)
                if action == 'status':
                    handler.send_data(request, self.out.strip())
                handler.success(request)
        reactor.spawnProcess(
            GetProcessOutput(),
            '/usr/bin/pkexec',
            ['pkexec', '/usr/lib/jolicloud-daemon/utils/guestmode'] + args,
            env=os.environ
        )
    
    def suspend_lock(self, request, handler, action='status'):
        if action == 'status':
            if self.gconf_client.get_bool('/apps/gnome-power-manager/lock/suspend'):
               return 'enabled'
            else:
               return 'disabled'
        if action == 'enable':
            self.gconf_client.set_bool('/apps/gnome-power-manager/lock/suspend', True)
        elif action == 'disable':
            self.gconf_client.set_bool('/apps/gnome-power-manager/lock/suspend', False)
        else:
            return handler.failed(request)
        handler.success(request)
    
    def hibernate_lock(self, request, handler, action='status'):
        if action == 'status':
            if self.gconf_client.get_bool('/apps/gnome-power-manager/lock/hibernate'):
               return 'enabled'
            else:
               return 'disabled'
        if action == 'enable':
            self.gconf_client.set_bool('/apps/gnome-power-manager/lock/hibernate', True)
        elif action == 'disable':
            self.gconf_client.set_bool('/apps/gnome-power-manager/lock/hibernate', False)
        else:
            return handler.failed(request)
        handler.success(request)

preferencesManager = PreferencesManager()
