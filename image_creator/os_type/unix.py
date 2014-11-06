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

"""This module hosts OS-specific code common to all Unix-like OSs."""

from image_creator.os_type import OSBase, sysprep

# Credits go to Wmconfig (https://www.arrishq.net/) for the biggest part of
# this collection
DESKTOPSESSIONS = {
    # Put the most popular GUIs first
    ('startkde',): 'KDE',
    ('gnome-session', 'gnomesession'): 'GNOME',
    ('unity',): 'Unity',
    ('xfce4-session', 'startxfce4', 'xfwm4'): 'Xfce',
    ('startlxde', 'lxsession'): 'LXDE',
    ('mate-session',): 'MATE',
    ('cinnamon', 'gnome-session-cinnamon', 'cinnamon-session'): 'Cinnamon',
    ('enlightenment',): 'Enlightenment',

    ('aewm',): 'aewm',
    ('afterstep',): 'AfterStep',
    ('amiwm',): 'amiwm',
    ('awesome',): 'awesome',
    ('blackbox',): 'Blackbox',
    ('ctwm',): 'CTWM',
    ('dwm',): 'dwm',
    ('epiwm',): 'EPIwm',
    ('fluxbox', 'startfluxbox'): 'Fluxbox',
    ('flwm',): 'flvm',
    ('fvwm',): 'FVWM',
    ('fvwm2',): 'FVWM',
    ('fvwm95',): 'FVWM95',
    ('golem',): 'Golem',
    ('i3',): 'i3',
    ('icewm', 'icewm-session'): 'IceVM',
    ('ion', 'ion2', 'ion3'): 'Ion',
    ('jwm',): "JWM",
    ('kahakai',): 'Kahakai',
    ('larswm',): 'larswm',
    ('mlvwm',): 'MLVWM',
    ('mwm',): 'Motif Window Manager',
    ('olvwm',): 'OLVWM',
    ('olwm',): 'OLWM',
    ('openbox', 'openbox-session'): 'Openbox',
    ('particleman', ): 'ParticleMan',
    ('pekwm',): 'PeKWM',
    ('pwm', 'pwm2', 'pwm3'): 'PWM',
    ('qvwm',): 'qvwm',
    ('rasor-session',): 'Razor-qt',
    ('ratpoison',): 'Ratpoison',
    ('sapphire',): 'Sapphire',
    ('sawfish',): 'Sawfish',
    ('sithwm',): 'SithWM',
    ('startede',): 'EDE',
    ('startstump',): 'StumpWM',
    ('starttrinity',): 'TDE',
    ('twm',): 'twm',
    ('uwm',): 'UDE',
    ('w9wm',): 'w9wm',
    ('wmaker',): 'WindowMaker',
    ('wmx',): 'wmx',
    ('wmi', 'wmii'): 'wmii',
    ('windowlab',): 'WindowLab',
    ('xmonad',): 'xmonad',
}

X11_EXECUTABLE = 'startx'


class Unix(OSBase):
    """OS class for Unix"""
    sensitive_userdata = [
        '.history',
        '.sh_history',
        '.bash_history',
        '.zsh_history',
        '.gnupg',
        '.ssh',
        '.kamakirc',
        '.kamaki.history',
        '.kamaki.log'
    ]

    def _mountpoints(self):
        """Return mountpoints in the correct order.
        / should be mounted before /boot or /usr, /usr befor /usr/bin ...
        """
        mps = self.image.g.inspect_get_mountpoints(self.root)

        def compare(a, b):
            if len(a[0]) > len(b[0]):
                return 1
            elif len(a[0]) == len(b[0]):
                return 0
            else:
                return -1
        mps.sort(compare)

        for mp in mps:
            yield mp

    def _do_mount(self, readonly):
        """Mount partitions in the correct order"""

        critical_mpoints = ('/', '/etc', '/root', '/home', '/var')

        mopts = 'ro' if readonly else 'rw'
        for mp, dev in self._mountpoints():
            try:
                self.image.g.mount_options(mopts, dev, mp)
            except RuntimeError as msg:
                if mp in critical_mpoints:
                    self._mount_error = str(msg)
                    return False
                else:
                    self._mount_warnings.append('%s (ignored)' % msg)

        return True

    def _do_collect_metadata(self):
        super(Unix, self)._do_collect_metadata()

        bin_prefixes = ('', '/usr', '/usr/local')
        gui = False

        paths = ['%s/bin/%s' % (p, X11_EXECUTABLE) for p in bin_prefixes]
        for path in paths:
            if self.image.g.is_file(path):
                gui = True
                break

        if not gui:
            self.meta['GUI'] = "No GUI"
        else:
            self.meta['GUI'] = 'Unknown'

        desktop = []
        for exe, session in DESKTOPSESSIONS.items():
            paths = ["%s/bin/%s" % (p, e) for p in bin_prefixes for e in exe]
            for path in paths:
                if self.image.g.is_file(path):
                    desktop.append(session)
                    break
        if gui and len(desktop) != 0:
            self.meta['GUI'] = " | ".join(desktop)

    def ssh_connection_options(self, users):
        """Returns a list of valid ssh connection options"""

        def sshd_config():
            """Read /etc/ssh/sshd_config and return it as a dictionary"""
            config = {}
            fname = '/etc/ssh/sshd_config'

            if not self.image.g.is_file(fname):
                return {}

            for line in self.image.g.cat(fname).splitlines():
                line = line.split('#')[0].strip()
                if not len(line):
                    continue
                line = line.split()
                config[line[0]] = line[1:]
            return config

        config = sshd_config()
        try:
            port = int(config['Port'][0])
        except:
            port = 22

        if 'PermitRootLogin' in config and config['PermitRootLogin'] == 'no':
            if 'root' in users:
                users.remove('root')

        return {'port': port, 'users': users}

    @sysprep('Removing files under /var/cache')
    def _cleanup_cache(self):
        """Remove all regular files under /var/cache"""

        self._foreach_file('/var/cache', self.image.g.rm, ftype='r')

    @sysprep('Removing files under /tmp and /var/tmp')
    def _cleanup_tmp(self):
        """Remove all files under /tmp and /var/tmp"""

        self._foreach_file('/tmp', self.image.g.rm_rf, maxdepth=1)
        self._foreach_file('/var/tmp', self.image.g.rm_rf, maxdepth=1)

    @sysprep('Emptying all files under /var/log')
    def _cleanup_log(self):
        """Empty all files under /var/log"""

        self._foreach_file('/var/log', self.image.g.truncate, ftype='r')

    @sysprep('Removing files under /var/mail & /var/spool/mail', enabled=False)
    def _cleanup_mail(self):
        """Remove all files under /var/mail and /var/spool/mail"""

        self._foreach_file('/var/spool/mail', self.image.g.rm_rf, maxdepth=1)

        self._foreach_file('/var/mail', self.image.g.rm_rf, maxdepth=1)

    @sysprep('Removing sensitive user data')
    def _cleanup_userdata(self):
        """Delete sensitive user data"""

        homedirs = ['/root']
        if self.image.g.is_dir('/home/'):
            homedirs += self._ls('/home/')

        action = self.image.g.rm_rf
        if self._scrub_support:
            action = self.image.g.scrub_file
        else:
            self.out.warn("Sensitive data won't be scrubbed (not supported)")

        for homedir in homedirs:
            for data in self.sensitive_userdata:
                fname = "%s/%s" % (homedir, data)
                if self.image.g.is_file(fname):
                    action(fname)
                elif self.image.g.is_dir(fname):
                    self._foreach_file(fname, action, ftype='r')

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
