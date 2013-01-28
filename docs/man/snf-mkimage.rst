:orphan:

snf-mkimage manual page
=======================

Synopsis
--------

**snf-mkimage** [OPTION] [<INPUT MEDIA>]

Description
-----------
Create image out of an <INPUT MEDIA>. The <INPUT MEDIA> may be a block device,
a regular file that represents a hard disk or \`/' to bundle the host system
itself. If the <INPUT MEDIA> argument is missing, the user will be asked during
the program initializaton to specify one.

Options
-------
--version
	show program's version number and exit
-h, --help
	show this help message and exit
-l FILE, --logfile=FILE
	log all messages to FILE
--tmpdir=DIR
	create large temporary image files under DIR
