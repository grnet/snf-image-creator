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

from image_creator.util import get_command
from image_creator.util import FatalError

findfs = get_command('findfs')
truncate = get_command('truncate')
dd = get_command('dd')

def get_root_partition():
    if not os.path.isfile('/etc/fstab'):
        raise FatalError("Unable to open `/etc/fstab'. File is missing.")

    with open('/etc/fstab') as fstab:
        for line in iter(fstab):
            entry = line.split('#')[0].strip().split()
            if len(entry) != 6:
                continue

            if entry[1] == "/":
                return entry[0]

        raise FatalError("Unable to find root device in /etc/fstab")

def mnt_mounted():
    if not os.path.isfile('/etc/mtab'):
        raise FatalError("Unable to open `/etc/fstab'. File is missing.")

    with open('/etc/mtab') as mtab:
        for line in iter(mtab):
            entry = line.split('#')[0].strip().split()
            if len(entry) != 6:
                continue

            if entry[1] == '/mnt':
                return True

    return False


def part_to_dev(part):
    return re.split('[0-9]', part)[0]

def part_to_num(part):
    return re.split('[^0-9]+', part)[-1]

def bundle_volume(out):

    if mnt_mounted():
        raise FatalError('The directory /mnt where the image will be hosted'
            'is mounted. Please unmount it and start over again.')

    out.output('Searching for root device...', False)
    root_part = get_root_partition()

    if root_part.startswith("UUID=") or root_part.startswith("LABEL="):
        root_part = findfs(root_part)
    elif not root_part.startswith("/"):
        raise FatalError("Unable to find a block device for: %s" % root_dev)

    if not re.match('/dev/[hsv]d[a-z][1-9]*$', root_part):
        raise FatalError("Don't know how to handle root device: %s" % root_dev)

    device = parted.Device(part_to_dev(root_part))

    image = '/mnt/%s.diskdump' % uuid.uuid4().hex

    # Create sparse file to host the image
    truncate("-s", "%d" % (device.getLength() * device.sectorSize), image)

    disk = parted.Disk(device)
    if disk.type != 'msdos':
        raise FatalError('For now we can only handle msdos partition tables')

    # Copy the MBR and the space between the MBR and the first partition.
    # In Grub version 1 Stage 1.5 is located there.
    first_sector = disk.getPrimaryPartitions()[0].geometry.start

    dd('if=%s' % device.path, 'of=%s' % image, 'bs=%d' % device.sectorSize,
        'count=%d' % first_sector, 'conv=notrunc')

    return image

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
