#!/usr/bin/env python
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

"""This module is the entrance point for the dialog-based version of the
snf-image-creator program. The main function will create a dialog where the
user is asked if he wants to use the program in expert or wizard mode.
"""

import dialog
import sys
import os
import textwrap
import signal
import optparse
import types
import termios
import traceback

from image_creator import __version__ as version
from image_creator.util import FatalError
from image_creator.output import Output
from image_creator.output.cli import SimpleOutput
from image_creator.output.dialog import GaugeOutput
from image_creator.output.composite import CompositeOutput
from image_creator.disk import Disk
from image_creator.dialog_wizard import start_wizard
from image_creator.dialog_menu import main_menu
from image_creator.dialog_util import WIDTH, confirm_exit, Reset, \
    update_background_title, select_file

PROGNAME = os.path.basename(sys.argv[0])


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
        # There is no need to snapshot the media if it was created by the Disk
        # instance as a temporary object.
        device = disk.device if disk.source == '/' else disk.snapshot()

        image = disk.get_image(device)

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

        if image.is_unsupported():

            session['excluded_tasks'] = [-1]
            session['task_metadata'] = ["EXCLUDE_ALL_TASKS"]

            msg = "The system on the input media is not supported." \
                "\n\nReason: %s\n\n" \
                "We highly recommend not to create an image out of this, " \
                "since the image won't be cleaned up and you will not be " \
                "able to configure it during the deployment. Press <YES> if " \
                "you still want to continue with the image creation process." \
                % image._unsupported

            if not d.yesno(msg, width=WIDTH, defaultno=1, height=12):
                main_menu(session)

            d.infobox("Thank you for using snf-image-creator. Bye", width=53)
            return 0

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


def dialog_main(media, logfile, tmpdir):

    # In openSUSE dialog is buggy under xterm
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

    d.setBackgroundTitle('snf-image-creator')

    try:
        while True:
            media = select_file(d, init=media, ftype="br", bundle_host=True,
                                title="Please select an input media.")
            if media is None:
                if confirm_exit(
                        d, "You canceled the media selection dialog box."):
                    return 0
                continue
            break

        log = SimpleOutput(False, logfile) if logfile is not None else Output()
        while 1:
            try:
                out = CompositeOutput([log])
                out.output("Starting %s v%s ..." % (PROGNAME, version))
                return create_image(d, media, out, tmpdir)
            except Reset:
                log.output("Resetting everything ...")
                continue
    except FatalError as error:
        msg = textwrap.fill(str(error), width=WIDTH-4)
        d.infobox(msg, width=WIDTH, title="Fatal Error")
        return 1


def main():
    """Entrance Point"""
    if os.geteuid() != 0:
        sys.stderr.write("Error: You must run %s as root\n" % PROGNAME)
        sys.exit(2)

    usage = "Usage: %prog [options] [<input_media>]"
    parser = optparse.OptionParser(version=version, usage=usage)
    parser.add_option("-l", "--logfile", type="string", dest="logfile",
                      default=None, help="log all messages to FILE",
                      metavar="FILE")
    parser.add_option("--tmpdir", type="string", dest="tmp", default=None,
                      help="create large temporary image files under DIR",
                      metavar="DIR")

    opts, args = parser.parse_args(sys.argv[1:])

    if len(args) > 1:
        parser.error("Wrong number of arguments")

    media = args[0] if len(args) == 1 else None

    if opts.tmp is not None and not os.path.isdir(opts.tmp):
        parser.error("Directory: `%s' specified with --tmpdir is not valid"
                     % opts.tmp)

    try:
        logfile = open(opts.logfile, 'w') if opts.logfile is not None else None
    except IOError as error:
        parser.error("Unable to open logfile `%s' for writing. Reason: %s" %
                     (opts.logfile, error.strerror))

    try:
        # Save the terminal attributes
        attr = termios.tcgetattr(sys.stdin.fileno())
        try:
            ret = dialog_main(media, logfile, opts.tmp)
        finally:
            # Restore the terminal attributes. If an error occurs make sure
            # that the terminal turns back to normal.
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, attr)
    except:
        # Clear the screen
        sys.stdout.write('\033[2J')  # Erase Screen
        sys.stdout.write('\033[H')  # Cursor Home
        sys.stdout.flush()

        exception = traceback.format_exc()
        sys.stderr.write(exception)
        if logfile is not None:
            logfile.write(exception)

        sys.exit(3)
    finally:
        if logfile is not None:
            logfile.close()

    sys.exit(ret)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
