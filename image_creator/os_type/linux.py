from image_creator.os_type.unix import Unix
import re


class Linux(Unix):
    def __init__(self, rootdev, ghandler):
        super(Linux, self).__init__(rootdev, ghandler)
        self._uuid = dict()
        self._persistent = re.compile('/dev/[hsv]d[a-z][1-9]*')

    def is_persistent(self, dev):
        return not self._persistent.match(dev)

    def get_uuid(self, dev):
        if dev in self._uuid:
            return self._uuid[dev]

        for attr in self.g.blkid(dev):
            if attr[0] == 'UUID':
                self._uuid[dev] = attr[1]
                return attr[1]

    def remove_persistent_net(self):
        persistent_net_rule = '/etc/udev/rules.d/70-persistent-net.rules'
        if self.g.is_file(persistent_net_rule):
            self.g.rm(persistent_net_rule)

    def convert_to_persistent_dev(self):
        # convert all devices in fstab to persistent
        persistent_root = self._persistent_fstab()

        # convert all devices in grub1 to persistent
        self._persistent_grub1(persistent_root)

    def _persistent_grub1(self, conf, new_root):
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
            print "Warning: detected abnorman entry in fstab"
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
