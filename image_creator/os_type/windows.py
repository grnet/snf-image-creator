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
from image_creator.util import FatalError, check_guestfs_version

import hivex
import tempfile
import os


class Windows(OSBase):
    """OS class for Windows"""

    @sysprep(enabled=False)
    def remove_user_accounts(self, print_header=True):
        """Remove all user accounts with id greater than 1000"""
        pass
 
    def do_sysprep(self):
        """Prepare system for image creation."""

        if getattr(self, 'syspreped', False):
            raise FatalError("Image is already syspreped!")

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

        self.out.output("Starting windows VM ...", False)
        try:
            pass
        finally:
            self.out.output("Relaunching helper VM (may take a while) ...",
                            False)
            self.g.launch()
            self.out.success('done')

        if disabled_uac:
            self._update_uac_remote_setting(0)

        self.syspreped = True

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

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
