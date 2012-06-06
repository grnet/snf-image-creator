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

import sys
from progress.bar import Bar
from colors import red, green, yellow


def error(msg, new_line=True, color=True):
    nl = "\n" if new_line else ''
    if color:
        sys.stderr.write(red('Error: %s' % msg) + nl)
    else:
        sys.stderr.write('Error: %s' % msg + nl)


def warn(msg, new_line=True, color=True):
    nl = "\n" if new_line else ''
    if color:
        sys.stderr.write(yellow("Warning: %s" % msg) + nl)
    else:
        sys.stderr.write("Warning: %s" % msg + nl)


def success(msg, new_line=True, color=True):
    nl = "\n" if new_line else ''
    if color:
        sys.stdout.write(green(msg) + nl)
    else:
        sys.stdout.write(msg + nl)
    if not nl:
        sys.stdout.flush()


def output(msg='', new_line=True):
    nl = "\n" if new_line else ''
    sys.stdout.write(msg + nl)
    if not nl:
        sys.stdout.flush()


class Output(object):
    def error(self, msg, new_line=True):
        error(msg, new_line, False)

    def warn(self, msg, new_line=True):
        warn(msg, new_line, False)

    def success(self, msg, new_line=True):
        success(msg, new_line, False)

    def output(self, msg='', new_line=True):
        output(msg, new_line)

    class Progress(object):
        def __init__(self, title, bar_type='default'):
            output("%s..." % title, False)

        def goto(self, dest):
            pass

        def next(self):
            pass

        def success(self, result):
            sucess(result)

    def progress_generator(self, message):
        def generator(n):
            progressbar = self.Progress(message, 'default')
            progressbar.max = n

            for _ in range(n):
                yield
                progressbar.next()

            progressbar.success('done')
            yield
        return generator


class Output_wth_colors(Output):
    def error(self, msg, new_line=True):
        error(msg, new_line)

    def warn(self, msg, new_line=True):
        warn(msg, new_line)

    def success(self, msg, new_line=True):
        success(msg, new_line)


class Output_wth_progress(Output_wth_colors):
    class Progress(Bar):
        MESSAGE_LENGTH = 30

        template = {
            'default': '%(index)d/%(max)d',
            'percent': '%(percent)d%%',
            'b': '%(index)d/%(max)d B',
            'kb': '%(index)d/%(max)d KB',
            'mb': '%(index)d/%(max)d MB'
        }

        def __init__(self, title, bar_type='default'):
            super(Output_wth_progress.Progress, self).__init__()
            self.title = title
            self.fill = '#'
            self.bar_prefix = ' ['
            self.bar_suffix = '] '
            self.message = ("%s:" % self.title).ljust(self.MESSAGE_LENGTH)
            self.suffix = self.template[bar_type]

        def success(self, result):
            output("\r%s... \033[K" % self.title, False)
            success(result)


class Silent(Output):
    def warn(self, msg, new_line=True):
        pass

    def success(self, msg, new_line=True):
        pass

    def output(self, msg='', new_line=True):
        pass

    class Progress(Output.Progress):
        def __init__(self, title, bar_type='default'):
            pass

        def success(self, result):
            pass

class Silent_wth_colors(Silent):
    def error(self, msg, new_line=True):
        error(msg, new_line)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
