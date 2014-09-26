:orphan:

snf-mkimage manual page
=======================

Synopsis
--------

**snf-mkimage** [OPTION] <INPUT MEDIA>

Description
-----------
Create image out of an <INPUT MEDIA>. The <INPUT MEDIA> may be a block device,
a regular file that represents a hard disk or \`/' to bundle the host system
itself.

Options
-------
-a URL, --authentication-url=URL
	use this authentication URL when uploading/registering images

--allow-unsupported
	Proceed with the image creation even if the media is not supported

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

--no-snapshot
	don't snapshot the input media. (THIS IS DANGEROUS AS IT WILL ALTER THE
	ORIGINAL MEDIA!!!)
--no-sysprep
	don't perform any system preparation operation

-o FILE, --outfile=FILE
	dump image to FILE

--public
	register image with the storage service as public

--print-syspreps
	print the enabled and disabled system preparation operations for this
	input media

--print-sysprep-params
	print the needed sysprep parameters for this input media

-r IMAGENAME, --register=IMAGENAME
	register the image with the compute service with name IMAGENAME

-s, --silent
	output only errors

--sysprep-param=SYSPREP_PARAMS
	add KEY=VALUE system preparation parameter

-t TOKEN, --token=TOKEN
	use this token when uploading/registering images

--tmpdir=DIR
	create large temporary image files under DIR

-u FILENAME, --upload=FILENAME
	save the image to the storage service with remote name FILENAME

--version
	show program's version number and exit

