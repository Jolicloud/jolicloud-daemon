#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus

from functools import partial

from twisted.python import log
from twisted.internet import reactor, protocol

from jolicloud_pkg_daemon.plugins import LinuxBaseManager
from jolicloud_pkg_daemon.enums import *

AUTO_UPDATE_INTERVAL = 600 # Time in seconds

class Transaction():
    
    tid = None
    pk_control = None
    last_status = None
    last_progress = None
    known_errors = [
        'org.freedesktop.DBus.Error.ServiceUnknown',
        'org.freedesktop.DBus.Error.NoReply',
        'org.freedesktop.DBus.Error.LimitsExceeded',
        'org.freedesktop.DBus.Error.TimedOut'
    ]
    sigs = []
    
    def __init__(self, request, handler):
        self.sigs = []
        self.dbus_system = dbus.SystemBus()
        self.request = request
        self.handler = handler
    
    def get_property(self, key):
        proxy = dbus.Interface(self.dbus_system.get_object(
            'org.freedesktop.PackageKit',
            '/org/freedesktop/PackageKit'
        ), dbus.PROPERTIES_IFACE)
        return proxy.Get('org.freedesktop.PackageKit', key)
    
    def run(self, command, *args):
        def run_it():
            self.tid = self.pk_control.GetTid()
            log.msg('[%s] New transaction' % self.tid)
            self.transaction = dbus.Interface(self.dbus_system.get_object(
                'org.freedesktop.PackageKit',
                self.tid,
                False
            ), 'org.freedesktop.PackageKit.Transaction')
            self.properties = dbus.Interface(self.transaction, dbus_interface=dbus.PROPERTIES_IFACE)
            for s in dir(self):
                if getattr(self, s) != None and s.startswith('_s_'):
                    self.sigs.append(self.transaction.connect_to_signal(s.replace('_s_', ''), getattr(self, s)))
            getattr(self.transaction, command)(*args)
        
        while True:
            try:
                run_it()
                break
            except (AttributeError, dbus.DBusException), e:
                if self.pk_control == None or (hasattr(e, '_dbus_error_name') and e._dbus_error_name in self.known_errors):
                    # first initialization (lazy) or timeout
                    if self.pk_control != None:
                        log.msg('Warning, starting a new dbus system because of: %s' % e._dbus_error_name)
                        self.dbus_system.set_exit_on_disconnect(False)
                        self.dbus_system.close()
                        self.dbus_system = dbus.SystemBus()
                    self.pk_control = dbus.Interface(self.dbus_system.get_object(
                        'org.freedesktop.PackageKit',
                        '/org/freedesktop/PackageKit',
                        False
                    ), 'org.freedesktop.PackageKit')
                    continue
                else:
                    raise
                    self.handler.send_meta(OPERATION_FAILED, request=self.request)
                    break
    
    #def _s_Category(self, parent_id, cat_id, name, summary, icon):
    #    log.msg('[%s] Category' % self.tid)
    
    #def _s_Details(self, package_id, license, group, detail, url, size):
    #    log.msg('Details')
    
    def _s_ErrorCode(self, code, details):
        log.msg('ErrorCode [%s] [%s]' % (code, details))
        if hasattr(self, 'ErrorCode'):
            return getattr(self, 'ErrorCode')(code, details)
    
    #def _s_Files(self, package_id, file_list):
    #    log.msg('Files')
    
    def _s_Finished(self, exit, runtime):
        log.msg('[%s] Finished [%s] [%s]' % (self.tid, exit, runtime))
        if exit == 'success':
            self.handler.send_meta(OPERATION_SUCCESSFUL, request=self.request)
        else:
            self.handler.send_meta(OPERATION_FAILED, request=self.request)
        
    #def _s_Message(self, type, details):
    #    log.msg('Message')
    
    #def _s_Package(self, info, package_id, summary):
    #    log.msg('[%s] Package [%s] [%s] [%s]' % (self.tid, info, package_id, summary))
    
    #def _s_RepoDetail(self, repo_id, description, enabled):
    #    log.msg('RepoDetail')
    
    #def _s_RepoSignatureRequired(self, package_id, repository_name, key_url, key_userid, key_id, key_fingerprint, key_timestamp, type):
    #    plog.msg('RepoSignatureRequired')
    
    #def _s_EulaRequired(self, eula_id, package_id, vendor_name, license_agreement):
    #    log.msg('EulaRequired')
    
    #def _s_MediaChangeRequired(self, media_type, media_id, media_text):
    #    log.msg('MediaChangeRequired')
    
    #def _s_RequireRestart(self, type, package_id):
    #    log.msg('RequireRestart')
    
    #def _s_Transaction(self, old_tid, timespec, succeeded, role, duration, data, uid, cmdline):
    #    log.msg('Transaction')
    
    #def _s_UpdateDetail(self, package_id, updates, obsoletes, vendor_url, bugzilla_url, cve_url, restart, update_text, changelog, state, issued, updated):
    #    log.msg('UpdateDetail')
    
    #def _s_DistroUpgrade(self, type, name, summary):
    #    log.msg('DistroUpgrade')
    
    def _s_Changed(self):
        # TODO: Do a GetAll to limit the number of DBus call
        try:
            status = self.properties.Get('org.freedesktop.PackageKit.Transaction', 'Status')
        except dbus.DBusException, e:
            log.msg('Warning, DBus error: %s' % e._dbus_error_name)
            return self.handler.send_meta(OPERATION_FAILED, request=self.request)
        try:
            progress = self.properties.Get('org.freedesktop.PackageKit.Transaction', 'Percentage')
        except dbus.DBusException, e:
            log.msg('Warning, DBus error: %s' % e._dbus_error_name)
            return self.handler.send_meta(OPERATION_FAILED, request=self.request)
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
        for sig in self.sigs:
            sig.remove()

class PackagesManager(LinuxBaseManager):
    _auto_updating = False
    _transactions = {}
    
    def __init__(self):
        log.msg('================== INIT PackagesManager ==================')
        
    def _auto_update(self, request, handler):
        if self._auto_updating == True:
            log.msg('Another auto update is in progress, cancelling this attempt')
        else:
            rc_transaction = Transaction(None, None)
            def rc_finished(exit, runtime):
                if exit == 'success':
                    gu_result = []
                    def gu_get_package(i, p_id, summary):
                        gu_result.append(str(p_id))
                    def gu_finished(exit, runtime):
                        if exit == 'success':
                            if not len(gu_result):
                                self._auto_updating = False
                                handler.send_data(request, {'updates_ready': False})
                                return log.msg('Nothing to Autoupdate')
                            dp_transaction = Transaction(None, None)
                            def dp_finished(exit, runtime):
                                handler.send_data(request, {'updates_ready': True})
                                log.msg('Autoupdate finished')
                                self._auto_updating = False
                            dp_transaction._s_Finished = dp_finished
                            dp_transaction._s_Changed = None
                            dp_transaction.run('DownloadPackages', gu_result)
                        else:
                            log.msg('Autoupdate aborted')
                            self._auto_updating = False
                    gu_transaction = Transaction(None, None)
                    gu_transaction._s_Package = gu_get_package
                    gu_transaction._s_Finished = gu_finished
                    gu_transaction._s_Changed = None
                    gu_transaction.run('GetUpdates', 'installed')
                else:
                    self._auto_updating = False
                    log.msg('Autoupdate aborted')
            rc_transaction._s_Finished = rc_finished
            rc_transaction._s_Changed = None
            network_state = rc_transaction.get_property('NetworkState')
            if network_state != 'offline':
                self._auto_updating = True
                log.msg('Sarting an autoupdate')
                rc_transaction.run('RefreshCache', True)
            else:
                log.msg('No internet connection, not starting the autoupdate')
        reactor.callLater(AUTO_UPDATE_INTERVAL, partial(self._auto_update, request, handler))
    
    def _install_remove(self, method, request, handler, package):
        result = []
        def resolve_package(i, p_id, summary):
            result.append(str(p_id))
        def resolve_finished(exit, runtime):
            if exit == 'success' and len(result):
                t = Transaction(request, handler)
                if method == 'InstallPackages':
                    t.run(method, False, result)
                elif method == 'RemovePackages':
                    t.run(method, result, False, True)
            else:
                return handler.send_meta(OPERATION_FAILED, request=request)

        t = Transaction(request, handler)
        t._s_Package = resolve_package
        t._s_Finished = resolve_finished
        t._s_Changed = None
        if package == 'opera-jolicloud':
            package = ['opera-jolicloud', 'opera']
        else:
            package = [package]
        t.run('Resolve', 'none', package)
        # apt-cache show `dpkg-query -W --showformat='${Package}=${Version}' gajim` | egrep '(Package|Version|Architecture|Filename)'
    
    def install(self, request, handler, package):
        self._install_remove('InstallPackages', request, handler, package)
    
    def remove(self, request, handler, package):
        if package == 'nickel-codecs-ffmpeg-nonfree':
            return self._install_remove('InstallPackages', request, handler, 'nickel-codecs-ffmpeg')
        self._install_remove('RemovePackages', request, handler, package)
    
    def list_(self, request, handler):
        # PackageKit is buggy, it crashs when doing a GetPackages:
        # (jerem: ~) pkcon get-packages 
        # Getting packages              [=========================]         
        # Loading cache                 [=========================]         
        # Querying                      [                       ==]         The daemon crashed mid-transaction!
        # (jerem: ~/Downloads/PackageKit-0.6.10/src) sudo ./packagekitd --verbose
        # 10:30:12	PackageKit          auto-setting status based on info available
        # 10:30:12	PackageKit          emit package available, loadwatch;1.0+1.1alpha1-5;i386;maverick, Run a program using only idle cycles
        # terminate called after throwing an instance of 'std::logic_error'
        #   what():  basic_string::_S_construct NULL not valid
        # Aborted
        # (jerem: ~/Downloads/PackageKit-0.6.10/src)
        #        res = []
        #        def get_package(i, p_id, summary):
        #            name = p_id.split(';')[0]
        #            log.msg('[%s]' % name)
        #            res.append({'name': name})
        #        def finished(exit, runtime):
        #            log.msg('List Finished [%s] [%s]' % (exit, runtime))
        #            handler.send_data(request, res)
        #            if exit == 'success':
        #                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
        #            else:
        #                handler.send_meta(OPERATION_FAILED, request=request)
        #        t = Transaction(request, handler)
        #        t._s_Package = get_package
        #        t._s_Finished = finished
        #        t.run('GetPackages', 'installed')
        class DpkgGetSelecions(protocol.ProcessProtocol):
            out = ''
            
            def outReceived(self, data):
                self.out += data
            
            def errReceived(self, data):
                log.msg("[DpkgGetSelecions] [stderr] %s" % data)
            
            def processEnded(self, status_object):
                res = []
                for p in self.out.split('\n'):
                    p = p.strip()
                    if len(p):
                        p, status = p.split(':')
                        if status.startswith('install'):
                            res.append({'name': p})
                handler.send_data(request, res)
                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
                log.msg("[DpkgGetSelecions] [processEnded] status = %d" % status_object.value.exitCode)
        reactor.spawnProcess(
            DpkgGetSelecions(),
            '/usr/bin/dpkg-query',
            ['dpkg-query', '-W', '--showformat=${Package}:${Status}\n']
        )
    
    def check_updates(self, request, handler, force_reload=True):
        t = Transaction(request, handler)
        t.run('RefreshCache', force_reload)
    
    def list_updates(self, request, handler):
        result = {}
        def get_package(info, package_id, summary):
            result[str(package_id)] = {
                'name': str(package_id).split(';')[0],
                'summary': str(summary),
                'info': str(info),
                'ver': str(package_id).split(';')[1]
                # TODO: Size
            }
        def finished(exit, runtime):
            if exit == 'success':
                handler.send_data(request, result.values())
                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
            else:
                handler.send_meta(OPERATION_FAILED, request=request)
        t = Transaction(request, handler)
        t._s_Package = get_package
        t._s_Finished = finished
        t._s_Changed = None
        t.run('GetUpdates', 'installed')

    def perform_updates(self, request, handler):
        t = Transaction(request, handler)
        t.run('UpdateSystem', False)

    def event_register(self, request, handler, event):
        if event == 'packages/auto_update':
            reactor.callLater(AUTO_UPDATE_INTERVAL, partial(self._auto_update, request, handler))

packagesManager = PackagesManager()

