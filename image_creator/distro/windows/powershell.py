# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2018 GRNET S.A.
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

"""This module hosts Windows PowerShell scripts that need to be injected into
the windows image."""

# Just a random 16 character long token
from image_creator.distro.windows.vm import RANDOM_TOKEN

COM1_WRITE = r"""
$port=new-Object System.IO.Ports.SerialPort COM1,9600,None,8,one
$port.open()
$port.WriteLine('""" + RANDOM_TOKEN + """')
$port.Close()

"""

# Installs drivers found in a directory
DRVINST_HEAD = r"""
#requires -version 2

Param([string]$dirName=$(throw "You need to provide a directory name"))

if (!(Test-Path -PathType Container "$dirName")) {
    Write-Error -Category InvalidArgument "Invalid Directory: $dirName"
    Exit
}

""" + COM1_WRITE + r"""

function Cat2Cert
{
    $catFile = Get-Item $args[0]
    $cert = (Get-AuthenticodeSignature $catFile.FullName).SignerCertificate
    $certFile = "$dirName" + "\" + $catFile.BaseName + ".cer"
    [System.IO.File]::WriteAllBytes($certFile, $cert.Export("Cert"))
    return $certFile
}

# This is not needed on VMs
powercfg.exe /hibernate off
"""

ADD_CERTIFICATE = r"""
CertUtil -addstore TrustedPublisher "$(Cat2Cert "$dirName\%s")"
"""

ADD_DRIVER = r"""
PnPUtil -a "$dirName\%s"
"""

INSTALL_DRIVER = r"""
PnPUtil -i -a "$dirName\%s"
"""

REMOVE_DRIVER = r"""
PnPUtil -f -d %s
"""

DRVINST_TAIL = COM1_WRITE + """
shutdown /s /t 0
"""

DISABLE_AUTOLOGON = r"""
Remove-ItemProperty -Path `
    'HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon\' `
    DefaultUserName
Remove-ItemProperty -Path `
    'HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon\' `
    DefaultPassword
Remove-ItemProperty -Path `
    'HKLM:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon\' `
    AutoAdminLogon
"""

# Reboots system in safe mode
SAFEBOOT = r"""
bcdedit /set safeboot minimal

$winlogon = 'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
New-ItemProperty `
    -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce `
    -Name *1snf-image-creator-safeboot -PropertyType String `
    -Value 'bcdedit /deletevalue safeboot'

New-ItemProperty `
    -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce `
    -Name *2snf-image-creator-safeboot -PropertyType String `
    -Value "reg delete `"$winlogon`" /v DefaultUserName /f"
New-ItemProperty `
    -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce `
    -Name *3snf-image-creator-safeboot -PropertyType String `
    -Value "reg delete `"$winlogon`" /v DefaultPassword /f"
New-ItemProperty `
    -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce `
    -Name *4snf-image-creator-safeboot -PropertyType String `
    -Value "reg delete `"$winlogon`" /v AutoAdminLogon /f"

New-ItemProperty `
    -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce `
    -Name *5snf-image-creator-safeboot -PropertyType String `
    -Value 'shutdown /s /t 5'
"""

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
