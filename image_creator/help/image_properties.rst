Image properties with special meaning
=====================================

Properties used during image deployment
---------------------------------------
 - OSFAMILY={linux, windows}
     This specifies whether this is a Linux or a Windows image.
 - ROOT_PARTITION=n
     The partition number of the root partition.
 - USERS="username1 username2..."
     This is a space-seperated list of users, whose password will
     be reset during deployment.
 - SWAP=<n>:<size>
     If this property is present, a swap partition with given
     size will be created at the end of the instance's disk.
     This property only makes sense for Linux images.

Properties used by the synnefo User Interface
----------------------------------------------
 - OS
     The value of this property is used to associate the image
     with an Operating System Logo.
 - DESCRIPTION
     A short description about the image.
 - GUI
     Short description about the Graphical User Interface the
     image hosts.
 - KERNEL
     The kernel version of the image OS.
 - SORTORDER
     A number used to sort the available images
