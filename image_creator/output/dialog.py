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

"""This module provides various dialog-based Output classes"""

from image_creator.output import Output
import time
import fcntl


class GaugeOutput(Output):
    """Output class implemented using dialog's gauge widget"""
    def __init__(self, dialog, title, msg=''):
        self.d = dialog
        self.msg = msg
        self.percent = 0
        self.d.gauge_start(self.msg, title=title)

        # Open pipe workaround. A fork will duplicate the open file descriptor.
        # The FD_CLOEXEC flag makes sure that the gauge internal fd will be
        # closed if execve is executed. This is needed because libguestfs will
        # fork/exec the KVM process. If this fd stays open in the KVM process,
        # then doing a gauge_stop will make this process wait forever for
        # a dialog process that is blocked waiting for input from the KVM
        # process's open file descriptor.
        fd = self.d._gauge_process['stdin'].fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL, 0)
        fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

    def info(self, msg='', new_line=True):
        """Print msg as normal output"""
        self.msg = msg
        self.percent = 0
        self.d.gauge_update(self.percent, self.msg, update_text=True)
        time.sleep(0.4)

    def result(self, msg=''):
        """Print a result"""
        self.info(msg)

    def success(self, result):
        """Print result after a successful action"""
        self.percent = 100
        self.d.gauge_update(self.percent, "%s %s" % (self.msg, result),
                            update_text=True)
        time.sleep(0.4)

    def warn(self, msg):
        """Print a warning"""
        self.d.gauge_update(self.percent, "%s Warning: %s" % (self.msg, msg),
                            update_text=True)
        time.sleep(0.4)

    def error(self, msg):
        """Print an error"""
        self.d.gauge_update(self.percent, "%s Error: %s" % (self.msg, msg),
                            update_text=True)
        time.sleep(0.4)

    def cleanup(self):
        """Cleanup the GaugeOutput instance"""
        self.d.gauge_stop()

    class _Progress(Output._Progress):
        """Progress class for dialog's gauge widget"""
        template = {
            'default': '%(index)d/%(size)d',
            'percent': '',
            'b': "%(index)d/%(size)d B",
            'kb': "%(index)d/%(size)d KB",
            'mb': "%(index)d/%(size)d MB"
        }

        def __init__(self, size, title, bar_type='default'):
            """Initialize a _Progress instance"""
            self.parent.size = size
            self.bar_type = bar_type
            self.parent.msg = "%s ..." % title
            self.goto(0)

        def goto(self, dest):
            """Move progress bar to a specific position"""
            self.parent.index = dest
            self.parent.percent = self.parent.index * 100 // self.parent.size

            postfix = self.template[self.bar_type] % self.parent.__dict__
            msg = "%s %s" % (self.parent.msg, postfix)
            self.parent.d.gauge_update(self.parent.percent, msg,
                                       update_text=True)

        def next(self):
            """Move progress bar one step forward"""
            self.goto(self.parent.index + 1)


class InfoBoxOutput(Output):
    """Output class implemented using dialog's infobox widget"""
    def __init__(self, dialog, title, msg='', height=20, width=70):
        self.d = dialog
        self.title = title
        self.msg = msg
        self.width = width
        self.height = height
        self.d.infobox(self.msg, title=self.title)

    def info(self, msg='', new_line=True):
        """Print msg as normal output"""
        nl = '\n' if new_line else ''
        self.msg += "%s%s" % (msg, nl)
        # If output is long, only output the last lines that fit in the box
        lines = self.msg.splitlines()
        # The height of the active region is 2 lines shorter that the height of
        # the dialog
        h = self.height - 2
        display = self.msg if len(lines) <= h else "\n".join(lines[-h:])
        self.d.infobox(display, title=self.title, height=self.height,
                       width=self.width)

    def result(self, msg=''):
        """Print a result"""
        self.info(msg)

    def success(self, result):
        """Print result after an action is completed successfully"""
        self.info(result)

    def warn(self, msg):
        """Print a warning message"""
        self.info("Warning: %s" % msg)

    def error(self, msg):
        """Print an error message"""
        self.info("Error: %s" % msg)

    def finalize(self):
        """Finalize the output. After this is called, the InfoboxOutput
        instance should be destroyed
        """
        self.d.msgbox(self.msg, title=self.title, height=(self.height + 2),
                      width=self.width)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
