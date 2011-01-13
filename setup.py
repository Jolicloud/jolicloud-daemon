#!/usr/bin/python

import glob
from distutils.core import setup

setup(
    name='jolicloud-pkg-daemon',
    version='1.1.20',
    license='GPL v2',
    author='Jolicloud Developers',
    author_email='developers@jolicloud.org',
    url='http://www.jolicloud.com',
    packages=[
        'jolicloud_pkg_daemon',
        'jolicloud_pkg_daemon/managers',
        'jolicloud_pkg_daemon/jolidaemon'
    ],
    scripts=['jolicloud-pkg-daemon'],
    data_files=[
        ('share/jolicloud-pkg-daemon/htdocs', glob.glob('htdocs/*')),
        ('lib/jolicloud-pkg-daemon/utils', glob.glob('utils/*')),
        ('share/polkit-1/actions', glob.glob('polkit/*.policy')),
        ('/var/lib/polkit-1/localauthority/10-vendor.d', glob.glob('polkit/*.pkla'))
    ],
    package_data={'jolicloud_pkg_daemon/managers': ['dropin.cache']}
)
