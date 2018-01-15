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

"""This module hosts OS-specific code for Ubuntu Linux."""

import re

from image_creator.distro.linux import Linux


class Ubuntu(Linux):
    """OS class for Ubuntu Linux variants"""

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""

        super(Ubuntu, self)._do_collect_metadata()

        regexp = re.compile('^(k|l|x)ubuntu-desktop$')
        variant = ""
        for app in self.image.g.inspect_list_applications(self.root):
            match = regexp.match(app['app_name'])
            if match:
                variant = match.group(1) + 'ubuntu'
                break

        if variant:
            self.meta['OS'] = variant
            descr = self.meta['DESCRIPTION'].replace('Ubuntu',
                                                     variant.capitalize())
            self.meta['DESCRIPTION'] = descr

        # Check if this is a bitnami image
        if self.image.g.is_dir('/opt/bitnami'):
            self.meta['OS'] = 'bitnami'
            readme = '/opt/bitnami/README.txt'
            if self.image.g.is_file(readme):
                content = self.image.g.cat(readme).splitlines()
                if content:
                    self.meta['OSVERSION'] = self.meta['DESCRIPTION']
                    self.meta['DESCRIPTION'] = content[0].strip()


# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
