#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os

from twisted.enterprise import adbapi
from twisted.python import log

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

class Local_storageManager(LinuxSessionManager):
    # http://twistedmatrix.com/documents/current/core/howto/rdbms.html
    # http://twistedmatrix.com/trac/ticket/3629
    
    _CREATE_TABLE = 'CREATE TABLE IF NOT EXISTS storage (key VARCHAR NOT NULL PRIMARY KEY, value TEXT)'
    _CREATE_INDEX = 'CREATE UNIQUE INDEX IF NOT EXISTS idxKey ON storage (key)'
    _SELECT = 'SELECT value FROM storage WHERE key=? LIMIT 1'
    _INSERT = 'INSERT OR REPLACE INTO storage VALUES (?, ?)'
    
    _table_ready = False
    
    def __init__(self):
        try:
            import xdg.BaseDirectory
            self.path = os.path.join(xdg.BaseDirectory.save_config_path('Jolicloud', 'jolicloud-daemon'), 'localstorage.db')
        except ImportError:
            self.path = os.path.join(os.getenv('HOME'), '.config', 'Jolicloud', 'jolicloud-daemon', 'localstorage.db')
        log.msg('Using DB path %s' % self.path)
        self.dbpool = adbapi.ConnectionPool('sqlite3', self.path, check_same_thread=False)
        def get_success(result):
            self._table_ready = True
        def get_error():
            self._table_ready = False
        self.dbpool.runInteraction(self._create_table_and_index).addCallbacks(get_success, get_error)
    
    def _create_table_and_index(self, txn):
        txn.execute(self._CREATE_TABLE)
        txn.execute(self._CREATE_INDEX)
    
    def get_item(self, request, handler, key):
        if self._table_ready == False:
            return handler.failed(request)
        def get_result(result):
            handler.send_data(request, result[0][0] if result else '')
            handler.success(request)
        def get_error():
            handler.failed(request)
        self.dbpool.runQuery(self._SELECT, (key,)).addCallbacks(get_result, get_error)

    def set_item(self, request, handler, key, value):
        if self._table_ready == False:
            return handler.failed(request)
        def get_success(result):
            handler.success(request)
        def get_error():
            handler.failed(request)
        self.dbpool.runQuery(self._INSERT, (key, value)).addCallbacks(get_success, get_error)

#    # Second implementation, using deffered
#    def _create_table(self):
#        return self.dbpool.runQuery(self._CREATE_TABLE)
#    
#    def _create_index(self):
#        return self.dbpool.runQuery(self._CREATE_INDEX)
#    
#    def _get_item(self, key):
#        return self.dbpool.runQuery(self._SELECT, (key,))
#    
#    def _set_item(self, key, value):
#        return self.dbpool.runQuery(self._INSERT, (key, value))
#    
#    def get_item(self, request, handler, key):
#        def get_item_finished(result):
#            if result:
#                result = result[0][0]
#            else:
#                result = ''
#            handler.send_data(request, result)
#        def create_index_finished(ignored):
#            self._get_item(key).addCallback(get_item_finished)
#        def create_table_finished(ignored):
#            self._create_index().addCallback(create_index_finished)
#        self._create_table().addCallback(create_table_finished)
#    
#    def set_item(self, request, handler, key, value):
#        def set_item_finished(result):
#            handler.success(request)
#        def create_index_finished(ignored):
#            self._set_item(key, value).addCallback(set_item_finished)
#        def create_table_finished(ignored):
#            self._create_index().addCallback(create_index_finished)
#        self._create_table().addCallback(create_table_finished)

localstorageManager = Local_storageManager()
