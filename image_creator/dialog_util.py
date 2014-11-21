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

"""Module providing useful functions for the dialog-based version of
snf-image-creator.
"""

import os
import stat
import re
import json
from image_creator.output.dialog import GaugeOutput
from image_creator.kamaki_wrapper import Kamaki

SMALL_WIDTH = 60
WIDTH = 70


def select_file(d, **kwargs):
    """Select a file or directory.

    The following optional arguments can be applied:

    * init: Initial file path. If this path is valid this will be returned

    * ftype: Allowed file types. If the value of this argument is "br" only
             block devices and regular files are valid. For a list of available
             file types, see here:
             http://libguestfs.org/guestfs.3.html#guestfs_readdir

    * title: The dialog box title. The default one is: "Please select a file"

    * bundle_host: This can be True or False. If this is True, an extra
      "Bundle Host" button will be present if the file selection dialog.
    """

    type_check = {'b': stat.S_ISBLK,   # Block special
                  'c': stat.S_ISCHR,   # Char special
                  'd': stat.S_ISDIR,   # Directory
                  'f': stat.S_ISFIFO,  # FIFO (named pipe)
                  'l': stat.S_ISLNK,   # Symbolic link
                  'r': stat.S_ISREG,   # Regular file
                  's': stat.S_ISSOCK}  # Socket

    fname = None if "init" not in kwargs else kwargs['init']
    ftype = set(t for t in kwargs['ftype']) if 'ftype' in kwargs else set('r')
    title = kwargs['title'] if 'title' in kwargs else 'Please select a file.'

    bundle_host = kwargs['bundle_host'] if 'bundle_host' in kwargs else None
    extra_button = 1 if bundle_host else 0

    for t in ftype:
        assert t in type_check, "Invalid ftype: %s" % t

    # This is a special case
    if bundle_host and fname == os.sep:
        return os.sep

    default = os.getcwd() + os.sep

    while 1:
        if fname is not None:
            if not os.path.exists(fname):
                d.msgbox("The file `%s' you choose does not exist." % fname,
                         width=SMALL_WIDTH)
            else:
                mode = os.stat(fname).st_mode
                for i in ftype:
                    if type_check[i](mode):
                        return fname

                if stat.S_ISDIR(mode):
                    default = fname
                else:
                    d.msgbox("Invalid input.", width=SMALL_WIDTH)

        (code, fname) = d.fselect(default, 10, 60, extra_button=extra_button,
                                  title=title, extra_label="Bundle Host")
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return None
        elif code == d.DIALOG_EXTRA:
            return os.sep

    return fname


def update_background_title(session):
    """Update the background title of the dialog page"""
    d = session['dialog']
    disk = session['disk']
    image = session['image']

    MB = 2 ** 20

    size = (image.size + MB - 1) // MB
    postfix = " (shrinked)" if image.os.shrinked else ''

    title = "OS: %s, Distro: %s, Size: %dMB%s, Source: %s" % \
            (image.ostype.capitalize(), image.distro.capitalize(), size,
             postfix, os.path.abspath(disk.source))

    d.setBackgroundTitle(title)


def confirm_exit(d, msg=''):
    """Ask the user to confirm when exiting the program"""
    return not d.yesno("%s Do you want to exit?" % msg, width=SMALL_WIDTH)


def confirm_reset(d):
    """Ask the user to confirm a reset action"""
    return not d.yesno("Are you sure you want to reset everything?",
                       width=SMALL_WIDTH, defaultno=1)


class Reset(Exception):
    """Exception used to reset the program"""
    pass


def extract_metadata_string(session):
    """Convert image metadata to text"""
    metadata = {}
    metadata.update(session['image'].meta)
    if 'task_metadata' in session:
        for key in session['task_metadata']:
            metadata[key] = 'yes'

    return unicode(json.dumps({'properties': metadata,
                               'disk-format': 'diskdump'}, ensure_ascii=False))


def extract_image(session):
    """Dump the image to a local file"""
    d = session['dialog']
    dir = os.getcwd()
    while 1:
        if dir and dir[-1] != os.sep:
            dir = dir + os.sep

        (code, path) = d.fselect(dir, 10, 50, title="Save image as...")
        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        if os.path.isdir(path):
            dir = path
            continue

        if os.path.isdir("%s.meta" % path):
            d.msgbox("Can't overwrite directory `%s.meta'" % path,
                     width=SMALL_WIDTH)
            continue

        if os.path.isdir("%s.md5sum" % path):
            d.msgbox("Can't overwrite directory `%s.md5sum'" % path,
                     width=SMALL_WIDTH)
            continue

        basedir = os.path.dirname(path)
        name = os.path.basename(path)
        if not os.path.exists(basedir):
            d.msgbox("Directory `%s' does not exist" % basedir,
                     width=SMALL_WIDTH)
            continue

        dir = basedir
        if len(name) == 0:
            continue

        files = ["%s%s" % (path, ext) for ext in ('', '.meta', '.md5sum')]
        overwrite = filter(os.path.exists, files)

        if len(overwrite) > 0:
            if d.yesno("The following file(s) exist:\n"
                       "%s\nDo you want to overwrite them?" %
                       "\n".join(overwrite), width=SMALL_WIDTH):
                continue

        gauge = GaugeOutput(d, "Image Extraction", "Extracting image...")
        try:
            image = session['image']
            out = image.out
            out.add(gauge)
            try:
                if "checksum" not in session:
                    session['checksum'] = image.md5()

                # Extract image file
                image.dump(path)

                # Extract metadata file
                out.output("Extracting metadata file ...")
                with open('%s.meta' % path, 'w') as f:
                    f.write(extract_metadata_string(session))
                out.success('done')

                # Extract md5sum file
                out.output("Extracting md5sum file ...")
                md5str = "%s %s\n" % (session['checksum'], name)
                with open('%s.md5sum' % path, 'w') as f:
                    f.write(md5str)
                out.success("done")
            finally:
                out.remove(gauge)
        finally:
            gauge.cleanup()
        d.msgbox("Image file `%s' was successfully extracted!" % path,
                 width=SMALL_WIDTH)
        break

    return True


def _check_cloud(session, name, url, token):
    """Checks if the provided info for a cloud are valid"""
    d = session['dialog']
    regexp = re.compile(r'^[~@#$:\-\w]+$')

    if not re.match(regexp, name):
        d.msgbox("Allowed characters for name: a-zA-Z0-9_~@#$:-", width=WIDTH)
        return False

    if len(url) == 0:
        d.msgbox("URL cannot be empty!", width=WIDTH)
        return False

    if len(token) == 0:
        d.msgbox("Token cannot be empty!", width=WIDTH)
        return False

    if Kamaki.create_account(url, token) is None:
        d.msgbox("The cloud info you provided is not valid. Please check the "
                 "Authentication URL and the token values again!", width=WIDTH)
        return False

    return True


def add_cloud(session):
    """Add a new cloud account"""

    d = session['dialog']

    name = ""
    description = ""
    url = ""
    token = ""

    while 1:
        fields = [
            ("Name:", name, 60),
            ("Description (optional): ", description, 80),
            ("Authentication URL: ", url, 200),
            ("Token:", token, 100)]

        (code, output) = d.form("Add a new cloud account:", height=13,
                                width=WIDTH, form_height=4, fields=fields)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        name, description, url, token = output

        name = name.strip()
        description = description.strip()
        url = url.strip()
        token = token.strip()

        if _check_cloud(session, name, url, token):
            if name in Kamaki.get_clouds().keys():
                d.msgbox("A cloud with name `%s' already exists. If you want "
                         "to edit the existing cloud account, use the edit "
                         "menu." % name, width=WIDTH)
            else:
                Kamaki.save_cloud(name, url, token, description)
                break

        continue

    return True


def edit_cloud(session, name):
    """Edit a cloud account"""

    info = Kamaki.get_cloud_by_name(name)

    assert info, "Cloud: `%s' does not exist" % name

    description = info['description'] if 'description' in info else ""
    url = info['url'] if 'url' in info else ""
    token = info['token'] if 'token' in info else ""

    d = session['dialog']

    while 1:
        fields = [
            ("Description (optional): ", description, 80),
            ("Authentication URL: ", url, 200),
            ("Token:", token, 100)]

        (code, output) = d.form("Edit cloud account: `%s'" % name, height=13,
                                width=WIDTH, form_height=3, fields=fields)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return False

        description, url, token = output

        description = description.strip()
        url = url.strip()
        token = token.strip()

        if _check_cloud(session, name, url, token):
            Kamaki.save_cloud(name, url, token, description)
            break

        continue

    return True


def _get_sysprep_param_value(session, param, default, title=None,
                             delete=False):
    """Get the value of a sysprep parameter"""
    d = session['dialog']

    if param.type in ("file", "dir"):
        if not title:
            title = "Please select a %s to use for the `%s' parameter" % \
                ('file' if param.type == 'file' else 'directory', param.name)
        ftype = "br" if param.type == 'file' else 'd'

        value = select_file(d, ftype=ftype, title=title)
    else:
        if not title:
            title = ("Please provide a new value for configuration parameter: "
                     "`%s' or press <Delete> to completely delete it." %
                     param.name)
        (code, answer) = d.inputbox(title, width=WIDTH, init=str(default),
                                    extra_button=int(delete),
                                    extra_label="Delete")

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return (None, False)
        if code == d.DIALOG_EXTRA:
            return ("", True)

        value = answer.strip()

    return (value, False)


def update_sysprep_param(session, name, title=None):
    """Modify the value of a sysprep parameter"""

    d = session['dialog']
    image = session['image']

    param = image.os.sysprep_params[name]

    default_item = 1
    while 1:
        value = []
        for i in param.value:
            value.append(i)
        if param.is_list:
            choices = [(str(i+1), str(value[i])) for i in xrange(len(value))]
            if len(choices) == 0:
                action = 'add'
                default_value = ""
            else:
                (code, choice) = d.menu(
                    "Please press <Edit> to edit or remove a value or <Add> "
                    "to add a new one. Press <Back> to go back.", height=18,
                    width=WIDTH, choices=choices, menu_height=10,
                    ok_label="Edit", extra_button=1, extra_label="Add",
                    cancel="Back", default_item=str(default_item), title=name)

                if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
                    return True
                elif code == d.DIALOG_EXTRA:
                    action = 'add'
                    default_value = ""
                elif code == d.DIALOG_OK:
                    action = 'edit'
                    choice = int(choice)
                    default_value = choices[choice-1][1]
                    default_item = choice
        else:
            default_value = param.value
            action = 'edit'

        (new_value, delete) = _get_sysprep_param_value(
            session, param, default_value, title,
            delete=(param.is_list and action == 'edit'))

        if new_value is None:
            if not param.is_list or len(param.value) == 0:
                return False
            continue

        if param.is_list:
            if action == 'add':
                value = value + [new_value]
            if action == 'edit':
                if delete:
                    del value[choice-1]
                else:
                    value[choice-1] = new_value

        if param.set_value(value) is False:
            d.msgbox("Error: %s" % param.error, width=WIDTH)
            param.error = None
            continue
        elif param.is_list:
            if action == 'add':
                default_item = len(param.value)
            elif delete:
                default_item = (default_item - 1) if default_item > 1 else 1

        if not param.is_list or len(param.value) == 0:
            break

    return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
