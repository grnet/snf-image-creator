#!/usr/bin/env python

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
