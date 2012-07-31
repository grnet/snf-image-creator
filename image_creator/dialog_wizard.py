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

from image_creator.kamaki_wrapper import Kamaki

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


def wizard(session):

    name = WizardPage("ImageName", "Please provide a name for the image:",
                      title="Image Name", init=session['device'].distro)
    descr = WizardPage("ImageDescription",
        "Please provide a description for the image:",
        title="Image Description", empty=True,
        init=session['metadata']['DESCRIPTION'] if 'DESCRIPTION' in
        session['metadata'] else '')
    account = WizardPage("account",
        "Please provide your ~okeanos account e-mail:",
        title="~okeanos account information", init=Kamaki.get_account())
    token = WizardPage("token",
        "Please provide your ~okeanos account token:",
        title="~okeanos account token", init=Kamaki.get_token())

    w = Wizard(session)
    w.add_page(name)
    w.add_page(descr)
    w.add_page(account)
    w.add_page(token)

    return w.run()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
