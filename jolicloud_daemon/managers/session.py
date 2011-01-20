#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus

from twisted.python import log
from twisted.internet import reactor, protocol

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

class SessionManager(LinuxSessionManager):
    
    (
        GSM_LOGOUT_MODE_NORMAL,
        GSM_LOGOUT_MODE_NO_CONFIRMATION,
        GSM_LOGOUT_MODE_FORCE
    ) = range(3)
    
    def __init__(self):
        self.dbus_session = dbus.SessionBus()
    
    def logout(self, request, handler):
        gnome_session = self.dbus_session.get_object(
            'org.gnome.SessionManager',
            '/org/gnome/SessionManager'
        )
        def reply_handler():
            handler.success(request)
        def error_handler(error):
            log.msg("Problem contacting the SessionManager.  Calling gnome-session-save instead.")
            status = os.system('gnome-session-save --logout')
            if status > 0:
                log.msg("gnome-session-save returned failure status %s" % status)
            else:
                handler.failed(request)
        gnome_session.Logout(
            dbus.UInt32(self.GSM_LOGOUT_MODE_NO_CONFIRMATION),
            reply_handler=reply_handler,
            error_handler=error_handler
        )
    
    def inhibit_screensaver(self, request, handler, reason='No particular reason'):
        """ Add an inhibitor to the screensaver with an optional reason """
        def reply_handler(cookie):
            handler.send_data(request, cookie)
            handler.success(request)
        def error_handler(error):
            log.msg('Failed to inhibit the screensaver. %s' % error)
            handler.failed(request)
        screensaver_bus = self.dbus_session.get_object(
            'org.gnome.ScreenSaver',
            '/org/gnome/ScreenSaver'
        )
        screensaver_bus.Inhibit(
            'jolicloud-daemon',
            reason, 
            reply_handler=reply_handler, 
            error_handler=error_handler
        )
    
    def uninhibit_screensaver(self, request, handler, cookie):
        """ Remove the screensaver inhibitor corresponding to the cookie """
        def reply_handler():
            handler.success(request)
        def error_handler(error):
            log.msg('Failed to uninhibit the screensaver. %s' % error)
            handler.failed(request)
        screensaver_bus = self.dbus_session.get_object(
            'org.gnome.ScreenSaver',
            '/org/gnome/ScreenSaver'
        )
        screensaver_bus.UnInhibit(
            dbus.UInt32(cookie), 
            reply_handler=reply_handler,
            error_handler=error_handler
        )

sessionManager = SessionManager()
