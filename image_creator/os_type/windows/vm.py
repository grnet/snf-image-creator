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

"""This module provides an interface for launching windows VMs"""

import random
import subprocess
import signal
import tempfile
import os
import time
import errno
from string import lowercase, uppercase, digits

from image_creator.util import FatalError, get_kvm_binary
from image_creator.os_type.windows.winexe import WinEXE, WinexeTimeout

# Just a random 16 character long token
RANDOM_TOKEN = "".join(random.choice(lowercase + uppercase) for _ in range(16))


class VM(object):
    """Windows Virtual Machine"""
    def __init__(self, disk, params, admin):
        """Create VM instance"""

        self.disk = disk
        self.params = params
        self.admin = admin
        self.interface = 'virtio'

        # expected number of token occurrences in serial port
        self._ntokens = 0

        kvm, needed_args = get_kvm_binary()
        if kvm is None:
            raise FatalError("Can't find the kvm binary")

        self.kvm = [kvm] + list(needed_args)

        def random_mac():
            """creates a random mac address"""
            mac = [0x00, 0x16, 0x3e,
                   random.randint(0x00, 0x7f),
                   random.randint(0x00, 0xff),
                   random.randint(0x00, 0xff)]

            return ':'.join(['%02x' % x for x in mac])

        self.mac = random_mac()

        def random_password():
            """Creates a random password"""

            # I borrowed this from Synnefo
            pool = lowercase + uppercase + digits
            lowerset = set(lowercase)
            upperset = set(uppercase)
            digitset = set(digits)
            length = 10

            password = ''.join(random.choice(pool) for i in range(length - 2))

            # Make sure the password is compliant
            chars = set(password)
            if not chars & lowerset:
                password += random.choice(lowercase)
            if not chars & upperset:
                password += random.choice(uppercase)
            if not chars & digitset:
                password += random.choice(digits)

            # Pad if necessary to reach required length
            password += ''.join(random.choice(pool) for i in
                                range(length - len(password)))

            return password

        self.password = random_password()

        # Use Ganeti's VNC port range for a random vnc port
        self.display = random.randint(11000, 14999) - 5900

        self.serial = None
        self.process = None

    def isalive(self):
        """Check if the VM is alive"""
        return self.process is not None and self.process.poll() is None

    def start(self, **kwargs):
        """Start the windows VM"""

        self._ntokens = 0

        args = []
        args.extend(self.kvm)

        if 'smp' in self.params:
            args.extend(['-smp', str(self.params['smp'].value)])

        if 'mem' in self.params:
            args.extend(['-m', str(self.params['mem'].value)])

        args.extend(['-drive', 'file=%s,cache=unsafe,if=%s' %
                     (self.disk, self.interface)])

        args.extend(
            ['-netdev', 'type=user,hostfwd=tcp::445-:445,id=netdev0',
             '-device', 'rtl8139,mac=%s,netdev=netdev0' % self.mac])

        if 'extra_disk' in kwargs:
            fname, iftype = kwargs['extra_disk']
            args.extend(['-drive',
                         'file=%s,format=raw,cache=unsafe,if=%s' %
                         (fname, iftype)])

        args.extend(['-vnc', ":%d" % self.display])

        # The serial port
        serialfd, self.serial = tempfile.mkstemp()
        os.close(serialfd)
        args.extend(['-serial', 'file:%s' % self.serial])

        args.extend(['-monitor', 'stdio'])

        self.process = subprocess.Popen(args, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

    def stop(self, timeout=0, fatal=True):
        """Stop the VM"""

        try:
            if not self.isalive():
                return

            def handler(signum, frame):
                self.process.terminate()
                time.sleep(1)
                if self.isalive():
                    self.process.kill()
                self.process.wait()
                if fatal:
                    raise FatalError("Stopping the VM timed-out")

            signal.signal(signal.SIGALRM, handler)

            signal.alarm(timeout)
            self.process.communicate(input="system_powerdown\n")
            signal.alarm(0)

        finally:
            if self.serial is not None:
                try:
                    os.unlink(self.serial)
                except OSError as e:
                    if errno.errorcode[e.errno] != 'ENOENT':  # File not found
                        raise

    def wait_on_serial(self, timeout):
        """Wait until the random token appears on the VM's serial port"""

        self._ntokens += 1

        for _ in xrange(timeout):
            time.sleep(1)
            with open(self.serial) as f:
                current = 0
                for line in f:
                    if line.startswith(RANDOM_TOKEN):
                        current += 1
                        if current == self._ntokens:
                            return True
            if not self.isalive():
                (stdout, stderr, rc) = self.wait()
                raise FatalError("Windows VM died unexpectedly!\n\n"
                                 "(rc=%d)\n%s" % (rc, stderr))

        return False

    def wait(self, timeout=0):
        """Wait for the VM to shutdown by itself"""

        def handler(signum, frame):
            raise FatalError("VM wait timed-out.")

        signal.signal(signal.SIGALRM, handler)

        signal.alarm(timeout)
        stdout, stderr = self.process.communicate()
        signal.alarm(0)

        return (stdout, stderr, self.process.poll())

    def rexec(self, command, **kwargs):
        """Remote execute a command on the windows VM

        The following optional flags are allowed:

        * fatal: If True, a FatalError is thrown if the command fails

        * debug: If True, WinEXE is executed in the highest debug level

        * uninstall: If True, the winexesvc.exe service will be uninstalled
          after the execution of the command.
        """

        fatal = kwargs['fatal'] if 'fatal' in kwargs else True
        debug = kwargs['debug'] if 'debug' in kwargs else False
        uninstall = kwargs['uninstall'] if 'uninstall' in kwargs else False

        winexe = WinEXE(self.admin.name, 'localhost', password=self.password)
        winexe.no_pass()

        if debug:
            winexe.debug(9)

        if uninstall:
            winexe.uninstall()

        try:
            (stdout, stderr, rc) = winexe.run(command)
        except WinexeTimeout:
            raise FatalError("Command: `%s' timeout out." % command)

        if rc != 0 and fatal:
            log = tempfile.NamedTemporaryFile(delete=False)
            try:
                log.file.write("STDOUT:\n%s\n" % stdout)
                log.file.write("STDERR:\n%s\n" % stderr)
            finally:
                fname = log.name
                log.close()

            # self.out.output("Command: `%s' failed (rc=%d). Reason: %s" %
            #                 (command, rc, reason))
            raise FatalError("Command: `%s' failed (rc=%d). See: %s" %
                             (command, rc, fname))

        return (stdout, stderr, rc)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
