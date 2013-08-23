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

"""This module hosts OS-specific code common to all Unix-like OSs."""

from image_creator.os_type import OSBase, sysprep


class Unix(OSBase):
    """OS class for Unix"""
    sensitive_userdata = [
        '.history',
        '.bash_history',
        '.gnupg',
        '.ssh',
        '.kamakirc',
        '.kamaki.history'
    ]

    def _mountpoints(self):
        """Return mountpoints in the correct order.
        / should be mounted before /boot or /usr, /usr befor /usr/bin ...
        """
        mps = self.image.g.inspect_get_mountpoints(self.root)

        def compare(a, b):
            if len(a[0]) > len(b[0]):
                return 1
            elif len(a[0]) == len(b[0]):
                return 0
            else:
                return -1
        mps.sort(compare)

        for mp in mps:
            yield mp

    def _do_mount(self, readonly):
        """Mount partitions in the correct order"""

        critical_mpoints = ('/', '/etc', '/root', '/home', '/var')

        mopts = 'ro' if readonly else 'rw'
        for mp, dev in self._mountpoints():
            try:
                self.image.g.mount_options(mopts, dev, mp)
            except RuntimeError as msg:
                if mp in critical_mpoints:
                    self.out.warn('unable to mount %s. Reason: %s' % (mp, msg))
                    return False
                else:
                    self.out.warn('%s (ignored)' % msg)

        return True

    @sysprep('Removing files under /var/cache')
    def cleanup_cache(self):
        """Remove all regular files under /var/cache"""

        self._foreach_file('/var/cache', self.image.g.rm, ftype='r')

    @sysprep('Removing files under /tmp and /var/tmp')
    def cleanup_tmp(self):
        """Remove all files under /tmp and /var/tmp"""

        self._foreach_file('/tmp', self.image.g.rm_rf, maxdepth=1)
        self._foreach_file('/var/tmp', self.image.g.rm_rf, maxdepth=1)

    @sysprep('Emptying all files under /var/log')
    def cleanup_log(self):
        """Empty all files under /var/log"""

        self._foreach_file('/var/log', self.image.g.truncate, ftype='r')

    @sysprep('Removing files under /var/mail & /var/spool/mail', enabled=False)
    def cleanup_mail(self):
        """Remove all files under /var/mail and /var/spool/mail"""

        self._foreach_file('/var/spool/mail', self.image.g.rm_rf, maxdepth=1)

        self._foreach_file('/var/mail', self.image.g.rm_rf, maxdepth=1)

    @sysprep('Removing sensitive user data')
    def cleanup_userdata(self):
        """Delete sensitive userdata"""

        homedirs = ['/root']
        if self.image.g.is_dir('/home/'):
            homedirs += self._ls('/home/')

        action = self.image.g.rm_rf
        if self._scrub_support:
            action = self.image.g.scrub_file
        else:
            self.out.warn("Sensitive data won't be scrubbed (not supported)")

        for homedir in homedirs:
            for data in self.sensitive_userdata:
                fname = "%s/%s" % (homedir, data)
                if self.image.g.is_file(fname):
                    action(fname)
                elif self.image.g.is_dir(fname):
                    self._foreach_file(fname, action, ftype='r')

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
