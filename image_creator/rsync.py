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

"""This module provides an interface for the rsync utility."""

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

        self._out.info("Calculating total number of %s files ..." % slabel,
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
                """Signal handler"""
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
