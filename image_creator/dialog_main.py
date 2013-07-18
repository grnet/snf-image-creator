#!/usr/bin/env python
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

"""This module is the entrance point for the dialog-based version of the
snf-image-creator program. The main function will create a dialog where the
user is asked if he wants to use the program in expert or wizard mode.
"""

import dialog
import sys
import os
import stat
import textwrap
import signal
import optparse
import types

from image_creator import __version__ as version
from image_creator.util import FatalError
from image_creator.output import Output
from image_creator.output.cli import SimpleOutput
from image_creator.output.dialog import GaugeOutput
from image_creator.output.composite import CompositeOutput
from image_creator.disk import Disk
from image_creator.dialog_wizard import start_wizard
from image_creator.dialog_menu import main_menu
from image_creator.dialog_util import SMALL_WIDTH, WIDTH, confirm_exit, \
    Reset, update_background_title


def create_image(d, media, out, tmp):
    """Create an image out of `media'"""
    d.setBackgroundTitle('snf-image-creator')

    gauge = GaugeOutput(d, "Initialization", "Initializing...")
    out.add(gauge)
    disk = Disk(media, out, tmp)

    def signal_handler(signum, frame):
        gauge.cleanup()
        disk.cleanup()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:
        snapshot = disk.snapshot()
        image = disk.get_image(snapshot)

        out.output("Collecting image metadata ...")
        metadata = {}
        for (key, value) in image.meta.items():
            metadata[str(key)] = str(value)

        for (key, value) in image.os.meta.items():
            metadata[str(key)] = str(value)

        out.success("done")
        gauge.cleanup()
        out.remove(gauge)

        # Make sure the signal handler does not call gauge.cleanup again
        def dummy(self):
            pass
        gauge.cleanup = type(GaugeOutput.cleanup)(dummy, gauge, GaugeOutput)

        session = {"dialog": d,
                   "disk": disk,
                   "image": image,
                   "metadata": metadata}

        msg = "snf-image-creator detected a %s system on the input media. " \
              "Would you like to run a wizard to assist you through the " \
              "image creation process?\n\nChoose <Wizard> to run the wizard," \
              " <Expert> to run the snf-image-creator in expert mode or " \
              "press ESC to quit the program." \
              % (image.ostype if image.ostype == image.distro or
                 image.distro == "unknown" else "%s (%s)" %
                 (image.ostype, image.distro))

        update_background_title(session)

        while True:
            code = d.yesno(msg, width=WIDTH, height=12, yes_label="Wizard",
                           no_label="Expert")
            if code == d.DIALOG_OK:
                if start_wizard(session):
                    break
            elif code == d.DIALOG_CANCEL:
                main_menu(session)
                break

            if confirm_exit(d):
                break

        d.infobox("Thank you for using snf-image-creator. Bye", width=53)
    finally:
        disk.cleanup()

    return 0


def select_file(d, media):
    """Select a media file"""
    if media == '/':
        return '/'

    default = os.getcwd() + os.sep
    while 1:
        if media is not None:
            if not os.path.exists(media):
                d.msgbox("The file `%s' you choose does not exist." % media,
                         width=SMALL_WIDTH)
            else:
                mode = os.stat(media).st_mode
                if not stat.S_ISDIR(mode):
                    break
                default = media

        (code, media) = d.fselect(default, 10, 60, extra_button=1,
                                  title="Please select an input media.",
                                  extra_label="Bundle Host")
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            if confirm_exit(d, "You canceled the media selection dialog box."):
                sys.exit(0)
            else:
                media = None
                continue
        elif code == d.DIALOG_EXTRA:
            return '/'

    return media


def _dialog_form(self, text, height=20, width=60, form_height=15, fields=[],
                 **kwargs):
    """Display a form box.

    fields is in the form: [(label1, item1, item_length1), ...]
    """

    cmd = ["--form", text, str(height), str(width), str(form_height)]

    label_len = 0
    for field in fields:
        if len(field[0]) > label_len:
            label_len = len(field[0])

    input_len = width - label_len - 1

    line = 1
    for field in fields:
        label = field[0]
        item = field[1]
        item_len = field[2]
        cmd.extend((label, str(line), str(1), item, str(line),
                   str(label_len + 1), str(input_len), str(item_len)))
        line += 1

    code, output = self._perform(*(cmd,), **kwargs)

    if not output:
        return (code, [])

    return (code, output.splitlines())


def main():

    # In OpenSUSE dialog is buggy under xterm
    if os.environ['TERM'] == 'xterm':
        os.environ['TERM'] = 'linux'

    d = dialog.Dialog(dialog="dialog")

    # Add extra button in dialog library
    dialog._common_args_syntax["extra_button"] = \
        lambda enable: dialog._simple_option("--extra-button", enable)

    dialog._common_args_syntax["extra_label"] = \
        lambda string: ("--extra-label", string)

    # Allow yes-no label overwriting
    dialog._common_args_syntax["yes_label"] = \
        lambda string: ("--yes-label", string)

    dialog._common_args_syntax["no_label"] = \
        lambda string: ("--no-label", string)

    # Monkey-patch pythondialog to include support for form dialog boxes
    if not hasattr(dialog, 'form'):
        d.form = types.MethodType(_dialog_form, d)

    usage = "Usage: %prog [options] [<input_media>]"
    parser = optparse.OptionParser(version=version, usage=usage)
    parser.add_option("-l", "--logfile", type="string", dest="logfile",
                      default=None, help="log all messages to FILE",
                      metavar="FILE")
    parser.add_option("--tmpdir", type="string", dest="tmp", default=None,
                      help="create large temporary image files under DIR",
                      metavar="DIR")

    options, args = parser.parse_args(sys.argv[1:])

    if len(args) > 1:
        parser.error("Wrong number of arguments")

    d.setBackgroundTitle('snf-image-creator')

    try:
        if os.geteuid() != 0:
            raise FatalError("You must run %s as root" %
                             parser.get_prog_name())

        if options.tmp is not None and not os.path.isdir(options.tmp):
            raise FatalError("The directory `%s' specified with --tmpdir is "
                             "not valid" % options.tmp)

        logfile = None
        if options.logfile is not None:
            try:
                logfile = open(options.logfile, 'w')
            except IOError as e:
                raise FatalError(
                    "Unable to open logfile `%s' for writing. Reason: %s" %
                    (options.logfile, e.strerror))

        media = select_file(d, args[0] if len(args) == 1 else None)

        try:
            log = SimpleOutput(False, logfile) if logfile is not None \
                else Output()
            while 1:
                try:
                    out = CompositeOutput([log])
                    out.output("Starting %s v%s ..." %
                               (parser.get_prog_name(), version))
                    ret = create_image(d, media, out, options.tmp)
                    sys.exit(ret)
                except Reset:
                    log.output("Resetting everything ...")
                    continue
        finally:
            if logfile is not None:
                logfile.close()
    except FatalError as e:
        msg = textwrap.fill(str(e), width=WIDTH)
        d.infobox(msg, width=WIDTH, title="Fatal Error")
        sys.exit(1)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
