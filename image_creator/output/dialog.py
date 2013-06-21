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

        # Open pipe workaround. A fork will dublicate the open file descriptor.
        # The FD_CLOEXEC flag makes sure that the gauge internal fd will be
        # closed if execve is executed. This is needed because libguestfs will
        # fork/exec the kvm process. If this fd stays open in the kvm process,
        # then doing a gauge_stop will make this process wait forever for
        # a dialog process that is blocked waiting for input from the kvm
        # process's open file descriptor.
        fd = self.d._gauge_process['stdin'].fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL, 0)
        fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

    def output(self, msg='', new_line=True):
        """Print msg as normal output"""
        self.msg = msg
        self.percent = 0
        self.d.gauge_update(self.percent, self.msg, update_text=True)
        time.sleep(0.4)

    def success(self, result, new_line=True):
        """Print result after a successfull action"""
        self.percent = 100
        self.d.gauge_update(self.percent, "%s %s" % (self.msg, result),
                            update_text=True)
        time.sleep(0.4)

    def warn(self, msg, new_line=True):
        """Print a warning"""
        self.d.gauge_update(self.percent, "%s Warning: %s" % (self.msg, msg),
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
            self.output.size = size
            self.bar_type = bar_type
            self.output.msg = "%s ..." % title
            self.goto(0)

        def _postfix(self):
            return self.template[self.bar_type] % self.output.__dict__

        def goto(self, dest):
            """Move progress bar to a specific position"""
            self.output.index = dest
            self.output.percent = self.output.index * 100 // self.output.size
            msg = "%s %s" % (self.output.msg, self._postfix())
            self.output.d.gauge_update(self.output.percent, msg,
                                       update_text=True)

        def next(self):
            """Move progress bar one step forward"""
            self.goto(self.output.index + 1)


class InfoBoxOutput(Output):
    """Output class implemented using dialog's infobox widget"""
    def __init__(self, dialog, title, msg='', height=20, width=70):
        self.d = dialog
        self.title = title
        self.msg = msg
        self.width = width
        self.height = height
        self.d.infobox(self.msg, title=self.title)

    def output(self, msg='', new_line=True):
        """Print msg as normal output"""
        nl = '\n' if new_line else ''
        self.msg += "%s%s" % (msg, nl)
        # If output is long, only output the last lines that fit in the box
        lines = self.msg.splitlines()
        h = self.height
        display = self.msg if len(lines) <= h else "\n".join(lines[-h:])
        self.d.infobox(display, title=self.title, height=self.height,
                       width=self.width)

    def success(self, result, new_line=True):
        """Print result after an action is completed successfully"""
        self.output(result, new_line)

    def warn(self, msg, new_line=True):
        """Print a warning message"""
        self.output("Warning: %s" % msg, new_line)

    def finalize(self):
        """Finalize the output. After this is called, the InfoboxOutput
        instance should be destroyed
        """
        self.d.msgbox(self.msg, title=self.title, height=(self.height + 2),
                      width=self.width)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
