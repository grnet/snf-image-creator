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

PAGE_WIDTH = 70


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
            idx += self.pages[idx].run(self.session, idx, len(self.pages))

            if idx >= len(self.pages):
                break

            if idx < 0:
                return False
        return True


class WizardPage:
    NEXT = 1
    PREV = -1
    EXIT = -255

    def run(self, session, index, total):
        raise NotImplementedError


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
            (code, answer) = d.inputbox(self.message, init=init,
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
                return self.EXIT
            elif ret == d.DIALOG_OK:
                return self.NEXT


def wizard(session):

    name = WizardInputPage("ImageName", "Please provide a name for the image:",
                      title="Image Name", init=session['device'].distro)
    descr = WizardInputPage("ImageDescription",
        "Please provide a description for the image:",
        title="Image Description", empty=True,
        init=session['metadata']['DESCRIPTION'] if 'DESCRIPTION' in
        session['metadata'] else '')
    account = WizardInputPage("account",
        "Please provide your ~okeanos account e-mail:",
        title="~okeanos account information", init=Kamaki.get_account())
    token = WizardInputPage("token",
        "Please provide your ~okeanos account token:",
        title="~okeanos account token", init=Kamaki.get_token())

    msg = "Do you wish to continue with the image extraction process?"
    proceed = WizardYesNoPage(msg, title="Confirmation")

    w = Wizard(session)

    w.add_page(name)
    w.add_page(descr)
    w.add_page(account)
    w.add_page(token)
    w.add_page(proceed)

    if w.run():
        extract_image(session)
    else:
        return False

    return True


def extract_image(session):
    disk = session['disk']
    device = session['device']
    snapshot = session['snapshot']
    image_os = session['image_os']
    wizard = session['wizard']

    out = OutputWthProgress(True)
    #Initialize the output
    disk.out = out
    device.out = out
    image_os.out = out

    out.clear()

    #Sysprep
    device.mount(False)
    image_os.do_sysprep()
    metadata = image_os.meta
    device.umount()

    #Shrink
    size = device.shrink()

    metadata.update(device.meta)
    metadata['DESCRIPTION'] = wizard['ImageDescription']

    #MD5
    md5 = MD5(out)
    checksum = md5.compute(snapshot, size)

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

        out.output("(3/4)  Uploading metadata file...", False)
        kamaki.upload(StringIO.StringIO(metastring), size=len(metastring),
                      remote_path="%s.%s" % (name, 'meta'))
        out.success('done')
        out.output("(4/4)  Uploading md5sum file...", False)
        md5sumstr = '%s %s\n' % (checksum, name)
        kamaki.upload(StringIO.StringIO(md5sumstr), size=len(md5sumstr),
                      remote_path="%s.%s" % (name, 'md5sum'))
        out.success('done')
        out.output()

        out.output('Registring image to ~okeanos...', False)
        kamaki.register(wizard['ImageName'], pithos_file, metadata)
        out.success('done')
        out.output()
    except ClientError as e:
        raise FatalError("Pithos client: %d %s" % (e.status, e.message))

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
