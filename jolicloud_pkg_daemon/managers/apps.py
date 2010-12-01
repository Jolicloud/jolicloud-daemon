#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus

from twisted.python import log

from jolicloud_pkg_daemon.plugins import BaseManager, _need_dbus
from jolicloud_pkg_daemon.enums import *

# Launch
import commands
from xdg.DesktopEntry import DesktopEntry
from twisted.internet.utils import getProcessValue
# End Launch

class Transaction():
    
    tid = None
    pk_control = None
    last_status = None
    last_progress = None
        
    def _get_transaction(self):
        self._error_enum = None
        self._finished_status = None
        
        try:
            self.tid = self.pk_control.GetTid()
        except (AttributeError, dbus.DBusException), e:
            if self.pk_control == None or (hasattr(e, '_dbus_error_name') and e._dbus_error_name == 'org.freedesktop.DBus.Error.ServiceUnknown'):
                # first initialization (lazy) or timeout
                self.pk_control = dbus.Interface(self.dbus_system.get_object(
                    'org.freedesktop.PackageKit',
                    '/org/freedesktop/PackageKit',
                    False
                ), 'org.freedesktop.PackageKit')
                self.tid = self.pk_control.GetTid()
            else:
                raise
        
        log.msg('[%s] New transaction' % self.tid)
        return dbus.Interface(self.dbus_system.get_object(
            'org.freedesktop.PackageKit',
            self.tid,
            False
        ), 'org.freedesktop.PackageKit.Transaction')
    
    def __init__(self, dbus_system, request, handler):
        self.dbus_system = dbus_system
        self.request = request
        self.handler = handler
        self.transaction = self._get_transaction()
        self.properties = dbus.Interface(self.transaction, dbus_interface=dbus.PROPERTIES_IFACE)
    
    def run(self, command, *args):
        for s in dir(self):
            if getattr(self, s) != None and s.startswith('_s_'):
                self.transaction.connect_to_signal(s.replace('_s_', ''), getattr(self, s))
        getattr(self.transaction, command)(*args)
    
    def _s_Category(self, parent_id, cat_id, name, summary, icon):
        log.msg('[%s] Category' % self.tid)
    
    def _s_Details(self, package_id, license, group, detail, url, size):
        log.msg('Details')
    
    def _s_ErrorCode(self, code, details):
        log.msg('ErrorCode')
    
    def _s_Files(self, package_id, file_list):
        log.msg('Files')
    
    def _s_Finished(self, exit, runtime):
        log.msg('[%s] Finished [%s] [%s]' % (self.tid, exit, runtime))
        if exit == 'success':
            self.handler.send_meta(OPERATION_SUCCESSFUL, request=self.request)
        
    def _s_Message(self, type, details):
        log.msg('Message')
    
    def _s_Package(self, info, package_id, summary):
        log.msg('[%s] Package [%s] [%s] [%s]' % (self.tid, info, package_id, summary))
    
    def _s_RepoDetail(self, repo_id, description, enabled):
        log.msg('RepoDetail')
    
    def _s_RepoSignatureRequired(self, package_id, repository_name, key_url, key_userid, key_id, key_fingerprint, key_timestamp, type):
        plog.msg('RepoSignatureRequired')
    
    def _s_EulaRequired(self, eula_id, package_id, vendor_name, license_agreement):
        log.msg('EulaRequired')
    
    def _s_MediaChangeRequired(self, media_type, media_id, media_text):
        log.msg('MediaChangeRequired')
    
    def _s_RequireRestart(self, type, package_id):
        log.msg('RequireRestart')
    
    def _s_Transaction(self, old_tid, timespec, succeeded, role, duration, data, uid, cmdline):
        log.msg('Transaction')
    
    def _s_UpdateDetail(self, package_id, updates, obsoletes, vendor_url, bugzilla_url, cve_url, restart, update_text, changelog, state, issued, updated):
        log.msg('UpdateDetail')
    
    def _s_DistroUpgrade(self, type, name, summary):
        log.msg('DistroUpgrade')
    
    def _s_Changed(self):
        status = self.properties.Get('org.freedesktop.PackageKit.Transaction', 'Status')
        try:
            progress = self.properties.Get('org.freedesktop.PackageKit.Transaction', 'Percentage')
        except:
            progress = 0
        
        if status == self.last_status and progress == self.last_progress:
            return
        
        self.last_status = status
        self.last_progress = progress
        
        progress = float(progress) / 100
        
        log.msg('[%s] Changed [status:%s] [percentage:%.1f]' % (self.tid, status, progress))
        self.handler.send_data(self.request, {'status': status, 'progress': progress})
    
    def _s_Destroy(self):
        log.msg('[%s] Destroy' % self.tid)

class AppsManager(BaseManager):
    def _install_remove(self, method, request, handler, package):
        def get_package(i, p_id, summary):
            t = Transaction(self.dbus_system, request, handler)
            if method == 'InstallPackages':
                t.run(method, True, [p_id])
            elif method == 'RemovePackages':
                t.run(method, [p_id], True, True)
        
        t = Transaction(self.dbus_system, request, handler)
        t._s_Package = get_package
        t._s_Changed = None
        t._s_Finished = None
        t.run('Resolve', 'none', [package])
    
    @_need_dbus
    def install(self, request, handler, package):
        self._install_remove('InstallPackages', request, handler, package)
    
    @_need_dbus
    def remove(self, request, handler, package):
        self._install_remove('RemovePackages', request, handler, package)
    
    # Launch 
    def launch(self, request, handler, command):
        command_split = command.split()
        if '%F' in command_split: command_split.remove('%F')
        if '%u' in command_split: command_split.remove('%u')
        d = getProcessValue(
            command_split[0],
            args=command_split[1:],
            env=os.environ
        )
        def get_value(code):
            if code == 0:
                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
            else:
                handler.send_meta(OPERATION_FAILED, request=request)
        d.addCallback(get_value)
        
    # FIXME: this launches the first desktop file found and ignores the rest.  We should prompt or something.
    def launch_package(self, request, handler, package):
         """Launch a program from its package name"""
         desktop_files = commands.getoutput("dpkg -L %s | grep '^/usr/share/applications/.*\.desktop$'" % package).split("\n")
         # a simple hack for packages like firefox that keep the .desktop file in a different package
         if os.path.exists("/usr/share/applications/%s.desktop" % package):
             desktop_files.append("/usr/share/applications/%s.desktop" % package)
         for desktop_file in desktop_files:
             entry = DesktopEntry()
             try:
                 entry.parse(desktop_file)
             except:
                 continue
             if not ('Core' in entry.getCategories() or entry.getNoDisplay() or entry.getHidden()):
                 self.launch(request, handler, entry.getExec())
                 return
         handler.failed(request)
    # End Launch

appsManager = AppsManager()

