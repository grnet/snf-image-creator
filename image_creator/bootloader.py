# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GRNET S.A.
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

"""Module hosting code for determining the installed boot loader on an image.
The bootloader signatures are taken from the "Boot Info Script" project:
    https://github.com/arvidjaar/bootinfoscript
"""

# Master Boot Record Bootloaders
MBR_LDR = [
    # GRUB Legacy
    "grub1",            # 0
    # GRUB 2
    "grub2",
    # LILO (LInux LOader)
    "lilo",
    # SYSLINUX
    "syslinux",
    # Windows
    "Windows",
    # FreeBSD's boot0
    "freebsd",          # 5
    # NetBSD's Stage 0/SUSE generic MBR
    "netbsd",
    # OpenBSD's MBR
    "openbsd",
    # ReactOS
    "reactos",
    # FreeDOS
    "freedos",
    # MS-DOS
    "msdos",            # 10
    # Solaris
    "solaris",
    # ThinkPad MBR
    "thinkpad",
    # HP/Gateway
    "hp",
    # Plop Boot Manager
    "plop",
    # TrueCrypt boot loader
    "truecrypt",        # 15
    # Paragon Partition Manager
    "paragon",
    # Testdisk MBR
    "testdist",
    # GAG Graphical Boot Manager
    "gag",
    # BootIt Boot Manager
    "bootit",
    # DiskCryptor
    "diskcryptor",  # 20
    # xOSL (Extended Operating System Loader)
    "xosl",
    # Fbinst
    "fbinst",
    # Grub4Dos
    "grub4dos",
    # WEE boot manager
    "wee",
    # mbldr (Master Boot LoaDeR)
    "mbldr",   # 25
    # Libparted generic boot code
    "libparted",
    # ISOhybrid
    "isohybrid",
    # Acer PQservice MBR
    "pqservice",
]

# 2-bytes MBR signature
MBR_SIG2 = {
    "\x3b\x48": 0,
    "\xeb\x4c": 1,
    "\xeb\x63": 1,
    "\xeb\x04": 11,
    "\x0e\xbe": 12,
    "\x33\xed": 27,
    "\x33\xff": 13,
    "\xb8\x00": 14,
    "\xea\x1e": 15,
    "\xeb\x04":        11,
    "\xeb\x31": 16,
    "\xfa\x33": 10,
    "\xfa\xeb": 2,
    "\xfa\xfc": 8,
    "\xfc\x31": 17,
    "\xfc\x33": 18,
    "\xfc\xeb": 19,
}

# 3-bytes MBR signature
MBR_SIG3 = {
    "\x33\xc0\x8e": 4,
    "\x33\xc0\x90": 20,
    "\x33\xc0\xfa": 3,
    "\xea\x05\x00": 7,
    "\xea\x05\x01": 21,
    "\xeb\x5e\x00": 22,
    "\xeb\x5e\x80": 23,
    "\xeb\x5e\x90": 24,
    "\xfa\x31\xc0": 3,
    "\xfa\x31\xc9": 25,
    "\xfa\x31\xed": 27,
}

# 4-bytes MBR signature
MBR_SIG4 = {
    "\xfa\xb8\x00\x00": 9,
    "\xfa\xb8\x00\x10": 26,
}

# 8-bytes MBR signature
MBR_SIG8 = {
    "\x31\xc0\x8e\xd0\xbc\x00\x7c\x8e": 6,
    "\x31\xc0\x8e\xd0\xbc\x00\x7c\xfb": 28,
}


def mbr_bootinfo(mbr):
    """Inspect a Master Boot Record and return the installed bootloader"""
    if mbr[:2] == '\x00\x00':
        return "none"

    try:
        ret = MBR_SIG2[mbr[:2]]
    except KeyError:
        try:
            ret = MBR_SIG3[mbr[:3]]
        except KeyError:
            try:
                ret = MBR_SIG4[mbr[:4]]
            except KeyError:
                try:
                    ret = MBR_SIG8[mbr[:8]]
                except KeyError:
                    return "unknown"

    return MBR_LDR[ret]

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
