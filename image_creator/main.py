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

from image_creator import __version__ as version
from image_creator import util
from image_creator.disk import Disk
from image_creator.util import get_command, error, success, output, \
                                                    FatalError, progress, md5
from image_creator.os_type import get_os_class
from image_creator.kamaki_wrapper import Kamaki
import sys
import os
import optparse
import StringIO


def check_writable_dir(option, opt_str, value, parser):
    dirname = os.path.dirname(value)
    name = os.path.basename(value)
    if dirname and not os.path.isdir(dirname):
        raise FatalError("`%s' is not an existing directory" % dirname)

    if not name:
        raise FatalError("`%s' is not a valid file name" % dirname)

    setattr(parser.values, option.dest, value)


def parse_options(input_args):
    usage = "Usage: %prog [options] <input_media>"
    parser = optparse.OptionParser(version=version, usage=usage)

    account = os.environ["OKEANOS_USER"] if "OKEANOS_USER" in os.environ \
        else None
    token = os.environ["OKEANOS_TOKEN"] if "OKEANOS_TOKEN" in os.environ \
        else None

    parser.add_option("-o", "--outfile", type="string", dest="outfile",
        default=None, action="callback", callback=check_writable_dir,
        help="dump image to FILE", metavar="FILE")

    parser.add_option("-f", "--force", dest="force", default=False,
        action="store_true", help="overwrite output files if they exist")

    parser.add_option("-s", "--silent", dest="silent", default=False,
        help="silent mode, only output errors", action="store_true")

    parser.add_option("-u", "--upload", dest="upload", type="string",
        default=False, help="upload the image to pithos with name FILENAME",
        metavar="FILENAME")

    parser.add_option("-r", "--register", dest="register", type="string",
        default=False, help="register the image to ~okeanos as IMAGENAME",
        metavar="IMAGENAME")

    parser.add_option("-a", "--account", dest="account", type="string",
        default=account,
        help="Use this ACCOUNT when uploading/registring images [Default: %s]"\
        % account)

    parser.add_option("-t", "--token", dest="token", type="string",
        default=token,
        help="Use this token when uploading/registring images [Default: %s]"\
        % token)

    parser.add_option("--print-sysprep", dest="print_sysprep", default=False,
        help="print the enabled and disabled system preparation operations "
        "for this input media", action="store_true")

    parser.add_option("--enable-sysprep", dest="enabled_syspreps", default=[],
        help="run SYSPREP operation on the input media",
        action="append", metavar="SYSPREP")

    parser.add_option("--disable-sysprep", dest="disabled_syspreps",
        help="prevent SYSPREP operation from running on the input media",
        default=[], action="append", metavar="SYSPREP")

    parser.add_option("--no-sysprep", dest="sysprep", default=True,
        help="don't perform system preperation", action="store_false")

    parser.add_option("--no-shrink", dest="shrink", default=True,
        help="don't shrink any partition", action="store_false")

    options, args = parser.parse_args(input_args)

    if len(args) != 1:
        parser.error('Wrong number of arguments')
    options.source = args[0]
    if not os.path.exists(options.source):
        raise FatalError("Input media `%s' is not accessible" % options.source)

    if options.register and options.upload == False:
        raise FatalError("You also need to set -u when -r option is set")

    if options.upload and options.account is None:
        raise FatalError("Image uploading cannot be performed. No ~okeanos "
        "account name is specified. Use -a to set an account name.")

    if options.upload and options.token is None:
        raise FatalError("Image uploading cannot be performed. No ~okeanos "
        "token is specified. User -t to set a token.")

    return options


def image_creator():
    options = parse_options(sys.argv[1:])

    if options.silent:
        util.silent = True

    if options.outfile is None and not options.upload \
                                            and not options.print_sysprep:
        raise FatalError("At least one of `-o', `-u' or `--print-sysprep' " \
                                                                "must be set")

    title = 'snf-image-creator %s' % version
    output(title)
    output('=' * len(title))

    if os.geteuid() != 0:
        raise FatalError("You must run %s as root" \
                        % os.path.basename(sys.argv[0]))

    if not options.force and options.outfile is not None:
        for extension in ('', '.meta', '.md5sum'):
            filename = "%s%s" % (options.outfile, extension)
            if os.path.exists(filename):
                raise FatalError("Output file %s exists "
                    "(use --force to overwrite it)." % filename)

    disk = Disk(options.source)
    try:
        snapshot = disk.snapshot()

        dev = disk.get_device(snapshot)
        dev.mount()

        osclass = get_os_class(dev.distro, dev.ostype)
        image_os = osclass(dev.root, dev.g)
        metadata = image_os.get_metadata()
        output()

        for sysprep in options.disabled_syspreps:
            image_os.disable_sysprep(sysprep)

        for sysprep in options.enabled_syspreps:
            image_os.enable_sysprep(sysprep)

        if options.print_sysprep:
            image_os.print_syspreps()
            output()

        if options.outfile is None and not options.upload:
            return 0

        if options.sysprep:
            image_os.do_sysprep()

        dev.umount()

        size = options.shrink and dev.shrink() or dev.size
        metadata.update(dev.meta)

        checksum = md5(snapshot, size)

        metastring = '\n'.join(
                ['%s=%s' % (key, value) for (key, value) in metadata.items()])
        metastring += '\n'

        if options.outfile is not None:
            dev.dump(options.outfile)

            output('Dumping metadata file...', False)
            with open('%s.%s' % (options.outfile, 'meta'), 'w') as f:
                f.write(metastring)
            success('done')

            output('Dumping md5sum file...', False)
            with open('%s.%s' % (options.outfile, 'md5sum'), 'w') as f:
                f.write('%s %s\n' % (checksum, \
                                            os.path.basename(options.outfile)))
            success('done')

        # Destroy the device. We only need the snapshot from now on
        disk.destroy_device(dev)

        output()

        uploaded_obj = ""
        if options.upload:
            output("Uploading image to pithos:")
            kamaki = Kamaki(options.account, options.token)
            with open(snapshot) as f:
                uploaded_obj = kamaki.upload(f, size, options.upload,
                                "(1/4)  Calculating block hashes",
                                "(2/4)  Uploading missing blocks")

            output("(3/4)  Uploading metadata file...", False)
            kamaki.upload(StringIO.StringIO(metastring), size=len(metastring),
                                remote_path="%s.%s" % (options.upload, 'meta'))
            success('done')
            output("(4/4)  Uploading md5sum file...", False)
            md5sumstr = '%s %s\n' % (
                checksum, os.path.basename(options.upload))
            kamaki.upload(StringIO.StringIO(md5sumstr), size=len(md5sumstr),
                            remote_path="%s.%s" % (options.upload, 'md5sum'))
            success('done')
            output()

        if options.register:
            output('Registring image to ~okeanos...', False)
            kamaki.register(options.register, uploaded_obj, metadata)
            success('done')
            output()

    finally:
        output('cleaning up...')
        disk.cleanup()

    success("snf-image-creator exited without errors")

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
