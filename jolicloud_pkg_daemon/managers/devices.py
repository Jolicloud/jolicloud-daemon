#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os

from functools import partial

from twisted.python import log

from jolicloud_pkg_daemon.plugins import BaseManager, _need_dbus
from jolicloud_pkg_daemon.enums import *

class DevicesManager(BaseManager):
    
    _hal_proxy = None
    
    def _get_hal_proxy(self):
        if self._hal_proxy is None:
            self._hal_proxy = self.dbus_system.get_object(
                'org.freedesktop.Hal',
                '/org/freedesktop/Hal/Manager'
            ) 
    
    @_need_dbus
    def event_register(self, request, handler, event):
        self._get_hal_proxy()
        
        if event == "devices/device_added":
            self._hal_proxy.connect_to_signal(
                'DeviceAdded',
                partial(self._volume_added, request, handler)
            )
        elif event == "devices/device_removed":
            self._hal_proxy.connect_to_signal(
                'DeviceRemoved',
                partial(self._volume_removed, request, handler)
            )
    
    def _volume_added(self, request, handler, uid):
        log.msg('VOLUME ADDED', uid)
    
    def _volume_removed(self, request, handler, uid):
        log.msg('VOLUME REMOVED', uid)

# devicesManager = DevicesManager()

