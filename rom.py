"""ROM patch for Mega Man ZX (USA): ARM9 code patches, the AP icon set and the AP marker."""

import hashlib
import os
import pkgutil
import struct

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

from . import icons
from .apnds.code import CodeStartParams, START_INFO_SIGNATURE_DS
from .data import ICON_SET, NOTIFY_ADDR, PICKUP_MAILBOX_ADDR

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"

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

# AP marker, written by the token step into the zero padding after the header,
# and the option blob (mmzx_cfg.bin inside the .apmmzx) that patch_arm9 reads.
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
AP_MARKER_LEN = 0x80
AP_MARKER_VERSION_OFF = 0x08              # u32 major << 16 | minor << 8 | build
AP_MARKER_SLOT_OFF = 0x10
AP_MARKER_SLOT_MAX = 63                   # bytes of UTF-8, then a NUL
AP_MARKER_SEED_OFF = 0x50
AP_MARKER_SEED_MAX = 31
CFG_HU_IN_POOL = 0x01                     # mmzx_cfg.bin byte 0, bit 0

# Thumb `bl`: two halfwords, each carrying 11 bits of the halfword offset.
THUMB_BL_HIGH = 0xF000
THUMB_BL_LOW = 0xF800
THUMB_BL_OFFSET_MASK = 0x7FF

# Tutorial skip: New Game enters the scene through the LOAD handler, from the
# image the client seeds. The handler also serves the attract demo, so the cave
# checks the game mode (low 16 bits zero) and the title carousel step first.
SKIP_ENTRY_RAM = 0x02022544
SKIP_ENTRY_ORIG = bytes.fromhex("10b5041c00f020fa")
SKIP_ENTRY_NEW = bytes.fromhex("004b184761b40c02")    # jump to SKIP_CAVE_RAM
SKIP_CAVE_RAM = 0x020CB460
SKIP_CAVE = bytes.fromhex(
    "07490968090403d1064a1278062a05d010b5044657f78afa034b1847034b1847"
    "d8e6150270cd14024d2502022d250202")

# OAM drawer guards: two sprite loops exit only through `subs r5,#1; beq`; a zero
# count (frame table overwritten by a boss sheet) sprays RAM. `bls` exits at once.
OAM_LOOP_A_BR_RAM = 0x02009C30
OAM_LOOP_A_BR_ORIG = bytes.fromhex("01d0")   # beq
OAM_LOOP_A_BR_NEW = bytes.fromhex("01d9")    # bls
OAM_LOOP_B_BR_RAM = 0x02009D7C
OAM_LOOP_B_BR_ORIG = bytes.fromhex("01d0")
OAM_LOOP_B_BR_NEW = bytes.fromhex("01d9")

# Yellow Card Key dialogue: the Operator re-grants the key while Troop is
# reported and the key unowned. The key comes from the pool, so skip it for good.
YELLOWKEY_BR_RAM = 0x02093BE4
YELLOWKEY_BR_ORIG = bytes.fromhex("0cd0")   # beq
YELLOWKEY_BR_NEW = bytes.fromhex("0ce0")    # b

# Biometal ownership: the game counts set flags of a per-category list, in vanilla
# the two boss victory bits. The list becomes two free flags set only by the item.
BIOMETAL_CAT_PATCH = {
    # category: (count addr, list addr, half 1 flag, vanilla list[0], half 2 flag, vanilla list[1])
    3: (0x020DE9AF, 0x020DE9CC, 728, 33, 720, 41),   # H
    4: (0x020DE9B0, 0x020DE9BC, 729, 37, 721, 45),   # F
    5: (0x020DE9B1, 0x020DE9E4, 730, 35, 722, 43),   # L
    6: (0x020DE9B2, 0x020DE9F4, 731, 39, 723, 47),   # P
}
BIOMETAL_CAT_COUNT = 2   # vanilla value; checked, not changed

# Life Up / Sub Tank: the capacity byte doubled as the "slot collected" record.
# The pickup now sets the high nibble (bit 4 + slot): spawn gate and detection.
PICKUP_FLAG_PATCH = [
    # (RAM, vanilla, patched)
    (0x02045014, bytes.fromhex("0121"), bytes.fromhex("1021")),          # grant_life_up: set bit 4 + slot
    (0x0204501E, bytes.fromhex("00f005f8"), bytes.fromhex("c046c046")),  # grant_life_up: no +4 max HP
    (0x02044CAA, bytes.fromhex("0124"), bytes.fromhex("1024")),          # grant_sub_tank: set bit 4 + slot
    (0x02044CD4, bytes.fromhex("0a54"), bytes.fromhex("c046")),          # grant_sub_tank: tank contents untouched
    (0x020A3E30, bytes.fromhex("0121"), bytes.fromhex("1021")),          # Life Up spawn gate: bit 4 + slot
    (0x020A3E86, bytes.fromhex("0121"), bytes.fromhex("1021")),          # Sub Tank spawn gate: bit 4 + slot
]

# Pickup mailbox: layout refills respawn and keep no flag, so the cave hooked into
# the refill think reports (subarea, coords index, role) to a ring the client polls.
# The mailbox itself is data.PICKUP_MAILBOX_ADDR, right after the cave.
PICKUP_MAILBOX_HOOK_RAM = 0x020A30A2
PICKUP_MAILBOX_HOOK_ORIG = bytes.fromhex("6cf7b3fd")   # bl animation advance
PICKUP_MAILBOX_HOOK_NEW = bytes.fromhex("28f0fdf9")    # bl PICKUP_MAILBOX_CAVE_RAM
PICKUP_MAILBOX_CAVE_RAM = 0x020CB4A0
PICKUP_MAILBOX_CAVE = bytes.fromhex(
    "10b544f7b3fb94202858c0081dd3c0202858002819d00d490968002915d04a68"
    "aa4201d00968f8e70a891202084800780243287d00040243064b186807240440"
    "a400e41862600130186010bdf48110022882100200b50c02")

# DATA SELECT icons: the save-slot screen tests raw victory bits for H/F/L/P, so
# it ignored the free flags. Read the first-half flag; hide X when not owned.
DATASELECT_ICON_PATCH = [
    # (RAM, vanilla, patched)
    (0x020361FC, bytes.fromhex("2979022001400029"), bytes.fromhex("a96d090e01200140")),   # H
    (0x02036218, bytes.fromhex("2979202001400029"), bytes.fromhex("a96d090e02200140")),   # F
    (0x02036234, bytes.fromhex("2979082001400029"), bytes.fromhex("a96d090e04200140")),   # L
    (0x02036250, bytes.fromhex("2979802001400029"), bytes.fromhex("a96d090e08200140")),   # P
    (0x020361E2, bytes.fromhex("201c0221d9f73dfe"), bytes.fromhex("95f0cdfb64e0c046")),   # X/ZX: bl cave; b end
]
DATASELECT_CAVE_RAM = 0x020CB980
DATASELECT_CAVE = bytes.fromhex(
    "30b5201c022144f76dfae878000603d4a17afe200140a17230bd")

# Go to Transerver: Y on the MISSION tab. Cave A replaces the pad read and raises
# two flags on Y; cave B closes the menu on its flag. The client serves the warp.
MENU_WARP_FLAGS_RAM = 0x020CB9D0    # +0 request (client), +1 close (cave B)
MENU_WARP_CAVE_A_RAM = 0x020CB99C
MENU_WARP_CAVE_A = bytes.fromhex(
    "054a11885388db430b401b0503d5034a012313705370704768270f02d0b90c02")
MENU_WARP_CAVE_B_RAM = 0x020CB438
MENU_WARP_CAVE_B = bytes.fromhex(
    "04494a78002a03d000224a7001207047014b1847d0b90c020d2b0202")
MENU_WARP_HOOKS = [
    # (RAM, vanilla, patched)
    (0x020272B6, bytes.fromhex("1d490988"), bytes.fromhex("a4f071fb")),   # map scroll pad read: bl cave A
    (0x02023240, bytes.fromhex("fff764fc"), bytes.fromhex("a8f0faf8")),   # menu close call: bl cave B
]
MENU_WARP_TEXT_ROM = 0xDFB200        # m_sub_en.bin (NitroFS, uncompressed)
MENU_WARP_TEXT_SHA256 = "86da91168288b97f4ace3c34a86eba342e97e9afec9bb70949110693930c65a0"
MENU_WARP_TEXT_NEW = bytes.fromhex("3900225554544f4e1a274f00544f003452414e5345525645520000")
MENU_WARP_TEXT_OFFS = (0xB14, 0xB4B, 0xB85)   # three variants of the help text

# NOTIFY: the client's text in the game's small non-blocking popup. The cave
# wraps the message tick; it opens the popup when the message system is idle.
# The notice buffer itself is data.NOTIFY_ADDR, right after the cave.
NOTIFY_HOOK_RAM = 0x02021DD4
NOTIFY_HOOK_ORIG = bytes.fromhex("f0f72afb")   # bl message tick
NOTIFY_HOOK_NEW = bytes.fromhex("a9f014fc")    # bl NOTIFY_CAVE_RAM
NOTIFY_CAVE_RAM = 0x020CB600
NOTIFY_CAVE = bytes.fromhex(
    "10b5204c2078002839d01f496078002806d0487e062803d10020207060702ee0"
    "488900282bd18869002828d117480078400824d216480078800820d201206070"
    "2078022804d1a088618846f743fe16e0201d486260884861c889002801d03bf7"
    "61ff0c4846f7bafd0a4846f7f1fc0649087b002801d0012000e00220886146f7"
    "d5fe10bd00b70c02c4027e0202f5140206f51402cc027e02")

# Cutscene skip: START skips a story cutscene only on a replay. The "event seen"
# test becomes a no-op and the cave marks the event seen, as watching it would.
CUTSCENE_SKIP_PATCH = [
    # (RAM, vanilla, patched)
    (0x0201C00C, bytes.fromhex("17d0"), bytes.fromhex("c046")),           # open skippable block: beq -> nop
    (0x0201B1E4, bytes.fromhex("1348417f"), bytes.fromhex("b0f0acf9")),   # START reader: bl CUTSCENE_SKIP_CAVE_RAM
]
CUTSCENE_SKIP_CAVE_RAM = 0x020CB540
CUTSCENE_SKIP_CAVE = bytes.fromhex("10b5034ce0783df76df80248417f10bd00f51402b0f61402")

# AP icon set: pickups are drawn as the item placed there. icons.py builds the set
# (data.ICON_SET) from the player's ROM; it goes into obj_fnt/obj_dat and is made
# resident like set 58. The graphics caves share the zero stretch that ends at
# GFX_CAVES_END; the client's icon table is data.ICON_TABLE_ADDR.
ICON_FNT_FILE_ID, ICON_DAT_FILE_ID = 235, 234     # NitroFS ids of obj_fnt.bin, obj_dat.bin
GFX_CAVES_END = 0x020C8394
ICON_RESIDENT_LIST_PATCH = [
    # (RAM, vanilla, patched)
    (0x020C9C36, bytes.fromhex("0000"), bytes.fromhex("0501")),     # resident list [0, 1, 58] gains 261
    (0x0200BD16, bytes.fromhex("0322"), bytes.fromhex("0422")),     # list length 3 -> 4 (fnt)
    (0x0200BDB6, bytes.fromhex("0322"), bytes.fromhex("0422")),     # list length 3 -> 4 (dat)
]
# The boot cave uploads set 58 and registers set 261 without a palette of its own.
ICON_BOOT_HOOK_RAM = 0x0200BDA8                   # VRAM upload of set 58
ICON_BOOT_HOOK_ORIG = bytes.fromhex("faf7dcf9")
ICON_BOOT_CAVE_RAM = 0x020C8150
ICON_BOOT_CAVE = bytes.fromhex("10b584b000240094019401240294002403940f483a21002200230e4ca04701240094c0460c480d4909680d4a03230d4ca047002400940194012402940024039409480a4900220023094ca04700f074f840571002656100024057100234390f0205010000896a0002405710020501000065610002")

# Icon caves: LOOKUP finds the entity's code in the client's table; ATTACH and
# ANIM replace the graphics calls of the three pickup inits.
ICON_CAVES_RAM = 0x020C81C4
ICON_CAVES = bytes.fromhex("30b5264c2178264a127891421cd16178c90719d023490968002915d04a68824201d00968f8e70a89802a0dd2d3088433e35c07251540eb40db0705d1231d985c002801d0013830bd0020c04330bd30b504000d00fff7d4ff002808dbe17a08229143e172217b0122914321730e4d200029000e4a904730bd30b504000d00428c0b4b9a4204d1fff7bbff002800db050020002900074a904730bd00bf6014190228821002f481100205010000250601020501000065fe0002")
ICON_ATTACH_CAVE_RAM = 0x020C8212
ICON_ANIM_CAVE_RAM = 0x020C823C
# (RAM, vanilla bl); the patched bl is computed from the addresses
ICON_ATTACH_HOOKS = [(0x020A3BC4, bytes.fromhex("6cf72efd")), (0x020A3EEE, bytes.fromhex("6cf799fb")),
                     (0x020A36F4, bytes.fromhex("6cf796ff"))]
ICON_ANIM_HOOKS = [(0x020A3BCC, bytes.fromhex("6cf74af9")), (0x020A3EF6, bytes.fromhex("6bf7b5ff")),
                   (0x020A3706, bytes.fromhex("6cf7adfb"))]

# PALSHARE: set 261 borrows the palette slot of set 58. With a palette of its own,
# rooms using all 15 OBJ palettes would leave the next set unregistered and crash.
PALSHARE_CAVE_RAM = 0x020C8288
PALSHARE_CAVE = bytes.fromhex("03483a21415c0348017004b010bdc046e45e1002e95f1002")

# RETRY: a pickup born during the room load, before the client's table or the
# scouts arrive, keeps its vanilla look; re-attach every frame once a code resolves.
# The refill site belongs to the mailbox cave, so RETRY chains on that cave's call.
ICON_RETRY_CAVE_RAM = 0x020C82A0
ICON_RETRY_CAVE = bytes.fromhex("30b50400628c0e4b9a4214d0fff78aff002810db0500e17a08229143e172217b0122914321732000064948f7abf92000290047f7c7fd200047f798fc30bd00bf0501000005010000")
ICON_RETRY_HOOKS = [(0x020CB4A2, bytes.fromhex("44f7b3fb")), (0x020A3A7E, bytes.fromhex("6cf7c5f8")),
                    (0x020A3CAA, bytes.fromhex("6bf7afff"))]

# Sprite guard: when the registrar rejects a set (palette budget exhausted) ten
# drawers dereference a null slot record and data abort. The cave skips the read.
SPRITEGUARD_CAVE_RAM = 0x020C827C
SPRITEGUARD_CAVE = bytes.fromhex("002800d0408801237047")
SPRITEGUARD_ORIG = bytes.fromhex("40880123")
SPRITEGUARD_SITES = [0x0200F0D4, 0x0200F244, 0x0200F424, 0x0200F85A, 0x0200FA5A,
                     0x0200FC96, 0x0200FFA2, 0x02010236, 0x020104CA, 0x02010756]

# PICKUP_AP: a pickup standing for a multiworld location (the `present` bitmap
# of the icon table) skips its vanilla effect, popup and label; it only chimes.
PICKUP_AP_CAVE_RAM = 0x020CB800
PICKUP_AP_CAVE = bytes.fromhex(
    "10b5104c2178104a1278914217d16178c90714d00d490968002910d04a68824201d00968f8e70a89802a08d2d308a433e35c07211140cb400120184010bd002010bd00bf6014190228821002f48110021a203af743f810bd00b52800fff7d0ff002805d01a203af739f801bc0248004702bc287d00280847ad310a0210b50400fff7beff002803d12000d8f7d5f810bd04202061607a810003484158206980000858a061d4e700bfb0b80e0210b50400fff7a6ff0028cbd124203af70ff802485a2146f707fd10bd2904000010b50400fff796ff0028bbd1182039f7ffff02485a2146f7f7fc10bd2a040000")
PICKUP_AP_ENTRIES = {'apgate': 0, 'ap_tail': 80, 'refill': 88, 'disk': 124, 'lifeup': 172, 'subtank': 204}
# (RAM, vanilla code, cave entry, code kept before the bl, code after it)
PICKUP_AP_HOOKS = [
    (0x020A30F4, bytes.fromhex("287d0028"), "refill", b"", b""),
    (0x020A3ADE, bytes.fromhex("fff7abff"), "disk", b"", b""),
    (0x020A3CD4, bytes.fromhex("242061f701fe39485a216ef7f9fa"), "lifeup", bytes.fromhex("201c"),
     bytes.fromhex("c046") * 4),
    (0x020A3CEE, bytes.fromhex("182061f7f4fd33485a216ef7ecfa"), "subtank", bytes.fromhex("201c"),
     bytes.fromhex("c046") * 4),
]

# Hu gate (hu_in_pool): Hu is always owned because its category has no flag
# list. Pointing the list at a one-flag array makes Hu an item; the count is 1.
HUGATE_LISTS0_RAM = 0x020DEB78
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"
HUGATE_ARRAY_RAM = 0x020CB434
HUGATE_FLAG_INDEX = 136                   # 0x021045DD bit 0, unused by the game

# Secret Disk logo: the disk body tile of set 58 becomes the Archipelago logo of
# the Metroid Zero Mission apworld in the disk's palette; vanilla tile by digest.
DISK_LOGO_FNT_OFF = 0x5620C                       # disk body tile inside obj_fnt.bin
DISK_LOGO_SHA256 = "0cf5040681e341af0f130f438c12989c4747f7b7c531792025e6e8f9d9f8c65c"
DISK_LOGO_NEW = bytes.fromhex(
    "000000f00000009f00f0ff9900cfcc9ff0ccccfcf0ccccfcf0fcfffc005f550f"
    "ff000000990f000099f9ff00991f110ff91111f1f91111f1fff1fff1004f440f"
    "f05555f5f05555f5f05555af005ff5aa00f0ffaa0000f0aa000000af000000f0"
    "f04444f4ff4444f4aa4f44f4aafa440faafaff00aafa0000aa0f0000ff000000")


# Helpers shared by the patches: Thumb encoding, packaged files, sprite set
# containers and the BLZ encoder.

def _thumb_bl(src: int, dst: int) -> bytes:
    """Encode a Thumb `bl dst` placed at src (4 bytes)."""
    off = dst - (src + 4)
    return struct.pack("<HH", THUMB_BL_HIGH | ((off >> 12) & THUMB_BL_OFFSET_MASK),
                       THUMB_BL_LOW | ((off >> 1) & THUMB_BL_OFFSET_MASK))


def _gfx_data(name: str) -> bytes:
    """Bytes of a file in assets/, from a directory or from a zipped .apworld."""
    try:
        data = pkgutil.get_data(__name__.rsplit(".", 1)[0], "assets/" + name)
    except Exception:
        data = None
    if data is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name), "rb") as f:
            data = f.read()
    return data


def _insert_set(blob: bytes, setno: int, block: bytes) -> bytes:
    """Insert `block` as the empty set `setno` of an obj_fnt/obj_dat container."""
    n = struct.unpack_from("<I", blob, 0)[0]
    offs = [struct.unpack_from("<I", blob, 4 + i * 4)[0] for i in range(n + 1)]
    if offs[n] != len(blob):
        raise ValueError("MMZX: unexpected offset table in the sprite set file")
    if offs[setno] != offs[setno + 1]:
        raise ValueError("MMZX: sprite set %d is not empty" % setno)
    block = block + bytes((-len(block)) % 4)
    new = bytearray(blob[:4])
    for i in range(n + 1):
        new += struct.pack("<I", offs[i] + (len(block) if i > setno else 0))
    new += blob[4 + (n + 1) * 4:offs[setno]] + block + blob[offs[setno]:]
    return bytes(new)


# BLZ (DS code compression) with an optimal parse: a greedy encoder leaves no
# room in the ARM9 slot for the caves.
BLZ_HEADER_LEN = 0x4000        # never compressed: secure area and crt0
BLZ_MIN_MATCH = 3
BLZ_MAX_MATCH = 18
BLZ_MAX_DIST = 0x1002          # encoded displacement 0xFFF + 3


def _blz_longest_matches(r):
    """Longest earlier match at every position of `r`, the data reversed.

    Returns (lengths, positions): the longest r[q:q+L], 3 <= L <= 18, that also
    occurs within 0x1002 bytes before q, and its nearest occurrence; 0 = none.
    """
    n = len(r)
    lengths = [0] * n
    where = [0] * n
    rfind = r.rfind
    for q in range(n - BLZ_MIN_MATCH + 1):
        lo = q - BLZ_MAX_DIST
        if lo < 0:
            lo = 0
        p = rfind(r[q:q + BLZ_MIN_MATCH], lo, q)
        if p < 0:
            continue
        best_len, best_pos = BLZ_MIN_MATCH, p
        # A longer match implies the shorter ones: the feasible lengths are a prefix, bisect it.
        low, high = BLZ_MIN_MATCH + 1, min(BLZ_MAX_MATCH, n - q)
        while low <= high:
            mid = (low + high) >> 1
            p = rfind(r[q:q + mid], lo, q)
            if p < 0:
                high = mid - 1
            else:
                best_len, best_pos = mid, p
                low = mid + 1
        lengths[q] = best_len
        where[q] = best_pos
    return lengths, where


def _blz_parse(r, lengths):
    """Token per position (0 = literal, L = reference of L bytes) that minimises the stream.

    A literal costs 9 bits and a reference 17: their bytes plus the flag bit.
    """
    n = len(r)
    cost = [0] * (n + 1)
    pick = [0] * n
    for i in range(n - 1, -1, -1):
        best, tok = cost[i + 1] + 9, 0
        for ln in range(BLZ_MIN_MATCH, lengths[i] + 1):
            c = cost[i + ln] + 17
            if c < best:
                best, tok = c, ln
        cost[i] = best
        pick[i] = tok
    return pick


def _blz_compress(data):
    """BLZ region (raw prefix, backwards stream, footer) for the ARM9 minus its header.

    Returns None if the region would not be smaller than the data.
    """
    r = data[::-1]                       # encode the reversed data forwards
    n = len(r)
    lengths, where = _blz_longest_matches(r)
    pick = _blz_parse(r, lengths)

    # `gain` is how far the in-place decoder is ahead after each token (output
    # minus input, flag bytes included); the stream is cut at its first peak.
    stream = bytearray()
    i = 0
    tokens = 0
    gain = 0
    best_gain = 0
    cut_stream = 0                       # stream bytes kept
    cut_data = 0                         # reversed-data bytes covered by them
    while i < n:
        flag_at = len(stream)
        stream.append(0)
        gain -= 1
        flags = 0
        for bit in range(7, -1, -1):
            if i >= n:
                break
            ln = pick[i]
            if ln:
                disp = i - where[i] - BLZ_MIN_MATCH
                flags |= 1 << bit
                stream.append(((ln - BLZ_MIN_MATCH) << 4) | (disp >> 8))
                stream.append(disp & 0xFF)
                i += ln
                gain += ln - 2
            else:
                stream.append(r[i])
                i += 1
            tokens += 1
            if gain > best_gain:
                best_gain = gain
                cut_stream = len(stream)
                cut_data = i
        stream[flag_at] = flags
    if best_gain <= 0:
        return None

    raw = data[:n - cut_data]            # forward order: the uncut start
    body = bytes(stream[:cut_stream])[::-1]
    padding = (-(len(raw) + len(body))) & 3
    footer_len = 8 + padding
    total = len(raw) + len(body) + footer_len
    if total >= n:
        return None
    return b"".join((
        raw, body, b"\xFF" * padding,
        (len(body) + footer_len).to_bytes(3, "little"),
        bytes([footer_len]),
        (n - total).to_bytes(4, "little"),
    ))


class Arm9:
    """The decompressed ARM9 as apnds splits it: main code and autoload sections, by RAM address."""

    def __init__(self, code: bytes, ram: int):
        self.ram = ram
        self.params = CodeStartParams.from_code(code, ram)
        if self.params is None or self.params.compressed_end is None:
            raise ValueError("MMZX: ARM9 start parameters not found. Wrong ROM?")
        if code.find(START_INFO_SIGNATURE_DS) >= BLZ_HEADER_LEN:
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
        body = _blz_compress(packed[BLZ_HEADER_LEN:])
        if body is None:
            raise ValueError("MMZX: the ARM9 did not compress")
        self.params.compressed_end = self.ram + BLZ_HEADER_LEN + len(body)
        return self.params.write_start_info(packed, self.ram)[:BLZ_HEADER_LEN] + body


# One function per patch, applied in this order by patch_arm9.

def _patch_tutorial_skip(arm9: Arm9) -> None:
    """Send New Game through the LOAD handler, so a slot starts from the image the client seeds."""
    arm9.write(SKIP_ENTRY_RAM, SKIP_ENTRY_NEW, SKIP_ENTRY_ORIG)
    arm9.write(SKIP_CAVE_RAM, SKIP_CAVE)


def _patch_oam_loop_guards(arm9: Arm9) -> None:
    """Make the two OAM sprite loops exit on a zero count instead of spraying RAM."""
    arm9.write(OAM_LOOP_A_BR_RAM, OAM_LOOP_A_BR_NEW, OAM_LOOP_A_BR_ORIG)
    arm9.write(OAM_LOOP_B_BR_RAM, OAM_LOOP_B_BR_NEW, OAM_LOOP_B_BR_ORIG)


def _patch_yellow_key_dialogue(arm9: Arm9) -> None:
    """Stop the Operator from re-granting the Yellow Card Key on every visit."""
    arm9.write(YELLOWKEY_BR_RAM, YELLOWKEY_BR_NEW, YELLOWKEY_BR_ORIG)


def _patch_biometal_ownership(arm9: Arm9) -> None:
    """Own H/F/L/P through two free flags per model, set by its item, instead of the victory bits."""
    for count_ram, list_ram, flag1, orig1, flag2, orig2 in BIOMETAL_CAT_PATCH.values():
        arm9.write(list_ram, flag1.to_bytes(4, "little"), orig1.to_bytes(4, "little"))
        arm9.write(list_ram + 4, flag2.to_bytes(4, "little"), orig2.to_bytes(4, "little"))
        arm9.write(count_ram, bytes([BIOMETAL_CAT_COUNT]), bytes([BIOMETAL_CAT_COUNT]))


def _patch_life_up_sub_tank(arm9: Arm9) -> None:
    """Record a collected Life Up or Sub Tank in the high nibble instead of raising the capacity."""
    for ram, orig, new in PICKUP_FLAG_PATCH:
        arm9.write(ram, new, orig)


def _patch_pickup_mailbox(arm9: Arm9) -> None:
    """Report each collected layout refill (subarea, coords index, role) to the ring the client polls."""
    assert len(PICKUP_MAILBOX_CAVE) <= PICKUP_MAILBOX_ADDR - PICKUP_MAILBOX_CAVE_RAM
    arm9.write(PICKUP_MAILBOX_CAVE_RAM, PICKUP_MAILBOX_CAVE)
    arm9.write(PICKUP_MAILBOX_HOOK_RAM, PICKUP_MAILBOX_HOOK_NEW, PICKUP_MAILBOX_HOOK_ORIG)


def _patch_data_select_icons(arm9: Arm9) -> None:
    """Draw the DATA SELECT biometal icons from the free flags; hide X when the slot does not own it."""
    for ram, orig, new in DATASELECT_ICON_PATCH:
        arm9.write(ram, new, orig)
    arm9.write(DATASELECT_CAVE_RAM, DATASELECT_CAVE)


def _patch_menu_warp(arm9: Arm9) -> None:
    """Y on the MISSION tab raises the warp request flag and closes the menu; the client warps."""
    assert len(MENU_WARP_CAVE_A) <= MENU_WARP_FLAGS_RAM - MENU_WARP_CAVE_A_RAM
    assert len(MENU_WARP_CAVE_B) <= SKIP_CAVE_RAM - MENU_WARP_CAVE_B_RAM
    arm9.write(MENU_WARP_CAVE_A_RAM, MENU_WARP_CAVE_A)
    arm9.write(MENU_WARP_CAVE_B_RAM, MENU_WARP_CAVE_B)
    for ram, orig, new in MENU_WARP_HOOKS:
        arm9.write(ram, new, orig)


def _patch_notify(arm9: Arm9) -> None:
    """Show the client's notices in the game's small popup, from the per-frame message tick."""
    assert len(NOTIFY_CAVE) <= NOTIFY_ADDR - NOTIFY_CAVE_RAM
    arm9.write(NOTIFY_CAVE_RAM, NOTIFY_CAVE)
    arm9.write(NOTIFY_HOOK_RAM, NOTIFY_HOOK_NEW, NOTIFY_HOOK_ORIG)


def _patch_cutscene_skip(arm9: Arm9) -> None:
    """Let START skip every story cutscene; the cave marks the event seen, as watching it would."""
    assert CUTSCENE_SKIP_CAVE_RAM + len(CUTSCENE_SKIP_CAVE) <= NOTIFY_CAVE_RAM
    arm9.write(CUTSCENE_SKIP_CAVE_RAM, CUTSCENE_SKIP_CAVE)
    for ram, orig, new in CUTSCENE_SKIP_PATCH:
        arm9.write(ram, new, orig)


def _patch_icon_set(arm9: Arm9) -> None:
    """Keep the AP icon set resident: a fourth entry in the resident list and its upload at boot."""
    assert ICON_BOOT_CAVE_RAM + len(ICON_BOOT_CAVE) <= ICON_CAVES_RAM
    for ram, orig, new in ICON_RESIDENT_LIST_PATCH:
        arm9.write(ram, new, orig)
    arm9.write(ICON_BOOT_CAVE_RAM, ICON_BOOT_CAVE)
    arm9.write(ICON_BOOT_HOOK_RAM, _thumb_bl(ICON_BOOT_HOOK_RAM, ICON_BOOT_CAVE_RAM), ICON_BOOT_HOOK_ORIG)


def _patch_item_icons(arm9: Arm9) -> None:
    """Draw pickups as the item placed there: LOOKUP, ATTACH and ANIM caves on the three pickup inits."""
    assert ICON_CAVES_RAM + len(ICON_CAVES) <= GFX_CAVES_END
    arm9.write(ICON_CAVES_RAM, ICON_CAVES)
    for ram, orig in ICON_ATTACH_HOOKS:
        arm9.write(ram, _thumb_bl(ram, ICON_ATTACH_CAVE_RAM), orig)
    for ram, orig in ICON_ANIM_HOOKS:
        arm9.write(ram, _thumb_bl(ram, ICON_ANIM_CAVE_RAM), orig)


def _patch_palshare(arm9: Arm9) -> None:
    """Place the cave the boot cave calls to lend set 261 the palette slot of set 58."""
    assert PALSHARE_CAVE_RAM + len(PALSHARE_CAVE) <= GFX_CAVES_END
    arm9.write(PALSHARE_CAVE_RAM, PALSHARE_CAVE)


def _patch_icon_retry(arm9: Arm9) -> None:
    """Re-attach the icon every frame to a pickup born before the client's table arrived."""
    assert ICON_RETRY_CAVE_RAM >= PALSHARE_CAVE_RAM + len(PALSHARE_CAVE)
    assert ICON_RETRY_CAVE_RAM + len(ICON_RETRY_CAVE) <= GFX_CAVES_END
    arm9.write(ICON_RETRY_CAVE_RAM, ICON_RETRY_CAVE)
    for ram, orig in ICON_RETRY_HOOKS:
        arm9.write(ram, _thumb_bl(ram, ICON_RETRY_CAVE_RAM), orig)


def _patch_sprite_guard(arm9: Arm9) -> None:
    """Skip a sprite whose set got no VRAM slot instead of reading through a null record."""
    assert SPRITEGUARD_CAVE_RAM + len(SPRITEGUARD_CAVE) <= GFX_CAVES_END
    assert SPRITEGUARD_CAVE_RAM >= ICON_CAVES_RAM + len(ICON_CAVES)
    arm9.write(SPRITEGUARD_CAVE_RAM, SPRITEGUARD_CAVE)
    for ram in SPRITEGUARD_SITES:
        arm9.write(ram, _thumb_bl(ram, SPRITEGUARD_CAVE_RAM), SPRITEGUARD_ORIG)


def _patch_pickup_ap(arm9: Arm9) -> None:
    """Make a pickup that stands for a multiworld location skip its vanilla effect; it only chimes."""
    assert PICKUP_AP_CAVE_RAM + len(PICKUP_AP_CAVE) <= DATASELECT_CAVE_RAM
    arm9.write(PICKUP_AP_CAVE_RAM, PICKUP_AP_CAVE)
    for ram, orig, entry, pre, post in PICKUP_AP_HOOKS:
        new = pre + _thumb_bl(ram + len(pre), PICKUP_AP_CAVE_RAM + PICKUP_AP_ENTRIES[entry]) + post
        assert len(new) == len(orig)
        arm9.write(ram, new, orig)


def _patch_hu_gate(arm9: Arm9, hu_in_pool: bool) -> None:
    """With hu_in_pool, make Model Hu an item: category 0 counts a single free flag."""
    if not hu_in_pool:
        return
    arm9.write(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
    arm9.write(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"), HUGATE_LISTS0_ORIG)


# ROM-level steps that follow the ARM9.

def _replace_arm9(rom: bytearray, arm9_off: int, arm9_len: int, blob: bytes) -> None:
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


def _install_icon_set(d: bytearray) -> int:
    """Insert the AP icon set into obj_dat/obj_fnt and relocate both files to the end padding.

    Returns the new ROM offset of obj_fnt.bin.
    """
    fat = struct.unpack_from("<I", d, NDS_HDR_FAT)[0]
    fatsize = struct.unpack_from("<I", d, NDS_HDR_FAT_SIZE)[0]
    used = max(struct.unpack_from("<II", d, fat + k * FAT_ENTRY_LEN)[1]
               for k in range(fatsize // FAT_ENTRY_LEN))
    cur = (used + FILE_ALIGN_MASK) & ~FILE_ALIGN_MASK
    files = {}
    for fid in (ICON_DAT_FILE_ID, ICON_FNT_FILE_ID):
        s0, e0 = struct.unpack_from("<II", d, fat + fid * FAT_ENTRY_LEN)
        files[fid] = bytes(d[s0:e0])
    fnt_block, dat_block = icons.build_icon_set(files[ICON_FNT_FILE_ID], files[ICON_DAT_FILE_ID], _gfx_data)
    fnt_start = None
    for fid, block in ((ICON_DAT_FILE_ID, dat_block), (ICON_FNT_FILE_ID, fnt_block)):
        newfile = _insert_set(files[fid], ICON_SET, block)
        if cur + len(newfile) > len(d) or any(d[cur:cur + len(newfile)]):
            raise ValueError("MMZX: no free padding to relocate file %d" % fid)
        d[cur:cur + len(newfile)] = newfile
        struct.pack_into("<II", d, fat + fid * FAT_ENTRY_LEN, cur, cur + len(newfile))
        if fid == ICON_FNT_FILE_ID:
            fnt_start = cur
        cur = (cur + len(newfile) + FILE_ALIGN_MASK) & ~FILE_ALIGN_MASK
    struct.pack_into("<I", d, NDS_HDR_ROM_SIZE, cur)
    return fnt_start


def _patch_menu_warp_text(rom: bytearray) -> None:
    """Replace the three MISSION tab help texts in m_sub_en.bin, in place and of the same length."""
    for off in MENU_WARP_TEXT_OFFS:
        o = MENU_WARP_TEXT_ROM + off
        cur = bytes(rom[o:o + len(MENU_WARP_TEXT_NEW)])
        if cur == MENU_WARP_TEXT_NEW:
            continue
        if hashlib.sha256(cur).hexdigest() != MENU_WARP_TEXT_SHA256:
            raise ValueError("MMZX: unexpected text at m_sub_en.bin+0x%X (%s)" % (off, cur.hex()))
        rom[o:o + len(MENU_WARP_TEXT_NEW)] = MENU_WARP_TEXT_NEW


def _patch_disk_logo(rom: bytearray, fnt_start: int) -> None:
    """Replace the Secret Disk body tile of set 58, inside the relocated obj_fnt.bin, with the AP logo."""
    logo_off = fnt_start + DISK_LOGO_FNT_OFF
    cur = bytes(rom[logo_off:logo_off + len(DISK_LOGO_NEW)])
    if cur == DISK_LOGO_NEW:
        return
    if hashlib.sha256(cur).hexdigest() != DISK_LOGO_SHA256:
        raise ValueError("MMZX: unexpected disk tile at ROM 0x%X (%s)" % (logo_off, cur[:8].hex()))
    rom[logo_off:logo_off + len(DISK_LOGO_NEW)] = DISK_LOGO_NEW


def _update_header_crc(rom: bytearray) -> None:
    """Recompute the CRC-16 of the header."""
    crc = CRC16_INIT
    for b in bytes(rom[:NDS_HDR_CRC]):
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ CRC16_POLY if crc & 1 else crc >> 1
    struct.pack_into("<H", rom, NDS_HDR_CRC, crc)


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Apply the code patches to the ARM9 and the ROM-level edits; returns the new image."""
        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        d = bytearray(rom)
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", d, NDS_HDR_ARM9)
        arm9 = Arm9(bytes(d[arm9_off:arm9_off + arm9_len]), arm9_ram)

        _patch_tutorial_skip(arm9)
        _patch_oam_loop_guards(arm9)
        _patch_yellow_key_dialogue(arm9)
        _patch_biometal_ownership(arm9)
        _patch_life_up_sub_tank(arm9)
        _patch_pickup_mailbox(arm9)
        _patch_data_select_icons(arm9)
        _patch_menu_warp(arm9)
        _patch_notify(arm9)
        _patch_cutscene_skip(arm9)
        _patch_icon_set(arm9)
        _patch_item_icons(arm9)
        _patch_palshare(arm9)
        _patch_icon_retry(arm9)
        _patch_sprite_guard(arm9)
        _patch_pickup_ap(arm9)
        _patch_hu_gate(arm9, hu_in_pool)

        # Recompress into the original slot; a rebuilt ROM shifts the layout (melonDS: bad_alloc)
        _replace_arm9(d, arm9_off, arm9_len, arm9.pack())
        fnt_start = _install_icon_set(d)
        _patch_menu_warp_text(d)
        _patch_disk_logo(d, fnt_start)
        _update_header_crc(d)
        return bytes(d)


class MMZXPatch(APProcedurePatch, APTokenMixin):
    """The .apmmzx patch: the ARM9 and ROM edits of patch_arm9, then the AP marker."""
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    procedure = [
        ("patch_arm9", ["mmzx_cfg.bin"]),
        ("apply_tokens", ["token_data.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(get_settings().mmzx_settings.rom_file, "rb") as f:
            return f.read()


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str,
                       world_version: tuple[int, int, int], hu_in_pool: bool = False) -> None:
    """Write the AP marker (magic, version, slot, seed) and the option blob read by patch_arm9.

    `world_version` is the world's (major, minor, build), as the core reads it
    from archipelago.json.
    """
    blob = bytearray(AP_MARKER_LEN)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    major, minor, build = world_version
    version = major << 16 | minor << 8 | build
    blob[AP_MARKER_VERSION_OFF:AP_MARKER_VERSION_OFF + 4] = version.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:AP_MARKER_SLOT_MAX]
    blob[AP_MARKER_SLOT_OFF:AP_MARKER_SLOT_OFF + len(name)] = name
    seed = seed_name.encode("utf-8")[:AP_MARKER_SEED_MAX]
    blob[AP_MARKER_SEED_OFF:AP_MARKER_SEED_OFF + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
    # option flags for patch_arm9, which runs before apply_tokens
    cfg = bytearray(4)
    cfg[0] = CFG_HU_IN_POOL if hu_in_pool else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
