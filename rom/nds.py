"""The ROM container: header fields, the file allocation table and the header CRC."""

import struct

# NDS header fields, as ROM offsets. The CRC covers every byte before its field.
NDS_HDR_ARM9 = 0x20                       # u32 ROM offset, entry point, RAM address, size
NDS_HDR_ARM9_SIZE = 0x2C
NDS_HDR_ARM7 = 0x30
NDS_HDR_FNT = 0x40
NDS_HDR_FAT = 0x48
NDS_HDR_FAT_SIZE = 0x4C
NDS_HDR_OVERLAYS9 = 0x50
NDS_HDR_BANNER = 0x68
NDS_HDR_ROM_SIZE = 0x80                   # "used ROM size"
NDS_HDR_CRC = 0x15E
FAT_ENTRY_LEN = 8                         # u32 start, u32 end per NitroFS file
FILE_ALIGN_MASK = 0x1FF                   # NitroFS files start on 512-byte boundaries
NITROCODE_MAGIC = b"\x21\x06\xC0\xDE"     # footer(s) that follow the ARM9 in the ROM
NITROCODE_LEN = 12
CRC16_INIT = 0xFFFF                       # CRC-16/MODBUS of the header
CRC16_POLY = 0xA001


def file_bytes(rom: bytearray, fid: int) -> bytes:
    """A NitroFS file by id, wherever the FAT places it."""
    fat = struct.unpack_from("<I", rom, NDS_HDR_FAT)[0]
    start, end = struct.unpack_from("<II", rom, fat + fid * FAT_ENTRY_LEN)
    return bytes(rom[start:end])


def relocate_file(rom: bytearray, fid: int, data: bytes) -> int:
    """Write a new version of a NitroFS file into the free padding after every file.

    The FAT entry follows it and the used-size header grows. Returns the ROM offset
    of the new copy. The old bytes stay where they were: the image keeps its layout.
    """
    fat = struct.unpack_from("<I", rom, NDS_HDR_FAT)[0]
    fatsize = struct.unpack_from("<I", rom, NDS_HDR_FAT_SIZE)[0]
    used = max(struct.unpack_from("<II", rom, fat + k * FAT_ENTRY_LEN)[1]
               for k in range(fatsize // FAT_ENTRY_LEN))
    start = (used + FILE_ALIGN_MASK) & ~FILE_ALIGN_MASK
    end = start + len(data)
    if end > len(rom) or any(rom[start:end]):
        raise ValueError("MMZX: no free padding to relocate file %d" % fid)
    rom[start:end] = data
    struct.pack_into("<II", rom, fat + fid * FAT_ENTRY_LEN, start, end)
    struct.pack_into("<I", rom, NDS_HDR_ROM_SIZE, (end + FILE_ALIGN_MASK) & ~FILE_ALIGN_MASK)
    return start


def update_header_crc(rom: bytearray) -> None:
    crc = CRC16_INIT
    for b in bytes(rom[:NDS_HDR_CRC]):
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ CRC16_POLY if crc & 1 else crc >> 1
    struct.pack_into("<H", rom, NDS_HDR_CRC, crc)
