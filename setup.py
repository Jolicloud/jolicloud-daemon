#!/usr/bin/python

import glob
from distutils.core import setup

setup(
    name='jolicloud-pkg-daemon',
    version='0.1',
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
        ('share/jolicloud-pkg-daemon/htdocs', glob.glob('htdocs/*'))
    ],
    package_data={'jolicloud_pkg_daemon/managers': ['dropin.cache']}
)
