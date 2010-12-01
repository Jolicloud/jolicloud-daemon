__author__ = 'Andrew Stormont'

import os
import dbus

from jolicloud_pkg_daemon.plugins import BaseManager, _need_dbus

(
    GSM_LOGOUT_MODE_NORMAL,
    GSM_LOGOUT_MODE_NO_CONFIRMATION,
    GSM_LOGOUT_MODE_FORCE
) = [dbus.UInt32(i) for i in range(3)]


class PowerManager(object):

    def __init__(self, manager):
        raise TypeError("Do not instantiate this class directly")

    def Shutdown(self, **kwargs):
        raise NotImplementedError

    def Reboot(self, **kwargs):
        raise NotImplementedError

    def Hibernate(self, **kwargs):
        raise NotImplementedError

    def Suspend(self, **kwargs):
        raise NotImplementedError


class HalPowerManager(PowerManager):

    def __init__(self, manager):
        self._hal = manager.dbus_system.get_object('org.freedesktop.Hal',
                                                   '/org/freedesktop/Hal/devices/computer')

    def Shutdown(self, **kwargs):
        self._hal.Shutdown(**kwargs)

    def Reboot(self, **kwargs):
        self._hal.Reboot(**kwargs)

    def Hibernate(self, **kwargs):
        self._hal.Hibernate(**kwargs)

    def Suspend(self, **kwargs):
        self._hal.Suspend(**kwargs)


class GnomePowerManager(PowerManager):

    def __init__(self, manager):
        self._gpm = manager.dbus_session.get_object('org.freedesktop.PowerManagement',
                                                    '/org/freedesktop/PowerManagement')

    def Shutdown(self, **kwargs):
        self._gpm.Shutdown(**kwargs)

    def Reboot(self, **kwargs):
        self._gpm.Reboot(**kwargs)

    def Hibernate(self, **kwargs):
        self._gpm.Hibernate(**kwargs)

    def Suspend(self, **kwargs):
        self._gpm.Suspend(**kwargs)


# Upower and devkit-power dont implement everything so borrow the missing bits from HAL
class DevkitPowerManager(HalPowerManager):

    def __init__(self, manager):
        self._devkit = dbus.Interface(manager.dbus_session.get_object('org.freedesktop.DeviceKit.Power',
                                                                      '/org/freedesktop/DeviceKit/Power'),
                                                                      'org.freedesktop.DeviceKit.Power')
        HalPowerManager.__init__(self, manager)

    def Hibernate(self, **kwargs):
        self._devkit.Hibernate(**kwargs)

    def Suspend(self, **kwargs):
        self._devkit.Suspend(**kwargs)


class UPowerManager(HalPowerManager):

    def __init__(self, manager):
        self._upower = manager.dbus_system.get_object('org.freedesktop.UPower',
                                                      '/org/freedesktop/UPower')
        HalPowerManager.__init__(self, manager)

    def Hibernate(self, **kwargs):
        self._upower.Hibernate(**kwargs)

    def Suspend(self, **kwargs):
        self._upower.Suspend(**kwargs)


class SessionManager(BaseManager):
    """shutdown/reboot/hibernate/suspend computer"""

    def _need_pm(func):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "_power_manager"):
                try:
                    # Ubuntu 10.04
                    self._power_manager = UPowerManager(self)
                except dbus.DBusException:
                    #try:
                    #    # Jolicloud 1.0
                    #    self._power_manager = DevkitPowerManager(self)
                    #except dbus.DBusException:
                    #    # Jolicloud 0.9
                    self._power_manager = GnomePowerManager(self)
            return func(self, *args, **kwargs)
        return wrapper

    # Actions
    @_need_dbus
    @_need_pm
    def shutdown(self, request, handler):
        """Shutdown the computer"""
        def reply_handler(*args):
            handler.success(request)
        def error_handler(*args):
            handler.failure(request)
        self._power_manager.Shutdown(reply_handler=reply_handler,
                                     error_handler=error_handler)

    @_need_dbus
    @_need_pm
    def restart(self, request, handler):
        """Reboot the computer"""
        def reply_handler(*args):
            handler.success(request)
        def error_handler(*args):
            handler.failure(request)
        self._power_manager.Reboot(reply_handler=reply_handler,
                                   error_handler=error_handler)

    @_need_dbus
    @_need_pm
    def hibernate(self, request, handler):
        """Hibernate the computer"""
        def reply_handler(*args):
            handler.success(request)
        def error_handler(*args):
            handler.failure(request)
        self._power_manager.Hibernate(reply_handler=reply_handler,
                                      error_handler=error_handler)

    @_need_dbus
    @_need_pm
    def sleep(self, request, handler):
        """Suspend the computer"""
        def reply_handler(*args):
            handler.success(request)
        def error_handler(*args):
            handler.failure(request)
        self._power_manager.Suspend(reply_handler=reply_handler,
                                    error_handler=error_handler)

    @_need_dbus
    def logout(self, request, handler):
        """Logs the user out of the current session"""
        def reply_handler(*args):
            handler.success(request)
        def error_handler(*args):
            handler.failure(request)
        try:
            session_manager = self.dbus_session.get_object('org.gnome.SessionManager',
                                                           '/org/gnome/SessionManager')
        except dbus.DBusException:
            handler.failure(request)
        else:
            session_manager.Logout(GSM_LOGOUT_MODE_NO_CONFIRMATION,
                                   reply_handler=reply_handler, 
                                   error_handler=error_handler)

sessionManager = SessionManager()
