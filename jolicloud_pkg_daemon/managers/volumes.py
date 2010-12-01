__author__ = 'Andrew Stormont'

import dbus
import re
import os
import commands

from twisted.internet.defer import Deferred

from jolicloud_pkg_daemon.plugins import BaseManager, _need_dbus


def _db_to_py(func):
    """
    Function decorator that converts dbus input types to python
    """
    def db_wrapper(*args, **kwargs):
        newargs = []
        for arg in args:
            if type(arg) is dbus.String:
                newargs.append(str(arg))
            else:
                newargs.append(arg)
        return func(*newargs, **kwargs)
    return db_wrapper

def _need_hal(func):
    """
    Function decorator that sets up the
    dbus and hal connections when needed
    """
    def hal_wrapper(self, *args, **kwargs):
        if self._hal is None:
            self._hal = self.dbus_system.get_object('org.freedesktop.Hal',
                                                    '/org/freedesktop/Hal/Manager')
            return func(self, *args, **kwargs)
    return hal_wrapper

def _need_volumes(func):
    """
    Function decoration that scans for volumes when needed
    """
    def vols_wrapper(self, request, handler, *args, **kwargs):
        if self._volumes is None:
            def callback(volumes):
                # After the initial scan is done set up signals
                # so we'll be notified of device add/removal
                if self._volume_added_signal is None:
                    self._volume_added_signal = self._hal.connect_to_signal('DeviceAdded', self._volume_added)
                if self._volume_removed_signal is None:
                    self._volume_removed_signal = self._hal.connect_to_signal('DeviceRemoved', self._volume_removed)
                return func(self, request, handler, *args, **kwargs)
            ret = self.scan(request, handler, callback)
        else:
            ret = func(self, request, handler, *args, **kwargs)
        return ret
    return vols_wrapper

class DevicesSignalHandler(object):
    def __init__(self, request, handler):
        self.request = request
        self.handler = handler

    def __call__(self, params):
        self.handler.send_data(request, params)
        return self        
    
class DevicesManager(BaseManager):
    def __init__(self):
        self._hal = None
        self._volumes = None
        self._volume_changed_signals = {}
        self._volume_added_signal = None
        self._volume_removed_signal = None

    @_db_to_py
    def _watch_device(self, udi):
        self._volume_changed_signals[udi] = self.dbus_system.add_signal_receiver(self._volume_changed_signals,
                                                           "PropertyModified",
                                                           "org.freedesktop.Hal.Device",
                                                           "org.freedesktop.Hal",
                                                           udi,
                                                           path_keyword = "udi")
                                                           
    @_db_to_py
    def _unwatch_device(self, udi):
        if udi in self._volume_changed_signals:
            self._volume_changed_signals[udi].remove()

    @_db_to_py
    def _volume_added(self, udi):
        dev_obj = self.dbus_system.get_object('org.freedesktop.Hal', udi)
        dev = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device')
        if 'volume' in dev.GetProperty('info.capabilities'):
            properties = dev.GetAllProperties()
            if not 'info.udi' in properties:
                properties['info.udi'] = udi
            #self._run_callbacks("device_added", udi=udi, properties=properties)
            self._watch_device(udi)
            self._volumes.append(udi)
            
    @_db_to_py
    def _volume_changed(self, update_count, updates, udi):
        properties = self.properties(udi)
        #if properties:
        #    self._run_callbacks("device_changed", udi=udi, properties=properties)

    @_db_to_py
    def _volume_removed(self, udi):
        if udi in self._volumes:
            #self._run_callbacks("device_removed", udi=udi)
            self._unwatch_device(udi)
            self._volumes.remove(udi)

    @_db_to_py
    @_need_volumes
    def properties(self, request, handler, udi, callback=None):
        """Returns details of a HAL volume from its udi"""
        def reply_handler(props):
            if 'volume.mount_point' in props and props['volume.mount_point']:
                disk = os.statvfs(props['volume.mount_point'])
                props['volume.size_free'] = disk.f_bsize * disk.f_bavail
            else:
                props['volume.size_free'] = 'unknown'
            if callable(callback):
                callback(props)
            else:
                handler.send_data(request, props)
                handler.success(request)
        def error_handler(error):
            if callable(callback):
                callback(None)
            else:
                handler.failed(request)
        if udi in self._volumes:
            dev_obj = self.dbus_system.get_object('org.freedesktop.Hal', udi)
            dev = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device')
            dev.GetAllProperties(reply_handler=reply_handler,
                                 error_handler=error_handler)

    @_need_dbus
    @_need_hal
    def scan(self, request, handler, callback=None):
        """Finds any volumes that we aren't tracking"""
        def reply_handler(udis):
            for udi in udis:
                udi = str(udi)
                dev_obj = self.dbus_system.get_object ('org.freedesktop.Hal', udi)
                dev = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device')
                # Check that the device is a volume and has mounting methods
                if dev.PropertyExists('info.capabilities') and \
                  'volume' in dev.GetProperty('info.capabilities') and \
                   dev.PropertyExists('org.freedesktop.Hal.Device.Volume.method_names'):
                   if self._volumes is None:
                       self._volumes = []
                   if udi not in self._volumes:
                      self._watch_device(udi)
                      self._volumes.append(udi)
            if callable(callback):
                callback(self._volumes)
        def error_handler():
            if not self._volumes and not self._volumes is None:
                self._volumes = None # Reset so scan will be tried again
        iface = dbus.Interface(self._hal, 'org.freedesktop.Hal.Manager')
        iface.FindDeviceByCapability('volume', 
                                     reply_handler=reply_handler,
                                     error_handler=error_handler)

    @_db_to_py
    @_need_volumes
    def unmount(self, request, handler, udi, options=None):
        """Unmount a volume with given udi"""
        if not udi in self._volumes:
            return False
        dev_obj = self.dbus_system.get_object('org.freedesktop.Hal', udi)
        dev = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device')
        vol = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device.Volume')
        unmounted = False
        if not options:
            options = ['']
        try:
            vol.Unmount(options)
            unmounted = True
        except dbus.DBusException, e:
            # If the volume is already unmounted swallow the exception
            dbus_name = e.get_dbus_name()
            if dbus_name == 'org.freedesktop.Hal.Device.Volume.NotMounted':
                unmounted = True
            # Not mounted by so hal we assume the volume lives in /etc/fstab or /etc/mtab
            elif dbus_name == 'org.freedesktop.Hal.Device.Volume.NotMountedByHal':
                if os.system("umount %s" % dev.GetProperty("volume.mount_point")) == 0:
                    unmounted = True
            else:
                raise e
        return unmounted

    @_db_to_py
    @_need_volumes
    def mount(self, request, handler, udi, mount_point=None, fs_type=None, options=None):
        """Mount a volume with given udi"""
        if not udi in self._volumes:
            return False
        dev_obj = self.dbus_system.get_object('org.freedesktop.Hal', udi)
        vol = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device.Volume')
        dev = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device')
        mounted = False
        if not mount_point:
            if dev.PropertyExists('volume.policy.desired_mount_point'):
                mount_point = dev.GetProperty('volume.policy.desired_mount_point')
            else:
                try:
                    mount_point = dev.GetProperty('volume.label')
                    if not mount_point:
                        mount_point = dev.GetProperty('info.product')
                except dbus.DBusException:
                    mount_point = dev.GetProperty('info.product')
        if not fs_type:
            fs_type = dev.GetProperty('volume.fstype')
        if not options:
            options = []
            valid_options = dev.GetProperty('volume.mount.valid_options')
            if 'rw' in valid_options:
                options.append('rw')
            if 'uid=' in valid_options:
                options.append('uid=%s' % os.getuid())
            if 'sync' in valid_options:
                options.append('sync')
            if not options:
                options.append('')
        # Change the mount_point if it is already in use
        if os.path.exists("/media/" + mount_point):
            i = 1
            while os.path.exists("/media/%s_%s" % (mount_point, i)):
                if i == 99:
                    return
                else:
                    i += 1
            mount_point = "%s_%s" % (mount_point, i)
        try:
            vol.Mount(mount_point, fs_type, options)
            mounted = True
        except dbus.DBusException, e:
            # If the volume is already mounted swallow the exception
            if e.get_dbus_name() == 'org.freedesktop.Hal.Device.Volume.AlreadyMounted':
                mounted = True
            # HAL is refusing to mount the volume because it is in /etc/fstab so do it the old fasioned way
            elif re.match("Device /dev/.* is listed in /etc/fstab\. Refusing to mount\.", e.get_dbus_message()):
                status = os.system("mount %s" % dev.GetProperty('block.device'))
                if status in (0, 8192): # 8192 == already mounted
                    mounted = True
            else:
                raise e
        if mounted:
            return {"udi": udi, "properties": self.properties(udi)}

    @_need_volumes
    def volumes(self, request, handler):
        volumes = []
        def callback(properties):
            volume = None
            if properties:
                udi = properties['info.udi']
                volume = {
                    'udi': udi, 
                    'properties': properties
                }
                if volume in volumes:
                    volume = None
            volumes.append(volume)
            if len(volumes) == len(self._volumes):
                handler.send_data(request, [v for v in volumes if not v is None])
        for udi in self._volumes:
            self.properties(request, handler, udi, callback)

    @_need_hal
    def event_register(self, request, handler, event):
        pass

devicesManager = DevicesManager()
