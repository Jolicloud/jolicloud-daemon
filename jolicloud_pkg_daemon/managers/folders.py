import os

from twisted.internet import reactor, protocol
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
        reactor.spawnProcess(
            protocol.ProcessProtocol(),
            '/usr/bin/setsid', # setsid - run a program in a new session
            ['setsid', 'nautilus', str(uri)],
            env=os.environ
        )
        handler.success(request)

foldersManager = FoldersManager()

