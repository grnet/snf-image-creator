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

"""This module hosts OS-specific code for OpenBSD."""

import re

from image_creator.os_type.bsd import Bsd


class Openbsd(Bsd):
    """OS class for OpenBSD"""

    def _check_enabled_sshd(self):
        """Check if the ssh daemon is enabled at boot"""

        sshd_enabled = True
        sshd_service = re.compile(r'^sshd_flags=')
        sshd_no = re.compile(r"^sshd_flags=(['\"]?)NO\1$")

        for rc_conf in ('/etc/rc.conf', '/etc/rc.conf.local'):
            if not self.image.g.is_file(rc_conf):
                self.out.warn("File: `%s' does not exist!" % rc_conf)
                continue

            for line in self.image.g.cat(rc_conf).splitlines():
                line = line.split('#')[0].strip()
                if sshd_service.match(line):
                    sshd_enabled = sshd_no.match(line) is None

        return sshd_enabled

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
