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

import time
import StringIO

from image_creator.kamaki_wrapper import Kamaki, ClientError
from image_creator.util import MD5, FatalError
from image_creator.output.cli import OutputWthProgress
from image_creator.dialog_util import extract_image, update_background_title

PAGE_WIDTH = 70


class WizardExit(Exception):
    """Exception used to exit the wizard"""
    pass


class WizardInvalidData(Exception):
    """Exception triggered when the user provided data are invalid"""
    pass


class Wizard:
    """Represents a dialog-based wizard

    The wizard is a collection of pages that have a "Next" and a "Back" button
    on them. The pages are used to collect user data.
    """

    def __init__(self, session):
        self.session = session
        self.pages = []
        self.session['wizard'] = {}
        self.d = session['dialog']

    def add_page(self, page):
        """Add a new page to the wizard"""
        self.pages.append(page)

    def run(self):
        """Run the wizard"""
        idx = 0
        while True:
            try:
                idx += self.pages[idx].run(self.session, idx, len(self.pages))
            except WizardExit:
                return False
            except WizardInvalidData:
                continue

            if idx >= len(self.pages):
                msg = "All necessary information has been gathered:\n\n"
                for page in self.pages:
                    msg += " * %s\n" % page.info
                msg += "\nContinue with the image creation process?"

                ret = self.d.yesno(
                    msg, width=PAGE_WIDTH, height=8 + len(self.pages),
                    ok_label="Yes", cancel="Back", extra_button=1,
                    extra_label="Quit", title="Confirmation")

                if ret == self.d.DIALOG_CANCEL:
                    idx -= 1
                elif ret == self.d.DIALOG_EXTRA:
                    return False
                elif ret == self.d.DIALOG_OK:
                    return True

            if idx < 0:
                return False


class WizardPage(object):
    """Represents a page in a wizard"""
    NEXT = 1
    PREV = -1

    def __init__(self, **kargs):
        validate = kargs['validate'] if 'validate' in kargs else lambda x: x
        setattr(self, "validate", validate)

        display = kargs['display'] if 'display' in kargs else lambda x: x
        setattr(self, "display", display)

    def run(self, session, index, total):
        """Display this wizard page

        This function is used by the wizard program when accessing a page.
        """
        raise NotImplementedError


class WizardRadioListPage(WizardPage):
    """Represent a Radio List in a wizard"""
    def __init__(self, name, printable, message, choices, **kargs):
        super(WizardRadioListPage, self).__init__(**kargs)
        self.name = name
        self.printable = printable
        self.message = message
        self.choices = choices
        self.title = kargs['title'] if 'title' in kargs else ''
        self.default = kargs['default'] if 'default' in kargs else ""

    def run(self, session, index, total):
        d = session['dialog']
        w = session['wizard']

        choices = []
        for i in range(len(self.choices)):
            default = 1 if self.choices[i][0] == self.default else 0
            choices.append((self.choices[i][0], self.choices[i][1], default))

        (code, answer) = d.radiolist(
            self.message, height=10, width=PAGE_WIDTH, ok_label="Next",
            cancel="Back", choices=choices,
            title="(%d/%d) %s" % (index + 1, total, self.title))

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV

        w[self.name] = self.validate(answer)
        self.default = answer
        self.info = "%s: %s" % (self.printable, self.display(w[self.name]))

        return self.NEXT


class WizardInputPage(WizardPage):
    """Represents an input field in a wizard"""
    def __init__(self, name, printable, message, **kargs):
        super(WizardInputPage, self).__init__(**kargs)
        self.name = name
        self.printable = printable
        self.message = message
        self.info = "%s: <none>" % self.printable
        self.title = kargs['title'] if 'title' in kargs else ''
        self.init = kargs['init'] if 'init' in kargs else ''

    def run(self, session, index, total):
        d = session['dialog']
        w = session['wizard']

        (code, answer) = d.inputbox(
            self.message, init=self.init, width=PAGE_WIDTH, ok_label="Next",
            cancel="Back", title="(%d/%d) %s" % (index + 1, total, self.title))

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV

        value = answer.strip()
        self.init = value
        w[self.name] = self.validate(value)
        self.info = "%s: %s" % (self.printable, self.display(w[self.name]))

        return self.NEXT


def start_wizard(session):
    """Run the image creation wizard"""
    init_token = Kamaki.get_token()
    if init_token is None:
        init_token = ""

    distro = session['image'].distro
    ostype = session['image'].ostype
    name = WizardInputPage(
        "ImageName", "Image Name", "Please provide a name for the image:",
        title="Image Name", init=ostype if distro == "unknown" else distro)

    descr = WizardInputPage(
        "ImageDescription", "Image Description",
        "Please provide a description for the image:",
        title="Image Description", init=session['metadata']['DESCRIPTION'] if
        'DESCRIPTION' in session['metadata'] else '')

    registration = WizardRadioListPage(
        "ImageRegistration", "Registration Type",
        "Please provide a registration type:",
        [("Private", "Image is accessible only by this user"),
         ("Public", "Everyone can create VMs from this image")],
        title="Registration Type", default="Private")

    def validate_account(token):
        """Check if a token is valid"""
        d = session['dialog']

        if len(token) == 0:
            d.msgbox("The token cannot be empty", width=PAGE_WIDTH)
            raise WizardInvalidData

        account = Kamaki.get_account(token)
        if account is None:
            d.msgbox("The token you provided in not valid!", width=PAGE_WIDTH)
            raise WizardInvalidData

        return account

    account = WizardInputPage(
        "Account", "Account",
        "Please provide your ~okeanos authentication token:",
        title="~okeanos account", init=init_token, validate=validate_account,
        display=lambda account: account['username'])

    w = Wizard(session)

    w.add_page(name)
    w.add_page(descr)
    w.add_page(registration)
    w.add_page(account)

    if w.run():
        create_image(session)
    else:
        return False

    return True


def create_image(session):
    """Create an image using the information collected by the wizard"""
    d = session['dialog']
    image = session['image']
    wizard = session['wizard']

    # Save Kamaki credentials
    Kamaki.save_token(wizard['Account']['auth_token'])

    with_progress = OutputWthProgress(True)
    out = image.out
    out.add(with_progress)
    try:
        out.clear()

        #Sysprep
        image.mount(False)
        err_msg = "Unable to execute the system preparation tasks."
        if not image.mounted:
            raise FatalError("%s Couldn't mount the media." % err_msg)
        elif image.mounted_ro:
            raise FatalError("%s Couldn't mount the media read-write."
                             % err_msg)
        image.os.do_sysprep()
        metadata = image.os.meta
        image.umount()

        #Shrink
        size = image.shrink()
        session['shrinked'] = True
        update_background_title(session)

        metadata.update(image.meta)
        metadata['DESCRIPTION'] = wizard['ImageDescription']

        #MD5
        md5 = MD5(out)
        session['checksum'] = md5.compute(image.device, size)

        #Metadata
        metastring = '\n'.join(
            ['%s=%s' % (key, value) for (key, value) in metadata.items()])
        metastring += '\n'

        out.output()
        try:
            out.output("Uploading image to pithos:")
            kamaki = Kamaki(wizard['Account'], out)

            name = "%s-%s.diskdump" % (wizard['ImageName'],
                                       time.strftime("%Y%m%d%H%M"))
            pithos_file = ""
            with open(image.device, 'rb') as f:
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

            is_public = True if wizard['ImageRegistration'] == "Public" else \
                False
            out.output('Registering %s image with ~okeanos ...' %
                       wizard['ImageRegistration'].lower(), False)
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
          % wizard['ImageRegistration'].lower()
    if not d.yesno(msg, width=PAGE_WIDTH):
        extract_image(session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
