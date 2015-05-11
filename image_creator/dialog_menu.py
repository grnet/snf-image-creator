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

"""This module implements the "expert" mode of the dialog-based version of
snf-image-creator.
"""

import os
import textwrap
import StringIO
import json
import re
import time
import tempfile

from image_creator import __version__ as version
from image_creator.util import FatalError, virtio_versions
from image_creator.output.dialog import GaugeOutput, InfoBoxOutput
from image_creator.kamaki_wrapper import Kamaki, ClientError, CONTAINER
from image_creator.help import get_help_file
from image_creator.dialog_util import SMALL_WIDTH, WIDTH, \
    update_background_title, confirm_reset, confirm_exit, Reset, \
    extract_image, add_cloud, edit_cloud, update_sysprep_param, select_file, \
    copy_file, create_form_elements

CONFIGURATION_TASKS = [
    ("Partition table manipulation", ["FixPartitionTable"], lambda x: True),
    ("File system resize",
     ["FilesystemResizeUnmounted", "FilesystemResizeMounted"], lambda x: True),
    ("Swap partition configuration", ["AddSwap"], lambda x: x == 'linux'),
    ("SSH keys removal", ["DeleteSSHKeys"], lambda x: x != 'windows'),
    ("Temporal RDP disabling", ["DisableRemoteDesktopConnections"],
     lambda x: x == "windows"),
    ("SELinux relabeling at next boot", ["SELinuxAutorelabel"],
     lambda x: x == "linux"),
    ("Hostname/Computer Name assignment", ["AssignHostname"], lambda x: True),
    ("Password change", ["ChangePassword"], lambda x: True),
    ("Network configuration", ["ConfigureNetwork"], lambda x: x != 'windows'),
    ("File injection", ["EnforcePersonality"], lambda x: True)
]

SYSPREP_PARAM_MAXLEN = 20


class MetadataMonitor(object):
    """Monitors image metadata chages"""
    def __init__(self, session, meta):
        self.session = session
        self.meta = meta
        self.old = {}

    def __enter__(self):
        self.old = {}
        for (k, v) in self.meta.items():
            self.old[k] = v

    def __exit__(self, exc_type, exc_val, exc_tb):
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

        d.msgbox(msg, title="Image Property Changes", width=SMALL_WIDTH)


def upload_image(session):
    """Upload the image to the storage service"""
    d = session["dialog"]
    image = session['image']

    if "account" not in session:
        d.msgbox("You need to select a valid cloud before you can upload "
                 "images to it", width=SMALL_WIDTH)
        return False

    while 1:
        if 'uploaded' in session:
            _, _, _, container, name = session['uploaded'].split('/')
        elif 'OS' in session['image'].meta:
            name = "%s.diskdump" % session['image'].meta['OS']
            container = CONTAINER
        else:
            name = ""
            container = CONTAINER

        fields = [("Remote Name:", name, 60), ("Container:", container, 60)]

        (code, output) = d.form("Please provide the following upload info:",
                                create_form_elements(fields), height=11,
                                width=WIDTH, form_height=2)

        if code in (d.CANCEL, d.ESC):
            return False

        name, container = output
        name = name.strip()
        container = container.strip()

        if len(name) == 0:
            d.msgbox("Remote Name cannot be empty", width=SMALL_WIDTH)
            continue

        if len(container) == 0:
            d.msgbox("Container cannot be empty", width=SMALL_WIDTH)
            continue

        kamaki = Kamaki(session['account'], None)
        overwrite = []
        for f in (name, "%s.md5sum" % name, "%s.meta" % name):
            if kamaki.object_exists(container, f):
                overwrite.append(f)

        if len(overwrite) > 0:
            if d.yesno("The following storage service object(s) already "
                       "exist(s):\n%s\nDo you want to overwrite them?" %
                       "\n".join(overwrite), width=WIDTH, defaultno=1
                       ) != d.OK:
                continue
        break

    gauge = GaugeOutput(d, "Image Upload", "Uploading ...")
    try:
        out = image.out
        out.append(gauge)
        kamaki.out = out
        try:
            if 'checksum' not in session:
                session['checksum'] = image.md5()

            try:
                # Upload image file
                with image.raw_device() as raw:
                    with open(raw, 'rb') as f:
                        session["uploaded"] = \
                            kamaki.upload(f, image.size, name, container,
                                          "Calculating block hashes",
                                          "Uploading missing blocks")
                # Upload md5sum file
                out.info("Uploading md5sum file ...")
                md5str = "%s %s\n" % (session['checksum'], name)
                kamaki.upload(StringIO.StringIO(md5str), size=len(md5str),
                              remote_path="%s.md5sum" % name,
                              container=container,
                              content_type="text/plain")
                out.success("done")

            except ClientError as e:
                d.msgbox(
                    "Error in storage service client: %s" % e.message,
                    title="Storage Service Client Error", width=SMALL_WIDTH)
                if 'uploaded' in session:
                    del session['uploaded']
                return False
        finally:
            out.remove(gauge)
    finally:
        gauge.cleanup()

    d.msgbox("Image file `%s' was successfully uploaded" % name,
             width=SMALL_WIDTH)

    return True


def register_image(session):
    """Register image with the compute service"""
    d = session["dialog"]
    image = session['image']

    is_public = False

    if "account" not in session:
        d.msgbox("You need to select a valid cloud before you "
                 "can register an images with it", width=SMALL_WIDTH)
        return False

    if "uploaded" not in session:
        d.msgbox("You need to upload the image to the cloud before you can "
                 "register it", width=SMALL_WIDTH)
        return False
    _, _, _, container, remote = session['uploaded'].split('/')

    name = "" if 'registered' not in session else session['registered'].name
    description = image.meta['DESCRIPTION'] if 'DESCRIPTION' in image.meta \
        else ""

    while 1:
        fields = [("Registration name:", name, 60),
                  ("Description (optional):", description, 80)]

        (code, output) = d.form(
            "Please provide the following registration info:",
            create_form_elements(fields), height=11, width=WIDTH,
            form_height=2)

        if code in (d.CANCEL, d.ESC):
            return False

        name, description = output
        name = name.strip()
        description = description.strip()

        if len(name) == 0:
            d.msgbox("Registration name cannot be empty", width=SMALL_WIDTH)
            continue

        answer = d.yesno("Make the image public?\\nA public image is "
                         "accessible by every user of the service.",
                         defaultno=1, width=WIDTH)
        if answer == d.ESC:
            continue

        is_public = (answer == d.OK)
        break

    image.meta['DESCRIPTION'] = description
    metadata = {}
    metadata.update(image.meta)
    if 'task_metadata' in session:
        for key in session['task_metadata']:
            metadata[key] = 'yes'

    img_type = "public" if is_public else "private"
    gauge = GaugeOutput(d, "Image Registration", "Registering image ...")
    try:
        out = session['image'].out
        out.append(gauge)
        try:
            try:
                out.info("Registering %s image with the cloud ..." % img_type,
                         False)
                kamaki = Kamaki(session['account'], out)
                session['registered'] = kamaki.register(
                    name, session['uploaded'], metadata, is_public)
                out.success('done')

                # Upload metadata file
                out.info("Uploading metadata file ...", False)
                metastring = unicode(json.dumps(session['registered'],
                                                indent=4, ensure_ascii=False))
                kamaki.upload(StringIO.StringIO(metastring),
                              size=len(metastring),
                              remote_path="%s.meta" % remote,
                              container=container,
                              content_type="application/json")
                out.success("done")
                if is_public:
                    out.info("Sharing metadata and md5sum files ...", False)
                    kamaki.share("%s.meta" % remote)
                    kamaki.share("%s.md5sum" % remote)
                    out.success('done')
            except ClientError as error:
                d.msgbox("Error in storage service client: %s" % error.message)
                return False
        finally:
            out.remove(gauge)
    finally:
        gauge.cleanup()

    d.msgbox("%s image `%s' was successfully registered with the cloud as `%s'"
             % (img_type.title(), remote, name), width=SMALL_WIDTH)
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

        if code in (d.CANCEL, d.ESC):
            return True
        elif code == d.OK:  # Edit button
            edit_cloud(session, choice)
        elif code == d.EXTRA:  # Add button
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
    to_delete = [x.strip('"') for x in to_delete]  # Needed for OpenSUSE

    if code in (d.CANCEL, d.ESC):
        return False

    if not len(to_delete):
        d.msgbox("Nothing selected!", width=SMALL_WIDTH)
        return False

    if d.yesno("Are you sure you want to remove the selected accounts?",
               width=WIDTH, defaultno=1) == d.OK:
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

    if 'registered' in session:
        default_item = "Info"
    elif 'uploaded' in session:
        default_item = "Register"
    else:
        default_item = "Upload"

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

        choices = [("Add/Edit", "Add/Edit cloud accounts"),
                   ("Delete", "Delete existing cloud accounts"),
                   ("Cloud", "Select cloud account to use: %s" % cloud),
                   ("Upload", "Upload image to the cloud")]

        if 'uploaded' in session:
            _, _, _, _, name = session['uploaded'].split('/')
            choices.append(("Register", "Register image with the cloud: %s"
                            % name))
        if 'registered' in session:
            choices.append(("Info", "Show registration info for \"%s\"" %
                            session['registered']['name']))

        (code, choice) = d.menu(
            text="Choose one of the following or press <Back> to go back.",
            width=WIDTH, choices=choices, cancel="Back", height=8+len(choices),
            menu_height=len(choices), default_item=default_item,
            title="Image Registration Menu")

        if code in (d.CANCEL, d.ESC):
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
            if code in (d.CANCEL, d.ESC):
                continue
            else:
                session['account'] = Kamaki.get_account(answer)

                if session['account'] is None:  # invalid account
                    if d.yesno("The cloud %s' is not valid! Would you like to "
                               "edit it?" % answer, width=WIDTH) == d.OK:
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
                default_item = "Info"
            else:
                default_item = "Register"
        elif choice == "Info":
            show_info(session)


def show_info(session):
    """Show registration info"""

    assert 'registered' in session
    info = json.dumps(session['registered'], ensure_ascii=False, indent=4)

    d = session['dialog']

    while 1:
        code = d.scrollbox(info, width=WIDTH, title="Registration info",
                           extra_label="Save", extra_button=1,
                           ok_label="Close")
        if code == d.EXTRA:
            path = select_file(d, title="Save registration information as...")
            if path is None:
                break
            if os.path.isdir(path):
                continue

            if os.path.exists(path):
                if d.yesno("File: `%s' already exists. Do you want to "
                           "overwrite it?" % path, width=WIDTH, defaultno=1
                           ) != d.OK:
                    continue

            with open(path, 'w') as f:
                f.write(info + '\n')

            d.msgbox("File `%s was successfully written." % path,
                     width=SMALL_WIDTH)
            break
        else:
            return


def add_property(session):
    """Add a new property to the image"""
    d = session['dialog']
    image = session['image']

    regexp = re.compile('^[A-Za-z_]+$')

    while 1:
        (code, answer) = d.inputbox("Please provide a case-insensitive name "
                                    "for a new image property:", width=WIDTH)
        if code in (d.CANCEL, d.ESC):
            return False

        name = answer.strip()
        if len(name) == 0:
            d.msgbox("A property name cannot be empty", width=SMALL_WIDTH)
            continue

        if not re.match(regexp, name):
            d.msgbox("Allowed characters for name: [a-zA-Z0-9_]", width=WIDTH)
            continue

        # Image properties are case-insensitive
        name = name.upper()

        if name in image.meta:
            d.msgbox("Image property: `%s' already exists" % name, width=WIDTH)
            continue

        break

    while 1:
        (code, answer) = d.inputbox("Please provide a value for image "
                                    "property: `%s'" % name, width=WIDTH)
        if code in (d.CANCEL, d.ESC):
            return False

        value = answer.strip()
        if len(value) == 0:
            d.msgbox("Value cannot be empty", width=SMALL_WIDTH)
            continue

        break

    image.meta[name] = value

    return True


def show_properties_help(session):
    """Show help for image properties"""
    d = session['dialog']

    help_file = get_help_file("image_properties")
    assert os.path.exists(help_file)
    d.textbox(help_file, title="Image Properties", width=78, height=40)


def modify_properties(session):
    """Modify an existing image property"""
    d = session['dialog']
    image = session['image']

    while 1:
        choices = []
        for (key, val) in image.meta.items():
            choices.append((str(key), str(val)))

        if len(choices) == 0:
            code = d.yesno(
                "No image properties are available. "
                "Would you like to add a new one?", width=WIDTH, help_button=1)
            if code == d.OK:
                if not add_property(session):
                    return True
            elif code == d.CANCEL or code == d.ESC:
                return True
            elif code == d.HELP:
                show_properties_help(session)
            continue

        (code, choice) = d.menu(
            "In this menu you can edit and delete existing image properties "
            "or add new ones. Be careful! Most properties have special "
            "meaning and alter the image deployment behavior. Press <HELP> to "
            "see more information about image properties. Press <BACK> when "
            "done.", height=18, width=WIDTH, choices=choices, menu_height=10,
            ok_label="Edit/Del", extra_button=1, extra_label="Add",
            cancel="Back", help_button=1, title="Image Properties")

        if code in (d.CANCEL, d.ESC):
            return True
        # Edit button
        elif code == d.OK:
            (code, answer) = d.inputbox(
                "Please provide a new value for `%s' image property or press "
                "<Delete> to completely delete it." % choice,
                init=image.meta[choice], width=WIDTH, extra_button=1,
                extra_label="Delete")
            if code == d.OK:
                value = answer.strip()
                if len(value) == 0:
                    d.msgbox("Value cannot be empty!")
                    continue
                else:
                    image.meta[choice] = value
            # Delete button
            elif code == d.EXTRA:
                if d.yesno("Are you sure you want to delete `%s' image "
                           "property?" % choice, width=WIDTH) == d.OK:
                    del image.meta[choice]
                    d.msgbox("Image property: `%s' was deleted." % choice,
                             width=SMALL_WIDTH)
        # ADD button
        elif code == d.EXTRA:
            add_property(session)
        elif code == 'help':
            show_properties_help(session)


def exclude_tasks(session):
    """Exclude specific tasks from running during image deployment"""
    d = session['dialog']
    image = session['image']

    if image.is_unsupported():
        d.msgbox("Image deployment configuration is disabled for unsupported "
                 "images.", width=SMALL_WIDTH)
        return False

    index = 0
    displayed_index = 1
    choices = []
    mapping = {}
    if 'excluded_tasks' not in session:
        session['excluded_tasks'] = []

    if -1 in session['excluded_tasks']:
        if d.yesno("Image deployment configuration is disabled. "
                   "Do you wish to enable it?", width=SMALL_WIDTH) == d.OK:
            session['excluded_tasks'].remove(-1)
        else:
            return False

    for (msg, task, os_check) in CONFIGURATION_TASKS:
        if os_check(image.meta['OSFAMILY']):
            checked = 1 if index in session['excluded_tasks'] else 0
            choices.append((str(displayed_index), msg, checked))
            mapping[displayed_index] = index
            displayed_index += 1
        index += 1

    if len(choices) == 0:
        d.msgbox("No configuration tasks available", width=WIDTH)
        return True

    while 1:
        text = "Please choose which configuration tasks you would like to " \
               "prevent from running during image deployment. " \
               "Press <No Config> to suppress any configuration. " \
               "Press <Help> for more help on the image deployment " \
               "configuration tasks."

        (code, tags) = d.checklist(
            text=text, choices=choices, height=19, list_height=8, width=WIDTH,
            help_button=1, extra_button=1, extra_label="No Config",
            title="Exclude Configuration Tasks")
        tags = [x.strip('"') for x in tags]  # Needed for OpenSUSE

        if code in (d.CANCEL, d.ESC):
            return False
        elif code == d.HELP:
            help_file = get_help_file("configuration_tasks")
            assert os.path.exists(help_file)
            d.textbox(help_file, title="Configuration Tasks",
                      width=70, height=40)
        # No Config button
        elif code == d.EXTRA:
            session['excluded_tasks'] = [-1]
            session['task_metadata'] = ["EXCLUDE_ALL_TASKS"]
            break
        elif code == d.OK:
            session['excluded_tasks'] = []
            for tag in tags:
                session['excluded_tasks'].append(mapping[int(tag)])

            exclude_metadata = []
            for task in session['excluded_tasks']:
                exclude_metadata.extend(CONFIGURATION_TASKS[task][1])

            session['task_metadata'] = ["EXCLUDE_TASK_%s" % x
                                        for x in exclude_metadata]
            break

    return True


def sysprep_params(session):
    """Collect the needed sysprep parameters"""
    d = session['dialog']
    image = session['image']

    default = None
    while 1:
        choices = []
        for name, param in image.os.sysprep_params.items():

            # Don't show the hidden parameters
            if param.hidden:
                continue

            value = "|".join([str(i) for i in param.value]) if param.is_list \
                else str(param.value)
            if len(value) == 0:
                value = "<not_set>"
            choices.append((name, value))

        if len(choices) == 0:
            d.msgbox("No customization parameters available", width=WIDTH)
            return True

        if default is None:
            default = choices[0][0]

        (code, choice) = d.menu(
            "In this menu you can see and update the value for parameters "
            "used in the system preparation tasks. Press <Details> to see "
            "more info about a specific configuration parameters and <Update> "
            "to update its value. Press <Back> when done.", height=18,
            width=WIDTH, choices=choices, menu_height=10, ok_label="Details",
            extra_button=1, extra_label="Update", cancel="Back",
            default_item=default, title="System Preparation Parameters")

        default = choice

        if code in (d.CANCEL, d.ESC):
            return True
        elif code == d.OK:  # Details button
            d.msgbox(image.os.sysprep_params[choice].description, width=WIDTH)
        else:  # Update button
            update_sysprep_param(session, choice)

    return True


def virtio(session):
    """Display the state of the VirtIO drivers in the media"""

    d = session['dialog']
    image = session['image']

    assert hasattr(image.os, 'virtio_state')
    assert hasattr(image.os, 'install_virtio_drivers')

    default_item = image.os.virtio_state.keys()[0]
    while 1:
        choices = []
        for name, details in virtio_versions(image.os.virtio_state).items():
            choices.append((name, details))

        (code, choice) = d.menu(
            "In this menu you can see details about the installed VirtIO "
            "drivers on the input media. Press <Info> to see more information "
            "about a specific installed driver or <Update> to install one or "
            "more new drivers.", height=16, width=WIDTH, choices=choices,
            ok_label="Info", menu_height=len(choices), cancel="Back",
            title="VirtIO Drivers", extra_button=1, extra_label="Update",
            default_item=default_item)

        if code in (d.CANCEL, d.ESC):
            return True
        elif code == d.OK:
            default_item = choice

            # Create a string with the driver details and display it.
            details = ""
            for fname, driver in image.os.virtio_state[choice].items():
                details += "%s\n%s\n" % (fname, "=" * len(fname))
                name = ""
                if 'DriverPackageDisplayName' in driver:
                    name = driver['DriverPackageDisplayName']
                provider = ""
                if 'Provider' in driver:
                    provider = driver['Provider']
                date = ""
                version = ""
                if 'DriverVer' in driver:
                    version = driver['DriverVer'].split(',', 1)
                    date = version[0].strip()
                    version = version[1] if len(version) > 1 else ""
                    try:
                        date = time.strptime(
                            date, "%m/%d/%y").strftime('%d/%m/%Y', date)
                    except ValueError:
                        pass
                dtype = ""
                if 'DriverPackageType' in driver:
                    dtype = driver['DriverPackageType']
                dclass = ""
                if 'Class' in driver:
                    dclass = driver['Class']

                details += "Name:      %s\n" % name.strip('\'"')
                details += "Provider:  %s\n" % provider.strip('\'"')
                details += "Date:      %s\n" % date
                details += "Version:   %s\n" % version
                details += "Type:      %s\n" % dtype
                details += "Class:     %s\n\n" % dclass

            if len(details):
                d.scrollbox(details, width=WIDTH)
        else:  # Update button
            title = "Please select a directory that hosts VirtIO drivers."
            if not update_sysprep_param(session, "virtio", title=title):
                continue
            install_virtio_drivers(session)

    return True


def install_virtio_drivers(session):
    """Installs new VirtIO drivers in the image"""
    d = session['dialog']
    image = session['image']

    assert hasattr(image.os, 'install_virtio_drivers')

    virtio = image.os.sysprep_params['virtio'].value
    new_drivers = virtio_versions(image.os.compute_virtio_state(virtio))

    msg = \
        "The following VirtIO drivers were discovered in the directory you "\
        "specified:\n\n"
    for drv, drv_ver in new_drivers.items():
        msg += "%s: %s\n" % (drv, drv_ver)
    msg += "\nPress <Install> to continue with the installation of the " \
        "aforementioned drivers or <Cancel> to return to the previous menu."
    if d.yesno(msg, width=WIDTH, defaultno=1, height=11+len(new_drivers),
               yes_label="Install", no_label="Cancel") != d.OK:
        return False

    title = "VirtIO Drivers Installation"
    infobox = InfoBoxOutput(d, title)
    try:
        image.out.append(infobox)
        try:
            image.os.install_virtio_drivers()
            infobox.finalize()
        except FatalError as e:
            d.msgbox("VirtIO Drivers Installation failed: %s" % e, title=title,
                     width=SMALL_WIDTH)
            return False
        finally:
            image.out.remove(infobox)
    finally:
        infobox.cleanup()

    return True


def sysprep(session):
    """Perform various system preparation tasks on the image"""
    d = session['dialog']
    image = session['image']

    # Is the image already shrinked?
    if image.os.shrinked:
        msg = "It seems you have shrinked the image. Running system " \
              "preparation tasks on a shrinked image is dangerous."

        if d.yesno("%s\n\nDo you really want to continue?" % msg,
                   width=SMALL_WIDTH, defaultno=1) != d.OK:
            return

    wrapper = textwrap.TextWrapper(width=WIDTH-5)

    syspreps = image.os.list_syspreps()

    if len(syspreps) == 0:
        d.msgbox("No system preparation task available to run!",
                 title="System Preparation", width=SMALL_WIDTH)
        return

    while 1:
        choices = []
        index = 0

        help_title = "System Preparation Tasks"
        sysprep_help = "%s\n%s\n\n" % (help_title, '=' * len(help_title))

        for task in syspreps:
            name, descr, display = image.os.sysprep_info(task)
            sysprep_help += "%s\n" % display
            sysprep_help += "%s\n" % ('-' * len(display))
            sysprep_help += "%s\n\n" % wrapper.fill(" ".join(descr.split()))
            enabled = 1 if image.os.sysprep_enabled(task) else 0
            choices.append((str(index + 1), display, enabled))
            index += 1

        (code, tags) = d.checklist(
            "Please choose which system preparation tasks you would like to "
            "run on the image. Press <Params> to view or modify the "
            "customization parameters or <Help> to see details about the "
            "system preparation tasks.", title="Run system preparation tasks",
            choices=choices, width=70, ok_label="Run", help_button=1,
            extra_button=1, extra_label="Params")

        tags = [x.strip('"') for x in tags]  # Needed for OpenSUSE

        if code in (d.CANCEL, d.ESC):
            return False
        elif code == d.EXTRA:
            sysprep_params(session)
        elif code == d.HELP:
            d.scrollbox(sysprep_help, width=WIDTH)
        elif code == d.OK:
            # Enable selected syspreps and disable the rest
            for i in range(len(syspreps)):
                if str(i + 1) in tags:
                    image.os.enable_sysprep(syspreps[i])
                else:
                    image.os.disable_sysprep(syspreps[i])

            if len([s for s in image.os.list_syspreps()
                    if image.os.sysprep_enabled(s)]) == 0:
                d.msgbox("No system preparation task is selected!",
                         title="System Preparation", width=SMALL_WIDTH)
                continue

            infobox = InfoBoxOutput(d, "Image Configuration")
            try:
                image.out.append(infobox)
                try:
                    # The checksum is invalid. We have mounted the image rw
                    if 'checksum' in session:
                        del session['checksum']

                    # Monitor the metadata changes during syspreps
                    with MetadataMonitor(session, image.os.meta):
                        try:
                            image.os.do_sysprep()
                            update_background_title(session)
                            infobox.finalize()
                        except FatalError as error:
                            d.msgbox("System Preparation failed: %s" % error,
                                     title="System Preparation",
                                     width=SMALL_WIDTH)
                finally:
                    image.out.remove(infobox)
            finally:
                infobox.cleanup()
            break
    return True


def mount(session):
    """Mount image on the local file system"""
    d = session['dialog']
    image = session['image']

    mpoint = tempfile.mkdtemp()
    try:
        try:
            image.mount(mpoint)
            if not image.is_mounted():
                d.msgbox("Mounting Failed!", title="Mount Image",
                         width=SMALL_WIDTH)
                return
            d.msgbox("The image was mounted successfully. You may access it "
                     "under %s. Press <OK> when you have finished "
                     "accessing it." % mpoint, title="Mount Image",
                     width=SMALL_WIDTH)
        finally:
            while 1:
                if image.umount():
                    break
                d.msgbox("Umount failed. Make sure no process is using any "
                         "files under %s and press <OK>." % mpoint,
                         width=SMALL_WIDTH)
    finally:
        os.rmdir(mpoint)


def show_log(session):
    """Show the current execution log"""

    d = session['dialog']
    log = session['image'].out[0].stderr

    log.file.flush()

    while 1:
        code = d.textbox(log.name, title="Log", width=70, height=40,
                         extra_button=1, extra_label="Save", ok_label="Close")
        if code == d.EXTRA:
            while 1:
                path = select_file(d, title="Save log as...")
                if path is None:
                    break
                if os.path.isdir(path):
                    continue

                if copy_file(d, log.name, path):
                    break
        else:
            return


def customization_menu(session):
    """Show image customization menu"""
    d = session['dialog']
    image = session['image']

    choices = []
    if image.mount_local_support:
        choices.append(("Mount", "Mount image on the local file system"))
    if hasattr(image.os, "install_virtio_drivers"):
        choices.append(("VirtIO", "Install or update the VirtIO drivers"))
    choices.extend(
        [("Sysprep", "Run various image preparation tasks"),
         ("Properties", "View & Modify image properties"),
         ("Exclude", "Exclude various deployment tasks from running")])

    default_item = 0

    actions = {"Mount": mount,
               "VirtIO": virtio,
               "Sysprep": sysprep,
               "Properties": modify_properties,
               "Exclude": exclude_tasks}
    while 1:
        (code, choice) = d.menu(
            text="Choose one of the following or press <Back> to exit.",
            width=WIDTH, choices=choices, cancel="Back", height=13,
            menu_height=len(choices), default_item=choices[default_item][0],
            title="Image Customization Menu")

        if code in (d.CANCEL, d.ESC):
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
               ("Log", "Show current execution log"),
               ("Reset", "Reset everything and start over again"),
               ("Help", "Get help for using snf-image-creator")]

    default_item = "Customize"

    actions = {"Customize": customization_menu, "Register": kamaki_menu,
               "Extract": extract_image, "Log": show_log}
    title = "Image Creator for Synnefo (snf-image-creator v%s)" % version
    while 1:
        (code, choice) = d.menu(
            text="Choose one of the following or press <Exit> to exit.",
            width=WIDTH, choices=choices, cancel="Exit", height=13,
            default_item=default_item, menu_height=len(choices),
            title=title)

        if code in (d.CANCEL, d.ESC):
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

        if len(choice):
            default_item = choice

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
