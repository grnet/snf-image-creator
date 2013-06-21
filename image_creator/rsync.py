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

"""This module provides an interface for the rsync utility"""

import subprocess
import time
import signal

from image_creator.util import FatalError


class Rsync:
    """Wrapper class for the rsync command"""

    def __init__(self, output):
        """Create an instance """
        self._out = output
        self._exclude = []
        self._options = ['-v']

    def archive(self):
        """Enable the archive option"""
        self._options.append('-a')
        return self

    def xattrs(self):
        """Preserve extended attributes"""
        self._options.append('-X')
        return self

    def hard_links(self):
        """Preserve hard links"""
        self._options.append('-H')
        return self

    def acls(self):
        """Preserve ACLs"""
        self._options.append('-A')
        return self

    def sparse(self):
        """Handle sparse files efficiently"""
        self._options.append('-S')
        return self

    def exclude(self, pattern):
        """Add an exclude pattern"""
        self._exclude.append(pattern)
        return self

    def reset(self):
        """Reset all rsync options"""
        self._exclude = []
        self._options = ['-v']

    def run(self, src, dest, slabel='source', dlabel='destination'):
        """Run the actual command"""
        cmd = []
        cmd.append('rsync')
        cmd.extend(self._options)
        for i in self._exclude:
            cmd.extend(['--exclude', i])

        self._out.output("Calculating total number of %s files ..." % slabel,
                         False)

        # If you don't specify a destination, rsync will list the source files.
        dry_run = subprocess.Popen(cmd + [src], shell=False,
                                   stdout=subprocess.PIPE, bufsize=0)
        try:
            total = 0
            for _ in iter(dry_run.stdout.readline, b''):
                total += 1
        finally:
            dry_run.communicate()
            if dry_run.returncode != 0:
                raise FatalError("rsync failed")

        self._out.success("%d" % total)

        progress = self._out.Progress(total, "Copying files to %s" % dlabel)
        run = subprocess.Popen(cmd + [src, dest], shell=False,
                               stdout=subprocess.PIPE, bufsize=0)
        try:
            t = time.time()
            i = 0
            for _ in iter(run.stdout.readline, b''):
                i += 1
                current = time.time()
                if current - t > 0.1:
                    t = current
                    progress.goto(i)

            progress.success('done')

        finally:
            def handler(signum, frame):
                run.terminate()
                time.sleep(1)
                run.poll()
                if run.returncode is None:
                    run.kill()
                run.wait()

            signal.signal(signal.SIGALRM, handler)
            signal.alarm(2)
            run.communicate()
            signal.alarm(0)
            if run.returncode != 0:
                raise FatalError("rsync failed")

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
