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

from image_creator.output import Output


class CompositeOutput(Output):
    """This class can be used to composite different outputs into a single one

    You may create an instance of this class and then add other output
    instances to it. Executing a method on this instance will cause the
    execution of the same method in each output instance that has been added to
    this one.
    """

    def __init__(self, outputs=[]):
        self._outputs = outputs

    def add(self, output):
        self._outputs.append(output)

    def remove(self, output):
        self._outputs.remove(output)

    def error(self, msg, new_line=True):
        for out in self._outputs:
            out.error(msg, new_line)

    def warn(self, msg, new_line=True):
        for out in self._outputs:
            out.warn(msg, new_line)

    def success(self, msg, new_line=True):
        for out in self._outputs:
            out.success(msg, new_line)

    def output(self, msg='', new_line=True):
        for out in self._outputs:
            out.output(msg, new_line)

    def cleanup(self):
        for out in self._outputs:
            out.cleanup()

    def clear(self):
        for out in self._outputs:
            out.clear()

    class _Progress(object):

        def __init__(self, size, title, bar_type='default'):
            self._progresses = []
            for out in self.output._outputs:
                self._progresses.append(out.Progress(size, title, bar_type))

        def goto(self, dest):
            for progress in self._progresses:
                progress.goto(dest)

        def next(self):
            for progress in self._progresses:
                progress.next()

        def success(self, result):
            for progress in self._progresses:
                progress.success(result)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
