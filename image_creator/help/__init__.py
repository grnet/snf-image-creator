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

"""This package hosts the help files of the program."""

import sys
import os


def get_help_file(name):
    """Returns the full path of a helpfile"""
    dirname = os.path.dirname(sys.modules[__name__].__file__)
    return "%s%s%s.rst" % (dirname, os.sep, name)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
