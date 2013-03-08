Configuration tasks performed during deployment
===============================================

Partition Table manipulation
----------------------------
During image deployment the last partiton is enlarged to use all
the available disk space. If SWAP property is present an extra
swap partition is also added.

File system Resize
------------------
This task enlarges the file system of the last partition to use
all the available partition space.

Swap partition configuration
----------------------------
If swap partition is added during the image deployment, the swap
partition is formated and a swap entry is added to the instance's
fstab.

SSH keys removal
----------------
All SSH keys found in the image are removed. For debian instance,
where the key creation is not perfored automatically, the keys
are recreated by this task.

Temporary disable Remote Desktop (RDP) connections
--------------------------------------------------
RDP connections are temporarily disabled during Windows
configuration. This is done because when sysprep runs, there is a
small time interval where the new password is not applied yet thus
allowing RDP connections which raises some security conserns.

Perform SELinux file system relabeling
--------------------------------------
For redhat-based images, since the instance's disk is modified
during deployment, a full SELinux file system relabeling needs to
be performed. This tasks triggers a full file system relabel at
the next boot.

Hostname or Computer name assignment
------------------------------------
The instance name is assigned as hostname (or Computer Name for
Windows instances).

Change password
---------------
This task will change the password for the users specified by
the USERS property.

File Injection
--------------
The files specified by the PERSONALITY image property are
injected into the instance's hard disk.
