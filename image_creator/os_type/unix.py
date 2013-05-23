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

import re

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

    def __init__(self, rootdev, ghandler, output):
        super(Unix, self).__init__(rootdev, ghandler, output)

    @sysprep()
    def cleanup_cache(self, print_header=True):
        """Remove all regular files under /var/cache"""

        if print_header:
            self.out.output('Removing files under /var/cache')

        self.foreach_file('/var/cache', self.g.rm, ftype='r')

    @sysprep()
    def cleanup_tmp(self, print_header=True):
        """Remove all files under /tmp and /var/tmp"""

        if print_header:
            self.out.output('Removing files under /tmp and /var/tmp')

        self.foreach_file('/tmp', self.g.rm_rf, maxdepth=1)
        self.foreach_file('/var/tmp', self.g.rm_rf, maxdepth=1)

    @sysprep()
    def cleanup_log(self, print_header=True):
        """Empty all files under /var/log"""

        if print_header:
            self.out.output('Emptying all files under /var/log')

        self.foreach_file('/var/log', self.g.truncate, ftype='r')

    @sysprep(enabled=False)
    def cleanup_mail(self, print_header=True):
        """Remove all files under /var/mail and /var/spool/mail"""

        if print_header:
            self.out.output('Removing files under /var/mail & /var/spool/mail')

        if self.g.is_dir('/var/spool/mail'):
            self.foreach_file('/var/spool/mail', self.g.rm_rf, maxdepth=1)

        self.foreach_file('/var/mail', self.g.rm_rf, maxdepth=1)

    @sysprep()
    def cleanup_userdata(self, print_header=True):
        """Delete sensitive userdata"""

        homedirs = ['/root']
        if self.g.is_dir('/home/'):
            homedirs += self.ls('/home/')

        if print_header:
            self.out.output("Removing sensitive user data under %s" %
                            " ".join(homedirs))

        for homedir in homedirs:
            for data in self.sensitive_userdata:
                fname = "%s/%s" % (homedir, data)
                if self.g.is_file(fname):
                    self.g.scrub_file(fname)
                elif self.g.is_dir(fname):
                    self.foreach_file(fname, self.g.scrub_file, ftype='r')

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
