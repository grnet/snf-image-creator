#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2015 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This module is the entrance point for the non-interactive version of the
snf-image-creator program.
"""

from image_creator import __version__ as version
from image_creator.disk import Disk
from image_creator.util import FatalError
from image_creator.output.cli import SilentOutput, SimpleOutput, \
    OutputWthProgress
from image_creator.output.composite import CompositeOutput
from image_creator.output.syslog import SyslogOutput
from image_creator.kamaki_wrapper import Kamaki, ClientError
import sys
import os
import optparse
import StringIO
import signal
import json
import textwrap
import tempfile
import subprocess
import time


def check_writable_dir(option, opt_str, value, parser):
    """Check if a directory is writable"""
    dirname = os.path.dirname(value)
    name = os.path.basename(value)
    if dirname and not os.path.isdir(dirname):
        raise FatalError("`%s' is not an existing directory" % dirname)

    if not name:
        raise FatalError("`%s' is not a valid file name" % dirname)

    setattr(parser.values, option.dest, value)


def parse_options(input_args):
    """Parse input parameters"""
    usage = "Usage: %prog [options] <input_media>"
    parser = optparse.OptionParser(version=version, usage=usage)

    parser.add_option("-a", "--authentication-url", dest="url", type="string",
                      default=None, help="use this authentication URL when "
                      "uploading/registering images")

    parser.add_option("--allow-unsupported", dest="allow_unsupported",
                      help="proceed with the image creation even if the media "
                      "is not supported", default=False, action="store_true")

    parser.add_option("-c", "--cloud", dest="cloud", type="string",
                      default=None, help="use this saved cloud account to "
                      "authenticate against a cloud when "
                      "uploading/registering images")

    parser.add_option("--disable-sysprep", dest="disabled_syspreps",
                      help="prevent SYSPREP operation from running on the "
                      "input media", default=[], action="append",
                      metavar="SYSPREP")

    parser.add_option("--enable-sysprep", dest="enabled_syspreps", default=[],
                      help="run SYSPREP operation on the input media",
                      action="append", metavar="SYSPREP")

    parser.add_option("-f", "--force", dest="force", default=False,
                      action="store_true",
                      help="overwrite output files if they exist")

    parser.add_option("--host-run", dest="host_run", default=[],
                      help="mount the media in the host and run a script "
                      "against the guest media. This option may be defined "
                      "multiple times. The script's working directory will be "
                      "the guest's root directory. BE CAREFUL! DO NOT USE "
                      "ABSOLUTE PATHS INSIDE THE SCRIPT! YOU MAY HARM YOUR "
                      "SYSTEM!", metavar="SCRIPT", action="append")

    parser.add_option("--install-virtio", dest="virtio", type="string",
                      help="install VirtIO drivers hosted under DIR "
                      "(Windows only)", metavar="DIR")

    parser.add_option("-m", "--metadata", dest="metadata", default=[],
                      help="add custom KEY=VALUE metadata to the image",
                      action="append", metavar="KEY=VALUE")

    parser.add_option("--no-snapshot", dest="snapshot", default=True,
                      help="don't snapshot the input media. (THIS IS "
                      "DANGEROUS AS IT WILL ALTER THE ORIGINAL MEDIA!!!)",
                      action="store_false")

    parser.add_option("--no-sysprep", dest="sysprep", default=True,
                      help="don't perform any system preparation operation",
                      action="store_false")

    parser.add_option("-o", "--outfile", type="string", dest="outfile",
                      default=None, action="callback", metavar="FILE",
                      callback=check_writable_dir, help="dump image to FILE")

    parser.add_option("--print-metadata", dest="print_metadata", default=False,
                      help="print the detected image metadata",
                      action='store_true')

    parser.add_option("--print-syspreps", dest="print_syspreps", default=False,
                      help="print the enabled and disabled system preparation "
                      "operations for this input media", action="store_true")

    parser.add_option("--print-sysprep-params", dest="print_sysprep_params",
                      default=False, action="store_true",
                      help="print the defined system preparation parameters "
                      "for this input media")

    parser.add_option("--public", dest="public", default=False,
                      help="register image with the cloud as public",
                      action="store_true")

    parser.add_option("-r", "--register", dest="register", type="string",
                      default=False, metavar="IMAGENAME",
                      help="register the image with a cloud as IMAGENAME")

    parser.add_option("-s", "--silent", dest="silent", default=False,
                      help="output only errors", action="store_true")

    parser.add_option('--syslog', dest="syslog", default=False,
                      help="log to syslog", action="store_true")

    parser.add_option("--sysprep-param", dest="sysprep_params", default=[],
                      help="add KEY=VALUE system preparation parameter",
                      action="append")

    parser.add_option("-t", "--token", dest="token", type="string",
                      default=None, help="use this authentication token when "
                      "uploading/registering images")

    parser.add_option("--tmpdir", dest="tmp", type="string", default=None,
                      help="create large temporary image files under DIR",
                      metavar="DIR")

    parser.add_option("-u", "--upload", dest="upload", type="string",
                      default=False, metavar="FILENAME",
                      help="upload the image to the cloud with name FILENAME")

    options, args = parser.parse_args(input_args)

    if len(args) != 1:
        parser.error('Wrong number of arguments')

    options.source = args[0]
    if not os.path.exists(options.source):
        parser.error("Input media `%s' is not accessible" % options.source)

    if options.register and not options.upload:
        parser.error("You also need to set -u when -r option is set")

    if options.upload and (options.token is None or options.url is None) and \
            options.cloud is None:

        parser.error("Image uploading cannot be performed. You need to either "
                     "specify an authentication URL and token pair or an "
                     "available cloud name.")

    if options.tmp is not None and not os.path.isdir(options.tmp):
        parser.error("The directory `%s' specified with --tmpdir is not valid"
                     % options.tmp)

    meta = {}
    for m in options.metadata:
        try:
            key, value = m.split('=', 1)
        except ValueError:
            parser.error("Metadata option: `%s' is not in KEY=VALUE format." %
                         m)
        meta[key.upper()] = value
    options.metadata = meta

    sysprep_params = {}
    for p in options.sysprep_params:
        try:
            key, value = p.split('=', 1)
        except ValueError:
            parser.error("Sysprep parameter option: `%s' is not in KEY=VALUE "
                         "format." % p)
        sysprep_params[key] = value

    if options.virtio is not None:
        sysprep_params['virtio'] = options.virtio
    options.sysprep_params = sysprep_params

    if options.outfile is None and not options.upload and not \
            options.print_syspreps and not options.print_sysprep_params \
            and not options.print_metadata:
        parser.error("At least one of `-o', `-u', `--print-syspreps', "
                     "`--print-sysprep-params' or `--print-metadata' must be "
                     "set")

    if not options.force and options.outfile is not None and \
            os.path.realpath(options.outfile) != '/dev/null':
        for extension in ('', '.meta', '.md5sum'):
            filename = "%s%s" % (options.outfile, extension)
            if os.path.exists(filename):
                parser.error("Output file `%s' exists (use --force to "
                             "overwrite it)." % filename)

    return options


def image_creator(options, out):
    """snf-mkimage main function"""

    if os.geteuid() != 0:
        raise FatalError("You must run %s as root"
                         % os.path.basename(sys.argv[0]))

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
                    "Cloud: `%s' exists but is not valid!" % options.cloud)
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
        # There is no need to snapshot the media if it was created by the Disk
        # instance as a temporary object.
        device = disk.file if not options.snapshot else disk.snapshot()
        image = disk.get_image(device, sysprep_params=options.sysprep_params)

        if image.is_unsupported() and not options.allow_unsupported:
            raise FatalError(
                "The media seems to be unsupported.\n\n" +
                textwrap.fill("To create an image from an unsupported media, "
                              "you'll need to use the`--allow-unsupported' "
                              "command line option. Using this is highly "
                              "discouraged, since the resulting image will "
                              "not be cleared out of sensitive data and will "
                              "not get customized during the deployment."))

        if len(options.host_run) != 0 and not image.mount_local_support:
            raise FatalError("Running scripts against the guest media is not "
                             "supported for this build of libguestfs.")

        if len(options.host_run) != 0:
            for script in options.host_run:
                if not os.path.isfile(script):
                    raise FatalError("File: `%s' does not exist." % script)
                if not os.access(script, os.X_OK):
                    raise FatalError("File: `%s' is not executable." % script)

        for name in options.disabled_syspreps:
            sysprep = image.os.get_sysprep_by_name(name)
            if sysprep is not None:
                image.os.disable_sysprep(sysprep)
            else:
                out.warn("Sysprep: `%s' does not exist. Can't disable it." %
                         name)

        for name in options.enabled_syspreps:
            sysprep = image.os.get_sysprep_by_name(name)
            if sysprep is not None:
                image.os.enable_sysprep(sysprep)
            else:
                out.warn("Sysprep: `%s' does not exist. Can't enable it." %
                         name)

        if options.print_syspreps:
            image.os.print_syspreps()
            out.info()

        if options.print_sysprep_params:
            image.os.print_sysprep_params()
            out.info()

        if options.print_metadata:
            image.os.print_metadata()
            out.info()

        if options.outfile is None and not options.upload:
            return 0

        if options.virtio is not None and \
                hasattr(image.os, 'install_virtio_drivers'):
            image.os.install_virtio_drivers()

        if len(options.host_run) != 0:
            out.info("Running scripts on the input media:")
            mpoint = tempfile.mkdtemp()
            try:
                image.mount(mpoint)
                if not image.is_mounted():
                    raise FatalError("Mounting the media on the host failed.")
                try:
                    size = len(options.host_run)
                    cnt = 1
                    for script in options.host_run:
                        script = os.path.abspath(script)
                        out.info(("(%d/%d)" % (cnt, size)).ljust(7), False)
                        out.info("Running `%s'" % script)
                        ret = subprocess.Popen([script], cwd=mpoint).wait()
                        if ret != 0:
                            raise FatalError("Script: `%s' failed (rc=%d)" %
                                             (script, ret))
                        cnt += 1
                finally:
                    while not image.umount():
                        out.warn("Unable to umount the media. Retrying ...")
                        time.sleep(1)
                    out.info()
            finally:
                os.rmdir

        if options.sysprep:
            image.os.do_sysprep()

        if image.is_unsupported():
            image.meta['EXCLUDE_ALL_TASKS'] = "yes"

        # Add command line metadata to the collected ones...
        image.meta.update(options.metadata)

        checksum = image.md5()

        metastring = unicode(json.dumps(
            {'properties': image.meta,
             'disk-format': 'diskdump'}, ensure_ascii=False))

        if options.outfile is not None:
            if os.path.realpath(options.outfile) == '/dev/null':
                out.warn('Not dumping file to /dev/null')
            else:
                image.dump(options.outfile)

                out.info('Dumping metadata file ...', False)
                with open('%s.%s' % (options.outfile, 'meta'), 'w') as f:
                    f.write(metastring)
                out.success('done')

                out.info('Dumping md5sum file ...', False)
                with open('%s.%s' % (options.outfile, 'md5sum'), 'w') as f:
                    f.write('%s %s\n' % (checksum,
                                         os.path.basename(options.outfile)))
                out.success('done')

        out.info()
        try:
            if options.upload:
                out.info("Uploading image to the storage service:")
                with image.raw_device() as raw:
                    with open(raw, 'rb') as f:
                        remote = kamaki.upload(
                            f, image.size, options.upload,
                            "(1/3)  Calculating block hashes",
                            "(2/3)  Uploading missing blocks")

                out.info("(3/3)  Uploading md5sum file ...", False)
                md5sumstr = '%s %s\n' % (checksum,
                                         os.path.basename(options.upload))
                kamaki.upload(StringIO.StringIO(md5sumstr),
                              size=len(md5sumstr),
                              remote_path="%s.%s" % (options.upload, 'md5sum'))
                out.success('done')
                out.info()

            if options.register:
                img_type = 'public' if options.public else 'private'
                out.info('Registering %s image with the compute service ...'
                         % img_type, False)
                result = kamaki.register(options.register, remote,
                                         image.meta, options.public)
                out.success('done')
                out.info("Uploading metadata file ...", False)
                metastring = unicode(json.dumps(result, ensure_ascii=False,
                                                indent=4))
                kamaki.upload(StringIO.StringIO(metastring),
                              size=len(metastring),
                              remote_path="%s.%s" % (options.upload, 'meta'))
                out.success('done')
                if options.public:
                    out.info("Sharing md5sum file ...", False)
                    kamaki.share("%s.md5sum" % options.upload)
                    out.success('done')
                    out.info("Sharing metadata file ...", False)
                    kamaki.share("%s.meta" % options.upload)
                    out.success('done')
                out.result(json.dumps(result, indent=4, ensure_ascii=False))
                out.info()
        except ClientError as e:
            raise FatalError("Service client: %d %s" % (e.status, e.message))

    finally:
        out.info('cleaning up ...')
        disk.cleanup()

    out.success("snf-image-creator exited without errors")

    return 0


def main():
    """Main entry point"""
    options = parse_options(sys.argv[1:])

    if options.silent:
        out = SilentOutput(colored=sys.stderr.isatty())
    else:
        out = OutputWthProgress() if sys.stderr.isatty() else \
            SimpleOutput(colored=False)

    if options.syslog:
        out = CompositeOutput([out, SyslogOutput()])

    title = 'snf-image-creator %s' % version
    out.info(title)
    out.info('=' * len(title))

    try:
        sys.exit(image_creator(options, out))
    except FatalError as e:
        out.error(e)
        sys.exit(1)

if __name__ == '__main__':
    main()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
