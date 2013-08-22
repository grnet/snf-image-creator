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

"""This module hosts the code that performes the host bundling operation. By
using the create_image method of the BundleVolume class the user can create an
image out of the running system.
"""

import os
import re
import tempfile
import uuid
from collections import namedtuple

import parted

from image_creator.rsync import Rsync
from image_creator.util import get_command
from image_creator.util import FatalError
from image_creator.util import try_fail_repeat
from image_creator.util import free_space
from image_creator.gpt import GPTPartitionTable

findfs = get_command('findfs')
dd = get_command('dd')
dmsetup = get_command('dmsetup')
losetup = get_command('losetup')
mount = get_command('mount')
umount = get_command('umount')
blkid = get_command('blkid')
tune2fs = get_command('tune2fs')

MKFS_OPTS = {'ext2': ['-F'],
             'ext3': ['-F'],
             'ext4': ['-F'],
             'reiserfs': ['-ff'],
             'btrfs': [],
             'minix': [],
             'xfs': ['-f'],
             'jfs': ['-f'],
             'ntfs': ['-F'],
             'msdos': [],
             'vfat': []}


class BundleVolume(object):
    """This class can be used to create an image out of the running system"""

    def __init__(self, out, meta, tmp=None):
        """Create an instance of the BundleVolume class."""
        self.out = out
        self.meta = meta
        self.tmp = tmp

        self.out.output('Searching for root device ...', False)
        root = self._get_root_partition()

        if root.startswith("UUID=") or root.startswith("LABEL="):
            root = findfs(root).stdout.strip()

        if not re.match('/dev/[hsv]d[a-z][1-9]*$', root):
            raise FatalError("Don't know how to handle root device: %s" % root)

        out.success(root)

        disk_file = re.split('[0-9]', root)[0]
        device = parted.Device(disk_file)
        self.disk = parted.Disk(device)

    def _read_fstable(self, f):
        """Use this generator to iterate over the lines of and fstab file"""

        if not os.path.isfile(f):
            raise FatalError("Unable to open: `%s'. File is missing." % f)

        FileSystemTableEntry = namedtuple('FileSystemTableEntry',
                                          'dev mpoint fs opts freq passno')
        with open(f) as table:
            for line in iter(table):
                entry = line.split('#')[0].strip().split()
                if len(entry) != 6:
                    continue
                yield FileSystemTableEntry(*entry)

    def _get_root_partition(self):
        """Return the fstab entry accosiated with the root filesystem"""
        for entry in self._read_fstable('/etc/fstab'):
            if entry.mpoint == '/':
                return entry.dev

        raise FatalError("Unable to find root device in /etc/fstab")

    def _is_mpoint(self, path):
        """Check if a directory is currently a mount point"""
        for entry in self._read_fstable('/proc/mounts'):
            if entry.mpoint == path:
                return True
        return False

    def _get_mount_options(self, device):
        """Return the mount entry associated with a mounted device"""
        for entry in self._read_fstable('/proc/mounts'):
            if not entry.dev.startswith('/'):
                continue

            if os.path.realpath(entry.dev) == os.path.realpath(device):
                return entry

        return None

    def _create_partition_table(self, image):
        """Copy the partition table of the host system into the image"""

        # Copy the MBR and the space between the MBR and the first partition.
        # In msdos partition tables Grub Stage 1.5 is located there.
        # In gpt partition tables the Primary GPT Header is there.
        first_sector = self.disk.getPrimaryPartitions()[0].geometry.start

        dd('if=%s' % self.disk.device.path, 'of=%s' % image,
           'bs=%d' % self.disk.device.sectorSize,
           'count=%d' % first_sector, 'conv=notrunc')

        if self.disk.type == 'gpt':
            # Copy the Secondary GPT Header
            table = GPTPartitionTable(self.disk.device.path)
            dd('if=%s' % self.disk.device.path, 'of=%s' % image,
               'bs=%d' % self.disk.device.sectorSize, 'conv=notrunc',
               'seek=%d' % table.primary.last_usable_lba,
               'skip=%d' % table.primary.last_usable_lba)

        # Create the Extended boot records (EBRs) in the image
        extended = self.disk.getExtendedPartition()
        if not extended:
            return

        # Extended boot records precede the logical partitions they describe
        logical = self.disk.getLogicalPartitions()
        start = extended.geometry.start
        for i in range(len(logical)):
            end = logical[i].geometry.start - 1
            dd('if=%s' % self.disk.device.path, 'of=%s' % image,
               'count=%d' % (end - start + 1), 'conv=notrunc',
               'seek=%d' % start, 'skip=%d' % start)
            start = logical[i].geometry.end + 1

    def _get_partitions(self, disk):
        """Returns a list with the partitions of the provided disk"""
        Partition = namedtuple('Partition', 'num start end type fs')

        partitions = []
        for p in disk.partitions:
            num = p.number
            start = p.geometry.start
            end = p.geometry.end
            ptype = p.type
            fs = p.fileSystem.type if p.fileSystem is not None else ''
            partitions.append(Partition(num, start, end, ptype, fs))

        return partitions

    def _shrink_partitions(self, image):
        """Remove the last partition of the image if it is a swap partition and
        shrink the partition before that. Make sure it can still host all the
        files the corresponding host file system hosts
        """
        new_end = self.disk.device.length

        image_disk = parted.Disk(parted.Device(image))

        is_extended = lambda p: p.type == parted.PARTITION_EXTENDED
        is_logical = lambda p: p.type == parted.PARTITION_LOGICAL

        partitions = self._get_partitions(self.disk)

        last = partitions[-1]
        if last.fs == 'linux-swap(v1)':
            MB = 2 ** 20
            size = (last.end - last.start + 1) * self.disk.device.sectorSize
            self.meta['SWAP'] = "%d:%s" % (last.num, (size + MB - 1) // MB)

            image_disk.deletePartition(
                image_disk.getPartitionBySector(last.start))
            image_disk.commitToDevice()

            if is_logical(last) and last.num == 5:
                extended = image_disk.getExtendedPartition()
                image_disk.deletePartition(extended)
                image_disk.commitToDevice()
                partitions.remove(filter(is_extended, partitions)[0])

            partitions.remove(last)
            last = partitions[-1]

            new_end = last.end

        mount_options = self._get_mount_options(
            self.disk.getPartitionBySector(last.start).path)
        if mount_options is not None:
            stat = os.statvfs(mount_options.mpoint)
            # Shrink the last partition. The new size should be the size of the
            # occupied blocks
            blcks = stat.f_blocks - stat.f_bavail
            new_size = (blcks * stat.f_frsize) // self.disk.device.sectorSize

            # Add 10% just to be on the safe side
            part_end = last.start + (new_size * 11) // 10
            # Align to 2048
            part_end = ((part_end + 2047) // 2048) * 2048

            # Make sure the partition starts where the old partition started.
            constraint = parted.Constraint(device=image_disk.device)
            constraint.startRange = parted.Geometry(device=image_disk.device,
                                                    start=last.start, length=1)

            image_disk.setPartitionGeometry(
                image_disk.getPartitionBySector(last.start), constraint,
                start=last.start, end=part_end)
            image_disk.commitToDevice()

            # Parted may have changed this for better alignment
            part_end = image_disk.getPartitionBySector(last.start).geometry.end
            last = last._replace(end=part_end)
            partitions[-1] = last

            new_end = part_end

            if last.type == parted.PARTITION_LOGICAL:
                # Fix the extended partition
                image_disk.minimizeExtendedPartition()

        return (new_end, self._get_partitions(image_disk))

    def _map_partition(self, dev, num, start, end):
        """Map a partition into a block device using the device mapper"""
        name = os.path.basename(dev) + "_" + uuid.uuid4().hex
        tablefd, table = tempfile.mkstemp()
        try:
            try:
                size = end - start + 1
                os.write(tablefd, "0 %d linear %s %d" % (size, dev, start))
            finally:
                os.close(tablefd)
            dmsetup('create', "%sp%d" % (name, num), table)
        finally:
            os.unlink(table)

        return "/dev/mapper/%sp%d" % (name, num)

    def _unmap_partition(self, dev):
        """Unmap a previously mapped partition"""
        if not os.path.exists(dev):
            return

        try_fail_repeat(dmsetup, 'remove', dev.split('/dev/mapper/')[1])

    def _mount(self, target, devs):
        """Mount a list of filesystems in mountpoints relative to target"""
        devs.sort(key=lambda d: d[1])
        for dev, mpoint, options in devs:
            absmpoint = os.path.abspath(target + mpoint)
            if not os.path.exists(absmpoint):
                os.makedirs(absmpoint)

            if len(options) > 0:
                mount(dev, absmpoint, '-o', ",".join(options))
            else:
                mount(dev, absmpoint)

    def _umount_all(self, target):
        """Unmount all filesystems that are mounted under the directory target
        """
        mpoints = []
        for entry in self._read_fstable('/proc/mounts'):
            if entry.mpoint.startswith(os.path.abspath(target)):
                mpoints.append(entry.mpoint)

        mpoints.sort()
        for mpoint in reversed(mpoints):
            try_fail_repeat(umount, mpoint)

    def _to_exclude(self):
        """Find which directories to exclude during the image copy. This is
        accompliced by checking which directories serve as mount points for
        virtual file systems
        """
        excluded = ['/tmp', '/var/tmp']
        if self.tmp is not None:
            excluded.append(self.tmp)
        local_filesystems = MKFS_OPTS.keys() + ['rootfs']
        for entry in self._read_fstable('/proc/mounts'):
            if entry.fs in local_filesystems:
                continue

            mpoint = entry.mpoint
            if mpoint in excluded:
                continue

            descendants = filter(
                lambda p: p.startswith(mpoint + '/'), excluded)
            if len(descendants):
                for d in descendants:
                    excluded.remove(d)
                excluded.append(mpoint)
                continue

            dirname = mpoint
            found_ancestor = False
            while dirname != '/':
                (dirname, _) = os.path.split(dirname)
                if dirname in excluded:
                    found_ancestor = True
                    break

            if not found_ancestor:
                excluded.append(mpoint)

        return excluded

    def _replace_uuids(self, target, new_uuid):
        """Replace UUID references in various files. This is needed after
        copying system files of the host into a new filesystem
        """

        files = ['/etc/fstab',
                 '/boot/grub/grub.cfg',
                 '/boot/grub/menu.lst',
                 '/boot/grub/grub.conf']

        orig = {}
        for p in self.disk.partitions:
            if p.number in new_uuid.keys():
                orig[p.number] = \
                    blkid('-s', 'UUID', '-o', 'value', p.path).stdout.strip()

        for f in map(lambda f: target + f, files):
            if not os.path.exists(f):
                continue

            with open(f, 'r') as src:
                lines = src.readlines()
            with open(f, 'w') as dest:
                for line in lines:
                    for i, uuid in new_uuid.items():
                        line = re.sub(orig[i], uuid, line)
                    dest.write(line)

    def _create_filesystems(self, image, partitions):
        """Fill the image with data. Host file systems that are not currently
        mounted are binary copied into the image. For mounted file systems, a
        file system level copy is performed.
        """

        filesystem = {}
        orig_dev = {}
        for p in self.disk.partitions:
            filesystem[p.number] = self._get_mount_options(p.path)
            orig_dev[p.number] = p.path

        unmounted = filter(lambda p: filesystem[p.num] is None, partitions)
        mounted = filter(lambda p: filesystem[p.num] is not None, partitions)

        # For partitions that are not mounted right now, we can simply dd them
        # into the image.
        for p in unmounted:
            self.out.output('Cloning partition %d ... ' % p.num, False)
            dd('if=%s' % self.disk.device.path, 'of=%s' % image,
               'count=%d' % (p.end - p.start + 1), 'conv=notrunc',
               'seek=%d' % p.start, 'skip=%d' % p.start)
            self.out.success("done")

        loop = str(losetup('-f', '--show', image)).strip()

        # Recreate mounted file systems
        mapped = {}
        try:
            for p in mounted:
                i = p.num
                mapped[i] = self._map_partition(loop, i, p.start, p.end)

            new_uuid = {}
            # Create the file systems
            for i, dev in mapped.iteritems():
                fs = filesystem[i].fs
                self.out.output('Creating %s filesystem on partition %d ... ' %
                                (fs, i), False)
                get_command('mkfs.%s' % fs)(*(MKFS_OPTS[fs] + [dev]))

                # For ext[234] enable the default mount options
                if re.match('^ext[234]$', fs):
                    mopts = filter(
                        lambda p: p.startswith('Default mount options:'),
                        tune2fs('-l', orig_dev[i]).splitlines()
                    )[0].split(':')[1].strip().split()

                    if not (len(mopts) == 1 and mopts[0] == '(none)'):
                        for opt in mopts:
                            tune2fs('-o', opt, dev)

                self.out.success('done')
                new_uuid[i] = blkid(
                    '-s', 'UUID', '-o', 'value', dev).stdout.strip()

            target = tempfile.mkdtemp()
            devs = []
            for i in mapped.keys():
                fs = filesystem[i].fs
                mpoint = filesystem[i].mpoint
                opts = []
                for opt in filesystem[i].opts.split(','):
                    if opt in ('acl', 'user_xattr'):
                        opts.append(opt)
                devs.append((mapped[i], mpoint, opts))
            try:
                self._mount(target, devs)

                excluded = self._to_exclude()

                rsync = Rsync(self.out)

                for excl in excluded + [image]:
                    rsync.exclude(excl)

                rsync.archive().hard_links().xattrs().sparse().acls()
                rsync.run('/', target, 'host', 'temporary image')

                # Create missing mountpoints. Since they are mountpoints, we
                # cannot determine the ownership and the mode of the real
                # directory. Make them inherit those properties from their
                # parent dir
                for excl in excluded:
                    dirname = os.path.dirname(excl)
                    stat = os.stat(dirname)
                    os.mkdir(target + excl)
                    os.chmod(target + excl, stat.st_mode)
                    os.chown(target + excl, stat.st_uid, stat.st_gid)

                # /tmp and /var/tmp are special cases. We exclude then even if
                # they aren't mountpoints. Restore their permissions.
                for excl in ('/tmp', '/var/tmp'):
                    if self._is_mpoint(excl):
                        os.chmod(target + excl, 041777)
                        os.chown(target + excl, 0, 0)
                    else:
                        stat = os.stat(excl)
                        os.chmod(target + excl, stat.st_mode)
                        os.chown(target + excl, stat.st_uid, stat.st_gid)

                # We need to replace the old UUID referencies with the new
                # ones in grub configuration files and /etc/fstab for file
                # systems that have been recreated.
                self._replace_uuids(target, new_uuid)

            finally:
                self._umount_all(target)
                os.rmdir(target)
        finally:
            for dev in mapped.values():
                self._unmap_partition(dev)
            losetup('-d', loop)

    def create_image(self, image):
        """Given an image filename, this method will create an image out of the
        running system.
        """

        size = self.disk.device.length * self.disk.device.sectorSize

        # Create sparse file to host the image
        fd = os.open(image, os.O_WRONLY | os.O_CREAT)
        try:
            os.ftruncate(fd, size)
        finally:
            os.close(fd)

        self._create_partition_table(image)
        end_sector, partitions = self._shrink_partitions(image)

        if self.disk.type == 'gpt':
            old_size = size
            size = (end_sector + 1) * self.disk.device.sectorSize
            ptable = GPTPartitionTable(image)
            size = ptable.shrink(size, old_size)
        else:
            # Alighn to 2048
            end_sector = ((end_sector + 2047) // 2048) * 2048
            size = (end_sector + 1) * self.disk.device.sectorSize

        # Truncate image to the new size.
        fd = os.open(image, os.O_RDWR)
        try:
            os.ftruncate(fd, size)
        finally:
            os.close(fd)

        # Check if the available space is enough to host the image
        dirname = os.path.dirname(image)
        self.out.output("Examining available space ...", False)
        if free_space(dirname) <= size:
            raise FatalError("Not enough space under %s to host the temporary "
                             "image" % dirname)
        self.out.success("sufficient")

        self._create_filesystems(image, partitions)

        return image

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
