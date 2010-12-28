from zope.interface import implements
from twisted.plugin import IPlugin

from jolidaemon.ijolidaemon import IManager

class BaseManager(object):
    """
    Base class for all daemon plugins
    """
    implements(IPlugin, IManager)

class LinuxBaseManager(BaseManager):
    pass

class MacOSXBaseManager(BaseManager):
    pass

class WindowsBaseManager(BaseManager):
    pass
