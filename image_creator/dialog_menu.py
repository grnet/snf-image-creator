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

"""This module implements the "expert" mode of the dialog-based version of
snf-image-creator.
"""

import os
import textwrap
import StringIO
import json

from image_creator import __version__ as version
from image_creator.util import MD5, FatalError
from image_creator.output.dialog import GaugeOutput, InfoBoxOutput
from image_creator.kamaki_wrapper import Kamaki, ClientError
from image_creator.help import get_help_file
from image_creator.dialog_util import SMALL_WIDTH, WIDTH, \
    update_background_title, confirm_reset, confirm_exit, Reset, \
    extract_image, extract_metadata_string, add_cloud, edit_cloud

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

SYSPREP_PARAM_MAXLEN = 20


class MetadataMonitor(object):
    """Monitors image metadata chages"""
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
    """Upload the image to the storage service"""
    d = session["dialog"]
    image = session['image']
    meta = session['metadata']
    size = image.size

    if "account" not in session:
        d.msgbox("You need to select a valid cloud before you can upload "
                 "images to it", width=SMALL_WIDTH)
        return False

    while 1:
        if 'upload' in session:
            init = session['upload']
        elif 'OS' in meta:
            init = "%s.diskdump" % meta['OS']
        else:
            init = ""
        (code, answer) = d.inputbox("Please provide a filename:", init=init,
                                    width=WIDTH)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        filename = answer.strip()
        if len(filename) == 0:
            d.msgbox("Filename cannot be empty", width=SMALL_WIDTH)
            continue

        kamaki = Kamaki(session['account'], None)
        overwrite = []
        for f in (filename, "%s.md5sum" % filename, "%s.meta" % filename):
            if kamaki.object_exists(f):
                overwrite.append(f)

        if len(overwrite) > 0:
            if d.yesno("The following storage service object(s) already "
                       "exist(s):\n%s\nDo you want to overwrite them?" %
                       "\n".join(overwrite), width=WIDTH, defaultno=1):
                continue

        session['upload'] = filename
        break

    gauge = GaugeOutput(d, "Image Upload", "Uploading ...")
    try:
        out = image.out
        out.add(gauge)
        kamaki.out = out
        try:
            if 'checksum' not in session:
                md5 = MD5(out)
                session['checksum'] = md5.compute(image.device, size)

            try:
                # Upload image file
                with open(image.device, 'rb') as f:
                    session["pithos_uri"] = \
                        kamaki.upload(f, size, filename,
                                      "Calculating block hashes",
                                      "Uploading missing blocks")
                # Upload md5sum file
                out.output("Uploading md5sum file ...")
                md5str = "%s %s\n" % (session['checksum'], filename)
                kamaki.upload(StringIO.StringIO(md5str), size=len(md5str),
                              remote_path="%s.md5sum" % filename)
                out.success("done")

            except ClientError as e:
                d.msgbox(
                    "Error in storage service client: %s" % e.message,
                    title="Storage Service Client Error", width=SMALL_WIDTH)
                if 'pithos_uri' in session:
                    del session['pithos_uri']
                return False
        finally:
            out.remove(gauge)
    finally:
        gauge.cleanup()

    d.msgbox("Image file `%s' was successfully uploaded" % filename,
             width=SMALL_WIDTH)

    return True


def register_image(session):
    """Register image with the compute service"""
    d = session["dialog"]

    is_public = False

    if "account" not in session:
        d.msgbox("You need to select a valid cloud before you "
                 "can register an images with it", width=SMALL_WIDTH)
        return False

    if "pithos_uri" not in session:
        d.msgbox("You need to upload the image to the cloud before you can "
                 "register it", width=SMALL_WIDTH)
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

        ret = d.yesno("Make the image public?\\nA public image is accessible "
                      "by every user of the service.", defaultno=1,
                      width=WIDTH)
        if ret not in (0, 1):
            continue

        is_public = True if ret == 0 else False

        break

    metadata = {}
    metadata.update(session['metadata'])
    if 'task_metadata' in session:
        for key in session['task_metadata']:
            metadata[key] = 'yes'

    img_type = "public" if is_public else "private"
    gauge = GaugeOutput(d, "Image Registration", "Registering image ...")
    try:
        out = session['image'].out
        out.add(gauge)
        try:
            try:
                out.output("Registering %s image with the cloud ..." %
                           img_type)
                kamaki = Kamaki(session['account'], out)
                result = kamaki.register(name, session['pithos_uri'], metadata,
                                         is_public)
                out.success('done')
                # Upload metadata file
                out.output("Uploading metadata file ...")
                metastring = unicode(json.dumps(result, ensure_ascii=False))
                kamaki.upload(StringIO.StringIO(metastring),
                              size=len(metastring),
                              remote_path="%s.meta" % session['upload'])
                out.success("done")
                if is_public:
                    out.output("Sharing metadata and md5sum files ...")
                    kamaki.share("%s.meta" % session['upload'])
                    kamaki.share("%s.md5sum" % session['upload'])
                    out.success('done')
            except ClientError as e:
                d.msgbox("Error in storage service client: %s" % e.message)
                return False
        finally:
            out.remove(gauge)
    finally:
        gauge.cleanup()

    d.msgbox("%s image `%s' was successfully registered with the cloud as `%s'"
             % (img_type.title(), session['upload'], name), width=SMALL_WIDTH)
    return True


def modify_clouds(session):
    """Modify existing cloud accounts"""
    d = session['dialog']

    while 1:
        clouds = Kamaki.get_clouds()
        if not len(clouds):
            if not add_cloud(session):
                break
            continue

        choices = []
        for (name, cloud) in clouds.items():
            descr = cloud['description'] if 'description' in cloud else ''
            choices.append((name, descr))

        (code, choice) = d.menu(
            "In this menu you can edit existing cloud accounts or add new "
            " ones. Press <Edit> to edit an existing account or <Add> to add "
            " a new one. Press <Back> or hit <ESC> when done.", height=18,
            width=WIDTH, choices=choices, menu_height=10, ok_label="Edit",
            extra_button=1, extra_label="Add", cancel="Back", help_button=1,
            title="Clouds")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return True
        elif code == d.DIALOG_OK:  # Edit button
            edit_cloud(session, choice)
        elif code == d.DIALOG_EXTRA:  # Add button
            add_cloud(session)


def delete_clouds(session):
    """Delete existing cloud accounts"""
    d = session['dialog']

    choices = []
    for (name, cloud) in Kamaki.get_clouds().items():
        descr = cloud['description'] if 'description' in cloud else ''
        choices.append((name, descr, 0))

    if len(choices) == 0:
        d.msgbox("No available clouds to delete!", width=SMALL_WIDTH)
        return True

    (code, to_delete) = d.checklist("Choose which cloud accounts to delete:",
                                    choices=choices, width=WIDTH)
    to_delete = map(lambda x: x.strip('"'), to_delete)  # Needed for OpenSUSE

    if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
        return False

    if not len(to_delete):
        d.msgbox("Nothing selected!", width=SMALL_WIDTH)
        return False

    if not d.yesno("Are you sure you want to remove the selected cloud "
                   "accounts?", width=WIDTH, defaultno=1):
        for i in to_delete:
            Kamaki.remove_cloud(i)
            if 'cloud' in session and session['cloud'] == i:
                del session['cloud']
                if 'account' in session:
                    del session['account']
    else:
        return False

    d.msgbox("%d cloud accounts were deleted." % len(to_delete),
             width=SMALL_WIDTH)
    return True


def kamaki_menu(session):
    """Show kamaki related actions"""
    d = session['dialog']
    default_item = "Cloud"

    if 'cloud' not in session:
        cloud = Kamaki.get_default_cloud_name()
        if cloud:
            session['cloud'] = cloud
            session['account'] = Kamaki.get_account(cloud)
            if not session['account']:
                del session['account']
        else:
            default_item = "Add/Edit"

    while 1:
        cloud = session["cloud"] if "cloud" in session else "<none>"
        if 'account' not in session and 'cloud' in session:
            cloud += " <invalid>"

        upload = session["upload"] if "upload" in session else "<none>"

        choices = [("Add/Edit", "Add/Edit cloud accounts"),
                   ("Delete", "Delete existing cloud accounts"),
                   ("Cloud", "Select cloud account to use: %s" % cloud),
                   ("Upload", "Upload image to the cloud"),
                   ("Register", "Register image with the cloud: %s" % upload)]

        (code, choice) = d.menu(
            text="Choose one of the following or press <Back> to go back.",
            width=WIDTH, choices=choices, cancel="Back", height=13,
            menu_height=5, default_item=default_item,
            title="Image Registration Menu")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        if choice == "Add/Edit":
            if modify_clouds(session):
                default_item = "Cloud"
        elif choice == "Delete":
            if delete_clouds(session):
                if len(Kamaki.get_clouds()):
                    default_item = "Cloud"
                else:
                    default_item = "Add/Edit"
            else:
                default_item = "Delete"
        elif choice == "Cloud":
            default_item = "Cloud"
            clouds = Kamaki.get_clouds()
            if not len(clouds):
                d.msgbox("No clouds available. Please add a new cloud!",
                         width=SMALL_WIDTH)
                default_item = "Add/Edit"
                continue

            if 'cloud' not in session:
                session['cloud'] = clouds.keys()[0]

            choices = []
            for name, info in clouds.items():
                default = 1 if session['cloud'] == name else 0
                descr = info['description'] if 'description' in info else ""
                choices.append((name, descr, default))

            (code, answer) = d.radiolist("Please select a cloud:",
                                         width=WIDTH, choices=choices)
            if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                continue
            else:
                session['account'] = Kamaki.get_account(answer)

                if session['account'] is None:  # invalid account
                    if not d.yesno("The cloud %s' is not valid! Would you "
                                   "like to edit it?" % answer, width=WIDTH):
                        if edit_cloud(session, answer):
                            session['account'] = Kamaki.get_account(answer)
                            Kamaki.set_default_cloud(answer)

                if session['account'] is not None:
                    session['cloud'] = answer
                    Kamaki.set_default_cloud(answer)
                    default_item = "Upload"
                else:
                    del session['account']
                    del session['cloud']
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
    """Add a new property to the image"""
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
    """Modify an existing image property"""
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
    """Delete an image property"""
    d = session['dialog']

    choices = []
    for (key, val) in session['metadata'].items():
        choices.append((key, "%s" % val, 0))

    (code, to_delete) = d.checklist("Choose which properties to delete:",
                                    choices=choices, width=WIDTH)
    to_delete = map(lambda x: x.strip('"'), to_delete)  # needed for OpenSUSE

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
    """Exclude specific tasks from running during image deployment"""
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
        tags = map(lambda x: x.strip('"'), tags)  # Needed for OpenSUSE

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


def sysprep_params(session):
    """Collect the needed sysprep parameters"""
    d = session['dialog']
    image = session['image']

    available = image.os.sysprep_params
    needed = image.os.needed_sysprep_params

    if len(needed) == 0:
        return True

    def print_form(names, extra_button=False):
        """print the dialog form providing sysprep_params"""
        fields = []
        for name in names:
            param = needed[name]
            default = str(available[name]) if name in available else ""
            fields.append(("%s: " % param.description, default,
                           SYSPREP_PARAM_MAXLEN))

        kwargs = {}
        if extra_button:
            kwargs['extra_button'] = 1
            kwargs['extra_label'] = "Advanced"

        txt = "Please provide the following system preparation parameters:"
        return d.form(txt, height=13, width=WIDTH, form_height=len(fields),
                      fields=fields, **kwargs)

    def check_params(names, values):
        """check if the provided sysprep parameters have leagal values"""
        for i in range(len(names)):
            param = needed[names[i]]
            try:
                normalized = param.type(values[i])
                if param.validate(normalized):
                    image.os.sysprep_params[names[i]] = normalized
                    continue
            except ValueError:
                pass

            d.msgbox("Invalid value for parameter: `%s'" % names[i],
                     width=SMALL_WIDTH)
            return False
        return True

    simple_names = [k for k, v in needed.items() if v.default is None]
    advanced_names = [k for k, v in needed.items() if v.default is not None]

    while 1:
        code, output = print_form(simple_names, extra_button=True)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False
        if code == d.DIALOG_EXTRA:
            while 1:
                code, output = print_form(advanced_names)
                if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                    break
                if check_params(advanced_names, output):
                    break
            continue

        if check_params(simple_names, output):
            break

    return True


def sysprep(session):
    """Perform various system preperation tasks on the image"""
    d = session['dialog']
    image = session['image']

    # Is the image already shrinked?
    if 'shrinked' in session and session['shrinked']:
        msg = "It seems you have shrinked the image. Running system " \
              "preparation tasks on a shrinked image is dangerous."

        if d.yesno("%s\n\nDo you really want to continue?" % msg,
                   width=SMALL_WIDTH, defaultno=1):
            return

    wrapper = textwrap.TextWrapper(width=WIDTH - 5)

    syspreps = image.os.list_syspreps()

    if len(syspreps) == 0:
        d.msgbox("No system preparation task available to run!",
                 title="System Preperation", width=SMALL_WIDTH)
        return

    while 1:
        choices = []
        index = 0

        help_title = "System Preperation Tasks"
        sysprep_help = "%s\n%s\n\n" % (help_title, '=' * len(help_title))

        for sysprep in syspreps:
            name, descr = image.os.sysprep_info(sysprep)
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
        tags = map(lambda x: x.strip('"'), tags)  # Needed for OpenSUSE

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False
        elif code == d.DIALOG_HELP:
            d.scrollbox(sysprep_help, width=WIDTH)
        elif code == d.DIALOG_OK:
            # Enable selected syspreps and disable the rest
            for i in range(len(syspreps)):
                if str(i + 1) in tags:
                    image.os.enable_sysprep(syspreps[i])
                else:
                    image.os.disable_sysprep(syspreps[i])

            if len([s for s in image.os.list_syspreps() if s.enabled]) == 0:
                d.msgbox("No system preperation task is selected!",
                         title="System Preperation", width=SMALL_WIDTH)
                continue

            if not sysprep_params(session):
                continue

            infobox = InfoBoxOutput(d, "Image Configuration")
            try:
                image.out.add(infobox)
                try:
                    # The checksum is invalid. We have mounted the image rw
                    if 'checksum' in session:
                        del session['checksum']

                    # Monitor the metadata changes during syspreps
                    with MetadataMonitor(session, image.os.meta):
                        try:
                            image.os.do_sysprep()
                            infobox.finalize()
                        except FatalError as e:
                            title = "System Preparation"
                            d.msgbox("System Preparation failed: %s" % e,
                                     title=title, width=SMALL_WIDTH)
                finally:
                    image.out.remove(infobox)
            finally:
                infobox.cleanup()
            break
    return True


def shrink(session):
    """Shrink the image"""
    d = session['dialog']
    image = session['image']

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
        with MetadataMonitor(session, image.meta):
            infobox = InfoBoxOutput(d, "Image Shrinking", height=4)
            image.out.add(infobox)
            try:
                image.shrink()
                infobox.finalize()
            finally:
                image.out.remove(infobox)

        session['shrinked'] = True
        update_background_title(session)
    else:
        return False

    return True


def customization_menu(session):
    """Show image customization menu"""
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
    """Show the main menu of the program"""
    d = session['dialog']

    update_background_title(session)

    choices = [("Customize", "Customize image & cloud deployment options"),
               ("Register", "Register image to a cloud"),
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
            title="Image Creator for synnefo (snf-image-creator version %s)" %
                  version)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            if confirm_exit(d):
                break
        elif choice == "Reset":
            if confirm_reset(d):
                d.infobox("Resetting snf-image-creator. Please wait ...",
                          width=SMALL_WIDTH)
                raise Reset
        elif choice == "Help":
            d.msgbox("For help, check the online documentation:\n\nhttp://www"
                     ".synnefo.org/docs/snf-image-creator/latest/",
                     width=WIDTH, title="Help")
        elif choice in actions:
            actions[choice](session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
