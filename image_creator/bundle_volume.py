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
import parted
import uuid
from collections import namedtuple

from image_creator.util import get_command
from image_creator.util import FatalError

findfs = get_command('findfs')
truncate = get_command('truncate')
dd = get_command('dd')

MB = 2 ** 20

def fstable(f):
    if not os.path.isfile(f):
        raise FatalError("Unable to open: `%s'. File is missing." % f)

    Entry = namedtuple('Entry', 'dev mpoint fs opts freq passno')

    with open(f) as table:
        for line in iter(table):
            entry = line.split('#')[0].strip().split()
            if len(entry) != 6:
                continue
            yield Entry(*entry)


def get_root_partition():
    for entry in fstable('/etc/fstab'):
        if entry.mpoint == '/':
            return entry.dev

    raise FatalError("Unable to find root device in /etc/fstab")


def is_mpoint(path):
    for entry in fstable('/proc/mounts'):
        if entry.mpoint == path:
            return True
    return False


def mpoint(device):
    for entry in fstable('/proc/mounts'):
        if not entry.dev.startswith('/'):
            continue

        if os.path.realpath(entry.dev) == os.path.realpath(device):
            return entry.mpoint

    return ""


def create_EBRs(src, dest):

    # The Extended boot records precede the logical partitions they describe
    extended = src.getExtendedPartition()
    if not extended:
        return

    logical = src.getLogicalPartitions()
    start = extended.geometry.start
    for i in range(len(logical)):
        end = logical[i].geometry.start - 1
        dd('if=%s' % src.device.path, 'of=%s' % dest,
            'count=%d' % (end - start + 1), 'conv=notrunc', 'seek=%d' % start,
            'skip=%d' % start)
        start = logical[i].geometry.end + 1


def bundle_volume(out, meta):

    if is_mpoint('/mnt'):
        raise FatalError('The directory /mnt where the image will be hosted'
            'is mounted. Please unmount it and start over again.')

    out.output('Searching for root device...', False)
    root_part = get_root_partition()

    if root_part.startswith("UUID=") or root_part.startswith("LABEL="):
        root_part = findfs(root_part).stdout.strip()
    elif not root_part.startswith("/"):
        raise FatalError("Unable to find a block device for: %s" % root_dev)

    if not re.match('/dev/[hsv]d[a-z][1-9]*$', root_part):
        raise FatalError("Don't know how to handle root device: %s" % root_dev)

    part_to_dev = lambda p: re.split('[0-9]', p)[0]

    root_dev = part_to_dev(root_part)

    out.success('%s' % root_dev)

    src_dev = parted.Device(root_dev)

    img = '/mnt/%s.diskdump' % uuid.uuid4().hex
    disk_size = src_dev.getLength() * src_dev.sectorSize

    # Create sparse file to host the image
    truncate("-s", "%d" % disk_size, img)

    src_disk = parted.Disk(src_dev)
    if src_disk.type != 'msdos':
        raise FatalError('For now we can only handle msdos partition tables')

    # Copy the MBR and the space between the MBR and the first partition.
    # In Grub version 1 Stage 1.5 is located there.
    first_sector = src_disk.getPrimaryPartitions()[0].geometry.start

    dd('if=%s' % src_dev.path, 'of=%s' % img, 'bs=%d' % src_dev.sectorSize,
        'count=%d' % first_sector, 'conv=notrunc')

    # Create the Extended boot records (EBRs) in the image
    create_EBRs(src_disk, img)

    img_dev = parted.Device(img)
    img_disk = parted.Disk(img_dev)

    is_extended = lambda p: p.type == parted.PARTITION_EXTENDED
    is_logical = lambda p: p.type == parted.PARTITION_LOGICAL

    Partition = namedtuple('Partition', 'num start end type fs mpoint')

    partitions = []
    for p in src_disk.partitions:
        g = p.geometry
        f = p.fileSystem
        partitions.append(Partition(p.number, g.start, g.end, p.type,
            f.type if f is not None else '', mpoint(p.path)))

    last = partitions[-1]
    new_end = src_dev.getLength()
    if last.fs == 'linux-swap(v1)':
        size = (last.end - last.start + 1) * src_dev.sectorSize
        meta['SWAP'] = "%d:%s" % (last.num, ((size + MB - 1) // MB))
        
        img_disk.deletePartition(img_disk.getPartitionBySector(last.start))
        img_disk.commit()

        if is_logical(last) and last.num == 5:
            img_disk.deletePartition(img_disk.getExtendedPartition())
            img_disk.commit()
            partitions.remove(filter(is_extended, partitions)[0])

        partitions.remove(last)
        last = partitions[-1]

        # Leave 2048 blocks at the end
        new_end = last.end + 2048

    if last.mpoint:
        stat = os.statvfs(last.mpoint)
        occupied_blocks = stat.f_blocks - stat.f_bavail
        new_size = (occupied_blocks * stat.f_frsize) // src_dev.sectorSize

        # Add 10% just to be on the safe side
        part_end = last.start + (new_size * 11) // 10
        # Alighn to 2048
        part_end = ((part_end + 2047) // 2048) * 2048
        last = last._replace(end=part_end)
        partitions[-1] = last
        
        # Leave 2048 blocks at the end.
        new_end = new_size + 2048

        img_disk.setPartitionGeometry(
            img_disk.getPartitionBySector(last.start),
            parted.Constraint(device=img_dev), start=last.start, end=last.end)
        img_disk.commit()

        if last.type == parted.PARTITION_LOGICAL:
            # Fix the extended partition
            ext = disk.getExtendedPartition()

            img_disk.setPartitionGeometry(ext,
                parted.Constraint(device=img_dev), ext.geometry.start,
                end=last.end)
            img_disk.commit()

    # Check if we have the available space on the filesystem hosting /mnt
    # for the image.
    out.output("Examining available space in /mnt ... ", False)
    stat = os.statvfs('/mnt')
    image_size = (new_end + 1) * src_dev.sectorSize
    available = stat.f_bavail * stat.f_frsize

    if available <= image_size:
        raise FatalError('Not enough space in /mnt to host the image')

    out.success("sufficient")

    return img

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
