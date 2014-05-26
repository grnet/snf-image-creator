# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 GRNET S.A.
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

"""This module hosts OS-specific code for FreeBSD."""

from image_creator.os_type.unix import Unix, sysprep

import re


class Freebsd(Unix):
    """OS class for FreeBSD Unix-like operating system"""

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

    def _do_inspect(self):
        """Run various diagnostics to check if media is supported"""

        self.out.output('Checking partition table type...', False)
        ptype = self.image.g.part_get_parttype(self.image.guestfs_device)
        if ptype != 'gpt':
            self.out.warn("partition table type is: `%s'" % ptype)
            self.image.set_unsupported(
                'On FreeBSD only GUID partition tables are supported')
        else:
            self.out.success(ptype)

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

        # Older libguestfs versions can't handle correct FreeBSD partitions on
        # a GUID Partition Table. We have to do the translation to Linux device
        # names ourselves
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
                    self._mount_error = str(msg)
                    return False
                else:
                    self.out.warn('%s (ignored)' % msg)

        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
