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

"""This module hosts code to handle unknown OSes."""

from image_creator.distro import OSBase


class Unsupported(OSBase):
    """OS class for unsupported OSes"""
    def __init__(self, image, **kwargs):
        super(Unsupported, self).__init__(image, **kwargs)

    def collect_metadata(self):
        """Collect metadata about the OS"""
        self.out.warn("Unable to collect metadata for unsupported media")

    def _do_mount(self, readonly):
        """Mount partitions in correct order"""
        self._mount_error = "not supported for this media"
        return False

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
