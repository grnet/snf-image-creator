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
from image_creator.disk import Disk
import sys
import os
import optparse
from pbs import dd


class FatalError(Exception):
    pass


def check_writable_dir(option, opt_str, value, parser):
    if not os.path.isdir(value):
        raise OptionValueError("%s is not a valid directory name" % value)
    setattr(parser.values, option.dest, value)


def parse_options(input_args):
    usage = "Usage: %prog [options] <input_media> <name>"
    parser = optparse.OptionParser(version=version, usage=usage)

    parser.add_option("-o", "--outdir", type="string", dest="outdir",
        default=".", action="callback", callback=check_writable_dir,
        help="Output files to DIR [default: working dir]",
        metavar="DIR")

    parser.add_option("-f", "--force", dest="force", default=False,
        action="store_true", help="Overwrite output files if they exist")

    parser.add_option("--no-shrink", dest="shrink", default=True,
        help="Don't shrink any partition before extracting the image",
        action="store_false")

    options, args = parser.parse_args(input_args)

    if len(args) != 2:
        parser.error('input media or name are missing')
    options.source = args[0]
    options.name = args[1]

    if not os.path.exists(options.source):
        parser.error('Input media is not accessible')

    return options


def main():

    options = parse_options(sys.argv[1:])

    if os.geteuid() != 0:
        raise FatalError("You must run %s as root" \
                        % os.path.basename(sys.argv[0]))

    if not options.force:
        for ext in ('diskdump', 'meta'):
            filename = "%s/%s.%s" % (options.outdir, options.name, ext)
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
        image_os.data_cleanup()
        dev.umount()
        size = options.shrink and dev.shrink() or dev.size()
        metadata['size'] = str(size // 2 ** 20)

        dd('if=%s' % dev.device,
            'of=%s/%s.%s' % (options.outdir, options.name, 'diskdump'),
            'bs=4M', 'count=%d' % ((size + 1) // 2 ** 22))

        f = open('%s/%s.%s' % (options.outdir, options.name, 'meta'), 'w')
        for key in metadata.keys():
            f.write("%s=%s\n" % (key, metadata[key]))
        f.close()
    finally:
        disk.cleanup()

    return 0

COLOR_BLACK = "\033[00m"
COLOR_RED = "\033[1;31m"

if __name__ == '__main__':
    try:
        ret = main()
        sys.exit(ret)
    except FatalError as e:
        print >> sys.stderr, "\n%sError: %s%s\n" % (COLOR_RED, e, COLOR_BLACK)
        sys.exit(1)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
