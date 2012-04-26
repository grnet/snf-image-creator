# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

import struct
import sys
import uuid
import binascii

BLOCKSIZE = 512


class MBR(object):
    class Partition(object):
        format = "<B3sB3sLL"

        def __init__(self, raw_part):

            (   self.status,
                self.start,
                self.type,
                self.end,
                self.first_sector,
                self.sector_count
            ) = struct.unpack(self.format, raw_part)

        def pack(self):
            return struct.pack(self.format,
                self.status,
                self.start,
                self.type,
                self.end,
                self.first_sector,
                self.sector_count
            )

        def show(self):
            start = self.unpack_chs(self.start)
            end = self.unpack_chs(self.end)
            print "%d %s %d %s %d %d" % (self.status, start, self.type, end,
                self.first_sector, self.sector_count)

        def unpack_chs(self, chs):

            assert len(chs) == 3

            head = struct.unpack('<B', chs[0])[0]
            sector = struct.unpack('<B', chs[1])[0] & 0x3f
            cylinder = (struct.unpack('<B', chs[1])[0] & 0xC0) << 2 | \
                struct.unpack('<B', chs[2])[0]

            return (cylinder, head, sector)

        def pack_chs(self, cylinder, head, sector):

            assert 1 <= sector <= 63
            assert 0 <= cylinder <= 1023
            assert 0 <= head <= 255

            byte0 = head
            byte1 = (cylinder >> 2) & 0xC0 | sector
            byte2 = cylinder & 0xff

            return struct.pack('<BBB', byte0, byte1, byte2)

    format = "<444s2x16s16s16s16s2s"
    """
    Offset  Length          Contents
    0       440(max. 446)   code area
    440     2(optional)     disk signature
    444     2               Usually nulls
    446     16              Partition 0
    462     16              Partition 1
    478     16              Partition 2
    494     16              Partition 3
    510     2               MBR signature
    """
    def __init__(self, block):
        raw_part = {}
        self.code_area, \
        raw_part[0], \
        raw_part[1], \
        raw_part[2], \
        raw_part[3], \
        self.signature = struct.unpack(self.format, block)

        self.part = {}
        for i in range(4):
            self.part[i] = self.Partition(raw_part[i])

    def pack(self):
        return struct.pack(self.format,
            self.code_area,
            self.part[0].pack(),
            self.part[1].pack(),
            self.part[2].pack(),
            self.part[3].pack(),
            self.signature
        )

    def show(self):
        for i in range(4):
            print "Part %d: " % i,
            self.part[i].show()


class GPTPartitionTable(object):
    class GPTHeader(object):
        format = "<8s4sII4xQQQQ16sQIII"
        """
        Offset	Length 	        Contents
        0       8 bytes         Signature
        8       4 bytes 	Revision
        12      4 bytes 	Header size in little endian
        16 	4 bytes 	CRC32 of header
        20 	4 bytes 	Reserved; must be zero
        24 	8 bytes 	Current LBA
        32 	8 bytes 	Backup LBA
        40 	8 bytes 	First usable LBA for partitions
        48 	8 bytes 	Last usable LBA
        56 	16 bytes 	Disk GUID
        72 	8 bytes 	Partition entries starting LBA
        80 	4 bytes 	Number of partition entries
        84 	4 bytes 	Size of a partition entry
        88 	4 bytes 	CRC32 of partition array
        92 	* 	        Reserved; must be zeroes
        LBA    size            Total
        """

        def __init__(self, block):
            self.signature, \
            self.revision, \
            self.size, \
            self.header_crc32, \
            self.current_lba, \
            self.backup_lba, \
            self.first_usable_lba, \
            self.last_usable_lba, \
            self.uuid, \
            self.part_entry_start, \
            self.part_count, \
            self.part_entry_size, \
            self.part_crc32 = struct.unpack(self.format, block)

        def pack(self):
            return struct.pack(self.format,
                self.signature, \
                self.revision, \
                self.size, \
                self.header_crc32, \
                self.current_lba, \
                self.backup_lba, \
                self.first_usable_lba, \
                self.last_usable_lba, \
                self.uuid, \
                self.part_entry_start, \
                self.part_count, \
                self.part_entry_size, \
                self.part_crc32
            )

        def show(self):
            print "Signature: %s" % self.signature
            print "Revision: %r" % self.revision
            print "Header Size: %d" % self.size
            print "CRC32: %d" % self.header_crc32
            print "Current LBA: %d" % self.current_lba
            print "Backup LBA: %d" % self.backup_lba
            print "First Usable LBA: %d" % self.first_usable_lba
            print "Last Usable LBA: %d" % self.last_usable_lba
            print "Disk GUID: %s" % uuid.UUID(bytes=self.uuid)
            print "Partition entries starting LBA: %d" % self.part_entry_start
            print "Number of Partition entries: %d" % self.part_count
            print "Size of a partition entry: %d" % self.part_entry_size
            print "CRC32 of partition array: %s" % self.part_crc32

    def __init__(self, disk):
        self.disk = disk
        with open(disk, "rb") as d:
            #MBR (Logical block address 0)
            lba0 = d.read(BLOCKSIZE)
            self.mbr = MBR(lba0)
            # Primary GPT Header (LBA 1)
            lba1 = d.read(BLOCKSIZE)
            self.primary = self.GPTHeader(lba1[:92])
            # Partition entries (LBA 2...34)
            d.seek(self.primary.part_entry_start * BLOCKSIZE)
            entries_size = self.primary.part_count * \
                                                self.primary.part_entry_size
            self.part_entries = d.read(entries_size)
            # Secondary GPT Header (LBA -1)
            d.seek(self.primary.backup_lba * BLOCKSIZE)
            lba_1 = d.read(BLOCKSIZE)
            self.secondary = self.GPTHeader(lba_1[:92])

    def size(self):
        return (self.primary.backup_lba + 1) * BLOCKSIZE 

    def shrink(self, size):

        if size == self.size():
            return size

        assert size < self.size()

        # new_size = size + Partition Entries + Secondary GPT Header
        new_size = size + len(self.part_entries) + BLOCKSIZE
        new_size = ((new_size + 4095) // 4096) * 4096  # align to 4K
        lba_count = new_size // BLOCKSIZE

        # Correct MBR
        #TODO: Check for hybrid partition tables
        self.mbr.part[0].sector_count = (new_size // BLOCKSIZE) - 1

        # Correct Primary header
        self.primary.header_crc32 = 0
        self.primary.backup_lba = lba_count - 1  # LBA-1
        self.primary.last_usable_lba = lba_count - 34  # LBA-34
        self.primary.header_crc32 = \
                            binascii.crc32(self.primary.pack()) & 0xffffffff

        # Correct Secondary header entries
        self.secondary.header_crc32 = 0
        self.secondary.current_lba = self.primary.backup_lba
        self.secondary.last_usable_lba = lba_count - 34  # LBA-34
        self.secondary.part_entry_start = lba_count - 33  # LBA-33
        self.secondary.header_crc32 = \
                            binascii.crc32(self.secondary.pack()) & 0xffffffff

        # Copy the new partition table back to the device
        with open(self.disk, "wb") as d:
            d.write(self.mbr.pack())
            d.write(struct.pack("%ss" % BLOCKSIZE, '\x00' * BLOCKSIZE))
            d.seek(BLOCKSIZE)
            d.write(self.primary.pack())
            d.seek(self.secondary.part_entry_start * BLOCKSIZE)
            d.write(self.part_entries)
            d.seek(self.primary.backup_lba * BLOCKSIZE)
            d.write(struct.pack("%ss" % BLOCKSIZE, '\x00' * BLOCKSIZE))
            d.seek(self.primary.backup_lba * BLOCKSIZE)
            d.write(self.secondary.pack())

        return new_size

if __name__ == '__main__':
    ptable = GPTPartitionTable(sys.argv[1])

    print "MBR:"
    ptable.mbr.show()
    print
    print "Primary partition table:"
    ptable.primary.show()
    print
    print "Secondary partition table:"
    ptable.secondary.show()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
