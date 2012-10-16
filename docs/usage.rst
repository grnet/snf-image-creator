Usage
=====

snf-image-creator comes in 2 variants:
 * snf-image-creator: A non-interactive command line program
 * snf-mkimage: A user-friendly dialog-based program

Non-interactive version
-----------------------

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
the image, you need to specify *-o* option. In order to upload the image to
pithos, you need to specify valid credentials with *-a* and *-t* options and a
filename using *-u* option. To also register the image with ~okeanos, specify a
name using the *-r* option.

By default snf-image-creator will run a number of system preparation tasks on
the snapshot of the media and will shrink the last partition found, before
extracting the image. Both can be disabled by specifying *--no-sysprep* and
*--no-shrink* respectively.

If *--print-sysprep* is defined, then snf-image-creator will not create an
image at all. It will only run the OS detection part and will output the system
preparation tasks that would and would not run on the image. This behavior is,
convenient because it allows you to see the available system preparation tasks
that you can enable or disable with *-{enable,disable}-sysprep* options when
you create a new image.

Running *snf-image-creator* with *--print-sysprep* on a raw file that hosts a
debian system, I get the following output:

.. code-block:: console

   $ snf-image-creator --print-sysprep debian_desktop.img

   snf-image-creator 0.1
   =====================
   Examining source media `debian_desktop.img'... looks like an image file
   Snapshotting media source... done
   Enabling recovery proc
   Launching helper VM... done
   Inspecting Operating System... found a(n) debian system
   Mounting image... done
   
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

If I want your images to also have all normal user accounts and all mail files
removed, you can create it specifying the *--enable-sysprep* option like this:

.. code-block:: console

   $ snf-image-creator --enable-sysprep cleanup-mail,remove-user-accounts ...

Dialog-based version
--------------------


Creating a new image
--------------------

Suppose you want to create a new ubuntu server image. Download the installation
disk from the internet:

.. code-block:: console

   $ wget http://ubuntureleases.tsl.gr/12.04.1/ubuntu-12.04.1-server-amd64.iso

Create a 2G sparce file to host the new system:

.. code-block:: console

   $ truncate -s 2G ubuntu_hd.raw

And install the ubuntu system on this file:

.. code-block:: console

   $ sudo kvm -boot d -drive file=ubuntu_hd.raw,format=raw,cache=none,if=virtio \
     -cdrom ubuntu-12.04.1-server-amd64.iso

After this, become root, activate the virtual environment you have installed
snf-image-creator in, and use *snf-mkimage* to create and upload the image:

.. code-block:: console

   $ sudo -s
   $ source /path/to/snf-image-env/bin/activate
   $ snf-mkimage ubuntu_hd.raw

In the first screen you will be asked to choose if you want to run the program
in *Wizand* or *Expert* mode. Choose *Wizard*.

.. image:: /snapshots/01_wizard.png

Then you will be asked to provide a name, a description, an ~okeanos account
and the token corresponding to this account. After that you will be asked to
confirm the provided data.

.. image:: /snapshots/06_confirm.png

Choosing *YES* will create the image and upload it to your ~okeanos account.

