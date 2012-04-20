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

import sys
import pbs
import hashlib
from clint.textui import colored, progress as uiprogress


class FatalError(Exception):
    pass


silent = False


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
    nl = "\n" if new_line else ''
    sys.stderr.write(colored.red('Error: %s' % msg) + nl)


def warn(msg, new_line=True):
    if not silent:
        nl = "\n" if new_line else ''
        sys.stderr.write(colored.yellow("Warning: %s" % msg) + nl)


def success(msg, new_line=True):
    if not silent:
        nl = "\n" if new_line else ''
        sys.stdout.write(colored.green(msg) + nl)
        if not nl:
            sys.stdout.flush()


def output(msg="", new_line=True):
    if not silent:
        nl = "\n" if new_line else ''
        sys.stdout.write(msg + nl)
        if not nl:
            sys.stdout.flush()


def progress(message=''):

    PROGRESS_LENGTH = 32
    MESSAGE_LENGTH = 32

    def progress_generator(n=100):
        position = 0
        msg = message.ljust(MESSAGE_LENGTH)
        for i in uiprogress.bar(range(n), msg, PROGRESS_LENGTH, silent):
            if i < position:
                continue
            position = yield
        yield  # suppress the StopIteration exception
    return progress_generator


def md5(filename, size, progress=None):

    BLOCKSIZE = 2 ^ 22  # 4MB

    md5 = hashlib.md5()
    with open(filename, "r") as src:
        left = size
        while left > 0:
            length = min(left, BLOCKSIZE)
            data = src.read(length)
            md5.update(data)
            left -= length

    return md5.hexdigest()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
