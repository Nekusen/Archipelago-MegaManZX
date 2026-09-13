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


def update_header_crc(rom: bytearray) -> None:
    crc = CRC16_INIT
    for b in bytes(rom[:NDS_HDR_CRC]):
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ CRC16_POLY if crc & 1 else crc >> 1
    struct.pack_into("<H", rom, NDS_HDR_CRC, crc)
