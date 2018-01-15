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

"""This module hosts OS-specific code for GNU Hurd."""

from image_creator.distro.unix import Unix


class Hurd(Unix):
    """OS class for GNU Hurd"""
    pass

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
