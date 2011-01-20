#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import dbus
import urllib2
import subprocess

from functools import partial

from twisted.python import log
from twisted.internet import reactor, protocol
from twisted.web.client import _makeGetterFactory, HTTPClientFactory

from jolicloud_daemon.plugins import LinuxSessionManager

def myGetPage(url, contextFactory=None, *args, **kwargs):
    return _makeGetterFactory(
        url,
        HTTPClientFactory,
        contextFactory=contextFactory,
        *args, **kwargs)

class NetworkManager(LinuxSessionManager):
    
    _NS = 'org.freedesktop.NetworkManager'
    _CONNECTION_ACTIVE_NS = 'org.freedesktop.NetworkManager.Connection.Active'
    _DEVICE_NS = 'org.freedesktop.NetworkManager.Device'
    _DEVICE_WIRELESS_NS = 'org.freedesktop.NetworkManager.DeviceWireless'
    _ACCESS_POINT_NS = 'org.freedesktop.NetworkManager.AccessPoint'

    _states = [
        'UNKNOWN',
        'ASLEEP',
        'CONNECTING',
        'CONNECTED',
        'DISCONNECTED'
    ]

    _NM_802_11_AP_SEC = {
        'NM_802_11_AP_SEC_NONE': 0x0,
        'NM_802_11_AP_SEC_PAIR_WEP40': 0x1,
        'NM_802_11_AP_SEC_PAIR_WEP104': 0x2,
        'NM_802_11_AP_SEC_PAIR_TKIP': 0x4,
        'NM_802_11_AP_SEC_PAIR_CCMP': 0x8,
        'NM_802_11_AP_SEC_GROUP_WEP40': 0x10,
        'NM_802_11_AP_SEC_GROUP_WEP104': 0x20,
        'NM_802_11_AP_SEC_GROUP_TKIP': 0x40,
        'NM_802_11_AP_SEC_GROUP_CCMP': 0x80,
        'NM_802_11_AP_SEC_KEY_MGMT_PSK': 0x100,
        'NM_802_11_AP_SEC_KEY_MGMT_802_1X': 0x200
    }
        
    def __init__(self):
        self.system_bus = dbus.SystemBus()
        self._network_obj = self.system_bus.get_object(
            self._NS,
            '/org/freedesktop/NetworkManager'
        )
        self._network_obj.connect_to_signal("StateChanged", self._state_changed)
    
    def _state_changed(self, state):
        #self.emit('state_changed', {'state': self._states[int(state)]})
        if int(state) == 3: # Connected
            self._is_on_public_wifi_with_auth_redirection()
    
    def _is_on_public_wifi_with_auth_redirection(self):
        """
            Ugly hack to fix public WiFi bug in Chromium on Linux.
        """
        on_public_wifi = False
        for connection in self._network_obj.Get(self._NS, 'ActiveConnections'):
            o_ca = self.system_bus.get_object(self._NS, connection)
            if o_ca.Get(self._CONNECTION_ACTIVE_NS, 'Default') == 1:
                for device in o_ca.Get(self._CONNECTION_ACTIVE_NS, 'Devices'):
                    o_d = self.system_bus.get_object(self._NS, device)
                    device_type = o_d.Get(self._DEVICE_NS, 'DeviceType')
                    if device_type == 2:
                        access_point = o_d.Get(self._DEVICE_WIRELESS_NS, 'ActiveAccessPoint')
                        o_ap = self.system_bus.get_object(self._NS, access_point)
                        rsn_flags = o_ap.Get(self._ACCESS_POINT_NS, 'RsnFlags')
                        wpa_flags = o_ap.Get(self._ACCESS_POINT_NS, 'WpaFlags')
                        on_public_wifi = True
                        for key in self._NM_802_11_AP_SEC:
                            if self._NM_802_11_AP_SEC[key] & rsn_flags or self._NM_802_11_AP_SEC[key] & wpa_flags:
                                on_public_wifi = False
        
        if on_public_wifi:
            log.msg('Connected to a public WiFi')
            def getpage_callback(factory, result):
                if 'joli-length' in factory.response_headers and \
                   (len(result) == int(factory.response_headers['joli-length'][0]) == int(factory.response_headers['content-length'][0])):
                    log.msg('Internet connection seems to work')
                else:
                    log.msg('Internet connections seems to be redirected. Launching wifi-connect.')
                    reactor.spawnProcess(
                        protocol.ProcessProtocol(),
                        '/usr/bin/setsid', # setsid - run a program in a new session
                        ['setsid', '/usr/lib/jolicloud-daemon/utils/wifi-connect'],
                        env=os.environ
                    )
            factory = myGetPage('http://ping.jolicloud.com', timeout=30)
            factory.deferred.addCallback(partial(getpage_callback, factory))
            response = urllib2.urlopen('http://ping.jolicloud.com')

    def on_cellular_network(self, request, handler):
        """
        We check if the default connection use one of the following DeviceType:
            
         - NM_DEVICE_TYPE_GSM = 3
                The device is a GSM-based cellular WAN device.
         - NM_DEVICE_TYPE_CDMA = 4
                The device is a CDMA/IS-95-based cellular WAN device.
        """
        for connection in self._network_obj.Get(self._NS, 'ActiveConnections'):
            o_ca = self.system_bus.get_object(self._NS, connection)
            if o_ca.Get(self._CONNECTION_ACTIVE_NS, 'Default') == 1:
                for device in o_ca.Get(self._CONNECTION_ACTIVE_NS, 'Devices'):
                    o_d = self.system_bus.get_object(self._NS, device)
                    device_type = o_d.Get(self._DEVICE_NS, 'DeviceType')
                    if device_type in (3, 4):
                        return True
        return False

networkManager = NetworkManager()
