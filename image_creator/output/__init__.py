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

"""This package is intended to provide output classes for printing messages and
progress bars. The user can change the output behavior of the program by
subclassing the Output class and assigning the derived one as the output class
of the various parts of the image-creator package.
"""


class Output(object):
    """A class for printing program output"""
    def error(self, msg, new_line=True):
        """Print an error"""
        pass

    def warn(self, msg, new_line=True):
        """Print a warning"""
        pass

    def success(self, msg, new_line=True):
        """Print msg after an action is completed"""
        pass

    def output(self, msg='', new_line=True):
        """Print normal program output"""
        pass

    def cleanup(self):
        """Cleanup this output class"""
        pass

    def clear(self):
        """Clear the screen"""
        pass

    def _get_progress(self):
        """Returns a new Progress object"""
        progress = self._Progress
        progress.parent = self
        return progress

    Progress = property(_get_progress)

    class _Progress(object):
        """Internal progress bar class"""
        def __init__(self, size, title, bar_type='default'):
            self.size = size
            self.bar_type = bar_type
            self.parent.output("%s ..." % title, False)

        def goto(self, dest):
            """Move progress to a specific position"""
            pass

        def next(self):
            """Move progress a step forward"""
            pass

        def success(self, result):
            """Print a msg after an action is completed successfully"""
            self.parent.success(result)

    def progress_generator(self, message):
        """A python generator for the progress bar class"""
        def generator(n):
            progressbar = self.Progress(n, message)

            for _ in range(n):
                yield
                progressbar.next()

            progressbar.success('done')
            yield
        return generator

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
