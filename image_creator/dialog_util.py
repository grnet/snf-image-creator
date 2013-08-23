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

"""Module providing useful functions for the dialog-based version of
snf-image-creator.
"""

import os
import re
import json
from image_creator.output.dialog import GaugeOutput
from image_creator.util import MD5
from image_creator.kamaki_wrapper import Kamaki

SMALL_WIDTH = 60
WIDTH = 70


def update_background_title(session):
    """Update the backgroud title of the dialog page"""
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
    """Ask the user to confirm when exiting the program"""
    return not d.yesno("%s Do you want to exit?" % msg, width=SMALL_WIDTH)


def confirm_reset(d):
    """Ask the user to confirm a reset action"""
    return not d.yesno("Are you sure you want to reset everything?",
                       width=SMALL_WIDTH, defaultno=1)


class Reset(Exception):
    """Exception used to reset the program"""
    pass


def extract_metadata_string(session):
    """Convert image metadata to text"""
    metadata = {}
    metadata.update(session['metadata'])
    if 'task_metadata' in session:
        for key in session['task_metadata']:
            metadata[key] = 'yes'

    return unicode(json.dumps({'properties': metadata,
                               'disk-format': 'diskdump'}, ensure_ascii=False))


def extract_image(session):
    """Dump the image to a local file"""
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
                out.output("Extracting metadata file ...")
                with open('%s.meta' % path, 'w') as f:
                    f.write(extract_metadata_string(session))
                out.success('done')

                # Extract md5sum file
                out.output("Extracting md5sum file ...")
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


def _check_cloud(session, name, description, url, token):
    """Checks if the provided info for a cloud are valid"""
    d = session['dialog']
    regexp = re.compile('^[~@#$:\-\w]+$')

    if not re.match(regexp, name):
        d.msgbox("Allowed characters for name: a-zA-Z0-9_~@#$:-", width=WIDTH)
        return False

    if len(url) == 0:
        d.msgbox("Url cannot be empty!", width=WIDTH)
        return False

    if len(token) == 0:
        d.msgbox("Token cannot be empty!", width=WIDTH)
        return False

    if Kamaki.create_account(url, token) is None:
        d.msgbox("The cloud info you provided is not valid. Please check the "
                 "Authentication URL and the token values again!", width=WIDTH)
        return False

    return True


def add_cloud(session):
    """Add a new cloud account"""

    d = session['dialog']

    name = ""
    description = ""
    url = ""
    token = ""

    while 1:
        fields = [
            ("Name:", name, 60),
            ("Description (optional): ", description, 80),
            ("Authentication URL: ", url, 200),
            ("Token:", token, 100)]

        (code, output) = d.form("Add a new cloud account:", height=13,
                                width=WIDTH, form_height=4, fields=fields)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        name, description, url, token = output

        name = name.strip()
        description = description.strip()
        url = url.strip()
        token = token.strip()

        if _check_cloud(session, name, description, url, token):
            if name in Kamaki.get_clouds().keys():
                d.msgbox("A cloud with name `%s' already exists. If you want "
                         "to edit the existing cloud account, use the edit "
                         "menu." % name, width=WIDTH)
            else:
                Kamaki.save_cloud(name, url, token, description)
                break

        continue

    return True


def edit_cloud(session, name):
    """Edit a cloud account"""

    info = Kamaki.get_cloud_by_name(name)

    assert info, "Cloud: `%s' does not exist" % name

    description = info['description'] if 'description' in info else ""
    url = info['url'] if 'url' in info else ""
    token = info['token'] if 'token' in info else ""

    d = session['dialog']

    while 1:
        fields = [
            ("Description (optional): ", description, 80),
            ("Authentication URL: ", url, 200),
            ("Token:", token, 100)]

        (code, output) = d.form("Edit cloud account: `%s'" % name, height=13,
                                width=WIDTH, form_height=3, fields=fields)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        description, url, token = output

        description = description.strip()
        url = url.strip()
        token = token.strip()

        if _check_cloud(session, name, description, url, token):
            Kamaki.save_cloud(name, url, token, description)
            break

        continue

    return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
