# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2017 GRNET S.A.
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

"""This module provides an interface for the WinEXE utility."""

import subprocess
import time
import signal
from sh import which

from image_creator.util import FatalError


class WinexeTimeout(FatalError):
    """Raised when a WinExE command times-out"""
    pass


class WinEXE(object):
    """Wrapper class for the winexe command"""

    @staticmethod
    def is_installed(program='winexe'):
        """Check if WinEXE is installed on the system"""
        return which(program) is not None

    def __init__(self, username, hostname, **kwargs):
        """Initialize a WinEXE instance"""
        self._user = username
        self._host = hostname

        self._pass = kwargs['password'] if 'password' in kwargs else None
        self._prog = kwargs['progname'] if 'progname' in kwargs else 'winexe'

        # -U USERNAME[%PASSWORD]
        user = '%s%s' % (self._user, '%%%s' % self._pass if self._pass else "")
        self._opts = ['-U', user]

    def reset(self):
        """Reset all winexe options"""

        # -U USERNAME[%PASSWORD]
        user = '%s%s' % (self._user, '%%%s' % self._pass if self._pass else "")
        self._opts = ['-U', user]

    def runas(self, username, passwd=None):
        """Run command as this user"""

        opt = '--runas=%s%s' % (username,
                                '%%%s' % passwd if passwd is not None else "")
        self._opts.append(opt)
        return self

    def system(self):
        """Use SYSTEM account"""
        self._opts.append('--system')
        return self

    def no_pass(self):
        """Do not ask for password"""
        self._opts.append('--no-pass')
        return self

    def uninstall(self):
        """Uninstall winexe service after remote execution"""
        self._opts.append('--uninstall')
        return self

    def reinstall(self):
        """Reinstall winexe service before remote execution"""
        self._opts.append('--reinstall')
        return self

    def debug(self, level):
        """Set debug level"""
        self._opts.append('--debuglevel=%d' % level)
        return self

    def debug_stderr(self):
        """Send debug output to STDERR"""
        self._opts.append('--debug-stderr')
        return self

    def run(self, command, timeout=0):
        """Run a command on a remote windows system"""

        args = [self._prog] + self._opts + ["//%s" % self._host] + [command]
        run = subprocess.Popen(args, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

        def handler(signum, frame):
            """Signal handler"""
            run.terminate()
            time.sleep(1)
            run.poll()
            if run.returncode is None:
                run.kill()
            run.wait()
            raise WinexeTimeout("Command: `%s' timed-out" % " ".join(args))

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)
        stdout, stderr = run.communicate()
        rc = run.poll()
        signal.alarm(0)

        return (stdout, stderr, rc)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
