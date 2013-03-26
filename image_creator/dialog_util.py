#!/usr/bin/env python

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

import os
from image_creator.output.dialog import GaugeOutput
from image_creator.util import MD5

SMALL_WIDTH = 60
WIDTH = 70


def update_background_title(session):
    d = session['dialog']
    disk = session['disk']
    image = session['image']

    MB = 2 ** 20

    size = (image.size + MB - 1) // MB
    shrinked = 'shrinked' in session and session['shrinked']
    postfix = " (shrinked)" if shrinked else ''

    title = "OS: %s, Distro: %s, Size: %dMB%s, Source: %s" % \
            (image.ostype, image.distro, size, postfix,
             os.path.abspath(disk.source))

    d.setBackgroundTitle(title)


def confirm_exit(d, msg=''):
    return not d.yesno("%s Do you want to exit?" % msg, width=SMALL_WIDTH)


def confirm_reset(d):
    return not d.yesno("Are you sure you want to reset everything?",
                       width=SMALL_WIDTH, defaultno=1)


class Reset(Exception):
    pass


def extract_metadata_string(session):
    metadata = ['%s=%s' % (k, v) for (k, v) in session['metadata'].items()]

    if 'task_metadata' in session:
        metadata.extend("%s=yes" % m for m in session['task_metadata'])

    return '\n'.join(metadata) + '\n'


def extract_image(session):
    d = session['dialog']
    dir = os.getcwd()
    while 1:
        if dir and dir[-1] != os.sep:
            dir = dir + os.sep

        (code, path) = d.fselect(dir, 10, 50, title="Save image as...")
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        if os.path.isdir(path):
            dir = path
            continue

        if os.path.isdir("%s.meta" % path):
            d.msgbox("Can't overwrite directory `%s.meta'" % path,
                     width=SMALL_WIDTH)
            continue

        if os.path.isdir("%s.md5sum" % path):
            d.msgbox("Can't overwrite directory `%s.md5sum'" % path,
                     width=SMALL_WIDTH)
            continue

        basedir = os.path.dirname(path)
        name = os.path.basename(path)
        if not os.path.exists(basedir):
            d.msgbox("Directory `%s' does not exist" % basedir,
                     width=SMALL_WIDTH)
            continue

        dir = basedir
        if len(name) == 0:
            continue

        files = ["%s%s" % (path, ext) for ext in ('', '.meta', '.md5sum')]
        overwrite = filter(os.path.exists, files)

        if len(overwrite) > 0:
            if d.yesno("The following file(s) exist:\n"
                       "%s\nDo you want to overwrite them?" %
                       "\n".join(overwrite), width=SMALL_WIDTH):
                continue

        gauge = GaugeOutput(d, "Image Extraction", "Extracting image...")
        try:
            image = session['image']
            out = image.out
            out.add(gauge)
            try:
                if "checksum" not in session:
                    md5 = MD5(out)
                    session['checksum'] = md5.compute(image.device, image.size)

                # Extract image file
                image.dump(path)

                # Extract metadata file
                out.output("Extracting metadata file...")
                with open('%s.meta' % path, 'w') as f:
                    f.write(extract_metadata_string(session))
                out.success('done')

                # Extract md5sum file
                out.output("Extracting md5sum file...")
                md5str = "%s %s\n" % (session['checksum'], name)
                with open('%s.md5sum' % path, 'w') as f:
                    f.write(md5str)
                out.success("done")
            finally:
                out.remove(gauge)
        finally:
            gauge.cleanup()
        d.msgbox("Image file `%s' was successfully extracted!" % path,
                 width=SMALL_WIDTH)
        break

    return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
