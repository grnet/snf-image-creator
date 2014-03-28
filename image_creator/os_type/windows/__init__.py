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

"""This package hosts OS-specific code common for the various Microsoft
Windows OSs."""

from image_creator.os_type import OSBase, sysprep, add_sysprep_param
from image_creator.util import FatalError
from image_creator.os_type.windows.vm import VM
from image_creator.os_type.windows.winexe import WinEXE, WinexeTimeout

import hivex
import tempfile
import os
import time
import random
import string
import struct
import re

# For more info see: http://technet.microsoft.com/en-us/library/jj612867.aspx
KMS_CLIENT_SETUP_KEYS = {
    "Windows 8.1 Professional": "GCRJD-8NW9H-F2CDX-CCM8D-9D6T9",
    "Windows 8.1 Professional N": "HMCNV-VVBFX-7HMBH-CTY9B-B4FXY",
    "Windows 8.1 Enterprise": "MHF9N-XY6XB-WVXMC-BTDCT-MKKG7",
    "Windows 8.1 Enterprise N": "TT4HM-HN7YT-62K67-RGRQJ-JFFXW",
    "Windows Server 2012 R2 Server Standard": "D2N9P-3P6X9-2R39C-7RTCD-MDVJX",
    "Windows Server 2012 R2 Datacenter": "W3GGN-FT8W3-Y4M27-J84CP-Q3VJ9",
    "Windows Server 2012 R2 Essentials": "KNC87-3J2TX-XB4WP-VCPJV-M4FWM",
    "Windows 8 Professional": "NG4HW-VH26C-733KW-K6F98-J8CK4",
    "Windows 8 Professional N": "XCVCF-2NXM9-723PB-MHCB7-2RYQQ",
    "Windows 8 Enterprise": "32JNW-9KQ84-P47T8-D8GGY-CWCK7",
    "Windows 8 Enterprise N": "JMNMF-RHW7P-DMY6X-RF3DR-X2BQT",
    "Windows Server 2012 Core": "BN3D2-R7TKB-3YPBD-8DRP2-27GG4",
    "Windows Server 2012 Core N": "8N2M2-HWPGY-7PGT9-HGDD8-GVGGY",
    "Windows Server 2012 Core Single Language":
    "2WN2H-YGCQR-KFX6K-CD6TF-84YXQ",
    "Windows Server 2012 Core Country Specific":
    "4K36P-JN4VD-GDC6V-KDT89-DYFKP",
    "Windows Server 2012 Server Standard": "XC9B7-NBPP2-83J2H-RHMBY-92BT4",
    "Windows Server 2012 Standard Core": "XC9B7-NBPP2-83J2H-RHMBY-92BT4",
    "Windows Server 2012 MultiPoint Standard": "HM7DN-YVMH3-46JC3-XYTG7-CYQJJ",
    "Windows Server 2012 MultiPoint Premium": "XNH6W-2V9GX-RGJ4K-Y8X6F-QGJ2G",
    "Windows Server 2012 Datacenter": "48HP8-DN98B-MYWDG-T2DCC-8W83P",
    "Windows Server 2012 Datacenter Core": "48HP8-DN98B-MYWDG-T2DCC-8W83P",
    "Windows 7 Professional": "FJ82H-XT6CR-J8D7P-XQJJ2-GPDD4",
    "Windows 7 Professional N": "MRPKT-YTG23-K7D7T-X2JMM-QY7MG",
    "Windows 7 Professional E": "W82YF-2Q76Y-63HXB-FGJG9-GF7QX",
    "Windows 7 Enterprise": "33PXH-7Y6KF-2VJC9-XBBR8-HVTHH",
    "Windows 7 Enterprise N": "YDRBP-3D83W-TY26F-D46B2-XCKRJ",
    "Windows 7 Enterprise E": "C29WB-22CC8-VJ326-GHFJW-H9DH4",
    "Windows Server 2008 R2 Web": "6TPJF-RBVHG-WBW2R-86QPH-6RTM4",
    "Windows Server 2008 R2 HPC edition": "TT8MH-CG224-D3D7Q-498W2-9QCTX",
    "Windows Server 2008 R2 Standard": "YC6KT-GKW9T-YTKYR-T4X34-R7VHC",
    "Windows Server 2008 R2 Enterprise": "489J6-VHDMP-X63PK-3K798-CPX3Y",
    "Windows Server 2008 R2 Datacenter": "74YFP-3QFB3-KQT8W-PMXWJ-7M648",
    "Windows Server 2008 R2 for Itanium-based Systems":
    "GT63C-RJFQ3-4GMB6-BRFB9-CB83V",
    "Windows Vista Business": "YFKBB-PQJJV-G996G-VWGXY-2V3X8",
    "Windows Vista Business N": "HMBQG-8H2RH-C77VX-27R82-VMQBT",
    "Windows Vista Enterprise": "VKK3X-68KWM-X2YGT-QR4M6-4BWMV",
    "Windows Vista Enterprise N": "VTC42-BM838-43QHV-84HX6-XJXKV",
    "Windows Web Server 2008": "WYR28-R7TFJ-3X2YQ-YCY4H-M249D",
    "Windows Server 2008 Standard": "TM24T-X9RMF-VWXK6-X8JC9-BFGM2",
    "Windows Server 2008 Standard without Hyper-V":
    "W7VD6-7JFBR-RX26B-YKQ3Y-6FFFJ",
    "Windows Server 2008 Enterprise":
    "YQGMW-MPWTJ-34KDK-48M3W-X4Q6V",
    "Windows Server 2008 Enterprise without Hyper-V":
    "39BXF-X8Q23-P2WWT-38T2F-G3FPG",
    "Windows Server 2008 HPC": "RCTX3-KWVHP-BR6TB-RB6DM-6X7HP",
    "Windows Server 2008 Datacenter": "7M67G-PC374-GR742-YH8V4-TCBY3",
    "Windows Server 2008 Datacenter without Hyper-V":
    "22XQ2-VRXRG-P8D42-K34TD-G3QQC",
    "Windows Server 2008 for Itanium-Based Systems":
    "4DWFP-JF3DJ-B7DTH-78FJB-PDRHK"}

_POSINT = lambda x: type(x) == int and x >= 0


class Windows(OSBase):
    """OS class for Windows"""
    @add_sysprep_param(
        'shutdown_timeout', int, 120, "Shutdown Timeout (seconds)", _POSINT)
    @add_sysprep_param(
        'boot_timeout', int, 300, "Boot Timeout (seconds)", _POSINT)
    @add_sysprep_param(
        'connection_retries', int, 5, "Connection Retries", _POSINT)
    @add_sysprep_param(
        'smp', int, 1, "Number of CPUs for the helper VM", _POSINT)
    @add_sysprep_param(
        'mem', int, 1024, "Virtual RAM size for the helper VM (MiB)", _POSINT)
    @add_sysprep_param('password', str, None, 'Image Administrator Password')
    def __init__(self, image, **kargs):
        super(Windows, self).__init__(image, **kargs)

        # The commit with the following message was added in
        # libguestfs 1.17.18 and was backported in version 1.16.11:
        #
        # When a Windows guest doesn't have a HKLM\SYSTEM\MountedDevices node,
        # inspection fails.  However inspection should not completely fail just
        # because we cannot get the drive letter mapping from a guest.
        #
        # Since Microsoft Sysprep removes the aforementioned key, image
        # creation for windows can only be supported if the installed guestfs
        # version is 1.17.18 or higher
        if self.image.check_guestfs_version(1, 17, 18) < 0 and \
                (self.image.check_guestfs_version(1, 17, 0) >= 0 or
                 self.image.check_guestfs_version(1, 16, 11) < 0):
            raise FatalError(
                'For windows support libguestfs 1.16.11 or above is required')

        # Check if winexe is installed
        if not WinEXE.is_installed():
            raise FatalError(
                "For windows support `Winexe' needs to be installed")

        device = self.image.g.part_to_dev(self.root)

        self.last_part_num = self.image.g.part_list(device)[-1]['part_num']
        self.last_drive = None
        self.system_drive = None

        for drive, part in self.image.g.inspect_get_drive_mappings(self.root):
            if part == "%s%d" % (device, self.last_part_num):
                self.last_drive = drive
            if part == self.root:
                self.system_drive = drive

        assert self.system_drive

        self.product_name = self.image.g.inspect_get_product_name(self.root)
        self.syspreped = False

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
        """Enable ping responses"""

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
            "cmd /q /c for /f \"tokens=*\" %l in ('wevtutil el') do "
            "wevtutil cl \"%l\"")

    @sysprep('Executing Sysprep on the image (may take more that 10 min)')
    def microsoft_sysprep(self):
        """Run the Microsoft System Preparation Tool. This will remove
        system-specific data and will make the image ready to be deployed.
        After this no other task may run.
        """

        self._guest_exec(r'C:\Windows\system32\sysprep\sysprep '
                         r'/quiet /generalize /oobe /shutdown')
        self.syspreped = True

    @sysprep('Converting the image into a KMS client', enabled=False)
    def kms_client_setup(self):
        """Install the appropriate KMS client setup key to the image to convert
        it to a KMS client. Computers that are running volume licensing
        editions of Windows 8, Windows Server 2012, Windows 7, Windows Server
        2008 R2, Windows Vista, and Windows Server 2008 are by default KMS
        clients with no additional configuration needed.
        """
        try:
            setup_key = KMS_CLIENT_SETUP_KEYS[self.product_name]
        except KeyError:
            self.out.warn(
                "Don't know the KMS client setup key for product: `%s'" %
                self.product_name)
            return

        self._guest_exec(
            r"cscript \Windows\system32\slmgr.vbs /ipk %s" % setup_key)

    @sysprep('Shrinking the last filesystem')
    def shrink(self):
        """Shrink the last filesystem. Make sure the filesystem is defragged"""

        # Query for the maximum number of reclaimable bytes
        cmd = (
            r'cmd /Q /V:ON /C "SET SCRIPT=%TEMP%\QUERYMAX_%RANDOM%.TXT & ' +
            r'ECHO SELECT DISK 0 > %SCRIPT% & ' +
            'ECHO SELECT PARTITION %d >> %%SCRIPT%% & ' % self.last_part_num +
            r'ECHO SHRINK QUERYMAX >> %SCRIPT% & ' +
            r'ECHO EXIT >> %SCRIPT% & ' +
            r'DISKPART /S %SCRIPT% & ' +
            r'IF NOT !ERRORLEVEL! EQU 0 EXIT /B 1 & ' +
            r'DEL /Q %SCRIPT%"')

        stdout, stderr, rc = self._guest_exec(cmd)

        querymax = None
        for line in stdout.splitlines():
            # diskpart will return something like this:
            #
            #   The maximum number of reclaimable bytes is: xxxx MB
            #
            if line.find('reclaimable') >= 0:
                answer = line.split(':')[1].strip()
                m = re.search('(\d+) MB', answer)
                if m:
                    querymax = m.group(1)
                else:
                    FatalError(
                        "Unexpected output for `shrink querymax' command: %s" %
                        line)

        if querymax is None:
            FatalError("Error in shrinking! "
                       "Couldn't find the max number of reclaimable bytes!")

        querymax = int(querymax)
        # From ntfsresize:
        # Practically the smallest shrunken size generally is at around
        # "used space" + (20-200 MB). Please also take into account that
        # Windows might need about 50-100 MB free space left to boot safely.
        # I'll give 100MB extra space just to be sure
        querymax -= 100

        if querymax < 0:
            self.out.warn("Not enough available space to shrink the image!")
            return

        self.out.output("\tReclaiming %dMB ..." % querymax)

        cmd = (
            r'cmd /Q /V:ON /C "SET SCRIPT=%TEMP%\QUERYMAX_%RANDOM%.TXT & ' +
            r'ECHO SELECT DISK 0 > %SCRIPT% & ' +
            'ECHO SELECT PARTITION %d >> %%SCRIPT%% & ' % self.last_part_num +
            'ECHO SHRINK DESIRED=%d >> %%SCRIPT%% & ' % querymax +
            r'ECHO EXIT >> %SCRIPT% & ' +
            r'DISKPART /S %SCRIPT% & ' +
            r'IF NOT !ERRORLEVEL! EQU 0 EXIT /B 1 & ' +
            r'DEL /Q %SCRIPT%"')

        stdout, stderr, rc = self._guest_exec(cmd, False)

        if rc != 0:
            FatalError("Shrinking failed. Please make sure the media is "
                       "defraged with a command like this: "
                       "`Defrag.exe /U /X /W'")
        for line in stdout.splitlines():
            if line.find('shrunk') >= 0:
                self.out.output(line)

    def do_sysprep(self):
        """Prepare system for image creation."""

        if getattr(self, 'syspreped', False):
            raise FatalError("Image is already syspreped!")

        txt = "System preparation parameter: `%s' is needed but missing!"
        for name, param in self.needed_sysprep_params.items():
            if name not in self.sysprep_params:
                raise FatalError(txt % name)

        self.mount(readonly=False)
        try:
            disabled_uac = self._update_uac_remote_setting(1)
            token = self._enable_os_monitor()

            # disable the firewalls
            firewall_states = self._update_firewalls(0, 0, 0)

            # Delete the pagefile. It will be recreated when the system boots
            systemroot = self.image.g.inspect_get_windows_systemroot(self.root)
            try:
                pagefile = "%s/pagefile.sys" % systemroot
                self.image.g.rm_rf(self.image.g.case_sensitive_path(pagefile))
            except RuntimeError:
                pass

        finally:
            self.umount()

        self.image.disable_guestfs()

        vm = None
        monitor = None
        try:
            self.out.output("Starting windows VM ...", False)
            monitorfd, monitor = tempfile.mkstemp()
            os.close(monitorfd)
            vm = VM(self.image.device, monitor, self.sysprep_params)
            self.out.success("started (console on VNC display: %d)" %
                             vm.display)

            self.out.output("Waiting for OS to boot ...", False)
            self._wait_vm_boot(vm, monitor, token)
            self.out.success('done')

            self.out.output("Checking connectivity to the VM ...", False)
            self._check_connectivity()
            self.out.success('done')

            self.out.output("Disabling automatic logon ...", False)
            self._disable_autologon()
            self.out.success('done')

            self.out.output('Preparing system for image creation:')

            tasks = self.list_syspreps()
            enabled = [task for task in tasks if task.enabled]
            size = len(enabled)

            # Make sure shrink runs in the end, before ms sysprep
            enabled = [task for task in enabled if
                       self.sysprep_info(task).name != 'shrink']

            if len(enabled) != size:
                enabled.append(self.shrink)

            # Make sure the ms sysprep is the last task to run if it is enabled
            enabled = [task for task in enabled if
                       self.sysprep_info(task).name != 'microsoft-sysprep']

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
            vm.wait(self.sysprep_params['shutdown_timeout'])
            self.out.success("done")
        finally:
            if monitor is not None:
                os.unlink(monitor)

            try:
                if vm is not None:
                    self.out.output("Destroying windows VM ...", False)
                    vm.destroy()
                    self.out.success("done")
            finally:
                self.image.enable_guestfs()

                self.mount(readonly=False)
                try:
                    if disabled_uac:
                        self._update_uac_remote_setting(0)

                    self._update_firewalls(*firewall_states)
                finally:
                    self.umount()

    def _open_hive(self, hive, write=False):
        """Returns a context manager for opening a hive file of the image for
        reading or writing.
        """
        g = self.image.g
        systemroot = self.image.g.inspect_get_windows_systemroot(self.root)
        path = "%s/system32/config/%s" % (systemroot, hive)
        try:
            path = g.case_sensitive_path(path)
        except RuntimeError as err:
            raise FatalError("Unable to retrieve file: %s. Reason: %s" %
                             (hive, str(err)))

        class OpenHive:
            """The OpenHive context manager"""
            def __enter__(self):
                localfd, self.localpath = tempfile.mkstemp()
                try:
                    os.close(localfd)
                    g.download(path, self.localpath)

                    hive = hivex.Hivex(self.localpath, write=write)
                except:
                    os.unlink(self.localpath)
                    raise

                return hive

            def __exit__(self, exc_type, exc_value, traceback):
                try:
                    if write:
                        g.upload(self.localpath, path)
                finally:
                    os.unlink(self.localpath)

        return OpenHive()

    def _shutdown(self):
        """Shuts down the windows VM"""
        self._guest_exec(r'shutdown /s /t 5')

    def _wait_vm_boot(self, vm, fname, msg):
        """Wait until a message appears on a file or the vm process dies"""

        for _ in range(self.sysprep_params['boot_timeout']):
            time.sleep(1)
            with open(fname) as f:
                for line in f:
                    if line.startswith(msg):
                        return True
            if not vm.isalive():
                raise FatalError("Windows VM died unexpectedly!")

        raise FatalError("Windows VM booting timed out!")

    def _disable_autologon(self):
        """Disable automatic logon on the windows image"""

        winlogon = \
            r'"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"'

        self._guest_exec('REG DELETE %s /v DefaultUserName /f' % winlogon)
        self._guest_exec('REG DELETE %s /v DefaultPassword /f' % winlogon)
        self._guest_exec('REG DELETE %s /v AutoAdminLogon /f' % winlogon)

    def _enable_os_monitor(self):
        """Add a script in the registry that will send a random string to the
        first serial port when the windows image finishes booting.
        """

        token = "".join(random.choice(string.ascii_letters) for x in range(16))

        with self._open_hive('SOFTWARE', write=True) as hive:
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

            winlogon = hive.root()
            for child in ('Microsoft', 'Windows NT', 'CurrentVersion',
                          'Winlogon'):
                winlogon = hive.node_get_child(winlogon, child)

            hive.node_set_value(
                winlogon,
                {'key': 'DefaultUserName', 't': 1,
                 'value': "Administrator".encode('utf-16le')})
            hive.node_set_value(
                winlogon,
                {'key': 'DefaultPassword', 't': 1,
                 'value':  self.sysprep_params['password'].encode('utf-16le')})
            hive.node_set_value(
                winlogon,
                {'key': 'AutoAdminLogon', 't': 1,
                 'value': "1".encode('utf-16le')})

            key = hive.root()
            for child in ('Microsoft', 'Windows', 'CurrentVersion'):
                key = hive.node_get_child(key, child)

            runonce = hive.node_get_child(key, "RunOnce")
            if runonce is None:
                runonce = hive.node_add_child(key, "RunOnce")

            value = (
                r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe '
                r'-ExecutionPolicy RemoteSigned '
                r'"&{$port=new-Object System.IO.Ports.SerialPort COM1,9600,'
                r'None,8,one;$port.open();$port.WriteLine(\"' + token + r'\");'
                r'$port.Close()}"').encode('utf-16le')

            hive.node_set_value(
                runonce, {'key': "BootMonitor", 't': 1, 'value': value})

            value = (
                r'REG ADD HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion'
                r'\policies\system /v LocalAccountTokenFilterPolicy'
                r' /t REG_DWORD /d 1 /f').encode('utf-16le')

            hive.node_set_value(
                runonce, {'key': "UpdateRegistry", 't': 1, 'value': value})

            hive.commit(None)

        return token

    def _update_firewalls(self, domain, public, standard):
        """Enables or disables the firewall for the Domain, the Public and the
        Standard profile. Returns a triple with the old values.

        1 will enable a firewall and 0 will disable it
        """

        if domain not in (0, 1):
            raise ValueError("Valid values for domain parameter are 0 and 1")

        if public not in (0, 1):
            raise ValueError("Valid values for public parameter are 0 and 1")

        if standard not in (0, 1):
            raise ValueError("Valid values for standard parameter are 0 and 1")

        with self._open_hive('SYSTEM', write=True) as hive:
            select = hive.node_get_child(hive.root(), 'Select')
            current_value = hive.node_get_value(select, 'Current')

            # expecting a little endian dword
            assert hive.value_type(current_value)[1] == 4
            current = "%03d" % hive.value_dword(current_value)

            firewall_policy = hive.root()
            for child in ('ControlSet%s' % current, 'services', 'SharedAccess',
                          'Parameters', 'FirewallPolicy'):
                firewall_policy = hive.node_get_child(firewall_policy, child)

            old_values = []
            new_values = [domain, public, standard]
            for profile in ('Domain', 'Public', 'Standard'):
                node = hive.node_get_child(firewall_policy,
                                           '%sProfile' % profile)

                old_value = hive.node_get_value(node, 'EnableFirewall')

                # expecting a little endian dword
                assert hive.value_type(old_value)[1] == 4
                old_values.append(hive.value_dword(old_value))

                hive.node_set_value(
                    node, {'key': 'EnableFirewall', 't': 4L,
                           'value': struct.pack("<I", new_values.pop(0))})
            hive.commit(None)

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

        with self._open_hive('SOFTWARE', write=True) as hive:
            key = hive.root()
            for child in ('Microsoft', 'Windows', 'CurrentVersion', 'Policies',
                          'System'):
                key = hive.node_get_child(key, child)

            policy = None
            for val in hive.node_values(key):
                if hive.value_key(val) == "LocalAccountTokenFilterPolicy":
                    policy = val

            if policy is not None:
                dword = hive.value_dword(policy)
                if dword == value:
                    return False
            elif value == 0:
                return False

            new_value = {'key': "LocalAccountTokenFilterPolicy", 't': 4L,
                         'value': struct.pack("<I", value)}

            hive.node_set_value(key, new_value)
            hive.commit(None)

        return True

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Windows, self)._do_collect_metadata()
        self.meta["USERS"] = " ".join(self._get_users())

    def _get_users(self):
        """Returns a list of users found in the images"""

        with self._open_hive('SAM') as hive:
            # Navigate to /SAM/Domains/Account/Users
            users_node = hive.root()
            for child in ('SAM', 'Domains', 'Account', 'Users'):
                users_node = hive.node_get_child(users_node, child)

            # Navigate to /SAM/Domains/Account/Users/Names
            names_node = hive.node_get_child(users_node, 'Names')

            # HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\%RID%
            # HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\Names\%Username%
            #
            # The RID (relative identifier) of each user is stored as the type!
            # (not the value) of the default key of the node under Names whose
            # name is the user's username. Under the RID node, there in a F
            # value that contains information about this user account.
            #
            # See sam.h of the chntpw project on how to translate the F value
            # of an account in the registry. Bytes 56 & 57 are the account type
            # and status flags. The first bit is the 'account disabled' bit
            disabled = lambda f: int(f[56].encode('hex'), 16) & 0x01

            users = []
            for user_node in hive.node_children(names_node):
                username = hive.node_name(user_node)
                rid = hive.value_type(hive.node_get_value(user_node, ""))[0]
                # if RID is 500 (=0x1f4), the corresponding node name under
                # Users is '000001F4'
                key = ("%8.x" % rid).replace(' ', '0').upper()
                rid_node = hive.node_get_child(users_node, key)
                f_val = hive.value_value(hive.node_get_value(rid_node, 'F'))[1]

                if disabled(f_val):
                    self.out.warn("Found disabled `%s' account!" % username)
                    continue

                users.append(username)

        # Filter out the guest account
        return users

    def _check_connectivity(self):
        """Check if winexe works on the Windows VM"""

        retries = self.sysprep_params['connection_retries']
        # If the connection_retries parameter is set to 0 disable the
        # connectivity check
        if retries == 0:
            return True

        passwd = self.sysprep_params['password']
        winexe = WinEXE('Administrator', passwd, 'localhost')
        winexe.uninstall().debug(9)

        for i in range(retries):
            (stdout, stderr, rc) = winexe.run('cmd /C')
            if rc == 0:
                return True
            log = tempfile.NamedTemporaryFile(delete=False)
            try:
                log.file.write(stdout)
            finally:
                log.close()
            self.out.output("failed! See: `%s' for the full output" % log.name)
            if i < retries - 1:
                self.out.output("retrying ...", False)

        raise FatalError("Connection to the Windows VM failed after %d retries"
                         % retries)

    def _guest_exec(self, command, fatal=True):
        """Execute a command on a windows VM"""

        passwd = self.sysprep_params['password']

        winexe = WinEXE('Administrator', passwd, 'localhost')
        winexe.runas('Administrator', passwd).uninstall()

        try:
            (stdout, stderr, rc) = winexe.run(command)
        except WinexeTimeout:
            FatalError("Command: `%s' timeout out." % command)

        if rc != 0 and fatal:
            reason = stderr if len(stderr) else stdout
            self.out.output("Command: `%s' failed (rc=%d). Reason: %s" %
                            (command, rc, reason))
            raise FatalError("Command: `%s' failed (rc=%d). Reason: %s" %
                             (command, rc, reason))

        return (stdout, stderr, rc)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
