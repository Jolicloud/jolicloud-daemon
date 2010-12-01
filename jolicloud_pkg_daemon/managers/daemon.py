#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

from twisted.python import log

from jolicloud_pkg_daemon.plugins import BaseManager
from jolicloud_pkg_daemon.enums import *

class DaemonManager(BaseManager):
    def is_live(self, request, handler):
        handler.send_data(request, True)

daemonManager = DaemonManager()

