#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus
import shutil
import grp

from urlparse import urlparse
from functools import partial

from twisted.python import log
from twisted.internet import reactor, protocol
from twisted.web.client import downloadPage

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

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

class PackagesManager(LinuxSessionManager):
    _prefetching = False
    _upgrading = False
    _installing_or_removing = False
    _prefetch_activated = False
    _prefetch_interval = 900
    _prefetch_force = False
    _transactions = {}
    
    _refresh_cache_needed = False
    
    _groups = []
    
    events = ['updates_ready']
    
    def __init__(self):
        for group_id in os.getgroups():
            self._groups.append(grp.getgrgid(group_id).gr_name)
        # Guest and live session.
        self._has_permissions = 'admin' in self._groups and 'guests' not in self._groups and os.getuid() != 999
        
        self._check_refresh_cache_needed()
    
    def _on_cellular_network(self):
        """
        We check if the default connection use one of the following DeviceType:
            
         - NM_DEVICE_TYPE_GSM = 3
                The device is a GSM-based cellular WAN device.
         - NM_DEVICE_TYPE_CDMA = 4
                The device is a CDMA/IS-95-based cellular WAN device.
        """
        system_bus = dbus.SystemBus()
        network_obj = system_bus.get_object(
            'org.freedesktop.NetworkManager',
            '/org/freedesktop/NetworkManager'
        )
        for connection in network_obj.Get('org.freedesktop.NetworkManager', 'ActiveConnections'):
            o_ca = system_bus.get_object('org.freedesktop.NetworkManager', connection)
            if o_ca.Get('org.freedesktop.NetworkManager.Connection.Active', 'Default') == 1:
                for device in o_ca.Get('org.freedesktop.NetworkManager.Connection.Active', 'Devices'):
                   o_d = system_bus.get_object('org.freedesktop.NetworkManager', device)
                   device_type = o_d.Get('org.freedesktop.NetworkManager.Device', 'DeviceType')
                   if device_type in (3, 4):
                        return True
        return False
    
    def _prefetch(self):
        if self._prefetch_activated == False:
            return
        if self._prefetching == True:
            log.msg('Another prefetch is in progress, cancelling this attempt')
        elif self._upgrading == True:
            log.msg('An upgrade is in progress, cancelling this attempt')
        elif self._installing_or_removing == True:
            log.msg('An install or remove is in progress, cancelling this attempt')
        else:
            rc_transaction = Transaction(None, None)
            def rc_finished(exit, runtime):
                gu_result = {}
                def gu_get_package(info, package_id, summary):
                    gu_result[str(package_id)] = {
                        'name': str(package_id).split(';')[0],
                        'summary': str(summary),
                        'info': str(info),
                        'ver': str(package_id).split(';')[1]
                        # TODO: Size
                    }
                def gu_finished(exit, runtime):
                    if exit == 'success':
                        if not len(gu_result):
                            self._prefetching = False
                            log.msg('Nothing to prefetch')
                            self.emit('updates_ready', [])
                            return
                        dp_transaction = Transaction(None, None)
                        def dp_finished(exit, runtime):
                            self._prefetching = False
                            log.msg('Prefetch finished')
                            self.emit('updates_ready', gu_result.values())
                        dp_transaction._s_Finished = dp_finished
                        dp_transaction._s_Changed = None
                        dp_transaction.run('DownloadPackages', gu_result.keys())
                    else:
                        self._prefetching = False
                        log.msg('Prefetch aborted')
                gu_transaction = Transaction(None, None)
                gu_transaction._s_Package = gu_get_package
                gu_transaction._s_Finished = gu_finished
                gu_transaction._s_Changed = None
                gu_transaction.run('GetUpdates', 'installed')
            rc_transaction._s_Finished = rc_finished
            rc_transaction._s_Changed = None
            network_state = rc_transaction.get_property('NetworkState')
            if network_state != 'offline' or self._prefetch_force:
                if self._on_cellular_network() and not self._prefetch_force:
                    log.msg('On cellular network, not starting the prefetch')
                else:
                    self._prefetching = True
                    log.msg('Sarting a prefetch')
                    rc_transaction.run('RefreshCache', True)
            else:
                log.msg('No internet connection, not starting the prefetch')
        reactor.callLater(self._prefetch_interval, self._prefetch)
    
    def _install_remove(self, method, request, handler, package):
        self._installing_or_removing = True
        result = []
        def resolve_package(i, p_id, summary):
            result.append(str(p_id))
        def resolve_finished(exit, runtime):
            if exit == 'success' and len(result):
                t_ir = Transaction(request, handler)
                def ir_finished(exit, runtime):
                    self._installing_or_removing = False
                    log.msg('%s Finished [%s] [%s]' % (method, exit, runtime))
                    if exit == 'success':
                        handler.send_meta(OPERATION_SUCCESSFUL, request=request)
                    else:
                        handler.send_meta(OPERATION_FAILED, request=request)
                t_ir._s_Finished = ir_finished
                if method == 'InstallPackages':
                    t_ir.run(method, False, result)
                elif method == 'RemovePackages':
                    t_ir.run(method, result, False, True)
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
      
    def install(self, request, handler, package, icon_url=None):
        if package.startswith('jolicloud-webapp-'):
            icon_base_path = '%s/.local/share/icons' % os.getenv('HOME')
            icon_path = os.path.join(icon_base_path, '%s.png' % package)
            if not os.path.exists(icon_base_path):
                os.makedirs(icon_base_path)
            # We copy the default icon first, in case we can't download the real icon
            shutil.copy('%sjolicloud-webapp-default.png' % os.environ['JPD_ICONS_PATH'], icon_path)
            def download_callback(result):
                log.msg('Icon saved: ~/.local/share/icons/%s.png' % package)
            downloadPage(str(icon_url), icon_path, timeout=30).addCallback(download_callback)
            return {'status': 'finished'}
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
        if self._refresh_cache_needed == True:
            self._silent_refresh_cache(partial(self.install, request, handler, package, icon_url))
            return
        self._install_remove('InstallPackages', request, handler, package)
    
    def remove(self, request, handler, package):
        if package.startswith('jolicloud-webapp-'):
            path = '%s/.local/share/icons/%s.png' % (os.getenv('HOME'), package)
            if os.path.exists(path):
                os.unlink(path)
            return {'status': 'finished'}
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
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
        if self._refresh_cache_needed == True:
            self._silent_refresh_cache(partial(self.list_, request, handler))
            return
        _silent_remove = self._silent_remove
        class DpkgGetSelecions(protocol.ProcessProtocol):
            out = ''
            
            def outReceived(self, data):
                self.out += data
            
            def errReceived(self, data):
                log.msg("[DpkgGetSelecions] [stderr] %s" % data)
            
            def processEnded(self, status_object):
                res = []
                webapps_to_be_deleted = []
                for p in self.out.split('\n'):
                    p = p.strip()
                    if len(p):
                        p, status = p.split(':')
                        if status.startswith('install'):
                            if p.startswith('jolicloud-webapp-'):
                                webapps_to_be_deleted.append(p)
                            else:
                                res.append({'name': p})
                # We add webapps and remove the legacy packages
                if len(webapps_to_be_deleted):
                    log.msg('Deleting legacy webapps packages: %s' % webapps_to_be_deleted)
                    for webapp in webapps_to_be_deleted:
                        src = '/usr/share/pixmaps/%s.png' % webapp
                        dst = '%s/.local/share/icons/%s.png' % (os.getenv('HOME'), webapp)
                        log.msg('Copying icon %s to %s.' % (src, dst))
                        if not os.path.exists(os.path.dirname(dst)):
                            os.makedirs(os.path.dirname(dst))
                        shutil.copy(src, dst)
                    _silent_remove(webapps_to_be_deleted)
                for icon in os.listdir('%s/.local/share/icons' % os.getenv('HOME')):
                    if icon.startswith('jolicloud-webapp-'):
                        res.append({'name': icon.split('.')[0]})
                handler.send_data(request, res)
                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
                log.msg("[DpkgGetSelecions] [processEnded] status = %d" % status_object.value.exitCode)
        reactor.spawnProcess(
            DpkgGetSelecions(),
            '/usr/bin/dpkg-query',
            ['dpkg-query', '-W', '--showformat=${Package}:${Status}\n']
        )
    
    def check_updates(self, request, handler, force_reload=True):
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
        t = Transaction(request, handler)
        t.run('RefreshCache', force_reload)
    
    def list_updates(self, request, handler):
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
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
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
        if self._refresh_cache_needed == True:
            self._silent_refresh_cache(partial(self.perform_updates, request, handler))
            return
        self._upgrading = True
        def finished(exit, runtime):
            self._upgrading = False
            log.msg('Upgrade Finished [%s] [%s]' % (exit, runtime))
            if exit == 'success':
                handler.send_meta(OPERATION_SUCCESSFUL, request=request)
            else:
                handler.send_meta(OPERATION_FAILED, request=request)
        t = Transaction(request, handler)
        t._s_Finished = finished
        t.run('UpdateSystem', False)
    
    def start_prefetch(self, request, handler, delay=30, interval=900, force=False):
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
        if self._prefetch_activated == False:
            self._prefetch_activated = True
            self._prefetch_interval = interval
            self._prefetch_force = force
            reactor.callLater(delay, self._prefetch)
        handler.success(request)
    
    def stop_prefetch(self, request, handler):
        if not self._has_permissions:
            return handler.send_meta(PERMISSION_DENIED, request)
        if self._prefetch_activated == True:
            self._prefetch_activated = False
        handler.success(request)
    
    def _silent_remove(self, packages):
        result = []
        def resolve_package(i, p_id, summary):
            result.append(str(p_id))
        def resolve_finished(exit, runtime):
            if exit == 'success' and len(result):
                t_r = Transaction(None, None)
                t_r._s_Finished = None
                t_r._s_Changed = None
                t_r.run('RemovePackages', result, False, True)
        t = Transaction(None, None)
        t._s_Package = resolve_package
        t._s_Finished = resolve_finished
        t._s_Changed = None
        t.run('Resolve', 'none', packages)
    
    def _silent_refresh_cache(self, callback=None):
        log.msg('Running a silent RefreshCache')
        def finished(exit, runtime):
            self._refresh_cache_needed = False
            if callback:
                callback()
        t = Transaction(None, None)
        t._s_Changed = None
        t._s_Finished = finished
        t.run('RefreshCache', False)
    
    def _check_refresh_cache_needed(self):
        hosts = []
        def repodetail(repo_id, description, enabled):
            source = description.split(' ')[2]
            if enabled and source.startswith('http'):
                o = urlparse(source)
                if o.hostname and o.hostname not in hosts:
                    hosts.append(o.hostname)
        def finished(exit, runtime):
            self._refresh_cache_needed = False
            for host in hosts:
                found = False
                for file in os.listdir('/var/lib/apt/lists'):
                    if file.startswith(host):
                        found = True
                        break
                if found == False:
                    self._refresh_cache_needed = True
                    log.msg('It seems we need to run a RefreshCache.')
                    return
        t = Transaction(None, None)
        t._s_RepoDetail = repodetail
        t._s_Finished = finished
        t._s_Changed = None
        t.run('GetRepoList', 'installed')

packagesManager = PackagesManager()
