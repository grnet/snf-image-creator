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

"""This module implements the CompositeOutput output class"""

from image_creator.output import Output


class CompositeOutput(Output):
    """This class can be used to composite different outputs into a single one

    You may create an instance of this class and then add other output
    instances to it. Executing a method on this instance will cause the
    execution of the same method in each output instance that has been added to
    this one.
    """

    def __init__(self, outputs=[]):
        """Add initial output instances"""
        self._outputs = outputs

    def add(self, output):
        """Add another output instance"""
        self._outputs.append(output)

    def remove(self, output):
        """Remove an output instance"""
        self._outputs.remove(output)

    def error(self, msg, new_line=True):
        """Call the error method of each of the output instances"""
        for out in self._outputs:
            out.error(msg, new_line)

    def warn(self, msg, new_line=True):
        """Call the warn method of each of the output instances"""
        for out in self._outputs:
            out.warn(msg, new_line)

    def success(self, msg, new_line=True):
        """Call the success method of each of the output instances"""
        for out in self._outputs:
            out.success(msg, new_line)

    def output(self, msg='', new_line=True):
        """Call the output method of each of the output instances"""
        for out in self._outputs:
            out.output(msg, new_line)

    def cleanup(self):
        """Call the cleanup method of each of the output instances"""
        for out in self._outputs:
            out.cleanup()

    def clear(self):
        """Call the clear method of each of the output instances"""
        for out in self._outputs:
            out.clear()

    class _Progress(object):
        """Class used to composite different Progress objects"""

        def __init__(self, size, title, bar_type='default'):
            """Create a progress on each of the added output instances"""
            self._progresses = []
            for out in self.output._outputs:
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
