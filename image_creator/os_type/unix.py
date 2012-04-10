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
import sys

from image_creator.os_type import OSBase, sysprep
from image_creator.util import warn, output


class Unix(OSBase):

    sensitive_userdata = [
        '.bash_history',
        '.gnupg',
        '.ssh',
        '.mozilla',
        '.thunderbird'
    ]

    def get_metadata(self):
        meta = super(Unix, self).get_metadata()
        meta["USERS"] = " ".join(self.get_passworded_users())
        return meta

    def get_passworded_users(self):
        users = []
        regexp = re.compile('(\S+):((?:!\S+)|(?:[^!*]\S+)|):(?:\S*:){6}')

        for line in self.g.cat('/etc/shadow').splitlines():
            match = regexp.match(line)
            if not match:
                continue

            user, passwd = match.groups()
            if len(passwd) > 0 and passwd[0] == '!':
                warn("Ignoring locked %s account." % user)
            else:
                users.append(user)

        return users

    @sysprep(enabled=False)
    def remove_user_accounts(self, print_header=True):
        """Remove all user account with id more than 1000"""

        if print_header:
            output('Removing all user accounts with id greater than 1000')

        # Remove users from /etc/passwd
        passwd = []
        removed_users = {}
        for line in self.g.cat('/etc/passwd').splitlines():
            fields = line.split(':')
            if int(fields[2]) > 1000:
                removed_users[fields[0]] = fields
            else:
                passwd.append(':'.join(fields))

        self.g.write('/etc/passwd', '\n'.join(passwd) + '\n')

        # Remove the corresponding /etc/shadow entries
        shadow = []
        for line in self.g.cat('/etc/shadow').splitlines():
            fields = line.split(':')
            if fields[0] not in removed_users:
                shadow.append(':'.join(fields))

        self.g.write('/etc/shadow', "\n".join(shadow) + '\n')

        # Remove the corresponding /etc/group entries
        group = []
        for line in self.g.cat('/etc/group').splitlines():
            fields = line.split(':')
            # Remove groups tha have the same name as the removed users
            if fields[0] not in removed_users:
                group.append(':'.join(fields))

        self.g.write('/etc/group', '\n'.join(group) + '\n')

        # Remove home directories
        for home in [field[5] for field in removed_users.values()]:
            if self.g.is_dir(home) and home.startswith('/home/'):
                self.g.rm_rf(home)

    @sysprep()
    def cleanup_passwords(self, print_header=True):
        """Remove all passwords and lock all user accounts"""

        if print_header:
            output('Cleaning up passwords & locking all user accounts')

        shadow = []

        for line in self.g.cat('/etc/shadow').splitlines():
            fields = line.split(':')
            if fields[1] not in ('*', '!'):
                fields[1] = '!'

            shadow.append(":".join(fields))

        self.g.write('/etc/shadow', "\n".join(shadow) + '\n')

    @sysprep()
    def cleanup_cache(self, print_header=True):
        """Remove all regular files under /var/cache"""

        if print_header:
            output('Removing files under /var/cache')

        self.foreach_file('/var/cache', self.g.rm, ftype='r')

    @sysprep()
    def cleanup_tmp(self, print_header=True):
        """Remove all files under /tmp and /var/tmp"""

        if print_header:
            output('Removing files under /tmp and /var/tmp')

        self.foreach_file('/tmp', self.g.rm_rf, maxdepth=1)
        self.foreach_file('/var/tmp', self.g.rm_rf, maxdepth=1)

    @sysprep()
    def cleanup_log(self, print_header=True):
        """Empty all files under /var/log"""

        if print_header:
            output('Emptying all files under /var/log')

        self.foreach_file('/var/log', self.g.truncate, ftype='r')

    @sysprep(enabled=False)
    def cleanup_mail(self, print_header=True):
        """Remove all files under /var/mail and /var/spool/mail"""

        if print_header:
            output('Removing files under /var/mail and /var/spool/mail')

        self.foreach_file('/var/spool/mail', self.g.rm_rf, maxdepth=1)
        self.foreach_file('/var/mail', self.g.rm_rf, maxdepth=1)

    @sysprep()
    def cleanup_userdata(self, print_header=True):
        """Delete sensitive userdata"""

        homedirs = ['/root'] + self.ls('/home/')

        if print_header:
            output('Removing sensitive user data under %s' % " ".
                                                        join(homedirs))

        for homedir in homedirs:
            for data in self.sensitive_userdata:
                fname = "%s/%s" % (homedir, data)
                if self.g.is_file(fname):
                    self.g.scrub_file(fname)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
