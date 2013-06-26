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

from image_creator.os_type import OSBase

import hivex
import tempfile
import os


class Windows(OSBase):
    """OS class for Windows"""

    def _do_collect_metadata(self):
        """Collect metadata about the OS"""
        super(Windows, self)._do_collect_metadata()
        self.meta["USERS"] = " ".join(self._get_users())

    def _get_users(self):
        """Returns a list of users found in the images"""
        samfd, sam = tempfile.mkstemp()
        try:
            systemroot = self.g.inspect_get_windows_systemroot(self.root)
            path = "%s/system32/config/sam" % systemroot
            path = self.g.case_sensitive_path(path)
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
