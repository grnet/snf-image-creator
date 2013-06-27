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

"""Normal Command-line interface output"""

from image_creator.output import Output

import sys
from colors import red, green, yellow
from progress.bar import Bar


def output(msg, new_line, decorate, stream):
    nl = "\n" if new_line else ' '
    stream.write(decorate(msg) + nl)


def error(msg, new_line, colored, stream):
    color = red if colored else lambda x: x
    output("Error: %s" % msg, new_line, color, stream)


def warn(msg, new_line, colored, stream):
    color = yellow if colored else lambda x: x
    output("Warning: %s" % msg, new_line, color, stream)


def success(msg, new_line, colored, stream):
    color = green if colored else lambda x: x
    output(msg, new_line, color, stream)


def clear(stream):
    """Clears the terminal screen."""
    if stream.isatty():
        stream.write('\033[H\033[2J')


class SilentOutput(Output):
    """Silent Output class. Only Errors are printed"""
    pass


class SimpleOutput(Output):
    """Print messages but not progress bars. Progress bars are treated as
    output messages. The user gets informed when the action begins and when it
    ends, but no progress is shown in between."""
    def __init__(self, colored=True, stream=None):
        self.colored = colored
        self.stream = sys.stderr if stream is None else stream

    def error(self, msg, new_line=True):
        """Print an error"""
        error(msg, new_line, self.colored, self.stream)

    def warn(self, msg, new_line=True):
        """Print a warning"""
        warn(msg, new_line, self.colored, self.stream)

    def success(self, msg, new_line=True):
        """Print msg after an action is completed"""
        success(msg, new_line, self.colored, self.stream)

    def output(self, msg='', new_line=True):
        """Print msg as normal program output"""
        output(msg, new_line, lambda x: x, self.stream)

    def clear(self):
        """Clear the screen"""
        clear(self.stream)


class OutputWthProgress(SimpleOutput):
    """Output class with progress."""
    class _Progress(Bar):
        MESSAGE_LENGTH = 30

        template = {
            'default': '%(index)d/%(max)d',
            'percent': '%(percent)d%%',
            'b': '%(index)d/%(max)d B',
            'kb': '%(index)d/%(max)d KB',
            'mb': '%(index)d/%(max)d MB'
        }

        def __init__(self, size, title, bar_type='default'):
            """Create a Progress bar"""
            self.hide_cursor = False
            super(OutputWthProgress._Progress, self).__init__()
            self.title = title
            self.fill = '#'
            self.bar_prefix = ' ['
            self.bar_suffix = '] '
            self.message = ("%s:" % self.title).ljust(self.MESSAGE_LENGTH)
            self.suffix = self.template[bar_type]
            self.max = size

            # print empty progress bar
            self.start()

        def success(self, result):
            """Print result after progress has finished"""
            self.output.output("\r%s ...\033[K" % self.title, False)
            self.output.success(result)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
