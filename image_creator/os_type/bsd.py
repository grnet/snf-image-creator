# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2017 GRNET S.A.
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

"""This module hosts OS-specific code for *BSD."""

import re

from image_creator.os_type.unix import Unix, sysprep


class Bsd(Unix):
    """OS class for *BSD Unix-like operating system"""

    @sysprep("Cleaning up passwords & locking all user accounts")
    def _cleanup_password(self):
        """Remove all passwords and lock all user accounts"""

        if not self.image.g.is_file('/etc/master.passwd'):
            self.out.warn(
                "File: `/etc/master.passwd' is missing. Nothing to do!")
            return

        master_passwd = []

        for line in self.image.g.cat('/etc/master.passwd').splitlines():

            # Check for empty or comment lines
            if not line.split('#')[0]:
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

    def _check_enabled_sshd(self):
        """Check if the ssh daemon is enabled at boot"""
        return False

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Bsd, self)._do_collect_metadata()

        users = self._get_passworded_users()

        self.meta["USERS"] = " ".join(users)

        # The original product name key is long and ugly
        self.meta['DESCRIPTION'] = \
            self.meta['DESCRIPTION'].split('#')[0].strip()

        # Delete the USERS metadata if empty
        if not self.meta['USERS']:
            self.out.warn("No passworded users found!")
            del self.meta['USERS']

        major = self.image.g.inspect_get_major_version(self.root)
        minor = self.image.g.inspect_get_minor_version(self.root)

        self.meta['KERNEL'] = "%sBSD %d.%d" % \
            (self.__class__.__name__[:-3], major, minor)
        self.meta['SORTORDER'] += 100 * major + minor

        # Check if ssh is enabled
        sshd_enabled = self._check_enabled_sshd()

        if sshd_enabled:
            ssh = []
            opts = self.ssh_connection_options(users)
            for user in opts['users']:
                ssh.append("ssh:port=%d,user=%s" % (opts['port'], user))

            if 'REMOTE_CONNECTION' not in self.meta:
                self.meta['REMOTE_CONNECTION'] = ""
            else:
                self.meta['REMOTE_CONNECTION'] += " "

            if users:
                self.meta['REMOTE_CONNECTION'] += " ".join(ssh)
            else:
                self.meta['REMOTE_CONNECTION'] += "ssh:port=%d" % opts['port']
        else:
            self.out.warn("OpenSSH Daemon is not configured to run on boot")

    def _get_passworded_users(self):
        """Returns a list of non-locked user accounts"""

        if not self.image.g.is_file('/etc/master.passwd'):
            self.out.warn("Unable to collect user info. "
                          "File: `/etc/master.passwd' is missing!")
            return []

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
            if passwd and passwd[0] == '!':
                self.out.warn("Ignoring locked %s account." % user)
            else:
                # Put root in the beginning.
                if user == 'root':
                    users.insert(0, user)
                else:
                    users.append(user)

        return users

    def _do_mount(self, readonly):
        """Mount partitions in the correct order"""

        critical_mpoints = ('/', '/etc', '/root', '/home', '/var')

        mopts1 = "ufstype=44bsd,%s" % ('ro' if readonly else 'rw')
        mopts2 = "ufstype=ufs2,%s" % ('ro' if readonly else 'rw')
        for mp, dev in self._mountpoints():
            try:
                try:
                    self.image.g.mount_vfs(mopts2, 'ufs', dev, mp)
                except RuntimeError:
                    self.image.g.mount_vfs(mopts1, 'ufs', dev, mp)
            except RuntimeError as msg:
                if mp in critical_mpoints:
                    self._mount_error = str(msg)
                    return False
                else:
                    self._mount_warnings.append('%s (ignored)' % msg)

        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
