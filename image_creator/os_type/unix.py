#!/usr/bin/env python

import re
import sys

from image_creator.os_type import OSBase


class Unix(OSBase):

    sensitive_userdata = [
        '.bash_history',
        '.gnupg',
        '.ssh',
        '.mozilla',
        '.thunderbird'
    ]

    def get_metadata(self):
        meta = super(Unix, self).get_metadata()
        meta["USERS"] = " ".join(self.get_passworded_users())
        return meta

    def get_passworded_users(self):
        users = []
        regexp = re.compile('(\S+):((?:!\S+)|(?:[^!*]\S+)|):(?:\S*:){6}')

        for line in self.g.cat('/etc/shadow').splitlines():
            match = regexp.match(line)
            if not match:
                continue

            user, passwd = match.groups()
            if len(passwd) > 0 and passwd[0] == '!':
                print "Warning: Ignoring locked %s account." % user
            else:
                users.append(user)

        return users

    def data_cleanup(self):
        self.data_cleanup_userdata()
        self.data_cleanup_tmp()
        self.data_cleanup_log()
        self.data_cleanup_mail()
        self.data_cleanup_cache()

    def data_cleanup_cache(self):
        """Remove all regular files under /var/cache"""
        self.foreach_file('/var/cache', self.g.rm, ftype='r')

    def data_cleanup_tmp(self):
        """Remove all files under /tmp and /var/tmp"""
        self.foreach_file('/tmp', self.g.rm_rf, maxdepth=1)
        self.foreach_file('/var/tmp', self.g.rm_rf, maxdepth=1)

    def data_cleanup_log(self):
        """Empty all files under /var/log"""
        self.foreach_file('/var/log', self.g.truncate, ftype='r')

    def data_cleanup_mail(self):
        """Remove all files under /var/mail and /var/spool/mail"""
        self.foreach_file('/var/spool/mail', self.g.rm_rf, maxdepth=1)
        self.foreach_file('/var/mail', self.g.rm_rf, maxdepth=1)

    def data_cleanup_userdata(self):
        """Delete sensitive userdata"""
        homedirs = ['/root'] + self.ls('/home/')

        for homedir in homedirs:
            for data in self.sensitive_userdata:
                fname = "%s/%s" % (homedir, data)
                if self.g.is_file(fname):
                    self.g.scrub_file(fname)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
