#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 GRNET S.A.
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

import image_creator

from setuptools import setup, find_packages

setup(
    name='snf_image_creator',
    version=image_creator.__version__,
    description='Command line tool for creating images',
    long_description=open('README.md').read(),
    url='https://code.grnet.gr/projects/snf-image-creator',
    author="Synnefo development team",
    author_email="synnefo-devel@googlegroups.com",
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['sh', 'ansicolors', 'progress>=1.0.2'],
    entry_points={
        'console_scripts': [
                'snf-mkimage = image_creator.main:main',
                'snf-image-creator = image_creator.dialog_main:main']
    }
)
# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
