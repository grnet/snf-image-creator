#!/usr/bin/env python

import re


def add_prefix(target):
    def wrapper(self, *args):
        prefix = args[0]
        return map(lambda x: prefix + x, target(self, *args))
    return wrapper


class OSBase(object):
    def __init__(self, rootdev, ghandler):
        self.root = rootdev
        self.g = ghandler

    @add_prefix
    def ls(self, directory):
        return self.g.ls(directory)

    @add_prefix
    def find(self, directory):
        return self.g.find(directory)

    def foreach_file(self, directory, action, **kargs):

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
        meta = {}
        meta["OSFAMILY"] = self.g.inspect_get_type(self.root)
        meta["OS"] = self.g.inspect_get_distro(self.root)
        meta["description"] = self.g.inspect_get_product_name(self.root)

        return meta

    def data_cleanup(self):
        raise NotImplementedError

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
