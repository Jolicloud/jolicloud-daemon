#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import shlex
import time
import wnck

from twisted.internet import reactor, protocol
from twisted.web.client import downloadPage
from twisted.python import log

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

try:
    from xdg.DesktopEntry import DesktopEntry
    import xdg.Menu
    import xdg.IconTheme
except ImportError:
    log.msg("Couldn't import xdg stuff. Some features might not work!")

class AppsManager(LinuxSessionManager):
    
    # http://my.jolicloud.com/api/apps/index?featured=true&sort=oemvye&page=1&per_page=10

    def __init__(self):
        self.screen = wnck.screen_get_default()
        self._launched_apps = {}

    def launch(self, request, handler, command):
        if command in self._launched_apps:
            for window in self.screen.get_windows():
                if window.get_pid() == self._launched_apps[command]:
                    log.msg('Activating window: %s' % window.get_name())
                    window.activate(int(time.time()))
                    return handler.success(request)
        for flag in 'UuFfDdNnickvm':
            command = command.replace('%%%s' % flag, '')
        command = command.replace('~', os.getenv('HOME')) # Is it really necessary ?
        splited_command = shlex.split(str(command)) # The shlex module currently does not support Unicode input.
        pp = protocol.ProcessProtocol()
        def process_ended(status_code):
            del self._launched_apps[command]
        pp.processEnded = process_ended
        f = reactor.spawnProcess(
            pp,
            '/usr/bin/setsid', # setsid - run a program in a new session
            ['setsid'] + splited_command,
            env=os.environ
        )
        self._launched_apps[command] = f.pid
        handler.success(request)
    
    def launch_webapp(self, request, handler, package, url, icon_url):
        def download_callback(result):
            log.msg('Icon saved: ~/.local/share/icons/%s.png' % package)
        icon_base_path = '%s/.local/share/icons' % os.getenv('HOME')
        if not os.path.exists(icon_base_path):
            os.makedirs(icon_base_path)
        downloadPage(
            str(icon_url),
            os.path.join(icon_base_path, '%s.png' % package),
            timeout=30
        ).addCallback(download_callback)
        if os.path.exists('/usr/bin/jolicloud-webapps-engine'):
            self.launch(request, handler, 'jolicloud-webapps-engine --app=%s --icon-id=%s' % (str(url), str(package)))
        else:
            self.launch(request, handler, 'google-chrome --app=%s' % str(url))
    
    def launch_desktop(self, request, handler, desktop):
        entry = DesktopEntry()
        entry.parse(desktop)
        exec_ = entry.getExec()
        self.launch(request, handler, '/bin/bash -c "%s"' % exec_.replace('"', '\\"')) # Is it really necessary to call bash ?
    
    def launch_settings(self, request, handler):
        self.launch(request, handler, 'gnome-control-center')
    
    def local_apps(self, request, handler):
        reload(xdg.IconTheme)
        desktops = {}

        def get_menu(menu):
            for entry in menu.getEntries():
                if isinstance(entry, xdg.Menu.Menu):
                    get_menu(entry)
                elif isinstance(entry, xdg.Menu.MenuEntry):
                    desktops[entry.DesktopEntry.getFileName()] = {
                        'name': entry.DesktopEntry.getName(),
                        'desktop': entry.DesktopEntry.getFileName()
                    }
        menu = xdg.Menu.parse()
        get_menu(menu)
        
        class DpkgOut(protocol.ProcessProtocol):
            out = ''
            def outReceived(self, data):
                self.out += data
            def processEnded(self, status_object):
                for line in self.out.split('\n'):
                    if len(line):
                        package, desktop = line.split(': ')
                        if desktops.has_key(desktop):
                            desktops[desktop]['package'] = package
                handler.send_data(request, desktops.values())
                handler.success(request)
        reactor.spawnProcess(DpkgOut(), '/usr/bin/dpkg', ['dpkg', '-S'] + desktops.keys())

appsManager = AppsManager()
