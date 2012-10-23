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

The first four programs (python2, setuptools, libguestfs and Python Dialog)
need to be installed manually by the user. In an Ubuntu 12.04 LTS system this
can be archived by installing packages provided by the distribution, using the
following command:

.. code-block:: console

   $ apt-get install python-setuptools python-guestfs python-dialog

The rest of the dependencies will be automatically resolved by setuptools.

Python Virtual Environment
==========================

Since snf-image-creator and the rest of it's dependencies won't be installed
using packages, it's better to work in an isolated python virtual environment
(virtualenv). Installing the Virtual Python Environment builder in Ubuntu can
be accomplished using the following command:

.. code-block:: console

   $ apt-get install python-virtualenv

Now, create a new python virtual environment like this:

.. code-block:: console

   $ virtualenv --system-site-packages ~/image-creator-env

and activate it by executing:

.. code-block:: console

   $ source ~/image-creator-env/bin/activate

You can later deactivate it using the following command:

.. code-block:: console

   $ deactivate


kamaki Installation
===================

Install kamaki from source, by cloning it's repository:

.. code-block:: console

   $ git clone https://code.grnet.gr/git/kamaki
   $ cd kamaki
   $ ./setup build

Then, make sure you are within the activated virtual environment before you
execute:

.. code-block:: console

   $ ./setup install

snf-image-creator Installation
==============================

Install snf-image-creator the same way:

.. code-block:: console

   $ git clone https://code.grnet.gr/git/snf-image-creator
   $ cd snf-image-creator
   $ ./setup build

And from within the virtual environment execute:

.. code-block:: console

   $ ./setup install

