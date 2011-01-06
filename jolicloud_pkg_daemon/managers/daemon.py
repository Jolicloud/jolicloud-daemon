#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os

from twisted.python import log

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *

class DaemonManager(LinuxSessionManager):
    def is_live(self, request, handler):
        """Find out if we are running in a live (trial) session"""
        is_live = False
        if os.path.exists('/proc/cmdline'):
            f = open('/proc/cmdline', 'r')
            l = f.readline()
            if l.find('/cdrom/preseed/jolicloud.seed') >= 0:
                is_live = True
            f.close()
        return is_live
    
    def version(self, request, handler):
        return '1.1.99'
    
    def computer(self, request, handler):
        return []

daemonManager = DaemonManager()
