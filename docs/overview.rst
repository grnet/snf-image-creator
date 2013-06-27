Overview
^^^^^^^^

snf-image-creator is a simple command-line tool for creating OS images. The
original media the image is created from, can be a block device, a regular
file that represents a hard disk or the host system itself.

Snapshotting
============

snf-image-creator works on snapshots. Any changes made by the program do not
affect the original media.

Image Preparation
=================

During the image creation, a number of system preparation operations are
applied on the media snapshot. Some of those are OS specific. snf-image-creator
will use heuristics to detect the OS and determine which operations to apply.
Those operations will:

 * Shrink the image
 * Clear out sensitive user data (passwords, ssh keys, history files, etc.)
 * Prepare the guest OS for being deployed on a virtual environment (change
   device names, remove persistent net rules, etc.)

Creation
========

The program can either dump the image file locally or use
`./kamaki <https://code.grnet.gr/projects/kamaki>`_ to directly upload and
register it on a `Synnefo <https://code.grnet.gr/projects/synnefo>`_
deployment as private or public image.

Image Format
============

The extracted images are in diskdump format, which is a raw dump of a disk
device (or file). This is the recommended format for
`snf-image <https://code.grnet.gr/projects/snf-image>`_, the Ganeti OS
Definition used by `Synnefo <https://code.grnet.gr/projects/synnefo>`_.
