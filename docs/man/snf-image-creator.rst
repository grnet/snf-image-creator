:orphan:

snf-image-creator manual page
=============================

Synopsis
--------

**snf-image-creator** [OPTION] <INPUT MEDIA>

Description
-----------
Create image out of an <INPUT MEDIA>. The <INPUT MEDIA> may be a block device,
a regular file that represents a hard disk or \`/' to bundle the host system
itself.

Options
-------
-a URL, --authentication-url=URL
	use this authentication URL when uploading/registering images

-c CLOUD, --cloud=CLOUD
        use this saved cloud account to authenticate against a cloud when
        uploading/registering images

--disable-sysprep=SYSPREP
	prevent SYSPREP operation from running on the input media

--enable-sysprep=SYSPREP
	run SYSPREP operation on the input media

-f, --force
	overwrite output files if they exist

-h, --help
	show this help message and exit

-m KEY=VALUE, --metadata=KEY=VALUE
	add custom KEY=VALUE metadata to the image

--no-shrink
	don't shrink any partition

--no-sysprep
	don't perform any system preparation operation

-o FILE, --outfile=FILE
	dump image to FILE

--public
	register image with the storage service as public

--print-sysprep
	print the enabled and disabled system preparation operations for this
	input media

-r IMAGENAME, --register=IMAGENAME
	register the image with the compute service with name IMAGENAME

-s, --silent
	output only errors

-t TOKEN, --token=TOKEN
	use this token when uploading/registering images

--tmpdir=DIR
	create large temporary image files under DIR

-u FILENAME, --upload=FILENAME
	save the image to the storage service with remote name FILENAME

--version
	show program's version number and exit

