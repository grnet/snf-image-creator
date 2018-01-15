# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2018 GRNET S.A.
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

"""This module hosts OS-specific code for NetBSD."""

import re

from image_creator.distro.bsd import Bsd


class Netbsd(Bsd):
    """OS class for NetBSD"""

    def _check_enabled_sshd(self):
        """Check if the ssh daemon is enabled at boot"""

        sshd_enabled = False
        sshd_service = re.compile(r'\bsshd=')
        sshd_yes = re.compile(r"\bsshd=(['\"]?)(YES|TRUE|ON|1)\1\b")

        for rc_conf in ('/etc/defaults/rc.conf', '/etc/rc.conf'):
            if not self.image.g.is_file(rc_conf):
                self.out.warn("File: `%s' does not exist!" % rc_conf)
                continue

            for line in self.image.g.cat(rc_conf).splitlines():
                line = line.split('#')[0].strip()
                if sshd_service.match(line):
                    sshd_enabled = bool(sshd_yes.findall(line))

        return sshd_enabled

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
