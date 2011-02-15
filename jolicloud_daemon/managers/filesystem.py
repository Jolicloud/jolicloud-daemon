#!/usr/bin/env python

__author__ = 'Jeremy Bethmont'

import os
import sys
import base64
import gio

from datetime import datetime

from gnome import ui

from twisted.internet import reactor, protocol, defer, threads

from jolicloud_daemon.plugins import LinuxSessionManager
from jolicloud_daemon.enums import *

# http://blogs.gnome.org/jamesh/2009/01/06/twisted-gio/
def file_read_deferred(file, io_priority=0, cancellable=None):
    d = defer.Deferred()
    def callback(file, async_result):
        try:
            in_stream = file.read_finish(async_result)
        except gio.Error:
            d.errback()
        else:
            d.callback(in_stream)
    file.read_async(callback, io_priority, cancellable)
    return d

def input_stream_read_deferred(in_stream, count, io_priority=0, cancellable=None):
    d = defer.Deferred()
    def callback(in_stream, async_result):
        try:
            bytes = in_stream.read_finish(async_result)
        except gio.Error:
            d.errback()
        else:
            d.callback(bytes)
    # the argument order seems a bit weird here ...
    in_stream.read_async(count, callback, io_priority, cancellable)
    return d

class FilesystemManager(LinuxSessionManager):
    
    _infos = 'standard::type,standard::size,standard::content-type,time::modified,thumbnail::path'
    
    def list_(self, request, handler, path='/', root='home'):
        vanilla_root = root
        if root == 'home' or root == 'HOME':
            root = os.getenv('HOME')
        
        def format_path(f):
            if len(root) and f.startswith(root):
                return f[len(root):]
            return f
        
        def info_cb(file, result):
            try:
                info = file.query_info_finish(result)
                result = {
                    'root': vanilla_root,
                    'path': format_path(file.get_path()),
                    'modified': datetime.fromtimestamp(info.get_modification_time()).strftime('%a, %d %b %Y %H:%M:%S %Z'),
                    'mime_type': info.get_content_type(),
                    'thumbnail': True if info.get_attribute_as_string('thumbnail::path') else False,
                }
                if info.get_file_type() == gio.FILE_TYPE_DIRECTORY:
                    result['is_dir'] = True
                    result['bytes'] = 0
                    result['contents'] = []
                    def get_contents(c_file, c_result):
                        c_infos = c_file.enumerate_children_finish(c_result)
                        for c_info in c_infos:
                            name = c_info.get_name()
                            path = c_file.get_child(name).get_path()
                            if not name.startswith('.'):
                                result['contents'].append({
                                    'root': vanilla_root,
                                    'path': format_path(path),
                                    'modified': datetime.fromtimestamp(c_info.get_modification_time()).strftime('%a, %d %b %Y %H:%M:%S %Z'),
                                    'is_dir': c_info.get_file_type() == gio.FILE_TYPE_DIRECTORY,
                                    'bytes': c_info.get_size(),
                                    'mime_type': c_info.get_content_type(),
                                    'thumbnail': True if c_info.get_attribute_as_string('thumbnail::path') else False,
                                })
                        handler.send_data(request, result)
                        handler.success(request)
                    file.enumerate_children_async('standard::name,%s' % self._infos, callback=get_contents)
                else:
                    result['is_dir'] = False
                    result['bytes'] = info.get_size()
                    handler.send_data(request, result)
                    handler.success(request)
            except gio.Error, e: # Path does not exist?
                handler.failed(request)
        
        current = gio.File('%s/%s' % (root, path.strip('/')))
        current.query_info_async(self._infos, callback=info_cb)
        
    def open_(self, request, handler, path='/', root='home'):
        
        if root == 'home' or root == 'HOME':
            root = os.getenv('HOME')
        
        f = reactor.spawnProcess(
            protocol.ProcessProtocol(),
            '/usr/bin/setsid', # setsid - run a program in a new session
            ['setsid', 'xdg-open', '%s/%s' % (root, path.strip('/'))],
            env=os.environ
        )
        handler.success(request)
    
    def account(self, request, handler, root='home'):
    
        if root == 'home' or root == 'HOME':
            root = os.getenv('HOME')
        
        def info_cb(file, result):
            try:
                info = file.query_filesystem_info_finish(result)
                result = {
                    'quota': {
                        'total': info.get_attribute_uint64('filesystem::size'),
                        'available': info.get_attribute_uint64('filesystem::free')
                    },
                    'description': info.get_attribute_as_string('filesystem::type')
                }
                handler.send_data(request, result)
                handler.success(request)
            except gio.Error, e: # Path does not exist?
                handler.failed(request)
        
        current = gio.File(root)
        current.query_filesystem_info_async('filesystem::*', callback=info_cb)
    
    def thumbnail(self, request, handler, path='/', root='home'):
        
        if root == 'home' or root == 'HOME':
            root = os.getenv('HOME')
        
        @defer.inlineCallbacks
        def send_contents(file, cancellable=None):
            result = ''
            in_stream = yield file_read_deferred(file, cancellable=cancellable)
            bytes = yield input_stream_read_deferred(in_stream, 4096, cancellable=cancellable)
            while bytes:
                result += bytes
                bytes = yield input_stream_read_deferred(in_stream, 4096, cancellable=cancellable)
            handler.send_data(request, 'data:image/png;base64,%s' % base64.b64encode(result))
            handler.success(request)
        
        def generate_thumbnail_blocking(file, info):
            tf = ui.ThumbnailFactory(ui.THUMBNAIL_SIZE_NORMAL)
            thumb = None
            if tf.can_thumbnail(file.get_uri(), info.get_content_type(), int(info.get_modification_time())):
                thumb = tf.generate_thumbnail(file.get_uri(), info.get_content_type())
                if thumb:
                    tf.save_thumbnail(thumb, file.get_uri(), int(info.get_modification_time()))
            return thumb
        
        def info_cb(file, result):
            try:
                info = file.query_info_finish(result)
                thumbnail_path = info.get_attribute_as_string('thumbnail::path')
                
                if thumbnail_path:
                    send_contents(gio.File(thumbnail_path))
                else:
                    def get_thumb(thumb):
                        if not thumb:
                            return handler.failed(request)
                        send_contents(gio.File(ui.thumbnail_path_for_uri(file.get_uri(), ui.THUMBNAIL_SIZE_NORMAL)))
                    threads.deferToThread(generate_thumbnail_blocking, file, info).addCallback(get_thumb)
            except gio.Error, e: # Path does not exist?
                handler.failed(request)
        
        current = gio.File('%s/%s' % (root, path.strip('/')))
        current.query_info_async('standard::content-type,thumbnail::path,time::modified,standard::content-type', callback=info_cb)
        
filesystemManager = FilesystemManager()
