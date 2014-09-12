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
import time
import os
import re
import json
import tempfile


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


def image_info(image):
    """Returns information about an image file"""

    qemu_img = get_command('qemu-img')
    info = qemu_img('info', '--output', 'json', image)
    return json.loads(str(info))


def create_snapshot(source, target_dir):
    """Returns a qcow2 snapshot of an image file"""

    qemu_img = get_command('qemu-img')
    snapfd, snap = tempfile.mkstemp(prefix='snapshot-', dir=target_dir)
    os.close(snapfd)
    qemu_img('create', '-f', 'qcow2', '-o',
             'backing_file=%s' % os.path.abspath(source), snap)
    return snap


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


def virtio_versions(virtio_state):
    """Returns the versions of the drivers defined by the virtio state"""

    ret = {}
    for name, infs in virtio_state.items():
        driver_ver = [drv['DriverVer'].split(',', 1) if 'DriverVer' in drv
                      else [] for drv in infs.values()]
        vers = [v[1] if len(v) > 1 else " " for v in driver_ver]
        ret[name] = "<not found>" if len(infs) == 0 else ", ".join(vers)

    return ret


class QemuNBD(object):
    """Wrapper class for the qemu-nbd tool"""

    def __init__(self, image):
        """Initialize an instance"""
        self.image = image
        self.device = None
        self.pattern = re.compile('^nbd\d+$')
        self.modprobe = get_command('modprobe')
        self.qemu_nbd = get_command('qemu-nbd')

    def _list_devices(self):
        """Returns all the NBD block devices"""
        return set([d for d in os.listdir('/dev/') if self.pattern.match(d)])

    def connect(self, ro=True):
        """Connect the image to a free NBD device"""
        devs = self._list_devices()

        if len(devs) == 0:  # Is nbd module loaded?
            self.modprobe('nbd', 'max_part=16')
            # Wait a second for /dev to be populated
            time.sleep(1)
            devs = self._list_devices()
            if len(devs) == 0:
                raise FatalError("/dev/nbd* devices not present!")

        # Ignore the nbd block devices that are in use
        with open('/proc/partitions') as partitions:
            for line in iter(partitions):
                entry = line.split()
                if len(entry) != 4:
                    continue
                if entry[3] in devs:
                    devs.remove(entry[3])

        if len(devs) == 0:
            raise FatalError("All NBD block devices are busy!")

        device = '/dev/%s' % devs.pop()
        args = ['-c', device]
        if ro:
            args.append('-r')
        args.append(self.image)

        self.qemu_nbd(*args)
        self.device = device
        return device

    def disconnect(self):
        """Disconnect the image from the connected device"""
        assert self.device is not None, "No device connected"

        self.qemu_nbd('-d', self.device)
        self.device = None

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
