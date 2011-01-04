import os

from twisted.internet.utils import getProcessValue
from twisted.internet.defer import Deferred

from jolicloud_pkg_daemon.plugins import LinuxSessionManager
from jolicloud_pkg_daemon.enums import *

class FoldersManager(LinuxSessionManager):
    
    def favorites(self, request, handler):
        def get_favorites(res):
            retval = []
            fp = file('%s/.gtk-bookmarks' % os.environ['HOME'])
            for line in fp.readlines():
                try:
                    uri, name = line.split()
                except ValueError:
                    uri = line.rstrip()
                name = os.path.basename(uri)
                retval.append({'name': name, 'uri': uri})
            handler.send_data(request, retval)
            handler.send_meta(OPERATION_SUCCESSFUL, request=request)
        def failed(err):
            handler.send_meta(OPERATION_FAILED, request=request)
        d = Deferred()
        d.addCallbacks(get_favorites, failed)
        d.callback(None)
    
    def open_(self, request, handler, uri):
        if '~' in uri:
            uri = uri.replace('~', os.environ['HOME'])
        d = getProcessValue(
            '/usr/bin/thunar',
            args=[uri],
            env=os.environ
        )
        def get_value(code):
            if code == 0:
                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
            else:
                handler.send_meta(OPERATION_FAILED, request=request)
        d.addCallback(get_value)

foldersManager = FoldersManager()

