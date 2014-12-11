# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 GRNET S.A.
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

"""This module implements the "wizard" mode of the dialog-based version of
snf-image-creator.
"""

import time
import StringIO
import json
import re

from image_creator.kamaki_wrapper import Kamaki, ClientError
from image_creator.util import FatalError, virtio_versions
from image_creator.output.cli import OutputWthProgress
from image_creator.dialog_util import extract_image, update_background_title, \
    add_cloud, edit_cloud, update_sysprep_param

PAGE_WIDTH = 70
PAGE_HEIGHT = 12


class WizardExit(Exception):
    """Exception used to exit the wizard"""
    pass


class WizardReloadPage(Exception):
    """Exception that reloads the last WizardPage"""
    pass


class Wizard(object):
    """Represents a dialog-based wizard

    The wizard is a collection of pages that have a "Next" and a "Back" button
    on them. The pages are used to collect user data.
    """

    def __init__(self, dialog):
        """Initialize the Wizard"""
        self._pages = []
        self.dialog = dialog

    def add_page(self, page):
        """Add a new page to the wizard"""
        self._pages.append(page)

    def run(self):
        """Run the wizard"""
        idx = 0
        while True:
            try:
                total = len(self._pages)
                title = "(%d/%d) %s" % (idx + 1, total, self._pages[idx].title)
                idx += self._pages[idx].show(self.dialog, title)
            except WizardExit:
                return False
            except WizardReloadPage:
                continue

            if idx >= len(self._pages):
                text = "All necessary information has been gathered:\n\n"
                for page in self._pages:
                    text += " * %s\n" % page
                text += "\nContinue with the image creation process?"

                ret = self.dialog.yesno(
                    text, width=PAGE_WIDTH, height=8 + len(self._pages),
                    ok_label="Yes", cancel="Back", extra_button=1,
                    extra_label="Quit", title="Confirmation")

                if ret == self.dialog.DIALOG_CANCEL:
                    idx -= 1
                elif ret == self.dialog.DIALOG_EXTRA:
                    return False
                elif ret == self.dialog.DIALOG_OK:
                    return True

            if idx < 0:
                return False

    @property
    def answers(self):
        """Returns the answers the user provided"""
        return dict((page.name, page.answer) for page in self._pages)


class WizardPage(object):
    """Represents a page in a wizard"""
    NEXT = 1
    PREV = -1

    def __init__(self, name, text, **kwargs):
        self.name = name
        self.answer = None
        self.text = text
        self.print_name = kwargs['print_name'] if 'print_name' in kwargs \
            else " ".join(re.findall('[A-Z][^A-Z]*', name))
        self.title = kwargs['title'] if 'title' in kwargs else self.print_name
        self.default = kwargs['default'] if 'default' in kwargs else ""
        self.extra = kwargs['extra'] if 'extra' in kwargs else None
        self.validate = \
            kwargs['validate'] if 'validate' in kwargs else lambda x: x
        self.display = \
            kwargs['display'] if 'display' in kwargs else lambda x: x

        self.dargs = {}
        self.dargs['ok_label'] = 'Next'
        self.dargs['cancel'] = 'Back'
        self.dargs['width'] = PAGE_WIDTH
        self.dargs['height'] = PAGE_HEIGHT

        if 'extra' in kwargs:
            self.dargs['extra_button'] = 1

        self.extra_label = kwargs['extra_label'] if 'extra_label' in kwargs \
            else lambda: "extra"

    def __str__(self):
        """Prints the answer"""
        return "%s: %s" % (self.print_name, self.display(self.answer))

    def show(self, dialog, title):
        """Display this wizard page

        This function is used by the wizard program when accessing a page.
        """
        raise NotImplementedError


class WizardInputPage(WizardPage):
    """Represents an input field in a wizard"""

    def show(self, dialog, title):
        """Display this wizard page"""
        (code, answer) = dialog.inputbox(self.text(), init=self.default,
                                         title=title,
                                         extra_label=self.extra_label(),
                                         **self.dargs)

        if code in (dialog.DIALOG_CANCEL, dialog.DIALOG_ESC):
            return self.PREV

        self.answer = self.validate(answer.strip())
        self.default = self.answer

        return self.NEXT


class WizardInfoPage(WizardPage):
    """Represents a Wizard Page that just displays some user-defined
    information.

    The user-defined information is created by the info function.
    """
    def __init__(self, name, text, info, **kwargs):
        """Initialize the WizardInfoPage instance"""
        super(WizardInfoPage, self).__init__(name, text, **kwargs)
        self.info = info

    def show(self, dialog, title):
        """Display this wizard page"""

        text = "%s\n\n%s" % (self.text(), self.info())

        ret = dialog.yesno(text, title=title, extra_label=self.extra_label(),
                           **self.dargs)

        if ret in (dialog.DIALOG_CANCEL, dialog.DIALOG_ESC):
            return self.PREV
        elif ret == dialog.DIALOG_EXTRA:
            self.extra()
            raise WizardReloadPage

        # DIALOG_OK
        self.answer = self.validate(None)
        return self.NEXT


class WizardFormPage(WizardPage):
    """Represents a Form in a wizard"""

    def __init__(self, name, text, fields, **kwargs):
        """Initialize the WizardFormPage instance"""
        super(WizardFormPage, self).__init__(name, text, **kwargs)
        self.fields = fields

    def show(self, dialog, title):
        """Display this wizard page"""
        field_lenght = len(self.fields())
        form_height = field_lenght if field_lenght < PAGE_HEIGHT - 4 \
            else PAGE_HEIGHT - 4

        (code, output) = dialog.form(self.text(), form_height=form_height,
                                     fields=self.fields(), title=title,
                                     extra_label=self.extra_label(),
                                     default_item=self.default, **self.dargs)

        if code in (dialog.DIALOG_CANCEL, dialog.DIALOG_ESC):
            return self.PREV

        self.answer = self.validate(output)
        self.default = output

        return self.NEXT


class WizardPageWthChoices(WizardPage):
    """Represents a Wizard Page that allows the user to select something from
    a list of choices.

    The available choices are created by a function passed to the class through
    the choices variable. If the choices function returns an empty list, a
    fallback function is executed if available.
    """
    def __init__(self, name, text, choices, **kwargs):
        """Initialize the WizardPageWthChoices instance"""
        super(WizardPageWthChoices, self).__init__(name, text, **kwargs)
        self.choices = choices
        self.fallback = kwargs['fallback'] if 'fallback' in kwargs else None


class WizardRadioListPage(WizardPageWthChoices):
    """Represent a Radio List in a wizard"""

    def show(self, dialog, title):
        """Display this wizard page"""
        choices = []
        for choice in self.choices():
            default = 1 if choice[0] == self.default else 0
            choices.append((choice[0], choice[1], default))

        (code, answer) = dialog.radiolist(self.text(), choices=choices,
                                          extra_label=self.extra_label(),
                                          title=title, **self.dargs)

        if code in (dialog.DIALOG_CANCEL, dialog.DIALOG_ESC):
            return self.PREV

        self.answer = self.validate(answer)
        self.default = answer

        return self.NEXT


class WizardMenuPage(WizardPageWthChoices):
    """Represents a menu dialog with available choices in a wizard"""

    def show(self, dialog, title):
        """Display this wizard page"""

        choices = self.choices()

        if len(choices) == 0:
            assert self.fallback, "Zero choices and no fallback"
            if self.fallback():
                raise WizardReloadPage
            else:
                return self.PREV

        default_item = self.default if self.default else choices[0][0]

        (code, choice) = dialog.menu(self.text(), title=title, choices=choices,
                                     extra_label=self.extra_label(),
                                     default_item=default_item, **self.dargs)

        if code in (dialog.DIALOG_CANCEL, dialog.DIALOG_ESC):
            return self.PREV
        elif code == dialog.DIALOG_EXTRA:
            self.extra()
            raise WizardReloadPage

        self.answer = self.validate(choice)
        self.default = choice

        return self.NEXT


def start_wizard(session):
    """Run the image creation wizard"""

    metadata = session['image'].meta
    distro = session['image'].distro
    ostype = session['image'].ostype

    # Create Cloud Wizard Page
    def cloud_choices():
        """Returns the available clouds"""
        choices = []
        for (name, cloud) in Kamaki.get_clouds().items():
            descr = cloud['description'] if 'description' in cloud else ''
            choices.append((name, descr))

        return choices

    def no_clouds():
        """Fallback function when no cloud account exists"""
        if not session['dialog'].yesno(
                "No available clouds found. Would you like to add one now?",
                width=PAGE_WIDTH, defaultno=0):
            return add_cloud(session)
        return False

    def cloud_validate(cloud):
        """Checks if a cloud is valid"""
        if not Kamaki.get_account(cloud):
            if not session['dialog'].yesno(
                    "The cloud you have selected is not valid! Would you "
                    "like to edit it now?", width=PAGE_WIDTH, defaultno=0):
                if edit_cloud(session, cloud):
                    return cloud
            raise WizardReloadPage
        return cloud

    cloud = WizardMenuPage(
        "Cloud", lambda:
        "Please select a cloud account or press <Add> to add a new one:",
        cloud_choices, extra_label=lambda: "Add",
        extra=lambda: add_cloud(session), title="Clouds",
        validate=cloud_validate, fallback=no_clouds)

    # Create Image Name Wizard Page
    name = WizardInputPage("ImageName", lambda:
                           "Please provide a name for the image:",
                           default=ostype if distro == "unknown" else distro)

    # Create Image Description Wizard Page
    descr = WizardInputPage(
        "ImageDescription", lambda:
        "Please provide a description for the image:",
        default=metadata['DESCRIPTION'] if 'DESCRIPTION' in metadata else '')

    # Create VirtIO Installation Page
    def display_installed_drivers():
        """Returns the installed VirtIO drivers"""
        image = session['image']
        versions = virtio_versions(image.os.virtio_state)

        ret = "Installed Block Device Driver:  %(netkvm)s\n" \
              "Installed Network Device Driver: %(viostor)s\n" % versions

        virtio = image.os.sysprep_params['virtio'].value
        if virtio:
            ret += "\nBlock Device Driver to be installed:   %(netkvm)s\n" \
                   "Network Device Driver to be installed: %(viostor)s\n" % \
                   virtio_versions(image.os.compute_virtio_state(virtio))
        return ret

    def validate_virtio(_):
        """Checks the state of the VirtIO drivers"""
        image = session['image']
        netkvm = len(image.os.virtio_state['netkvm']) != 0
        viostor = len(image.os.virtio_state['viostor']) != 0
        drv_dir = image.os.sysprep_params['virtio'].value

        if netkvm is False or viostor is False:
            new = image.os.compute_virtio_state(drv_dir) if drv_dir else None
            new_viostor = len(new['viostor']) != 0 if new else False
            new_netkvm = len(new['netkvm']) != 0 if new else False

            dialog = session['dialog']
            title = "VirtIO driver missing"
            msg = "Image creation cannot proceed unless a VirtIO %s driver " \
                  "is installed on the media!"
            if not (viostor or new_viostor):
                dialog.msgbox(msg % "Block Device", width=PAGE_WIDTH,
                              height=PAGE_HEIGHT, title=title)
                raise WizardReloadPage
            if not(netkvm or new_netkvm):
                dialog.msgbox(msg % "Network Device", width=PAGE_WIDTH,
                              height=PAGE_HEIGHT, title=title)
                raise WizardReloadPage

        return drv_dir

    def virtio_text():
        if not session['image'].os.sysprep_params['virtio'].value:
            return "Press <New> to update the image's VirtIO drivers."
        else:
            return "Press <Revert> to revert to the old state."

    def virtio_extra():
        if not session['image'].os.sysprep_params['virtio'].value:
            title = "Please select a directory that hosts VirtIO drivers."
            update_sysprep_param(session, 'virtio', title=title)
        else:
            session['image'].os.sysprep_params['virtio'].value = ""

    def virtio_extra_label():
        if not session['image'].os.sysprep_params['virtio'].value:
            return "New"
        else:
            return "Revert"

    virtio = WizardInfoPage(
        "virtio", virtio_text, display_installed_drivers,
        title="VirtIO Drivers", extra_label=virtio_extra_label,
        extra=virtio_extra, validate=validate_virtio,
        print_name="VirtIO Drivers Path")

    # Create Image Registration Wizard Page
    def registration_choices():
        """Choices for the registration wizard page"""
        return [("Private", "Image is accessible only by this user"),
                ("Public", "Everyone can create VMs from this image")]

    registration = WizardRadioListPage("RegistrationType", lambda:
                                       "Please provide a registration type:",
                                       registration_choices, default="Private")

    wizard = Wizard(session['dialog'])

    wizard.add_page(cloud)
    wizard.add_page(name)
    wizard.add_page(descr)
    if hasattr(session['image'].os, 'install_virtio_drivers'):
        wizard.add_page(virtio)
    wizard.add_page(registration)

    if wizard.run():
        create_image(session, wizard.answers)
    else:
        return False

    return True


def create_image(session, answers):
    """Create an image using the information collected by the wizard"""
    image = session['image']

    with_progress = OutputWthProgress(True)
    image.out.append(with_progress)
    try:
        image.out.clear()

        if 'virtio' in answers and image.os.sysprep_params['virtio'].value:
            image.os.install_virtio_drivers()

        # Sysprep
        image.os.do_sysprep()
        metadata = image.os.meta

        update_background_title(session)

        metadata['DESCRIPTION'] = answers['ImageDescription']

        # MD5
        session['checksum'] = image.md5()

        image.out.output()
        try:
            image.out.output("Uploading image to the cloud:")
            account = Kamaki.get_account(answers['Cloud'])
            assert account, "Cloud: %s is not valid" % answers['Cloud']
            kamaki = Kamaki(account, image.out)

            name = "%s-%s.diskdump" % (answers['ImageName'],
                                       time.strftime("%Y%m%d%H%M"))
            with image.raw_device() as raw:
                with open(raw, 'rb') as device:
                    remote = kamaki.upload(device, image.size, name,
                                           "(1/3)  Calculating block hashes",
                                           "(2/3)  Uploading image blocks")

            image.out.output("(3/3)  Uploading md5sum file ...", False)
            md5sumstr = '%s %s\n' % (session['checksum'], name)
            kamaki.upload(StringIO.StringIO(md5sumstr), size=len(md5sumstr),
                          remote_path="%s.%s" % (name, 'md5sum'))
            image.out.success('done')
            image.out.output()

            image.out.output('Registering %s image with the cloud ...' %
                             answers['RegistrationType'].lower(), False)
            result = kamaki.register(answers['ImageName'], remote, metadata,
                                     answers['RegistrationType'] == "Public")
            image.out.success('done')
            image.out.output("Uploading metadata file ...", False)
            metastring = unicode(json.dumps(result, ensure_ascii=False))
            kamaki.upload(StringIO.StringIO(metastring), size=len(metastring),
                          remote_path="%s.%s" % (name, 'meta'))
            image.out.success('done')

            if answers['RegistrationType'] == "Public":
                image.out.output("Sharing md5sum file ...", False)
                kamaki.share("%s.md5sum" % name)
                image.out.success('done')
                image.out.output("Sharing metadata file ...", False)
                kamaki.share("%s.meta" % name)
                image.out.success('done')

            image.out.output()

        except ClientError as error:
            raise FatalError("Storage service client: %d %s" %
                             (error.status, error.message))
    finally:
        image.out.remove(with_progress)

    text = "The %s image was successfully uploaded to the storage service " \
           "and registered with the compute service of %s. Would you like " \
           "to keep a local copy?" % \
           (answers['RegistrationType'].lower(), answers['Cloud'])

    if not session['dialog'].yesno(text, width=PAGE_WIDTH):
        extract_image(session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
