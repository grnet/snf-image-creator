# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2015 GRNET S.A.
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

"""Module hosting the Image class."""

from image_creator.util import FatalError, QemuNBD, get_command
from image_creator.gpt import GPTPartitionTable
from image_creator.os_type import os_cls

import os
# Make sure libguestfs runs qemu directly to launch an appliance.
os.environ['LIBGUESTFS_BACKEND'] = 'direct'
import guestfs

import re
import hashlib
from sendfile import sendfile
import threading


class Image(object):
    """The instances of this class can create images out of block devices."""

    def __init__(self, device, output, **kwargs):
        """Create a new Image instance"""

        self.device = device
        self.out = output
        self.format = kwargs['format'] if 'format' in kwargs else 'raw'

        self.meta = kwargs['meta'] if 'meta' in kwargs else {}
        self.sysprep_params = \
            kwargs['sysprep_params'] if 'sysprep_params' in kwargs else {}

        self.progress_bar = None
        self.guestfs_device = None
        self.size = 0

        self.g = guestfs.GuestFS()
        self.guestfs_enabled = False
        self.guestfs_version = self.g.version()

        # This is needed if the image format is not raw
        self.nbd = QemuNBD(device)

        if self.nbd.qemu_nbd is None and self.format != 'raw':
            raise FatalError("qemu-nbd command is missing, only raw input "
                             "media are supported")

        # Check If MOUNT LOCAL is supported for this guestfs build
        self.mount_local_support = hasattr(self.g, "mount_local")
        if self.mount_local_support:
            self._mount_thread = None

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

        self.out.info('Inspecting Operating System ...', False)
        roots = self.g.inspect_os()

        if len(roots) == 0 or len(roots) > 1:
            self.root = None
            self.ostype = "unsupported"
            self.distro = "unsupported"
            self.guestfs_device = '/dev/sda'
            self.size = self.g.blockdev_getsize64(self.guestfs_device)

            if len(roots) > 1:
                reason = "Multiple operating systems found on the media."
            else:
                reason = "Unable to detect any operating system on the media."

            self.set_unsupported(reason)
            return

        self.root = roots[0]
        self.meta['PARTITION_TABLE'] = self.g.part_get_parttype('/dev/sda')
        self.guestfs_device = '/dev/sda'  # self.g.part_to_dev(self.root)
        self.size = self.g.blockdev_getsize64(self.guestfs_device)

        self.ostype = self.g.inspect_get_type(self.root)
        self.distro = self.g.inspect_get_distro(self.root)
        self.out.success(
            'found a(n) %s system' %
            self.ostype if self.distro == "unknown" else self.distro)

        # Inspect the OS
        self.os.inspect()

    def set_unsupported(self, reason):
        """Flag this image as unsupported"""

        self._unsupported = reason
        self.meta['UNSUPPORTED'] = reason
        self.out.warn('Media is not supported. Reason: %s' % reason)

    def is_unsupported(self):
        """Returns if this image is unsupported"""
        return hasattr(self, '_unsupported')

    def enable_guestfs(self):
        """Enable the guestfs handler"""

        if self.guestfs_enabled:
            self.out.warn("Guestfs is already enabled")
            return

        # Before version 1.18.4 the behavior of kill_subprocess was different
        # and you need to reset the guestfs handler to relaunch a previously
        # shut down QEMU backend
        if self.check_guestfs_version(1, 18, 4) < 0:
            self.g = guestfs.GuestFS()

        self.g.add_drive_opts(self.device, readonly=0)

        # Before version 1.17.14 the recovery process, which is a fork of the
        # original process that called libguestfs, did not close its inherited
        # file descriptors. This can cause problems especially if the parent
        # process has opened pipes. Since the recovery process is an optional
        # feature of libguestfs, it's better to disable it.
        if self.check_guestfs_version(1, 17, 14) >= 0:
            self.out.info("Enabling recovery process ...", False)
            self.g.set_recovery_proc(1)
            self.out.success('done')
        else:
            self.g.set_recovery_proc(0)

        # self.g.set_trace(1)
        # self.g.set_verbose(1)

        self.out.info('Launching helper VM (may take a while) ...', False)
        # self.progressbar = self.out.Progress(100, "Launching helper VM",
        #                                     "percent")
        # eh = self.g.set_event_callback(self.progress_callback,
        #                               guestfs.EVENT_PROGRESS)
        try:
            self.g.launch()
        except RuntimeError as e:
            raise FatalError(
                "Launching libguestfs's helper VM failed!\nReason: %s.\n\n"
                "Please run `libguestfs-test-tool' for more info." % str(e))

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

        self.out.info("Shutting down helper VM ...", False)
        self.g.sync()
        # guestfs_shutdown which is the preferred way to shutdown the backend
        # process was introduced in version 1.19.16
        if self.check_guestfs_version(1, 19, 16) >= 0:
            self.g.shutdown()
        else:
            self.g.kill_subprocess()

        # We will reset the guestfs handler if needed
        if self.check_guestfs_version(1, 18, 4) < 0:
            self.g.close()

        self.guestfs_enabled = False
        self.out.success('done')

    @property
    def os(self):
        """Return an OS class instance for this image"""
        if hasattr(self, "_os"):
            return self._os

        if not self.guestfs_enabled:
            self.enable()

        cls = os_cls(self.distro, self.ostype)
        self._os = cls(self, sysprep_params=self.sysprep_params)

        self._os.collect_metadata()

        return self._os

    def raw_device(self, readonly=True):
        """Returns a context manager that exports the raw image device. If
        readonly is true, the block device that is returned is read only.
        """

        if self.guestfs_enabled:
            self.g.umount_all()
            self.g.sync()
            self.g.drop_caches(3)  # drop everything

        # Self gets overwritten
        img = self

        class RawImage(object):
            """The RawImage context manager"""
            def __enter__(self):
                return img.device if img.format == 'raw' else \
                    img.nbd.connect(readonly)

            def __exit__(self, exc_type, exc_value, traceback):
                if img.format != 'raw':
                    img.nbd.disconnect()

        return RawImage()

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
            extended = [p for p in partitions if is_extended(p)][0]
            last_primary = [p for p in partitions if p['part_num'] <= 4][-1]

            # check if extended is the last primary partition
            if last_primary['part_num'] > extended['part_num']:
                last_partition = last_primary

        return last_partition

    def shrink(self, silent=False):
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

        if self.is_unsupported():
            if not silent:
                self.out.warn("Shrinking is disabled for unsupported images")
            return self.size

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
            if not silent:
                self.out.warn(
                    "Don't know how to shrink %s partitions." % fstype)
            return self.size

        part_dev = "%s%d" % (self.guestfs_device, last_part['part_num'])

        try:
            if self.check_guestfs_version(1, 15, 17) >= 0:
                self.g.e2fsck(part_dev, forceall=1)
            else:
                self.g.e2fsck_f(part_dev)
        except RuntimeError as e:
            # There is a bug in some versions of libguestfs and a RuntimeError
            # is thrown although the command has successfully corrected the
            # found file system errors.
            if e.message.find('***** FILE SYSTEM WAS MODIFIED *****') == -1:
                raise

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

        assert new_size <= self.size

        if self.meta['PARTITION_TABLE'] == 'gpt':
            with self.raw_device(readonly=False) as raw:
                ptable = GPTPartitionTable(raw)
                self.size = ptable.shrink(new_size, self.size)
        else:
            self.size = min(new_size + 2048 * sector_size, self.size)

        if not silent:
            self.out.success("Image size is %dMB" %
                             ((self.size + MB - 1) // MB))

        return self.size

    def mount(self, mpoint, readonly=False):
        """Mount the image file system under a local directory"""

        assert self.mount_local_support, \
            "MOUNT LOCAL not supported for this build of libguestfs"

        assert self._mount_thread is None, "Image is already mounted"

        def do_mount():
            """Use libguestfs's guestmount API"""
            with self.os.mount(readonly=readonly, silent=True):
                if self.g.mount_local(mpoint, readonly=readonly) == -1:
                    return
                # The thread will block in mount_local_run until the file
                self.g.mount_local_run()

        self._mount_thread = threading.Thread(target=do_mount)
        self._mount_thread.mpoint = mpoint
        self._mount_thread.start()

    def is_mounted(self):
        """Check if the image is mounted"""

        assert self.mount_local_support, \
            "MOUNT LOCAL not supported for this build of libguestfs"

        if self._mount_thread is None:
            return False

        # Wait for 0.1 second to avoid race conditions if the thread is in an
        # initialization state but not alive yet.
        self._mount_thread.join(0.1)

        return self._mount_thread.is_alive()

    def umount(self, lazy=False):
        """umount the previously mounted image file system"""

        assert self.mount_local_support, \
            "MOUNT LOCAL not supported for this build of libguestfs"

        assert self._mount_thread is not None, "Image is not mounted"

        # Maybe the image was umounted externally
        if not self._mount_thread.is_alive():
            self._mount_thread = None
            return True

        try:
            args = (['-l'] if lazy else []) + [self._mount_thread.mpoint]
            get_command('umount')(*args)
        except:
            return False

        # Wait for a little while. If the image is umounted, mount_local_run
        # should have terminated
        self._mount_thread.join(5)

        if self._mount_thread.is_alive():
            raise FatalError('Unable to join the mount thread')

        self._mount_thread = None
        return True

    def dump(self, outfile):
        """Dumps the content of the image into a file.

        This method will only dump the actual payload, found by reading the
        partition table. Empty space in the end of the device will be ignored.
        """
        MB = 2 ** 20
        blocksize = 2 ** 22  # 4MB
        progr_size = (self.size + MB - 1) // MB  # in MB
        progressbar = self.out.Progress(progr_size, "Dumping image file", 'mb')

        with self.raw_device() as raw:
            with open(raw, 'rb') as src:
                with open(outfile, "wb") as dst:
                    left = self.size
                    offset = 0
                    progressbar.next()
                    while left > 0:
                        length = min(left, blocksize)
                        sent = sendfile(dst.fileno(), src.fileno(), offset,
                                        length)

                        # Workaround for python-sendfile API change. In
                        # python-sendfile 1.2.x (py-sendfile) the returning
                        # value of sendfile is a tuple, where in version 2.x
                        # (pysendfile) it is just a single integer.
                        if isinstance(sent, tuple):
                            sent = sent[1]

                        offset += sent
                        left -= sent
                        progressbar.goto((self.size - left) // MB)

        progressbar.success('image file %s was successfully created' % outfile)

    def md5(self):
        """Computes the MD5 checksum of the image"""

        MB = 2 ** 20
        blocksize = 2 ** 22  # 4MB
        progr_size = ((self.size + MB - 1) // MB)  # in MB
        progressbar = self.out.Progress(progr_size, "Calculating md5sum", 'mb')
        md5 = hashlib.md5()

        with self.raw_device() as raw:
            with open(raw, "rb") as src:
                left = self.size
                while left > 0:
                    length = min(left, blocksize)
                    data = src.read(length)
                    md5.update(data)
                    left -= length
                    progressbar.goto((self.size - left) // MB)

        checksum = md5.hexdigest()
        progressbar.success(checksum)

        return checksum


# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
