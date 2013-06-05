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

from image_creator.os_type.unix import Unix, sysprep

import re
import time


class Linux(Unix):
    """OS class for Linux"""
    def __init__(self, rootdev, ghandler, output):
        super(Linux, self).__init__(rootdev, ghandler, output)
        self._uuid = dict()
        self._persistent = re.compile('/dev/[hsv]d[a-z][1-9]*')

        self.meta["USERS"] = " ".join(self._get_passworded_users())

        # Delete the USERS metadata if empty
        if not len(self.meta['USERS']):
            self.out.warn("No passworded users found!")
            del self.meta['USERS']

    def _get_passworded_users(self):
        users = []
        regexp = re.compile('(\S+):((?:!\S+)|(?:[^!*]\S+)|):(?:\S*:){6}')

        for line in self.g.cat('/etc/shadow').splitlines():
            match = regexp.match(line)
            if not match:
                continue

            user, passwd = match.groups()
            if len(passwd) > 0 and passwd[0] == '!':
                self.out.warn("Ignoring locked %s account." % user)
            else:
                users.append(user)

        return users

    def is_persistent(self, dev):
        return not self._persistent.match(dev)

    def get_uuid(self, dev):
        if dev in self._uuid:
            return self._uuid[dev]

        uuid = self.g.vfs_uuid(dev)
        assert len(uuid)
        self._uuid[dev] = uuid
        return uuid

    @sysprep(enabled=False)
    def remove_user_accounts(self, print_header=True):
        """Remove all user accounts with id greater than 1000"""

        if print_header:
            self.out.output("Removing all user accounts with id greater than "
                            "1000")

        if 'USERS' not in self.meta:
            return

        # Remove users from /etc/passwd
        passwd = []
        removed_users = {}
        metadata_users = self.meta['USERS'].split()
        for line in self.g.cat('/etc/passwd').splitlines():
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

        self.g.write('/etc/passwd', '\n'.join(passwd) + '\n')

        # Remove the corresponding /etc/shadow entries
        shadow = []
        for line in self.g.cat('/etc/shadow').splitlines():
            fields = line.split(':')
            if fields[0] not in removed_users:
                shadow.append(':'.join(fields))

        self.g.write('/etc/shadow', "\n".join(shadow) + '\n')

        # Remove the corresponding /etc/group entries
        group = []
        for line in self.g.cat('/etc/group').splitlines():
            fields = line.split(':')
            # Remove groups tha have the same name as the removed users
            if fields[0] not in removed_users:
                group.append(':'.join(fields))

        self.g.write('/etc/group', '\n'.join(group) + '\n')

        # Remove home directories
        for home in [field[5] for field in removed_users.values()]:
            if self.g.is_dir(home) and home.startswith('/home/'):
                self.g.rm_rf(home)

    @sysprep()
    def cleanup_passwords(self, print_header=True):
        """Remove all passwords and lock all user accounts"""

        if print_header:
            self.out.output("Cleaning up passwords & locking all user "
                            "accounts")

        shadow = []

        for line in self.g.cat('/etc/shadow').splitlines():
            fields = line.split(':')
            if fields[1] not in ('*', '!'):
                fields[1] = '!'

            shadow.append(":".join(fields))

        self.g.write('/etc/shadow', "\n".join(shadow) + '\n')

    @sysprep()
    def fix_acpid(self, print_header=True):
        """Replace acpid powerdown action scripts to immediately shutdown the
        system without checking if a GUI is running.
        """

        if print_header:
            self.out.output('Fixing acpid powerdown action')

        powerbtn_action = '#!/bin/sh\n\nPATH=/sbin:/bin:/usr/bin\n' \
                          'shutdown -h now "Power button pressed"\n'

        events_dir = '/etc/acpi/events'
        if not self.g.is_dir(events_dir):
            self.out.warn("No acpid event directory found")
            return

        event_exp = re.compile('event=(.+)', re.I)
        action_exp = re.compile('action=(.+)', re.I)
        for f in self.g.readdir(events_dir):
            if f['ftyp'] != 'r':
                continue

            fullpath = "%s/%s" % (events_dir, f['name'])
            event = ""
            action = ""
            for line in self.g.cat(fullpath).splitlines():
                m = event_exp.match(line)
                if m:
                    event = m.group(1)
                    continue
                m = action_exp.match(line)
                if m:
                    action = m.group(1)
                    continue

            if event.strip() in ("button[ /]power", "button/power.*"):
                if action:
                    if not self.g.is_file(action):
                        self.out.warn("Acpid action file: %s does not exist" %
                                      action)
                        return
                    self.g.copy_file_to_file(action,
                                             "%s.orig.snf-image-creator-%d" %
                                             (action, time.time()))
                    self.g.write(action, powerbtn_action)
                    return
                else:
                    self.out.warn("Acpid event file %s does not contain and "
                                  "action")
                    return
            elif event.strip() == ".*":
                self.out.warn("Found action `.*'. Don't know how to handle "
                              "this. Please edit `%s' image file manually to "
                              "make the system immediatelly shutdown when an "
                              "power button acpi event occures." %
                              action.strip().split()[0])
                return

        self.out.warn("No acpi power button event found!")

    @sysprep()
    def remove_persistent_net_rules(self, print_header=True):
        """Remove udev rules that will keep network interface names persistent
        after hardware changes and reboots. Those rules will be created again
        the next time the image runs.
        """

        if print_header:
            self.out.output('Removing persistent network interface names')

        rule_file = '/etc/udev/rules.d/70-persistent-net.rules'
        if self.g.is_file(rule_file):
            self.g.rm(rule_file)

    @sysprep()
    def remove_swap_entry(self, print_header=True):
        """Remove swap entry from /etc/fstab. If swap is the last partition
        then the partition will be removed when shrinking is performed. If the
        swap partition is not the last partition in the disk or if you are not
        going to shrink the image you should probably disable this.
        """

        if print_header:
            self.out.output('Removing swap entry from fstab')

        new_fstab = ""
        fstab = self.g.cat('/etc/fstab')
        for line in fstab.splitlines():

            entry = line.split('#')[0].strip().split()
            if len(entry) == 6 and entry[2] == 'swap':
                continue

            new_fstab += "%s\n" % line

        self.g.write('/etc/fstab', new_fstab)

    @sysprep()
    def use_persistent_block_device_names(self, print_header=True):
        """Scan fstab & grub configuration files and replace all non-persistent
        device references with UUIDs.
        """

        if print_header:
            self.out.output("Replacing fstab & grub non-persistent device "
                            "references")

        # convert all devices in fstab to persistent
        persistent_root = self._persistent_fstab()

        # convert all devices in grub1 to persistent
        self._persistent_grub1(persistent_root)

    def _persistent_grub1(self, new_root):
        if self.g.is_file('/boot/grub/menu.lst'):
            grub1 = '/boot/grub/menu.lst'
        elif self.g.is_file('/etc/grub.conf'):
            grub1 = '/etc/grub.conf'
        else:
            return

        self.g.aug_init('/', 0)
        try:
            roots = self.g.aug_match('/files%s/title[*]/kernel/root' % grub1)
            for root in roots:
                dev = self.g.aug_get(root)
                if not self.is_persistent(dev):
                    # This is not always correct. Grub may contain root entries
                    # for other systems, but we only support 1 OS per hard
                    # disk, so this shouldn't harm.
                    self.g.aug_set(root, new_root)
        finally:
            self.g.aug_save()
            self.g.aug_close()

    def _persistent_fstab(self):
        mpoints = self.g.mountpoints()
        if len(mpoints) == 0:
            pass  # TODO: error handling

        device_dict = dict([[mpoint, dev] for dev, mpoint in mpoints])

        root_dev = None
        new_fstab = ""
        fstab = self.g.cat('/etc/fstab')
        for line in fstab.splitlines():

            line, dev, mpoint = self._convert_fstab_line(line, device_dict)
            new_fstab += "%s\n" % line

            if mpoint == '/':
                root_dev = dev

        self.g.write('/etc/fstab', new_fstab)
        if root_dev is None:
            pass  # TODO: error handling

        return root_dev

    def _convert_fstab_line(self, line, devices):
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

        if not self.is_persistent(dev):
            if mpoint in devices:
                dev = "UUID=%s" % self.get_uuid(devices[mpoint])
                entry[0] = dev
            else:
                # comment out the entry
                entry[0] = "#%s" % dev
            return " ".join(entry), dev, mpoint

        return orig, dev, mpoint

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
