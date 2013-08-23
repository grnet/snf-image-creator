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
from functools import wraps


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
    """Decorator that adds a prefix to the result of a function"""
    def wrapper(self, *args):
        prefix = args[0]
        return [prefix + path for path in target(self, *args)]
    return wrapper


def sysprep(message, enabled=True, **kwargs):
    """Decorator for system preparation tasks"""
    def wrapper(method):
        method.sysprep = True
        method.enabled = enabled
        method.executed = False

        for key, val in kwargs.items():
            setattr(method, key, val)

        @wraps(method)
        def inner(self, print_message=True):
            if print_message:
                self.out.output(message)
            return method(self)

        return inner
    return wrapper


def add_sysprep_param(name, type, default, descr, validate=lambda x: True):
    """Decorator for __init__ that adds the definition for a system preparation
    parameter in an instance of a os_type class
    """
    def wrapper(init):
        @wraps(init)
        def inner(self, *args, **kwargs):
            init(self, *args, **kwargs)
            self.needed_sysprep_params[name] = \
                self.SysprepParam(type, default, descr, validate)
            if default is not None:
                self.sysprep_params[name] = default
        return inner
    return wrapper


def del_sysprep_param(name):
    """Decorator for __init__ that deletes a previously added sysprep parameter
    definition from an instance of a os_type class.
    """
    def wrapper(func):
        @wraps(func)
        def inner(self, *args, **kwargs):
            del self.needed_sysprep_params[name]
            func(self, *args, **kwargs)
        return inner
    return wrapper


class OSBase(object):
    """Basic operating system class"""

    SysprepParam = namedtuple('SysprepParam',
                              ['type', 'default', 'description', 'validate'])

    def __init__(self, image, **kargs):
        self.image = image

        self.root = image.root
        self.out = image.out

        self.needed_sysprep_params = {}
        self.sysprep_params = \
            kargs['sysprep_params'] if 'sysprep_params' in kargs else {}

        self.meta = {}
        self.mounted = False

        # Many guestfs compilations don't support scrub
        self._scrub_support = True
        try:
            self.image.g.available(['scrub'])
        except RuntimeError:
            self._scrub_support = False

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

    def list_syspreps(self):
        """Returns a list of sysprep objects"""
        objs = [getattr(self, name) for name in dir(self)
                if not name.startswith('_')]

        return [x for x in objs if self._is_sysprep(x) and x.executed is False]

    def sysprep_info(self, obj):
        """Returns information about a sysprep object"""
        assert self._is_sysprep(obj), "Object is not a sysprep"

        SysprepInfo = namedtuple("SysprepInfo", "name description")

        return SysprepInfo(obj.__name__.replace('_', '-'),
                           textwrap.dedent(obj.__doc__))

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
        enabled = [sysprep for sysprep in syspreps if sysprep.enabled]
        disabled = [sysprep for sysprep in syspreps if not sysprep.enabled]

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

    def print_sysprep_params(self):
        """Print the system preparation parameter the user may use"""

        self.out.output("Needed system preparation parameters:")

        if len(self.needed_sysprep_params) == 0:
            self.out.output("(none)")
            return

        for name, param in self.needed_sysprep_params.items():
            self.out.output("\t%s (%s): %s" %
                            (param.description, name,
                             self.sysprep_params[name] if name in
                             self.sysprep_params else "(none)"))

    def do_sysprep(self):
        """Prepare system for image creation."""

        try:
            if not self.mount(readonly=False):
                raise FatalError("Unable to mount the media read-write")

            self.out.output('Preparing system for image creation:')

            enabled = [task for task in self.list_syspreps() if task.enabled]

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
        self.image.g.umount_all()
        self.mounted = False
        self.out.success('done')

    def _is_sysprep(self, obj):
        """Checks if an object is a sysprep"""
        return getattr(obj, 'sysprep', False) and callable(obj)

    @add_prefix
    def _ls(self, directory):
        """List the name of all files under a directory"""
        return self.image.g.ls(directory)

    @add_prefix
    def _find(self, directory):
        """List the name of all files recursively under a directory"""
        return self.image.g.find(directory)

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
        if not self.image.g.is_dir(directory):
            self.out.warn("Directory: `%s' does not exist!" % directory)
            return

        maxdepth = None if 'maxdepth' not in kargs else kargs['maxdepth']
        if maxdepth == 0:
            return

        # maxdepth -= 1
        maxdepth = None if maxdepth is None else maxdepth - 1
        kargs['maxdepth'] = maxdepth

        exclude = None if 'exclude' not in kargs else kargs['exclude']
        ftype = None if 'ftype' not in kargs else kargs['ftype']
        has_ftype = lambda x, y: y is None and True or x['ftyp'] == y

        for f in self.image.g.readdir(directory):
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
        self.meta['ROOT_PARTITION'] = \
            "%d" % self.image.g.part_to_partnum(self.root)
        self.meta['OSFAMILY'] = self.image.g.inspect_get_type(self.root)
        self.meta['OS'] = self.image.g.inspect_get_distro(self.root)
        if self.meta['OS'] == "unknown":
            self.meta['OS'] = self.meta['OSFAMILY']
        self.meta['DESCRIPTION'] = \
            self.image.g.inspect_get_product_name(self.root)

    def _do_mount(self, readonly):
        """helper method for mount"""
        try:
            self.image.g.mount_options(
                'ro' if readonly else 'rw', self.root, '/')
        except RuntimeError as msg:
            self.out.warn("unable to mount the root partition: %s" % msg)
            return False

        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
