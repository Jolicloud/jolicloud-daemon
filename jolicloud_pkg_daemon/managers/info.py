#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import grp

from twisted.python import log
from twisted.plugin import getPlugins

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *
from jolicloud_pkg_daemon import managers

class InfoManager(LinuxSessionManager):
    
    def all(self, request, handler):
        mount_point = '/'
        disk = os.statvfs(mount_point)
        return {
            'disk': {
                'size' : disk.f_bsize * disk.f_blocks,
                'size_free' : disk.f_bsize * disk.f_bavail,
                'mount_point' : mount_point
            },
            # TODO: guest
            'guest': grp.getgrgid(os.getgroups()[0]).gr_name
        }
    
    def introspection(self, request, handler):
        retval = {}
        for plugin in getPlugins(handler.manager_interface, managers):
            manager = plugin.__class__.__name__.replace('Manager', '').lower()
            retval[manager] = {}
            for method in dir(plugin):
                if hasattr(getattr(plugin, method), 'func_code') and not method.startswith('_'):
                    varnames = getattr(plugin, method).func_code.co_varnames
                    argcount = getattr(plugin, method).func_code.co_argcount
                    retval[manager][method.rstrip('_')] = varnames[3:argcount]
        return {'introspection': retval}

infoManager = InfoManager()
