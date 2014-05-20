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

"""This module hosts OS-specific code for Ubuntu Linux"""

from image_creator.os_type.linux import Linux


class Ubuntu(Linux):
    """OS class for Ubuntu Linux variants"""

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""

        super(Ubuntu, self)._do_collect_metadata()
        apps = self.image.g.inspect_list_applications(self.root)
        for app in apps:
            if app['app_name'] == 'kubuntu-desktop':
                self.meta['OS'] = 'kubuntu'
                descr = self.meta['DESCRIPTION'].replace('Ubuntu', 'Kubuntu')
                self.meta['DESCRIPTION'] = descr
                break

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
