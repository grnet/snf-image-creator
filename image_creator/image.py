# -*- coding: utf-8 -*-
#
# Copyright 2013 GRNET S.A. All rights reserved.
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

from image_creator.util import FatalError
from image_creator.gpt import GPTPartitionTable
from image_creator.os_type import os_cls

import re
import guestfs
from sendfile import sendfile


class Image(object):
    """The instances of this class can create images out of block devices."""

    def __init__(self, device, output, **kargs):
        """Create a new Image instance"""

        self.device = device
        self.out = output

        self.meta = kargs['meta'] if 'meta' in kargs else {}
        self.sysprep_params = \
            kargs['sysprep_params'] if 'sysprep_params' in kargs else {}

        self.progress_bar = None
        self.guestfs_device = None
        self.size = 0

        self.g = guestfs.GuestFS()
        self.guestfs_enabled = False
        self.guestfs_version = self.g.version()

    def check_guestfs_version(self, major, minor, release):
        """Checks if the version of the used libguestfs is smaller, equal or
        greater than the one specified by the major, minor and release triplet

        Returns:
            < 0 if the installed version is smaller than the specified one
            = 0 if they are equal
            > 0 if the installed one is greater than the specified one
        """

        for (a, b) in (self.guestfs_version['major'], major), \
                (self.guestfs_version['minor'], minor), \
                (self.guestfs_version['release'], release):
            if a != b:
                return a - b

        return 0

    def enable(self):
        """Enable a newly created Image instance"""

        self.enable_guestfs()

        self.out.output('Inspecting Operating System ...', False)
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
        self.out.success(
            'found a(n) %s system' %
            self.ostype if self.distro == "unknown" else self.distro)

    def enable_guestfs(self):
        """Enable the guestfs handler"""

        if self.guestfs_enabled:
            self.out.warn("Guestfs is already enabled")
            return

        # Before version 1.18.4 the behaviour of kill_subprocess was different
        # and you need to reset the guestfs handler to relaunch a previously
        # shut down qemu backend
        if self.check_guestfs_version(1, 18, 4) < 0:
            self.g = guestfs.GuestFS()

        self.g.add_drive_opts(self.device, readonly=0, format="raw")

        # Before version 1.17.14 the recovery process, which is a fork of the
        # original process that called libguestfs, did not close its inherited
        # file descriptors. This can cause problems especially if the parent
        # process has opened pipes. Since the recovery process is an optional
        # feature of libguestfs, it's better to disable it.
        if self.check_guestfs_version(1, 17, 14) >= 0:
            self.out.output("Enabling recovery proc")
            self.g.set_recovery_proc(1)
        else:
            self.g.set_recovery_proc(0)

        #self.g.set_trace(1)
        #self.g.set_verbose(1)

        self.out.output('Launching helper VM (may take a while) ...', False)
        # self.progressbar = self.out.Progress(100, "Launching helper VM",
        #                                     "percent")
        # eh = self.g.set_event_callback(self.progress_callback,
        #                               guestfs.EVENT_PROGRESS)
        self.g.launch()
        self.guestfs_enabled = True
        # self.g.delete_event_callback(eh)
        # self.progressbar.success('done')
        # self.progressbar = None

        if self.check_guestfs_version(1, 18, 4) < 0:
            self.g.inspect_os()  # some calls need this

        self.out.success('done')

    def disable_guestfs(self):
        """Disable the guestfs handler"""

        if not self.guestfs_enabled:
            self.out.warn("Guestfs is already disabled")
            return

        self.out.output("Shutting down helper VM ...", False)
        self.g.sync()
        # guestfs_shutdown which is the prefered way to shutdown the backend
        # process was introduced in version 1.19.16
        if self.check_guestfs_version(1, 19, 16) >= 0:
            self.g.shutdown()
        else:
            self.g.kill_subprocess()

        self.guestfs_enabled = False
        self.out.success('done')

    def _get_os(self):
        """Return an OS class instance for this image"""
        if hasattr(self, "_os"):
            return self._os

        if not self.guestfs_enabled:
            self.enable()

        cls = os_cls(self.distro, self.ostype)
        self._os = cls(self, sysprep_params=self.sysprep_params)

        self._os.collect_metadata()

        return self._os

    os = property(_get_os)

    def destroy(self):
        """Destroy this Image instance."""

        # In new guestfs versions, there is a handy shutdown method for this
        try:
            if self.guestfs_enabled:
                self.g.umount_all()
                self.g.sync()
        finally:
            # Close the guestfs handler if open
            self.g.close()

#    def progress_callback(self, ev, eh, buf, array):
#        position = array[2]
#        total = array[3]
#
#        self.progressbar.goto((position * 100) // total)

    def _last_partition(self):
        """Return the last partition of the image disk"""
        if self.meta['PARTITION_TABLE'] not in 'msdos' 'gpt':
            msg = "Unsupported partition table: %s. Only msdos and gpt " \
                "partition tables are supported" % self.meta['PARTITION_TABLE']
            raise FatalError(msg)

        is_extended = lambda p: \
            self.g.part_get_mbr_id(self.guestfs_device, p['part_num']) \
            in (0x5, 0xf)
        is_logical = lambda p: \
            self.meta['PARTITION_TABLE'] == 'msdos' and p['part_num'] > 4

        partitions = self.g.part_list(self.guestfs_device)
        last_partition = partitions[-1]

        if is_logical(last_partition):
            # The disk contains extended and logical partitions....
            extended = filter(is_extended, partitions)[0]
            last_primary = [p for p in partitions if p['part_num'] <= 4][-1]

            # check if extended is the last primary partition
            if last_primary['part_num'] > extended['part_num']:
                last_partition = last_primary

        return last_partition

    def shrink(self):
        """Shrink the image.

        This is accomplished by shrinking the last file system of the
        image and then updating the partition table. The new disk size
        (in bytes) is returned.

        ATTENTION: make sure unmount is called before shrink
        """
        get_fstype = lambda p: \
            self.g.vfs_type("%s%d" % (self.guestfs_device, p['part_num']))
        is_logical = lambda p: \
            self.meta['PARTITION_TABLE'] == 'msdos' and p['part_num'] > 4
        is_extended = lambda p: \
            self.meta['PARTITION_TABLE'] == 'msdos' and \
            self.g.part_get_mbr_id(self.guestfs_device, p['part_num']) \
            in (0x5, 0xf)

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

        self.out.output("Shrinking image (this may take a while) ...", False)

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
            self.out.warn("Don't know how to shrink %s partitions." % fstype)
            return self.size

        part_dev = "%s%d" % (self.guestfs_device, last_part['part_num'])

        if self.check_guestfs_version(1, 15, 17) >= 0:
            self.g.e2fsck(part_dev, forceall=1)
        else:
            self.g.e2fsck_f(part_dev)

        self.g.resize2fs_M(part_dev)

        out = self.g.tune2fs_l(part_dev)
        block_size = int(filter(lambda x: x[0] == 'Block size', out)[0][1])
        block_cnt = int(filter(lambda x: x[0] == 'Block count', out)[0][1])

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
                    'id': part_get_id(partition['part_num']),
                    'bootable': part_get_bootable(partition['part_num'])
                })

            logical[-1]['end'] = end  # new end after resize

            # Recreate the extended partition
            extended = filter(is_extended, partitions)[0]
            part_del(extended['part_num'])
            part_add('e', extended['part_start'] / sector_size, end)

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
            ptable = GPTPartitionTable(self.device)
            self.size = ptable.shrink(new_size, self.size)
        else:
            self.size = min(new_size + 2048 * sector_size, self.size)

        self.out.success("new size is %dMB" % ((self.size + MB - 1) // MB))

        return self.size

    def dump(self, outfile):
        """Dumps the content of the image into a file.

        This method will only dump the actual payload, found by reading the
        partition table. Empty space in the end of the device will be ignored.
        """
        MB = 2 ** 20
        blocksize = 4 * MB  # 4MB
        size = self.size
        progr_size = (size + MB - 1) // MB  # in MB
        progressbar = self.out.Progress(progr_size, "Dumping image file", 'mb')

        with open(self.device, 'r') as src:
            with open(outfile, "w") as dst:
                left = size
                offset = 0
                progressbar.next()
                while left > 0:
                    length = min(left, blocksize)
                    sent = sendfile(dst.fileno(), src.fileno(), offset, length)

                    # Workaround for python-sendfile API change. In
                    # python-sendfile 1.2.x (py-sendfile) the returning value
                    # of sendfile is a tuple, where in version 2.x (pysendfile)
                    # it is just a sigle integer.
                    if isinstance(sent, tuple):
                        sent = sent[1]

                    offset += sent
                    left -= sent
                    progressbar.goto((size - left) // MB)
        progressbar.success('image file %s was successfully created' % outfile)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
