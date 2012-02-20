#!/usr/bin/env python

import re

from image_creator.os_type import OSBase

class Unix(OSBase):
    def get_metadata(self):
        meta = super(Unix, self).get_metadata()
        meta["USERS"] = " ".join(self.get_passworded_users())
        return meta

    def get_passworded_users(self):
        
        users = []

        regexp = re.compile('(\S+):((?:!\S+)|(?:[^!*]\S+)|):(?:\S*:){6}')

        for line in open('/etc/shadow', 'r').readlines():
            match = regexp.match(line)
            if not match:
                continue

            user, passwd = match.groups()
            if len(passwd) > 0 and passwd[0] == '!':
                print "Warning: %s is locked" % user
            else:
                users.append(user)

        return users

    def cleanup_sensitive_data(self):
        cleanup_userdata()
        cleanup_tmp()
        cleanup_log()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
