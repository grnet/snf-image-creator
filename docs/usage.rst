Usage
^^^^^

snf-image-creator comes in 2 variants:

 * snf-image-creator: A non-interactive command line program
 * snf-mkimage: A user-friendly dialog-based program

Both expect the input media as first argument. The input media may be a local
file, a block device or *"/"* if you want to create an image out of the running
system (see `host bundling operation`_).

Non-interactive version
=======================

snf-image-creator receives the following options:

.. code-block:: console

 $ snf-image-creator --help
 Usage: snf-image-creator [options] <input_media>

 Options:
   --version             show program's version number and exit
   -h, --help            show this help message and exit
   -o FILE, --outfile=FILE
                         dump image to FILE
   -f, --force           overwrite output files if they exist
   -s, --silent          output only errors
   -u FILENAME, --upload=FILENAME
                         upload the image to pithos with name FILENAME
   -r IMAGENAME, --register=IMAGENAME
                         register the image with ~okeanos as IMAGENAME
   -a ACCOUNT, --account=ACCOUNT
                         use this ACCOUNT when uploading/registering images
                         [Default: None]
   -m KEY=VALUE, --metadata=KEY=VALUE
                         add custom KEY=VALUE metadata to the image
   -t TOKEN, --token=TOKEN
                         use this token when uploading/registering images
                         [Default: None]
   --print-sysprep       print the available enabled and disabled system
                         preparation operations for this input media
   --enable-sysprep=SYSPREP
                         run SYSPREP operation on the input media
   --disable-sysprep=SYSPREP
                         prevent SYSPREP operation from running on the input
                         media
   --no-sysprep          don't perform any system preparation operation
   --no-shrink           don't shrink the image
   --tmpdir=DIR          create large temporary image files under DIR

Most input options are self-describing. If you want to save a local copy of
the image you create, provide a filename using the *-o* option. To upload the
image to *pithos+*, provide valid credentials using *-a* and *-t* and a
filename using *-u*. If you also want to register the image with *~okeanos*, in
addition to *-u* provide a registration name using *-r*.

By default, before extracting the image, snf-image-creator will perform a
number of system preparation operations on the snapshot of the media and will
shrink the last partition found. Both actions can be disabled by specifying
*--no-sysprep* and *--no-shrink* respectively.

If *--print-sysprep* is defined, the program will exit after printing a
list of enabled and disabled system preparation operation applicable to this
input media. The user can enable or disable specific *syspreps*, using
*-{enable,disable}-sysprep* options. The user may specify those options
multiple times.

Running *snf-image-creator* with *--print-sysprep* on a raw file that hosts a
debian system, we print the following output:

.. _sysprep:

.. code-block:: console

   $ snf-image-creator --print-sysprep debian_desktop.img

   snf-image-creator 0.1
   =====================
   Examining source media `debian_desktop.img'... looks like an image file
   Snapshotting media source... done
   Enabling recovery proc
   Launching helper VM... done
   Inspecting Operating System... found a(n) debian system
   Mounting the media read-only... done

   Enabled system preparation operations:
       cleanup-cache:
   	Remove all regular files under /var/cache

       cleanup-log:
   	Empty all files under /var/log

       cleanup-passwords:
   	Remove all passwords and lock all user accounts

       cleanup-tmp:
   	Remove all files under /tmp and /var/tmp

       cleanup-userdata:
   	Delete sensitive userdata

       fix-acpid:
   	Replace acpid powerdown action scripts to immediately shutdown the
   	system without checking if a GUI is running.

       remove-persistent-net-rules:
   	Remove udev rules that will keep network interface names persistent
   	after hardware changes and reboots. Those rules will be created again
   	the next time the image runs.

       remove-swap-entry:
   	Remove swap entry from /etc/fstab. If swap is the last partition
   	then the partition will be removed when shrinking is performed. If the
   	swap partition is not the last partition in the disk or if you are not
   	going to shrink the image you should probably disable this.

       use-persistent-block-device-names:
   	Scan fstab & grub configuration files and replace all non-persistent
   	device references with UUIDs.

   Disabled system preparation operations:
       cleanup-mail:
   	Remove all files under /var/mail and /var/spool/mail

       remove-user-accounts:
   	Remove all user accounts with id greater than 1000


   cleaning up...

If you want the image to have all normal user accounts and all mail files
removed, you should use *--enable-sysprep* option like this:

.. code-block:: console

   $ snf-image-creator --enable-sysprep cleanup-mail --enable-sysprep remove-user-accounts ...

Dialog-based version
====================

*snf-mkimage* receives the following options:

.. code-block:: console

 $ snf-mkimage --help
 Usage: snf-mkimage [options] [<input_media>]

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
be given the choice to run *snf-mkimage* in *wizard* or *expert* mode.

Wizard mode
-----------

When *snf-mkimage* runs in *wizard* mode, the user is just asked to provide the
following basic information:

 * Name: A short name for the image (ex. "Slackware")
 * Description: An one-line description for the image
   (ex. "Slackware Linux 14.0 with KDE")
 * Account: An *~okeanos* account email
 * Token: A token corresponding to the account given above

After confirming, the image will be extracted, uploaded to *pithos+* and
registered with *~okeanos*. The user will also be given the choice to keep a
local copy of it.

For most users the functionality this mode provides should be sufficient.

Expert mode
-----------

Expert mode allows the user to have better control on the image creation
process. The main menu can be seen in the picture below:

.. image:: /snapshots/main_menu.png

In the *Customize* sub-menu the user can control:

 * The system preparation operations that will be applied on the media
 * Whether the image will be shrunk or not
 * The properties associated with the image
 * The configuration tasks that will run during image deployment

In the *Register* sub-menu the user can provide:

 * The credentials to login to *~okeanos*
 * A *pithos+* filename for the uploaded *diskdump* image
 * A name for the image to be registered to *~okeanos* with

By choosing the *Extract* menu entry, the user can dump the image to the local
file system. Finally, if the user selects *Reset*, the system will ignore
all changes made so far and will start the image creation process again.

Host bundling operation
=======================

As a new feature in *v0.2*, snf-image-creator can create images out of the host
system that runs the program. This is done either by specifying / as input
media or by using the *Bundle Host* button in the media selection dialog of
snf-mkimage. During this operation, the files of the disk are copied into a
temporary image file, which means that the file system that will host the
temporary image needs to have a lot of free space (see `large temporary files`_
for more information).

Creating a new image
====================

Suppose you want to create a new Ubuntu server image. Download the installation
disk from the Internet:

.. code-block:: console

   $ wget http://ubuntureleases.tsl.gr/12.04.1/ubuntu-12.04.1-server-amd64.iso

Verify that it has been downloaded correctly:

.. code-block:: console

   $ echo 'a8c667e871f48f3a662f3fbf1c3ddb17  ubuntu-12.04.1-server-amd64.iso' > check.md5
   $ md5sum -c check.md5

Create a 2G sparse file to host the new system:

.. code-block:: console

   $ truncate -s 2G ubuntu_hd.raw

And install the Ubuntu system on this file:

.. code-block:: console

   $ sudo kvm -boot d -drive file=ubuntu_hd.raw,format=raw,cache=none,if=virtio \
     -m 1G -cdrom ubuntu-12.04.1-server-amd64.iso

.. warning::

   During the installation, you will be asked about the partition scheme. Don't 
   use LVM partitions. They are not supported by snf-image-creator.

You will be able to boot your installed OS and make any changes you want
(e.g. install openssh-server) using the following command::

   $ sudo kvm -m 1G -boot c -drive file=ubuntu_hd.raw,format=raw,cache=none,if=virtio

After you're done, you may use *snf-mkimage* as root to create and upload the
image:

.. code-block:: console

   $ sudo -s
   $ snf-mkimage ubuntu_hd.raw

In the first screen you will be asked to choose if you want to run the program
in *Wizard* or *Expert* mode. Choose *Wizard*.

.. image:: /snapshots/01_wizard.png

Then you will be asked to provide a name, a description, an *~okeanos* account
and the token corresponding to this account. Finally, you'll be asked to
confirm the provided data.

.. image:: /snapshots/06_confirm.png

Choosing *YES* will create and upload the image to your *~okeanos* account.

Limitations
===========

Supported operating systems
---------------------------

*snf-image-creator* can only fully function on input media hosting *Linux*
systems. The program will detect the needed metadata and you may use it to
upload and register other *Unix* or *Windows* images, but you cannot use it to
shrink them or perform system preparation operations.

Logical Volumes
---------------

The program cannot work on LVM partitions [#f1]_. The input media may only
contain primary or logical partitions.

Para-virtualized drivers
------------------------

*~Okeanos* uses the *VirtIO* framework. The disk I/O controller and the
Ethernet cards on the VM instances are para-virtualized and need special
*VirtIO* drivers. Those drivers are included in the Linux Kernel mainline since
version 2.6.25 and are shipped with all the popular Linux distributions. The
problem is that if the driver for the para-virtualized disk I/O controller is
built as module, it needs to be preloaded using an initial ramdisk, otherwise
the VM won't be able to boot.

Many popular Linux distributions, like Ubuntu and Debian, will automatically
create a generic initial ramdisk file that contains many different modules,
including the VirtIO drivers. Others that target more experienced users, like
Slackware, won't do that [#f2]_. *snf-image-creator* cannot resolve this kind
of problems and it's left to the user to do so. Please refer to your
distribution's documentation for more information on this. You can always check
if a system can boot with para-virtualized disk controller by launching it with
kvm using the *if=virtio* option (see the kvm command in the
`Creating a new image`_ section).

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
 * When bundling the host system, the temporary image file may became as large
   as the rest of the disk files altogether.

*/tmp* directory is not a good place for hosting large files. In many systems
the contents of */tmp* are stored in volatile memory and the size they may occupy
is limited. By default, *snf-image-creator* will use a heuristic approach to
determine where to store large temporary files. It will examine the free space
under */var/tmp*, the user's home directory and */mnt* and will pick the one
with the most available space. The user may overwrite this behaviour and
indicate a different directory using the *tmpdir* option. This option is
supported by both *snf-image-creator* and *snf-mkimage*.

.. rubric:: Footnotes

.. [#f1] http://sourceware.org/lvm2/
.. [#f2] http://mirrors.slackware.com/slackware/slackware-14.0/README.initrd
