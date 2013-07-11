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
import string
import subprocess
import struct

kvm = get_command('kvm')

BOOT_TIMEOUT = 300


class Windows(OSBase):
    """OS class for Windows"""

    def needed_sysprep_params(self):
        """Returns a list of needed sysprep parameters. Each element in the
        list is a SysprepParam object.
        """
        password = self.SysprepParam(
            'password', 'Image Administrator Password', 20, lambda x: True)

        return [password]

    @sysprep('Disabling IPv6 privacy extensions')
    def disable_ipv6_privacy_extensions(self):
        """Disable IPv6 privacy extensions"""

        self._guest_exec('netsh interface ipv6 set global '
                         'randomizeidentifiers=disabled store=persistent')

    @sysprep('Disabling Teredo interface')
    def disable_teredo(self):
        """Disable Teredo interface"""

        self._guest_exec('netsh interface teredo set state disabled')

    @sysprep('Disabling ISATAP Adapters')
    def disable_isatap(self):
        """Disable ISATAP Adapters"""

        self._guest_exec('netsh interface isa set state disabled')

    @sysprep('Enabling ping responses')
    def enable_pings(self):
        """Enable ping responces"""

        self._guest_exec('netsh firewall set icmpsetting 8')

    @sysprep('Disabling hibernation support')
    def disable_hibernation(self):
        """Disable hibernation support and remove the hibernation file"""

        self._guest_exec(r'powercfg.exe /hibernate off')

    @sysprep('Setting the system clock to UTC')
    def utc(self):
        """Set the hardware clock to UTC"""

        path = r'HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation'
        self._guest_exec(
            r'REG ADD %s /v RealTimeIsUniversal /t REG_DWORD /d 1 /f' % path)

    @sysprep('Clearing the event logs')
    def clear_logs(self):
        """Clear all the event logs"""

        self._guest_exec(
            r"cmd /q /c for /f %l in ('wevtutil el') do wevtutil cl %l")

    @sysprep('Executing sysprep on the image (may take more that 10 minutes)')
    def microsoft_sysprep(self):
        """Run the Microsoft System Preparation Tool. This will remove
        system-specific data and will make the image ready to be deployed.
        After this no other task may run.
        """

        self._guest_exec(r'C:\Windows\system32\sysprep\sysprep '
                         r'/quiet /generalize /oobe /shutdown')
        self.syspreped = True

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
            token = self._enable_os_monitor()

            # disable the firewalls
            firewall_states = self._update_firewalls(0, 0, 0)

            # Delete the pagefile. It will be recreated when the system boots
            systemroot = self.g.inspect_get_windows_systemroot(self.root)
            pagefile = "%s/pagefile.sys" % systemroot
            self.g.rm_rf(self.g.case_sensitive_path(pagefile))

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

        vm = None
        monitor = None
        try:
            self.out.output("Starting windows VM ...", False)
            monitorfd, monitor = tempfile.mkstemp()
            os.close(monitorfd)
            vm, display = self._create_vm(monitor)
            self.out.success("started (console on vnc display: %d)." % display)

            self.out.output("Waiting for OS to boot ...", False)
            if not self._wait_on_file(monitor, token):
                raise FatalError("Windows booting timed out.")
            else:
                self.out.success('done')

            self.out.output("Disabling automatic logon ...", False)
            self._disable_autologon()
            self.out.success('done')

            self.out.output('Preparing system from image creation:')

            tasks = self.list_syspreps()
            enabled = filter(lambda x: x.enabled, tasks)
            size = len(enabled)

            # Make sure the ms sysprep is the last task to run if it is enabled
            enabled = filter(
                lambda x: x.im_func.func_name != 'microsoft_sysprep', enabled)

            ms_sysprep_enabled = False
            if len(enabled) != size:
                enabled.append(self.microsoft_sysprep)
                ms_sysprep_enabled = True

            cnt = 0
            for task in enabled:
                cnt += 1
                self.out.output(('(%d/%d)' % (cnt, size)).ljust(7), False)
                task()
                setattr(task.im_func, 'executed', True)

            self.out.output("Sending shut down command ...", False)
            if not ms_sysprep_enabled:
                self._shutdown()
            self.out.success("done")

            self.out.output("Waiting for windows to shut down ...", False)
            vm.wait()
            self.out.success("done")
        finally:
            if monitor is not None:
                os.unlink(monitor)

            if vm is not None:
                self._destroy_vm(vm)

            self.out.output("Relaunching helper VM (may take a while) ...",
                            False)
            self.g.launch()
            self.out.success('done')

            self.mount(readonly=False)
            try:
                if disabled_uac:
                    self._update_uac_remote_setting(0)

                self._update_firewalls(*firewall_states)
            finally:
                self.umount()

    def _create_vm(self, monitor):
        """Create a VM with the image attached as the disk

            monitor: a file to be used to monitor when the OS is up
        """

        def random_mac():
            mac = [0x00, 0x16, 0x3e,
                   random.randint(0x00, 0x7f),
                   random.randint(0x00, 0xff),
                   random.randint(0x00, 0xff)]

            return ':'.join(map(lambda x: "%02x" % x, mac))

        # Use ganeti's VNC port range for a random vnc port
        vnc_port = random.randint(11000, 14999)
        display = vnc_port - 5900

        vm = kvm('-smp', '1', '-m', '1024', '-drive',
                 'file=%s,format=raw,cache=none,if=virtio' % self.image.device,
                 '-netdev', 'type=user,hostfwd=tcp::445-:445,id=netdev0',
                 '-device', 'virtio-net-pci,mac=%s,netdev=netdev0' %
                 random_mac(), '-vnc', ':%d' % display, '-serial',
                 'file:%s' % monitor, _bg=True)

        return vm, display

    def _destroy_vm(self, vm):
        """Destroy a VM previously created by _create_vm"""
        if vm.process.alive:
            vm.terminate()

    def _shutdown(self):
        """Shuts down the windows VM"""
        self._guest_exec(r'shutdown /s /t 5')

    def _wait_on_file(self, fname, msg):
        """Wait until a message appears on a file"""

        for i in range(BOOT_TIMEOUT):
            time.sleep(1)
            with open(fname) as f:
                for line in f:
                    if line.startswith(msg):
                        return True
        return False

    def _disable_autologon(self):
        """Disable automatic logon on the windows image"""

        winlogon = \
            r'"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"'

        self._guest_exec('REG DELETE %s /v DefaultUserName /f' % winlogon)
        self._guest_exec('REG DELETE %s /v DefaultPassword /f' % winlogon)
        self._guest_exec('REG DELETE %s /v AutoAdminLogon /f' % winlogon)

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

    def _enable_os_monitor(self):
        """Add a script in the registry that will send a random string to the
        first serial port when the windows image finishes booting.
        """

        token = "".join(random.choice(string.ascii_letters) for x in range(16))

        path = self._registry_file_path('SOFTWARE')
        softwarefd, software = tempfile.mkstemp()
        try:
            os.close(softwarefd)
            self.g.download(path, software)

            h = hivex.Hivex(software, write=True)

            # Enable automatic logon.
            # This is needed because we need to execute a script that we add in
            # the RunOnce registry entry and those programs only get executed
            # when a user logs on. There is a RunServicesOnce registry entry
            # whose keys get executed in the background when the logon dialog
            # box first appears, but they seem to only work with services and
            # not arbitrary command line expressions :-(
            #
            # Instructions on how to turn on automatic logon in Windows can be
            # found here: http://support.microsoft.com/kb/324737
            #
            # Warning: Registry change will not work if the “Logon Banner” is
            # defined on the server either by a Group Policy object (GPO) or by
            # a local policy.

            winlogon = h.root()
            for child in ('Microsoft', 'Windows NT', 'CurrentVersion',
                          'Winlogon'):
                winlogon = h.node_get_child(winlogon, child)

            h.node_set_value(
                winlogon,
                {'key': 'DefaultUserName', 't': 1,
                 'value': "Administrator".encode('utf-16le')})
            h.node_set_value(
                winlogon,
                {'key': 'DefaultPassword', 't': 1,
                 'value':  self.sysprep_params['password'].encode('utf-16le')})
            h.node_set_value(
                winlogon,
                {'key': 'AutoAdminLogon', 't': 1,
                 'value': "1".encode('utf-16le')})

            key = h.root()
            for child in ('Microsoft', 'Windows', 'CurrentVersion'):
                key = h.node_get_child(key, child)

            runonce = h.node_get_child(key, "RunOnce")
            if runonce is None:
                runonce = h.node_add_child(key, "RunOnce")

            value = (
                r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe '
                r'-ExecutionPolicy RemoteSigned '
                r'"&{$port=new-Object System.IO.Ports.SerialPort COM1,9600,'
                r'None,8,one;$port.open();$port.WriteLine(\"' + token + r'\");'
                r'$port.Close()}"').encode('utf-16le')

            h.node_set_value(runonce,
                             {'key': "BootMonitor", 't': 1, 'value': value})

            value = (
                r'REG ADD HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion'
                r'\policies\system /v LocalAccountTokenFilterPolicy'
                r' /t REG_DWORD /d 1 /f').encode('utf-16le')

            h.node_set_value(runonce,
                             {'key': "UpdateRegistry", 't': 1, 'value': value})

            h.commit(None)

            self.g.upload(software, path)
        finally:
            os.unlink(software)

        return token

    def _update_firewalls(self, domain, public, standard):
        """Enables or disables the firewall for the Domain, the Public and the
        Standard profile. Returns a triplete with the old values.

        1 will enable a firewall and 0 will disable it
        """

        if domain not in (0, 1):
            raise ValueError("Valid values for domain parameter are 0 and 1")

        if public not in (0, 1):
            raise ValueError("Valid values for public parameter are 0 and 1")

        if standard not in (0, 1):
            raise ValueError("Valid values for standard parameter are 0 and 1")

        path = self._registry_file_path("SYSTEM")
        systemfd, system = tempfile.mkstemp()
        try:
            os.close(systemfd)
            self.g.download(path, system)

            h = hivex.Hivex(system, write=True)

            select = h.node_get_child(h.root(), 'Select')
            current_value = h.node_get_value(select, 'Current')

            # expecting a little endian dword
            assert h.value_type(current_value)[1] == 4
            current = "%03d" % h.value_dword(current_value)

            firewall_policy = h.root()
            for child in ('ControlSet%s' % current, 'services', 'SharedAccess',
                          'Parameters', 'FirewallPolicy'):
                firewall_policy = h.node_get_child(firewall_policy, child)

            old_values = []
            new_values = [domain, public, standard]
            for profile in ('Domain', 'Public', 'Standard'):
                node = h.node_get_child(firewall_policy, '%sProfile' % profile)

                old_value = h.node_get_value(node, 'EnableFirewall')

                # expecting a little endian dword
                assert h.value_type(old_value)[1] == 4
                old_values.append(h.value_dword(old_value))

                h.node_set_value(
                    node, {'key': 'EnableFirewall', 't': 4L,
                           'value': struct.pack("<I", new_values.pop(0))})

            h.commit(None)
            self.g.upload(system, path)

        finally:
            os.unlink(system)

        return old_values

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

            new_value = {'key': "LocalAccountTokenFilterPolicy", 't': 4L,
                         'value': struct.pack("<I", value)}

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

    def _guest_exec(self, command, fatal=True):
        """Execute a command on a windows VM"""

        user = "Administrator%" + self.sysprep_params['password']
        addr = 'localhost'
        runas = '--runas=%s' % user
        winexe = subprocess.Popen(
            ['winexe', '-U', user, "//%s" % addr, runas, command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout, stderr = winexe.communicate()
        rc = winexe.poll()

        if rc != 0 and fatal:
            reason = stderr if len(stderr) else stdout
            raise FatalError("Command: `%s' failed. Reason: %s" %
                             (command, reason))

        return (stdout, stderr, rc)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
