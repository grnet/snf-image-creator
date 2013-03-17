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

import dialog
import time
import StringIO

from image_creator.kamaki_wrapper import Kamaki, ClientError
from image_creator.util import MD5, FatalError
from image_creator.output.cli import OutputWthProgress
from image_creator.dialog_util import extract_image, update_background_title

PAGE_WIDTH = 70


class WizardExit(Exception):
    pass


class WizardInvalidData(Exception):
    pass


class Wizard:
    def __init__(self, session):
        self.session = session
        self.pages = []
        self.session['wizard'] = {}

    def add_page(self, page):
        self.pages.append(page)

    def run(self):
        idx = 0
        while True:
            try:
                idx += self.pages[idx].run(self.session, idx, len(self.pages))
            except WizardExit:
                return False
            except WizardInvalidData:
                continue

            if idx >= len(self.pages):
                break

            if idx < 0:
                return False
        return True


class WizardPage:
    NEXT = 1
    PREV = -1

    def run(self, session, index, total):
        raise NotImplementedError


class WizardRadioListPage(WizardPage):

    def __init__(self, name, message, choices, **kargs):
        self.name = name
        self.message = message
        self.choices = choices
        self.title = kargs['title'] if 'title' in kargs else ''
        self.default = kargs['default'] if 'default' in kargs else 0

    def run(self, session, index, total):
        d = session['dialog']
        w = session['wizard']

        choices = []
        for i in range(len(self.choices)):
            default = 1 if self.choices[i][0] == self.default else 0
            choices.append((self.choices[i][0], self.choices[i][1], default))

        while True:
            (code, answer) = \
                d.radiolist(self.message, height=10, width=PAGE_WIDTH,
                            ok_label="Next", cancel="Back", choices=choices,
                            title="(%d/%d) %s" % (index + 1, total, self.title)
                            )

            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                return self.PREV

            w[self.name] = answer
            self.default = answer

            return self.NEXT


class WizardInputPage(WizardPage):

    def __init__(self, name, message, **kargs):
        self.name = name
        self.message = message
        self.title = kargs['title'] if 'title' in kargs else ''
        self.init = kargs['init'] if 'init' in kargs else ''
        if 'validate' in kargs:
            validate = kargs['validate']
        else:
            validate = lambda x: x

        setattr(self, "validate", validate)

    def run(self, session, index, total):
        d = session['dialog']
        w = session['wizard']

        while True:
            (code, answer) = \
                d.inputbox(self.message, init=self.init,
                           width=PAGE_WIDTH, ok_label="Next", cancel="Back",
                           title="(%d/%d) %s" % (index + 1, total, self.title))

            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                return self.PREV

            value = answer.strip()
            self.init = value
            w[self.name] = self.validate(value)
            break

        return self.NEXT


class WizardYesNoPage(WizardPage):

    def __init__(self, message, **kargs):
        self.message = message
        self.title = kargs['title'] if 'title' in kargs else ''

    def run(self, session, index, total):
        d = session['dialog']

        while True:
            ret = d.yesno(self.message, width=PAGE_WIDTH, ok_label="Yes",
                          cancel="Back", extra_button=1, extra_label="Quit",
                          title="(%d/%d) %s" % (index + 1, total, self.title))

            if ret == d.DIALOG_CANCEL:
                return self.PREV
            elif ret == d.DIALOG_EXTRA:
                raise WizardExit
            elif ret == d.DIALOG_OK:
                return self.NEXT


def wizard(session):

    init_token = Kamaki.get_token()
    if init_token is None:
        init_token = ""

    name = WizardInputPage("ImageName", "Please provide a name for the image:",
                           title="Image Name", init=session['device'].distro)
    descr = WizardInputPage(
        "ImageDescription", "Please provide a description for the image:",
        title="Image Description", init=session['metadata']['DESCRIPTION'] if
        'DESCRIPTION' in session['metadata'] else '')
    registration = WizardRadioListPage(
        "ImageRegistration", "Please provide a registration type:",
        [("Private", "Image is accessible only by this user"),
         ("Public", "Everyone can create VMs from this image")],
        title="Registration Type", default="Private")

    def validate_account(token):
        if len(token) == 0:
            d.msgbox("The token cannot be empty", width=PAGE_WIDTH)
            raise WizardInvalidData

        account = Kamaki.get_account(token)
        if account is None:
            session['dialog'].msgbox("The token you provided in not valid!",
                                     width=PAGE_WIDTH)
            raise WizardInvalidData

        return account

    account = WizardInputPage(
        "account", "Please provide your ~okeanos authentication token:",
        title="~okeanos account", init=init_token, validate=validate_account)

    msg = "All necessary information has been gathered. Confirm and Proceed."
    proceed = WizardYesNoPage(msg, title="Confirmation")

    w = Wizard(session)

    w.add_page(name)
    w.add_page(descr)
    w.add_page(registration)
    w.add_page(account)
    w.add_page(proceed)

    if w.run():
        create_image(session)
    else:
        return False

    return True


def create_image(session):
    d = session['dialog']
    disk = session['disk']
    device = session['device']
    snapshot = session['snapshot']
    image_os = session['image_os']
    wizard = session['wizard']

    # Save Kamaki credentials
    Kamaki.save_token(wizard['account']['auth_token'])

    with_progress = OutputWthProgress(True)
    out = disk.out
    out.add(with_progress)
    try:
        out.clear()

        #Sysprep
        device.mount(False)
        image_os.do_sysprep()
        metadata = image_os.meta
        device.umount()

        #Shrink
        size = device.shrink()
        session['shrinked'] = True
        update_background_title(session)

        metadata.update(device.meta)
        metadata['DESCRIPTION'] = wizard['ImageDescription']

        #MD5
        md5 = MD5(out)
        session['checksum'] = md5.compute(snapshot, size)

        #Metadata
        metastring = '\n'.join(
            ['%s=%s' % (key, value) for (key, value) in metadata.items()])
        metastring += '\n'

        out.output()
        try:
            out.output("Uploading image to pithos:")
            kamaki = Kamaki(wizard['account'], out)

            name = "%s-%s.diskdump" % (wizard['ImageName'],
                                       time.strftime("%Y%m%d%H%M"))
            pithos_file = ""
            with open(snapshot, 'rb') as f:
                pithos_file = kamaki.upload(f, size, name,
                                            "(1/4)  Calculating block hashes",
                                            "(2/4)  Uploading missing blocks")

            out.output("(3/4)  Uploading metadata file ...", False)
            kamaki.upload(StringIO.StringIO(metastring), size=len(metastring),
                          remote_path="%s.%s" % (name, 'meta'))
            out.success('done')
            out.output("(4/4)  Uploading md5sum file ...", False)
            md5sumstr = '%s %s\n' % (session['checksum'], name)
            kamaki.upload(StringIO.StringIO(md5sumstr), size=len(md5sumstr),
                          remote_path="%s.%s" % (name, 'md5sum'))
            out.success('done')
            out.output()

            is_public = True if w['ImageRegistration'] == "Public" else False
            out.output('Registering %s image with ~okeanos ...' %
                       w['ImageRegistration'].lower(), False)
            kamaki.register(wizard['ImageName'], pithos_file, metadata,
                            is_public)
            out.success('done')
            out.output()

        except ClientError as e:
            raise FatalError("Pithos client: %d %s" % (e.status, e.message))
    finally:
        out.remove(with_progress)

    msg = "The %s image was successfully uploaded and registered with " \
          "~okeanos. Would you like to keep a local copy of the image?" \
          % w['ImageRegistration'].lower()
    if not d.yesno(msg, width=PAGE_WIDTH):
        extract_image(session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
