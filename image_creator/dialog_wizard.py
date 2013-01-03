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
            default = 1 if i == self.default else 0
            choices.append((self.choices[i][0], self.choices[i][1], default))

        while True:
            (code, answer) = \
                d.radiolist(self.message, width=PAGE_WIDTH,
                            ok_label="Next", cancel="Back", choices=choices,
                            title="(%d/%d) %s" % (index + 1, total, self.title)
                            )

            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                return self.PREV

            for i in range(len(choices)):
                if self.choices[i] == answer:
                    self.default = i
                    w[name] = i
                    break

            return self.NEXT


class WizardInputPage(WizardPage):

    def __init__(self, name, message, **kargs):
        self.name = name
        self.message = message
        self.title = kargs['title'] if 'title' in kargs else ''
        self.init_value = kargs['init'] if 'init' in kargs else ''
        self.allow_empty = kargs['empty'] if 'empty' in kargs else False

    def run(self, session, index, total):
        d = session['dialog']
        w = session['wizard']

        init = w[self.name] if self.name in w else self.init_value
        while True:
            (code, answer) = \
                d.inputbox(self.message, init=init,
                           width=PAGE_WIDTH, ok_label="Next", cancel="Back",
                           title="(%d/%d) %s" % (index + 1, total, self.title))

            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                return self.PREV

            value = answer.strip()
            if len(value) == 0 and self.allow_empty is False:
                d.msgbox("The value cannot be empty!", width=PAGE_WIDTH)
                continue
            w[self.name] = value
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
    init_account = Kamaki.get_account()
    if init_account is None:
        init_account = ""

    init_token = Kamaki.get_token()
    if init_token is None:
        init_token = ""

    name = WizardInputPage("ImageName", "Please provide a name for the image:",
                           title="Image Name", init=session['device'].distro)
    descr = WizardInputPage("ImageDescription",
                            "Please provide a description for the image:",
                            title="Image Description", empty=True,
                            init=session['metadata']['DESCRIPTION'] if
                            'DESCRIPTION' in session['metadata'] else '')
    account = WizardInputPage("account",
                              "Please provide your ~okeanos account e-mail:",
                              title="~okeanos account information",
                              init=init_account)
    token = WizardInputPage("token",
                            "Please provide your ~okeanos account token:",
                            title="~okeanos account token",
                            init=init_token)

    msg = "All necessary information has been gathered. Confirm and Proceed."
    proceed = WizardYesNoPage(msg, title="Confirmation")

    w = Wizard(session)

    w.add_page(name)
    w.add_page(descr)
    w.add_page(account)
    w.add_page(token)
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
    Kamaki.save_account(wizard['account'])
    Kamaki.save_token(wizard['token'])

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
            kamaki = Kamaki(wizard['account'], wizard['token'], out)

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

            out.output('Registering image with ~okeanos ...', False)
            kamaki.register(wizard['ImageName'], pithos_file, metadata)
            out.success('done')
            out.output()

        except ClientError as e:
            raise FatalError("Pithos client: %d %s" % (e.status, e.message))
    finally:
        out.remove(with_progress)

    msg = "The image was successfully uploaded and registered with " \
          "~okeanos. Would you like to keep a local copy of the image?"
    if not d.yesno(msg, width=PAGE_WIDTH):
        extract_image(session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
