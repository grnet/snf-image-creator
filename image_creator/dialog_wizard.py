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

class WizardPage:
    NEXT = 1
    PREV = -1

    def __init__(self, session, title):
        self.session = session
        self.title = title

    def run(self):
        raise NotImplementedError


class ImageName(WizardPage):
    def run(self):
        d = self.session['dialog']
        w = self.session['wizard']
        
        init = w['ImageName'] if 'ImageName' in w else ""
        while 1:
            (code, answer) = d.inputbox("Please provide a name for the image:",
                                        init=init, width=INPUTBOX_WIDTH,
                                        ok_label="Next", cancel="Back",
                                        title=self.title)

            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                return self.PREV

            name = answer.strip()
            if len(name) == 0:
                d.msgbox("Image name cannot be empty", width=MSGBOX_WIDTH)
                continue
            w['ImageName'] = name
            break

        return self.NEXT


class ImageDescription(WizardPage):
    def run(self):
        d = self.session['dialog']
        w = self.session['wizard']

        init = w['ImageDescription'] if 'ImageDescription' in w else ""

        while 1:
            (code, answer) = d.inputbox(
                                "Please provide a description for the image:",
                                init=init, width=INPUTBOX_WIDTH,
                                ok_label="Next", cancel="Back",
                                title=self.title)

            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                return self.PREV

            name = answer.strip()
            if len(filename) == 0:
                # Description is allowed to be empty
                del w['ImageDescription']
            else:
                w['ImageDescription'] = name
            break

        return self.NEXT


def wizard(session):
    session['wizard'] = {}

    steps = []
    steps.append(ImageName(session, "(1/5) Image Name"))
    steps.append(ImageDescription(session, "(2/5) Image Description"))

    return True


# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
