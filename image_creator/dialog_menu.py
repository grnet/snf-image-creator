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

import sys
import os
import textwrap
import StringIO

from image_creator import __version__ as version
from image_creator.util import MD5
from image_creator.output.dialog import GaugeOutput, InfoBoxOutput
from image_creator.kamaki_wrapper import Kamaki, ClientError
from image_creator.help import get_help_file
from image_creator.dialog_util import SMALL_WIDTH, WIDTH, \
    update_background_title, confirm_reset, confirm_exit, Reset, \
    extract_image, extract_metadata_string

CONFIGURATION_TASKS = [
    ("Partition table manipulation", ["FixPartitionTable"],
        ["linux", "windows"]),
    ("File system resize",
        ["FilesystemResizeUnmounted", "FilesystemResizeMounted"],
        ["linux", "windows"]),
    ("Swap partition configuration", ["AddSwap"], ["linux"]),
    ("SSH keys removal", ["DeleteSSHKeys"], ["linux"]),
    ("Temporal RDP disabling", ["DisableRemoteDesktopConnections"],
        ["windows"]),
    ("SELinux relabeling at next boot", ["SELinuxAutorelabel"], ["linux"]),
    ("Hostname/Computer Name assignment", ["AssignHostname"],
        ["windows", "linux"]),
    ("Password change", ["ChangePassword"], ["windows", "linux"]),
    ("File injection", ["EnforcePersonality"], ["windows", "linux"])
]


class metadata_monitor(object):
    def __init__(self, session, meta):
        self.session = session
        self.meta = meta

    def __enter__(self):
        self.old = {}
        for (k, v) in self.meta.items():
            self.old[k] = v

    def __exit__(self, type, value, traceback):
        d = self.session['dialog']

        altered = {}
        added = {}

        for (k, v) in self.meta.items():
            if k not in self.old:
                added[k] = v
            elif self.old[k] != v:
                altered[k] = v

        if not (len(added) or len(altered)):
            return

        msg = "The last action has changed some image properties:\n\n"
        if len(added):
            msg += "New image properties:\n"
            for (k, v) in added.items():
                msg += '    %s: "%s"\n' % (k, v)
            msg += "\n"
        if len(altered):
            msg += "Updated image properties:\n"
            for (k, v) in altered.items():
                msg += '    %s: "%s" -> "%s"\n' % (k, self.old[k], v)
            msg += "\n"

        self.session['metadata'].update(added)
        self.session['metadata'].update(altered)
        d.msgbox(msg, title="Image Property Changes", width=SMALL_WIDTH)


def upload_image(session):
    d = session["dialog"]
    dev = session['device']
    size = dev.size

    if "account" not in session:
        d.msgbox("You need to provide your ~okeanos login username before you "
                 "can upload images to pithos+", width=SMALL_WIDTH)
        return False

    if "token" not in session:
        d.msgbox("You need to provide your ~okeanos account authentication "
                 "token before you can upload images to pithos+",
                 width=SMALL_WIDTH)
        return False

    while 1:
        init = session["upload"] if "upload" in session else ''
        (code, answer) = d.inputbox("Please provide a filename:", init=init,
                                    width=WIDTH)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        filename = answer.strip()
        if len(filename) == 0:
            d.msgbox("Filename cannot be empty", width=SMALL_WIDTH)
            continue
        session['upload'] = filename
        break

    gauge = GaugeOutput(d, "Image Upload", "Uploading...")
    try:
        out = dev.out
        out.add(gauge)
        try:
            if 'checksum' not in session:
                md5 = MD5(out)
                session['checksum'] = md5.compute(session['snapshot'], size)

            kamaki = Kamaki(session['account'], session['token'], out)
            try:
                # Upload image file
                with open(session['snapshot'], 'rb') as f:
                    session["pithos_uri"] = \
                        kamaki.upload(f, size, filename,
                                      "Calculating block hashes",
                                      "Uploading missing blocks")
                # Upload metadata file
                out.output("Uploading metadata file...")
                metastring = extract_metadata_string(session)
                kamaki.upload(StringIO.StringIO(metastring),
                              size=len(metastring),
                              remote_path="%s.meta" % filename)
                out.success("done")

                # Upload md5sum file
                out.output("Uploading md5sum file...")
                md5str = "%s %s\n" % (session['checksum'], filename)
                kamaki.upload(StringIO.StringIO(md5str), size=len(md5str),
                              remote_path="%s.md5sum" % filename)
                out.success("done")

            except ClientError as e:
                d.msgbox("Error in pithos+ client: %s" % e.message,
                         title="Pithos+ Client Error", width=SMALL_WIDTH)
                if 'pithos_uri' in session:
                    del session['pithos_uri']
                return False
        finally:
            out.remove(gauge)
    finally:
        gauge.cleanup()

    d.msgbox("Image file `%s' was successfully uploaded to pithos+" % filename,
             width=SMALL_WIDTH)

    return True


def register_image(session):
    d = session["dialog"]
    dev = session['device']

    if "account" not in session:
        d.msgbox("You need to provide your ~okeanos login username before you "
                 "can register an images to cyclades",
                 width=SMALL_WIDTH)
        return False

    if "token" not in session:
        d.msgbox("You need to provide your ~okeanos account authentication "
                 "token before you can register an images to cyclades",
                 width=SMALL_WIDTH)
        return False

    if "pithos_uri" not in session:
        d.msgbox("You need to upload the image to pithos+ before you can "
                 "register it to cyclades", width=SMALL_WIDTH)
        return False

    while 1:
        (code, answer) = d.inputbox("Please provide a registration name:",
                                    width=WIDTH)
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        name = answer.strip()
        if len(name) == 0:
            d.msgbox("Registration name cannot be empty", width=SMALL_WIDTH)
            continue
        break

    metadata = {}
    metadata.update(session['metadata'])
    if 'task_metadata' in session:
        for key in session['task_metadata']:
            metadata[key] = 'yes'

    gauge = GaugeOutput(d, "Image Registration", "Registering image...")
    try:
        out = dev.out
        out.add(gauge)
        try:
            out.output("Registering image with Cyclades...")
            try:
                kamaki = Kamaki(session['account'], session['token'], out)
                kamaki.register(name, session['pithos_uri'], metadata)
                out.success('done')
            except ClientError as e:
                d.msgbox("Error in pithos+ client: %s" % e.message)
                return False
        finally:
            out.remove(gauge)
    finally:
        gauge.cleanup()

    d.msgbox("Image `%s' was successfully registered with Cyclades as `%s'" %
             (session['upload'], name), width=SMALL_WIDTH)
    return True


def kamaki_menu(session):
    d = session['dialog']
    default_item = "Account"

    account = Kamaki.get_account()
    if account:
        session['account'] = account

    token = Kamaki.get_token()
    if token:
        session['token'] = token

    while 1:
        account = session["account"] if "account" in session else "<none>"
        token = session["token"] if "token" in session else "<none>"
        upload = session["upload"] if "upload" in session else "<none>"

        choices = [("Account", "Change your ~okeanos username: %s" % account),
                   ("Token", "Change your ~okeanos token: %s" % token),
                   ("Upload", "Upload image to pithos+"),
                   ("Register", "Register the image to cyclades: %s" % upload)]

        (code, choice) = d.menu(
            text="Choose one of the following or press <Back> to go back.",
            width=WIDTH, choices=choices, cancel="Back", height=13,
            menu_height=5, default_item=default_item,
            title="Image Registration Menu")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        if choice == "Account":
            default_item = "Account"
            (code, answer) = d.inputbox(
                "Please provide your ~okeanos account e-mail address:",
                init=session["account"] if "account" in session else '',
                width=WIDTH)
            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                continue
            if len(answer) == 0 and "account" in session:
                    del session["account"]
            else:
                session["account"] = answer.strip()
                Kamaki.save_account(session['account'])
                default_item = "Token"
        elif choice == "Token":
            default_item = "Token"
            (code, answer) = d.inputbox(
                "Please provide your ~okeanos account authetication token:",
                init=session["token"] if "token" in session else '',
                width=WIDTH)
            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                continue
            if len(answer) == 0 and "token" in session:
                del session["token"]
            else:
                session["token"] = answer.strip()
                Kamaki.save_token(session['token'])
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


def add_property(session):
    d = session['dialog']

    while 1:
        (code, answer) = d.inputbox("Please provide a name for a new image"
                                    " property:", width=WIDTH)
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        name = answer.strip()
        if len(name) == 0:
            d.msgbox("A property name cannot be empty", width=SMALL_WIDTH)
            continue

        break

    while 1:
        (code, answer) = d.inputbox("Please provide a value for image "
                                    "property %s" % name, width=WIDTH)
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        value = answer.strip()
        if len(value) == 0:
            d.msgbox("Value cannot be empty", width=SMALL_WIDTH)
            continue

        break

    session['metadata'][name] = value

    return True


def modify_properties(session):
    d = session['dialog']

    while 1:
        choices = []
        for (key, val) in session['metadata'].items():
            choices.append((str(key), str(val)))

        (code, choice) = d.menu(
            "In this menu you can edit existing image properties or add new "
            "ones. Be careful! Most properties have special meaning and "
            "alter the image deployment behaviour. Press <HELP> to see more "
            "information about image properties. Press <BACK> when done.",
            height=18, width=WIDTH, choices=choices, menu_height=10,
            ok_label="Edit", extra_button=1, extra_label="Add", cancel="Back",
            help_button=1, title="Image Properties")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return True
        # Edit button
        elif code == d.DIALOG_OK:
            (code, answer) = d.inputbox("Please provide a new value for the "
                                        "image property with name `%s':" %
                                        choice,
                                        init=session['metadata'][choice],
                                        width=WIDTH)
            if code not in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                value = answer.strip()
                if len(value) == 0:
                    d.msgbox("Value cannot be empty!")
                    continue
                else:
                    session['metadata'][choice] = value
        # ADD button
        elif code == d.DIALOG_EXTRA:
            add_property(session)
        elif code == 'help':
            help_file = get_help_file("image_properties")
            assert os.path.exists(help_file)
            d.textbox(help_file, title="Image Properties", width=70, height=40)


def delete_properties(session):
    d = session['dialog']

    choices = []
    for (key, val) in session['metadata'].items():
        choices.append((key, "%s" % val, 0))

    (code, to_delete) = d.checklist("Choose which properties to delete:",
                                    choices=choices, width=WIDTH)

    # If the user exits with ESC or CANCEL, the returned tag list is empty.
    for i in to_delete:
        del session['metadata'][i]

    cnt = len(to_delete)
    if cnt > 0:
        d.msgbox("%d image properties were deleted." % cnt, width=SMALL_WIDTH)
        return True
    else:
        return False


def exclude_tasks(session):
    d = session['dialog']

    index = 0
    displayed_index = 1
    choices = []
    mapping = {}
    if 'excluded_tasks' not in session:
        session['excluded_tasks'] = []

    if -1 in session['excluded_tasks']:
        if not d.yesno("Image deployment configuration is disabled. "
                       "Do you wish to enable it?", width=SMALL_WIDTH):
            session['excluded_tasks'].remove(-1)
        else:
            return False

    for (msg, task, osfamily) in CONFIGURATION_TASKS:
        if session['metadata']['OSFAMILY'] in osfamily:
            checked = 1 if index in session['excluded_tasks'] else 0
            choices.append((str(displayed_index), msg, checked))
            mapping[displayed_index] = index
            displayed_index += 1
        index += 1

    while 1:
        (code, tags) = d.checklist(
            text="Please choose which configuration tasks you would like to "
                 "prevent from running during image deployment. "
                 "Press <No Config> to supress any configuration. "
                 "Press <Help> for more help on the image deployment "
                 "configuration tasks.",
            choices=choices, height=19, list_height=8, width=WIDTH,
            help_button=1, extra_button=1, extra_label="No Config",
            title="Exclude Configuration Tasks")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False
        elif code == d.DIALOG_HELP:
            help_file = get_help_file("configuration_tasks")
            assert os.path.exists(help_file)
            d.textbox(help_file, title="Configuration Tasks",
                      width=70, height=40)
        # No Config button
        elif code == d.DIALOG_EXTRA:
            session['excluded_tasks'] = [-1]
            session['task_metadata'] = ["EXCLUDE_ALL_TASKS"]
            break
        elif code == d.DIALOG_OK:
            session['excluded_tasks'] = []
            for tag in tags:
                session['excluded_tasks'].append(mapping[int(tag)])

            exclude_metadata = []
            for task in session['excluded_tasks']:
                exclude_metadata.extend(CONFIGURATION_TASKS[task][1])

            session['task_metadata'] = map(lambda x: "EXCLUDE_TASK_%s" % x,
                                           exclude_metadata)
            break

    return True


def sysprep(session):
    d = session['dialog']
    image_os = session['image_os']

    # Is the image already shrinked?
    if 'shrinked' in session and session['shrinked']:
        msg = "It seems you have shrinked the image. Running system " \
              "preparation tasks on a shrinked image is dangerous."

        if d.yesno("%s\n\nDo you really want to continue?" % msg,
                   width=SMALL_WIDTH, defaultno=1):
            return

    wrapper = textwrap.TextWrapper(width=WIDTH - 5)

    help_title = "System Preperation Tasks"
    sysprep_help = "%s\n%s\n\n" % (help_title, '=' * len(help_title))

    if 'exec_syspreps' not in session:
        session['exec_syspreps'] = []

    all_syspreps = image_os.list_syspreps()
    # Only give the user the choice between syspreps that have not ran yet
    syspreps = [s for s in all_syspreps if s not in session['exec_syspreps']]

    if len(syspreps) == 0:
        d.msgbox("No system preparation task available to run!",
                 title="System Preperation", width=SMALL_WIDTH)
        return

    while 1:
        choices = []
        index = 0
        for sysprep in syspreps:
            name, descr = image_os.sysprep_info(sysprep)
            display_name = name.replace('-', ' ').capitalize()
            sysprep_help += "%s\n" % display_name
            sysprep_help += "%s\n" % ('-' * len(display_name))
            sysprep_help += "%s\n\n" % wrapper.fill(" ".join(descr.split()))
            enabled = 1 if sysprep.enabled else 0
            choices.append((str(index + 1), display_name, enabled))
            index += 1

        (code, tags) = d.checklist(
            "Please choose which system preparation tasks you would like to "
            "run on the image. Press <Help> to see details about the system "
            "preparation tasks.", title="Run system preparation tasks",
            choices=choices, width=70, ok_label="Run", help_button=1)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False
        elif code == d.DIALOG_HELP:
            d.scrollbox(sysprep_help, width=WIDTH)
        elif code == d.DIALOG_OK:
            # Enable selected syspreps and disable the rest
            for i in range(len(syspreps)):
                if str(i + 1) in tags:
                    image_os.enable_sysprep(syspreps[i])
                    session['exec_syspreps'].append(syspreps[i])
                else:
                    image_os.disable_sysprep(syspreps[i])

            infobox = InfoBoxOutput(d, "Image Configuration")
            try:
                dev = session['device']
                dev.out.add(infobox)
                try:
                    dev.mount(readonly=False)
                    try:
                        # The checksum is invalid. We have mounted the image rw
                        if 'checksum' in session:
                            del session['checksum']

                        # Monitor the metadata changes during syspreps
                        with metadata_monitor(session, image_os.meta):
                            image_os.do_sysprep()
                            infobox.finalize()

                        # Disable syspreps that have ran
                        for sysprep in session['exec_syspreps']:
                            image_os.disable_sysprep(sysprep)
                    finally:
                        dev.umount()
                finally:
                    dev.out.remove(infobox)
            finally:
                infobox.cleanup()
            break
    return True


def shrink(session):
    d = session['dialog']
    dev = session['device']

    shrinked = 'shrinked' in session and session['shrinked']

    if shrinked:
        d.msgbox("The image is already shrinked!", title="Image Shrinking",
                 width=SMALL_WIDTH)
        return True

    msg = "This operation will shrink the last partition of the image to " \
          "reduce the total image size. If the last partition is a swap " \
          "partition, then this partition is removed and the partition " \
          "before that is shrinked. The removed swap partition will be " \
          "recreated during image deployment."

    if not d.yesno("%s\n\nDo you want to continue?" % msg, width=WIDTH,
                   height=12, title="Image Shrinking"):
        with metadata_monitor(session, dev.meta):
            infobox = InfoBoxOutput(d, "Image Shrinking", height=4)
            dev.out.add(infobox)
            try:
                dev.shrink()
                infobox.finalize()
            finally:
                dev.out.remove(infobox)

        session['shrinked'] = True
        update_background_title(session)
    else:
        return False

    return True


def customization_menu(session):
    d = session['dialog']

    choices = [("Sysprep", "Run various image preparation tasks"),
               ("Shrink", "Shrink image"),
               ("View/Modify", "View/Modify image properties"),
               ("Delete", "Delete image properties"),
               ("Exclude", "Exclude various deployment tasks from running")]

    default_item = 0

    actions = {"Sysprep": sysprep,
               "Shrink": shrink,
               "View/Modify": modify_properties,
               "Delete": delete_properties,
               "Exclude": exclude_tasks}
    while 1:
        (code, choice) = d.menu(
            text="Choose one of the following or press <Back> to exit.",
            width=WIDTH, choices=choices, cancel="Back", height=13,
            menu_height=len(choices), default_item=choices[default_item][0],
            title="Image Customization Menu")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            break
        elif choice in actions:
            default_item = [entry[0] for entry in choices].index(choice)
            if actions[choice](session):
                default_item = (default_item + 1) % len(choices)


def main_menu(session):
    d = session['dialog']
    dev = session['device']

    update_background_title(session)

    choices = [("Customize", "Customize image & ~okeanos deployment options"),
               ("Register", "Register image to ~okeanos"),
               ("Extract", "Dump image to local file system"),
               ("Reset", "Reset everything and start over again"),
               ("Help", "Get help for using snf-image-creator")]

    default_item = "Customize"

    actions = {"Customize": customization_menu, "Register": kamaki_menu,
               "Extract": extract_image}
    while 1:
        (code, choice) = d.menu(
            text="Choose one of the following or press <Exit> to exit.",
            width=WIDTH, choices=choices, cancel="Exit", height=13,
            default_item=default_item, menu_height=len(choices),
            title="Image Creator for ~okeanos (snf-image-creator version %s)" %
                  version)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            if confirm_exit(d):
                break
        elif choice == "Reset":
            if confirm_reset(d):
                d.infobox("Resetting snf-image-creator. Please wait...",
                          width=SMALL_WIDTH)
                raise Reset
        elif choice in actions:
            actions[choice](session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
