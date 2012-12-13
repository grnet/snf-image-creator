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

 * Name: A short name for the image (ex. "Slackware")
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

Usage example
=============

Supposing you have snf-image-creator installed on a machine (hereafter referred
to as your **host machine**), you can follow the next steps to upload and
register an image of an OS of your preference (hereafter referred to as your
**guest OS**) to your synnefo deployment.

 * `Step 1: Install the guest OS`_
 * `Step 2: Create and upload an image of the guest OS`_
 * `Step 3: Create your VM`_


Step 1: Install the guest OS
-----------------------------

The guest OS has to be installed on a media such as a block device or a regular
raw file, that can be **accessible** by your host machine.

But why is accessible empasized? Well, because you don't need to do the
installation of the guest OS on your host machine. You can just as well install
it on a raw file, upload it on Pithos+, download it on your host machine and
use it for Step 2.

*Note: If you have a guest OS already installed, you may want to skip the
next step. However, be sure to check out the* `Caveats`_ *section, where
some requirements about the guest OS are presented.*

Installation example
""""""""""""""""""""

To simplify things a bit, we will install the guest OS on the host machine
where snf-image-creator is installed. We will assume that the host machine is
an Ubuntu 12.04 ~okeanos VM, built with max specifications (4 CPUs, 2GB of
ram, 40GB of disk space at the time of writing this).

*Note: Since the installation of the guest OS will take place on your host
VM, you must be able to connect to it graphically. This is covered by our*
`connection guide <https://okeanos.grnet.gr/support/user-guide/cyclades-how-do-
i-connect-to-a-vm/#windows-linux-host-to-linux-guest-graphical>`_.

For our guest OS, we will choose, Linux Mint, which is the most hyped Linux
OS according to Distrowatch. A new version has just been released, so
this seems like a fine choice. ::

   Warning: The installation might take a long time (~1 hour) and a bit of
   lagginess due to nested virtualization is to be expected.

Fire up your terminal, go to your home directory and type the following to
download the Linux Mint live cd::

   $ wget http://ftp.ntua.gr/pub/linux/linuxmint//stable/14/linuxmint-14-mate-dvd-64 bit.iso

Verify that it has been downloaded correctly. If the following command
prints "OK". then you are good to go::

   $ echo 'b370ac59d1ac6362f1662cfcc22a489c linuxmint-14-mate-dvd-64bit.iso' > check.md5
   $ md5sum -c check.md5

Allocate a few gigs of space to create a sparse file::

   $ truncate -s 7G linuxmint.raw

Use `kvm` to boot the Live CD::

   $ sudo kvm -m 1200 -smp 4 -boot d -drive \
     file=linuxmint.raw,format=raw,cache=none,if=virtio \
     -cdrom linuxmint-14-mate-dvd-64bit.iso

   At a glance, let's see what the above options do:
     -m 1200:               Use 1200MB of RAM for the guest OS. You should
                            allocate as much as possible
     -smp 4:                Simulate an SMP system with 4 CPUs for the
                            guest OS to use.
     -boot d:               Place cdrom first in the boot order
     file=opensuse.raw      Use this raw file as the "hard disk" for the
                            installation
     if=virtio:             Inform the OS that it should preload the
                            VirtIO drivers (more on that on `Caveats`_
                            section)
     -cdrom linuxmint-14-mate-dvd-64bit.iso:
                            "Insert" Linux Mint's live cd in the cdrom
                            drive

Wait a few seconds and then a new screen with the Linux Mint logo should
appear. You don't have to press any key since it will boot automatically to
Linux Mint's live desktop after a few minutes.

|qemu-live|

Choose "Install Linux Mint". The installation process should be pretty
straightforward. Just keep two things in mind:

* The username you choose will also be used later on, when you create a VM
  from this OS image. The password, however, will be removed and you will
  be given a new one.
* The installed OS must have no more than one primary partition and
  optionally a swap partition. You can read more in the `Caveats`_
  section below. You don't have to worry about it in this installation
  however, since the default option takes care of that.

  |qemu-partition|

After the installation is complete, you can close the QEMU window. You
will be able to boot your installed OS and make any changes you want to it
using the following command::

   $ sudo kvm -m 1200 -smp 4 -boot d -drive \
   file=linuxmint.raw,format=raw,cache=none,if=virtio

At the very least, you should install OpenSSH server to connect to your VM
properly. You can install OpenSSH server using the following command::

   $ sudo apt-get install openssh-server

Bear in mind that once the OS image has been uploaded to your synnefo
deployment, you will not be able to make changes to it. Since you can only
apply changes to your raw file, you are advised to do so now and then proceed
to Step 2.

Caveats
"""""""
This is a list of restrictions you must have in mind while installing the
guest OS:

**Partitions**

The installation must consist of no more than one primary partition. It
can have a swap partition though, which should ideally - but not
necessarily - be located at the end of the media. In this case, the
uploaded image will be much smaller and the VM deployment process much
faster.

**VirtIO drivers**

Depending on your synnefo-deployment, you may need to use para-virtualized
drivers for your storage and network needs.

~okeanos uses the VirtIO framework which is essential for the ~okeanos VMs
to work properly since their disk I/O controller and Ethernet cards are
para-virtualized.

Fortunately, you will not need to deal with the installation of VirtIO drivers
directly, since they are included in Linux kernel since version 2.6.25 and
shipped with all the modern Linux distributions. However, if the VirtIO drivers
are built as a module (and most modern OSes do so), they need to be preloaded
using an initial ramdisk (initramfs), otherwise the VM you create from this OS
image will not be able to boot.

Debian derivatives will create an initial ramdisk with VirtIO included if
they are connected during the installation on a para-virtualized interface
(the "if=virtio" option in the Linux Mint example).

In many other distros though, this is not the case. In Arch Linux for
example, the user needs to manually add virtio_blk and virtio_pci drivers
in /etc/mkinitcpio.conf and rebuild the initial ramdisk to make the
virtio drivers get preloaded during boot. You can read more in the `Arch
Linux wiki <https://wiki.archlinux.org/index.php/KVM#Paravirtualized_
guests_.28virtio.29>`_ on how to do it.

For now, snf-image-creator cannot resolve this kind of problems and it's
left to the user to do it.

Step 2: Create and upload an image of the guest OS
--------------------------------------------------

This is the step on which we use snf-image-creator. There are actually two
variants of snf-image-creator, `snf-image-creator`_ and `snf-mkimage`_, both
achieving the same results but suited for different needs. Their scope is
documented at the start of the `Usage`_ section of this document.

*Note: Both tools take a snapshot of the installed OS on the media
provided to them. So, any changes they apply do not affect the OS
installed on the original media.*

Let's see both tools in action. We will use them to create an image of the
Linux Mint 14 OS we installed in Step 2.

snf-mkimage
"""""""""""

In order to use snf-mkimage, simply type::

   $ sudo snf-mkimage linuxmint.raw

snf-mkimage will initially check if the media is indeed a single disk
partition or a raw file representing a hard disk. Then, it will use
heuristics to understand which OS has been installed on the media. After
that, you will be asked which mode you prefer.

|mkimage-wizard|

* Wizard mode is intuitive and consists of 4 simple steps.
* Expert mode has an abundance of options but requires a bit of knowledge
  of the inner workings of Cyclades from your part. You can learn more on the
  `Expert Mode`_ section of snf-mkimage.

For our tutorial, we will use Wizard mode. So, choose "Wizard" and then provide
a name for the image.

|mkimage1|

This name will appear on Pithos+ and on the Public Images section of Cyclades.

Then, provide a description for the image.

|mkimage2|

This will appear under the chosen image name on the Public Images section of
cyclades.

Next, add your account e-mail

|mkimage3|

... your account token...

|mkimage4|

...and you're done! A list operations will appear on your console.

|mkimage-results|

We will briefly comment on the above output.

* **Sysprep:** Operations from 1/9 to 9/9 are part of the system
  preparation operations and are best explained in the snf-image-creator's
  `sysprep`_ section.
* **Shrinking:** When shrinking the image, we check if a swap partition
  exists at the end of the media. If this is the case, it will be removed
  and re-inserted upon the deployment process of the VM. Alternatively, if
  the swap partition lies at the start of the media, it will be left
  untouched. On both cases, the primary partition will be shrunken as much
  as possible. On this example, we can see that the final size is 3.5GB,
  whereas the orginal size was 7GB. This means that the image was reduced
  by half, a pretty impressive feat.
* **MD5SUM:** The md5sum of the image is used later on to verify that the
  image has been uploaded successfully.
* **Uploading:** Everytime you upload an OS image, every block is hashed,
  checked against existing blocks in Pithos+ and finally uploaded, if no
  other block has the same hash.

  *Consider this example: You have just uploaded a Gentoo Linux image but
  had forgotten to install a necessary package. In this case, you would
  probably edit the OS in the raw file and then use snf-mkimage to upload
  the new image. However, since there is an almost identical image already
  uploaded on Pithos+, you can just as well upload only the blocks that
  differentiate those two images. This is both time and space efficient.*

Finally, after the image has been uploaded successfully, you will be asked
whether you want to save a local copy of the **shrunken** image. This is
just a copy of the diskdump that has been uploaded to Pithos+ and, in case
you are confused, the original OS installed on the media (linuxmint.raw in
our example) remains intact.

snf-image-creator
"""""""""""""""""

snf-image-creator is the command-line equivalent of snf-mkimage. All the
info provided in the steps above are given now as options, which makes it
ideal for scripting purposes. The full set of options can be found in the
`Usage section <#non-interactive-version>`_ of snf-image-creator's
documentation.

This tool is most commonly used with the following set of options::

   $ sudo snf-image-creator linuxmint.raw -a user@email.com \
   -t hUudl4DEIlomlnvWnv7Rlw== -u linuxmint.diskdump -r "Linux Mint 14 Nadia"

As you can see, these options are exactly what snf-mkimage's steps
translate to. You can also see that the output is nearly identical:

|image-creator|

Step 3: Create your VM
----------------------

Creating a VM out of an uploaded custom image is a fairly simple task.
Just select "New Machine", go to "My Images" section and select your
image.

|custom-vm|

Alternatively, if you want to create a VM from another user's custom
image, you can go to the "Public Images" section.

.. |qemu-live| image:: /snapshots/qemu-live.png

.. |qemu-partition| image:: /snapshots/qemu-partition.png

.. |mkimage-wizard| image:: /snapshots/mkimage-wizard.png

.. |mkimage1| image:: /snapshots/mkimage1.png

.. |mkimage2| image:: /snapshots/mkimage2.png

.. |mkimage3| image:: /snapshots/mkimage3.png

.. |mkimage4| image:: /snapshots/mkimage4.png

.. |mkimage-fin| image:: /snapshots/mkimage-fin.png

.. |mkimage-results| image:: /snapshots/mkimage-results.png

.. |image-creator| image:: /snapshots/image-creator.png

.. |custom-vm| image:: /snapshots/custom-vm.png

