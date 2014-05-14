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

# http://technet.microsoft.com/en-us/library/hh824815.aspx
WINDOWS_SETUP_STATES = (
    "IMAGE_STATE_COMPLETE",
    "IMAGE_STATE_UNDEPLOYABLE",
    "IMAGE_STATE_GENERALIZE_RESEAL_TO_OOBE",
    "IMAGE_STATE_GENERALIZE_RESEAL_TO_AUDIT",
    "IMAGE_STATE_SPECIALIZE_RESEAL_TO_OOBE",
    "IMAGE_STATE_SPECIALIZE_RESEAL_TO_AUDIT")


class Registry(object):
    """Windows Registry manipulation methods"""

    def __init__(self, guestfs_handler, root_partition):
        self.g = guestfs_handler
        self.root = root_partition

    def open_hive(self, hive, write=False):
        """Returns a context manager for opening a hive file of the image for
        reading or writing.
        """
        systemroot = self.g.inspect_get_windows_systemroot(self.root)
        path = "%s/system32/config/%s" % (systemroot, hive)
        try:
            path = self.g.case_sensitive_path(path)
        except RuntimeError as err:
            raise FatalError("Unable to retrieve file: %s. Reason: %s" %
                             (hive, str(err)))

        g = self.g  # OpenHive class needs this since 'self' gets overwritten

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
                assert type(desc) is str and type(cmd) is str
                value = {'key': desc, 't': 1, 'value': cmd.encode('utf-16le')}
                hive.node_set_value(runonce, value)

            hive.commit(None)

    def enable_autologon(self, username, password="", autoadminlogon=True):
        """Enable automatic logon for a specific user"""

        assert type(username) is str and type(password) is str

        with self.open_hive('SOFTWARE', write=True) as hive:

            winlogon = hive.root()
            for child in ('Microsoft', 'Windows NT', 'CurrentVersion',
                          'Winlogon'):
                winlogon = hive.node_get_child(winlogon, child)

            hive.node_set_value(winlogon,
                                {'key': 'DefaultUserName', 't': 1,
                                 'value': username.encode('utf-16le')})
            hive.node_set_value(winlogon,
                                {'key': 'DefaultPassword', 't': 1,
                                 'value':  password.encode('utf-16le')})
            hive.node_set_value(
                winlogon,
                {'key': 'AutoAdminLogon', 't': 1,
                 'value': ("%d" % int(autoadminlogon)).encode('utf-16le')})

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

    def enum_users(self):
        """Returns a list of users found on the system and a second list of
        active users.
        """

        users = []
        active = []

        # Under HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\%RID% there is
        # an F field that contains information about this user account. Bytes
        # 56 & 57 are the account type and status flags. The first bit is the
        # 'account disabled' bit:
        #
        # http://www.beginningtoseethelight.org/ntsecurity/index.htm
        #        #8603CF0AFBB170DD
        #
        disabled = lambda f: int(f[56].encode('hex'), 16) & 0x01

        def collect_users(hive, username, rid_node):

            f_val = hive.value_value(hive.node_get_value(rid_node, 'F'))[1]

            if not disabled(f_val):
                active.append(username)

            users.append(username)

        self._foreach_user([], collect_users)

        return (users, active)

    def reset_passwd(self, user, v_field=None):
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
                new = ("\x00" * 4).join(struct.unpack(fmt,  v_val))

            hive.node_set_value(rid_node, {'key': "V", 't': 3L, 'value': new})
            hive.commit(None)
            parent['old'] = v_val

        self._foreach_user([user], update_v_field, write=True)

        assert 'old' in parent, "user: `%s' does not exist" % user
        return parent['old']

    def _foreach_user(self, userlist, action, write=False):
        """Performs an action on the RID node of a user in the registry, for
        every user found in the userlist. If userlist is empty, it performs the
        action on all users. The write flag determines if the registry is
        opened for reading or writing.
        """

        with self.open_hive('SAM', write) as hive:
            # Navigate to /SAM/Domains/Account/Users
            users_node = hive.root()
            for child in ('SAM', 'Domains', 'Account', 'Users'):
                users_node = hive.node_get_child(users_node, child)

            # Navigate to /SAM/Domains/Account/Users/Names
            names_node = hive.node_get_child(users_node, 'Names')

            # HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\%RID%
            # HKEY_LOCAL_MACHINE\SAM\SAM\Domains\Account\Users\Names\%Username%
            #
            # The RID (relative identifier) of each user is stored as the
            # type!!!! (not the value) of the default key of the node under
            # Names whose name is the user's username.
            for user_node in hive.node_children(names_node):

                username = hive.node_name(user_node)

                if len(userlist) != 0 and username not in userlist:
                    continue

                rid = hive.value_type(hive.node_get_value(user_node, ""))[0]
                # if RID is 500 (=0x1f4), the corresponding node name under
                # Users is '000001F4'
                key = ("%8.x" % rid).replace(' ', '0').upper()
                rid_node = hive.node_get_child(users_node, key)

                action(hive, username, rid_node)


# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
