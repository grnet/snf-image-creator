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

from image_creator.util import get_command, warn, progress_generator
from image_creator import FatalError
from clint.textui import indent, puts, colored

import stat
import os
import tempfile
import uuid
import re
import sys
import guestfs
import time


class DiskError(Exception):
    pass

dd = get_command('dd')
dmsetup = get_command('dmsetup')
losetup = get_command('losetup')
blockdev = get_command('blockdev')


class Disk(object):
    """This class represents a hard disk hosting an Operating System

    A Disk instance never alters the source media it is created from.
    Any change is done on a snapshot created by the device-mapper of
    the Linux kernel.
    """

    def __init__(self, source):
        """Create a new Disk instance out of a source media. The source
        media can be an image file, a block device or a directory."""
        self._cleanup_jobs = []
        self._devices = []
        self.source = source

    def _add_cleanup(self, job, *args):
        self._cleanup_jobs.append((job, args))

    def _losetup(self, fname):
        loop = losetup('-f', '--show', fname)
        loop = loop.strip()  # remove the new-line char
        self._add_cleanup(losetup, '-d', loop)
        return loop

    def _dir_to_disk(self):
        raise NotImplementedError

    def cleanup(self):
        """Cleanup internal data. This needs to be called before the
        program ends.
        """
        while len(self._devices):
            device = self._devices.pop()
            device.destroy()

        while len(self._cleanup_jobs):
            job, args = self._cleanup_jobs.pop()
            job(*args)

    def get_device(self):
        """Returns a newly created DiskDevice instance.

        This instance is a snapshot of the original source media of
        the Disk instance.
        """

        puts("Examining source media `%s'" % self.source)
        with indent(4):
            sourcedev = self.source
            mode = os.stat(self.source).st_mode
            if stat.S_ISDIR(mode):
                puts(colored.green('Looks like a directory'))
                return self._losetup(self._dir_to_disk())
            elif stat.S_ISREG(mode):
                puts(colored.green('Looks like an image file'))
                sourcedev = self._losetup(self.source)
            elif not stat.S_ISBLK(mode):
                raise ValueError("Invalid media source. Only block devices, "
                                "regular files and directories are supported.")
            else:
                puts(colored.green('Looks like a block device'))
            #puts()

        # Take a snapshot and return it to the user
        puts("Snapshotting media source")
        with indent(4):
            size = blockdev('--getsize', sourcedev)
            cowfd, cow = tempfile.mkstemp()
            os.close(cowfd)
            self._add_cleanup(os.unlink, cow)
            # Create 1G cow sparse file
            dd('if=/dev/null', 'of=%s' % cow, 'bs=1k', \
                                            'seek=%d' % (1024 * 1024))
            cowdev = self._losetup(cow)
    
            snapshot = uuid.uuid4().hex
            tablefd, table = tempfile.mkstemp()
            try:
                os.write(tablefd, "0 %d snapshot %s %s n 8" % \
                                            (int(size), sourcedev, cowdev))
                dmsetup('create', snapshot, table)
                self._add_cleanup(dmsetup, 'remove', snapshot)
                # Sometimes dmsetup remove fails with Device or resource busy,
                # although everything is cleaned up and the snapshot is not
                # used by anyone. Add a 2 seconds delay to be on the safe side.
                self._add_cleanup(time.sleep, 2)

            finally:
                os.unlink(table)
            puts(colored.green('Done'))
        # puts()
        new_device = DiskDevice("/dev/mapper/%s" % snapshot)
        self._devices.append(new_device)
        new_device.enable()
        return new_device

    def destroy_device(self, device):
        """Destroys a DiskDevice instance previously created by
        get_device method.
        """
        self._devices.remove(device)
        device.destroy()


class DiskDevice(object):
    """This class represents a block device hosting an Operating System
    as created by the device-mapper.
    """

    def __init__(self, device, bootable=True):
        """Create a new DiskDevice."""

        self.device = device
        self.bootable = bootable
        self.progress_bar = None

        self.g = guestfs.GuestFS()
        self.g.add_drive_opts(self.device, readonly=0)

        #self.g.set_trace(1)
        #self.g.set_verbose(1)

        self.guestfs_enabled = False

    def enable(self):
        """Enable a newly created DiskDevice"""
        self.progressbar = progress_generator("Launching helper VM: ")
        with indent(4):
            self.progressbar.next()
            eh = self.g.set_event_callback(self.progress_callback,
                                                        guestfs.EVENT_PROGRESS)
            self.g.launch()
            self.guestfs_enabled = True
            self.g.delete_event_callback(eh)
            if self.progressbar is not None:
                self.progressbar.send(100)
                self.progressbar = None
            puts(colored.green('Done'))

        puts('Inspecting Operating System')
        with indent(4):
            roots = self.g.inspect_os()
            if len(roots) == 0:
                raise FatalError("No operating system found")
            if len(roots) > 1:
                raise FatalError("Multiple operating systems found."
                                "We only support images with one filesystem.")
            self.root = roots[0]
            self.ostype = self.g.inspect_get_type(self.root)
            self.distro = self.g.inspect_get_distro(self.root)
            puts(colored.green('Found a %s system' % self.distro))
        puts()

    def destroy(self):
        """Destroy this DiskDevice instance."""

        if self.guestfs_enabled:
            self.g.umount_all()
            self.g.sync()

        # Close the guestfs handler if open
        self.g.close()

    def progress_callback(self, ev, eh, buf, array):
        position = array[2]
        total = array[3]

        self.progressbar.send((position * 100) // total)

        if position == total:
            self.progressbar = None

    def mount(self):
        """Mount all disk partitions in a correct order."""
        mps = self.g.inspect_get_mountpoints(self.root)

        # Sort the keys to mount the fs in a correct order.
        # / should be mounted befor /boot, etc
        def compare(a, b):
            if len(a[0]) > len(b[0]):
                return 1
            elif len(a[0]) == len(b[0]):
                return 0
            else:
                return -1
        mps.sort(compare)
        for mp, dev in mps:
            try:
                self.g.mount(dev, mp)
            except RuntimeError as msg:
                print "%s (ignored)" % msg

    def umount(self):
        """Umount all mounted filesystems."""
        self.g.umount_all()

    def shrink(self):
        """Shrink the disk.

        This is accomplished by shrinking the last filesystem in the
        disk and then updating the partition table. The new disk size
        (in bytes) is returned.
        """
        puts("Shrinking image (this may take a while)")
        
        dev = self.g.part_to_dev(self.root)
        parttype = self.g.part_get_parttype(dev)
        if parttype != 'msdos':
            raise FatalError("You have a %s partition table. "
                "Only msdos partitions are supported" % parttype)

        last_partition = self.g.part_list(dev)[-1]

        if last_partition['part_num'] > 4:
            raise FatalError("This disk contains logical partitions. "
                "Only primary partitions are supported.")

        part_dev = "%s%d" % (dev, last_partition['part_num'])
        fs_type = self.g.vfs_type(part_dev)
        if not re.match("ext[234]", fs_type):
            warn("Don't know how to resize %s partitions." % vfs_type)
            return

        with indent(4):
            self.g.e2fsck_f(part_dev)
            self.g.resize2fs_M(part_dev)

            output = self.g.tune2fs_l(part_dev)
            block_size = int(
                filter(lambda x: x[0] == 'Block size', output)[0][1])
            block_cnt = int(
                filter(lambda x: x[0] == 'Block count', output)[0][1])

            sector_size = self.g.blockdev_getss(dev)

            start = last_partition['part_start'] / sector_size
            end = start + (block_size * block_cnt) / sector_size - 1

            self.g.part_del(dev, last_partition['part_num'])
            self.g.part_add(dev, 'p', start, end)

            new_size = (end + 1) * sector_size
            puts("  New image size is %dMB\n" % (new_size // 2 ** 20))
        return new_size

    def size(self):
        """Returns the "payload" size of the device.

        The size returned by this method is the size of the space occupied by
        the partitions (including the space before the first partition).
        """
        dev = self.g.part_to_dev(self.root)
        last = self.g.part_list(dev)[-1]

        return last['part_end']

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
