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

"""This package hosts OS-specific code common for the various Microsoft
Windows OSes."""

import tempfile
import re
import os
import uuid
import time
from collections import namedtuple

from image_creator.os_type import OSBase, sysprep, add_sysprep_param
from image_creator.util import FatalError
from image_creator.os_type.windows.vm import VM, RANDOM_TOKEN as TOKEN
from image_creator.os_type.windows.registry import Registry
from image_creator.os_type.windows.winexe import WinEXE
from image_creator.os_type.windows import powershell

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

ID_2_VIO = {
    "1000": "netkvm",     # Virtio network device
    "1001": "viostor",    # Virtio block device
    "1002": "ballon",     # Virtio memory balloon
    "1003": "vioserial",  # Virtio console
    "1004": "vioscsi",    # Virtio SCSI
    "1005": "viorng",     # Virtio RNG
    "1009": "vio9p",      # Virtio filesystem
    "1041": "netkvm",     # Virtio network device
    "1042": "viostor",    # Virtio block device
    "1043": "vioserial",  # Virtio console
    "1044": "viorng",     # Virtio RNG
    "1045": "ballon",     # Virtio memory balloon
    "1048": "vioscsi",    # Virtio SCSI
    "1049": "vio9p",      # Virtio filesystem
    "1050": "viogpu",     # Virtio GPU
    "1052": "vioinput",   # Virtio input
}

# The PCI Device ID for VirtIO devices. 1af4 is the Vendor ID for Red Hat, Inc
PCI_DEV_ID = re.compile(r'pci\\ven_1af4&dev_(%s)' % "|".join(ID_2_VIO.keys()))

# A set of the available VirtIO drivers
VIRTIO = set(ID_2_VIO.values())

# The Administrator's Relative ID
ADMIN_RID = 500

TARGET_OS_VERSION = re.compile(
    r'nt(x86|ia64|amd64|arm)(?:.(\d*)(?:.(\d*)?)?)?', re.I)


def parse_inf(inf):
    """Parse the content of a Windows INF file and fetch all information found
    in the Version section, the target OS as well as the VirtIO drivers it
    defines.

    For more info check here:
        http://msdn.microsoft.com/en-us/library/windows/hardware/ff549520
    """

    driver = None
    target_os = set()

    sections = {}
    current = []

    prev_line = ""
    for line in iter(inf):
        # Strip comments
        line = prev_line + line.split(';')[0].strip()
        prev_line = ""

        if not len(line):
            continue

        # Does the directive span more lines?
        if line[-1] == "\\":
            prev_line = line
            continue

        # Does the line denote a section?
        if line.startswith('[') and line.endswith(']'):
            section_name = line[1:-1].strip().lower()
            if section_name not in sections:
                current = []
                sections[section_name] = current
            else:
                current = sections[section_name]
            continue

        # We only care about param = value lines
        if line.find('=') > 0:
            param, value = line.split('=', 1)
            current.append((param.strip(), value.strip()))

    models = []
    if 'manufacturer' in sections:
        for _, value in sections['manufacturer']:
            value = value.split(',')
            if len(value) == 0:
                continue

            # %strkey%=models-section-name [,TargetOSVersion] ...
            models.append(value[0].strip().lower())
            for i in range(len(value) - 1):
                target_os.add(value[i+1].strip().lower())

    if len(models):
        # [models-section-name] | [models-section-name.TargetOSVersion]
        models_section_name = \
            re.compile('^(' + "|".join(models) + ')(\\..+)?$')
        for model in [s for s in sections if models_section_name.match(s)]:
            for _, value in sections[model]:
                value = value.split(',')
                if len(value) == 1:
                    continue
                # The second value in a device-description entry is always the
                # hardware ID:
                #   install-section-name[,hw-id][,compatible-id...]
                hw_id = value[1].strip().lower()
                # If this matches a VirtIO device, then this is a VirtIO driver
                id_match = PCI_DEV_ID.match(hw_id)
                if id_match:
                    driver = ID_2_VIO[id_match.group(1)]

    strings = dict(sections['strings']) if 'strings' in sections else {}
    version = {}
    if 'version' in sections:
        # Replace all strkey tokens with their actual value
        for key, val in sections['version']:
            if val.startswith('%') and val.endswith('%'):
                try:
                    val = strings[val[1:-1]]
                except KeyError:
                    pass
            version[key] = val

    if len(target_os) == 0:
        target_os.add('ntx86')

    return driver, target_os, version


def virtio_dir_check(dirname):
    """Check if the needed virtio driver files are present in the dirname
    directory
    """
    if not dirname:
        return ""  # value not set

    # Check files in a case insensitive manner
    files = set(os.listdir(dirname))

    for inf in [f for f in files if f.lower().endswith('.inf')]:
        with open(os.path.join(dirname, inf)) as content:
            driver, _, _ = parse_inf(content)
            if driver:
                return dirname

    raise ValueError("Could not find any VirtIO driver in this directory. "
                     "Please select another one.")


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
    "virtio": "Directory hosting the Windows virtio drivers.",
    "virtio_timeout":
    "Time in seconds to wait for the installation of the VirtIO drivers."}


class Windows(OSBase):
    """OS class for Windows"""
    @add_sysprep_param('mem', "posint", 1024, DESCR['mem'])
    @add_sysprep_param('smp', "posint", 1, DESCR['smp'])
    @add_sysprep_param(
        'connection_retries', "posint", 5, DESCR['connection_retries'])
    @add_sysprep_param(
        'shutdown_timeout', "posint", 300, DESCR['shutdown_timeout'])
    @add_sysprep_param('boot_timeout', "posint", 600, DESCR['boot_timeout'])
    @add_sysprep_param('virtio', 'dir', "", DESCR['virtio'],
                       check=virtio_dir_check, hidden=True)
    @add_sysprep_param(
        'virtio_timeout', 'posint', 900, DESCR['virtio_timeout'])
    def __init__(self, image, **kwargs):
        super(Windows, self).__init__(image, **kwargs)

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

        self.registry = Registry(self.image)

        with self.mount(readonly=True, silent=True):
            self.out.info("Checking media state ...", False)

            # Enumerate the windows users
            (self.usernames,
             self.active_users,
             self.admins) = self.registry.enum_users()
            assert ADMIN_RID in self.usernames, "Administrator account missing"

            self.virtio_state = self.compute_virtio_state()

            self.arch = self.image.g.inspect_get_arch(self.root)
            if self.arch == 'x86_64':
                self.arch = 'amd64'
            elif self.arch == 'i386':
                self.arch = 'x86'
            major = int(self.image.g.inspect_get_major_version(self.root))
            minor = int(self.image.g.inspect_get_minor_version(self.root))
            self.nt_version = (major, minor)

            # The get_setup_state() command does not work for old windows
            if self.nt_version[0] >= 6:
                # If the image is already sysprepped, we cannot further
                # customize it.
                self.sysprepped = self.registry.get_setup_state() > 0
            else:
                # Fallback to NO although we done know
                # TODO: Add support for detecting the setup state on XP
                self.sysprepped = False

            self.out.success("done")

        # If the image is sysprepped no driver mappings will be present.
        self.systemdrive = None
        for drive, root in self.image.g.inspect_get_drive_mappings(self.root):
            if root == self.root:
                self.systemdrive = drive

        active_admins = [u for u in self.admins if u in self.active_users]
        if ADMIN_RID in self.active_users or len(active_admins) == 0:
            admin = ADMIN_RID
        else:
            active_admins.sort()
            admin = active_admins[0]

        self.vm = VM(
            self.image.device, self.sysprep_params,
            namedtuple('User', 'rid name')(admin, self.usernames[admin]))

    @sysprep('Disabling IPv6 privacy extensions',
             display="Disable IPv6 privacy extensions")
    def _disable_ipv6_privacy_extensions(self):
        """Disable IPv6 privacy extensions"""

        self.vm.rexec('netsh interface ipv6 set global '
                      'randomizeidentifiers=disabled store=persistent')

    @sysprep('Disabling Teredo interface', display="Disable Teredo")
    def _disable_teredo(self):
        """Disable Teredo interface"""

        self.vm.rexec('netsh interface teredo set state disabled')

    @sysprep('Disabling ISATAP Adapters', display="Disable ISATAP")
    def _disable_isatap(self):
        """Disable ISATAP Adapters"""

        self.vm.rexec('netsh interface isa set state disabled')

    @sysprep('Enabling ping responses')
    def _enable_pings(self):
        """Enable ping responses"""

        self.vm.rexec('netsh firewall set icmpsetting 8')

    @sysprep('Setting the system clock to UTC', display="UTC")
    def _utc(self):
        """Set the hardware clock to UTC"""

        path = r'HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation'
        self.vm.rexec(
            r'REG ADD %s /v RealTimeIsUniversal /t REG_DWORD /d 1 /f' % path)

    @sysprep('Clearing the event logs')
    def _clear_logs(self):
        """Clear all the event logs"""

        self.vm.rexec(
            "cmd /q /c for /f \"tokens=*\" %l in ('wevtutil el') do "
            "wevtutil cl \"%l\"")

    @sysprep('Executing Sysprep on the image (may take more that 10 min)',
             display="Microsoft Sysprep")
    def _microsoft_sysprep(self):
        """Run the Microsoft System Preparation Tool. This will remove
        system-specific data and will make the image ready to be deployed.
        After this no other task may run.
        """

        self.vm.rexec(r'C:\Windows\system32\sysprep\sysprep '
                      r'/quiet /generalize /oobe /shutdown', uninstall=True)
        self.sysprepped = True

    @sysprep('Converting the image into a KMS client', enabled=False,
             display="KMS client setup")
    def _kms_client_setup(self):
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

    @sysprep('Shrinking file system on the last partition')
    def _shrink(self):
        """Shrink the last file system. Please make sure the file system is
        defragged.
        """

        # Shrink the volume as much as possible and then give 100MB back.
        # From ntfsresize:
        # Practically the smallest shrunken size generally is at around
        # "used space" + (20-200 MB). Please also take into account that
        # Windows might need about 50-100 MB free space left to boot safely.
        cmd = (
            r'cmd /Q /V:ON /C "SET SCRIPT=%TEMP%\QUERYMAX_%RANDOM%.TXT & ' +
            r'ECHO SELECT DISK 0 > %SCRIPT% & ' +
            'ECHO SELECT PARTITION %d >> %%SCRIPT%% & ' % self.last_part_num +
            r'ECHO SHRINK NOERR >> %SCRIPT% & ' +
            r'ECHO EXTEND SIZE=100 NOERR >> %SCRIPT% & ' +
            r'ECHO EXIT >> %SCRIPT% & ' +
            r'DISKPART /S %SCRIPT% & ' +
            r'IF NOT !ERRORLEVEL! EQU 0 EXIT /B 1 & ' +
            r'DEL /Q %SCRIPT%"')

        stdout, _, rc = self.vm.rexec(cmd, fatal=False)

        if rc != 0:
            raise FatalError(
                "Shrinking failed. Please make sure the media is defragged.")

        for line in stdout.splitlines():
            line = line.strip()
            if not len(line):
                continue
            self.out.info(" %s" % line)

        self.shrinked = True

    def do_sysprep(self):
        """Prepare system for image creation."""

        self.out.info('Preparing system for image creation:')

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

        timeout = self.sysprep_params['boot_timeout'].value
        shutdown_timeout = self.sysprep_params['shutdown_timeout'].value

        self.out.info("Preparing media for boot ...", False)

        with self.mount(readonly=False, silent=True):

            if not self.registry.reset_account(self.vm.admin.rid):
                self._add_cleanup('sysprep', self.registry.reset_account,
                                  self.vm.admin.rid, False)

            old = self.registry.update_uac(0)
            if old != 0:
                self._add_cleanup('sysprep', self.registry.update_uac, old)

            old = self.registry.update_uac_remote_setting(1)
            if old != 1:
                self._add_cleanup('sysprep',
                                  self.registry.update_uac_remote_setting, old)

            def if_not_sysprepped(task, *args):
                """Only perform this if the image is not sysprepped"""
                if not self.sysprepped:
                    task(*args)

            # The next 2 registry values get completely removed by Microsoft
            # Sysprep. They should not be reverted if Sysprep gets executed.
            old = self.registry.update_noautoupdate(1)
            if old != 1:
                self._add_cleanup('sysprep', if_not_sysprepped,
                                  self.registry.update_noautoupdate, old)

            old = self.registry.update_auoptions(1)
            if old != 1:
                self._add_cleanup('sysprep', if_not_sysprepped,
                                  self.registry.update_auoptions, old)

            # disable the firewalls
            self._add_cleanup('sysprep', self.registry.update_firewalls,
                              *self.registry.update_firewalls(0, 0, 0))

            v_val = self.registry.reset_passwd(self.vm.admin.rid)

            self._add_boot_scripts()

            # Delete the pagefile. It will be recreated when the system boots
            try:
                pagefile = "%s/pagefile.sys" % self.systemroot
                self.image.g.rm_rf(self.image.g.case_sensitive_path(pagefile))
            except RuntimeError:
                pass

        self.out.success('done')

        self.image.disable_guestfs()
        booted = False
        try:
            self.out.info("Starting windows VM ...", False)
            self.vm.start()
            try:
                self.out.success("started (console on VNC display: %d)" %
                                 self.vm.display)

                self.out.info("Waiting for OS to boot ...", False)
                if not self.vm.wait_on_serial(timeout):
                    raise FatalError("Windows VM booting timed out!")
                self.out.success('done')
                booted = True

                # Since the password is reset when logging in, sleep a little
                # bit before checking the connectivity, to avoid race
                # conditions
                time.sleep(5)

                self.out.info("Checking connectivity to the VM ...", False)
                self._check_connectivity()
                # self.out.success('done')

                # self.out.info("Disabling automatic logon ...", False)
                self._disable_autologon()
                self.out.success('done')

                self._exec_sysprep_tasks()

                self.out.info("Waiting for windows to shut down ...", False)
                (_, stderr, rc) = self.vm.wait(shutdown_timeout)
                if rc != 0 or "terminating on signal" in stderr:
                    raise FatalError("Windows VM died unexpectedly!\n\n"
                                     "(rc=%d)\n%s" % (rc, stderr))
                self.out.success("done")
            finally:
                # if the VM is not already dead here, a Fatal Error will have
                # already been raised. There is no reason to make the command
                # fatal.
                self.vm.stop(shutdown_timeout if booted else 1, fatal=False)
        finally:
            self.image.enable_guestfs()

            self.out.info("Reverting media boot preparations ...", False)
            with self.mount(readonly=False, silent=True, fatal=False):

                if not self.ismounted:
                    self.out.warn("The boot changes cannot be reverted. "
                                  "The snapshot may be in a corrupted state.")
                else:
                    if not self.sysprepped:
                        # Reset the old password
                        self.registry.reset_passwd(self.vm.admin.rid, v_val)

                    self._cleanup('sysprep')
                    self.out.success("done")

        self.image.shrink(silent=True)

    def _exec_sysprep_tasks(self):
        """This function hosts the actual code for executing the enabled
        sysprep tasks. At the end of this method the VM is shut down if needed.
        """
        tasks = self.list_syspreps()
        enabled = [t for t in tasks if self.sysprep_enabled(t)]
        size = len(enabled)

        # Make sure shrink runs in the end, before ms sysprep
        enabled = [t for t in enabled if self.sysprep_info(t).name != 'shrink']
        if len(enabled) != size:
            enabled.append(self._shrink)

        # Make sure the ms sysprep is the last task to run if it is enabled
        enabled = [t for t in enabled
                   if self.sysprep_info(t).name != 'microsoft-sysprep']

        if len(enabled) != size:
            enabled.append(self._microsoft_sysprep)

        cnt = 0
        for task in enabled:
            cnt += 1
            self.out.info(('(%d/%d)' % (cnt, size)).ljust(7), False)
            task()
            del self._sysprep_tasks[task.__name__]

        self.out.info("Sending shut down command ...", False)
        if not self.sysprepped:
            self._shutdown()
        self.out.success("done")

    def _shutdown(self):
        """Shuts down the windows VM"""
        self.vm.rexec(r'shutdown /s /t 5', uninstall=True)

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

        # Disable hibernation. This is not needed for a VM
        commands['hibernate'] = r'powercfg.exe /hibernate off'
        # This script will send a random string to the first serial port. This
        # can be used to determine when the OS has booted.
        commands['BootMonitor'] = "cmd /q /a /c echo " + TOKEN + " > COM1"

        # This will update the password of the admin user to self.vm.password
        commands["UpdatePassword"] = "net user %s %s" % \
            (self.vm.admin.name, self.vm.password)

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

        self.registry.enable_autologon(self.vm.admin.name)

    def _do_inspect(self):
        """Run various diagnostics to check if the medium is supported"""

        self.out.info(
            'Checking if this version of Windows is supported ...', False)

        # TODO: Check if PowerShell is installed. By default this is installed
        # in every version after Windows Vista. Maybe we could support a
        # Windows Vista medium if it has PowerShell installed.
        if self.nt_version >= (6, 1):
            self.out.success('yes')
        else:
            self.out.info()
            self.image.set_unsupported(
                '%s is too old. Versions prior to Windows 7 are not supported.'
                % self.meta['DESCRIPTION'])

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Windows, self)._do_collect_metadata()

        # We only care for active users
        active = [self.usernames[a] for a in self.active_users]
        self.meta["USERS"] = " ".join(active)

        # Get RDP settings
        settings = self.registry.get_rdp_settings()

        if settings['disabled']:
            self.out.warn("RDP is disabled on the image")
        else:
            if 'REMOTE_CONNECTION' not in self.meta:
                self.meta['REMOTE_CONNECTION'] = ""
            else:
                self.meta['REMOTE_CONNECTION'] += " "

            port = settings['port']
            if len(active):
                rdp = ["rdp:port=%d,user=%s" % (port, user) for user in active]
                self.meta['REMOTE_CONNECTION'] += " ".join(rdp)
            else:
                self.meta['REMOTE_CONNECTION'] += "rdp:port=%d" % port
        self.meta["KERNEL"] = "Windows NT %d.%d" % self.nt_version
        self.meta['GUI'] = 'Windows'

        major, minor = self.nt_version
        self.meta['SORTORDER'] += (100 * major + minor) * 100

    def _check_connectivity(self):
        """Check if winexe works on the Windows VM"""

        retries = self.sysprep_params['connection_retries'].value
        timeout = [5]
        for i in xrange(1, retries - 1):
            timeout.insert(0, timeout[0] * 2)

        # If the connection_retries parameter is set to 0 disable the
        # connectivity check
        if retries == 0:
            return True

        for i in xrange(retries):
            (stdout, stderr, rc) = self.vm.rexec('cmd /C', fatal=False,
                                                 debug=True)
            if rc == 0:
                return True

            log = tempfile.NamedTemporaryFile(delete=False)
            try:
                log.file.write("STDOUT:\n%s\n" % stdout)
                log.file.write("STDERR:\n%s\n" % stderr)
            finally:
                log.close()
            self.out.info("failed! See: `%s' for the full output" % log.name)
            if i < retries - 1:
                wait = timeout.pop()
                self.out.info("retrying in %d seconds ..." % wait, False)
                time.sleep(wait)

        raise FatalError("Connection to the Windows VM failed after %d retries"
                         % retries)

    def compute_virtio_state(self, directory=None):
        """Returns information about the VirtIO drivers found either in a
        directory or the media itself if the directory is None.
        """
        state = {}
        for driver in VIRTIO:
            state[driver] = {}

        def oem_files():
            """Parse oem*.inf files under the %SystemRoot%/Inf directory"""
            path = self.image.g.case_sensitive_path("%s/inf" % self.systemroot)
            oem = re.compile(r'^oem\d+\.inf', flags=re.IGNORECASE)
            for name in [f['name'] for f in self.image.g.readdir(path)]:
                if not oem.match(name):
                    continue
                yield name, \
                    self.image.g.cat("%s/%s" % (path, name)).splitlines()

        def local_files():
            """Parse *.inf files under a local directory"""
            assert os.path.isdir(directory)
            inf = re.compile(r'^.+\.inf', flags=re.IGNORECASE)
            for name in os.listdir(directory):
                fullpath = os.path.join(directory, name)
                if inf.match(name) and os.path.isfile(fullpath):
                    with open(fullpath, 'r') as content:
                        yield name, content

        for name, txt in oem_files() if directory is None else local_files():
            driver, target, content = parse_inf(txt)

            if driver:
                content['TargetOSVersions'] = target
                state[driver][name] = content

        return state

    def _fetch_virtio_drivers(self, dirname):
        """Examines a directory for VirtIO drivers and returns only the drivers
        that are suitable for this media.
        """
        collection = self.compute_virtio_state(dirname)

        files = set([f.lower() for f in os.listdir(dirname)
                     if os.path.isfile(dirname + os.sep + f)])

        num = 0
        for drv_type, drvs in collection.items():
            for inf, content in drvs.items():
                valid = True
                found_match = False
                # Check if the driver is suitable for the input media
                for target in content['TargetOSVersions']:
                    match = TARGET_OS_VERSION.match(target)
                    if match:
                        arch = match.group(1).lower()
                        major = int(match.group(2)) if match.group(2) else 0
                        minor = int(match.group(3)) if match.group(3) else 0
                        if self.arch != arch:
                            continue
                        if self.nt_version >= (major, minor):
                            found_match = True
                            break
                if not found_match:  # Wrong Target
                    self.out.warn(
                        'Ignoring %s. Driver not targeted for this OS.' % inf)
                    valid = False
                elif 'CatalogFile' not in content:
                    self.out.warn(
                        'Ignoring %s. CatalogFile entry missing.' % inf)
                    valid = False
                elif content['CatalogFile'].lower() not in files:
                    self.out.warn('Ignoring %s. Catalog File not found.' % inf)
                    valid = False

                if not valid:
                    del collection[drv_type][inf]
                    continue

                num += 1
            if len(drvs) == 0:
                del collection[drv_type]

        self.out.info('Found %d valid driver%s' %
                      (num, "s" if num != 1 else ""))
        return collection

    def install_virtio_drivers(self, upgrade=True):
        """Install new VirtIO drivers on the input media. If upgrade is True,
        then the old drivers found in the media will be removed.
        """

        dirname = self.sysprep_params['virtio'].value
        if not dirname:
            raise FatalError('No directory hosting the VirtIO drivers defined')

        self.out.info('Installing VirtIO drivers:')

        valid_drvs = self._fetch_virtio_drivers(dirname)
        if not len(valid_drvs):
            self.out.warn('No suitable driver found to install!')
            return

        remove = []
        certs = []
        install = []
        add = []
        # Check which drivers we need to install, which to add to the database
        # and which to remove.
        for dtype in valid_drvs:
            versions = [v['DriverVer'] for k, v in valid_drvs[dtype].items()]
            certs.extend([v['CatalogFile'] for k, v in
                          valid_drvs[dtype].items() if 'CatalogFile' in v])
            installed = [(k, v['DriverVer']) for k, v in
                         self.virtio_state[dtype].items()]
            found = [d[0] for d in installed if d[1] in versions]
            not_found = [d[0] for d in installed if d[1] not in versions]

            for drvr in found:
                details = self.virtio_state[dtype][drvr]
                self.out.warn('%s driver with version %s is already installed!'
                              % (dtype, details['DriverVer']))
            if upgrade:
                remove.extend(not_found)

            if dtype == 'viostor':
                install.extend([d for d in valid_drvs[dtype]])
            else:
                add.extend([d for d in valid_drvs[dtype]])

        try:
            self._update_driver_database('virtio', upload=dirname, certs=certs,
                                         add=add, install=install,
                                         remove=remove)
        finally:
            with self.mount(readonly=False, silent=True, fatal=False):
                if not self.ismounted:
                    self.out.warn("The boot changes cannot be reverted. "
                                  "The image may be in a corrupted state.")
                else:
                    self._cleanup('virtio')

        self.out.success("VirtIO drivers were successfully installed")
        self.out.info()

    def _update_driver_database(self, namespace, **kwargs):
        """Upload a directory that contains the VirtIO drivers and add scripts
        for installing and removing specific drivers.

        Keyword arguments:
        namespace -- namespace for the cleanup entries
        upload  -- Host directory that contains drivers to upload
        add     -- List of drivers to add to the driver database
        install -- List of drivers to install to the system
        remove  -- List of drivers to remove from the system
        """

        upload = kwargs['upload'] if 'upload' in kwargs else None
        add = kwargs['add'] if 'add' in kwargs else []
        install = kwargs['install'] if 'install' in kwargs else []
        certs = kwargs['certs'] if 'certs' in kwargs else []
        remove = kwargs['remove'] if 'remove' in kwargs else []

        assert len(add) == 0 or upload is not None
        assert len(install) == 0 or upload is not None

        with self.mount(readonly=False, silent=True):
            # Reset admin password
            self._add_cleanup(namespace, self.registry.reset_passwd,
                              self.vm.admin.rid,
                              self.registry.reset_passwd(self.vm.admin.rid))

            # Enable admin account (if needed)
            self._add_cleanup(namespace, self.registry.reset_account,
                              self.vm.admin.rid,
                              self.registry.reset_account(self.vm.admin.rid))

            old = self.registry.update_uac(0)
            if old != 0:
                self._add_cleanup(namespace, self.registry.update_uac, old)

            old = self.registry.update_noautoupdate(1)
            if old != 1:
                self._add_cleanup(namespace,
                                  self.registry.update_noautoupdate, old)

            old = self.registry.update_auoptions(1)
            if old != 1:
                self._add_cleanup(namespace,
                                  self.registry.update_auoptions, old)

            # We disable this with powershell scripts
            self.registry.enable_autologon(self.vm.admin.name)

            # Disable first logon animation (if needed)
            self._add_cleanup(namespace,
                              self.registry.reset_first_logon_animation,
                              self.registry.reset_first_logon_animation(False))

            tmp = uuid.uuid4().hex
            self.image.g.mkdir_p("%s/%s" % (self.systemroot, tmp))

            # This is a hack. We create a function here and pass it to
            # _add_cleanup because self.image.g may change and the _add_cleanup
            # will cache it which is wrong. For older versions of the guestfs
            # library we recreate the g handler in enable_guestfs() and the
            # program will crash if cleanup retains an older value for the
            # guestfs handler.
            def remove_tmp():
                self.image.g.rm_rf("%s/%s" % (self.systemroot, tmp))

            self._add_cleanup(namespace, remove_tmp)

            if upload is not None:
                for fname in os.listdir(upload):
                    full_path = os.path.join(upload, fname)
                    if os.path.isfile(full_path):
                        self.image.g.upload(full_path, "%s/%s/%s" %
                                            (self.systemroot, tmp, fname))

            drvs_install = powershell.DRVINST_HEAD

            for cert in certs:
                drvs_install += powershell.ADD_CERTIFICATE % cert

            for driver in install:
                drvs_install += powershell.INSTALL_DRIVER % driver

            for driver in add:
                drvs_install += powershell.ADD_DRIVER % driver

            for driver in remove:
                drvs_install += powershell.REMOVE_DRIVER % driver

            if self.check_version(6, 1) <= 0:
                self._install_viostor_driver(upload)
                old = self.registry.update_devices_dirs("%SystemRoot%\\" + tmp)
                self._add_cleanup(
                    namespace, self.registry.update_devices_dirs, old, False)
                drvs_install += powershell.DISABLE_AUTOLOGON
            else:
                # In newer windows, in order to reduce the boot process the
                # boot drivers are cached. To be able to boot with viostor, we
                # need to reboot in safe mode.
                drvs_install += powershell.SAFEBOOT

            drvs_install += powershell.DRVINST_TAIL

            target = "%s/%s/InstallDrivers.ps1" % (self.systemroot, tmp)
            self.image.g.write(target, drvs_install.replace('\n', '\r\n'))

            # The -windowstyle option was introduced in PowerShell V2. We need
            # to have at least Windows NT 6.1 (Windows 7 or Windows 2008R2) to
            # make this work.
            hidden_support = self.check_version(6, 1) >= 0
            cmd = (
                '%(drive)s:%(root)s\\System32\\WindowsPowerShell\\v1.0\\'
                'powershell.exe -ExecutionPolicy RemoteSigned %(hidden)s '
                '-File %(drive)s:%(root)s\\%(tmp)s\\InstallDrivers.ps1 '
                '%(drive)s:%(root)s\\%(tmp)s' %
                {'root': self.systemroot.replace('/', '\\'),
                 'drive': self.systemdrive,
                 'tmp': tmp,
                 'hidden': '-windowstyle hidden' if hidden_support else ""})

            # The value name of RunOnce keys can be prefixed with an asterisk
            # (*) to force the program to run even in Safe mode.
            self.registry.runonce({'*InstallDrivers': cmd})

        # Boot the Windows VM to update the driver's database
        self._boot_virtio_vm()

    def _boot_virtio_vm(self):
        """Boot the media and install the VirtIO drivers"""

        old_windows = self.check_version(6, 1) <= 0
        self.image.disable_guestfs()
        try:
            timeout = self.sysprep_params['boot_timeout'].value
            shutdown_timeout = self.sysprep_params['shutdown_timeout'].value
            virtio_timeout = self.sysprep_params['virtio_timeout'].value
            self.out.info("Starting Windows VM ...", False)
            booted = False
            try:
                if old_windows:
                    self.vm.start()
                else:
                    self.vm.interface = 'ide'
                    self.vm.start(extra_disk=('/dev/null', 'virtio'))
                    self.vm.interface = 'virtio'

                self.out.success("started (console on VNC display: %d)" %
                                 self.vm.display)
                self.out.info("Waiting for Windows to boot ...", False)
                if not self.vm.wait_on_serial(timeout):
                    raise FatalError("Windows VM booting timed out!")
                self.out.success('done')
                booted = True
                self.out.info("Installing new drivers ...", False)
                if not self.vm.wait_on_serial(virtio_timeout):
                    raise FatalError("Windows VirtIO installation timed out!")
                self.out.success('done')
                self.out.info('Shutting down ...', False)
                (_, stderr, rc) = self.vm.wait(shutdown_timeout)
                if rc != 0 or "terminating on signal" in stderr:
                    raise FatalError("Windows VM died unexpectedly!\n\n"
                                     "(rc=%d)\n%s" % (rc, stderr))
                self.out.success('done')
            finally:
                self.vm.stop(shutdown_timeout if booted else 1, fatal=False)
        finally:
            self.image.enable_guestfs()

        with self.mount(readonly=True, silent=True):
            self.virtio_state = self.compute_virtio_state()
            viostor_service_found = self.registry.check_viostor_service()

        if not (len(self.virtio_state['viostor']) and viostor_service_found):
            raise FatalError("viostor was not successfully installed")

        if self.check_version(6, 1) > 0:
            # Hopefully restart in safe mode. Newer windows will not boot from
            # a viostor device unless we initially start them in safe mode
            try:
                self.out.info('Rebooting Windows VM in safe mode ...', False)
                self.vm.start()
                (_, stderr, rc) = self.vm.wait(timeout + shutdown_timeout)
                if rc != 0 or "terminating on signal" in stderr:
                    raise FatalError("Windows VM died unexpectedly!\n\n"
                                     "(rc=%d)\n%s" % (rc, stderr))
                self.out.success('done')
            finally:
                self.vm.stop(1, fatal=True)

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

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
