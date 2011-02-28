#!/usr/bin/env python

import os
import sys
import base64
import time

import cairo
import rsvg

import xdg.DesktopEntry
import xdg.Menu
import xdg.IconTheme

from urllib import unquote

from twisted.web import server
from twisted.web.resource import Resource
from twisted.internet import reactor

weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def date_time_string(timestamp=None):
    """Return the current date and time formatted for a message header."""
    if timestamp is None:
        timestamp = time.time()
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
            weekdayname[wd],
            day, monthname[month], year,
            hh, mm, ss)
    return s

def convert_svg_to_png(ifile, ofile, maxwidth=0, maxheight=0):
    svg = rsvg.Handle(ifile)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, svg.props.width, svg.props.height)
    context = cairo.Context(surface)
    svg.render_cairo(context)
    surface.write_to_png(ofile)
    surface.finish()

def get_icon_blocking(request):
    if not request.args.get('desktop', None):
        request.setHeader('Content-type', 'text/html')
        request.write('error 1')
        request.finish()
    
    entry = xdg.DesktopEntry.DesktopEntry()
    try:
        entry.parse(unquote(request.args['desktop'][0]))
    except Exception, e:
        request.setHeader('Content-type', 'text/html')
        request.write('error 2<br/>%s' % e)
        request.finish()
    
    icon_name = entry.getIcon()
    for theme in ['Jolicloud', 'gnome-jolicloud', 'Humanity-Dark', 'Humanity', 'gnome-colors-common', 'gnome']:
        icon_path = xdg.IconTheme.getIconPath(icon_name, size=128, theme=theme, extensions=['svg', 'png'])
        if icon_path:
            break
    
    if (icon_path and os.path.isfile(icon_path)):
        fd = open(icon_path, 'rb')
        file = fd.read()
        fd.close()
        
        format_detected = True
        if (file[:4] == '\x89PNG'):
            type = 'image/png'
        elif (icon_path.endswith('.svg')):
            type = 'image/svg+xml'
        elif (file[:2] == '\xff\xd8'):
            type = 'image/jpeg'
        elif (file[:2] == 'BM'):
            type = 'image/bmp'
        elif (file[:6] == 'GIF87a' or file[:6] == 'GIF89a'):
            type = 'image/gif'
        elif (file[:4] == 'MM\x00\x2a' or file[:4] == 'II\x2a\x00'):
            type = 'image/tiff'
        elif (icon_path.endswith('.ico')):
            type = 'image/x-icon'
        else:
            format_detected = False
        
        if format_detected:
            request.setHeader('Content-type', type)
            request.setHeader('Cache-Control', 'max-age=%d' % 604800)
            request.setHeader('Last-Modified', date_time_string())
            request.setHeader('Date', date_time_string())
            if type == 'image/svg+xml':
                request.setHeader('Content-type', 'image/png')
                convert_svg_to_png(icon_path, request)
                request.finish()
            else:
                request.write(file)
                request.finish()

class IconResource(Resource):
    def render_GET(self, request):
        reactor.callFromThread(get_icon_blocking, request)
        return server.NOT_DONE_YET

resource = IconResource()
