#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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

"""This module is the entrance point for the non-interactive version of the
snf-image-creator program.
"""

from image_creator import __version__ as version
from image_creator.disk import Disk
from image_creator.util import FatalError, MD5
from image_creator.output.cli import SilentOutput, SimpleOutput, \
    OutputWthProgress
from image_creator.kamaki_wrapper import Kamaki, ClientError
import sys
import os
import optparse
import StringIO
import signal
import json


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

    parser.add_option("-o", "--outfile", type="string", dest="outfile",
                      default=None, action="callback",
                      callback=check_writable_dir, help="dump image to FILE",
                      metavar="FILE")

    parser.add_option("-f", "--force", dest="force", default=False,
                      action="store_true",
                      help="overwrite output files if they exist")

    parser.add_option("-s", "--silent", dest="silent", default=False,
                      help="output only errors",
                      action="store_true")

    parser.add_option("-u", "--upload", dest="upload", type="string",
                      default=False,
                      help="upload the image to the cloud with name FILENAME",
                      metavar="FILENAME")

    parser.add_option("-r", "--register", dest="register", type="string",
                      default=False,
                      help="register the image with a cloud as IMAGENAME",
                      metavar="IMAGENAME")

    parser.add_option("-m", "--metadata", dest="metadata", default=[],
                      help="add custom KEY=VALUE metadata to the image",
                      action="append", metavar="KEY=VALUE")

    parser.add_option("-t", "--token", dest="token", type="string",
                      default=None, help="use this authentication token when "
                      "uploading/registering images")

    parser.add_option("-a", "--authentication-url", dest="url", type="string",
                      default=None, help="use this authentication URL when "
                      "uploading/registering images")

    parser.add_option("-c", "--cloud", dest="cloud", type="string",
                      default=None, help="use this saved cloud account to "
                      "authenticate against a cloud when "
                      "uploading/registering images")

    parser.add_option("--print-syspreps", dest="print_syspreps", default=False,
                      help="print the enabled and disabled system preparation "
                      "operations for this input media", action="store_true")

    parser.add_option("--enable-sysprep", dest="enabled_syspreps", default=[],
                      help="run SYSPREP operation on the input media",
                      action="append", metavar="SYSPREP")

    parser.add_option("--disable-sysprep", dest="disabled_syspreps",
                      help="prevent SYSPREP operation from running on the "
                      "input media", default=[], action="append",
                      metavar="SYSPREP")

    parser.add_option("--print-sysprep-params", dest="print_sysprep_params",
                      default=False, help="print the needed sysprep parameters"
                      " for this input media", action="store_true")

    parser.add_option("--sysprep-param", dest="sysprep_params", default=[],
                      help="Add KEY=VALUE system preparation parameter",
                      action="append")

    parser.add_option("--no-sysprep", dest="sysprep", default=True,
                      help="don't perform any system preparation operation",
                      action="store_false")

    parser.add_option("--no-shrink", dest="shrink", default=True,
                      help="don't shrink any partition", action="store_false")

    parser.add_option("--public", dest="public", default=False,
                      help="register image with the cloud as public",
                      action="store_true")

    parser.add_option("--tmpdir", dest="tmp", type="string", default=None,
                      help="create large temporary image files under DIR",
                      metavar="DIR")

    options, args = parser.parse_args(input_args)

    if len(args) != 1:
        parser.error('Wrong number of arguments')

    options.source = args[0]
    if not os.path.exists(options.source):
        raise FatalError("Input media `%s' is not accessible" % options.source)

    if options.register and not options.upload:
        raise FatalError("You also need to set -u when -r option is set")

    if options.upload and (options.token is None or options.url is None) and \
            options.cloud is None:

        err = "You need to either specify an authentication URL and token " \
              "pair or an available cloud name."

        raise FatalError("Image uploading cannot be performed. %s" % err)

    if options.tmp is not None and not os.path.isdir(options.tmp):
        raise FatalError("The directory `%s' specified with --tmpdir is not "
                         "valid" % options.tmp)

    meta = {}
    for m in options.metadata:
        try:
            key, value = m.split('=', 1)
        except ValueError:
            raise FatalError("Metadata option: `%s' is not in KEY=VALUE "
                             "format." % m)
        meta[key] = value
    options.metadata = meta

    sysprep_params = {}
    for p in options.sysprep_params:
        try:
            key, value = p.split('=', 1)
        except ValueError:
            raise FatalError("Sysprep parameter optiont: `%s' is not in "
                             "KEY=VALUE format." % p)
        sysprep_params[key] = value
    options.sysprep_params = sysprep_params

    return options


def image_creator():
    options = parse_options(sys.argv[1:])

    if options.outfile is None and not options.upload and not \
            options.print_syspreps and not options.print_sysprep_params:
        raise FatalError("At least one of `-o', `-u', `--print-syspreps' or "
                         "`--print-sysprep-params' must be set")

    if options.silent:
        out = SilentOutput()
    else:
        out = OutputWthProgress(True) if sys.stderr.isatty() else \
            SimpleOutput(False)

    title = 'snf-image-creator %s' % version
    out.output(title)
    out.output('=' * len(title))

    if os.geteuid() != 0:
        raise FatalError("You must run %s as root"
                         % os.path.basename(sys.argv[0]))

    if not options.force and options.outfile is not None:
        for extension in ('', '.meta', '.md5sum'):
            filename = "%s%s" % (options.outfile, extension)
            if os.path.exists(filename):
                raise FatalError("Output file `%s' exists "
                                 "(use --force to overwrite it)." % filename)

    # Check if the authentication info is valid. The earlier the better
    if options.token is not None and options.url is not None:
        try:
            account = Kamaki.create_account(options.url, options.token)
            if account is None:
                raise FatalError("The authentication token and/or URL you "
                                 "provided is not valid!")
            else:
                kamaki = Kamaki(account, out)
        except ClientError as e:
            raise FatalError("Astakos client: %d %s" % (e.status, e.message))
    elif options.cloud:
        avail_clouds = Kamaki.get_clouds()
        if options.cloud not in avail_clouds.keys():
            raise FatalError(
                "Cloud: `%s' does not exist.\n\nAvailable clouds:\n\n\t%s\n"
                % (options.cloud, "\n\t".join(avail_clouds.keys())))
        try:
            account = Kamaki.get_account(options.cloud)
            if account is None:
                raise FatalError(
                    "Cloud: `$s' exists but is not valid!" % options.cloud)
            else:
                kamaki = Kamaki(account, out)
        except ClientError as e:
            raise FatalError("Astakos client: %d %s" % (e.status, e.message))

    if options.upload and not options.force:
        if kamaki.object_exists(options.upload):
            raise FatalError("Remote storage service object: `%s' exists "
                             "(use --force to overwrite it)." % options.upload)
        if kamaki.object_exists("%s.md5sum" % options.upload):
            raise FatalError("Remote storage service object: `%s.md5sum' "
                             "exists (use --force to overwrite it)." %
                             options.upload)

    if options.register and not options.force:
        if kamaki.object_exists("%s.meta" % options.upload):
            raise FatalError("Remote storage service object `%s.meta' exists "
                             "(use --force to overwrite it)." % options.upload)

    disk = Disk(options.source, out, options.tmp)

    def signal_handler(signum, frame):
        disk.cleanup()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        snapshot = disk.snapshot()

        image = disk.get_image(snapshot, sysprep_params=options.sysprep_params)

        for sysprep in options.disabled_syspreps:
            image.os.disable_sysprep(image.os.get_sysprep_by_name(sysprep))

        for sysprep in options.enabled_syspreps:
            image.os.enable_sysprep(image.os.get_sysprep_by_name(sysprep))

        if options.print_syspreps:
            image.os.print_syspreps()
            out.output()

        if options.print_sysprep_params:
            image.os.print_sysprep_params()
            out.output()

        if options.outfile is None and not options.upload:
            return 0

        if options.sysprep:
            image.os.do_sysprep()

        metadata = image.os.meta

        size = options.shrink and image.shrink() or image.size
        metadata.update(image.meta)

        # Add command line metadata to the collected ones...
        metadata.update(options.metadata)

        md5 = MD5(out)
        checksum = md5.compute(image.device, size)

        metastring = unicode(json.dumps(
            {'properties': metadata,
             'disk-format': 'diskdump'}, ensure_ascii=False))

        if options.outfile is not None:
            image.dump(options.outfile)

            out.output('Dumping metadata file ...', False)
            with open('%s.%s' % (options.outfile, 'meta'), 'w') as f:
                f.write(metastring)
            out.success('done')

            out.output('Dumping md5sum file ...', False)
            with open('%s.%s' % (options.outfile, 'md5sum'), 'w') as f:
                f.write('%s %s\n' % (checksum,
                                     os.path.basename(options.outfile)))
            out.success('done')

        # Destroy the image instance. We only need the snapshot from now on
        disk.destroy_image(image)

        out.output()
        try:
            uploaded_obj = ""
            if options.upload:
                out.output("Uploading image to the storage service:")
                with open(snapshot, 'rb') as f:
                    uploaded_obj = kamaki.upload(
                        f, size, options.upload,
                        "(1/3)  Calculating block hashes",
                        "(2/3)  Uploading missing blocks")
                out.output("(3/3)  Uploading md5sum file ...", False)
                md5sumstr = '%s %s\n' % (checksum,
                                         os.path.basename(options.upload))
                kamaki.upload(StringIO.StringIO(md5sumstr),
                              size=len(md5sumstr),
                              remote_path="%s.%s" % (options.upload, 'md5sum'))
                out.success('done')
                out.output()

            if options.register:
                img_type = 'public' if options.public else 'private'
                out.output('Registering %s image with the compute service ...'
                           % img_type, False)
                result = kamaki.register(options.register, uploaded_obj,
                                         metadata, options.public)
                out.success('done')
                out.output("Uploading metadata file ...", False)
                metastring = unicode(json.dumps(result, ensure_ascii=False))
                kamaki.upload(StringIO.StringIO(metastring),
                              size=len(metastring),
                              remote_path="%s.%s" % (options.upload, 'meta'))
                out.success('done')
                if options.public:
                    out.output("Sharing md5sum file ...", False)
                    kamaki.share("%s.md5sum" % options.upload)
                    out.success('done')
                    out.output("Sharing metadata file ...", False)
                    kamaki.share("%s.meta" % options.upload)
                    out.success('done')

                out.output()
        except ClientError as e:
            raise FatalError("Service client: %d %s" % (e.status, e.message))

    finally:
        out.output('cleaning up ...')
        disk.cleanup()

    out.success("snf-image-creator exited without errors")

    return 0


def main():
    try:
        ret = image_creator()
        sys.exit(ret)
    except FatalError as e:
        colored = sys.stderr.isatty()
        SimpleOutput(colored).error(e)
        sys.exit(1)

if __name__ == '__main__':
    main()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
