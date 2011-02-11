#!/usr/bin/python

import glob
from distutils.core import setup

setup(
    name='jolicloud-daemon',
    version='1.2.1',
    license='GPL v2',
    author='Jolicloud Developers',
    author_email='developers@jolicloud.org',
    url='http://www.jolicloud.com',
    packages=[
        'jolicloud_daemon',
        'jolicloud_daemon/managers',
        'jolicloud_daemon/jolidaemon'
    ],
    scripts=['jolicloud-daemon'],
    data_files=[
        ('share/jolicloud-daemon/icons', glob.glob('icons/*.png')),
        ('share/jolicloud-daemon/htdocs', glob.glob('htdocs/*.html') + glob.glob('htdocs/*.css')),
        ('share/jolicloud-daemon/htdocs/cgi-bin', glob.glob('htdocs/cgi-bin/*.py')),
        ('share/jolicloud-daemon/htdocs/tests', glob.glob('htdocs/tests/*.html')),
        ('lib/jolicloud-daemon/utils', glob.glob('utils/*')),
        ('share/polkit-1/actions', glob.glob('polkit/*.policy')),
        ('/var/lib/polkit-1/localauthority/10-vendor.d', glob.glob('polkit/*.pkla')),
        ('/etc/apt/apt.conf.d', glob.glob('apt.conf.d/*'))
    ],
    package_data={'jolicloud_daemon/managers': ['dropin.cache']}
)
