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
 * pyparted [https://fedorahosted.org/pyparted/]
 * ./kamaki [https://code.grnet.gr/projects/kamaki]
 * Python sh (previously pbs) [https://github.com/amoffat/sh]
 * ANSI colors for Python [http://pypi.python.org/pypi/ansicolors]
 * progress [http://pypi.python.org/pypi/progress]

The above dependencies are resolved differently, depending on the installation
method you choose. There are two installation methods available:

#. `Installation using official packages <#install-snf-image-creator-using-official-packages>`_ (currently only for Ubuntu 12.04 LTS and 12.10).

#. `Installation from source <#install-snf-image-creator-using-official-packages>`_

Install snf-image-creator using official packages
=================================================

For Ubuntu systems, you can use our official packages found in the Lauchpad
PPA: *ppa:grnet/synnefo*

.. note::
   This method of installing snf-image-creator has all the advantages of
   Ubuntu's APT installation, like automatic dependencies resolution and simple
   update process.

In order to proceed with the installation, you must first add the synnefo PPA
repository in your system:

.. code-block:: console

   $ sudo apt-add-repository ppa:grnet/synnefo
   $ sudo apt-get update

If *apt-add-repository* is missing, install *software-properties-common* first:

.. code-block:: console

   $ sudo apt-get install software-properties-common

The snf-image-creator package should now be listed calling:

.. code-block:: console

   $ apt-cache showpkg snf-image-creator

You can now install the package by issuing:

.. code-block:: console

   $ sudo apt-get install snf-image-creator

.. note::
   If you are asked during the installation to create/update a
   "supermin appliance", choose "Yes".

Install snf-image-creator from source
=====================================

Manually install the following dependencies:

 * Python 2 [http://www.python.org/]
 * Python setuptools [http://pypi.python.org/pypi/setuptools]
 * Python Dialog [http://pythondialog.sourceforge.net/]
 * Python bindings for libguestfs [http://libguestfs.org/]
 * Python interface to sendfile [http://pypi.python.org/pypi/pysendfile]
 * pyparted [https://fedorahosted.org/pyparted/]

In Ubuntu you can do this using:
 
.. code-block:: console

   $ apt-get install python-setuptools python-guestfs python-dialog \
     python-sendfile python-parted

.. note::

   If during the installation you get prompted to create/update a
   "supermin appliance", choose "Yes".


Python Virtual Environment
--------------------------

Since snf-image-creator and the rest of its dependencies won't be installed
using packages, it's better to work in an isolated python virtual environment
(virtualenv).

Install the Virtual Python Environment builder:
http://pypi.python.org/pypi/virtualenv.

For Ubuntu use the following command:

.. code-block:: console

   $ apt-get install python-virtualenv

Create a new python virtual environment:

.. code-block:: console

   $ virtualenv --system-site-packages ~/image-creator-env

and activate it by executing:

.. code-block:: console

   $ source ~/image-creator-env/bin/activate

You may later deactivate it using:

.. code-block:: console

   $ deactivate

kamaki Installation
-------------------

Refer to `./kamaki documentation <http://docs.dev.grnet.gr/kamaki/latest/installation.html>`_
for instructions. You may install kamaki from source inside the virtualenv or
use binary packages if they are available for your distribution.

snf-image-creator Installation
------------------------------

Download the latest snf-image-creator source package from
`here <https://code.grnet.gr/projects/snf-image-creator/files>`_ and install it
inside the virtualenv using the following commands:

.. code-block:: console

   $ tar -xf snf_image_creator-<VERSION>.tar.gz
   $ cd snf_image_creator-<VERSION>
   $ python ./setup install

Alternatively, you can install the bleeding edge version of the software by
cloning its git repository:

.. code-block:: console

   $ git clone https://code.grnet.gr/git/snf-image-creator
   $ cd snf-image-creator
   $ python ./setup.py install

To do the latter, you'll need to have git (http://git-scm.com/) installed.
For ubuntu this can be done using:

.. code-block:: console

   $ apt-get install git

.. warning::

   Keep in mind that the bleeding edge version may be unstable or even
   unusable.


