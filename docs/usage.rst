Usage
^^^^^

snf-image-creator comes in 2 variants:
 * snf-image-creator: A non-interactive command line program
 * snf-mkimage: A user-friendly dialog-based program

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
  -s, --silent          silent mode, only output errors
  -u FILENAME, --upload=FILENAME
                        upload the image to pithos with name FILENAME
  -r IMAGENAME, --register=IMAGENAME
                        register the image with ~okeanos as IMAGENAME
  -a ACCOUNT, --account=ACCOUNT
                        Use this ACCOUNT when uploading/registering images
                        [Default: None]
  -m KEY=VALUE, --metadata=KEY=VALUE
                        Add custom KEY=VALUE metadata to the image
  -t TOKEN, --token=TOKEN
                        Use this token when uploading/registering images
                        [Default: None]
  --print-sysprep       print the enabled and disabled system preparation
                        operations for this input media
  --enable-sysprep=SYSPREP
                        run SYSPREP operation on the input media
  --disable-sysprep=SYSPREP
                        prevent SYSPREP operation from running on the input
                        media
  --no-sysprep          don't perform system preparation
  --no-shrink           don't shrink any partition


Most input options are self-describing. If you want to save a local copy for
the image you create, you specify *-o* option. To upload the image to
*pithos+*, you specify valid credentials with *-a* and *-t* options and a
filename using *-u*. If you want to register the image with *~okeanos*,
in addition to *-u* specify a registration name using *-r*.

By default snf-image-creator will perform a number of system preparation
operations on the snapshot of the media and will shrink the last partition
found, before extracting the image. Both can be disabled by specifying
*--no-sysprep* and *--no-shrink* respectively.

If *--print-sysprep* is defined, the program will exit after outputing a
list of enabled and disabled system preparation operation appliable to this
media source. The user can enable or disable specific *syspreps* when creating
an image, using *-{enable,disable}-sysprep* options. You can specify those
options multiple times to enable or disable multiple *syspreps*.

Running *snf-image-creator* with *--print-sysprep* on a raw file that hosts a
debian system, we get the following output:

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

If we want the image to have all normal user accounts and all mail files
removed, we can create it specifying *--enable-sysprep* option like this:

.. code-block:: console

   $ snf-image-creator --enable-sysprep cleanup-mail --enable-sysprep remove-user-accounts ...

Dialog-based version
====================

*snf-mkimage* receives the following options:

.. code-block:: console

   $ Usage: snf-mkimage [options] [<input_media>]

   Options:
     --version             show program's version number and exit
     -h, --help            show this help message and exit
     -l FILE, --logfile=FILE
                            log all messages to FILE

If the input media is not specified in the command line, in the first dialog
box the user will be asked to specify it. After the input media is examined and
the program is initialized, the user will be given the choice to run
*snf-mkimage* in *wizard* or *expert* mode.

Wizard mode
-----------

When *snf-mkimage* runs in *wizard* mode, the user is just asked to provide the
following basic information:

 * Name: A short name for image (ex. "Slackware")
 * Description: An one-line description for the image (ex. "Slackware Linux 14.0 with KDE")
 * Account: An *~okeanos* account email
 * Token: A token corresponding to the account defined previously

After confirming, the image will be extracted, uploaded to *pithos+* and
registered to *~okeanos*. The user will also be given the choice to keep a local
copy of it. For most users the functionality this mode provides should be
sufficient.

Expert mode
-----------

Expert mode allows the user to have better control on the image creation
process. In the picture below the main menu can be seen:

.. image:: /snapshots/main_menu.png

In the *Customize* sub-menu the user can control:

 * The system preparation operations that will be applied on the media
 * Whether the image will be shrunk or not
 * The properties associated with the image
 * The configuration tasks that will run during image deployment

In the *Register* sub-menu the user can provide:

 * The credentials to login to *~okeanos*
 * A pithos filename for the uploaded *diskdump* image
 * A name for the image to be registered to *~okeanos* with

By choosing the *Extract* menu entry the user can dump the image to the local
file system and finally, if the user selects *Reset*, the system will ignore
all changes made so far and will start the image creation process again.

Creating a new image
====================

Suppose you want to create a new Ubuntu server image. Download the installation
disk from the Internet:

.. code-block:: console

   $ wget http://ubuntureleases.tsl.gr/12.04.1/ubuntu-12.04.1-server-amd64.iso

Create a 2G sparce file to host the new system:

.. code-block:: console

   $ truncate -s 2G ubuntu_hd.raw

And install the Ubuntu system on this file:

.. code-block:: console

   $ sudo kvm -boot d -drive file=ubuntu_hd.raw,format=raw,cache=none,if=virtio \
     -cdrom ubuntu-12.04.1-server-amd64.iso

After the installation finishes, become root, activate the virtual environment
you have installed snf-image-creator in, and use *snf-mkimage* to create and
upload the image:

.. code-block:: console

   $ sudo -s
   $ source /path/to/snf-image-env/bin/activate
   $ snf-mkimage ubuntu_hd.raw

In the first screen you will be asked to choose if you want to run the program
in *Wizard* or *Expert* mode. Choose *Wizard*.

.. image:: /snapshots/01_wizard.png

Then you will be asked to provide a name, a description, an *~okeanos* account
and the token corresponding to this account. After that you will be asked to
confirm the provided data.

.. image:: /snapshots/06_confirm.png

Choosing *YES* will create the image and upload it to your *~okeanos* account.

Some caveats on image creation
==============================

Para-virtualized drivers
------------------------

*~Okeanos* uses the *VirtIO* framework. The disk I/O controller and the
Ethernet cards on the VM instances are para-virtualized and need special
*VirtIO* drivers. Those drivers are included in the Linux Kernel mainline since
version 2.6.25 and are shipped with all the popular Linux distributions. The
problem is that if the driver for the para-virtualized disk I/O controller is
built as module, it needs to be preloaded using an initial ramdisk, otherwise
the VM will not be able to boot.

In the image creation demonstration above, we initially installed the Ubuntu
system on a hard disk (*ubuntu_hd.raw*) that was connected on a
para-virtualized interface (pay attention to the *if=virtio* option of the kvm
line). Ubuntu and Debian create a generic initial ramdisk file that contains
many different modules, including the VirtIO drivers. In many distros this is
not the case. In Arch Linux for example, the user needs to manually add
*virtio_blk* and *virtio_pci* drivers in */etc/mkinitcpio.conf* and rebuild the
initial ramdisk [#f1]_ to make the virtio drivers get preloaded during boot.
For now, *snf-image-creator* cannot resolve this kind of problems and it's left
to the user to do it.

Swap partitions
---------------

If you want your image to have a swap partitions, make sure this is the last
partition on the disk. If snf-image-creator detects a swap partition in the end
of the input media, it will remove the partition when shrinking and will save
enough information to be able to recreate it during image deployment. This will
make the image smaller and will speed up the deployment process.

.. rubric:: Footnotes

.. [#f1] https://wiki.archlinux.org/index.php/KVM#Paravirtualized_guests_.28virtio.29
