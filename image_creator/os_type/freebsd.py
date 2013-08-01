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

"""This module hosts OS-specific code for FreeBSD."""

from image_creator.os_type.unix import Unix, sysprep

import re


class Freebsd(Unix):
    """OS class for FreeBSD Unix-like os"""

    @sysprep("Cleaning up passwords & locking all user accounts")
    def cleanup_password(self):
        """Remove all passwords and lock all user accounts"""

        master_passwd = []

        for line in self.image.g.cat('/etc/master.passwd').splitlines():

            # Check for empty or comment lines
            if len(line.split('#')[0]) == 0:
                master_passwd.append(line)
                continue

            fields = line.split(':')
            if fields[1] not in ('*', '!'):
                fields[1] = '!'

            master_passwd.append(":".join(fields))

        self.image.g.write(
            '/etc/master.passwd', "\n".join(master_passwd) + '\n')

        # Make sure no one can login on the system
        self.image.g.rm_rf('/etc/spwd.db')

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Freebsd, self)._do_collect_metadata()
        self.meta["USERS"] = " ".join(self._get_passworded_users())

        #The original product name key is long and ugly
        self.meta['DESCRIPTION'] = \
            self.meta['DESCRIPTION'].split('#')[0].strip()

        # Delete the USERS metadata if empty
        if not len(self.meta['USERS']):
            self.out.warn("No passworded users found!")
            del self.meta['USERS']

    def _get_passworded_users(self):
        """Returns a list of non-locked user accounts"""
        users = []
        regexp = re.compile(
            '^([^:]+):((?:![^:]+)|(?:[^!*][^:]+)|):(?:[^:]*:){7}(?:[^:]*)'
        )

        for line in self.image.g.cat('/etc/master.passwd').splitlines():
            line = line.split('#')[0]
            match = regexp.match(line)
            if not match:
                continue

            user, passwd = match.groups()
            if len(passwd) > 0 and passwd[0] == '!':
                self.out.warn("Ignoring locked %s account." % user)
            else:
                users.append(user)

        return users

    def _do_mount(self, readonly):
        """Mount partitions in the correct order"""

        critical_mpoints = ('/', '/etc', '/root', '/home', '/var')

        # libguestfs can't handle correct freebsd partitions on a GUID
        # Partition Table. We have to do the translation to linux device names
        # ourselves
        guid_device = re.compile(r'^/dev/((?:ada)|(?:vtbd))(\d+)p(\d+)$')

        mopts = "ufstype=ufs2,%s" % ('ro' if readonly else 'rw')
        for mp, dev in self._mountpoints():
            match = guid_device.match(dev)
            if match:
                group2 = int(match.group(2))
                group3 = int(match.group(3))
                dev = '/dev/sd%c%d' % (chr(ord('a') + group2), group3)
            try:
                self.image.g.mount_vfs(mopts, 'ufs', dev, mp)
            except RuntimeError as msg:
                if mp in critical_mpoints:
                    self.out.warn('unable to mount %s. Reason: %s' % (mp, msg))
                    return False
                else:
                    self.out.warn('%s (ignored)' % msg)

        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
