Overview
^^^^^^^^

snf-image-creator is a simple command-line tool for creating OS images. The
original media from which the image is created, can be a block device or a
regular file that represents a hard disk. Given a media file, snf-image-creator
will create a snapshot for it and will run a number of system preparation
operations on the snapshot, before the image is created.

Snapshotting
============

snf-image-creator works on snapshots of the original media. Any changes made by
the program do not affect the original media.

Preparation
===========

Some of the system preparation operations are OS specific. snf-image-creator
will use heuristics to detect the OS of the media and determine which
operations should perform on it. The main purpose of running them is to:

 * Shrink the image
 * Clear out sensitive user data (passwords, ssh keys, history files, etc.)
 * Prepare the guest OS for being deployed on a virtual environment (change
   device names, remove persistent net rules, etc.)

Creation
========

The program can either dump the image file locally or directly upload it to
pithos and register it with `okeanos <http://www.okeanos.grnet.gr>`_.

Image Format
============

The images the program creates are in diskdump format. This is the recommended
format for `snf-image <https://code.grnet.gr/projects/snf-image>`_, the Ganeti
OS Definition used by `Synnefo <https://code.grnet.gr/projects/synnefo>`_.
