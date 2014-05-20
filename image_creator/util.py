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

"""This module provides various helper functions to be used by other parts of
the package.
"""

import sh
import hashlib
import time
import os
import re


class FatalError(Exception):
    """Fatal Error exception of snf-image-creator"""
    pass


def get_command(command):
    """Return a file system binary command"""
    def find_sbin_command(command, exception):
        search_paths = ['/usr/local/sbin', '/usr/sbin', '/sbin']
        for fullpath in map(lambda x: "%s/%s" % (x, command), search_paths):
            if os.path.exists(fullpath) and os.access(fullpath, os.X_OK):
                return sh.Command(fullpath)
        raise exception

    try:
        return sh.__getattr__(command)
    except sh.CommandNotFound as e:
        return find_sbin_command(command, e)


def get_kvm_binary():
    """Returns the path to the kvm binary and some extra arguments if needed"""

    uname = get_command('uname')
    which = get_command('which')

    machine = str(uname('-m')).strip()
    if re.match('i[3-6]86', machine):
        machine = 'i386'

    binary = which('qemu-system-%s' % machine)

    needed_args = "--enable-kvm",

    if binary is None:
        return which('kvm'), tuple()

    return binary, needed_args


def try_fail_repeat(command, *args):
    """Execute a command multiple times until it succeeds"""
    times = (0.1, 0.5, 1, 2)
    i = iter(times)
    while True:
        try:
            command(*args)
            return
        except sh.ErrorReturnCode:
            try:
                wait = i.next()
            except StopIteration:
                break
            time.sleep(wait)

    raise FatalError("Command: `%s %s' failed" % (command, " ".join(args)))


def free_space(dirname):
    """Compute the free space in a directory"""
    stat = os.statvfs(dirname)
    return stat.f_bavail * stat.f_frsize


class MD5:
    """Represents MD5 computations"""
    def __init__(self, output):
        """Create an MD5 instance"""
        self.out = output

    def compute(self, filename, size):
        """Compute the MD5 checksum of a file"""
        MB = 2 ** 20
        BLOCKSIZE = 4 * MB  # 4MB

        prog_size = ((size + MB - 1) // MB)  # in MB
        progressbar = self.out.Progress(prog_size, "Calculating md5sum", 'mb')
        md5 = hashlib.md5()
        with open(filename, "r") as src:
            left = size
            while left > 0:
                length = min(left, BLOCKSIZE)
                data = src.read(length)
                md5.update(data)
                left -= length
                progressbar.goto((size - left) // MB)

        checksum = md5.hexdigest()
        progressbar.success(checksum)

        return checksum

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
