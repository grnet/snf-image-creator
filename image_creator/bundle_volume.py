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

import os
import re
import uuid
import tempfile
import time
from collections import namedtuple

import parted

from image_creator.rsync import Rsync
from image_creator.util import get_command
from image_creator.util import FatalError

findfs = get_command('findfs')
truncate = get_command('truncate')
dd = get_command('dd')
dmsetup = get_command('dmsetup')
losetup = get_command('losetup')
mount = get_command('mount')
umount = get_command('umount')

MKFS_OPTS = {
    'ext2': ['-F'],
    'ext3': ['-F'],
    'ext4': ['-F'],
    'reiserfs': ['-ff'],
    'btrfs': [],
    'minix': [],
    'xfs': ['-f'],
    'jfs': ['-f'],
    'ntfs': ['-F'],
    'msdos': [],
    'vfat': []
    }


class BundleVolume():

    def __init__(self, out, meta):
        self.out = out
        self.meta = meta

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
        for entry in self._read_fstable('/etc/fstab'):
            if entry.mpoint == '/':
                return entry.dev

        raise FatalError("Unable to find root device in /etc/fstab")

    def _is_mpoint(self, path):
        for entry in self._read_fstable('/proc/mounts'):
            if entry.mpoint == path:
                return True
        return False

    def _get_mount_options(self, device):
        for entry in self._read_fstable('/proc/mounts'):
            if not entry.dev.startswith('/'):
                continue

            if os.path.realpath(entry.dev) == os.path.realpath(device):
                return entry

        return None

    def _create_partition_table(self, image):

        if self.disk.type != 'msdos':
            raise FatalError('Only msdos partition tables are supported')

        # Copy the MBR and the space between the MBR and the first partition.
        # In Grub version 1 Stage 1.5 is located there.
        first_sector = self.disk.getPrimaryPartitions()[0].geometry.start

        dd('if=%s' % self.disk.device.path, 'of=%s' % image,
           'bs=%d' % self.disk.device.sectorSize,
           'count=%d' % first_sector, 'conv=notrunc')

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

        new_end = self.disk.device.getLength()

        image_dev = parted.Device(image)
        image_disk = parted.Disk(image_dev)

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
            image_disk.commit()

            if is_logical(last) and last.num == 5:
                extended = image_disk.getExtendedPartition()
                image_disk.deletePartition(extended)
                image_disk.commit()
                partitions.remove(filter(is_extended, partitions)[0])

            partitions.remove(last)
            last = partitions[-1]

            # Leave 2048 blocks at the end
            new_end = last.end + 2048

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
            # Alighn to 2048
            part_end = ((part_end + 2047) // 2048) * 2048

            image_disk.setPartitionGeometry(
                image_disk.getPartitionBySector(last.start),
                parted.Constraint(device=image_disk.device),
                start=last.start, end=last.end)
            image_disk.commit()

            # Parted may have changed this for better alignment
            part_end = image_disk.getPartitionBySector(last.start).geometry.end
            last = last._replace(end=part_end)
            partitions[-1] = last

            # Leave 2048 blocks at the end.
            new_end = new_size + 2048

            if last.type == parted.PARTITION_LOGICAL:
                # Fix the extended partition
                extended = disk.getExtendedPartition()

                image_disk.setPartitionGeometry(extended,
                    parted.Constraint(device=img_dev),
                    ext.geometry.start, end=last.end)
                image_disk.commit()

        return new_end

    def _map_partition(self, dev, num, start, end):
        name = os.path.basename(dev)
        tablefd, table = tempfile.mkstemp()
        try:
            size = end - start + 1
            os.write(tablefd, "0 %d linear %s %d" % (size, dev, start))
            dmsetup('create', "%sp%d" % (name, num), table)
        finally:
            os.unlink(table)

        return "/dev/mapper/%sp%d" % (name, num)

    def _unmap_partition(self, dev):
        if not os.path.exists(dev):
            return

        dmsetup('remove', dev.split('/dev/mapper/')[1])
        time.sleep(0.1)

    def _mount(self, target, devs):

        devs.sort(key=lambda d: d[1])
        for dev, mpoint in devs:
            absmpoint = os.path.abspath(target + mpoint)
            if not os.path.exists(absmpoint):
                os.makedirs(absmpoint)
            mount(dev, absmpoint)

    def _umount_all(self, target):
        mpoints = []
        for entry in self._read_fstable('/proc/mounts'):
            if entry.mpoint.startswith(os.path.abspath(target)):
                    mpoints.append(entry.mpoint)

        mpoints.sort()
        for mpoint in reversed(mpoints):
            umount(mpoint)

    def _to_exclude(self):
        excluded = ['/tmp']
        local_filesystems = MKFS_OPTS.keys() + ['rootfs']
        for entry in self._read_fstable('/proc/mounts'):
            if entry.fs in local_filesystems:
                continue

            mpoint = entry.mpoint
            if mpoint in excluded:
                continue

            descendants = filter(lambda p: p.startswith(mpoint + '/'),
                    excluded)
            if len(descendants):
                for d in descendants:
                    excluded.remove(d)
                excluded.append(mpoint)
                continue

            dirname = mpoint
            basename = ''
            found_ancestor = False
            while dirname != '/':
                (dirname, basename) = os.path.split(dirname)
                if dirname in excluded:
                    found_ancestor = True
                    break

            if not found_ancestor:
                excluded.append(mpoint)

        return map(lambda d: d + "/*", excluded)

    def _create_filesystems(self, image):

        partitions = self._get_partitions(parted.Disk(parted.Device(image)))
        filesystems = {}
        for p in self.disk.partitions:
            filesystems[p.number] = self._get_mount_options(p.path)

        unmounted = filter(lambda p: filesystems[p.num] is None, partitions)
        mounted = filter(lambda p: filesystems[p.num] is not None, partitions)

        # For partitions that are not mounted right now, we can simply dd them
        # into the image.
        for p in unmounted:
            dd('if=%s' % self.disk.device.path, 'of=%s' % image,
               'count=%d' % (p.end - p.start + 1), 'conv=notrunc',
               'seek=%d' % p.start, 'skip=%d' % p.start)

        loop = str(losetup('-f', '--show', image)).strip()
        mapped = {}
        try:
            for p in mounted:
                i = p.num
                mapped[i] = self._map_partition(loop, i, p.start, p.end)

            # Create the file systems
            for i, dev in mapped.iteritems():
                fs = filesystems[i].fs
                self.out.output('Creating %s filesystem on partition %d ... ' %
                    (fs, i), False)
                get_command('mkfs.%s' % fs)(*(MKFS_OPTS[fs] + [dev]))
                self.out.success('done')

            target = tempfile.mkdtemp()
            try:
                absmpoints = self._mount(target,
                    [(mapped[i], filesystems[i].mpoint) for i in mapped.keys()]
                )
                exclude = self._to_exclude() + [image]
                rsync = Rsync('/', target, exclude)
                msg = "Copying host files into the image"
                rsync.archive().run(self.out, msg)

            finally:
                self._umount_all(target)
                os.rmdir(target)
        finally:
            for dev in mapped.values():
                self._unmap_partition(dev)
            losetup('-d', loop)

    def create_image(self):

        image = '/mnt/%s.diskdump' % uuid.uuid4().hex

        disk_size = self.disk.device.getLength() * self.disk.device.sectorSize

        # Create sparse file to host the image
        truncate("-s", "%d" % disk_size, image)

        self._create_partition_table(image)
        end_sector = self._shrink_partitions(image)

        # Check if the available space is enough to host the image
        dirname = os.path.dirname(image)
        size = (end_sector + 1) * self.disk.device.sectorSize
        self.out.output("Examining available space in %s ..." % dirname, False)
        stat = os.statvfs(dirname)
        available = stat.f_bavail * stat.f_frsize
        if available <= size:
            raise FatalError('Not enough space in %s to host the image' %
                             dirname)
        self.out.success("sufficient")

        self._create_filesystems(image)

        return image

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
