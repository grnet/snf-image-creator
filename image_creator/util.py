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

import pbs
from clint.textui import puts, puts_err, colored, progress


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


def error(msg, new_line=True):
    puts_err(colored.red("Error: %s\n" % msg), new_line)


def warn(msg, new_line=True):
    puts_err(colored.yellow("Warning: %s" % msg), new_line)


def success(msg, new_line=True):
    puts(colored.green(msg), new_line)


def progress_generator(label='', n=100):
    position = 0
    for i in progress.bar(range(n), label):
        if i < position:
            continue
        position = yield
    yield  # suppress the StopIteration exception

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
