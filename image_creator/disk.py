#!/usr/bin/env python

import losetup
import stat
import os
import tempfile
import uuid
import re
import sys
import guestfs

from pbs import dmsetup
from pbs import blockdev
from pbs import dd

class DiskError(Exception): pass

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
        while len(self._devices):
            device = self._devices.pop()
            device.destroy()
            
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
        # Create 1G cow file
        dd('if=/dev/null', 'of=%s' % cow, 'bs=1k' ,'seek=%d' % (1024*1024))
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

        new_device = DiskDevice("/dev/mapper/%s" % snapshot)
        self._devices.append(new_device)
        return new_device

    def destroy_device(self, device):
        self._devices.remove(device)
        device.destroy()

class DiskDevice(object):

    def __init__(self, device, bootable = True):
        self.device = device
        self.bootable = bootable

        self.g = guestfs.GuestFS()
        self.g.add_drive_opts(device, readonly = 0)
        self.g.launch()
        roots = self.g.inspect_os()
        if len(roots) == 0:
            raise DiskError("No operating system found")
        if len(roots) > 1:
            raise DiskError("Multiple operating systems found")

        self.root = roots[0]
    
    def destroy(self):
        self.g.umount_all()
        self.g.sync()
        # Close the guestfs handler
        del self.g
    
    def get_image_metadata(self):
        meta = {}
        meta["OSFAMILY"] = self.g.inspect_get_type(self.root)
        meta["OS"] = self.g.inspect_get_distro(self.root)
        meta["description"] = self.g.inspect_get_product_name(self.root)
        return meta

    def mount(self):
        mps = g.inspect_get_mountpoints(self.root)
        # Sort the keys to mount the fs in a correct order.
        # / should be mounted befor /boot, etc
        def compare (a, b):
            if len(a[0]) > len(b[0]): return 1
            elif len(a[0]) == len(b[0]): return 0
            else: return -1
        mps.sort(compare)
        for mp, dev in mps:
            try:
                self.g.mount(dev, mp)
            except RuntimeError as msg:
                print "%s (ignored)" % msg

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
