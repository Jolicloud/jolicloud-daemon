#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus

from functools import partial

from twisted.python import log

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *

class DevicesManager(LinuxSessionManager):
    
    events = ['device_added', 'device_changed', 'device_removed']
    
    _NS = 'org.freedesktop.UDisks'
    _PROPS_NS = 'org.freedesktop.DBus.Properties'
    _PATH = '/org/freedesktop/UDisks'
    _DEVICE_NS = 'org.freedesktop.UDisks.Devices'
    
    def __init__(self):
        self.dbus_system = dbus.SystemBus()
        self._udisks_proxy = self.dbus_system.get_object(self._NS, self._PATH)
        self._udisks_iface = dbus.Interface(self._udisks_proxy, self._NS)
        self._udisks_iface.connect_to_signal("DeviceAdded", self._device_added)
        self._udisks_iface.connect_to_signal("DeviceChanged", self._device_changed)
        self._udisks_iface.connect_to_signal("DeviceRemoved", self._device_removed)
    
    def _get_size_free(self, mount_point):
        disk = os.statvfs(mount_point)
        return disk.f_bsize * disk.f_bavail
    
    def _device_added(self, path):
        print 'DEVICE ADDED', path
        
        def reply_handler(udi, properties):
            properties = self._parse_volume_properties(properties)
            if properties:
                self.emit('device_added',{
                    'udi': udi,
                    'properties': properties
                })
        def error_handler(udi, error):
            log.msg('[%s] %s' % (udi, error))
        
        props = dbus.Interface(
            dbus.SystemBus().get_object('org.freedesktop.UDisks', path),
            'org.freedesktop.DBus.Properties'
        )
        props.GetAll(
            'org.freedesktop.UDisks.Device',
            reply_handler=partial(reply_handler, path),
            error_handler=partial(error_handler, path)
        )
    
    def _device_changed(self, path):
        print 'DEVICE CHANGED', path
        
        def reply_handler(udi, properties):
            properties = self._parse_volume_properties(properties)
            if properties:
                self.emit('device_changed',{
                    'udi': udi,
                    'properties': properties
                })
        def error_handler(udi, error):
            log.msg('[%s] %s' % (udi, error))
        
        props = dbus.Interface(
            dbus.SystemBus().get_object('org.freedesktop.UDisks', path),
            'org.freedesktop.DBus.Properties'
        )
        props.GetAll(
            'org.freedesktop.UDisks.Device',
            reply_handler=partial(reply_handler, path),
            error_handler=partial(error_handler, path)
        )
    
    def _device_removed(self, path):
        print 'DEVICE REMOVED', path
        self.emit('device_removed', {
            'udi': path
        })
    
    def _parse_volume_properties(self, dev_props):
        if dev_props.get('IdUsage', '') == 'filesystem' and not dev_props['DevicePresentationHide'] and not dev_props['DeviceIsDrive']:
            label, mount_point, size_free = None, None, None
            if dev_props['DeviceIsMounted']:
               mount_point = dev_props['DeviceMountPaths'][0]
               size_free = self._get_size_free(dev_props['DeviceMountPaths'][0])
            if mount_point == '/':
               label = 'Jolicloud'
            return {
               'volume.label': label or dev_props['IdLabel'] or dev_props['IdUuid'],
               'volume.model': dev_props['DriveModel'],
               'volume.is_disk': dev_props['DeviceIsOpticalDisc'],
               'volume.mount_point': mount_point,
               'volume.size': dev_props['PartitionSize'],
               'volume.size_free': size_free,
            }
    
    def volumes(self, request, handler):
        result = []
        devices = self._udisks_iface.EnumerateDevices()
        def reply_handler(udi, properties):
            result.append({
                'udi': udi,
                'properties': self._parse_volume_properties(properties)
            })
            if len(result) == len(devices):
                handler.send_data(request, [r for r in result if r['properties']])
                handler.success(request)
        def error_handler(udi, error):
            log.msg('[%s] %s' % (udi, error))
            handler.failed()
        for device in devices:
            props = dbus.Interface(
                dbus.SystemBus().get_object('org.freedesktop.UDisks', device),
                'org.freedesktop.DBus.Properties'
            )
            props.GetAll(
                'org.freedesktop.UDisks.Device',
                reply_handler=partial(reply_handler, device),
                error_handler=partial(error_handler, device)
            )

devicesManager = DevicesManager()

