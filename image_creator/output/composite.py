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

"""This module implements the CompositeOutput output class"""

from image_creator.output import Output


class CompositeOutput(Output, list):
    """This class can be used to composite different outputs into a single one

    You may create an instance of this class and then add other output
    instances to it. Executing a method on this instance will cause the
    execution of the same method in each output instance that has been added to
    this one.
    """

    def __init__(self, outputs=None):
        """Add initial output instances"""
        super(CompositeOutput, self).__init__()

        if outputs is not None:
            self.extend(outputs)

    def error(self, msg, new_line=True):
        """Call the error method of each of the output instances"""
        for out in self:
            out.error(msg, new_line)

    def warn(self, msg, new_line=True):
        """Call the warn method of each of the output instances"""
        for out in self:
            out.warn(msg, new_line)

    def success(self, msg, new_line=True):
        """Call the success method of each of the output instances"""
        for out in self:
            out.success(msg, new_line)

    def output(self, msg='', new_line=True):
        """Call the output method of each of the output instances"""
        for out in self:
            out.output(msg, new_line)

    def cleanup(self):
        """Call the cleanup method of each of the output instances"""
        for out in self:
            out.cleanup()

    def clear(self):
        """Call the clear method of each of the output instances"""
        for out in self:
            out.clear()

    class _Progress(object):
        """Class used to composite different Progress objects"""

        def __init__(self, size, title, bar_type='default'):
            """Create a progress on each of the added output instances"""
            self._progresses = []
            for out in self.parent:
                self._progresses.append(out.Progress(size, title, bar_type))

        def goto(self, dest):
            """Call the goto method of each of the progress instances"""
            for progress in self._progresses:
                progress.goto(dest)

        def next(self):
            """Call the next method of each of the progress instances"""
            for progress in self._progresses:
                progress.next()

        def success(self, result):
            """Call the success method of each of the progress instances"""
            for progress in self._progresses:
                progress.success(result)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
