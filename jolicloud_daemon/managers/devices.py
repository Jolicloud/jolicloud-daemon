#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus

from functools import partial

from twisted.python import log

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

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
        self._udisks_iface.connect_to_signal('DeviceAdded', self._device_added)
        self._udisks_iface.connect_to_signal('DeviceChanged', self._device_changed)
        self._udisks_iface.connect_to_signal('DeviceRemoved', self._device_removed)
    
    def _get_size_free(self, mount_point):
        disk = os.statvfs(mount_point)
        return disk.f_bsize * disk.f_bavail
    
    def _device_added(self, path):
        log.msg('DEVICE ADDED %s' % path)
        
        def reply_handler(udi, properties):
            properties = self._parse_volume_properties(properties)
            if properties:
                self.emit('device_added', {
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
        log.msg('DEVICE CHANGED %s' % path)
        
        def reply_handler(udi, properties):
            parsed_properties = self._parse_volume_properties(properties)
            if parsed_properties:
                self.emit('device_changed', {
                    'udi': udi,
                    'properties': parsed_properties
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
        log.msg('DEVICE REMOVED %s' % path)
        self.emit('device_removed', {
            'udi': path
        })
    
    def _parse_volume_properties(self, dev_props):
#        print dev_props['DeviceFile']
#        print 'IdUsage', dev_props.get('IdUsage', '')
#        print 'DevicePresentationHide', dev_props['DevicePresentationHide']
#        print 'DeviceIsDrive', dev_props['DeviceIsDrive']
#        print 'DeviceIsOpticalDisc', dev_props['DeviceIsOpticalDisc']
#        print 'DeviceIsMounted', dev_props['DeviceIsMounted']
#        print 'DriveIsMediaEjectable', dev_props['DriveIsMediaEjectable']
        if dev_props.get('IdUsage', '') == 'filesystem' and \
           not dev_props['DevicePresentationHide'] and \
           not dev_props['DeviceIsDrive'] or \
           dev_props['DriveIsMediaEjectable']:# or \
           #dev_props['DriveCanDetach']:
            label, mount_point, size_free = None, None, None
            if not dev_props['IdLabel'] and (dev_props['DriveIsMediaEjectable'] or dev_props['DriveCanDetach']):
                label = dev_props['DriveModel']
            if dev_props['DeviceIsMounted']:
                mount_point = dev_props['DeviceMountPaths'][0]
                size_free = self._get_size_free(dev_props['DeviceMountPaths'][0])
            if mount_point == '/':
                label = 'Jolicloud'
            return {
                # Old API
                'volume.label': label or dev_props['IdLabel'] or dev_props['IdUuid'],
                'volume.model': dev_props['DriveModel'],
                'volume.is_disc': dev_props['DriveIsMediaEjectable'],
                'volume.mount_point': mount_point,
                'volume.size': dev_props['PartitionSize'],
                'volume.size_free': size_free,
                
                # New API matching org.freedesktop.UDisks
                
                # Id / Label / Model
                'IdLabel': dev_props['IdLabel'],
                'IdUuid': dev_props['IdUuid'],
                'DriveModel': dev_props['DriveModel'],
                
                # Partition
                'PartitionSize': dev_props['PartitionSize'],
                
                # Optical Disc
                'OpticalDiscNumAudioTracks': dev_props['OpticalDiscNumAudioTracks'],
                'OpticalDiscNumSessions': dev_props['OpticalDiscNumSessions'],
                'OpticalDiscNumTracks': dev_props['OpticalDiscNumTracks'],
                
                # Drive
                'DriveIsMediaEjectable': dev_props['DriveIsMediaEjectable'],
                
                # Device
                'DeviceIsMediaAvailable': dev_props['DeviceIsMediaAvailable'],
                'DeviceIsMounted': dev_props['DeviceIsMounted'],
                'DeviceMountPaths': dev_props['DeviceMountPaths'],
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
            handler.failed(request)
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
    
    def mount(self, request, handler, udi):
        props_iface = dbus.Interface(
            dbus.SystemBus().get_object('org.freedesktop.UDisks', udi),
            'org.freedesktop.DBus.Properties'
        )
        def reply_handler(udi, properties, mount_path):
            log.msg('[MOUNT SUCCESS] %s %s' % (udi, mount_path))
            handler.send_data(request, {
                'udi': udi,
                'properties': properties
            })
            handler.success(request)
        def error_handler(udi, error):
            log.msg('[%s] %s' % (udi, error))
            handler.failed(request)
        def props_reply_handler(udi, properties):
            if properties['DeviceIsMounted']:
                log.msg('[%s] Device is already mounted' % udi)
                return handler.failed(request)
            dev_iface = dbus.Interface(
                dbus.SystemBus().get_object('org.freedesktop.UDisks', udi),
                'org.freedesktop.UDisks.Device'
            )
            dev_iface.FilesystemMount(
                properties['IdType'],
                [],
                reply_handler=partial(reply_handler, udi, properties),
                error_handler=partial(error_handler, udi)
            )
        props_iface.GetAll(
            'org.freedesktop.UDisks.Device',
            reply_handler=partial(props_reply_handler, udi),
            error_handler=partial(error_handler, udi)
        )
    
    def unmount(self, request, handler, udi):
        props_iface = dbus.Interface(
            dbus.SystemBus().get_object('org.freedesktop.UDisks', udi),
            'org.freedesktop.DBus.Properties'
        )
        def reply_handler(udi, properties):
            log.msg('[UNMOUNT SUCCESS] %s' % udi)
            handler.success(request)
        def error_handler(udi, error):
            log.msg('[%s] %s' % (udi, error))
            handler.failed(request)
        def props_reply_handler(udi, properties):
            if not properties['DeviceIsMounted']:
                log.msg('[%s] Device is not mounted' % udi)
                return handler.failed(request)
            dev_iface = dbus.Interface(
                dbus.SystemBus().get_object('org.freedesktop.UDisks', udi),
                'org.freedesktop.UDisks.Device'
            )
            dev_iface.FilesystemUnmount(
                [],
                reply_handler=partial(reply_handler, udi, properties),
                error_handler=partial(error_handler, udi)
            )
        props_iface.GetAll(
            'org.freedesktop.UDisks.Device',
            reply_handler=partial(props_reply_handler, udi),
            error_handler=partial(error_handler, udi)
        )
    
    def eject(self, request, handler, udi):
        props_iface = dbus.Interface(
            dbus.SystemBus().get_object('org.freedesktop.UDisks', udi),
            'org.freedesktop.DBus.Properties'
        )
        dev_iface = dbus.Interface(
            dbus.SystemBus().get_object('org.freedesktop.UDisks', udi),
            'org.freedesktop.UDisks.Device'
        )
        def error_handler(udi, error):
            log.msg('[%s] %s' % (udi, error))
            handler.failed(request)
        def eject_reply_handler(udi, properties):
            log.msg('[EJECT SUCCESS] %s' % udi)
            handler.success(request)
        def reply_handler(udi, properties):
            log.msg('[UNMOUNT SUCCESS] %s' % udi)
            if not properties['DriveIsMediaEjectable']:
                log.msg('[%s] Drive is not ejectable' % udi)
                return handler.failed(request)
            dev_iface.DriveEject(
                [],
                reply_handler=partial(eject_reply_handler, udi, properties),
                error_handler=partial(error_handler, udi)
            )
        def props_reply_handler(udi, properties):
            if not properties['DeviceIsMounted']:
                log.msg('[%s] Device is not mounted' % udi)
                return handler.failed(request)
            dev_iface.FilesystemUnmount(
                [],
                reply_handler=partial(reply_handler, udi, properties),
                error_handler=partial(error_handler, udi)
            )
        props_iface.GetAll(
            'org.freedesktop.UDisks.Device',
            reply_handler=partial(props_reply_handler, udi),
            error_handler=partial(error_handler, udi)
        )

devicesManager = DevicesManager()

