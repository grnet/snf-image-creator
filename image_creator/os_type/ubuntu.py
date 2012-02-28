from image_creator.os_type.linux import Linux


class Ubuntu(Linux):
    def get_metadata(self):
        meta = super(Ubuntu, self).get_metadata()
        apps = self.g.inspect_list_applications(self.root)
        for app in apps:
            if app['app_name'] == 'kubuntu-desktop':
                meta['OS'] = 'kubuntu'
                meta['description'] = \
                            meta['description'].replace('Ubuntu', 'Kubuntu')
                break
        return meta

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
