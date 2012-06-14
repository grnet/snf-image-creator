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

from image_creator.util import FatalError

import textwrap
import re


def os_cls(distro, osfamily):
    module = None
    classname = None
    try:
        module = __import__("image_creator.os_type.%s"
            % distro, fromlist=['image_creator.os_type'])
        classname = distro.capitalize()
    except ImportError:
        module = __import__("image_creator.os_type.%s"
            % osfamily, fromlist=['image_creator.os_type'])
        classname = osfamily.capitalize()

    return getattr(module, classname)


def add_prefix(target):
    def wrapper(self, *args):
        prefix = args[0]
        return map(lambda x: prefix + x, target(self, *args))
    return wrapper


def sysprep(enabled=True):
    def wrapper(func):
        func.sysprep = True
        func.enabled = enabled
        return func
    return wrapper


class OSBase(object):
    """Basic operating system class"""

    def __init__(self, rootdev, ghandler, output):
        self.root = rootdev
        self.g = ghandler
        self.out = output

        # Collect metadata about the OS
        self.meta = {}
        self.meta['ROOT_PARTITION'] = "%d" % self.g.part_to_partnum(self.root)
        self.meta['OSFAMILY'] = self.g.inspect_get_type(self.root)
        self.meta['OS'] = self.g.inspect_get_distro(self.root)
        self.meta['DESCRIPTION'] = self.g.inspect_get_product_name(self.root)

    def _is_sysprep(self, obj):
        return getattr(obj, 'sysprep', False) and callable(obj)

    def list_syspreps(self):

        objs = [getattr(self, name) for name in dir(self) \
            if not name.startswith('_')]

        enabled = [x for x in objs if self._is_sysprep(x) and x.enabled]
        disabled = [x for x in objs if self._is_sysprep(x) and not x.enabled]

        return enabled, disabled

    def _sysprep_change_status(self, name, status):

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

        setattr(method.im_func, 'enabled', status)

    def enable_sysprep(self, name):
        """Enable a system preperation operation"""
        self._sysprep_change_status(name, True)

    def disable_sysprep(self, name):
        """Disable a system preperation operation"""
        self._sysprep_change_status(name, False)

    def print_syspreps(self):
        """Print enabled and disabled system preperation operations."""

        enabled, disabled = self.list_syspreps()

        wrapper = textwrap.TextWrapper()
        wrapper.subsequent_indent = '\t'
        wrapper.initial_indent = '\t'
        wrapper.width = 72

        self.out.output("Enabled system preperation operations:")
        if len(enabled) == 0:
            self.out.output("(none)")
        else:
            for sysprep in enabled:
                name = sysprep.__name__.replace('_', '-')
                descr = wrapper.fill(textwrap.dedent(sysprep.__doc__))
                self.out.output('    %s:\n%s\n' % (name, descr))

        self.out.output("Disabled system preperation operations:")
        if len(disabled) == 0:
            self.out.output("(none)")
        else:
            for sysprep in disabled:
                name = sysprep.__name__.replace('_', '-')
                descr = wrapper.fill(textwrap.dedent(sysprep.__doc__))
                self.out.output('    %s:\n%s\n' % (name, descr))

    @add_prefix
    def ls(self, directory):
        """List the name of all files under a directory"""
        return self.g.ls(directory)

    @add_prefix
    def find(self, directory):
        """List the name of all files recursively under a directory"""
        return self.g.find(directory)

    def foreach_file(self, directory, action, **kargs):
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
                self.foreach_file(full_path, action, **kargs)

            if has_ftype(f, ftype):
                action(full_path)

    def do_sysprep(self):
        """Prepere system for image creation."""

        self.out.output('Preparing system for image creation:')

        tasks, _ = self.list_syspreps()
        size = len(tasks)
        cnt = 0
        for task in tasks:
            cnt += 1
            self.out.output(('(%d/%d)' % (cnt, size)).ljust(7), False)
            task()
        self.out.output()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
