from zope.interface import Attribute, implements
from twisted.plugin import IPlugin

from jolidaemon.ijolidaemon import IManager

def _need_dbus(func):
    """
    Function decorator used for setting up 
    dbus connections on manager method call
    """
    def dbus_wrapper(self, request, handler, *args, **kwargs):
        if not hasattr(self, "dbus_session"):
            self.dbus_session = handler.factory.dbus_session
        if not hasattr(self, "dbus_system"):
            self.dbus_system = handler.factory.dbus_system
        return func(self, request, handler, *args, **kwargs)
    return dbus_wrapper

class BaseManager(object):
    """
    Base class for all daemon plugins
    """
    implements(IPlugin, IManager)
