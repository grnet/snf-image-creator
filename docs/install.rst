Installation
^^^^^^^^^^^^

This guide describes how to install snf-image-creator on an Ubuntu 12.04 LTS
system. It it highly recommended to have virtualization capable hardware.
snf-image-creator will work on processors that do not support virtualization
but it will be extremely slow.

Dependencies
============

snf-image-creator depends on the following programs:

 * Python 2 [http://www.python.org/]
 * Python setuptools [http://pypi.python.org/pypi/setuptools]
 * Python Dialog [http://pythondialog.sourceforge.net/]
 * Python bindings for libguestfs [http://libguestfs.org/]
 * Kamaki [https://code.grnet.gr/projects/kamaki]
 * Python sh (previously pbs) [https://github.com/amoffat/sh]
 * ANSI colors for Python [http://pypi.python.org/pypi/ansicolors]
 * progress [http://pypi.python.org/pypi/progress]
 * Python interface to sendfile [http://pypi.python.org/pypi/pysendfile]

When installing snf-image-creator, the above dependencies are automatically
resolved.

Development repository addition
===============================

In order to install snf-image-creator and the rest of it's dependencies, you
must first add GRNET's dev repo to your sources. You can use the following
commands:

.. code-block:: console

   cd /etc/apt/sources.list.d
   echo "deb http://apt.dev.grnet.gr precise main" | \
   sudo tee -a  apt.dev.grnet.gr.list
   echo "deb-src http://apt.dev.grnet.gr precise main" | \
   sudo tee -a apt.dev.grnet.gr.list

You will also need to import the repo's GPG key. You can use the ``curl`` tool
for this.

.. code-block:: console

   $ sudo apt-get install curl

Use the following command to import the GPG key:

.. code-block:: console

   $ sudo curl https://dev.grnet.gr/files/apt-grnetdev.pub | sudo apt-key add -

You can verify that the repo has been added successfully if snf-image-creator
exists as a package. First do an update of your sources:

.. code-block:: console

   $ sudo apt-get update

then check if snf-image-creator exists with the following command:

.. code-block:: console

   $ apt-cache showpkg snf-image-creator

snf-image-creator Installation
==============================

If GRNET's dev repo has been added successfully, you can install
snf-image-creator, along with its dependencies, with the following command:

.. code-block:: console

   $ sudo apt-get install snf-image-creator

The installation might take a while. Please note that at some point during the
installation you will be prompted to create/update a "supermin appliance". This
is a setting regarding libguestfs and you can safely choose "Yes".
