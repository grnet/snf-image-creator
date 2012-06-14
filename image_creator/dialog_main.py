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
import sys
import os
import textwrap
import signal

from image_creator import __version__ as version
from image_creator.util import FatalError, MD5
from image_creator.output.dialog import InitializationOutput
from image_creator.disk import Disk
from image_creator.os_type import os_cls

MSGBOX_WIDTH = 60
YESNO_WIDTH = 50
MENU_WIDTH = 70


class Reset(Exception):
    pass


def confirm_exit(d, msg=''):
    return not d.yesno("%s Do you want to exit?" % msg, width=YESNO_WIDTH)


def confirm_reset(d):
    return not d.yesno(
        "Are you sure you want to reset everything?",
        width=YESNO_WIDTH)


def upload_image(session):
    d = session["dialog"]

    if "account" not in session:
        d.msgbox("You need to provide your ~okeanos login username before you "
                 "can upload images to pithos+", width=MSGBOX_WIDTH)
        return False

    if "token" not in session:
        d.msgbox("You need to provide your ~okeanos account authentication "
                 "token before you can upload images to pithos+",
                 width=MSGBOX_WIDTH)
        return False

    while 1:
        (code, answer) = d.inputbox("Please provide a filename:",
                        init=session["upload"] if "upload" in session else '')
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        answer = answer.strip()
        if len(answer) == 0:
            d.msgbox("Filename cannot be empty", width=MSGBOX_WIDTH)
            continue

        session["upload"] = answer
        return True


def register_image(session):
    d = session["dialog"]

    if "account" not in session:
        d.msgbox("You need to provide your ~okeanos login username before you "
                 "can register an images to cyclades",
                 width=MSGBOX_WIDTH)
        return False

    if "token" not in session:
        d.msgbox("You need to provide your ~okeanos account authentication "
                 "token before you can register an images to cyclades",
                 width=MSGBOX_WIDTH)
        return False

    if "upload" not in session:
        d.msgbox("You need to have an image uploaded to pithos+ before you "
                 "can register it to cyclades",
                 width=MSGBOX_WIDTH)
        return False

    return True


def kamaki_menu(session):
    d = session['dialog']
    default_item = "Account"
    while 1:
        account = session["account"] if "account" in session else "<none>"
        token = session["token"] if "token" in session else "<none>"
        upload = session["upload"] if "upload" in session else "<none>"
        (code, choice) = d.menu(
            "Choose one of the following or press <Back> to go back.",
            width=MENU_WIDTH,
            choices=[("Account", "Change your ~okeanos username: %s" %
                      account),
                     ("Token", "Change your ~okeanos token: %s" %
                      token),
                     ("Upload", "Upload image to pithos+"),
                     ("Register", "Register image to cyclades: %s" % upload)],
            cancel="Back",
            default_item=default_item,
            title="Image Registration Menu")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        if choice == "Account":
            default_item = "Account"
            (code, answer) = d.inputbox(
                "Please provide your ~okeanos account e-mail address:",
                init=session["account"] if "account" in session else '',
                width=70)
            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                continue
            if len(answer) == 0 and "account" in session:
                    del session["account"]
            else:
                session["account"] = answer.strip()
                default_item = "Token"
        elif choice == "Token":
            default_item = "Token"
            (code, answer) = d.inputbox(
                "Please provide your ~okeanos account authetication token:",
                init=session["token"] if "token" in session else '',
                width=70)
            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                continue
            if len(answer) == 0 and "token" in session:
                del session["token"]
            else:
                session["token"] = answer.strip()
                default_item = "Upload"
        elif choice == "Upload":
            if upload_image(session):
                default_item = "Register"
            else:
                default_item = "Upload"
        elif choice == "Register":
            if register_image(session):
                return True
            else:
                default_item = "Register"


def main_menu(session):
    d = session['dialog']
    dev = session['device']
    d.setBackgroundTitle("OS: %s, Distro: %s" % (dev.ostype, dev.distro))
    actions = {"Register": kamaki_menu}
    default_item = "Customize"

    while 1:
        (code, choice) = d.menu(
            "Choose one of the following or press <Exit> to exit.",
            width=MENU_WIDTH,
            choices=[("Customize", "Run various image customization tasks"),
                     ("Deploy", "Configure ~okeanos image deployment options"),
                     ("Register", "Register image to ~okeanos"),
                     ("Extract", "Dump image to local file system"),
                     ("Reset", "Reset everything and start over again"),
                     ("Help", "Get help for using snf-image-creator")],
            cancel="Exit",
            default_item=default_item,
            title="Image Creator for ~okeanos (snf-image-creator version %s)" %
                  version)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            if confirm_exit(d):
                break
            else:
                continue

        if choice == "Reset":
            if confirm_reset(d):
                d.infobox("Resetting snf-image-creator. Please wait...")
                raise Reset
            else:
                continue
        elif choice in actions:
            actions[choice](session)


def select_file(d):
    root = os.sep
    while 1:
        (code, path) = d.fselect(root, 10, 50,
                                 title="Please select input media")
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            if confirm_exit(d, "You canceled the media selection dialog box."):
                sys.exit(0)
            else:
                continue

        if not os.path.exists(path):
            d.msgbox("The file you choose does not exist", width=MSGBOX_WIDTH)
            continue
        else:
            break

    return path


def collect_metadata(dev, out):

    dev.mount(readonly=True)
    out.output("Collecting image metadata...")
    cls = os_cls(dev.distro, dev.ostype)
    image_os = cls(dev.root, dev.g, out)
    out.success("done")
    dev.umount()

    return image_os.meta


def image_creator(d):
    basename = os.path.basename(sys.argv[0])
    usage = "Usage: %s [input_media]" % basename
    if len(sys.argv) > 2:
        sys.stderr.write("%s\n" % usage)
        return 1

    if os.geteuid() != 0:
        raise FatalError("You must run %s as root" % basename)

    media = sys.argv[1] if len(sys.argv) == 2 else select_file(d)

    out = InitializationOutput(d)
    disk = Disk(media, out)

    def signal_handler(signum, fram):
        out.cleanup()
        disk.cleanup()

    signal.signal(signal.SIGINT, signal_handler)
    try:
        snapshot = disk.snapshot()
        dev = disk.get_device(snapshot)

        metadata = collect_metadata(dev, out)
        out.cleanup()

        # Make sure the signal handler does not call out.cleanup again
        def dummy(self):
            pass
        instancemethod = type(InitializationOutput.cleanup)
        out.cleanup = instancemethod(dummy, out, InitializationOutput)

        session = {"dialog": d,
                   "disk": disk,
                   "device": dev,
                   "metadata": metadata}

        main_menu(session)
        d.infobox("Thank you for using snf-image-creator. Bye", width=53)
    finally:
        disk.cleanup()

    return 0


def main():

    d = dialog.Dialog(dialog="dialog")

    while 1:
        try:
            try:
                ret = image_creator(d)
                sys.exit(ret)
            except FatalError as e:
                msg = textwrap.fill(str(e), width=70)
                d.infobox(msg, width=70, title="Fatal Error")
                sys.exit(1)
        except Reset:
            continue

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
