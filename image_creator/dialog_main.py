#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2015 GRNET S.A.
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

from __future__ import unicode_literals

import dialog
import sys
import os
import signal
import argparse
import types
import termios
import traceback
import tempfile

from image_creator import __version__ as version
from image_creator.util import FatalError
from image_creator.output.cli import SimpleOutput
from image_creator.output.dialog import GaugeOutput
from image_creator.output.composite import CompositeOutput
from image_creator.output.syslog import SyslogOutput
from image_creator.disk import Disk
from image_creator.dialog_wizard import start_wizard
from image_creator.dialog_menu import main_menu
from image_creator.dialog_util import WIDTH, confirm_exit, Reset, \
    update_background_title, select_file

PROGNAME = os.path.basename(sys.argv[0])


def create_image(d, media, out, tmp, snapshot):
    """Create an image out of `media'"""
    d.setBackgroundTitle('snf-image-creator')

    gauge = GaugeOutput(d, "Initialization", "Initializing...")
    out.append(gauge)
    disk = Disk(media, out, tmp)

    def signal_handler(signum, frame):
        gauge.cleanup()
        disk.cleanup()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:

        device = disk.file if not snapshot else disk.snapshot()

        image = disk.get_image(device)

        gauge.cleanup()
        out.remove(gauge)

        # Make sure the signal handler does not call gauge.cleanup again
        def dummy(self):
            pass
        gauge.cleanup = type(GaugeOutput.cleanup)(dummy, gauge, GaugeOutput)

        session = {"dialog": d,
                   "disk": disk,
                   "image": image}

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

            if d.yesno(msg, width=WIDTH, defaultno=1, height=12) == d.OK:
                main_menu(session)

            d.infobox("Thank you for using snf-image-creator. Bye", width=53)
            return 0

        msg = "snf-image-creator detected a %s system on the input media. " \
              "Would you like to run a wizard to assist you through the " \
              "image creation process?\n\nChoose <Wizard> to run the wizard," \
              " <Expert> to run snf-image-creator in expert mode or press " \
              "ESC to quit the program." \
              % (image.ostype.capitalize() if image.ostype == image.distro or
                 image.distro == "unknown" else "%s (%s)" %
                 (image.ostype.capitalize(), image.distro.capitalize()))

        update_background_title(session)

        while True:
            code = d.yesno(msg, width=WIDTH, height=12, yes_label="Wizard",
                           no_label="Expert")
            if code == d.OK:
                if start_wizard(session):
                    break
            elif code == d.CANCEL:
                main_menu(session)
                break

            if confirm_exit(d):
                break

        d.infobox("Thank you for using snf-image-creator. Bye", width=53)
    finally:
        disk.cleanup()

    return 0


def _dialog_form(self, text, elements, height=20, width=60, form_height=15,
                 **kwargs):
    """Display a form box.
       Each element of *elements* must itself be a sequence
       :samp:`({label}, {yl}, {xl}, {item}, {yi}, {xi}, {field_length},
       {input_length})` containing the various parameters concerning a
       given field and the associated label.
       *label* is a string that will be displayed at row *yl*, column
       *xl*. *item* is a string giving the initial value for the field,
       which will be displayed at row *yi*, column *xi* (row and column
       numbers starting from 1).
       *field_length* and *input_length* are integers that respectively
       specify the number of characters used for displaying the field
       and the maximum number of characters that can be entered for
       this field. These two integers also determine whether the
       contents of the field can be modified, as follows:
         - if *field_length* is zero, the field cannot be altered and
           its contents determines the displayed length;
         - if *field_length* is negative, the field cannot be altered
           and the opposite of *field_length* gives the displayed
           length;
         - if *input_length* is zero, it is set to *field_length*.
    """

    cmd = ["--form", text, str(height), str(width), str(form_height)]

    for element in elements:
        label, yl, xl, item, yi, xi, field_len, input_len = element[:8]

        cmd.extend((label, unicode(yl), unicode(xl), item, unicode(yi),
                    unicode(xi), unicode(field_len), unicode(input_len)))

    code, output = self._perform(*(cmd,), **kwargs)

    if not output:
        return (code, [])

    return (code, output.splitlines())


def dialog_main(media, **kwargs):
    """Main function for the dialog-based version of the program"""

    tmpdir = kwargs['tmpdir'] if 'tmpdir' in kwargs else None
    snapshot = kwargs['snapshot'] if 'snapshot' in kwargs else True
    logfile = kwargs['logfile'] if 'logfile' in kwargs else None
    syslog = kwargs['syslog'] if 'syslog' in kwargs else False

    # In openSUSE dialog is buggy under xterm
    if os.environ['TERM'] == 'xterm':
        os.environ['TERM'] = 'linux'

    d = dialog.Dialog(dialog="dialog")

    # Add extra button in dialog library if missing
    if 'extra_button' not in dialog._common_args_syntax:
        dialog._common_args_syntax["extra_button"] = \
            lambda enable: dialog._simple_option("--extra-button", enable)
    if 'extra_label' not in dialog._common_args_syntax:
        dialog._common_args_syntax["extra_label"] = \
            lambda string: ("--extra-label", string)

    # Allow yes-no label overwriting if missing
    if 'yes_label' not in dialog._common_args_syntax:
        dialog._common_args_syntax["yes_label"] = \
            lambda string: ("--yes-label", string)
    if 'no_label' not in dialog._common_args_syntax:
        dialog._common_args_syntax["no_label"] = \
            lambda string: ("--no-label", string)

    # Add exit label overwriting if missing
    if 'exit_label' not in dialog._common_args_syntax:
        dialog._common_args_syntax["exit_label"] = \
            lambda string: ("--exit-label", string)

    # Monkey-patch pythondialog to include support for form dialog boxes
    if not hasattr(d, 'form'):
        d.form = types.MethodType(_dialog_form, d)

    # Add sort dialog constants if missing
    if not hasattr(d, 'OK'):
        d.OK = d.DIALOG_OK

    if not hasattr(d, 'CANCEL'):
        d.CANCEL = d.DIALOG_CANCEL

    if not hasattr(d, 'ESC'):
        d.ESC = d.DIALOG_ESC

    if not hasattr(d, 'EXTRA'):
        d.EXTRA = d.DIALOG_EXTRA

    if not hasattr(d, 'HELP'):
        d.HELP = d.DIALOG_HELP

    d.setBackgroundTitle('snf-image-creator')

    # Pick input media
    while True:
        media = select_file(d, init=media, ftype="br", bundle_host=True,
                            title="Please select an input media.")
        if media is None:
            if confirm_exit(
                    d, "You canceled the media selection dialog box."):
                return 0
            continue
        break

    tmplog = None if logfile else tempfile.NamedTemporaryFile(prefix='fatal-',
                                                              delete=False)

    logs = []
    try:
        stream = logfile if logfile else tmplog
        logs.append(SimpleOutput(colored=False, stderr=stream, stdout=stream,
                                 timestamp=True))
        if syslog:
            logs.append(SyslogOutput())

        while 1:
            try:
                out = CompositeOutput(logs)
                out.info("Starting %s v%s ..." % (PROGNAME, version))
                ret = create_image(d, media, out, tmpdir, snapshot)
                break
            except Reset:
                for log in logs:
                    log.info("Resetting everything ...")
    except FatalError as error:
        for log in logs:
            log.error(str(error))
        msg = 'A fatal error occured. See %s for a full log.' % log.stderr.name
        d.infobox(msg, width=WIDTH, title="Fatal Error")
        return 1
    else:
        if tmplog:
            os.unlink(tmplog.name)
    finally:
        if tmplog:
            tmplog.close()

    return ret


def main():
    """Entrance Point"""
    if os.geteuid() != 0:
        sys.stderr.write("Error: You must run %s as root\n" % PROGNAME)
        sys.exit(2)

    description = "Dialog-based tool for creating OS images"
    parser = argparse.ArgumentParser(version=version, description=description)
    parser.add_argument("-l", "--logfile", dest="logfile", metavar="FILE",
                        default=None, help="log all messages to FILE")
    parser.add_argument("--no-snapshot", dest="snapshot", default=True,
                        help="don't snapshot the input media. (THIS IS "
                        "DANGEROUS AS IT WILL ALTER THE ORIGINAL MEDIA!!!)",
                        action="store_false")
    parser.add_argument("--syslog", dest="syslog", default=False,
                        help="log to syslog", action="store_true")
    parser.add_argument("--tmpdir", dest="tmp", default=None, metavar="DIR",
                        help="create large temporary image files under DIR")
    parser.add_argument("source", metavar="SOURCE", default=None, nargs='?',
                        help="Image file, block device or /")

    opts = parser.parse_args()

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
            ret = dialog_main(opts.source, logfile=logfile, tmpdir=opts.tmp,
                              snapshot=opts.snapshot, syslog=opts.syslog)
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
