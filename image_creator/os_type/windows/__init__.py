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
from image_creator.os_type.windows.vm import VM, RANDOM_TOKEN as TOKEN
from image_creator.os_type.windows.registry import Registry
from image_creator.os_type.windows.winexe import WinEXE
from image_creator.os_type.windows.powershell import DRVINST_HEAD, SAFEBOOT, \
    DRVINST_TAIL

import tempfile
import re
import os

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
    "Windows Server 2008 Enterprise": "YQGMW-MPWTJ-34KDK-48M3W-X4Q6V",
    "Windows Server 2008 Enterprise without Hyper-V":
    "39BXF-X8Q23-P2WWT-38T2F-G3FPG",
    "Windows Server 2008 HPC": "RCTX3-KWVHP-BR6TB-RB6DM-6X7HP",
    "Windows Server 2008 Datacenter": "7M67G-PC374-GR742-YH8V4-TCBY3",
    "Windows Server 2008 Datacenter without Hyper-V":
    "22XQ2-VRXRG-P8D42-K34TD-G3QQC",
    "Windows Server 2008 for Itanium-Based Systems":
    "4DWFP-JF3DJ-B7DTH-78FJB-PDRHK"}

VIRTIO = (
    "viostor",  # "VirtIO SCSI controller"
    "vioscsi",  # "VirtIO SCSI pass-through controller"
    "vioser",   # "VirtIO Serial Driver"
    "netkvm",   # "VirtIO Ethernet Adapter"
    "balloon",  # "VirtIO Balloon Driver
    "viorng")   # "VirtIO RNG Driver"


def virtio_dir_check(dirname):
    """Check if the needed virtio driver files are present in the dirname
    directory
    """
    if not dirname:
        return ""  # value not set

    ext = ('cat', 'inf', 'sys')

    # Check files in a case insensitive manner
    files = set([f.lower() for f in os.listdir(dirname)])

    found = False
    for cat, inf, sys in [["%s.%s" % (b, e) for e in ext] for b in VIRTIO]:
        if cat in files and inf in files and sys in files:
            found = True

    if not found:
        raise ValueError("Invalid VirtIO directory. No VirtIO driver found")

    return dirname


DESCR = {
    "boot_timeout":
    "Time in seconds to wait for the Windows customization VM to boot.",
    "shutdown_timeout":
    "Time in seconds to wait for the Windows customization VM to shut down "
    "after the initial command is given.",
    "connection_retries":
    "Number of times to try to connect to the Windows customization VM after "
    "it has booted, before giving up.",
    "smp": "Number of CPUs to use for the Windows customization VM.",
    "mem": "Virtual RAM size in MiB for the Windows customization VM.",
    "admin": "Name of the Administration user.",
    "virtio": "Directory hosting the Windows virtio drivers.",
    "virtio_timeout": "Time in seconds to wait for the installation of the "
    "VirtIO drivers."}


class Windows(OSBase):
    """OS class for Windows"""
    @add_sysprep_param('admin', "string", 'Administrator', DESCR['admin'])
    @add_sysprep_param('mem', "posint", 1024, DESCR['mem'])
    @add_sysprep_param('smp', "posint", 1, DESCR['smp'])
    @add_sysprep_param(
        'connection_retries', "posint", 5, DESCR['connection_retries'])
    @add_sysprep_param(
        'shutdown_timeout', "posint", 120, DESCR['shutdown_timeout'])
    @add_sysprep_param('boot_timeout', "posint", 300, DESCR['boot_timeout'])
    @add_sysprep_param('virtio', 'dir', "", DESCR['virtio'], virtio_dir_check)
    @add_sysprep_param(
        'virtio_timeout', 'posint', 300, DESCR['virtio_timeout'])
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

        device = self.image.g.part_to_dev(self.root)

        self.last_part_num = self.image.g.part_list(device)[-1]['part_num']

        self.product_name = self.image.g.inspect_get_product_name(self.root)
        self.systemroot = self.image.g.inspect_get_windows_systemroot(
            self.root)

        self.vm = VM(self.image.device, self.sysprep_params)
        self.registry = Registry(self.image.g, self.root)

        # If the image is already sysprepped we cannot further customize it
        with self.mount(readonly=True, silent=True):
            self.out.output("Checking media state ...", False)
            self.sysprepped = self.registry.get_setup_state() > 0
            self.virtio_state = self._virtio_state()
            self.out.success("done")

        # If the image is sysprepped no driver mappings will be present.
        self.systemdrive = None
        for drive, root in self.image.g.inspect_get_drive_mappings(self.root):
            if root == self.root:
                self.systemdrive = drive

    @sysprep('Disabling IPv6 privacy extensions')
    def disable_ipv6_privacy_extensions(self):
        """Disable IPv6 privacy extensions"""

        self.vm.rexec('netsh interface ipv6 set global '
                      'randomizeidentifiers=disabled store=persistent')

    @sysprep('Disabling Teredo interface')
    def disable_teredo(self):
        """Disable Teredo interface"""

        self.vm.rexec('netsh interface teredo set state disabled')

    @sysprep('Disabling ISATAP Adapters')
    def disable_isatap(self):
        """Disable ISATAP Adapters"""

        self.vm.rexec('netsh interface isa set state disabled')

    @sysprep('Enabling ping responses')
    def enable_pings(self):
        """Enable ping responses"""

        self.vm.rexec('netsh firewall set icmpsetting 8')

    @sysprep('Disabling hibernation support')
    def disable_hibernation(self):
        """Disable hibernation support and remove the hibernation file"""

        self.vm.rexec(r'powercfg.exe /hibernate off')

    @sysprep('Setting the system clock to UTC')
    def utc(self):
        """Set the hardware clock to UTC"""

        path = r'HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation'
        self.vm.rexec(
            r'REG ADD %s /v RealTimeIsUniversal /t REG_DWORD /d 1 /f' % path)

    @sysprep('Clearing the event logs')
    def clear_logs(self):
        """Clear all the event logs"""

        self.vm.rexec(
            "cmd /q /c for /f \"tokens=*\" %l in ('wevtutil el') do "
            "wevtutil cl \"%l\"")

    @sysprep('Executing Sysprep on the image (may take more that 10 min)')
    def microsoft_sysprep(self):
        """Run the Microsoft System Preparation Tool. This will remove
        system-specific data and will make the image ready to be deployed.
        After this no other task may run.
        """

        self.vm.rexec(r'C:\Windows\system32\sysprep\sysprep '
                      r'/quiet /generalize /oobe /shutdown')
        self.sysprepped = True

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

        self.vm.rexec(
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

        stdout, stderr, rc = self.vm.rexec(cmd)

        querymax = None
        for line in stdout.splitlines():
            # diskpart will return something like this:
            #
            #   The maximum number of reclaimable bytes is: xxxx MB
            #
            if line.find('reclaimable') >= 0:
                answer = line.split(':')[1].strip()
                m = re.search(r'(\d+) MB', answer)
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

        stdout, stderr, rc = self.vm.rexec(cmd, False)

        if rc != 0:
            FatalError("Shrinking failed. Please make sure the media is "
                       "defraged with a command like this: "
                       "`Defrag.exe /U /X /W'")
        for line in stdout.splitlines():
            if line.find('shrunk') >= 0:
                self.out.output(line)

    def do_sysprep(self):
        """Prepare system for image creation."""

        self.out.output('Preparing system for image creation:')

        # Check if winexe is installed
        if not WinEXE.is_installed():
            raise FatalError(
                "Winexe not found! In order to be able to customize a Windows "
                "image you need to have Winexe installed.")

        if self.sysprepped:
            raise FatalError(
                "Microsoft's System Preparation Tool has ran on the media. "
                "Further image customization is not possible.")

        if len(self.virtio_state['viostor']) == 0:
            raise FatalError(
                "The media has no VirtIO SCSI controller driver installed. "
                "Further image customization is not possible.")

        if len(self.virtio_state['netkvm']) == 0:
            raise FatalError(
                "The media has no VirtIO Ethernet Adapter driver installed. "
                "Further image customization is not possible.")

        admin = self.sysprep_params['admin'].value
        timeout = self.sysprep_params['boot_timeout'].value
        shutdown_timeout = self.sysprep_params['shutdown_timeout'].value

        self.out.output("Preparing media for boot ...", False)

        with self.mount(readonly=False, silent=True):
            v_val = self.registry.reset_passwd(admin)
            disabled_uac = self.registry.update_uac_remote_setting(1)
            self._add_boot_scripts()

            # disable the firewalls
            firewall_states = self.registry.update_firewalls(0, 0, 0)

            # Delete the pagefile. It will be recreated when the system boots
            try:
                pagefile = "%s/pagefile.sys" % self.systemroot
                self.image.g.rm_rf(self.image.g.case_sensitive_path(pagefile))
            except RuntimeError:
                pass

        self.out.success('done')

        self.image.disable_guestfs()
        try:
            self.out.output("Starting windows VM ...", False)
            self.vm.start()
            try:
                self.out.success("started (console on VNC display: %d)" %
                                 self.vm.display)

                self.out.output("Waiting for OS to boot ...", False)
                if not self.vm.wait_on_serial(timeout):
                    raise FatalError("Windows VM booting timed out!")
                self.out.success('done')

                self.out.output("Checking connectivity to the VM ...", False)
                self._check_connectivity()
                # self.out.success('done')

                # self.out.output("Disabling automatic logon ...", False)
                self._disable_autologon()
                self.out.success('done')

                self._exec_sysprep_tasks()

                self.out.output("Waiting for windows to shut down ...", False)
                self.vm.wait(shutdown_timeout)
                self.out.success("done")
            finally:
                # if the VM is not already dead here, a Fatal Error will have
                # already been raised. There is no reason to make the command
                # fatal.
                self.vm.stop(1, fatal=False)
        finally:
            self.image.enable_guestfs()

            self.out.output("Reverting media boot preparations ...", False)
            with self.mount(readonly=False, silent=True, fatal=False):
                if disabled_uac:
                    self.registry.update_uac_remote_setting(0)

                if not self.sysprepped:
                    # Reset the old password
                    admin = self.sysprep_params['admin'].value
                    self.registry.reset_passwd(admin, v_val)

                self.registry.update_firewalls(*firewall_states)
            self.out.success("done")

    def _exec_sysprep_tasks(self):
        """This function hosts the actual code for executing the enabled
        sysprep tasks. At the end of this method the VM is shut down if needed.
        """
        tasks = self.list_syspreps()
        enabled = [task for task in tasks if task.enabled]
        size = len(enabled)

        # Make sure shrink runs in the end, before ms sysprep
        enabled = [task for task in enabled
                   if self.sysprep_info(task).name != 'shrink']
        if len(enabled) != size:
            enabled.append(self.shrink)

        # Make sure the ms sysprep is the last task to run if it is enabled
        enabled = [task for task in enabled
                   if self.sysprep_info(task).name != 'microsoft-sysprep']

        if len(enabled) != size:
            enabled.append(self.microsoft_sysprep)

        cnt = 0
        for task in enabled:
            cnt += 1
            self.out.output(('(%d/%d)' % (cnt, size)).ljust(7), False)
            task()
            setattr(task.im_func, 'executed', True)

        self.out.output("Sending shut down command ...", False)
        if not self.sysprepped:
            self._shutdown()
        self.out.success("done")

    def _shutdown(self):
        """Shuts down the windows VM"""
        self.vm.rexec(r'shutdown /s /t 5')

    def _disable_autologon(self):
        """Disable automatic logon on the windows image"""

        winlogon = \
            r'"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"'

        self.vm.rexec('REG DELETE %s /v DefaultUserName /f' % winlogon)
        self.vm.rexec('REG DELETE %s /v DefaultPassword /f' % winlogon)
        self.vm.rexec('REG DELETE %s /v AutoAdminLogon /f' % winlogon)

    def _add_boot_scripts(self):
        """Add various scripts in the registry that will be executed during the
        next boot.
        """

        commands = {}

        # This script will send a random string to the first serial port. This
        # can be used to determine when the OS has booted.
        commands['BootMonitor'] = "cmd /q /a /c echo " + TOKEN + " > COM1"

        # This will update the password of the admin user to self.vm.password
        commands["UpdatePassword"] = "net user %s %s" % \
            (self.sysprep_params['admin'].value, self.vm.password)

        # This is previously done with hivex when we executed
        # self.registry.update_uac_remote_setting(1).
        # Although the command above works on all windows version and the
        # UAC remote restrictions are disabled, on Windows 2012 the registry
        # value seems corrupted after we run the command. Maybe this has to do
        # with a bug or a limitation in hivex. As a workaround we re-update the
        # value from within Windows.
        commands["UpdateRegistry"] = \
            (r'REG ADD HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion'
             r'\policies\system /v LocalAccountTokenFilterPolicy'
             r' /t REG_DWORD /d 1 /f')

        self.registry.runonce(commands)

        # Enable automatic logon.
        # This is needed in order for the scripts we added in the RunOnce
        # registry entry to get executed, since the RunOnce commands only get
        # executed when a user logs on. There is a RunServicesOnce registry
        # entry whose keys get executed in the background when the logon dialog
        # box first appears, but they seem to only work with services and not
        # arbitrary command line expressions :-(
        #
        # Instructions on how to turn on automatic logon in Windows can be
        # found here: http://support.microsoft.com/kb/324737
        #
        # Warning: Registry change will not work if the “Logon Banner” is
        # defined on the server either by a Group Policy object (GPO) or by a
        # local policy.

        self.registry.enable_autologon(self.sysprep_params['admin'].value)

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Windows, self)._do_collect_metadata()

        # We only care for active users
        _, users = self.registry.enum_users()
        self.meta["USERS"] = " ".join(users)

    def _check_connectivity(self):
        """Check if winexe works on the Windows VM"""

        retries = self.sysprep_params['connection_retries'].value
        # If the connection_retries parameter is set to 0 disable the
        # connectivity check
        if retries == 0:
            return True

        for i in range(retries):
            (stdout, stderr, rc) = self.vm.rexec('cmd /C', fatal=False,
                                                 debug=True)
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

    def _virtio_state(self):
        """Check if the virtio drivers are install and return the information
        about the installed driver
        """

        inf_path = self.image.g.case_sensitive_path("%s/inf" % self.systemroot)

        state = {}
        for driver in VIRTIO:
            state[driver] = {}

        def parse_inf(filename):
            """Parse a Windows INF file and fetch all information found in the
            Version section.
            """
            version = {}  # The 'Version' section
            strings = {}  # The 'Strings' section
            section = ""
            current = None
            prev_line = ""
            fullpath = "%s/%s" % (inf_path, filename)
            for line in self.image.g.cat(fullpath).splitlines():
                line = prev_line + line.strip().split(';')[0].strip()
                prev_line = ""

                if not len(line):
                    continue

                if line[-1] == "\\":
                    prev_line = line
                    continue

                # Does the line denote a section?
                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1].lower()
                    if section == 'version':
                        current = version
                    if section == 'strings':
                        current = strings

                # We only care about 'version' and 'string' sections
                if section not in ('version', 'strings'):
                    continue

                # We only care about param = value lines
                if line.find('=') < 0:
                    continue

                param, value = line.split('=', 1)
                current[param.strip()] = value.strip()

            # Replace all strkey tokens with their actual value
            for k, v in version.items():
                if v.startswith('%') and v.endswith('%'):
                    strkey = v[1:-1]
                    if strkey in strings:
                        version[k] = strings[strkey]

            cat = version['CatalogFile'] if 'CatalogFile' in version else ""
            for driver in VIRTIO:
                if cat.lower() == "%s.cat" % driver:
                    state[driver][filename] = version

        oem = re.compile(r'^oem\d+\.inf', flags=re.IGNORECASE)
        for f in self.image.g.readdir(inf_path):
            if oem.match(f['name']):
                parse_inf(f['name'])

        return state

    def install_virtio_drivers(self):
        """Install the virtio drivers on the media"""

        dirname = self.sysprep_params['virtio'].value
        if not dirname:
            raise FatalError('No directory hosting the VirtIO drivers defined')

        self.out.output('Installing virtio drivers:')

        with self.mount(readonly=False, silent=True):

            admin = self.sysprep_params['admin'].value
            v_val = self.registry.reset_passwd(admin)
            self.registry.enable_autologon(admin)
            self._upload_virtio_drivers(dirname)

            drvs_install = DRVINST_HEAD.replace('\n', '\r\n')

            if self.check_version(6, 1) <= 0:
                self._install_viostor_driver(dirname)
            else:
                # In newer windows, in order to reduce the boot process the
                # boot drivers are cached. To be able to boot with viostor, we
                # need to reboot in safe mode.
                drvs_install += SAFEBOOT.replace('\n', '\r\n')

            drvs_install += DRVINST_TAIL.replace('\n', '\r\n')

            remotedir = self.image.g.case_sensitive_path("%s/VirtIO" %
                                                         self.systemroot)
            self.image.g.write(remotedir + "/InstallDrivers.ps1", drvs_install)

            cmd = (
                '%(drive)s:%(root)s\\System32\\WindowsPowerShell\\v1.0\\'
                'powershell.exe -ExecutionPolicy RemoteSigned -File '
                '%(drive)s:%(root)s\\VirtIO\\InstallDrivers.ps1 '
                '%(drive)s:%(root)s\\Virtio' %
                {'root': self.systemroot.replace('/', '\\'),
                 'drive': self.systemdrive})

            # The value name of RunOnce keys can be prefixed with an asterisk
            # (*) to force the program to run even in Safe mode.
            self.registry.runonce({'*InstallDrivers': cmd})

        timeout = self.sysprep_params['boot_timeout'].value
        shutdown_timeout = self.sysprep_params['shutdown_timeout'].value
        virtio_timeout = self.sysprep_params['virtio_timeout'].value
        self.out.output("Starting Windows VM ...", False)
        try:
            if self.check_version(6, 1) <= 0:
                self.vm.start()
            else:
                self.vm.interface = 'ide'
                self.vm.start(extra_disk=('/dev/null', 'virtio'))
                self.vm.interface = 'virtio'

            self.out.success("started (console on VNC display: %d)" %
                             self.vm.display)
            self.out.output("Waiting for Windows to boot ...", False)
            if not self.vm.wait_on_serial(timeout):
                raise FatalError("Windows VM booting timed out!")
            self.out.success('done')
            self.out.output("Performing the drivers installation ...", False)
            if not self.vm.wait_on_serial(virtio_timeout):
                raise FatalError("Windows VirtIO installation timed out!")
            self.out.success('done')
            self.out.output('Shutting down ...', False)
            self.vm.wait(shutdown_timeout)
            self.out.success('done')
        finally:
            self.vm.stop(1, fatal=False)

        with self.mount(readonly=True, silent=True):
            self.virtio_state = self._virtio_state()
            viostor_service_found = self.registry.check_viostor_service()

        if not (len(self.virtio_state['viostor']) and viostor_service_found):
            raise FatalError("viostor was not successfully installed")

        if self.check_version(6, 1) > 0:
            # Hopefully restart in safe mode. Newer windows will not boot from
            # a viostor device unless we initially start them in safe mode
            try:
                self.out.output('Rebooting Windows VM in safe mode ...', False)
                self.vm.start()
                self.vm.wait(timeout + shutdown_timeout)
                self.out.success('done')
            finally:
                self.vm.stop(1, fatal=False)
        self.out.output("VirtIO drivers were successfully installed")

    def _install_viostor_driver(self, dirname):
        """Quick and dirty installation of the VirtIO SCSI controller driver.
        It is done to make the image boot from the VirtIO disk.

        http://rwmj.wordpress.com/2010/04/30/
            tip-install-a-device-driver-in-a-windows-vm/
        """

        drivers_path = "%s/system32/drivers" % self.systemroot

        try:
            drivers_path = self.image.g.case_sensitive_path(drivers_path)
        except RuntimeError as err:
            raise FatalError("Unable to browse to directory: %s. Reason: %s" %
                             (drivers_path, str(err)))
        viostor = dirname + os.sep + 'viostor.sys'
        try:
            self.image.g.upload(viostor, drivers_path + '/viostor.sys')
        except RuntimeError as err:
            raise FatalError("Unable to upload file %s to %s. Reason: %s" %
                             (viostor, drivers_path, str(err)))

        self.registry.add_viostor()

    def _upload_virtio_drivers(self, dirname):
        """Install the virtio drivers to the media"""

        virtio_dir = self.image.g.case_sensitive_path("%s/VirtIO" %
                                                      self.systemroot)
        self.image.g.mkdir_p(virtio_dir)

        for fname in os.listdir(dirname):
            full_path = os.path.join(dirname, fname)
            if os.path.isfile(full_path):
                self.image.g.upload(full_path, "%s/%s" % (virtio_dir, fname))

        self.registry.update_devices_dirs(r"%SystemRoot%\VirtIO")

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
