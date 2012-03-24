#!/usr/bin/env python

# Copyright 2011 GRNET S.A. All rights reserved.
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

from image_creator import get_os_class
from image_creator import __version__ as version
from image_creator import FatalError
from image_creator.disk import Disk
from image_creator.util import get_command, error, progress_generator, success
from clint.textui import puts

import sys
import os
import optparse

dd = get_command('dd')


def check_writable_dir(option, opt_str, value, parser):
    dirname = os.path.dirname(value)
    name = os.path.basename(value)
    if dirname and not os.path.isdir(dirname):
        parser.error("`%s' is not an existing directory" % dirname)

    if not name:
        parser.error("`%s' is not a valid file name" % dirname)

    setattr(parser.values, option.dest, value)


def parse_options(input_args):
    usage = "Usage: %prog [options] <input_media>"
    parser = optparse.OptionParser(version=version, usage=usage)

    parser.add_option("-f", "--force", dest="force", default=False,
        action="store_true", help="overwrite output files if they exist")

    parser.add_option("--no-cleanup", dest="cleanup", default=True,
        help="don't cleanup sensitive data",
        action="store_false")

    parser.add_option("--no-sysprep", dest="sysprep", default=True,
        help="don't perform system preperation",
        action="store_false")

    parser.add_option("--no-shrink", dest="shrink", default=True,
        help="don't shrink any partition",
        action="store_false")

    parser.add_option("-o", "--outfile", type="string", dest="outfile",
        default=None, action="callback", callback=check_writable_dir,
        help="dump image to FILE",
        metavar="FILE")

    parser.add_option("-u", "--upload", dest="upload", default=False,
        help="upload the image to pithos",
        action="store_true")

    parser.add_option("-r", "--register", dest="register", default=False,
        help="register the image to ~okeanos", action="store_true")

    options, args = parser.parse_args(input_args)

    if len(args) != 1:
        parser.error('Wrong number of arguments')
    options.source = args[0]
    if not os.path.exists(options.source):
        parser.error('input media is not accessible')

    if options.register:
        options.upload = True

    if options.outfile is None and not options.upload:
        parser.error('either outfile (-o) or upload (-u) must be set.')

    return options


def image_creator():
    puts('snf-image-creator %s\n' % version)
    options = parse_options(sys.argv[1:])

    if os.geteuid() != 0:
        raise FatalError("You must run %s as root" \
                        % os.path.basename(sys.argv[0]))

    if not options.force and options.outfile is not None:
        for extension in ('', '.meta'):
            filename = "%s%s" % (options.outfile, extension)
            if os.path.exists(filename):
                raise FatalError("Output file %s exists "
                    "(use --force to overwrite it)." % filename)

    disk = Disk(options.source)
    try:
        dev = disk.get_device()
        dev.mount()

        osclass = get_os_class(dev.distro, dev.ostype)
        image_os = osclass(dev.root, dev.g)
        metadata = image_os.get_metadata()

        puts()

        if options.sysprep:
            image_os.sysprep()

        if options.cleanup:
            image_os.data_cleanup()

        dev.umount()

        size = options.shrink and dev.shrink() or dev.size()
        metadata['SIZE'] = str(size // 2 ** 20)

        if options.outfile is not None:
            f = open('%s.%s' % (options.outfile, 'meta'), 'w')
            try:
                for key in metadata.keys():
                    f.write("%s=%s\n" % (key, metadata[key]))
            finally:
                f.close()

            dev.dump(options.outfile)
    finally:
        puts('cleaning up...')
        disk.cleanup()

    return 0


def main():
    try:
        ret = image_creator()
        sys.exit(ret)
    except FatalError as e:
        error(e)
        sys.exit(1)


if __name__ == '__main__':
    main()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
