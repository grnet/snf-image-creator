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

"""This module provides the Syslog output class"""

from __future__ import absolute_import
import syslog

from image_creator.output import Output


class SyslogOutput(Output):
    """This class implements the Output interface for the system logger"""
    def __init__(self, ident=None, logoption=None, facility=None):
        """Initialize a Syslog instance"""

        self.ident = ident if ident is not None else 'snf-image-creator'
        self.logoption = logoption if logoption is not None else syslog.LOG_PID
        self.facility = facility if facility is not None else syslog.LOG_USER
        self.line = []

        syslog.openlog(self.ident, self.logoption, self.facility)

    def error(self, msg):
        """Print an error to syslog"""

        if self.line:
            syslog.syslog(syslog.LOG_INFO, " ".join(self.line))
            self.line = []

        syslog.syslog(syslog.LOG_ERR, "[ERROR] %s" % msg)

    def warn(self, msg):
        """Print a warning"""

        if self.line:
            syslog.syslog(syslog.LOG_INFO, "[INFO] %s " % " ".join(self.line))
            self.line = []

        syslog.syslog(syslog.LOG_WARNING, "[WARNING] %s" % msg)

    def success(self, msg):
        """Print msg after an action is completed"""

        self.line.append(msg)
        syslog.syslog(syslog.LOG_INFO, "[INFO] %s" % " ".join(self.line))
        self.line = []

    def info(self, msg='', new_line=True):
        """Print normal program output"""

        if not msg:
            return

        self.line.append(msg)
        if new_line:
            syslog.syslog(syslog.LOG_INFO, "[INFO] %s" % " ".join(self.line))
            self.line = []

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
