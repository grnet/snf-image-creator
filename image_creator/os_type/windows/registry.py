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

"""This package hosts code for accessing the windows registry"""

from image_creator.util import FatalError

import hivex
import tempfile
import os
import struct

# The Administrators group RID
ADMINS = 0x00000220

# http://technet.microsoft.com/en-us/library/hh824815.aspx
WINDOWS_SETUP_STATES = (
    "IMAGE_STATE_COMPLETE",
    "IMAGE_STATE_UNDEPLOYABLE",
    "IMAGE_STATE_GENERALIZE_RESEAL_TO_OOBE",
    "IMAGE_STATE_GENERALIZE_RESEAL_TO_AUDIT",
    "IMAGE_STATE_SPECIALIZE_RESEAL_TO_OOBE",
    "IMAGE_STATE_SPECIALIZE_RESEAL_TO_AUDIT")

REG_SZ = lambda k, v: {'key': k, 't': 1L,
                       'value': (v + '\x00').encode('utf-16le')}
REG_EXPAND_SZ = lambda k, v: {'key': k, 't': 2L,
                              'value': (v + '\x00').encode('utf-16le')}
REG_BINARY = lambda k, v: {'key': k, 't': 3L, 'value': v}
REG_DWORD = lambda k, v: {'key': k, 't': 4L, 'value': struct.pack('<I', v)}


def safe_add_node(hive, parent, name):
    """Add a registry node only if it is not present"""

    node = hive.node_get_child(parent, name)
    return hive.node_add_child(parent, name) if node is None else node


def traverse(hive, path):
    """Traverse a hive following a path"""

    node = hive.root()

    for name in path.split('/'):

        if len(name) == 0:
            continue

        node = hive.node_get_child(node, name)
        if node is None:
            break

    return node


class Registry(object):
    """Windows Registry manipulation methods"""

    def __init__(self, image):
        # Do not copy the guestfs handler. It may be overwritten by the image
        # class in the future
        self.image = image
        self.root = image.root

    def open_hive(self, hive, write=False):
        """Returns a context manager for opening a hive file of the image for
        reading or writing.
        """
        systemroot = self.image.g.inspect_get_windows_systemroot(self.root)
        path = "%s/system32/config/%s" % (systemroot, hive)
        try:
            path = self.image.g.case_sensitive_path(path)
        except RuntimeError as err:
            raise FatalError("Unable to retrieve file: %s. Reason: %s" %
                             (hive, str(err)))

        # OpenHive class needs this since 'self' gets overwritten
        g = self.image.g

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

    @property
    def current_control_set(self):
        """Returns the current control set of the registry"""

        if hasattr(self, '_current_control_set'):
            return self._current_control_set

        with self.open_hive('SYSTEM') as hive:
            select = hive.node_get_child(hive.root(), 'Select')
            current_value = hive.node_get_value(select, 'Current')

            # expecting a little endian dword
            assert hive.value_type(current_value)[1] == 4
            current = "%03d" % hive.value_dword(current_value)

            self._current_control_set = 'ControlSet%s' % current

        return self._current_control_set

    def get_setup_state(self):
        """Returns the stage of Windows Setup the image is in.
        The method will return an int with one of the following values:
            0 => IMAGE_STATE_COMPLETE
            1 => IMAGE_STATE_GENERALIZE_RESEAL_TO_OOBE
            2 => IMAGE_STATE_GENERALIZE_RESEAL_TO_AUDIT
            3 => IMAGE_STATE_SPECIALIZE_RESEAL_TO_OOBE
            4 => IMAGE_STATE_SPECIALIZE_RESEAL_TO_AUDIT
        For more information check here:
            http://technet.microsoft.com/en-us/library/hh824815.aspx
        """

        with self.open_hive('SOFTWARE') as hive:
            # Navigate to:
            #   SOFTWARE/Microsoft/Windows/CurrentVersion/Setup/State
            state = hive.root()
            for child in ('Microsoft', 'Windows', 'CurrentVersion',
                          'Setup', 'State'):
                state = hive.node_get_child(state, child)

            image_state = hive.node_get_value(state, 'ImageState')
            vtype, value = hive.value_value(image_state)
            assert vtype == 1L, \
                "ImageState field type (=%d) is not REG_SZ" % vtype

            value = value.decode('utf-16le')

            ret = 0
            for known_state in WINDOWS_SETUP_STATES:
                if value == known_state + '\x00':  # REG_SZ is null-terminated
                    return ret
                ret += 1

        raise FatalError("Unknown Windows Setup State: %s" % value)

    def runonce(self, commands):
        """Add commands to the RunOnce registry key"""

        with self.open_hive('SOFTWARE', write=True) as hive:

            key = hive.root()
            for child in ('Microsoft', 'Windows', 'CurrentVersion'):
                key = hive.node_get_child(key, child)

            runonce = hive.node_get_child(key, "RunOnce")
            if runonce is None:
                runonce = hive.node_add_child(key, "RunOnce")

            for desc, cmd in commands.items():
                hive.node_set_value(runonce, REG_SZ(desc, cmd))

            hive.commit(None)

    def enable_autologon(self, username, password=""):
        """Enable automatic logon for a specific user"""

        with self.open_hive('SOFTWARE', write=True) as hive:

            winlogon = hive.root()
            for child in ('Microsoft', 'Windows NT', 'CurrentVersion',
                          'Winlogon'):
                winlogon = hive.node_get_child(winlogon, child)

            hive.node_set_value(winlogon, REG_SZ('DefaultUserName', username))
            hive.node_set_value(winlogon, REG_SZ('DefaultPassword', password))
            hive.node_set_value(winlogon, REG_SZ('AutoAdminLogon', "1"))

            hive.commit(None)

    def update_firewalls(self, domain, public, standard):
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

        with self.open_hive('SYSTEM', write=True) as hive:
            firewall_policy = hive.root()
            for child in (self.current_control_set, 'services', 'SharedAccess',
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

                hive.node_set_value(node, REG_DWORD('EnableFirewall',
                                                    new_values.pop(0)))
            hive.commit(None)

        return old_values

    def update_uac_remote_setting(self, value):
        r"""Updates the registry key value:
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

        with self.open_hive('SOFTWARE', write=True) as hive:
            path = 'Microsoft/Windows/CurrentVersion/Policies/System'
            system = traverse(hive, path)

            policy = None
            for val in hive.node_values(system):
                if hive.value_key(val) == "LocalAccountTokenFilterPolicy":
                    policy = val

            if policy is not None:
                if value == hive.value_dword(policy):
                    return False
            elif value == 0:
                return False

            hive.node_set_value(
                system, REG_DWORD("LocalAccountTokenFilterPolicy", value))
            hive.commit(None)

        return True

    def update_uac(self, value):
        """Enable or disable the User Account Control by changing the value of
        the EnableLUA registry key

        value = 1 will enable the UAC
        value = 0 will disable the UAC

        Returns:
            True if the key is changed
            False if the key is unchanged
        """

        if value not in (0, 1):
            raise ValueError("Valid values for value parameter are 0 and 1")

        with self.open_hive('SOFTWARE', write=True) as hive:
            path = 'Microsoft/Windows/CurrentVersion/Policies/System'
            system = traverse(hive, path)

            enablelua = None
            for val in hive.node_values(system):
                if hive.value_key(val) == 'EnableLUA':
                    enablelua = val

            if enablelua is not None:
                if value == hive.value_dword(enablelua):
                    return False
            elif value == 1:
                return False

            hive.node_set_value(system, REG_DWORD('EnableLUA', value))
            hive.commit(None)

        return True

    def enum_users(self):
        """Returns:
            a map of RID->username for all users found on the system
            a list of RIDs of active users
            a list of RIDs of members of the Administrators group
        """

        users = {}
        active = []
        members = []

        # Under HKLM\SAM\SAM\Domains\Account\Users\%RID% there is an F field
        # that contains information about this user account. Bytes 56 & 57 are
        # the account type and status flags and the first bit in this flag is
        # the 'account disabled' bit:
        #
        # http://www.beginningtoseethelight.org/ntsecurity/index.htm
        #        #8603CF0AFBB170DD
        #
        disabled = lambda f: int(f[56].encode('hex'), 16) & 0x01

        def collect_group_members(hive, group, rid_node):
            """Enumerate group members"""
            c_val = hive.value_value(hive.node_get_value(rid_node, 'C'))[1]

            # Check http://pogostick.net/~pnh/ntpasswd/ for more info
            offset = struct.unpack('<I', c_val[0x28:0x2c])[0] + 0x34
            #size = struct.unpack('<I', c_val[0x2c:0x30])[0]
            count = struct.unpack('<I', c_val[0x30:0x34])[0]

            # Parse the sid array and get all members
            while len(members) < count:
                sections = struct.unpack('<B', c_val[offset+1:offset+2])[0]
                rid_offs = offset + 8 + (sections - 1) * 4
                rid = struct.unpack('<I', c_val[rid_offs:rid_offs+4])[0]
                members.append(rid)
                offset += sections * 4 + 8

        def collect_users(hive, username, rid_node):
            """Enumerate active users"""
            f_val = hive.value_value(hive.node_get_value(rid_node, 'F'))[1]
            rid = int(hive.node_name(rid_node), 16)

            if not disabled(f_val):
                active.append(rid)

            users[rid] = username

        self._foreach_account(
            userlist=[], useraction=collect_users,
            grouplist=[ADMINS], groupaction=collect_group_members)

        return (users, active, members)

    def reset_passwd(self, rid, v_field=None):
        r"""Reset the password for user 'user'. If v_field is not None, the
        value of key \HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\%RID%\V
        is replaced with this one, otherwise the LM and NT passwords of the
        original V field are cleared out. In any case, the value of the
        original V field is returned.
        """

        # This is a hack because python 2.x does not support assigning new
        # values to nonlocal variables
        parent = {}

        def update_v_field(hive, username, rid_node):
            """Updates the user's V field to reset the password"""
            assert 'old' not in parent, "Multiple users with same username"

            field = hive.node_get_value(rid_node, 'V')
            v_type, v_val = hive.value_value(field)
            assert v_type == 3L, "V field type (=%d) isn't REG_BINARY" % v_type

            new = v_field
            if new is None:
                # In order to reset the passwords, all we need to do is to zero
                # out the length fields for the LM password hash and the NT
                # password hash in the V field of the user's %RID% node. LM
                # password hash length field is at offset 0xa0 and NT password
                # hash length is at offset 0xac. See here for more info:
                #
                # http://www.beginningtoseethelight.org/ntsecurity/index.htm
                #        #D3BC3F5643A17823
                fmt = '%ds4x8s4x%ds' % (0xa0, len(v_val) - 0xb0)
                new = ("\x00" * 4).join(struct.unpack(fmt, v_val))

            hive.node_set_value(rid_node, REG_BINARY('V', new))
            hive.commit(None)
            parent['old'] = v_val

        self._foreach_account(True, userlist=[rid], useraction=update_v_field)

        assert 'old' in parent, "user whith RID: `%s' does not exist" % rid
        return parent['old']

    def reset_account(self, rid, activate=True):

        # This is a hack. I cannot assign a new value to nonlocal variable.
        # This is why I'm using a dict
        state = {}

        # Convert byte to int
        to_int = lambda b: int(b.encode('hex'), 16)

        # Under HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\%RID% there is
        # an F field that contains information about this user account. Bytes
        # 56 & 57 are the account type and status flags. The first bit is the
        # 'account disabled' bit:
        #
        # http://www.beginningtoseethelight.org/ntsecurity/index.htm
        #        #8603CF0AFBB170DD
        #
        isactive = lambda f: (to_int(f[56]) & 0x01) == 0

        def update_f_field(hive, username, rid_node):
            """Updates the user's F field to reset the account"""
            field = hive.node_get_value(rid_node, 'F')
            f_type, f_val = hive.value_value(field)
            assert f_type == 3L, "F field type (=%d) isn't REG_BINARY" % f_type

            state['old'] = isactive(f_val)
            if activate is state['old']:
                # nothing to do
                return

            mask = (lambda b: b & 0xfe) if activate else (lambda b: b | 0x01)
            new = struct.pack("56sB23s", f_val[:56], mask(to_int(f_val[56])),
                              f_val[57:])

            hive.node_set_value(rid_node, REG_BINARY('F', new))
            hive.commit(None)

        self._foreach_account(True, userlist=[rid], useraction=update_f_field)

        return state['old']

    def reset_first_logon_animation(self, activate=True):
        """Enable or disable the first-logon animation.

        The method return the old value
        """

        with self.open_hive('SOFTWARE', write=True) as hive:
            path = 'Microsoft/Windows/CurrentVersion/Policies/System'
            system = traverse(hive, path)
            try:
                val = hive.node_get_value(system, 'EnableFirstLogonAnimation')
                old = bool(hive.value_dword(val))

                # There is no need to reset the value
                if old is activate:
                    return old
            except RuntimeError:
                # The value is not present at all
                if activate is False:
                    return False
                old = False

            hive.node_set_value(system, REG_DWORD('EnableFirstLogonAnimation',
                                                  int(activate)))
            hive.commit(None)

        return old

    def _foreach_account(self, write=False, **kargs):
        """Performs an action on the RID node of a user or a group in the
        registry, for every user/group found in the userlist/grouplist.
        If userlist/grouplist is empty, it performs the action on all
        users/groups.
        The write flag determines if the registry is opened for reading or
        writing.
        """

        def parse_sam(ridlist, action, path):
            """Parse the registry users and groups nodes"""

            accounts = traverse(hive, 'SAM/Domains/' + path)
            names = hive.node_get_child(accounts, 'Names')

            # The RID (relative identifier) of each user/group is stored as the
            # type!!!! (not the value) of the default key of the node under
            # Names whose name is the username/groupname.

            for node in hive.node_children(names):
                name = hive.node_name(node)
                rid = hive.value_type(hive.node_get_value(node, ""))[0]

                if len(ridlist) != 0 and rid not in ridlist:
                    continue

                # if RID is 500 (=0x1f4), the corresponding node name is
                # '000001F4'
                key = ("%8.x" % rid).replace(' ', '0').upper()
                rid_node = hive.node_get_child(accounts, key)

                action(hive, name, rid_node)

        userlist = kargs['userlist'] if 'userlist' in kargs else None
        useraction = kargs['useraction'] if 'useraction' in kargs else None

        grouplist = kargs['grouplist'] if 'grouplist' in kargs else None
        groupaction = kargs['groupaction'] if 'groupaction' in kargs else None

        if userlist is not None:
            assert useraction is not None

        if grouplist is not None:
            assert groupaction is not None

        with self.open_hive('SAM', write) as hive:
            if userlist is not None:
                parse_sam(userlist, useraction, 'Account/Users')

            if grouplist is not None:
                parse_sam(grouplist, groupaction, 'Builtin/Aliases')
                parse_sam(grouplist, groupaction, 'Account/Aliases')

    def add_viostor(self):
        """Add the viostor driver to the critical device database and register
        the viostor service
        """

        path = r"system32\drivers\viostor.sys"
        pci = r"PCI\VEN_1AF4&DEV_1001&SUBSYS_00021AF4&REV_00\3&13c0b0c5&0&20"

        with self.open_hive('SYSTEM', write=True) as hive:

            # SYSTEM/CurrentControlSet/Control/CriticalDeviceDatabase
            control = traverse(hive, "/%s/Control" % self.current_control_set)
            cdd = safe_add_node(hive, control, 'CriticalDeviceDatabase')

            guid = "{4D36E97B-E325-11CE-BFC1-08002BE10318}"

            for subsys in '00000000', '00020000', '00021af4':
                name = "pci#ven_1af4&dev_1001&subsys_%s" % subsys

                node = safe_add_node(hive, cdd, name)

                hive.node_set_value(node, REG_SZ('ClassGUID', guid))
                hive.node_set_value(node, REG_SZ('Service', 'viostor'))

            # SYSTEM/CurrentContolSet/Services/viostor
            services = hive.root()
            for child in (self.current_control_set, 'Services'):
                services = hive.node_get_child(services, child)

            viostor = safe_add_node(hive, services, 'viostor')
            hive.node_set_value(viostor, REG_SZ('Group', 'SCSI miniport'))
            hive.node_set_value(viostor, REG_SZ('ImagePath', path))
            hive.node_set_value(viostor, REG_DWORD('ErrorControl', 1))
            hive.node_set_value(viostor, REG_DWORD('Start', 0))
            hive.node_set_value(viostor, REG_DWORD('Type', 1))
            hive.node_set_value(viostor, REG_DWORD('Tag', 0x21))

            params = safe_add_node(hive, viostor, 'Parameters')
            hive.node_set_value(params, REG_DWORD('BusType', 1))

            mts = safe_add_node(hive, params, 'MaxTransferSize')
            hive.node_set_value(mts,
                                REG_SZ('ParamDesc', 'Maximum Transfer Size'))
            hive.node_set_value(mts, REG_SZ('type', 'enum'))
            hive.node_set_value(mts, REG_SZ('default', '0'))

            enum = safe_add_node(hive, mts, 'enum')
            hive.node_set_value(enum, REG_SZ('0', '64  KB'))
            hive.node_set_value(enum, REG_SZ('1', '128 KB'))
            hive.node_set_value(enum, REG_SZ('2', '256 KB'))

            pnp_interface = safe_add_node(hive, params, 'PnpInterface')
            hive.node_set_value(pnp_interface, REG_DWORD('5', 1))
            enum = safe_add_node(hive, viostor, 'Enum')
            hive.node_set_value(enum, REG_SZ('0', pci))
            hive.node_set_value(enum, REG_DWORD('Count', 1))
            hive.node_set_value(enum, REG_DWORD('NextInstance', 1))

            hive.commit(None)

    def check_viostor_service(self):
        """Checks if the viostor service is installed"""

        service = '%s/Services/viostor' % self.current_control_set

        with self.open_hive('SYSTEM', write=False) as hive:
            return traverse(hive, service) is not None

    def update_devices_dirs(self, dirname, append=True):
        """Update the value of the DevicePath registry key. If the append flag
        is True, the dirname is appended to the list of devices directories,
        otherwise the value is overwritten.

        This function returns the old value of the registry key
        """

        with self.open_hive('SOFTWARE', write=True) as hive:

            current = traverse(hive, '/Microsoft/Windows/CurrentVersion')

            device_path = hive.node_get_value(current, 'DevicePath')
            regtype, value = hive.value_value(device_path)

            assert regtype == 2L, "Type (=%d) is not REG_EXPAND_SZ" % regtype

            # Remove the trailing '\x00' character
            old_value = value.decode('utf-16le')[:-1]

            new_value = "%s;%s" % (old_value, dirname) if append else dirname

            hive.node_set_value(current,
                                REG_EXPAND_SZ('DevicePath', new_value))
            hive.commit(None)

        return old_value

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
