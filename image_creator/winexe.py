# -*- coding: utf-8 -*-
#
# Copyright 2013 GRNET S.A. All rights reserved.
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

"""This module provides an interface for the WinEXE utility"""

import subprocess
import time
import signal

from image_creator.util import FatalError


class WinexeTimeout(FatalError):
    """Raised when a WinExE command times-out"""
    pass


class WinEXE:
    """Wrapper class for the winexe command"""

    def __init__(self, username, password, hostname, program='winexe'):
        self._host = hostname
        self._user = username
        self._pass = password
        self._prog = program

        # -U USERNAME[%PASSWORD]
        user = '%s%s' % (self._user, '%%%s' % self._pass if self._pass else "")
        self._opts = ['-U', user]

    def reset(self):
        """Reset all winexe options"""

        # -U USERNAME[%PASSWORD]
        user = '%s%s' % (self._user, '%%%s' % self._pass if self._pass else "")
        self._opts = ['-U', user]

    def runas(self, username, password):
        """Run command as this user"""
        self._opts.append('--runas=%s%%%s' % (username, password))
        return self

    def system(self):
        """Use SYSTEM account"""
        self._opts.append('--system')
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

    def run(self, command, timeout=0):
        """Run a command on a remote windows system"""

        args = [self._prog] + self._opts + ["//%s" % self._host] + [command]
        run = subprocess.Popen(args, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

        def handler(signum, frame):
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
