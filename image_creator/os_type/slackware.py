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

"""This module hosts OS-specific code for Slackware Linux."""

from image_creator.os_type.linux import Linux, sysprep


class Slackware(Linux):
    """OS class for Slackware Linux"""
    @sysprep("Emptying all files under /var/log")
    def _cleanup_log(self):
        """Empty all files under /var/log"""

        # In Slackware the metadata about installed packages are
        # stored in /var/log/packages. Clearing all /var/log files
        # will destroy the package management system.
        self._foreach_file('/var/log', self.image.g.truncate, ftype='r',
                           exclude='/var/log/packages')

    def is_enabled(self, service):
        """Check if a service is enabled to start on boot"""

        name = '/etc/rc.d/%s' % service
        # In slackware a service will be executed during boot if the
        # execute bit is set for the root
        if self.image.g.is_file(name):
            return self.image.g.stat(name)['mode'] & 0400

        self.out.warn('Service %s not found on the media' % service)
        return False

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
