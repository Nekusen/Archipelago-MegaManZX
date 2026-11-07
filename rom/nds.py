"""The ROM container: header fields, the file allocation table, the ARM9 overlays and the header CRC."""

import struct

from ..apnds import lz
from . import blz

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
# ARM9 overlay table entries: id, RAM address, size, bss size, static init start and end,
# file id, then the compressed size with the compressed flag in its high byte
OVERLAY_ENTRY_LEN = 32
OVERLAY_SIZE_OFF = 28
OVERLAY_COMPRESSED = 1 << 24
OVERLAY_SIZE_MASK = 0xFFFFFF


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


def overlay_entry(rom: bytearray, ovl: int) -> int:
    """ROM offset of the overlay's entry in the ARM9 overlay table."""
    table, size = struct.unpack_from("<II", rom, NDS_HDR_OVERLAYS9)
    if (ovl + 1) * OVERLAY_ENTRY_LEN > size:
        raise ValueError("MMZX: no overlay %d in the ROM" % ovl)
    return table + ovl * OVERLAY_ENTRY_LEN


def overlay_code(rom: bytearray, ovl: int) -> tuple[int, bytes]:
    """(RAM address, code) of an overlay, decompressed when the table says it is."""
    entry = overlay_entry(rom, ovl)
    _id, ram, size, _bss, _init0, _init1, fid, comp = struct.unpack_from("<8I", rom, entry)
    data = file_bytes(rom, fid)
    if comp & OVERLAY_COMPRESSED:
        data = lz.decompress_code(data, len(data))[0]
    return ram, bytes(data[:size])


def patch_overlay(rom: bytearray, ovl: int, patches) -> None:
    """Apply (RAM, vanilla, patched) replacements inside an overlay and store it again.

    The new file goes to the free padding after every file, like a relocated
    NitroFS file, and the table entry takes its size.
    """
    entry = overlay_entry(rom, ovl)
    ram, code = overlay_code(rom, ovl)
    fid, comp = struct.unpack_from("<II", rom, entry + OVERLAY_SIZE_OFF - 4)
    buf = bytearray(code)
    for addr, orig, new in patches:
        orig, new = bytes.fromhex(orig) if isinstance(orig, str) else orig, bytes.fromhex(new) if isinstance(new, str) else new
        off = addr - ram
        if not 0 <= off <= len(buf) - len(new):
            raise ValueError("MMZX: 0x%08X is outside overlay %d" % (addr, ovl))
        cur = bytes(buf[off:off + len(new)])
        if cur == new:
            continue
        if cur != orig:
            raise ValueError("MMZX: unexpected bytes at 0x%08X of overlay %d (%s, expected %s). Wrong ROM?"
                             % (addr, ovl, cur.hex(), orig.hex()))
        buf[off:off + len(new)] = new
    packed = bytes(buf)
    if comp & OVERLAY_COMPRESSED:
        packed = blz.compress(packed)
        if packed is None:
            raise ValueError("MMZX: overlay %d did not compress" % ovl)
    relocate_file(rom, fid, packed)
    struct.pack_into("<I", rom, entry + OVERLAY_SIZE_OFF, (comp & ~OVERLAY_SIZE_MASK) | len(packed))


def update_header_crc(rom: bytearray) -> None:
    crc = CRC16_INIT
    for b in bytes(rom[:NDS_HDR_CRC]):
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ CRC16_POLY if crc & 1 else crc >> 1
    struct.pack_into("<H", rom, NDS_HDR_CRC, crc)


OVERLAY_RAM_SIZE_OFF = 8                  # size of the loaded code, then the bss size
OVERLAY_BSS_SIZE_OFF = 12
OVERLAY_CODE_MAX = 25312                  # the largest room overlay of the game: what the room slot is known to hold


def overlay_bss_size(rom: bytearray, ovl: int) -> int:
    """Bytes the loader clears after the overlay's code."""
    return struct.unpack_from("<I", rom, overlay_entry(rom, ovl) + OVERLAY_BSS_SIZE_OFF)[0]


def store_overlay(rom: bytearray, ovl: int, code: bytes, bss_size: int | None = None) -> None:
    """Store a new version of an overlay, which may have grown, and update its table entry.

    A grown overlay reaches into its old bss: the caller appends that many zeros first
    and passes the bss size that is left.
    """
    if len(code) > OVERLAY_CODE_MAX:
        raise ValueError("MMZX: overlay %d would grow to %d bytes, past the room slot" % (ovl, len(code)))
    entry = overlay_entry(rom, ovl)
    fid, comp = struct.unpack_from("<II", rom, entry + OVERLAY_SIZE_OFF - 4)
    packed = bytes(code)
    if comp & OVERLAY_COMPRESSED:
        packed = blz.compress(packed)
        if packed is None:
            raise ValueError("MMZX: overlay %d did not compress" % ovl)
    relocate_file(rom, fid, packed)
    struct.pack_into("<I", rom, entry + OVERLAY_RAM_SIZE_OFF, len(code))
    if bss_size is not None:
        struct.pack_into("<I", rom, entry + OVERLAY_BSS_SIZE_OFF, bss_size)
    struct.pack_into("<I", rom, entry + OVERLAY_SIZE_OFF, (comp & ~OVERLAY_SIZE_MASK) | len(packed))
