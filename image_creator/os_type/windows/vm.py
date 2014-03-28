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

from image_creator.util import FatalError, get_kvm_binary


class VM(object):
    """Windows Virtual Machine"""
    def __init__(self, disk, serial, params):
        """Create _VM instance

            disk: VM's hard disk
            serial: File to save the output of the serial port
        """

        self.disk = disk
        self.serial = serial
        self.params = params

        def random_mac():
            """creates a random mac address"""
            mac = [0x00, 0x16, 0x3e,
                   random.randint(0x00, 0x7f),
                   random.randint(0x00, 0xff),
                   random.randint(0x00, 0xff)]

            return ':'.join(['%02x' % x for x in mac])

        # Use Ganeti's VNC port range for a random vnc port
        self.display = random.randint(11000, 14999) - 5900

        kvm, needed_args = get_kvm_binary()

        if kvm is None:
            FatalError("Can't find the kvm binary")

        args = [kvm]
        args.extend(needed_args)

        args.extend([
            '-smp', str(self.params['smp']), '-m', str(self.params['mem']),
            '-drive', 'file=%s,format=raw,cache=unsafe,if=virtio' % self.disk,
            '-netdev', 'type=user,hostfwd=tcp::445-:445,id=netdev0',
            '-device', 'virtio-net-pci,mac=%s,netdev=netdev0' % random_mac(),
            '-vnc', ':%d' % self.display, '-serial', 'file:%s' % self.serial,
            '-monitor', 'stdio'])

        self.process = subprocess.Popen(args, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE)

    def isalive(self):
        """Check if the VM is still alive"""
        return self.process.poll() is None

    def destroy(self):
        """Destroy the VM"""

        if not self.isalive():
            return

        def handler(signum, frame):
            self.process.terminate()
            time.sleep(1)
            if self.isalive():
                self.process.kill()
            self.process.wait()
            raise FatalError("VM destroy timed-out")

        signal.signal(signal.SIGALRM, handler)

        signal.alarm(self.params['shutdown_timeout'])
        self.process.communicate(input="system_powerdown\n")
        signal.alarm(0)

    def wait(self, timeout=0):
        """Wait for the VM to terminate"""

        def handler(signum, frame):
            self.destroy()
            raise FatalError("VM wait timed-out.")

        signal.signal(signal.SIGALRM, handler)

        signal.alarm(timeout)
        stdout, stderr = self.process.communicate()
        signal.alarm(0)

        return (stdout, stderr, self.process.poll())

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
