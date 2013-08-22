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

"""Module hosting the Disk class."""

from image_creator.util import get_command
from image_creator.util import try_fail_repeat
from image_creator.util import free_space
from image_creator.util import FatalError
from image_creator.bundle_volume import BundleVolume
from image_creator.image import Image

import stat
import os
import tempfile
import uuid
import shutil

dd = get_command('dd')
dmsetup = get_command('dmsetup')
losetup = get_command('losetup')
blockdev = get_command('blockdev')


def get_tmp_dir(default=None):
    """Check tmp directory candidates and return the one with the most
    available space.
    """
    if default is not None:
        return default

    TMP_CANDIDATES = ['/var/tmp', os.path.expanduser('~'), '/mnt']

    space = map(free_space, TMP_CANDIDATES)

    max_idx = 0
    max_val = space[0]
    for i, val in zip(range(len(space)), space):
        if val > max_val:
            max_val = val
            max_idx = i

    # Return the candidate path with more available space
    return TMP_CANDIDATES[max_idx]


class Disk(object):
    """This class represents a hard disk hosting an Operating System

    A Disk instance never alters the source media it is created from.
    Any change is done on a snapshot created by the device-mapper of
    the Linux kernel.
    """

    def __init__(self, source, output, tmp=None):
        """Create a new Disk instance out of a source media. The source
        media can be an image file, a block device or a directory.
        """
        self._cleanup_jobs = []
        self._images = []
        self.source = source
        self.out = output
        self.meta = {}
        self.tmp = tempfile.mkdtemp(prefix='.snf_image_creator.',
                                    dir=get_tmp_dir(tmp))

        self._add_cleanup(shutil.rmtree, self.tmp)

    def _add_cleanup(self, job, *args):
        """Add a new job in the cleanup list"""
        self._cleanup_jobs.append((job, args))

    def _losetup(self, fname):
        """Setup a loop device and add it to the cleanup list. The loop device
        will be detached when cleanup is called.
        """
        loop = losetup('-f', '--show', fname)
        loop = loop.strip()  # remove the new-line char
        self._add_cleanup(try_fail_repeat, losetup, '-d', loop)
        return loop

    def _dir_to_disk(self):
        """Create a disk out of a directory"""
        if self.source == '/':
            bundle = BundleVolume(self.out, self.meta)
            image = '%s/%s.diskdump' % (self.tmp, uuid.uuid4().hex)

            def check_unlink(path):
                if os.path.exists(path):
                    os.unlink(path)

            self._add_cleanup(check_unlink, image)
            bundle.create_image(image)
            return self._losetup(image)
        raise FatalError("Using a directory as media source is supported")

    def cleanup(self):
        """Cleanup internal data. This needs to be called before the
        program ends.
        """
        try:
            while len(self._images):
                image = self._images.pop()
                image.destroy()
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

        self.out.output("Examining source media `%s' ..." % self.source, False)
        sourcedev = self.source
        mode = os.stat(self.source).st_mode
        if stat.S_ISDIR(mode):
            self.out.success('looks like a directory')
            return self._dir_to_disk()
        elif stat.S_ISREG(mode):
            self.out.success('looks like an image file')
            sourcedev = self._losetup(self.source)
        elif not stat.S_ISBLK(mode):
            raise FatalError("Invalid media source. Only block devices, "
                             "regular files and directories are supported.")
        else:
            self.out.success('looks like a block device')

        # Take a snapshot and return it to the user
        self.out.output("Snapshotting media source ...", False)
        size = blockdev('--getsz', sourcedev)
        cowfd, cow = tempfile.mkstemp(dir=self.tmp)
        os.close(cowfd)
        self._add_cleanup(os.unlink, cow)
        # Create cow sparse file
        dd('if=/dev/null', 'of=%s' % cow, 'bs=512', 'seek=%d' % int(size))
        cowdev = self._losetup(cow)

        snapshot = uuid.uuid4().hex
        tablefd, table = tempfile.mkstemp()
        try:
            try:
                os.write(tablefd, "0 %d snapshot %s %s n 8" %
                                  (int(size), sourcedev, cowdev))
            finally:
                os.close(tablefd)

            dmsetup('create', snapshot, table)
            self._add_cleanup(try_fail_repeat, dmsetup, 'remove', snapshot)
        finally:
            os.unlink(table)
        self.out.success('done')
        return "/dev/mapper/%s" % snapshot

    def get_image(self, media, **kargs):
        """Returns a newly created Image instance."""

        image = Image(media, self.out, **kargs)
        self._images.append(image)
        image.enable()
        return image

    def destroy_image(self, image):
        """Destroys an Image instance previously created by get_image method.
        """
        self._images.remove(image)
        image.destroy()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
