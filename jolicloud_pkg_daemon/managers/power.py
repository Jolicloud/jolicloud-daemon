#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus

from twisted.python import log
from twisted.internet import reactor, protocol

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *

class PowerManager(LinuxSessionManager):
    
    events = ['changed']
    
    _NS = 'org.freedesktop.UPower'
    _PROPS_NS = 'org.freedesktop.DBus.Properties'
    _PATH = '/org/freedesktop/UPower'
    
    def __init__(self):
        self.dbus_system = dbus.SystemBus()
        self._upower_proxy = self.dbus_system.get_object(self._NS, self._PATH)
        self._upower_iface = dbus.Interface(self._upower_proxy, self._NS)
        self._upower_iface.connect_to_signal("Changed", self._changed)
        self._props_iface = dbus.Interface(self._upower_proxy, self._PROPS_NS)
        self._ck_iface = dbus.Interface(self.dbus_system.get_object(
            'org.freedesktop.ConsoleKit',
            '/org/freedesktop/ConsoleKit/Manager'
        ), 'org.freedesktop.ConsoleKit.Manager')
    
    def _changed(self):
        self.emit('changed', self._props_iface.GetAll(self._NS))
        log.msg('UPower changed: %s' % self._props_iface.GetAll(self._NS))
        
    def shutdown(self, request, handler):
        def reply_handler():
            handler.success(request)
        def error_handler(error):
            handler.failed(request)
            log.msg("Caught error when calling Stop()")
        self._ck_iface.Stop(reply_handler=reply_handler, error_handler=error_handler)

    def restart(self, request, handler):
        def reply_handler():
            handler.success(request)
        def error_handler(error):
            handler.failed(request)
            log.msg("Caught error when calling Restart()")
        self._ck_iface.Restart(reply_handler=reply_handler, error_handler=error_handler)

    def hibernate(self, request, handler):
        def reply_handler():
            handler.success(request)
        def error_handler(error):
            handler.failed(request)
        self._upower_iface.Hibernate(reply_handler=reply_handler, error_handler=error_handler)

    def sleep(self, request, handler):
        def reply_handler():
            handler.success(request)
        def error_handler(error):
            handler.failed(request)
        self._upower_iface.Suspend(reply_handler=reply_handler, error_handler=error_handler)

    def on_battery(self, request, handler):
        def reply_handler(on_battery):
            handler.send_data(request, on_battery == 1)
            handler.success(request)
        def error_handler(error):
            handler.failed(request)
            log.msg("Caught error when getting battery state")
        self._props_iface.Get(self._NS, 'OnBattery', reply_handler=reply_handler, error_handler=error_handler)

powerManager = PowerManager()
