# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2015 GRNET S.A.
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

"""This module hosts OS-specific code for Linux."""

from image_creator.os_type.unix import Unix, sysprep, add_sysprep_param

import os
import re
import time
import pkg_resources
import tempfile

X2GO_DESKTOPSESSIONS = {
    'CINNAMON': 'cinnamon',
    'KDE': 'startkde',
    'GNOME': 'gnome-session',
    'MATE': 'mate-session',
    'XFCE': 'xfce4-session',
    'LXDE': 'startlxde',
    'TRINITY': 'starttrinity',
    'UNITY': 'unity',
}

X2GO_EXECUTABLE = "x2goruncommand"

DISTRO_ORDER = {
    "ubuntu": 80,
    "linuxmint": 75,
    "debian": 70,
    "rhel": 60,
    "fedora": 58,
    "centos": 55,
    "scientificlinux": 50,
    "sles": 45,
    "opensuse": 44,
    "archlinux": 40,
    "gentoo": 35,
    "slackware": 30,
    "oraclelinux": 28,
    "mageia": 20,
    "mandriva": 19,
    "cirros": 15,
    "pardus": 10
}


class Linux(Unix):
    """OS class for Linux"""
    @add_sysprep_param(
        'bootmenu_timeout', 'posint', 10, "Boot menu timeout in seconds")
    def __init__(self, image, **kwargs):
        super(Linux, self).__init__(image, **kwargs)
        self._uuid = dict()
        self._persistent = re.compile('/dev/[hsv]d[a-z][1-9]*')

    @sysprep('Removing user accounts with id greater that 1000', enabled=False)
    def _remove_user_accounts(self):
        """Remove all user accounts with id greater than 1000"""

        if 'USERS' not in self.meta:
            return

        # Remove users from /etc/passwd
        passwd = []
        removed_users = {}
        metadata_users = self.meta['USERS'].split()
        for line in self.image.g.cat('/etc/passwd').splitlines():
            fields = line.split(':')
            if int(fields[2]) > 1000:
                removed_users[fields[0]] = fields
                # remove it from the USERS metadata too
                if fields[0] in metadata_users:
                    metadata_users.remove(fields[0])
            else:
                passwd.append(':'.join(fields))

        self.meta['USERS'] = " ".join(metadata_users)

        # Delete the USERS metadata if empty
        if not len(self.meta['USERS']):
            del self.meta['USERS']

        self.image.g.write('/etc/passwd', '\n'.join(passwd) + '\n')

        # Remove the corresponding /etc/shadow entries
        shadow = []
        for line in self.image.g.cat('/etc/shadow').splitlines():
            fields = line.split(':')
            if fields[0] not in removed_users:
                shadow.append(':'.join(fields))

        self.image.g.write('/etc/shadow', "\n".join(shadow) + '\n')

        # Remove the corresponding /etc/group entries
        group = []
        for line in self.image.g.cat('/etc/group').splitlines():
            fields = line.split(':')
            # Remove groups tha have the same name as the removed users
            if fields[0] not in removed_users:
                group.append(':'.join(fields))

        self.image.g.write('/etc/group', '\n'.join(group) + '\n')

        # Remove home directories
        for home in [field[5] for field in removed_users.values()]:
            if self.image.g.is_dir(home) and home.startswith('/home/'):
                self.image.g.rm_rf(home)

    @sysprep('Cleaning up password & locking all user accounts')
    def _cleanup_passwords(self):
        """Remove all passwords and lock all user accounts"""

        shadow = []

        for line in self.image.g.cat('/etc/shadow').splitlines():
            fields = line.split(':')
            if fields[1] not in ('*', '!'):
                fields[1] = '!'

            shadow.append(":".join(fields))

        self.image.g.write('/etc/shadow', "\n".join(shadow) + '\n')

        # Remove backup file for /etc/shadow
        self.image.g.rm_rf('/etc/shadow-')

    @sysprep('Fixing acpid powerdown action')
    def _fix_acpid(self):
        """Replace acpid powerdown action scripts to immediately shutdown the
        system without checking if a GUI is running.
        """

        powerbtn_action = '#!/bin/sh\n\nPATH=/sbin:/bin:/usr/bin\n' \
                          'shutdown -h now "Power button pressed"\n'

        events_dir = '/etc/acpi/events'
        if not self.image.g.is_dir(events_dir):
            self.out.warn("No acpid event directory found")
            return

        event_exp = re.compile('event=(.+)', re.I)
        action_exp = re.compile('action=(.+)', re.I)
        for events_file in self.image.g.readdir(events_dir):
            if events_file['ftyp'] != 'r':
                continue

            fullpath = "%s/%s" % (events_dir, events_file['name'])
            event = ""
            action = ""
            for line in self.image.g.cat(fullpath).splitlines():
                match = event_exp.match(line)
                if match:
                    event = match.group(1)
                    continue
                match = action_exp.match(line)
                if match:
                    action = match.group(1)
                    continue

            if event.strip() in ("button[ /]power", "button/power.*"):
                if action:
                    if not self.image.g.is_file(action):
                        self.out.warn("Acpid action file: %s does not exist" %
                                      action)
                        return
                    self.image.g.copy_file_to_file(
                        action, "%s.orig.snf-image-creator-%d" %
                        (action, time.time()))
                    self.image.g.write(action, powerbtn_action)
                    return
                else:
                    self.out.warn("Acpid event file %s does not contain and "
                                  "action")
                    return
            elif event.strip() == ".*":
                self.out.warn("Found action `.*'. Don't know how to handle "
                              "this. Please edit `%s' image file manually to "
                              "make the system immediately shutdown when an "
                              "power button ACPI event occurs." %
                              action.strip().split()[0])
                return

        self.out.warn("No acpi power button event found!")

    @sysprep('Removing persistent network interface names')
    def _remove_persistent_net_rules(self):
        """Remove udev rules that will keep network interface names persistent
        after hardware changes and reboots. Those rules will be created again
        the next time the image runs.
        """

        rule_file = '/etc/udev/rules.d/70-persistent-net.rules'
        if self.image.g.is_file(rule_file):
            self.image.g.rm(rule_file)

    @sysprep('Removing swap entry from fstab')
    def _remove_swap_entry(self):
        """Remove swap entry from /etc/fstab. If swap is the last partition
        then the partition will be removed when shrinking is performed. If the
        swap partition is not the last partition in the disk or if you are not
        going to shrink the image you should probably disable this.
        """

        new_fstab = ""
        fstab = self.image.g.cat('/etc/fstab')
        for line in fstab.splitlines():

            entry = line.split('#')[0].strip().split()
            if len(entry) == 6 and entry[2] == 'swap':
                continue

            new_fstab += "%s\n" % line

        self.image.g.write('/etc/fstab', new_fstab)

    @sysprep('Change boot menu timeout to %(bootmenu_timeout)s seconds')
    def _change_bootmenu_timeout(self):
        """Change the boot menu timeout to the one specified by the namesake
        system preparation parameter.
        """

        timeout = self.sysprep_params['bootmenu_timeout'].value

        if self.image.g.is_file('/etc/default/grub'):
            self.image.g.aug_init('/', 0)
            try:
                self.image.g.aug_set('/files/etc/default/grub/GRUB_TIMEOUT',
                                     str(timeout))
            finally:
                self.image.g.aug_save()
                self.image.g.aug_close()

        def replace_timeout(remote, regexp, timeout):
            """Replace the timeout value from a config file"""
            tmpfd, tmp = tempfile.mkstemp()
            try:
                for line in self.image.g.cat(remote).splitlines():
                    if regexp.match(line):
                        line = re.sub('\d+', str(timeout), line)
                    os.write(tmpfd, line + '\n')
                os.close(tmpfd)
                tmpfd = None
                self.image.g.upload(tmp, remote)
            finally:
                if tmpfd is not None:
                    os.close(tmpfd)
                os.unlink(tmp)

        grub1_config = '/boot/grub/menu.lst'
        grub2_config = '/boot/grub/grub.cfg'
        syslinux_config = '/boot/syslinux/syslinux.cfg'

        if self.image.g.is_file(grub1_config):
            regexp = re.compile(r'^\s*timeout\s+\d+\s*$')
            replace_timeout(grub1_config, regexp, timeout)
        elif self.image.g.is_file(grub2_config):
            regexp = re.compile(r'^\s*set\s+timeout=\d+\s*$')
            replace_timeout(grub2_config, regexp, timeout)

        if self.image.g.is_file(syslinux_config):
            regexp = re.compile(r'^\s*TIMEOUT\s+\d+\s*$', re.IGNORECASE)
            # In syslinux the timeout unit is 0.1 seconds
            replace_timeout(syslinux_config, regexp, timeout * 10)

    @sysprep('Replacing fstab & grub non-persistent device references')
    def _use_persistent_block_device_names(self):
        """Scan fstab & grub configuration files and replace all non-persistent
        device references with UUIDs.
        """

        # convert all devices in fstab to persistent
        persistent_root = self._persistent_fstab()

        # convert root device in grub1 to persistent
        self._persistent_grub1(persistent_root)

        # convert root device in syslinux to persistent
        self._persistent_syslinux(persistent_root)

    @sysprep('Disabling IPv6 privacy extensions',
             display='Disable IPv6 privacy enxtensions')
    def _disable_ipv6_privacy_extensions(self):
        """Disable IPv6 privacy extensions."""

        file_path = '/files/etc/sysctl.conf/net.ipv6.conf.%s.use_tempaddr'
        dir_path = '/files/etc/sysctl.d/*/net.ipv6.conf.%s.use_tempaddr'

        self.image.g.aug_init('/', 0)
        try:
            default = self.image.g.aug_match(file_path % 'default') + \
                self.image.g.aug_match(dir_path % 'default')

            all = self.image.g.aug_match(file_path % 'all') + \
                self.image.g.aug_match(dir_path % 'all')

            if len(default) == 0:
                self.image.g.aug_set(file_path % 'default', '0')
            else:
                for token in default:
                    self.image.g.aug_set(token, '0')

            if len(all) == 0:
                self.image.g.aug_set(file_path % 'all', '0')
            else:
                for token in all:
                    self.image.g.aug_set(token, '0')

        finally:
            self.image.g.aug_save()
            self.image.g.aug_close()

    def _persistent_grub1(self, new_root):
        """Replaces non-persistent device name occurrences with persistent
        ones in GRUB1 configuration files.
        """
        if self.image.g.is_file('/boot/grub/menu.lst'):
            grub1 = '/boot/grub/menu.lst'
        elif self.image.g.is_file('/etc/grub.conf'):
            grub1 = '/etc/grub.conf'
        else:
            return

        self.image.g.aug_init('/', 0)
        try:
            roots = self.image.g.aug_match(
                '/files%s/title[*]/kernel/root' % grub1)
            for root in roots:
                dev = self.image.g.aug_get(root)
                if not self._is_persistent(dev):
                    # This is not always correct. Grub may contain root entries
                    # for other systems, but we only support 1 OS per hard
                    # disk, so this shouldn't harm.
                    self.image.g.aug_set(root, new_root)
        finally:
            self.image.g.aug_save()
            self.image.g.aug_close()

    def _persistent_syslinux(self, new_root):
        """Replace non-persistent root device name occurrences with persistent
        ones in the syslinux configuration files.
        """

        config = '/boot/syslinux/syslinux.cfg'
        append_regexp = re.compile(
            r'\s*APPEND\s+.*\broot=/dev/[hsv]d[a-z][1-9]*\b', re.IGNORECASE)

        if not self.image.g.is_file(config):
            return

        # There is no augeas lense for syslinux :-(
        tmpfd, tmp = tempfile.mkstemp()
        try:
            for line in self.image.g.cat(config).splitlines():
                if append_regexp.match(line):
                    line = re.sub(r'\broot=/dev/[hsv]d[a-z][1-9]*\b',
                                  'root=%s' % new_root, line)
                os.write(tmpfd, line + '\n')
            os.close(tmpfd)
            tmpfd = None
            self.image.g.upload(tmp, config)
        finally:
            if tmpfd is not None:
                os.close(tmpfd)
            os.unlink(tmp)

    def _persistent_fstab(self):
        """Replaces non-persistent device name occurrences in /etc/fstab with
        persistent ones.
        """
        mpoints = self.image.g.mountpoints()
        if len(mpoints) == 0:
            pass  # TODO: error handling

        device_dict = dict([[mpoint, dev] for dev, mpoint in mpoints])

        root_dev = None
        new_fstab = ""
        fstab = self.image.g.cat('/etc/fstab')
        for line in fstab.splitlines():

            line, dev, mpoint = self._convert_fstab_line(line, device_dict)
            new_fstab += "%s\n" % line

            if mpoint == '/':
                root_dev = dev

        self.image.g.write('/etc/fstab', new_fstab)
        if root_dev is None:
            pass  # TODO: error handling

        return root_dev

    def _convert_fstab_line(self, line, devices):
        """Replace non-persistent device names in an fstab line to their UUID
        equivalent
        """
        orig = line
        line = line.split('#')[0].strip()
        if len(line) == 0:
            return orig, "", ""

        entry = line.split()
        if len(entry) != 6:
            self.out.warn("Detected abnormal entry in fstab")
            return orig, "", ""

        dev = entry[0]
        mpoint = entry[1]

        if not self._is_persistent(dev):
            if mpoint in devices:
                dev = "UUID=%s" % self._get_uuid(devices[mpoint])
                entry[0] = dev
            else:
                # comment out the entry
                entry[0] = "#%s" % dev
            return " ".join(entry), dev, mpoint

        return orig, dev, mpoint

    def _do_inspect(self):
        """Run various diagnostics to check if media is supported"""

        self.out.info(
            'Checking if the media contains logical volumes (LVM)...', False)

        has_lvm = True if len(self.image.g.lvs()) else False

        if has_lvm:
            self.out.info()
            self.image.set_unsupported('The media contains logical volumes')
        else:
            self.out.success('no')

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Linux, self)._do_collect_metadata()
        users = self._get_passworded_users()
        self.meta["USERS"] = " ".join(users)

        # Delete the USERS metadata if empty
        if not len(self.meta['USERS']):
            self.out.warn("No passworded users found!")
            del self.meta['USERS']

        kernels = []
        for f in self.image.g.ls('/boot'):
            if f.startswith('config-'):
                kernels.append(f[7:])

        if len(kernels):
            kernels.sort(key=pkg_resources.parse_version)
            self.meta['KERNEL'] = kernels[-1]

        distro = self.image.g.inspect_get_distro(self.root)
        major = self.image.g.inspect_get_major_version(self.root)
        if major > 99:
            major = 99
        minor = self.image.g.inspect_get_minor_version(self.root)
        if minor > 99:
            minor = 99
        try:
            self.meta['SORTORDER'] += \
                10000 * DISTRO_ORDER[distro] + 100 * major + minor
        except KeyError:
            pass

        if self.is_enabled('sshd'):
            ssh = []
            opts = self.ssh_connection_options(users)
            for user in opts['users']:
                ssh.append("ssh:port=%d,user=%s" % (opts['port'], user))

            if 'REMOTE_CONNECTION' not in self.meta:
                self.meta['REMOTE_CONNECTION'] = ""
            else:
                self.meta['REMOTE_CONNECTION'] += " "

            if len(ssh):
                self.meta['REMOTE_CONNECTION'] += " ".join(ssh)
            else:
                self.meta['REMOTE_CONNECTION'] += "ssh:port=%d" % opts['port']

            # Check if x2go is installed
            x2go_installed = False
            desktops = set()
            for path in ('/bin', '/usr/bin', '/usr/local/bin'):
                if self.image.g.is_file("%s/%s" % (path, X2GO_EXECUTABLE)):
                    x2go_installed = True
                for name, exe in X2GO_DESKTOPSESSIONS.items():
                    if self.image.g.is_file("%s/%s" % (path, exe)):
                        desktops.add(name)

            if x2go_installed:
                self.meta['REMOTE_CONNECTION'] += " "
                if len(desktops) == 0:
                    self.meta['REMOTE_CONNECTION'] += "x2go"
                else:
                    self.meta['REMOTE_CONNECTION'] += \
                        " ".join(["x2go:session=%s" % d for d in desktops])
        else:
            self.out.warn("OpenSSH Daemon is not configured to run on boot")

    def is_enabled(self, service):
        """Check if a service is enabled to run on boot"""

        systemd_services = '/etc/systemd/system/multi-user.target.wants'
        exec_start = re.compile(r'^\s*ExecStart=.+bin/%s\s?' % service)
        if self.image.g.is_dir(systemd_services):
            for entry in self.image.g.readdir(systemd_services):
                if entry['ftyp'] not in ('l', 'f'):
                    continue
                service_file = "%s/%s" % (systemd_services, entry['name'])
                for line in self.image.g.cat(service_file).splitlines():
                    if exec_start.search(line):
                        return True

        found = set()

        def check_file(path):
            regexp = re.compile(r"[/=\s'\"]%s('\")?\s" % service)
            for line in self.image.g.cat(path).splitlines():
                line = line.split('#', 1)[0].strip()
                if len(line) == 0:
                    continue
                if regexp.search(line):
                    found.add(path)
                    return

        # Check upstart config files under /etc/init
        # Only examine *.conf files
        if self.image.g.is_dir('/etc/init'):
            self._foreach_file('/etc/init', check_file, maxdepth=1,
                               include=r'.+\.conf$')
            if len(found):
                return True

        # Check scripts under /etc/rc[1-5].d/ and /etc/rc.d/rc[1-5].d/
        for conf in ["/etc/%src%d.d" % (d, i) for i in xrange(1, 6)
                     for d in ('', 'rc.d/')]:
            try:
                for entry in self.image.g.readdir(conf):
                    if entry['ftyp'] not in ('l', 'f'):
                        continue
                    check_file("%s/%s" % (conf, entry['name']))

                    if len(found):
                        return True

            except RuntimeError:
                continue

        return False

    def _get_passworded_users(self):
        """Returns a list of non-locked user accounts"""

        if not self.image.g.is_file('/etc/shadow'):
            self.out.warn(
                "Unable to collect user info. File: `/etc/shadow' is missing!")
            return []

        users = []
        regexp = re.compile(r'(\S+):((?:!\S+)|(?:[^!*]\S+)|):(?:\S*:){6}')

        for line in self.image.g.cat('/etc/shadow').splitlines():
            match = regexp.match(line)
            if not match:
                continue

            user, passwd = match.groups()
            if len(passwd) > 0 and passwd[0] == '!':
                self.out.warn("Ignoring locked %s account." % user)
            else:
                users.append(user)

        return users

    def _is_persistent(self, dev):
        """Checks if a device name is persistent."""
        return not self._persistent.match(dev)

    def _get_uuid(self, dev):
        """Returns the UUID corresponding to a device"""
        if dev in self._uuid:
            return self._uuid[dev]

        uuid = self.image.g.vfs_uuid(dev)
        assert len(uuid)
        self._uuid[dev] = uuid
        return uuid

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
