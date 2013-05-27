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

    def __init__(self, device, output, bootable=True, meta={}):
        """Create a new Image instance"""

        self.device = device
        self.out = output
        self.bootable = bootable
        self.meta = meta
        self.progress_bar = None
        self.guestfs_device = None
        self.size = 0
        self.mounted = False
        self.mounted_ro = False

        self.g = guestfs.GuestFS()
        self.g.add_drive_opts(self.device, readonly=0, format="raw")

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
        """Enable a newly created Image instance"""

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
        self.out.success('done')

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

    def _get_os(self):
        """Return an OS class instance for this image"""
        if hasattr(self, "_os"):
            return self._os

        if not self.guestfs_enabled:
            self.enable()

        if not self.mounted:
            do_unmount = True
            self.mount(readonly=True)
        else:
            do_unmount = False

        try:
            cls = os_cls(self.distro, self.ostype)
            self._os = cls(self.root, self.g, self.out)

        finally:
            if do_unmount:
                self.umount()

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

    def mount(self, readonly=False):
        """Mount all disk partitions in a correct order."""

        msg = "Mounting the media%s ..." % (" read-only" if readonly else "")
        self.out.output(msg, False)

        #If something goes wrong when mounting rw, remount the filesystem ro
        remount_ro = False
        rw_mpoints = ('/', '/etc', '/root', '/home', '/var')

        # Sort the keys to mount the fs in a correct order.
        # / should be mounted befor /boot, etc
        def compare(a, b):
            if len(a[0]) > len(b[0]):
                return 1
            elif len(a[0]) == len(b[0]):
                return 0
            else:
                return -1
        mps = self.g.inspect_get_mountpoints(self.root)
        mps.sort(compare)

        mopts = 'ro' if readonly else 'rw'
        for mp, dev in mps:
            if self.ostype == 'freebsd':
                # libguestfs can't handle correct freebsd partitions on GUID
                # Partition Table. We have to do the translation to linux
                # device names ourselves
                m = re.match('^/dev/((?:ada)|(?:vtbd))(\d+)p(\d+)$', dev)
                if m:
                    m2 = int(m.group(2))
                    m3 = int(m.group(3))
                    dev = '/dev/sd%c%d' % (chr(ord('a') + m2), m3)
            try:
                self.g.mount_options(mopts, dev, mp)
            except RuntimeError as msg:
                if self.ostype == 'freebsd':
                    freebsd_mopts = "ufstype=ufs2,%s" % mopts
                    try:
                        self.g.mount_vfs(freebsd_mopts, 'ufs', dev, mp)
                    except RuntimeError as msg:
                        if readonly is False and mp in rw_mpoints:
                            remount_ro = True
                            break
                elif readonly is False and mp in rw_mpoints:
                    remount_ro = True
                    break
                else:
                    self.out.warn("%s (ignored)" % msg)
        if remount_ro:
            self.out.warn("Unable to mount %s read-write. "
                          "Remounting everything read-only..." % mp)
            self.umount()
            self.mount(True)
        else:
            self.mounted = True
            self.mounted_ro = readonly
            self.out.success("done")

    def umount(self):
        """Umount all mounted filesystems."""
        self.g.umount_all()
        self.mounted = False

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
