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

"""This module hosts OS-specific code for Red Hat Enterprise Linux"""

from image_creator.os_type.linux import Linux


class Rhel(Linux):
    "OS class for Red Hat Enterprise Linux"""

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Rhel, self)._do_collect_metadata()

        # Check if the image is Oracle Linux
        oracle = '/etc/oracle-release'
        if self.image.g.is_file(oracle):
            self.meta['OS'] = 'oraclelinux'
            self.meta['DESCRIPTION'] = self.image.g.head_n(1, oracle)[0]


# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
