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

from image_creator.util import get_command
from image_creator.util import warn, progress, success, output, FatalError
from image_creator.gpt import GPTPartitionTable
import stat
import os
import tempfile
import uuid
import re
import sys
import guestfs
import time
from sendfile import sendfile


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

    def snapshot(self):
        """Creates a snapshot of the original source media of the Disk
        instance.
        """

        output("Examining source media `%s'..." % self.source, False)
        sourcedev = self.source
        mode = os.stat(self.source).st_mode
        if stat.S_ISDIR(mode):
            success('looks like a directory')
            return self._losetup(self._dir_to_disk())
        elif stat.S_ISREG(mode):
            success('looks like an image file')
            sourcedev = self._losetup(self.source)
        elif not stat.S_ISBLK(mode):
            raise ValueError("Invalid media source. Only block devices, "
                            "regular files and directories are supported.")
        else:
            success('looks like a block device')

        # Take a snapshot and return it to the user
        output("Snapshotting media source...", False)
        size = blockdev('--getsize', sourcedev)
        cowfd, cow = tempfile.mkstemp()
        os.close(cowfd)
        self._add_cleanup(os.unlink, cow)
        # Create 1G cow sparse file
        dd('if=/dev/null', 'of=%s' % cow, 'bs=1k', 'seek=%d' % (1024 * 1024))
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
        success('done')
        return "/dev/mapper/%s" % snapshot

    def get_device(self, media):
        """Returns a newly created DiskDevice instance."""

        new_device = DiskDevice(media)
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

        self.real_device = device
        self.bootable = bootable
        self.progress_bar = None
        self.guestfs_device = None
        self.size = None
        self.parttype = None

        self.g = guestfs.GuestFS()
        self.g.add_drive_opts(self.real_device, readonly=0)

        #self.g.set_trace(1)
        #self.g.set_verbose(1)

        self.guestfs_enabled = False

    def enable(self):
        """Enable a newly created DiskDevice"""
        self.progressbar = progress("Launching helper VM: ", "percent")
        self.progressbar.max = 100
        self.progressbar.goto(1)
        eh = self.g.set_event_callback(self.progress_callback,
                                                    guestfs.EVENT_PROGRESS)
        self.g.launch()
        self.guestfs_enabled = True
        self.g.delete_event_callback(eh)
        if self.progressbar is not None:
            output("\rLaunching helper VM...\033[K", False)
            success("done")
            self.progressbar = None

        output('Inspecting Operating System...', False)
        roots = self.g.inspect_os()
        if len(roots) == 0:
            raise FatalError("No operating system found")
        if len(roots) > 1:
            raise FatalError("Multiple operating systems found."
                            "We only support images with one filesystem.")
        self.root = roots[0]
        self.guestfs_device = self.g.part_to_dev(self.root)
        self.size = self.g.blockdev_getsize64(self.guestfs_device)
        self.parttype = self.g.part_get_parttype(self.guestfs_device)

        self.ostype = self.g.inspect_get_type(self.root)
        self.distro = self.g.inspect_get_distro(self.root)
        success('found a(n) %s system' % self.distro)

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

        self.progressbar.goto((position * 100) // total)

    def mount(self):
        """Mount all disk partitions in a correct order."""

        output("Mounting image...", False)
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
                warn("%s (ignored)" % msg)
        success("done")

    def umount(self):
        """Umount all mounted filesystems."""
        self.g.umount_all()

    def shrink(self):
        """Shrink the disk.

        This is accomplished by shrinking the last filesystem in the
        disk and then updating the partition table. The new disk size
        (in bytes) is returned.

        ATTENTION: make sure unmount is called before shrink
        """
        output("Shrinking image (this may take a while)...", False)

        if self.parttype not in 'msdos' 'gpt':
            raise FatalError("You have a %s partition table. "
                "Only msdos and gpt partitions are supported" % self.parttype)

        last_partition = self.g.part_list(self.guestfs_device)[-1]

        if self.parttype == 'msdos' and last_partition['part_num'] > 4:
            raise FatalError("This disk contains logical partitions. "
                                    "Only primary partitions are supported.")

        part_dev = "%s%d" % (self.guestfs_device, last_partition['part_num'])
        fs_type = self.g.vfs_type(part_dev)
        if not re.match("ext[234]", fs_type):
            warn("Don't know how to resize %s partitions." % fs_type)
            return self.size

        self.g.e2fsck_f(part_dev)
        self.g.resize2fs_M(part_dev)

        out = self.g.tune2fs_l(part_dev)
        block_size = int(
            filter(lambda x: x[0] == 'Block size', out)[0][1])
        block_cnt = int(
            filter(lambda x: x[0] == 'Block count', out)[0][1])

        sector_size = self.g.blockdev_getss(self.guestfs_device)

        start = last_partition['part_start'] / sector_size
        end = start + (block_size * block_cnt) / sector_size - 1

        self.g.part_del(self.guestfs_device, last_partition['part_num'])
        self.g.part_add(self.guestfs_device, 'p', start, end)

        self.size = (end + 1) * sector_size
        success("new size is %dMB" % ((self.size + 2 ** 20 - 1) // 2 ** 20))

        if self.parttype == 'gpt':
            ptable = GPTPartitionTable(self.real_device)
            self.size = ptable.shrink(self.size)

        return self.size

    def dump(self, outfile):
        """Dumps the content of device into a file.

        This method will only dump the actual payload, found by reading the
        partition table. Empty space in the end of the device will be ignored.
        """
        blocksize = 2 ** 22  # 4MB
        progress_size = (self.size + 2 ** 20 - 1) // 2 ** 20  # in MB
        progressbar = progress("Dumping image file: ", 'mb')
        progressbar.max = progress_size

        with open(self.real_device, 'r') as src:
            with open(outfile, "w") as dst:
                left = self.size
                offset = 0
                progressbar.next()
                while left > 0:
                    length = min(left, blocksize)
                    sent = sendfile(dst.fileno(), src.fileno(), offset, length)
                    offset += sent
                    left -= sent
                    progressbar.goto((self.size - left) // 2 ** 20)
        output("\rDumping image file...\033[K", False)
        success('image file %s was successfully created' % outfile)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
