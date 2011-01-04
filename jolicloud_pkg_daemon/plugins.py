from zope.interface import implements
from twisted.plugin import IPlugin

from jolidaemon.ijolidaemon import ISessionManager, ISystemManager


class SystemManager(object):
    """
    Base class for all system plugins
    """
    implements(IPlugin, ISystemManager)

class LinuxSystemManager(SystemManager):
    pass

class MacOSXSystemnManager(SystemManager):
    pass

class WindowsSystemManager(SystemManager):
    pass


class SessionManager(object):
    """
    Base class for all session plugins
    """
    implements(IPlugin, ISessionManager)

class LinuxSessionManager(SessionManager):
    pass

class MacOSXSessionManager(SessionManager):
    pass

class WindowsSessionManager(SessionManager):
    pass
