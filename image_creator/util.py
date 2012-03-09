#!/usr/bin/env python

import pbs

def get_command(command):
    def find_sbin_command(command, exception):
        search_paths = ['/usr/local/sbin', '/usr/sbin', '/sbin']
        for fullpath in map(lambda x: "%s/%s" % (x, command), search_paths):
            if os.path.exists(fullpath) and os.access(fullpath, os.X_OK):
                return pbs.Command(fullpath)
        raise exception

    try:
        return pbs.__getattr__(command)
    except pbs.CommadNotFount as e:
        return find_sbin_command(command, e)
