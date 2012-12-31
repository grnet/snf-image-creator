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

import subprocess
import time
import signal

from image_creator.util import FatalError


class Rsync:
    """Wrapper class for the rsync command"""

    def __init__(self, src, dest, exclude=[]):
        """Create an instance by defining a source, a destinationa and a number
        of exclude patterns.
        """
        self.src = src
        self.dest = dest
        self.exclude = exclude
        self.options = ['-v']

    def archive(self):
        """Enable the archive option"""
        self.options.append('-a')
        return self

    def run(self, out):
        """Run the actual command"""
        cmd = []
        cmd.append('rsync')
        cmd.extend(self.options)
        for i in self.exclude:
            cmd.extend(['--exclude', i])

        out.output("Calculating total number of host files ...", False)
        dry_run = subprocess.Popen(cmd + ['-n', self.src, self.dest],
                                   shell=False, stdout=subprocess.PIPE,
                                   bufsize=0)
        try:
            total = 0
            for line in iter(dry_run.stdout.readline, b''):
                total += 1
        finally:
            dry_run.communicate()
            if dry_run.returncode != 0:
                raise FatalError("rsync failed")

        out.success("%d" % total)

        progress = out.Progress(total, "Copying files into the image ... ")
        run = subprocess.Popen(cmd + [self.src, self.dest], shell=False,
                               stdout=subprocess.PIPE, bufsize=0)
        try:
            t = time.time()
            i = 0
            for line in iter(run.stdout.readline, b''):
                i += 1
                current = time.time()
                if current - t > 0.1:
                    t = current
                    progress.goto(i)

            progress.success('done')

        finally:
            run.poll()
            if run.returncode is None:
                run.send_signal(signal.SIGHUP)
            run.communicate()
            if run.returncode != 0:
                raise FatalError("rsync failed")


# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
