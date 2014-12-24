Usage
^^^^^

snf-image-creator comes in 2 variants:

 * snf-mkimage: A non-interactive command line program
 * snf-image-creator: A user-friendly dialog-based program

Both expect the input media as first argument. The input media may be a local
file, a block device or *"/"* if you want to create an image out of the running
system (see `host bundling operation`_).

Non-interactive version
=======================

snf-mkimage receives the following options:

.. code-block:: console

  # snf-mkimage --help
  Usage: snf-mkimage [options] <input_media>

  Options:
    --version             show program's version number and exit
    -h, --help            show this help message and exit
    -a URL, --authentication-url=URL
                          use this authentication URL when uploading/registering
                          images
    --allow-unsupported   proceed with the image creation even if the media is
                          not supported
    -c CLOUD, --cloud=CLOUD
                          use this saved cloud account to authenticate against a
                          cloud when uploading/registering images
    --disable-sysprep=SYSPREP
                          prevent SYSPREP operation from running on the input
                          media
    --enable-sysprep=SYSPREP
                          run SYSPREP operation on the input media
    -f, --force           overwrite output files if they exist
    --host-run=SCRIPT     mount the media in the host and run a script against
                          the guest media. This option may be defined multiple
                          times. The script's working directory will be the
                          guest's root directory. BE CAREFUL! DO NOT USE
                          ABSOLUTE PATHS INSIDE THE SCRIPT! YOU MAY HARM YOUR
                          SYSTEM!
    --install-virtio=DIR  install VirtIO drivers hosted under DIR (Windows only)
    -m KEY=VALUE, --metadata=KEY=VALUE
                          add custom KEY=VALUE metadata to the image
    --no-snapshot         don't snapshot the input media. (THIS IS DANGEROUS AS
                          IT WILL ALTER THE ORIGINAL MEDIA!!!)
    --no-sysprep          don't perform any system preparation operation
    -o FILE, --outfile=FILE
                          dump image to FILE
    --print-metadata      print the detected image metadata
    --print-syspreps      print the enabled and disabled system preparation
                          operations for this input media
    --print-sysprep-params
                          print the defined system preparation parameters for
                          this input media
    --public              register image with the cloud as public
    -r IMAGENAME, --register=IMAGENAME
                          register the image with a cloud as IMAGENAME
    -s, --silent          output only errors
    --sysprep-param=SYSPREP_PARAMS
                          add KEY=VALUE system preparation parameter
    -t TOKEN, --token=TOKEN
                          use this authentication token when
                          uploading/registering images
    --tmpdir=DIR          create large temporary image files under DIR
    -u FILENAME, --upload=FILENAME
                        upload the image to the cloud with name FILENAME

Most input options are self-describing. If you want to save a local copy of
the image you create, provide a filename using the *-o* option. To upload the
image to the storage service of a cloud, provide valid cloud API access info
(by either using a token and a URL with *-t* and *-a* respectively, or a cloud
name with *-c*) and a remote filename using *-u*. If you also want to register
the image with the compute service of the cloud, in addition to *-u* provide a
registration name using *-r*. All images are registered as *private*. Only the
user that registers the image can create VM's out of it. If you want the image
to be visible by other user too, use the *--public* option.

By default, before extracting the image, snf-mkimage will perform a number of
system preparation operations on the snapshot of the media. You can disable
this by specifying *--no-sysprep*.

You may use the *--host-run* option multiple times to define scripts that will
run on the image's locally mounted root directory before the image
customization is performed. Be careful when using those. The scripts run on the
host system without any jail protection. Use only relative paths.

If *--print-sysprep* is defined, the program will exit after printing a
list of enabled and disabled system preparation operations applicable to this
input media. The user can enable or disable specific *syspreps*, using
*-{enable,disable}-sysprep* options. The user may specify those options
multiple times.

Running *snf-mkimage* with *--print-sysprep* on a raw file that hosts an
Ubuntu system, will print the following output:

.. _sysprep:

.. code-block:: console

  # snf-mkimage --print-syspreps ubuntu.raw

  snf-image-creator 0.7
  ===========================
  Examining source media `ubuntu.raw' ... looks like an image file
  Snapshotting media source ... done
  Enabling recovery proc
  Launching helper VM (may take a while) ... done
  Inspecting Operating System ... ubuntu
  Collecting image metadata ... done

  Running OS inspection:
  Checking if the media contains logical volumes (LVM)... no

  Enabled system preparation operations:
      cleanup-tmp:
          Remove all files under /tmp and /var/tmp

      remove-swap-entry:
          Remove swap entry from /etc/fstab. If swap is the last partition
          then the partition will be removed when shrinking is performed. If the
          swap partition is not the last partition in the disk or if you are not
          going to shrink the image you should probably disable this.

      cleanup-cache:
          Remove all regular files under /var/cache

      cleanup-userdata:
          Delete sensitive user data

      cleanup-passwords:
          Remove all passwords and lock all user accounts

      cleanup-log:
          Empty all files under /var/log

      remove-persistent-net-rules:
          Remove udev rules that will keep network interface names persistent
          after hardware changes and reboots. Those rules will be created again
          the next time the image runs.

      use-persistent-block-device-names:
          Scan fstab & grub configuration files and replace all non-persistent
          device references with UUIDs.

      fix-acpid:
          Replace acpid powerdown action scripts to immediately shutdown the
          system without checking if a GUI is running.

      shrink:
          Shrink the last file system and update the partition table

  Disabled system preparation operations:
      remove-user-accounts:
          Remove all user accounts with id greater than 1000

      cleanup-mail:
          Remove all files under /var/mail and /var/spool/mail


  cleaning up ...

If you want the image to have all normal user accounts and all mail files
removed, you should use *--enable-sysprep* option like this:

.. code-block:: console

   $ snf-mkimage --enable-sysprep cleanup-mail --enable-sysprep remove-user-accounts ...

Sysprep parameters are parameters used by some sysprep tasks. In most cases you
don't need to change their value. You can see the available sysprep parameters
and the default values they have by using the *--print-sysprep-params* option.
You can update their values by using the *--sysprep-param* option.

If the media is a Windows image, you can install or update its VirtIO drivers
by using the *--install-virtio* option. With this option you can point to a
directory that hosts a set of extracted Windows VirtIO drivers.

Dialog-based version
====================

*snf-image-creator* receives the following options:

.. code-block:: console

 # snf-image-creator --help
 Usage: snf-image-creator [options] [<input_media>]

 Options:
   --version             show program's version number and exit
   -h, --help            show this help message and exit
   -l FILE, --logfile=FILE
                         log all messages to FILE
   --tmpdir=DIR          create large temporary image files under DIR

If the input media is not specified in the command line, in the first dialog
box the user will be asked to specify it:

.. image:: /snapshots/select_media.png

The user can select a file (regular or block device) or use the *Bundle Host*
button to create an image out of the running system (see
`Host bundling operation`_).

After the input media is examined and the program is initialized, the user will
be given the choice to run *snf-image-creator* in *wizard* or *expert* mode.

Wizard mode
-----------

When *snf-image-creator* runs in *wizard* mode, the user is just asked to
provide the following basic information:

 * Cloud: The cloud account to use to upload and register the resulting image
 * Name: A short name for the image (ex. "Slackware")
 * Description: An one-line description for the image
   (ex. "Slackware Linux 14.0 with KDE")
 * VirtIO: A directory that hosts VirtIO drivers (for Windows images only)
 * Registration Type: Private or Public

After confirming, the image will be extracted, uploaded to the storage service
and registered with the compute service of the selected cloud. The user will
also be given the choice to keep a local copy of it.

For most users the functionality this mode provides should be sufficient.

Expert mode
-----------

Expert mode allows the user to have better control on the image creation
process. The main menu can be seen in the picture below:

.. image:: /snapshots/main_menu.png

In the *Customize* sub-menu the user can control:

 * The installation of VirtIO drivers (only for Windows images)
 * The system preparation operations that will be applied on the media
 * The properties associated with the image
 * The configuration tasks that will run during image deployment

In the *Register* sub-menu the user can provide:

 * Which cloud account to use
 * A filename for the uploaded *diskdump* image
 * A name for the image to use when registering it with the storage service of
   the cloud, as well as the registration type (*private* or *public*)

By choosing the *Extract* menu entry, the user can dump the image to the local
file system. Finally, if the user selects *Reset*, the system will ignore
all changes made so far and will start the image creation process again.

Host bundling operation
=======================

As a new feature in *v0.2*, snf-image-creator can create images out of the host
system that runs the program. This is done either by specifying */* as input
media or by using the *Bundle Host* button in the media selection dialog.
During this operation, the files of the disk are copied into a temporary image
file, which means that the file system that will host the temporary image needs
to have a lot of free space (see `large temporary files`_ for more
information).

Creating a new image
====================

Suppose your host system is a Debian Wheezy and you want to create a new Ubuntu
server image. Download the installation disk from the Internet:

.. code-block:: console

   $ wget http://ubuntureleases.tsl.gr/12.04.2/ubuntu-12.04.2-server-amd64.iso

Verify that it has been downloaded correctly:

.. code-block:: console

   $ echo 'a8c667e871f48f3a662f3fbf1c3ddb17  ubuntu-12.04.2-server-amd64.iso' > check.md5
   $ md5sum -c check.md5

Create a 2G sparse file to host the new system:

.. code-block:: console

   $ truncate -s 2G ubuntu.raw

And install the Ubuntu system on this file:

.. code-block:: console

   $ sudo kvm -boot d -drive file=ubuntu.raw,format=raw,cache=none,if=virtio \
     -m 1G -cdrom ubuntu-12.04.2-server-amd64.iso

.. warning::

   During the installation, you will be asked about the partition scheme. Don't 
   use LVM partitions. They are not supported by snf-image-creator.

You will be able to boot your installed OS and make any changes you want
(e.g. install OpenSSH Server) using the following command:

.. code-block:: console

   $ sudo kvm -m 1G -boot c -drive file=ubuntu.raw,format=raw,cache=none,if=virtio

After you're done, you may use *snf-image-creator* as root to create and upload
the image:

.. code-block:: console

   $ sudo -s
   # snf-image-creator ubuntu.raw

In the first screen you will be asked to choose if you want to run the program
in *Wizard* or *Expert* mode. Choose *Wizard*.

.. image:: /snapshots/wizard.png

Then you will be asked to select a cloud and provide a name, a description and
a registration type (*private* or *public*). Finally, you'll be asked to
confirm the provided data.

.. image:: /snapshots/confirm.png

Choosing *YES* will create and upload the image to your cloud account.

Working with different image formats
====================================

*snf-image-creator* is able to work with the most popular disk image formats.
It has been successfully tested with:

* Raw disk images
* VMDK (VMware)
* VHD (Microsoft Hyper-V)
* VDI (VirtualBox)
* qcow2 (QEMU)

It can support any image format QEMU supports as long as it represents a
bootable hard drive.

Limitations
===========

Supported operating systems
---------------------------

*snf-image-creator* can fully function on input media hosting *Linux*,
*FreeBSD*, *OpenBSD*, *NetBSD* and *Windows* (Server starting from 2008R2 and
Desktop starting from 7) systems.

Logical Volumes
---------------

The program cannot work on input media that contain LVM partitions inside
[#f2]_. The input media may only contain primary or logical partitions.

Para-virtualized drivers
------------------------

Most Synnefo deployments uses the *VirtIO* framework. The disk I/O controller
and the Ethernet cards on the VM instances are para-virtualized and need
special *VirtIO* drivers. Those drivers are included in the Linux Kernel
mainline since version 2.6.25 and are shipped with all the popular Linux
distributions. The problem is that if the driver for the para-virtualized disk
I/O controller is built as module, it needs to be preloaded using an initial
ramdisk, otherwise the VM won't be able to boot.

Many popular Linux distributions, like Ubuntu and Debian, will automatically
create a generic initial ramdisk file that contains many different modules,
including the VirtIO drivers. Others that target more experienced users, like
Slackware, won't do that [#f3]_. *snf-image-creator* cannot resolve this kind
of problems and it's left to the user to do so. Please refer to your
distribution's documentation for more information on this. You can always check
if a system can boot with para-virtualized disk controller by launching it with
kvm using the *if=virtio* option (see the kvm command in the
`Creating a new image`_ section).

For Windows the program supports installing VirtIO drivers. You may download
the latest drivers from the
`Fedora Project <http://alt.fedoraproject.org/pub/alt/virtio-win/latest/images/>`_.

Some caveats on image creation
==============================

Image partition schemes and shrinking
-------------------------------------

When image shrinking is enabled, *snf-image-creator* will shrink the last
partition on the disk. If this is a swap partition, it will remove it, save
enough information to recreate it during image deployment and shrink the
partition that lays just before that. This will make the image smaller which
speeds up the deployment process.

During image deployment, the last partition is enlarged to occupy the available
space in the VM's hard disk and a swap partition is added at the end if a SWAP
image property is present.

Keep this in mind when creating images. It's always better to have your swap
partition placed as the last partition on the disk and have your largest
partition (*/* or */home*) just before that.

Large temporary files
---------------------

*snf-image-creator* may create large temporary files when running:

 * During image shrinking, the input media snapshot file may reach the size of
   the original media.
 * When bundling the host system, the temporary image file may became 10%
   larger than rest of the disk files altogether.

*/tmp* directory is not a good place for hosting large files. In many systems
the contents of */tmp* are stored in volatile memory and the size they may
occupy is limited. By default, *snf-image-creator* will use a heuristic
approach to determine where to store large temporary files. It will examine the
free space under */var/tmp*, the user's home directory and */mnt* and will pick
the one with the most available space. The user may overwrite this behavior and
indicate a different directory using the *tmpdir* option. This option is
supported by both *snf-image-creator* and *snf-mkimage*.

Troubleshooting
===============

Failures in launching libguestfs's helper VM
--------------------------------------------

The most common error you may get when using *snf-image-creator* is a failure
when launching *libguestfs*'s helper VM. *libguestfs* [#f4]_ is a library
for manipulating disk images and *snf-image-creator* makes heavy use of it.
Most of the time those errors have to do with the installation of this
library and not with *snf-image-creator* itself.

The first thing you should do when troubleshooting this is to run the
``liguestfs-test-tool`` diagnostic tool. This tool gets shipped with the
library to test if *libguestfs* works as expected. If it runs to completion
successfully, you will see this near the end:

.. code-block:: console

    ===== TEST FINISHED OK =====

and the test tool will exit with code 0.

If you get errors like this:

.. code-block:: console

   libguestfs: launch: backend=libvirt
   libguestfs: launch: tmpdir=/tmp/libguestfseKwXgq
   libguestfs: launch: umask=0022
   libguestfs: launch: euid=0
   libguestfs: libvirt version = 1001001 (1.1.1)
   libguestfs: [00012ms] connect to libvirt
   libguestfs: opening libvirt handle: URI = NULL, auth = virConnectAuthPtrDefault, flags = 0
   libvirt: XML-RPC error : Failed to connect socket to '/var/run/libvirt/libvirt-sock': No such file or directory
   libguestfs: error: could not connect to libvirt (URI = NULL): Failed to connect socket to '/var/run/libvirt/libvirt-sock': No such file or directory [code=38 domain=7]
   libguestfs-test-tool: failed to launch appliance
   libguestfs: closing guestfs handle 0x7ff0d44f8bb0 (state 0)
   libguestfs: command: run: rm
   libguestfs: command: run: \ -rf /tmp/libguestfseKwXgq

it means that *libguestfs* is configured to use *libvirt* backend by default
but the libvirt deamon is not running. You can either start libvirt deamon
(providing instructions on how to do this is out of the scope of this
tutorial) or change the default backend to *direct* by defining the
**LIBGUESTFS_BACKEND** variable like this:

.. code-block:: console

   # export LIBGUESTFS_BACKEND=direct

If you run the ``libguestfs-test-tool``, the command should finish without
errors. Do the same every time before running *snf-image-creator*.

If you get errors on *febootstrap-supermin-helper* like this one:

.. code-block:: console

   febootstrap-supermin-helper: ext2: parent directory not found: /lib:
   File not found by ext2_lookup
   libguestfs: error: external command failed, see earlier error messages
   libguestfs-test-tool: failed to launch appliance
   libguestfs: closing guestfs handle 0x7b3160 (state 0)

you probably need to update the supermin appliance (just once). On Debian
and Ubuntu systems you can do it using the command below:

.. code-block:: console

   # update-guestfs-appliance

.. rubric:: Footnotes

.. [#f1] http://technet.microsoft.com/en-us/library/bb676673.aspx
.. [#f2] http://sourceware.org/lvm2/
.. [#f3] http://mirrors.slackware.com/slackware/slackware-14.0/README.initrd
.. [#f4] http://libguestfs.org/
