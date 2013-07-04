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

"""This module hosts OS-specific code common for the various Microsoft
Windows OSs."""

from image_creator.os_type import OSBase, sysprep
from image_creator.util import FatalError, check_guestfs_version, get_command

import hivex
import tempfile
import os
import time
import random
import subprocess

kvm = get_command('kvm')


class Windows(OSBase):
    """OS class for Windows"""

    def needed_sysprep_params(self):
        """Returns a list of needed sysprep parameters. Each element in the
        list is a SysprepParam object.
        """

        password = self.SysprepParam(
            'password', 'Image Administrator Password', 20, lambda x: True)

        return [password]

    @sysprep(enabled=True)
    def disable_ipv6_privacy_extensions(self, print_header=True):
        """Disable IPv6 privacy extensions"""

        if print_header:
            self.out.output("Disabling IPv6 privacy extensions")

        out, err, rc = self._guest_exec(
            'netsh interface ipv6 set global randomizeidentifiers=disabled '
            'store=persistent')

        if rc != 0:
            raise FatalError("Unable to disable IPv6 privacy extensions: %s" %
                             err)

    @sysprep(enabled=True)
    def microsoft_sysprep(self, print_header=True):
        """Run the Micorsoft System Preparation Tool on the Image. After this
        runs, no other task may run.
        """

        if print_header:
            self.out.output("Executing sysprep on the image (may take more "
                            "than 10 minutes)")

        out, err, rc = self._guest_exec(r'C:\windows\system32\sysprep\sysprep '
                                        r'/quiet /generalize /oobe /shutdown')
        self.syspreped = True
        if rc != 0:
            raise FatalError("Unable to perform sysprep: %s" % err)

    def do_sysprep(self):
        """Prepare system for image creation."""

        if getattr(self, 'syspreped', False):
            raise FatalError("Image is already syspreped!")

        txt = "System preparation parameter: `%s' is needed but missing!"
        for param in self.needed_sysprep_params():
            if param[0] not in self.sysprep_params:
                raise FatalError(txt % param[0])

        self.mount(readonly=False)
        try:
            disabled_uac = self._update_uac_remote_setting(1)
        finally:
            self.umount()

        self.out.output("Shutting down helper VM ...", False)
        self.g.sync()
        # guestfs_shutdown which is the prefered way to shutdown the backend
        # process was introduced in version 1.19.16
        if check_guestfs_version(self.g, 1, 19, 16) >= 0:
            ret = self.g.shutdown()
        else:
            ret = self.g.kill_subprocess()

        self.out.success('done')
        try:
            self.out.output("Starting windows VM ...", False)

            def random_mac():
                mac = [0x00, 0x16, 0x3e,
                       random.randint(0x00, 0x7f),
                       random.randint(0x00, 0xff),
                       random.randint(0x00, 0xff)]
                return ':'.join(map(lambda x: "%02x" % x, mac))

            vm = kvm('-smp', '1', '-m', '1024', '-drive',
                     'file=%s,format=raw,cache=none,if=virtio' %
                     self.image.device,
                     '-netdev', 'type=user,hostfwd=tcp::445-:445,id=netdev0',
                     '-device', 'virtio-net-pci,mac=%s,netdev=netdev0' %
                     random_mac(), '-vnc', ':0', _bg=True)
            time.sleep(60)
            self.out.success('done')

            tasks = self.list_syspreps()
            enabled = filter(lambda x: x.enabled, tasks)

            size = len(enabled)

            # Make sure the ms sysprep is the last task to run if it is enabled
            enabled = filter(
                lambda x: x.im_func.func_name != 'microsoft_sysprep', enabled)

            ms_sysprep_enabled = False
            if len(enabled) != size:
                enabled.append(self.ms_sysprep)
                ms_sysprep_enabled = True

            cnt = 0
            for task in enabled:
                cnt += 1
                self.out.output(('(%d/%d)' % (cnt, size)).ljust(7), False)
                task()
                setattr(task.im_func, 'executed', True)

            if not ms_sysprep_enabled:
                self._shutdown()

            vm.wait()
        finally:
            if vm.process.alive:
                vm.terminate()

            self.out.output("Relaunching helper VM (may take a while) ...",
                            False)
            self.g.launch()
            self.out.success('done')

        if disabled_uac:
            self._update_uac_remote_setting(0)

    def _shutdown(self):
        """Shuts down the windows VM"""

        self.out.output("Shutting down windows VM ...", False)
        out, err, rc = self._guest_exec(r'shutdown /s /t 5')

        if rc != 0:
            raise FatalError("Unable to perform shutdown: %s" % err)

        self.out.success('done')

    def _registry_file_path(self, regfile):
        """Retrieves the case sensitive path to a registry file"""

        systemroot = self.g.inspect_get_windows_systemroot(self.root)
        path = "%s/system32/config/%s" % (systemroot, regfile)
        try:
            path = self.g.case_sensitive_path(path)
        except RuntimeError as e:
            raise FatalError("Unable to retrieve registry file: %s. Reason: %s"
                             % (regfile, str(e)))
        return path

    def _update_uac_remote_setting(self, value):
        """Updates the registry key value:
        [HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies
        \System]"LocalAccountTokenFilterPolicy"

        value = 1 will disable the UAC remote restrictions
        value = 0 will enable the UAC remote restrictions

        For more info see here: http://support.microsoft.com/kb/951016

        Returns:
            True if the key is changed
            False if the key is unchanged
        """

        if value not in (0, 1):
            raise ValueError("Valid values for value parameter are 0 and 1")

        path = self._registry_file_path('SOFTWARE')
        softwarefd, software = tempfile.mkstemp()
        try:
            os.close(softwarefd)
            self.g.download(path, software)

            h = hivex.Hivex(software, write=True)

            key = h.root()
            for child in ('Microsoft', 'Windows', 'CurrentVersion', 'Policies',
                          'System'):
                key = h.node_get_child(key, child)

            policy = None
            for val in h.node_values(key):
                if h.value_key(val) == "LocalAccountTokenFilterPolicy":
                    policy = val

            if policy is not None:
                dword = h.value_dword(policy)
                if dword == value:
                    return False
            elif value == 0:
                return False

            new_value = {
                'key': "LocalAccountTokenFilterPolicy", 't': 4L,
                'value': '%s\x00\x00\x00' % '\x00' if value == 0 else '\x01'}

            h.node_set_value(key, new_value)
            h.commit(None)

            self.g.upload(software, path)

        finally:
            os.unlink(software)

        return True

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Windows, self)._do_collect_metadata()
        self.meta["USERS"] = " ".join(self._get_users())

    def _get_users(self):
        """Returns a list of users found in the images"""
        path = self._registry_file_path('SAM')
        samfd, sam = tempfile.mkstemp()
        try:
            os.close(samfd)
            self.g.download(path, sam)

            h = hivex.Hivex(sam)

            key = h.root()
            # Navigate to /SAM/Domains/Account/Users/Names
            for child in ('SAM', 'Domains', 'Account', 'Users', 'Names'):
                key = h.node_get_child(key, child)

            users = [h.node_name(x) for x in h.node_children(key)]

        finally:
            os.unlink(sam)

        # Filter out the guest account
        return filter(lambda x: x != "Guest", users)

    def _guest_exec(self, command):
        user = "Administrator%" + self.sysprep_params['password']
        addr = 'localhost'
        runas = '--runas=%s' % user
        winexe = subprocess.Popen(
            ['winexe', '-U', user, "//%s" % addr, runas, command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        result = winexe.communicate()
        rc = winexe.poll()

        return (result[0], result[1], rc)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
