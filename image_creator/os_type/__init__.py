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

"""This package provides various classes for preparing different Operating
Systems for image creation.
"""

from image_creator.util import FatalError

import textwrap
import re
from collections import namedtuple


def os_cls(distro, osfamily):
    """Given the distro name and the osfamily, return the appropriate class"""
    module = None
    classname = None
    try:
        module = __import__("image_creator.os_type.%s" % distro,
                            fromlist=['image_creator.os_type'])
        classname = distro.capitalize()
    except ImportError:
        module = __import__("image_creator.os_type.%s" % osfamily,
                            fromlist=['image_creator.os_type'])
        classname = osfamily.capitalize()

    return getattr(module, classname)


def add_prefix(target):
    def wrapper(self, *args):
        prefix = args[0]
        return map(lambda x: prefix + x, target(self, *args))
    return wrapper


def sysprep(enabled=True):
    """Decorator for system preparation tasks"""
    def wrapper(func):
        func.sysprep = True
        func.enabled = enabled
        func.executed = False
        return func
    return wrapper


class OSBase(object):
    """Basic operating system class"""

    SysprepParam = namedtuple('SysprepParam',
                              'name description length validator')

    def __init__(self, image, **kargs):
        self.image = image

        self.root = image.root
        self.g = image.g
        self.out = image.out

        self.sysprep_params = \
            kargs['sysprep_params'] if 'sysprep_params' in kargs else {}

        self.meta = {}

    def collect_metadata(self):
        """Collect metadata about the OS"""
        try:
            if not self.mount(readonly=True):
                raise FatalError("Unable to mount the media read-only")

            self.out.output('Collecting image metadata ...', False)
            self._do_collect_metadata()
            self.out.success('done')
        finally:
            self.umount()

        self.out.output()

    def needed_sysprep_params(self):
        """Returns a list of needed sysprep parameters. Each element in the
        list is a SysprepParam object.
        """
        return []

    def list_syspreps(self):
        """Returns a list of sysprep objects"""
        objs = [getattr(self, name) for name in dir(self)
                if not name.startswith('_')]

        return [x for x in objs if self._is_sysprep(x) and x.executed is False]

    def sysprep_info(self, obj):
        """Returns information about a sysprep object"""
        assert self._is_sysprep(obj), "Object is not a sysprep"

        return (obj.__name__.replace('_', '-'), textwrap.dedent(obj.__doc__))

    def get_sysprep_by_name(self, name):
        """Returns the sysprep object with the given name"""
        error_msg = "Syprep operation %s does not exist for %s" % \
                    (name, self.__class__.__name__)

        method_name = name.replace('-', '_')
        method = None
        try:
            method = getattr(self, method_name)
        except AttributeError:
            raise FatalError(error_msg)

        if not self._is_sysprep(method):
            raise FatalError(error_msg)

        return method

    def enable_sysprep(self, obj):
        """Enable a system preparation operation"""
        setattr(obj.im_func, 'enabled', True)

    def disable_sysprep(self, obj):
        """Disable a system preparation operation"""
        setattr(obj.im_func, 'enabled', False)

    def print_syspreps(self):
        """Print enabled and disabled system preparation operations."""

        syspreps = self.list_syspreps()
        enabled = filter(lambda x: x.enabled, syspreps)
        disabled = filter(lambda x: not x.enabled, syspreps)

        wrapper = textwrap.TextWrapper()
        wrapper.subsequent_indent = '\t'
        wrapper.initial_indent = '\t'
        wrapper.width = 72

        self.out.output("Enabled system preparation operations:")
        if len(enabled) == 0:
            self.out.output("(none)")
        else:
            for sysprep in enabled:
                name = sysprep.__name__.replace('_', '-')
                descr = wrapper.fill(textwrap.dedent(sysprep.__doc__))
                self.out.output('    %s:\n%s\n' % (name, descr))

        self.out.output("Disabled system preparation operations:")
        if len(disabled) == 0:
            self.out.output("(none)")
        else:
            for sysprep in disabled:
                name = sysprep.__name__.replace('_', '-')
                descr = wrapper.fill(textwrap.dedent(sysprep.__doc__))
                self.out.output('    %s:\n%s\n' % (name, descr))

    def do_sysprep(self):
        """Prepare system for image creation."""

        try:
            if not self.mount(readonly=False):
                raise FatalError("Unable to mount the media read-write")

            self.out.output('Preparing system for image creation:')

            tasks = self.list_syspreps()
            enabled = filter(lambda x: x.enabled, tasks)

            size = len(enabled)
            cnt = 0
            for task in enabled:
                cnt += 1
                self.out.output(('(%d/%d)' % (cnt, size)).ljust(7), False)
                task()
                setattr(task.im_func, 'executed', True)
        finally:
            self.umount()

        self.out.output()

    def mount(self, readonly=False):
        """Mount image."""

        if getattr(self, "mounted", False):
            return True

        mount_type = 'read-only' if readonly else 'read-write'
        self.out.output("Mounting the media %s ..." % mount_type, False)

        if not self._do_mount(readonly):
            return False

        self.mounted = True
        self.out.success('done')
        return True

    def umount(self):
        """Umount all mounted filesystems."""

        self.out.output("Umounting the media ...", False)
        self.g.umount_all()
        self.mounted = False
        self.out.success('done')

    def _is_sysprep(self, obj):
        """Checks if an object is a sysprep"""
        return getattr(obj, 'sysprep', False) and callable(obj)

    @add_prefix
    def _ls(self, directory):
        """List the name of all files under a directory"""
        return self.g.ls(directory)

    @add_prefix
    def _find(self, directory):
        """List the name of all files recursively under a directory"""
        return self.g.find(directory)

    def _foreach_file(self, directory, action, **kargs):
        """Perform an action recursively on all files under a directory.

        The following options are allowed:

        * maxdepth: If defined the action will not be performed on
          files that are below this level of directories under the
          directory parameter.

        * ftype: The action will only be performed on files of this
          type. For a list of all allowed filetypes, see here:
          http://libguestfs.org/guestfs.3.html#guestfs_readdir

        * exclude: Exclude all files that follow this pattern.
        """
        maxdepth = None if 'maxdepth' not in kargs else kargs['maxdepth']
        if maxdepth == 0:
            return

        # maxdepth -= 1
        maxdepth = None if maxdepth is None else maxdepth - 1
        kargs['maxdepth'] = maxdepth

        exclude = None if 'exclude' not in kargs else kargs['exclude']
        ftype = None if 'ftype' not in kargs else kargs['ftype']
        has_ftype = lambda x, y: y is None and True or x['ftyp'] == y

        for f in self.g.readdir(directory):
            if f['name'] in ('.', '..'):
                continue

            full_path = "%s/%s" % (directory, f['name'])

            if exclude and re.match(exclude, full_path):
                continue

            if has_ftype(f, 'd'):
                self._foreach_file(full_path, action, **kargs)

            if has_ftype(f, ftype):
                action(full_path)

    def _do_collect_metadata(self):
        """helper method for collect_metadata"""
        self.meta['ROOT_PARTITION'] = "%d" % self.g.part_to_partnum(self.root)
        self.meta['OSFAMILY'] = self.g.inspect_get_type(self.root)
        self.meta['OS'] = self.g.inspect_get_distro(self.root)
        if self.meta['OS'] == "unknown":
            self.meta['OS'] = self.meta['OSFAMILY']
        self.meta['DESCRIPTION'] = self.g.inspect_get_product_name(self.root)

    def _do_mount(self, readonly):
        """helper method for mount"""
        try:
            self.g.mount_options('ro' if readonly else 'rw', self.root, '/')
        except RuntimeError as msg:
            self.out.warn("unable to mount the root partition: %s" % msg)
            return False

        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
