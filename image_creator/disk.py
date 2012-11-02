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
from image_creator.util import FatalError
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

    def __init__(self, source, output):
        """Create a new Disk instance out of a source media. The source
        media can be an image file, a block device or a directory."""
        self._cleanup_jobs = []
        self._devices = []
        self.source = source
        self.out = output

    def _add_cleanup(self, job, *args):
        self._cleanup_jobs.append((job, args))

    def _losetup(self, fname):
        loop = losetup('-f', '--show', fname)
        loop = loop.strip()  # remove the new-line char
        self._add_cleanup(losetup, '-d', loop)
        return loop

    def _dir_to_disk(self):
        raise FatalError("Using a directory as media source is not supported "
                         "yet!")

    def cleanup(self):
        """Cleanup internal data. This needs to be called before the
        program ends.
        """
        try:
            while len(self._devices):
                device = self._devices.pop()
                device.destroy()
        finally:
            # Make sure those are executed even if one of the device.destroy
            # methods throws exeptions.
            while len(self._cleanup_jobs):
                job, args = self._cleanup_jobs.pop()
                job(*args)

    def snapshot(self):
        """Creates a snapshot of the original source media of the Disk
        instance.
        """

        self.out.output("Examining source media `%s'..." % self.source, False)
        sourcedev = self.source
        mode = os.stat(self.source).st_mode
        if stat.S_ISDIR(mode):
            self.out.success('looks like a directory')
            return self._losetup(self._dir_to_disk())
        elif stat.S_ISREG(mode):
            self.out.success('looks like an image file')
            sourcedev = self._losetup(self.source)
        elif not stat.S_ISBLK(mode):
            raise ValueError("Invalid media source. Only block devices, "
                             "regular files and directories are supported.")
        else:
            self.out.success('looks like a block device')

        # Take a snapshot and return it to the user
        self.out.output("Snapshotting media source...", False)
        size = blockdev('--getsz', sourcedev)
        cowfd, cow = tempfile.mkstemp()
        os.close(cowfd)
        self._add_cleanup(os.unlink, cow)
        # Create cow sparse file
        dd('if=/dev/null', 'of=%s' % cow, 'bs=512', 'seek=%d' % int(size))
        cowdev = self._losetup(cow)

        snapshot = uuid.uuid4().hex
        tablefd, table = tempfile.mkstemp()
        try:
            os.write(tablefd, "0 %d snapshot %s %s n 8" %
                              (int(size), sourcedev, cowdev))
            dmsetup('create', snapshot, table)
            self._add_cleanup(dmsetup, 'remove', snapshot)
            # Sometimes dmsetup remove fails with Device or resource busy,
            # although everything is cleaned up and the snapshot is not
            # used by anyone. Add a 2 seconds delay to be on the safe side.
            self._add_cleanup(time.sleep, 2)

        finally:
            os.unlink(table)
        self.out.success('done')
        return "/dev/mapper/%s" % snapshot

    def get_device(self, media):
        """Returns a newly created DiskDevice instance."""

        new_device = DiskDevice(media, self.out)
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

    def __init__(self, device, output, bootable=True):
        """Create a new DiskDevice."""

        self.real_device = device
        self.out = output
        self.bootable = bootable
        self.progress_bar = None
        self.guestfs_device = None
        self.size = 0
        self.meta = {}

        self.g = guestfs.GuestFS()
        self.g.add_drive_opts(self.real_device, readonly=0)

        # Before version 1.17.14 the recovery process, which is a fork of the
        # original process that called libguestfs, did not close its inherited
        # file descriptors. This can cause problems especially if the parent
        # process has opened pipes. Since the recovery process is an optional
        # feature of libguestfs, it's better to disable it.
        self.g.set_recovery_proc(0)
        version = self.g.version()
        if version['major'] > 1 or \
            (version['major'] == 1 and (version['minor'] >= 18 or
                                        (version['minor'] == 17 and
                                         version['release'] >= 14))):
            self.g.set_recovery_proc(1)
            self.out.output("Enabling recovery proc")

        #self.g.set_trace(1)
        #self.g.set_verbose(1)

        self.guestfs_enabled = False

    def enable(self):
        """Enable a newly created DiskDevice"""
        self.progressbar = self.out.Progress(100, "Launching helper VM",
                                             "percent")
        eh = self.g.set_event_callback(self.progress_callback,
                                       guestfs.EVENT_PROGRESS)
        self.g.launch()
        self.guestfs_enabled = True
        self.g.delete_event_callback(eh)
        self.progressbar.success('done')
        self.progressbar = None

        self.out.output('Inspecting Operating System...', False)
        roots = self.g.inspect_os()
        if len(roots) == 0:
            raise FatalError("No operating system found")
        if len(roots) > 1:
            raise FatalError("Multiple operating systems found."
                             "We only support images with one OS.")
        self.root = roots[0]
        self.guestfs_device = self.g.part_to_dev(self.root)
        self.size = self.g.blockdev_getsize64(self.guestfs_device)
        self.meta['PARTITION_TABLE'] = \
            self.g.part_get_parttype(self.guestfs_device)

        self.ostype = self.g.inspect_get_type(self.root)
        self.distro = self.g.inspect_get_distro(self.root)
        self.out.success('found a(n) %s system' % self.distro)

    def destroy(self):
        """Destroy this DiskDevice instance."""

        # In new guestfs versions, there is a handy shutdown method for this
        try:
            if self.guestfs_enabled:
                self.g.umount_all()
                self.g.sync()
        finally:
            # Close the guestfs handler if open
            self.g.close()

    def progress_callback(self, ev, eh, buf, array):
        position = array[2]
        total = array[3]

        self.progressbar.goto((position * 100) // total)

    def mount(self, readonly=False):
        """Mount all disk partitions in a correct order."""

        mount = self.g.mount_ro if readonly else self.g.mount
        msg = " read-only" if readonly else ""
        self.out.output("Mounting the media%s..." % msg, False)
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
                mount(dev, mp)
            except RuntimeError as msg:
                self.out.warn("%s (ignored)" % msg)
        self.out.success("done")

    def umount(self):
        """Umount all mounted filesystems."""
        self.g.umount_all()

    def _last_partition(self):
        if self.meta['PARTITION_TABLE'] not in 'msdos' 'gpt':
            msg = "Unsupported partition table: %s. Only msdos and gpt " \
                "partition tables are supported" % self.meta['PARTITION_TABLE']
            raise FatalError(msg)

        is_extended = lambda p: \
            self.g.part_get_mbr_id(self.guestfs_device, p['part_num']) == 5
        is_logical = lambda p: \
            self.meta['PARTITION_TABLE'] != 'msdos' and p['part_num'] > 4

        partitions = self.g.part_list(self.guestfs_device)
        last_partition = partitions[-1]

        if is_logical(last_partition):
            # The disk contains extended and logical partitions....
            extended = [p for p in partitions if is_extended(p)][0]
            last_primary = [p for p in partitions if p['part_num'] <= 4][-1]

            # check if extended is the last primary partition
            if last_primary['part_num'] > extended['part_num']:
                last_partition = last_primary

        return last_partition

    def shrink(self):
        """Shrink the disk.

        This is accomplished by shrinking the last filesystem in the
        disk and then updating the partition table. The new disk size
        (in bytes) is returned.

        ATTENTION: make sure unmount is called before shrink
        """
        get_fstype = lambda p: \
            self.g.vfs_type("%s%d" % (self.guestfs_device, p['part_num']))
        is_logical = lambda p: \
            self.meta['PARTITION_TABLE'] == 'msdos' and p['part_num'] > 4
        is_extended = lambda p: \
            self.meta['PARTITION_TABLE'] == 'msdos' and \
            self.g.part_get_mbr_id(self.guestfs_device, p['part_num']) == 5

        part_add = lambda ptype, start, stop: \
            self.g.part_add(self.guestfs_device, ptype, start, stop)
        part_del = lambda p: self.g.part_del(self.guestfs_device, p)
        part_get_id = lambda p: self.g.part_get_mbr_id(self.guestfs_device, p)
        part_set_id = lambda p, id: \
            self.g.part_set_mbr_id(self.guestfs_device, p, id)
        part_get_bootable = lambda p: \
            self.g.part_get_bootable(self.guestfs_device, p)
        part_set_bootable = lambda p, bootable: \
            self.g.part_set_bootable(self.guestfs_device, p, bootable)

        MB = 2 ** 20

        self.out.output("Shrinking image (this may take a while)...", False)

        sector_size = self.g.blockdev_getss(self.guestfs_device)

        last_part = None
        fstype = None
        while True:
            last_part = self._last_partition()
            fstype = get_fstype(last_part)

            if fstype == 'swap':
                self.meta['SWAP'] = "%d:%s" % \
                    (last_part['part_num'],
                     (last_part['part_size'] + MB - 1) // MB)
                part_del(last_part['part_num'])
                continue
            elif is_extended(last_part):
                part_del(last_part['part_num'])
                continue

            # Most disk manipulation programs leave 2048 sectors after the last
            # partition
            new_size = last_part['part_end'] + 1 + 2048 * sector_size
            self.size = min(self.size, new_size)
            break

        if not re.match("ext[234]", fstype):
            self.out.warn("Don't know how to resize %s partitions." % fstype)
            return self.size

        part_dev = "%s%d" % (self.guestfs_device, last_part['part_num'])
        self.g.e2fsck_f(part_dev)
        self.g.resize2fs_M(part_dev)

        out = self.g.tune2fs_l(part_dev)
        block_size = int(
            filter(lambda x: x[0] == 'Block size', out)[0][1])
        block_cnt = int(
            filter(lambda x: x[0] == 'Block count', out)[0][1])

        start = last_part['part_start'] / sector_size
        end = start + (block_size * block_cnt) / sector_size - 1

        if is_logical(last_part):
            partitions = self.g.part_list(self.guestfs_device)

            logical = []  # logical partitions
            for partition in partitions:
                if partition['part_num'] < 4:
                    continue
                logical.append({
                    'num': partition['part_num'],
                    'start': partition['part_start'] / sector_size,
                    'end': partition['part_end'] / sector_size,
                    'id': part_get_(partition['part_num']),
                    'bootable': part_get_bootable(partition['part_num'])
                })

            logical[-1]['end'] = end  # new end after resize

            # Recreate the extended partition
            extended = [p for p in partitions if self._is_extended(p)][0]
            part_del(extended['part_num'])
            part_add('e', extended['part_start'], end)

            # Create all the logical partitions back
            for l in logical:
                part_add('l', l['start'], l['end'])
                part_set_id(l['num'], l['id'])
                part_set_bootable(l['num'], l['bootable'])
        else:
            # Recreate the last partition
            if self.meta['PARTITION_TABLE'] == 'msdos':
                last_part['id'] = part_get_id(last_part['part_num'])

            last_part['bootable'] = part_get_bootable(last_part['part_num'])
            part_del(last_part['part_num'])
            part_add('p', start, end)
            part_set_bootable(last_part['part_num'], last_part['bootable'])

            if self.meta['PARTITION_TABLE'] == 'msdos':
                part_set_id(last_part['part_num'], last_part['id'])

        new_size = (end + 1) * sector_size

        assert (new_size <= self.size)

        if self.meta['PARTITION_TABLE'] == 'gpt':
            ptable = GPTPartitionTable(self.real_device)
            self.size = ptable.shrink(new_size, self.size)
        else:
            self.size = min(new_size + 2048 * sector_size, self.size)

        self.out.success("new size is %dMB" % ((self.size + MB - 1) // MB))

        return self.size

    def dump(self, outfile):
        """Dumps the content of device into a file.

        This method will only dump the actual payload, found by reading the
        partition table. Empty space in the end of the device will be ignored.
        """
        MB = 2 ** 20
        blocksize = 4 * MB  # 4MB
        size = self.size
        progr_size = (size + MB - 1) // MB  # in MB
        progressbar = self.out.Progress(progr_size, "Dumping image file", 'mb')

        with open(self.real_device, 'r') as src:
            with open(outfile, "w") as dst:
                left = size
                offset = 0
                progressbar.next()
                while left > 0:
                    length = min(left, blocksize)
                    _, sent = sendfile(dst.fileno(), src.fileno(), offset,
                        length)
                    offset += sent
                    left -= sent
                    progressbar.goto((size - left) // MB)
        progressbar.success('image file %s was successfully created' % outfile)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
