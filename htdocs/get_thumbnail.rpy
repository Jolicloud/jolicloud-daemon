#!/usr/bin/env python

import os
import cgi
import gio

from gnome import ui

from twisted.web import server
from twisted.web.resource import Resource
from twisted.internet import defer, threads

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

class ThumbnailResource(Resource):
    def render_GET(self, request):
        
        path = cgi.escape(request.args.get('path', ['/'])[0])
        root = cgi.escape(request.args.get('root', ['home'])[0])
        
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
            request.setHeader('Content-type', 'image/png')
            request.write(result)
            request.finish()
        
        def generate_thumbnail_blocking(file, info):
            tf = ui.ThumbnailFactory(ui.THUMBNAIL_SIZE_NORMAL)
            thumb = None
            if tf.can_thumbnail(file.get_uri(), info.get_content_type(), info.get_modification_time()):
                thumb = tf.generate_thumbnail(file.get_uri(), info.get_content_type())
                if thumb:
                    tf.save_thumbnail(thumb, file.get_uri(), info.get_modification_time())
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
                            request.write('error 2')
                            request.finish()
                            return
                        send_contents(gio.File(ui.thumbnail_path_for_uri(file.get_uri(), ui.THUMBNAIL_SIZE_NORMAL)))
                    threads.deferToThread(generate_thumbnail_blocking, file, info).addCallback(get_thumb)
            except gio.Error, e: # Path does not exist?
                request.write('error 1')
                request.write('%s' % e)
                request.finish()
        
        current = gio.File('%s/%s' % (root, path.strip('/')))
        current.query_info_async('standard::content-type,thumbnail::path,time::modified,standard::content-type', callback=info_cb)
        return server.NOT_DONE_YET

resource = ThumbnailResource()
