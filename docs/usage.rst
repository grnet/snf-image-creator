Usage
=====

snf-image-creator comes in 2 variants:
 * snf-mkimage: A user-friendly dialog-based program
 * snf-image-creator: A non-interactive command line program

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
