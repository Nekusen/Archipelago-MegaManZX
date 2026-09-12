"""The ARM9 image: its sections, checked writes, Thumb `bl` encoding and the slot it goes back into."""

import struct

from ..apnds.code import CodeStartParams, START_INFO_SIGNATURE_DS
from . import blz
from .nds import (NDS_HDR_ARM7, NDS_HDR_ARM9_SIZE, NDS_HDR_BANNER, NDS_HDR_FAT, NDS_HDR_FNT,
                  NDS_HDR_OVERLAYS9, NITROCODE_LEN, NITROCODE_MAGIC)

# Thumb `bl`: two halfwords, each carrying 11 bits of the halfword offset.
THUMB_BL_HIGH = 0xF000
THUMB_BL_LOW = 0xF800
THUMB_BL_OFFSET_MASK = 0x7FF


def thumb_bl(src: int, dst: int) -> bytes:
    """Encode a Thumb `bl dst` placed at src (4 bytes)."""
    off = dst - (src + 4)
    return struct.pack("<HH", THUMB_BL_HIGH | ((off >> 12) & THUMB_BL_OFFSET_MASK),
                       THUMB_BL_LOW | ((off >> 1) & THUMB_BL_OFFSET_MASK))


class Arm9:
    """The decompressed ARM9 as apnds splits it: main code and autoload sections, by RAM address."""

    def __init__(self, code: bytes, ram: int):
        self.ram = ram
        self.params = CodeStartParams.from_code(code, ram)
        if self.params is None or self.params.compressed_end is None:
            raise ValueError("MMZX: ARM9 start parameters not found. Wrong ROM?")
        if code.find(START_INFO_SIGNATURE_DS) >= blz.BLZ_HEADER_LEN:
            raise ValueError("MMZX: ARM9 start parameters outside the uncompressed header")
        split, rem = self.params.get_sections(code, ram)
        if rem:
            raise ValueError("MMZX: unexpected data after the compressed ARM9")
        self.infos = [info for _, info in split]
        self.sections = []               # (RAM address, data) per piece: main code, autoload sections, table
        pos = ram
        for data, info in split:
            self.sections.append((info.destination if info else pos, bytearray(data)))
            pos += len(data)

    def write(self, ram: int, new: bytes, orig: bytes | None = None) -> None:
        """Write `new` at RAM address `ram` after checking the bytes there.

        They must be `orig`, the vanilla bytes, or already `new`; `orig`
        defaults to zeros, what the free stretches that take the caves hold.
        """
        if orig is None:
            orig = bytes(len(new))
        for base, buf in self.sections:
            if base <= ram < base + len(buf):
                off = ram - base
                cur = bytes(buf[off:off + len(new)])
                if cur == new:
                    return  # already patched
                if cur != orig:
                    raise ValueError(
                        "MMZX: unexpected bytes at 0x%08X (%s, expected "
                        "%s). Wrong ROM?" % (ram, cur.hex(), orig.hex()))
                buf[off:off + len(new)] = new
                return
        raise ValueError("MMZX: 0x%08X is outside the ARM9 sections" % ram)

    def pack(self) -> bytes:
        """Recompress into the image the game boots: raw header, BLZ body, start parameters."""
        pieces = [(bytes(buf), info) for (_, buf), info in zip(self.sections, self.infos)]
        packed = self.params.pack_code_from_sections((pieces, b""), self.ram, "9",
                                                     try_compress=False)
        body = blz.compress(packed[blz.BLZ_HEADER_LEN:])
        if body is None:
            raise ValueError("MMZX: the ARM9 did not compress")
        self.params.compressed_end = self.ram + blz.BLZ_HEADER_LEN + len(body)
        return self.params.write_start_info(packed, self.ram)[:blz.BLZ_HEADER_LEN] + body


def replace_arm9(rom: bytearray, arm9_off: int, arm9_len: int, blob: bytes) -> None:
    """Put the recompressed ARM9 back in its slot, the nitrocode footers after it, zeros to the end."""
    post_off = post_end = arm9_off + arm9_len
    while bytes(rom[post_end:post_end + 4]) == NITROCODE_MAGIC:
        post_end += NITROCODE_LEN
    post = bytes(rom[post_off:post_end])
    # the slot ends where the next part of the ROM begins
    others = [struct.unpack_from("<I", rom, o)[0]
              for o in (NDS_HDR_ARM7, NDS_HDR_FNT, NDS_HDR_FAT, NDS_HDR_OVERLAYS9, NDS_HDR_BANNER)]
    slot_end = min(x for x in others if x > arm9_off)
    if len(blob) + len(post) > slot_end - arm9_off:
        raise ValueError(
            "MMZX: the recompressed ARM9 (0x%X+%d) does not fit in its slot "
            "(0x%X)" % (len(blob), len(post), slot_end - arm9_off))
    rom[arm9_off:arm9_off + len(blob)] = blob
    end = arm9_off + len(blob)
    rom[end:end + len(post)] = post
    rom[end + len(post):slot_end] = b"\x00" * (slot_end - end - len(post))
    struct.pack_into("<I", rom, NDS_HDR_ARM9_SIZE, len(blob))
