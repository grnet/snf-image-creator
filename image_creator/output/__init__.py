# -*- coding: utf-8 -*-
#
# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

"""This package is intended to provide output classes for printing messages and
progress bars. The user can change the output behaviour of the program by
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
        progress.output = self
        return progress

    Progress = property(_get_progress)

    class _Progress(object):
        """Internal progress bar class"""
        def __init__(self, size, title, bar_type='default'):
            self.size = size
            self.bar_type = bar_type
            self.output.output("%s ..." % title, False)

        def goto(self, dest):
            """Move progress to a specific position"""
            pass

        def next(self):
            """Move progress a step forward"""
            pass

        def success(self, result):
            """Print a msg after an action is completed successfully"""
            self.output.success(result)

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
