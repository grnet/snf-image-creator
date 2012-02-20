#!/usr/bin/env python

class OSBase(object):
    def __init__(self, rootdev, ghandler):
        self.root = rootdev
        self.g = ghandler

    def get_metadata(self):
        meta = {}
        meta["OSFAMILY"] = self.g.inspect_get_type(self.root)
        meta["OS"] = self.g.inspect_get_distro(self.root)
        meta["description"] = self.g.inspect_get_product_name(self.root)

        return meta

    def mount_all(self):
        mps = g.inspect_get_mountpoints(self.root)
        # Sort the keys to mount the fs in a correct order.
        # / should be mounted befor /boot, etc
        def compare (a, b):
            if len(a[0]) > len(b[0]): return 1
            elif len(a[0]) == len(b[0]): return 0
            else: return -1
        mps.sort(compare)
        for mp, dev in mps:
            try:
                self.g.mount(dev, mp)
            except RuntimeError as msg:
                print "%s (ignored)" % msg

    def cleanup_sensitive_data(self):
        raise NotImplementedError

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
