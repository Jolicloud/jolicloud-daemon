import os

from twisted.internet import reactor, protocol
from twisted.internet.utils import getProcessValue
from twisted.internet.defer import Deferred

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

class FoldersManager(LinuxSessionManager):
    
    def favorites(self, request, handler):
        retval = []
        for f in os.listdir(os.environ['HOME']):
            path = os.path.join(os.environ['HOME'], f)
            if os.path.isdir(path) and not f.startswith('.'):
                retval.append({'name': f, 'uri': path})
        if os.path.exists('/host'):
            retval.append({'name': 'Windows', 'uri': '/host'})
        return retval
    
    def open_(self, request, handler, uri):
        if '~' in uri:
            uri = uri.replace('~', os.environ['HOME'])
        reactor.spawnProcess(
            protocol.ProcessProtocol(),
            '/usr/bin/setsid', # setsid - run a program in a new session
            ['setsid', 'nautilus', '--no-desktop', uri.encode('utf-8')],
            env=os.environ
        )
        handler.success(request)

foldersManager = FoldersManager()

