#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import grp

from ConfigParser import SafeConfigParser

from twisted.python import log
from twisted.internet import reactor, protocol

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

class DaemonManager(LinuxSessionManager):
    
    _OEM_USER_ID = 29999
    _OEM_USER_LOGNAME = 'oem'
    _OEM_CONF_FILE = '/etc/jolicloud-oem.conf'
    
    # NOTE: is_live also returns is_guest
    def is_live(self, request, handler):
        """Find out if we are running in a live (trial) session"""
        is_live = False
        if os.path.exists('/proc/cmdline'):
            f = open('/proc/cmdline', 'r')
            l = f.readline()
            if l.find('/cdrom/preseed/jolicloud.seed') >= 0:
                is_live = True
            f.close()
        return is_live or self.is_guest(request, handler)
    
    def is_guest(self, request, handler):
        for group in os.getgroups():
            if grp.getgrgid(group).gr_name == 'guests':
                return True
        return False
    
    def version(self, request, handler):
        return '1.1.20'
    
    def computer(self, request, handler):
        # Returns uuid, password and oem
        retval = {
            'settings': {
                'autologin': True
            }
        }
        # OEM
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
        # UUID
        class GetProcessOutput(protocol.ProcessProtocol):
            out = ''
            def outReceived(self, data):
                self.out += data
            def errReceived(self, data):
                log.msg("[UUID] [stderr] %s" % data)
            def processEnded(self, status_object):
                try:
                    uuid, password = self.out.strip().split('\n')
                    retval['uuid'] = uuid.strip()
                    retval['password'] = password.strip()
                except ValueError:
                    pass
                handler.send_data(request, retval)
                handler.success(request)
        reactor.spawnProcess(
            GetProcessOutput(),
            '/usr/bin/pkexec',
            ['pkexec', '/usr/lib/jolicloud-pkg-daemon/utils/uuid']
        )

    def kill_nickel(self, request, handler):
        handler.success(request)

daemonManager = DaemonManager()
