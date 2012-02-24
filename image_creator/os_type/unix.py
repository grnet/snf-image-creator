#!/usr/bin/env python

import re
import sys

from image_creator.os_type import OSBase


class Unix(OSBase):

    sensitive_userdata = ['.bash_history']

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

    def data_cleanup(self):
        self.cleanup_userdata()
        self.cleanup_tmp()
        self.cleanup_log()

    def cleanup_tmp(self):
        self.foreach_file('/tmp', self.g.rm_rf, maxdepth=1)

    def cleanup_log(self):
        self.foreach_file('/var/log', self.g.truncate, ftype='r')

    def cleanup_userdata(self):
        homedirs = ['/root'] + self.ls('/home/')

        for homedir in homedirs:
            for data in self.sensitive_userdata:
                fname = "%s/%s" % (homedir, data)
                if self.g.is_file(fname):
                    self.g.scrub_file(fname)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
