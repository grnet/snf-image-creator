# -*- coding: utf-8 -*-
#
# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

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
