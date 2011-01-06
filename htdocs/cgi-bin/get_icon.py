#!/usr/bin/env python

# Licensed under the GNU General Public License Version 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# (c) 2010
#    Jolicloud SAS.
#    Jeremy Bethmont <jerem@jolicloud.org>

#import cgitb
#cgitb.enable()
import cgi
import os
import sys
import base64
import time

import xdg.DesktopEntry
import xdg.Menu
import xdg.IconTheme

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

def get():
    form = cgi.FieldStorage()
    if not form.getvalue('desktop'):
        print 'Content-type: text/html'
        print
        print 'error'
        exit() # TODO 500 Error

    entry = xdg.DesktopEntry.DesktopEntry()
    try:
        entry.parse(cgi.escape(form.getvalue('desktop')))
    except:
        return

    icon_name = entry.getIcon()
    for theme in ['Jolicloud', 'gnome-jolicloud', 'Humanity-Dark', 'Humanity', 'gnome-colors-common', 'gnome']:
        icon_path = xdg.IconTheme.getIconPath(icon_name, size=128, theme=theme, extensions=['svg', 'png'])
        if icon_path:
            break

    if (icon_path and os.path.isfile(icon_path)):
        fd = open(icon_path, 'rb')
        file = fd.read()
        
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
            print 'Content-type: %s' % type
            print 'Cache-Control: max-age=%d' % 604800 # one week
            print 'Last-Modified: %s' % date_time_string()
            print 'Date: %s' % date_time_string()
            #print 'Expires: %s' % date_time_string(time.time() + 604800)
            #print 'X-Desktop: %s' % cgi.escape(form.getvalue('desktop'))
            #print 'X-IconName: %s' % icon_name
            #print 'X-IconPath: %s' % icon_path
            #print 'X-Env: %s' % os.environ
            #import random
            #random.seed()
            #print 'X-Random: %f' % random.random()
            print
            print file
        fd.close()

get()
