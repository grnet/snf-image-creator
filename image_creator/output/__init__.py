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


class Output(object):
    def error(self, msg, new_line=True):
        pass

    def warn(self, msg, new_line=True):
        pass

    def success(self, msg, new_line=True):
        pass

    def output(self, msg='', new_line=True):
        pass

    def cleanup(self):
        pass

    def _get_progress(self):
        progress = self._Progress
        progress.output = self
        return progress

    Progress = property(_get_progress)

    class _Progress(object):
        def __init__(self, size, title, bar_type='default'):
            self.size = size
            self.bar_type = bar_type
            self.output.output("%s..." % title, False)

        def goto(self, dest):
            pass

        def next(self):
            pass

        def success(self, result):
            self.output.success(result)

    def progress_generator(self, message):
        def generator(n):
            progressbar = self.Progress(n, message)

            for _ in range(n):
                yield
                progressbar.next()

            progressbar.success('done')
            yield
        return generator

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
