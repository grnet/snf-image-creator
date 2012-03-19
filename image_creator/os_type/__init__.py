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

import re


def add_prefix(target):
    def wrapper(self, *args):
        prefix = args[0]
        return map(lambda x: prefix + x, target(self, *args))
    return wrapper


class OSBase(object):
    """Basic operating system class"""
    def __init__(self, rootdev, ghandler):
        self.root = rootdev
        self.g = ghandler

    @add_prefix
    def ls(self, directory):
        """List the name of all files under a directory"""
        return self.g.ls(directory)

    @add_prefix
    def find(self, directory):
        """List the name of all files recursively under a directory"""
        return self.g.find(directory)

    def foreach_file(self, directory, action, **kargs):
        """Perform an action recursively on all files under a directory.

        The following options are allowed:

        * maxdepth: If defined the action will not be performed on
          files that are below this level of directories under the
          directory parameter.

        * ftype: The action will only be performed on files of this
          type. For a list of all allowed filetypes, see here:
          http://libguestfs.org/guestfs.3.html#guestfs_readdir

        * exclude: Exclude all files that follow this pattern.
        """
        maxdepth = None if 'maxdepth' not in kargs else kargs['maxdepth']
        if maxdepth == 0:
            return

        # maxdepth -= 1
        maxdepth = None if maxdepth is None else maxdepth - 1
        kargs['maxdepth'] = maxdepth

        exclude = None if 'exclude' not in kargs else kargs['exclude']
        ftype = None if 'ftype' not in kargs else kargs['ftype']
        has_ftype = lambda x, y: y is None and True or x['ftyp'] == y

        for f in self.g.readdir(directory):
            if f['name'] in ('.', '..'):
                continue

            full_path = "%s/%s" % (directory, f['name'])

            if exclude and re.match(exclude, full_path):
                continue

            if has_ftype(f, 'd'):
                self.foreach_file(full_path, action, **kargs)

            if has_ftype(f, ftype):
                action(full_path)

    def get_metadata(self):
        """Returns some descriptive metadata about the OS."""
        meta = {}
        meta['ROOT_PARTITION'] = "%d" % self.g.part_to_partnum(self.root)
        meta['OSFAMILY'] = self.g.inspect_get_type(self.root)
        meta['OS'] = self.g.inspect_get_distro(self.root)
        meta['description'] = self.g.inspect_get_product_name(self.root)

        return meta

    def data_cleanup(self):
        """Cleanup sensitive data out of the OS image."""
        raise NotImplementedError

    def sysprep(self):
        """Prepere system for image creation."""
        raise NotImplementedError

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
