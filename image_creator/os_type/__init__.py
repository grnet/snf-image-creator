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

OSTYPE_ORDER = {
    "windows": 8,
    "linux": 7,
    "freebsd": 6,
    "netbsd": 5,
    "openbsd": 4,
    "hurd": 3,
    "dos": 2,
    "minix": 1
}


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
        assert method.__name__.startswith('_'), \
            "Invalid sysprep name:` %s'. Should start with _" % method.__name__

        method._sysprep = True
        method._sysprep_enabled = enabled
        method._sysprep_nomount = False

        for key, val in kwargs.items():
            setattr(method, "_sysprep_%s" % key, val)

        @wraps(method)
        def inner(self, print_message=True):
            if print_message:
                self.out.info(message)
            return method(self)

        return inner
    return wrapper


class SysprepParam(object):
    """This class represents a system preparation parameter"""

    def __init__(self, name, type, default, description, **kwargs):

        self.name = name
        self.is_list = type.startswith('list:')
        self.type = type.split(':', 1)[1] if self.is_list else type
        self.default = default
        self.description = description
        self.value = default
        self.error = None
        self.check = kwargs['check'] if 'check' in kwargs else lambda x: x
        self.hidden = kwargs['hidden'] if 'hidden' in kwargs else False

        assert hasattr(self, "_check_%s" % self.type), \
            "Invalid type: %s" % self.type

    def set_value(self, value):
        """Update the value of the parameter"""

        check_type = getattr(self, "_check_%s" % self.type)

        tmp = []

        for item in value if self.is_list else [value]:
            try:
                tmp.append(self.check(check_type(item)))
            except ValueError as e:
                self.error = e.message
                return False

        self.value = tmp if self.is_list else tmp[0]

        return True

    @staticmethod
    def _check_posint(value):
        """Check if the value is a positive integer"""
        try:
            value = int(value)
        except ValueError:
            raise ValueError("Invalid number")

        if value <= 0:
            raise ValueError("Value is negative or zero")

        return value

    @staticmethod
    def _check_string(value):
        """Check if a value is a string"""
        return str(value)

    @staticmethod
    def _check_file(value):
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

    @staticmethod
    def _check_dir(value):
        """Check if the value is a valid directory"""

        value = str(value)
        if len(value) == 0:
            return ""

        import os
        if os.path.isdir(value):
            return value

        raise ValueError("Invalid dirname")


def add_sysprep_param(name, type, default, descr, **kwargs):
    """Decorator for __init__ that adds the definition for a system preparation
    parameter in an instance of an os_type class
    """
    extra = kwargs

    def wrapper(init):
        @wraps(init)
        def inner(self, *args, **kwargs):

            if not hasattr(self, 'sysprep_params'):
                self.sysprep_params = {}

            self.sysprep_params[name] = \
                SysprepParam(name, type, default, descr, **extra)
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

    def __init__(self, image, **kwargs):
        self.image = image

        self.root = image.root
        self.out = image.out

        # Could be defined in a decorator
        if not hasattr(self, 'sysprep_params'):
            self.sysprep_params = {}

        if 'sysprep_params' in kwargs:
            for key, val in kwargs['sysprep_params'].items():
                if key not in self.sysprep_params:
                    self.out.warn("Ignoring invalid `%s' parameter." % key)
                    continue
                param = self.sysprep_params[key]
                if param.is_list:
                    def split_in_comma(val):
                        tmp = val.split(',')
                        prev = ""
                        for i in xrange(len(tmp)):
                            item = prev + tmp[i]
                            if item.endswith('\\'):
                                prev = item[:-1]
                                continue
                            prev = ""
                            yield item
                    val = list(split_in_comma(val))

                if not param.set_value(val):
                    raise FatalError("Invalid value for sysprep parameter: "
                                     "`%s'. Reason: %s" % (key, param.error))

        self.meta = self.image.meta
        self.shrinked = False

        # This will host the error if mount fails
        self._mount_error = ""
        self._mount_warnings = []
        self._mounted = False

        # Many guestfs compilations don't support scrub
        self._scrub_support = True
        try:
            self.image.g.available(['scrub'])
        except RuntimeError:
            self._scrub_support = False

        # Create a list of available syspreps
        self._sysprep_tasks = {}
        for name in dir(self):
            obj = getattr(self, name)
            if not hasattr(obj, '_sysprep'):
                continue
            self._sysprep_tasks[name] = obj._sysprep_enabled

        self._cleanup_jobs = {}

    def _add_cleanup(self, namespace, job, *args):
        """Add a new job in a cleanup list"""

        if namespace not in self._cleanup_jobs:
            self._cleanup_jobs[namespace] = []

        self._cleanup_jobs[namespace].append((job, args))

    def _cleanup(self, namespace):
        """Run the cleanup tasks that are defined under a specific namespace"""

        if namespace not in self._cleanup_jobs:
            self.out.warn("Cleanup namespace: `%s' is not defined", namespace)
            return

        while len(self._cleanup_jobs[namespace]):
            job, args = self._cleanup_jobs[namespace].pop()
            job(*args)

        del self._cleanup_jobs[namespace]

    def inspect(self):
        """Inspect the media to check if it is supported"""

        if self.image.is_unsupported():
            return

        self.out.info('Running OS inspection:')
        with self.mount(readonly=True, silent=True):
            self._do_inspect()
        self.out.info()

    def collect_metadata(self):
        """Collect metadata about the OS"""

        self.out.info('Collecting image metadata ...', False)

        with self.mount(readonly=True, silent=True):
            self._do_collect_metadata()

        self.out.success('done')
        self.out.info()

    def list_syspreps(self):
        """Returns a list of sysprep objects"""
        return [getattr(self, name) for name in self._sysprep_tasks]

    def sysprep_info(self, obj):
        """Returns information about a sysprep object"""
        assert hasattr(obj, '_sysprep'), "Object is not a sysprep"

        SysprepInfo = namedtuple("SysprepInfo", "name description display")

        name = obj.__name__.replace('_', '-')[1:]
        description = textwrap.dedent(obj.__doc__)
        display = getattr(obj, '_sysprep_display',
                          name.replace('-', ' ').capitalize())

        return SysprepInfo(name, description, display)

    def get_sysprep_by_name(self, name):
        """Returns the sysprep object with the given name"""

        method_name = '_' + name.replace('-', '_')

        if hasattr(self, method_name):
            method = getattr(self, method_name)

            if hasattr(method, '_sysprep'):
                return method

        return None

    def enable_sysprep(self, obj):
        """Enable a system preparation operation"""
        assert hasattr(obj, '_sysprep'), "Object is not a sysprep"
        assert obj.__name__ in self._sysprep_tasks, "Sysprep already executed"

        self._sysprep_tasks[obj.__name__] = True

    def disable_sysprep(self, obj):
        """Disable a system preparation operation"""
        assert hasattr(obj, '_sysprep'), "Object is not a sysprep"
        assert obj.__name__ in self._sysprep_tasks, "Sysprep already executed"

        self._sysprep_tasks[obj.__name__] = False

    def sysprep_enabled(self, obj):
        """Returns True if this system praparation operation is enabled"""
        assert hasattr(obj, '_sysprep'), "Object is not a sysprep"
        assert obj.__name__ in self._sysprep_tasks, "Sysprep already executed"

        return self._sysprep_tasks[obj.__name__]

    def print_metadata(self):
        """Print the image metadata"""

        self.out.info("Detected image metadata:")

        col_width = max(len(key) for key in self.meta) + 2
        for key, val in self.meta.items():
            self.out.info("%s %s" % (key.ljust(col_width), val))

    def print_syspreps(self):
        """Print enabled and disabled system preparation operations"""

        syspreps = self.list_syspreps()
        enabled = [s for s in syspreps if self.sysprep_enabled(s)]
        disabled = [s for s in syspreps if not self.sysprep_enabled(s)]

        wrapper = textwrap.TextWrapper()
        wrapper.subsequent_indent = '\t'
        wrapper.initial_indent = '\t'
        wrapper.width = 72

        self.out.info("Enabled system preparation operations:")
        if len(enabled) == 0:
            self.out.info("(none)")
        else:
            for sysprep in enabled:
                name = sysprep.__name__.replace('_', '-')[1:]
                descr = wrapper.fill(textwrap.dedent(sysprep.__doc__))
                self.out.info('    %s:\n%s\n' % (name, descr))

        self.out.info("Disabled system preparation operations:")
        if len(disabled) == 0:
            self.out.info("(none)")
        else:
            for sysprep in disabled:
                name = sysprep.__name__.replace('_', '-')[1:]
                descr = wrapper.fill(textwrap.dedent(sysprep.__doc__))
                self.out.info('    %s:\n%s\n' % (name, descr))

    def print_sysprep_params(self):
        """Print the system preparation parameter the user may use"""

        self.out.info("System preparation parameters:")
        self.out.info()

        public_params = [(n, p) for n, p in self.sysprep_params.items()
                         if not p.hidden]
        if len(public_params) == 0:
            self.out.info("(none)")
            return

        wrapper = textwrap.TextWrapper()
        wrapper.subsequent_indent = "             "
        wrapper.width = 80

        for name, param in public_params:
            if param.hidden:
                continue
            self.out.info("NAME:".ljust(13) + name)
            self.out.info(wrapper.fill("DESCRIPTION:".ljust(13) +
                                       "%s" % param.description))
            self.out.info("TYPE:".ljust(13) + "%s%s" %
                          ("list:" if param.is_list else "", param.type))
            self.out.info("VALUE:".ljust(13) +
                          ("\n".ljust(14).join(param.value) if param.is_list
                           else param.value))
            self.out.info()

    def do_sysprep(self):
        """Prepare system for image creation."""

        self.out.info('Preparing system for image creation:')

        if self.image.is_unsupported():
            self.out.warn(
                "System preparation is disabled for unsupported media")
            return

        enabled = [s for s in self.list_syspreps() if self.sysprep_enabled(s)]
        size = len(enabled)
        cnt = 0

        def exec_sysprep(cnt, size, task):
            self.out.info(('(%d/%d)' % (cnt, size)).ljust(7), False)
            task()
            del self._sysprep_tasks[task.__name__]

        with self.mount():
            for task in [t for t in enabled if t._sysprep_nomount is False]:
                cnt += 1
                exec_sysprep(cnt, size, task)

        for task in [t for t in enabled if t._sysprep_nomount]:
            cnt += 1
            exec_sysprep(cnt, size, task)

        self.out.info()

    @sysprep('Shrinking image (may take a while)', nomount=True)
    def _shrink(self):
        """Shrink the last file system and update the partition table"""
        self.image.shrink()
        self.shrinked = True

    @property
    def ismounted(self):
        return self._mounted

    def mount(self, readonly=False, silent=False, fatal=True):
        """Returns a context manager for mounting an image"""

        parent = self
        output = lambda msg='', nl=True: None if silent else self.out.info
        success = lambda msg='', nl=True: None if silent else self.out.success
        warn = lambda msg='', nl=True: None if silent else self.out.warn

        class Mount:
            """The Mount context manager"""
            def __enter__(self):
                mount_type = 'read-only' if readonly else 'read-write'
                output("Mounting the media %s ..." % mount_type, False)

                parent._mount_error = ""
                del parent._mount_warnings[:]

                try:
                    parent._mounted = parent._do_mount(readonly)
                except:
                    parent.image.g.umount_all()
                    raise

                if not parent.ismounted:
                    msg = "Unable to mount the media %s. Reason: %s" % \
                        (mount_type, parent._mount_error)
                    if fatal:
                        raise FatalError(msg)
                    else:
                        warn(msg)

                for warning in parent._mount_warnings:
                    warn(warning)

                if parent.ismounted:
                    success('done')

            def __exit__(self, exc_type, exc_value, traceback):
                output("Umounting the media ...", False)
                parent.image.g.umount_all()
                parent._mounted = False
                success('done')

        return Mount()

    def check_version(self, major, minor):
        """Checks the OS version against the one specified by the major, minor
        tuple.

        Returns:
            < 0 if the OS version is smaller than the specified one
            = 0 if they are equal
            > 0 if it is greater
        """
        guestfs = self.image.g
        for a, b in ((guestfs.inspect_get_major_version(self.root), major),
                     (guestfs.inspect_get_minor_version(self.root), minor)):
            if a != b:
                return a - b

        return 0

    @add_prefix
    def _ls(self, directory):
        """List the name of all files under a directory"""
        return self.image.g.ls(directory)

    @add_prefix
    def _find(self, directory):
        """List the name of all files recursively under a directory"""
        return self.image.g.find(directory)

    def _foreach_file(self, directory, action, **kwargs):
        """Perform an action recursively on all files under a directory.

        The following options are allowed:

        * maxdepth: If defined, the action will not be performed on files that
          are below this level of directories under the directory parameter.

        * ftype: The action will only be performed on files of this type. For a
          list of all allowed file types, see here:
          http://libguestfs.org/guestfs.3.html#guestfs_readdir

        * exclude: Exclude all files that follow this pattern.

        * include: Only include files that follow this pattern.
        """
        if not self.image.g.is_dir(directory):
            self.out.warn("Directory: `%s' does not exist!" % directory)
            return

        maxdepth = None if 'maxdepth' not in kwargs else kwargs['maxdepth']
        if maxdepth == 0:
            return

        # maxdepth -= 1
        maxdepth = None if maxdepth is None else maxdepth - 1
        kwargs['maxdepth'] = maxdepth

        exclude = None if 'exclude' not in kwargs else kwargs['exclude']
        include = None if 'include' not in kwargs else kwargs['include']
        ftype = None if 'ftype' not in kwargs else kwargs['ftype']
        has_ftype = lambda x, y: y is None and True or x['ftyp'] == y

        for f in self.image.g.readdir(directory):
            if f['name'] in ('.', '..'):
                continue

            full_path = "%s/%s" % (directory, f['name'])

            if exclude and re.match(exclude, full_path):
                continue

            if include and not re.match(include, full_path):
                continue

            if has_ftype(f, 'd'):
                self._foreach_file(full_path, action, **kwargs)

            if has_ftype(f, ftype):
                action(full_path)

    def _do_inspect(self):
        """helper method for inspect"""
        self.out.warn("No inspection method available")

    def _do_collect_metadata(self):
        """helper method for collect_metadata"""

        try:
            self.meta['ROOT_PARTITION'] = \
                "%d" % self.image.g.part_to_partnum(self.root)
        except RuntimeError:
            self.out.warn("Unable to identify the partition number from root "
                          "partition: %s" % self.root)

        osfamily = self.image.g.inspect_get_type(self.root)
        distro = self.image.g.inspect_get_distro(self.root)
        name = self.image.g.inspect_get_product_name(self.root)

        self.meta['OSFAMILY'] = osfamily
        self.meta['OS'] = distro if distro != "unknown" else osfamily
        self.meta['DESCRIPTION'] = name
        try:
            self.meta['SORTORDER'] = 1000000 * OSTYPE_ORDER[osfamily]
        except KeyError:
            self.meta['SORTORDER'] = 0

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
