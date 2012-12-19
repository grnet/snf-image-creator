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
from collections import namedtuple

import parted

from image_creator.util import get_command
from image_creator.util import FatalError

findfs = get_command('findfs')
truncate = get_command('truncate')
dd = get_command('dd')
dmsetup = get_command('dmsetup')


class BundleVolume():
    _FileSystemEntry = namedtuple('FileSystemEntry',
                                  'dev mpoint fs opts freq passno')

    _Partition = namedtuple('Partition', 'num start end type fs mopts')

    def __init__(self, out, meta):
        self.out = out
        self.meta = meta

        self.out.output('Searching for root device...', False)
        root = self._get_root_partition()

        if root.startswith("UUID=") or root.startswith("LABEL="):
            self.root = findfs(root).stdout.strip()
        else:
            self.root = root

        if not re.match('/dev/[hsv]d[a-z][1-9]*$', self.root):
            raise FatalError("Don't know how to handle root device: %s" % \
                             self.root)

        self.disk = re.split('[0-9]', self.root)[0]

        out.success('%s' % root_dev)

    def _read_fstable(f):
        if not os.path.isfile(f):
            raise FatalError("Unable to open: `%s'. File is missing." % f)

        with open(f) as table:
            for line in iter(table):
                entry = line.split('#')[0].strip().split()
                if len(entry) != 6:
                    continue
                yield FileSystemEntry(*entry)

    def _get_root_partition():
        for entry in self._read_fstable('/etc/fstab'):
            if entry.mpoint == '/':
                return entry.dev

        raise FatalError("Unable to find root device in /etc/fstab")

    def _is_mpoint(path):
        for entry in fstable('/proc/mounts'):
            if entry.mpoint == path:
                return True
        return False

    def _mount_options(device):
        for entry in fstable('/proc/mounts'):
            if not entry.dev.startswith('/'):
                continue

            if os.path.realpath(entry.dev) == os.path.realpath(device):
                return entry

        return

    def _create_partition_table(src_disk, dest_file):

        if src_disk.type != 'msdos':
            raise FatalError('Only msdos partition tables are supported')

        first_sector = src_disk.getPrimaryPartitions()[0].geometry.start

        # Copy the MBR and the space between the MBR and the first partition.
        # In Grub version 1 Stage 1.5 is located there.
        first_sector = src_disk.getPrimaryPartitions()[0].geometry.start

        dd('if=%s' % src_disk.device.path, 'of=%s' % dest_file,
           'bs=%d' % src_disk.device.sectorSize,
           'count=%d' % first_sector, 'conv=notrunc')

        # Create the Extended boot records (EBRs) in the image
        extended = src_disk.getExtendedPartition()
        if not extended:
            return

        # Extended boot records precede the logical partitions they describe
        logical = src_disk.getLogicalPartitions()
        start = extended.geometry.start
        for i in range(len(logical)):
            end = logical[i].geometry.start - 1
            dd('if=%s' % src.device.path, 'of=%s' % dest,
               'count=%d' % (end - start + 1), 'conv=notrunc',
               'seek=%d' % start, 'skip=%d' % start)
            start = logical[i].geometry.end + 1

    def _shrink_partitions(src_disk, image_file):

        partitions = []
        new_end = 0

        image_dev = parted.Device(image_file)
        try:
            image_disk = parted.Disk(image_dev)
            try:
                is_extended = lambda p: p.type == parted.PARTITION_EXTENDED
                is_logical = lambda p: p.type == parted.PARTITION_LOGICAL

                partitions = []
                for p in src_disk.partitions:
                    g = p.geometry
                    f = p.fileSystem
                    partitions.append(self._Partition(p.number, g.start, g.end,
                                      p.type, f.type if f is not None else '',
                                      mount_options(p.path)))

                last = partitions[-1]
                new_end = src_disk.device.getLength()
                if last.fs == 'linux-swap(v1)':
                    MB = 2 ** 20
                    size = (last.end - last.start + 1) * \
                        src_disk.device.sectorSize
                    meta['SWAP'] = "%d:%s" % (last.num, (size + MB - 1) // MB)

                    img_disk.deletePartition(
                        image_disk.getPartitionBySector(last.start))
                    img_disk.commit()

                    if is_logical(last) and last.num == 5:
                        extended = image_disk.getExtendedPartition()
                        image_disk.deletePartition(extended)
                        image_disk.commit()
                        partitions.remove(filter(is_extended, partitions)[0])

                    partitions.remove(last)
                    last = partitions[-1]

                    # Leave 2048 blocks at the end
                    new_end = last.end + 2048

                if last.mpoint:
                    stat = os.statvfs(last.mpoint)
                    # Shrink the last partition. The new size should be the
                    # size of the occupied blocks
                    blcks = stat.f_blocks - stat.f_bavail
                    new_size = (blcks * stat.f_frsize) // src_dev.sectorSize

                    # Add 10% just to be on the safe side
                    part_end = last.start + (new_size * 11) // 10
                    # Alighn to 2048
                    part_end = ((part_end + 2047) // 2048) * 2048
                    last = last._replace(end=part_end)
                    partitions[-1] = last

                    # Leave 2048 blocks at the end.
                    new_end = new_size + 2048

                    image_disk.setPartitionGeometry(
                        image_disk.getPartitionBySector(last.start),
                        parted.Constraint(device=image_disk.device),
                        start=last.start, end=last.end)
                    image_disk.commit()

                    if last.type == parted.PARTITION_LOGICAL:
                        # Fix the extended partition
                        extended = disk.getExtendedPartition()

                        image_disk.setPartitionGeometry(extended,
                            parted.Constraint(device=img_dev),
                            ext.geometry.start, end=last.end)
                        image_disk.commit()
            finally:
                image_disk.destroy()
        finally:
            image_dev.destroy()

        # Check if the available space is enough to host the image
        location = os.path.dirname(image_file)
        size = (new_end + 1) * src_disk.device.sectorSize
        self.out.output("Examining available space in %s" % location, False)
        stat = os.statvfs(location)
        available = stat.f_bavail * stat.f_frsize
        if available <= size:
            raise FatalError('Not enough space in %s to host the image' % \
                             location)
        out.success("sufficient")

        return partitions

    def _fill_partitions(src_disk, image, partitions):
        pass

    def create_image():

        image_file = '/mnt/%s.diskdump' % uuid.uuid4().hex

        src_dev = parted.Device(self.disk)
        try:
            size = src_dev.getLength() * src_dev.sectorSize

            # Create sparse file to host the image
            truncate("-s", "%d" % disk_size, image_file)

            src_disk = parted.Disk(src_dev)
            try:
                self._create_partition_table(src_disk, image_file)
                partitions = self._shrink_partitions(src_disk, image_file)
                self.fill_partitions(src_disk, image_file, partitions)

            finally:
                src_disk.destroy()
        finally:
            src_dev.destroy()

        return image_file

#    	unmounted = filter(lambda p: not p.mopts.mpoint, partitions)
#        mounted = filter(lambda p: p.mopts.mpoint, partitions)
#
#        for p in unmounted:
#            dd('if=%s' % src_dev.path, 'of=%s' % img_dev.path,
#               'count=%d' % (p.end - p.start + 1), 'conv=notrunc',
#                'seek=%d' % p.start, 'skip=%d' % p.start)
#
#        partition_devices = create_devices(dest, partitions)
#
#        mounted.sort(key=lambda p: p.mopts.mpoint)
#
#        return img

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
