Installation
^^^^^^^^^^^^

This guide describes how to install snf-image-creator on your machine. It is
highly recommended to have virtualization capable hardware. snf-image-creator
will work on processors that do not support virtualization but it will be slow.

Dependencies
============

snf-image-creator depends on the following programs:

 * Python 2 [http://www.python.org/]
 * Python setuptools [http://pypi.python.org/pypi/setuptools]
 * Python Dialog [http://pythondialog.sourceforge.net/]
 * Python bindings for libguestfs [http://libguestfs.org/]
 * Python interface to sendfile [http://pypi.python.org/pypi/pysendfile]
 * Kamaki [https://code.grnet.gr/projects/kamaki]
 * Python sh (previously pbs) [https://github.com/amoffat/sh]
 * ANSI colors for Python [http://pypi.python.org/pypi/ansicolors]
 * progress [http://pypi.python.org/pypi/progress]

The above dependencies are resolved differently, depending on the installation
method you choose. There are two installation methods available:

#. `Install snf-image-creator using official packages`_ (currently only for
   Ubuntu 12.04, more OSes will be supported soon)
#. `Install snf-image-creator from source`_ (provided you meet the above
   dependencies)

Both methods are presented below.

Install snf-image-creator using official packages
=================================================

This method of installing snf-image-creator has all the advantages of Ubuntu's
APT installation:

* Automatic resolution of dependencies
* Simple installation of consequent updates

In order to proceed with the installation, you must first add GRNET's dev repo
to your sources. You can use the following commands:

.. code-block:: console

   $ cd /etc/apt/sources.list.d
   $ echo "deb http://apt.dev.grnet.gr precise main" | \
   sudo tee -a  apt.dev.grnet.gr.list
   $ echo "deb-src http://apt.dev.grnet.gr precise main" | \
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

If GRNET's dev repo has been added successfully, you can install
snf-image-creator, along with its dependencies, with the following command:

.. code-block:: console

   $ sudo apt-get install snf-image-creator

The installation may take a while. Please note that at some point during the
installation you will be prompted to create/update a "supermin appliance". This
is a setting regarding libguestfs and you can safely choose "Yes".

Install snf-image-creator from source
=====================================

This method provides you with the cutting edge of snf-image-creator, which
gives you access to all the latest features. Keep in mind, however,
that you may experience instability issues.

The first five dependencies (python2, setuptools, Python-Dialog, libguestfs and
python-sendfile) need to be installed manually by the user. In an Ubuntu 12.04
LTS system this can be achieved by installing packages provided by the
distribution, using the following command:

.. code-block:: console

   $ apt-get install python-setuptools python-guestfs python-dialog python-sendfile

The rest of the dependencies will be automatically resolved by setuptools.
Note that at some point during the installation, you will be prompted to
create/update a "supermin appliance". This is a setting regarding libguestfs
and you can safely choose "Yes".

In order to download the source files, git needs to be installed. You can do
so with the following command:

.. code-block:: console

   $ apt-get install git

Python Virtual Environment
--------------------------

Since snf-image-creator and the rest of its dependencies won't be installed
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

snf-common Installation
-----------------------

Install snf-common from source, by cloning it's repository:

.. code-block:: console

   $ cd ~
   $ git clone https://code.grnet.gr/git/synnefo
   $ cd synnefo/snf-common
   $ python setup.py build

Then, make sure you are within the activated virtual environment before you
execute:

.. code-block:: console

   $ python setup.py install

kamaki Installation
-------------------

Install kamaki from source, by cloning it's repository:

.. code-block:: console

   $ cd ~
   $ git clone https://code.grnet.gr/git/kamaki
   $ cd kamaki
   $ ./setup.py build

As above, make sure you are within the activated virtual environment before you
execute:

.. code-block:: console

   $ ./setup.py install

snf-image-creator Installation
------------------------------

Install snf-image-creator the same way:

.. code-block:: console

   $ cd ~
   $ git clone https://code.grnet.gr/git/snf-image-creator
   $ cd snf-image-creator
   $ git checkout stable-0.1
   $ ./setup.py build

And from within the virtual environment execute:

.. code-block:: console

   $ ./setup.py install
