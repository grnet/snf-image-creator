# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GRNET S.A.
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

"""This module hosts OS-specific code for Arch Linux."""

from image_creator.os_type.linux import Linux

import re


class Archlinux(Linux):
    """OS class for Arch Linux"""

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Archlinux, self)._do_collect_metadata()

        local_be = '/var/lib/pacman/local'

        if not self.image.g.is_dir(local_be):
            self.out.warn("Directory: `%s' does not exist!" % local_be)
            return

        kernel_regexp = re.compile(r'linux-(lts-)?(\d+[\.\d+]*-\d+)')
        for f in self.image.g.readdir(local_be):
            match = kernel_regexp.match(f['name'])
            if match:
                lts = match.group(1) is not None
                version = match.group(2)
                self.meta['KERNEL'] = "%s%s" % (version, " LTS" if lts else "")

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
