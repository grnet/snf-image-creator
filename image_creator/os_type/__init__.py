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

"""This package provides various classes for preparing different Operating
Systems for image creation.
"""

from image_creator.util import FatalError

import textwrap
import re
from collections import namedtuple
from functools import wraps


def os_cls(distro, osfamily):
    """Given the distro name and the osfamily, return the appropriate OSBase
    derived class
    """

    # hyphens are not allowed in module names
    canonicalize = lambda x: x.replace('-', '_').lower()

    distro = canonicalize(distro)
    osfamily = canonicalize(osfamily)

    try:
        module = __import__("image_creator.os_type.%s" % distro,
                            fromlist=['image_creator.os_type'])
        classname = distro.capitalize()
    except ImportError:
        try:
            module = __import__("image_creator.os_type.%s" % osfamily,
                                fromlist=['image_creator.os_type'])
            classname = osfamily.capitalize()
        except ImportError:
            raise FatalError("Unknown OS name: `%s'" % osfamily)

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


class SysprepParam(object):
    """This class represents an system preparation parameter"""

    def __init__(self, type, default, description):

        type_checker = {"posint": self._check_posint,
                        "string": self._check_string,
                        "file": self._check_fname,
                        "dir": self._check_dname}

        assert type in type_checker.keys(), "Invalid parameter type: %s" % type

        self.type = type
        self.default = default
        self.description = description
        self.value = default
        self.error = None

        self._checker = type_checker[type]

    def set_value(self, value):
        """Update the value of the parameter"""
        try:
            self.value = self._checker(value)
        except ValueError as e:
            self.error = e.message
            return False
        return True

    def _check_posint(self, value):
        """Check if the value is a positive integer"""
        try:
            value = int(value)
        except ValueError:
            raise ValueError("Invalid number")

        if value <= 0:
            raise ValueError("Value is negative or zero")

        return value

    def _check_string(self, value):
        """Check if a value is a string"""
        return str(value)

    def _check_fname(self, value):
        """Check if the value is a valid filename"""

        value = str(value)
        if len(value) == 0:
            return ""

        import os

        def isblockdev(filename):
            import stat
            try:
                return stat.S_ISBLK(os.stat(filename).st_mode)
            except OSError:
                return False
        if os.path.isfile(value) or isblockdev(value):
            return value

        raise ValueError("Invalid filename")

    def _check_dname(self, value):
        """Check if the value is a valid directory"""

        value = str(value)
        if len(value) == 0:
            return ""

        import os
        if os.path.isdir(value):
            return value

        raise ValueError("Invalid dirname")


def add_sysprep_param(name, type, default, descr):
    """Decorator for __init__ that adds the definition for a system preparation
    parameter in an instance of an os_type class
    """
    def wrapper(init):
        @wraps(init)
        def inner(self, *args, **kwargs):

            if not hasattr(self, 'sysprep_params'):
                self.sysprep_params = {}

            self.sysprep_params[name] = SysprepParam(type, default, descr)

            init(self, *args, **kwargs)
        return inner
    return wrapper


def del_sysprep_param(name):
    """Decorator for __init__ that deletes a previously added sysprep parameter
    definition from an instance of a os_type class.
    """
    def wrapper(func):
        @wraps(func)
        def inner(self, *args, **kwargs):
            del self.sysprep_params[name]
            func(self, *args, **kwargs)
        return inner
    return wrapper


class OSBase(object):
    """Basic operating system class"""

    def __init__(self, image, **kargs):
        self.image = image

        self.root = image.root
        self.out = image.out

        # Could be defined in a decorator
        if not hasattr(self, 'sysprep_params'):
            self.sysprep_params = {}

        if 'sysprep_params' in kargs:
            for key, val in kargs['sysprep_params'].items():
                param = self.sysprep_params[key]
                if not param.set_value(val):
                    raise FatalError("Invalid value for sysprep parameter: "
                                     "`%s'. Reason: %s" % (key, param.error))

        self.meta = {}
        self.mounted = False

        # This will host the error if mount fails
        self._mount_error = ""

        # Many guestfs compilations don't support scrub
        self._scrub_support = True
        try:
            self.image.g.available(['scrub'])
        except RuntimeError:
            self._scrub_support = False

    def inspect(self):
        """Inspect the media to check if it is supported"""

        if self.image.is_unsupported():
            return

        self.out.output('Running OS inspection:')
        try:
            if not self.mount(readonly=True, silent=True):
                raise FatalError("Unable to mount the media read-only")
            self._do_inspect()
        finally:
            self.umount(silent=True)

        self.out.output()

    def collect_metadata(self):
        """Collect metadata about the OS"""
        try:
            if not self.mount(readonly=True, silent=True):
                raise FatalError("Unable to mount the media read-only")

            self.out.output('Collecting image metadata ...', False)
            self._do_collect_metadata()
            self.out.success('done')
        finally:
            self.umount(silent=True)

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

        self.out.output("System preparation parameters:")
        self.out.output()

        if len(self.sysprep_params) == 0:
            self.out.output("(none)")
            return

        wrapper = textwrap.TextWrapper()
        wrapper.subsequent_indent = "             "
        wrapper.width = 72

        for name, param in self.sysprep_params.items():
            self.out.output("NAME:        %s" % name)
            self.out.output("VALUE:       %s" % param.value)
            self.out.output(
                wrapper.fill("DESCRIPTION: %s" % param.description))
            self.out.output()

    def do_sysprep(self):
        """Prepare system for image creation."""

        self.out.output('Preparing system for image creation:')

        if self.image.is_unsupported():
            self.out.warn(
                "System preparation is disabled for unsupported media")
            return

        try:
            if not self.mount(readonly=False):
                msg = "Unable to mount the media read-write. Reason: %s" % \
                    self._mount_error
                raise FatalError(msg)

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

    def mount(self, readonly=False, silent=False):
        """Mount image."""

        if getattr(self, "mounted", False):
            return True

        mount_type = 'read-only' if readonly else 'read-write'
        if not silent:
            self.out.output("Mounting the media %s ..." % mount_type, False)

        self._mount_error = ""
        if not self._do_mount(readonly):
            return False

        self.mounted = True
        if not silent:
            self.out.success('done')
        return True

    def umount(self, silent=False):
        """Umount all mounted file systems."""

        if not silent:
            self.out.output("Umounting the media ...", False)
        self.image.g.umount_all()
        self.mounted = False
        if not silent:
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

        * maxdepth: If defined, the action will not be performed on files that
          are below this level of directories under the directory parameter.

        * ftype: The action will only be performed on files of this type. For a
          list of all allowed file types, see here:
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

    def _do_inspect(self):
        """helper method for inspect"""
        self.out.warn("No inspection method available")
        pass

    def _do_collect_metadata(self):
        """helper method for collect_metadata"""

        try:
            self.meta['ROOT_PARTITION'] = \
                "%d" % self.image.g.part_to_partnum(self.root)
        except RuntimeError:
            self.out.warn("Unable to identify the partition number from root "
                          "partition: %s" % self.root)

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
            self._mount_error = str(msg)
            return False

        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
