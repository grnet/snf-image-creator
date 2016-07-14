#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2016 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os.path import dirname, abspath, join
from setuptools import setup, find_packages
from imp import load_source

CWD = dirname(abspath(__file__))
README = join(CWD, 'README.md')
VERSION = join(CWD, 'image_creator', 'version.py')

setup(
    name='snf_image_creator',
    version=getattr(load_source('version', VERSION), "__version__"),
    description='Command line tool for creating images',
    long_description=open(README).read(),
    url='https://github.com/grnet/snf-image',
    download_url='https://pypi.python.org/pypi/snf_image_creator',
    author='Synnefo development team',
    author_email='synnefo-devel@googlegroups.com',
    maintainer='Synnefo development team',
    maintainer_email='synnefo-devel@googlegroups.com',
    license='GNU GPLv3',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['sh', 'ansicolors', 'progress>=1.0.2', 'kamaki>=0.9',
                      'argparse'],
    # Unresolvable dependencies:
    #   pysendfile|py-sendfile, hivex, guestfs, parted, rsync,
    entry_points={
        'console_scripts': [
                'snf-mkimage = image_creator.main:main',
                'snf-image-creator = image_creator.dialog_main:main']
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Console :: Curses',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7'],
    keywords='cloud IaaS OS images'
)
# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
