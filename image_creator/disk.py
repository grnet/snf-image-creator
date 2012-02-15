#!/usr/bin/env python

import losetup
import stat
import os
import tempfile
import uuid
import re
from pbs import dmsetup
from pbs import blockdev
from pbs import dd
from pbs import kpartx
from pbs import mount
from pbs import umount

class Disk(object):

    def __init__(self, source):
        self._cleanup_jobs = []
        self._devices = []
        self.source = source

    def _add_cleanup(self, job, *args):
        self._cleanup_jobs.append((job, args))

    def _losetup(self, fname):
        loop = losetup.find_unused_loop_device()
        loop.mount(fname)
        self._add_cleanup(loop.unmount)
        return loop.device

    def _dir_to_disk(self):
        raise NotImplementedError

    def cleanup(self):
        while len(self._cleanup_jobs):
            job, args = self._cleanup_jobs.pop()
            job(*args)

    def get_device(self):
        sourcedev = self.source
        mode = os.stat(self.source).st_mode
        if stat.S_ISDIR(mode):
            return self._losetup(self._dir_to_disk())
        elif stat.S_ISREG(mode):
            sourcedev = self._losetup(self.source)
        elif not stat.S_ISBLK(mode):
            raise ValueError("Value for self.source is invalid")

        # Take a snapshot and return it to the user
        size = blockdev('--getsize', sourcedev)
        cowfd, cow = tempfile.mkstemp()
        self._add_cleanup(os.unlink, cow)
        dd('if=/dev/zero', 'of=%s' % cow, 'count=%d' % (1024*1024))#(int(size)/4))
        cowdev = self._losetup(cow)

        snapshot = uuid.uuid4().hex
        tablefd, table = tempfile.mkstemp()
        try:
            os.write(tablefd, "0 %d snapshot %s %s n 8" % \
                                        (int(size), sourcedev, cowdev))
            dmsetup('create', snapshot, table)
            self._add_cleanup(dmsetup, 'remove', snapshot)
        finally:
            os.unlink(table)

        new_device = DiskDevice(self, "/dev/mapper/%s" % snapshot)
        self._devices.append(new_device)
        return new_device

class DiskDevice(object):

    def __init__(self, disk, device):
        self.disk = disk
        self.dev = device
        self.partitions_mapped = False
        self.magic_number = uuid.uuid4().hex

    def list_partitions(self):
        output = kpartx("-l", "-p", self.magic_number, self.dev)
        return [ "/dev/mapper/%s" % x for x in
                re.findall('^\S+', str(output), flags=re.MULTILINE)]

    def mount(self, partition):
        if not self.partitions_mapped:
            kpartx("-a", "-p", self.magic_number, self.dev)
            self.disk._cleanup_jobs.append(kpartx, "-d", "-p",
                        self.magic_number, self.dev)
            self.partitions_mapped = True

        targetfd, target = tempfile.mkdtemp()
        try:
            mount(dev, partition)
        except:
            os.rmdir(table)
            raise
        return target

    def unmount(self, partition):
        umount(target)

        mode = os.stat(self.source).st_mode
        if stat.S_ISDIR(mode):
            os.rmdir(target)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
