"""ROM patch for Mega Man ZX (USA): ARM9 code patches, the AP icon set and the AP marker.

Each patch is described in docs/rom_patches.md; the addresses and the layouts
of the blocks the client shares with the ROM are in docs/memory_map.md.
"""

import hashlib

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"
AP_MAGIC_OFFSET = 0x1000                  # zero padding after the NDS header
AP_MAGIC = b"MZXAP\x00"
WORLD_VERSION_INT = 1

# Tutorial skip: New Game enters the scene through the LOAD handler, from the
# image the client seeds. The handler also serves the attract demo, so the cave
# checks the game mode (low 16 bits zero) and the title carousel step first.
SKIP_ENTRY_RAM = 0x02022544
SKIP_ENTRY = bytes.fromhex("004b184761b40c02")        # jump to SKIP_CAVE_RAM
SKIP_ENTRY_ORIG = bytes.fromhex("10b5041c00f020fa")
SKIP_CAVE_RAM = 0x020CB460
SKIP_CAVE = bytes.fromhex(
    "07490968090403d1064a1278062a05d010b5044657f78afa034b1847034b1847"
    "d8e6150270cd14024d2502022d250202")

# Hu gate (hu_in_pool): Hu is always owned because its category has no flag
# list. Pointing the list at a one-flag array makes Hu an item; the count is 1.
HUGATE_LISTS0_RAM = 0x020DEB78
HUGATE_ARRAY_RAM = 0x020CB434
HUGATE_FLAG_INDEX = 136                   # 0x021045DD bit 0, unused by the game
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"

CFG_HU_IN_POOL = 0x01                     # mmzx_cfg.bin byte 0, bit 0

# Yellow Card Key dialogue: the Operator re-grants the key while Troop is
# reported and the key unowned. The key comes from the pool, so skip it for good.
YELLOWKEY_BR_RAM = 0x02093BE4
YELLOWKEY_BR_ORIG = bytes.fromhex("0cd0")   # beq
YELLOWKEY_BR_NEW = bytes.fromhex("0ce0")    # b

# OAM drawer guards: two sprite loops exit only through `subs r5,#1; beq`; a zero
# count (frame table overwritten by a boss sheet) sprays RAM. `bls` exits at once.
OAMLOOP_BR_RAM = 0x02009C30
OAMLOOP_BR_ORIG = bytes.fromhex("01d0")   # beq
OAMLOOP_BR_NEW = bytes.fromhex("01d9")    # bls
OAMLOOP2_BR_RAM = 0x02009D7C
OAMLOOP2_BR_ORIG = bytes.fromhex("01d0")
OAMLOOP2_BR_NEW = bytes.fromhex("01d9")

# Sprite guard: when the registrar rejects a set (palette budget exhausted) ten
# drawers dereference a null slot record and data abort. The cave skips the read.
SPRITEGUARD_CAVE_RAM = 0x020C827C
SPRITEGUARD_CAVE = bytes.fromhex("002800d0408801237047")
SPRITEGUARD_ORIG = bytes.fromhex("40880123")
SPRITEGUARD_SITES = [0x0200F0D4, 0x0200F244, 0x0200F424, 0x0200F85A, 0x0200FA5A,
                     0x0200FC96, 0x0200FFA2, 0x02010236, 0x020104CA, 0x02010756]


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
    (0x02045014, "0121", "1021"),          # grant_life_up: set bit 4 + slot
    (0x0204501E, "00f005f8", "c046c046"),  # grant_life_up: no +4 max HP
    (0x02044CAA, "0124", "1024"),          # grant_sub_tank: set bit 4 + slot
    (0x02044CD4, "0a54", "c046"),          # grant_sub_tank: tank contents untouched
    (0x020A3E30, "0121", "1021"),          # Life Up spawn gate: bit 4 + slot
    (0x020A3E86, "0121", "1021"),          # Sub Tank spawn gate: bit 4 + slot
]


# Pickup mailbox: layout refills respawn and keep no flag, so the cave hooked into
# the refill think reports (subarea, coords index, role) to a ring the client polls.
PICKUP_MAILBOX_HOOK_RAM = 0x020A30A2
PICKUP_MAILBOX_HOOK_ORIG = bytes.fromhex("6cf7b3fd")   # bl animation advance
PICKUP_MAILBOX_HOOK_NEW = bytes.fromhex("28f0fdf9")    # bl PICKUP_MAILBOX_CAVE_RAM
PICKUP_MAILBOX_CAVE_RAM = 0x020CB4A0
PICKUP_MAILBOX_CAVE = bytes.fromhex(
    "10b544f7b3fb94202858c0081dd3c0202858002819d00d490968002915d04a68"
    "aa4201d00968f8e70a891202084800780243287d00040243064b186807240440"
    "a400e41862600130186010bdf48110022882100200b50c02")
PICKUP_MAILBOX_RAM = 0x020CB500          # = data.PICKUP_MAILBOX_ADDR
PICKUP_MAILBOX_SLOTS = 8

# NOTIFY: the client's text in the game's small non-blocking popup. The cave
# wraps the message tick; it opens the popup when the message system is idle.
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
NOTIFY_RAM = 0x020CB700        # = data.NOTIFY_ADDR
NOTIFY_BUF_MAX = 0xFC
NOTIFY_POPUP_GLYPHS = 30       # one popup line

# PICKUP_AP: a pickup standing for a multiworld location (the `present` bitmap
# of the icon table) skips its vanilla effect, popup and label; it only chimes.
PICKUP_AP_CAVE_RAM = 0x020CB800
PICKUP_AP_CAVE = bytes.fromhex(
    "10b5104c2178104a1278914217d16178c90714d00d490968002910d04a68824201d00968f8e70a89802a08d2d308a433e35c07211140cb400120184010bd002010bd00bf6014190228821002f48110021a203af743f810bd00b52800fff7d0ff002805d01a203af739f801bc0248004702bc287d00280847ad310a0210b50400fff7beff002803d12000d8f7d5f810bd04202061607a810003484158206980000858a061d4e700bfb0b80e0210b50400fff7a6ff0028cbd124203af70ff802485a2146f707fd10bd2904000010b50400fff796ff0028bbd1182039f7ffff02485a2146f7f7fc10bd2a040000")
PICKUP_AP_ENTRIES = {'apgate': 0, 'ap_tail': 80, 'refill': 88, 'disk': 124, 'lifeup': 172, 'subtank': 204}
# (RAM, vanilla code, cave entry, code kept before the bl, code after it)
PICKUP_AP_HOOKS = [
    (0x020A30F4, "287d0028", "refill", "", ""),
    (0x020A3ADE, "fff7abff", "disk", "", ""),
    (0x020A3CD4, "242061f701fe39485a216ef7f9fa", "lifeup", "201c", "c046" * 4),
    (0x020A3CEE, "182061f7f4fd33485a216ef7ecfa", "subtank", "201c", "c046" * 4),
]
ICON_TABLE_PRESENT_OFF = 0xA4            # `present` bitmap read by the gate

# Cutscene skip: START skips a story cutscene only on a replay. The "event seen"
# test becomes a no-op and the cave marks the event seen, as watching it would.
CUTSCENE_SKIP_PATCH = [
    (0x0201C00C, "17d0", "c046"),           # open skippable block: beq -> nop
    (0x0201B1E4, "1348417f", "b0f0acf9"),   # START reader: bl CUTSCENE_SKIP_CAVE_RAM
]
CUTSCENE_SKIP_CAVE_RAM = 0x020CB540
CUTSCENE_SKIP_CAVE = bytes.fromhex("10b5034ce0783df76df80248417f10bd00f51402b0f61402")

# DATA SELECT icons: the save-slot screen tests raw victory bits for H/F/L/P, so
# it ignored the free flags. Read the first-half flag; hide X when not owned.
DATASELECT_ICON_PATCH = [
    (0x020361FC, "2979022001400029", "a96d090e01200140"),   # H
    (0x02036218, "2979202001400029", "a96d090e02200140"),   # F
    (0x02036234, "2979082001400029", "a96d090e04200140"),   # L
    (0x02036250, "2979802001400029", "a96d090e08200140"),   # P
    (0x020361E2, "201c0221d9f73dfe", "95f0cdfb64e0c046"),   # X/ZX: bl cave; b end
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
    (0x020272B6, "1d490988", "a4f071fb"),   # map scroll pad read: bl cave A
    (0x02023240, "fff764fc", "a8f0faf8"),   # menu close call: bl cave B
]
MENU_WARP_TEXT_ROM = 0xDFB200        # m_sub_en.bin (NitroFS, uncompressed)
MENU_WARP_TEXT_SHA256 = "86da91168288b97f4ace3c34a86eba342e97e9afec9bb70949110693930c65a0"
MENU_WARP_TEXT_NEW = bytes.fromhex("3900225554544f4e1a274f00544f003452414e5345525645520000")
MENU_WARP_TEXT_OFFS = (0xB14, 0xB4B, 0xB85)   # three variants of the help text

# Secret Disk logo: the disk body tile of set 58 becomes the Archipelago logo of
# the Metroid Zero Mission apworld in the disk's palette; vanilla tile by digest.
DISK_LOGO_ROM = 0x00F5F20C   # vanilla offset; patched through DISK_LOGO_FNT_OFF
DISK_LOGO_SHA256 = "0cf5040681e341af0f130f438c12989c4747f7b7c531792025e6e8f9d9f8c65c"
DISK_LOGO_NEW = bytes.fromhex(
    "000000f00000009f00f0ff9900cfcc9ff0ccccfcf0ccccfcf0fcfffc005f550f"
    "ff000000990f000099f9ff00991f110ff91111f1f91111f1fff1fff1004f440f"
    "f05555f5f05555f5f05555af005ff5aa00f0ffaa0000f0aa000000af000000f0"
    "f04444f4ff4444f4aa4f44f4aafa440faafaff00aafa0000aa0f0000ff000000")


# AP icon set: pickups are drawn as the item placed there. icons.py builds set 261
# from the player's ROM; it goes into obj_fnt/obj_dat and is made resident like set 58.
ICON_SET = 261
ICON_FNT_FILE_ID, ICON_DAT_FILE_ID = 235, 234     # NitroFS ids of obj_fnt.bin, obj_dat.bin
DISK_LOGO_FNT_OFF = 0x5620C                       # disk body tile inside obj_fnt.bin
ICON_TABLE_RAM = 0x02191460                       # = data.ICON_TABLE_ADDR, written by the client
ICON_TABLE_SIZE = 0xC4
ICON_RESIDENT_LIST_PATCH = [
    (0x020C9C36, "0000", "0501"),     # resident list [0, 1, 58] gains 261
    (0x0200BD16, "0322", "0422"),     # list length 3 -> 4 (fnt)
    (0x0200BDB6, "0322", "0422"),     # list length 3 -> 4 (dat)
]
ICON_BOOT_HOOK_RAM = 0x0200BDA8                   # VRAM upload of set 58
ICON_BOOT_HOOK_ORIG = "faf7dcf9"
# The boot cave uploads set 58 and registers set 261 without a palette of its own.
ICON_BOOT_CAVE_RAM = 0x020C8150
ICON_BOOT_CAVE = bytes.fromhex("10b584b000240094019401240294002403940f483a21002200230e4ca04701240094c0460c480d4909680d4a03230d4ca047002400940194012402940024039409480a4900220023094ca04700f074f840571002656100024057100234390f0205010000896a0002405710020501000065610002")
# PALSHARE: set 261 borrows the palette slot of set 58. With a palette of its own,
# rooms using all 15 OBJ palettes would leave the next set unregistered and crash.
PALSHARE_CAVE_RAM = 0x020C8288
PALSHARE_CAVE = bytes.fromhex("03483a21415c0348017004b010bdc046e45e1002e95f1002")
# RETRY: a pickup born during the room load, before the client's table or the
# scouts arrive, keeps its vanilla look; re-attach every frame once a code resolves.
ICON_RETRY_CAVE_RAM = 0x020C82A0
ICON_RETRY_CAVE = bytes.fromhex("30b50400628c0e4b9a4214d0fff78aff002810db0500e17a08229143e172217b0122914321732000064948f7abf92000290047f7c7fd200047f798fc30bd00bf0501000005010000")
# The refill site belongs to the mailbox cave, so RETRY chains on that cave's call.
ICON_RETRY_HOOKS = [(0x020CB4A2, "44f7b3fb"), (0x020A3A7E, "6cf7c5f8"), (0x020A3CAA, "6bf7afff")]
# Icon caves: LOOKUP finds the entity's code in the client's table; ATTACH and
# ANIM replace the graphics calls of the three pickup inits.
ICON_CAVES_RAM = 0x020C81C4
ICON_CAVES = bytes.fromhex("30b5264c2178264a127891421cd16178c90719d023490968002915d04a68824201d00968f8e70a89802a0dd2d3088433e35c07251540eb40db0705d1231d985c002801d0013830bd0020c04330bd30b504000d00fff7d4ff002808dbe17a08229143e172217b0122914321730e4d200029000e4a904730bd30b504000d00428c0b4b9a4204d1fff7bbff002800db050020002900074a904730bd00bf6014190228821002f481100205010000250601020501000065fe0002")
ICON_ATTACH_CAVE_RAM = 0x020C8212
ICON_ANIM_CAVE_RAM = 0x020C823C
ICON_ATTACH_HOOKS = [(0x020A3BC4, "6cf72efd"), (0x020A3EEE, "6cf799fb"), (0x020A36F4, "6cf796ff")]
ICON_ANIM_HOOKS = [(0x020A3BCC, "6cf74af9"), (0x020A3EF6, "6bf7b5ff"), (0x020A3706, "6cf7adfb")]


def _thumb_bl(src: int, dst: int) -> bytes:
    """Encode a Thumb `bl dst` placed at src (4 bytes)."""
    import struct
    off = dst - (src + 4)
    return struct.pack("<HH", 0xF000 | ((off >> 12) & 0x7FF), 0xF800 | ((off >> 1) & 0x7FF))


def _gfx_data(name: str) -> bytes:
    """Bytes of a file in gfx/, from a directory or from a zipped .apworld."""
    import os
    import pkgutil
    try:
        data = pkgutil.get_data(__name__.rsplit(".", 1)[0], "gfx/" + name)
    except Exception:
        data = None
    if data is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gfx", name), "rb") as f:
            data = f.read()
    return data


def _insert_set(blob: bytes, setno: int, block: bytes) -> bytes:
    """Insert `block` as the empty set `setno` of an obj_fnt/obj_dat container."""
    import struct
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


def _install_icon_set(d: bytearray) -> int:
    """Insert the AP icon set into obj_dat/obj_fnt and relocate both files to the end padding.

    Returns the new ROM offset of obj_fnt.bin.
    """
    import struct

    from . import icons
    fat = struct.unpack_from("<I", d, 0x48)[0]
    fatsize = struct.unpack_from("<I", d, 0x4C)[0]
    used = max(struct.unpack_from("<II", d, fat + k * 8)[1] for k in range(fatsize // 8))
    cur = (used + 0x1FF) & ~0x1FF
    files = {}
    for fid in (ICON_DAT_FILE_ID, ICON_FNT_FILE_ID):
        s0, e0 = struct.unpack_from("<II", d, fat + fid * 8)
        files[fid] = bytes(d[s0:e0])
    fnt_block, dat_block = icons.build_icon_set(files[ICON_FNT_FILE_ID], files[ICON_DAT_FILE_ID], _gfx_data)
    fnt_start = None
    for fid, block in ((ICON_DAT_FILE_ID, dat_block), (ICON_FNT_FILE_ID, fnt_block)):
        newfile = _insert_set(files[fid], ICON_SET, block)
        if cur + len(newfile) > len(d) or any(d[cur:cur + len(newfile)]):
            raise ValueError("MMZX: no free padding to relocate file %d" % fid)
        d[cur:cur + len(newfile)] = newfile
        struct.pack_into("<II", d, fat + fid * 8, cur, cur + len(newfile))
        if fid == ICON_FNT_FILE_ID:
            fnt_start = cur
        cur = (cur + len(newfile) + 0x1FF) & ~0x1FF
    struct.pack_into("<I", d, 0x80, cur)          # "used ROM size"
    return fnt_start

# BLZ (DS code compression) with an optimal parse: a greedy encoder leaves no
# room in the ARM9 slot for the caves. Format in docs/rom_patches.md.
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


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Apply the code patches to the ARM9 and the ROM-level edits; returns the new image."""
        import struct

        from .apnds.code import CodeStartParams, START_INFO_SIGNATURE_DS

        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        d = bytearray(rom)
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", d, 0x20)
        code = bytes(d[arm9_off:arm9_off + arm9_len])
        params = CodeStartParams.from_code(code, arm9_ram)
        if params is None or params.compressed_end is None:
            raise ValueError("MMZX: ARM9 start parameters not found. Wrong ROM?")
        if code.find(START_INFO_SIGNATURE_DS) >= BLZ_HEADER_LEN:
            raise ValueError("MMZX: ARM9 start parameters outside the uncompressed header")
        split, rem = params.get_sections(code, arm9_ram)
        if rem:
            raise ValueError("MMZX: unexpected data after the compressed ARM9")
        # (RAM address, data) per piece: main code, autoload sections, autoload table
        sections = []
        pos = arm9_ram
        for data, info in split:
            sections.append((info.destination if info else pos, bytearray(data)))
            pos += len(data)

        def poke(ram, data, orig=None):
            for base, buf in sections:
                if base <= ram < base + len(buf):
                    off = ram - base
                    cur = bytes(buf[off:off + len(data)])
                    if cur == data:
                        return  # already patched
                    if orig is not None and cur != orig:
                        raise ValueError(
                            "MMZX: unexpected bytes at 0x%08X (%s, expected "
                            "%s). Wrong ROM?" % (ram, cur.hex(), orig.hex()))
                    buf[off:off + len(data)] = data
                    return
            raise ValueError("MMZX: 0x%08X is outside the ARM9 sections" % ram)

        # Tutorial skip
        poke(SKIP_ENTRY_RAM, SKIP_ENTRY, SKIP_ENTRY_ORIG)
        poke(SKIP_CAVE_RAM, SKIP_CAVE)
        # OAM drawer guards
        poke(OAMLOOP_BR_RAM, OAMLOOP_BR_NEW, OAMLOOP_BR_ORIG)
        poke(OAMLOOP2_BR_RAM, OAMLOOP2_BR_NEW, OAMLOOP2_BR_ORIG)
        # Yellow Card Key dialogue
        poke(YELLOWKEY_BR_RAM, YELLOWKEY_BR_NEW, YELLOWKEY_BR_ORIG)
        # Biometal ownership through free flags
        for cnt_a, lst_a, flag1, orig1, flag2, orig2 in BIOMETAL_CAT_PATCH.values():
            poke(lst_a, flag1.to_bytes(4, "little"), orig1.to_bytes(4, "little"))
            poke(lst_a + 4, flag2.to_bytes(4, "little"), orig2.to_bytes(4, "little"))
            poke(cnt_a, bytes([BIOMETAL_CAT_COUNT]), bytes([BIOMETAL_CAT_COUNT]))
        # Life Up / Sub Tank: collected versus capacity
        for ram, orig, new in PICKUP_FLAG_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # Pickup mailbox
        assert len(PICKUP_MAILBOX_CAVE) <= PICKUP_MAILBOX_RAM - PICKUP_MAILBOX_CAVE_RAM
        poke(PICKUP_MAILBOX_CAVE_RAM, PICKUP_MAILBOX_CAVE,
             bytes(len(PICKUP_MAILBOX_CAVE)))
        poke(PICKUP_MAILBOX_HOOK_RAM, PICKUP_MAILBOX_HOOK_NEW, PICKUP_MAILBOX_HOOK_ORIG)
        # DATA SELECT biometal icons
        for ram, orig, new in DATASELECT_ICON_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        poke(DATASELECT_CAVE_RAM, DATASELECT_CAVE, bytes(len(DATASELECT_CAVE)))
        # Go to Transerver from the pause menu
        assert len(MENU_WARP_CAVE_A) <= MENU_WARP_FLAGS_RAM - MENU_WARP_CAVE_A_RAM
        assert len(MENU_WARP_CAVE_B) <= SKIP_CAVE_RAM - MENU_WARP_CAVE_B_RAM
        poke(MENU_WARP_CAVE_A_RAM, MENU_WARP_CAVE_A, bytes(len(MENU_WARP_CAVE_A)))
        poke(MENU_WARP_CAVE_B_RAM, MENU_WARP_CAVE_B, bytes(len(MENU_WARP_CAVE_B)))
        for ram, orig, new in MENU_WARP_HOOKS:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # NOTIFY
        assert len(NOTIFY_CAVE) <= NOTIFY_RAM - NOTIFY_CAVE_RAM
        poke(NOTIFY_CAVE_RAM, NOTIFY_CAVE, bytes(len(NOTIFY_CAVE)))
        poke(NOTIFY_HOOK_RAM, NOTIFY_HOOK_NEW, NOTIFY_HOOK_ORIG)
        # Cutscene skip
        assert CUTSCENE_SKIP_CAVE_RAM + len(CUTSCENE_SKIP_CAVE) <= NOTIFY_CAVE_RAM
        poke(CUTSCENE_SKIP_CAVE_RAM, CUTSCENE_SKIP_CAVE, bytes(len(CUTSCENE_SKIP_CAVE)))
        for ram, orig, new in CUTSCENE_SKIP_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # AP icon set: resident set, boot cave, icon caves, PALSHARE, RETRY
        for ram, orig, new in ICON_RESIDENT_LIST_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        assert ICON_BOOT_CAVE_RAM + len(ICON_BOOT_CAVE) <= ICON_CAVES_RAM
        assert ICON_CAVES_RAM + len(ICON_CAVES) <= 0x020C8394
        poke(ICON_BOOT_CAVE_RAM, ICON_BOOT_CAVE, bytes(len(ICON_BOOT_CAVE)))
        poke(ICON_BOOT_HOOK_RAM, _thumb_bl(ICON_BOOT_HOOK_RAM, ICON_BOOT_CAVE_RAM),
             bytes.fromhex(ICON_BOOT_HOOK_ORIG))
        poke(ICON_CAVES_RAM, ICON_CAVES, bytes(len(ICON_CAVES)))
        assert PALSHARE_CAVE_RAM + len(PALSHARE_CAVE) <= 0x020C8394
        poke(PALSHARE_CAVE_RAM, PALSHARE_CAVE, bytes(len(PALSHARE_CAVE)))
        assert ICON_RETRY_CAVE_RAM >= PALSHARE_CAVE_RAM + len(PALSHARE_CAVE)
        assert ICON_RETRY_CAVE_RAM + len(ICON_RETRY_CAVE) <= 0x020C8394
        poke(ICON_RETRY_CAVE_RAM, ICON_RETRY_CAVE, bytes(len(ICON_RETRY_CAVE)))
        for ram, orig in ICON_RETRY_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_RETRY_CAVE_RAM), bytes.fromhex(orig))
        for ram, orig in ICON_ATTACH_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_ATTACH_CAVE_RAM), bytes.fromhex(orig))
        for ram, orig in ICON_ANIM_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_ANIM_CAVE_RAM), bytes.fromhex(orig))

        # Sprite guard
        assert SPRITEGUARD_CAVE_RAM + len(SPRITEGUARD_CAVE) <= 0x020C8394
        assert SPRITEGUARD_CAVE_RAM >= ICON_CAVES_RAM + len(ICON_CAVES)
        poke(SPRITEGUARD_CAVE_RAM, SPRITEGUARD_CAVE, bytes(len(SPRITEGUARD_CAVE)))
        for ram in SPRITEGUARD_SITES:
            poke(ram, _thumb_bl(ram, SPRITEGUARD_CAVE_RAM), SPRITEGUARD_ORIG)
        # PICKUP_AP
        assert PICKUP_AP_CAVE_RAM + len(PICKUP_AP_CAVE) <= DATASELECT_CAVE_RAM
        poke(PICKUP_AP_CAVE_RAM, PICKUP_AP_CAVE, bytes(len(PICKUP_AP_CAVE)))
        for ram, orig, entry, pre, post in PICKUP_AP_HOOKS:
            new = (bytes.fromhex(pre) + _thumb_bl(ram + len(pre) // 2, PICKUP_AP_CAVE_RAM + PICKUP_AP_ENTRIES[entry])
                   + bytes.fromhex(post))
            assert len(new) == len(orig) // 2
            poke(ram, new, bytes.fromhex(orig))
        # Hu gate (optional)
        if hu_in_pool:
            poke(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
            poke(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"),
                 HUGATE_LISTS0_ORIG)

        # Recompress into the original slot; a rebuilt ROM shifts the layout (melonDS: bad_alloc)
        pieces = [(bytes(buf), info) for (_, buf), (_, info) in zip(sections, split)]
        packed = params.pack_code_from_sections((pieces, rem), arm9_ram, "9",
                                                try_compress=False)
        body = _blz_compress(packed[BLZ_HEADER_LEN:])
        if body is None:
            raise ValueError("MMZX: the ARM9 did not compress")
        params.compressed_end = arm9_ram + BLZ_HEADER_LEN + len(body)
        blob = params.write_start_info(packed, arm9_ram)[:BLZ_HEADER_LEN] + body
        # the 12-byte "nitrocode" footer(s) that follow the ARM9 in the ROM
        post_off = post_end = arm9_off + arm9_len
        while bytes(d[post_end:post_end + 4]) == b"\x21\x06\xC0\xDE":
            post_end += 12
        post = bytes(d[post_off:post_end])
        others = [struct.unpack_from("<I", d, o)[0]
                  for o in (0x30, 0x40, 0x48, 0x50, 0x68)]
        slot_end = min(x for x in others if x > arm9_off)
        if len(blob) + len(post) > slot_end - arm9_off:
            raise ValueError(
                "MMZX: the recompressed ARM9 (0x%X+%d) does not fit in its slot "
                "(0x%X)" % (len(blob), len(post), slot_end - arm9_off))
        d[arm9_off:arm9_off + len(blob)] = blob
        end = arm9_off + len(blob)
        d[end:end + len(post)] = post
        d[end + len(post):slot_end] = b"\x00" * (slot_end - end - len(post))
        struct.pack_into("<I", d, 0x2C, len(blob))

        # AP icon set; relocates obj_dat and obj_fnt
        fnt_start = _install_icon_set(d)

        # Help texts of the MISSION tab, in place and of the same length
        for off in MENU_WARP_TEXT_OFFS:
            o = MENU_WARP_TEXT_ROM + off
            cur = bytes(d[o:o + len(MENU_WARP_TEXT_NEW)])
            if cur == MENU_WARP_TEXT_NEW:
                continue
            if hashlib.sha256(cur).hexdigest() != MENU_WARP_TEXT_SHA256:
                raise ValueError("MMZX: unexpected text at m_sub_en.bin+0x%X (%s)" % (off, cur.hex()))
            d[o:o + len(MENU_WARP_TEXT_NEW)] = MENU_WARP_TEXT_NEW

        # Secret Disk logo inside the relocated obj_fnt.bin; set 58 precedes the AP set
        logo_off = fnt_start + DISK_LOGO_FNT_OFF
        cur = bytes(d[logo_off:logo_off + len(DISK_LOGO_NEW)])
        if cur != DISK_LOGO_NEW:
            if hashlib.sha256(cur).hexdigest() != DISK_LOGO_SHA256:
                raise ValueError("MMZX: unexpected disk tile at ROM 0x%X (%s)" % (logo_off, cur[:8].hex()))
            d[logo_off:logo_off + len(DISK_LOGO_NEW)] = DISK_LOGO_NEW

        # Header CRC16 (CRC-16/MODBUS over [0:0x15E])
        crc = 0xFFFF
        for b in bytes(d[:0x15E]):
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        struct.pack_into("<H", d, 0x15E, crc)
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
                       hu_in_pool: bool = False) -> None:
    """Write the AP marker (magic, version, slot, seed) and the option blob read by patch_arm9."""
    blob = bytearray(0x80)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    blob[0x08:0x0C] = WORLD_VERSION_INT.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:63]
    blob[0x10:0x10 + len(name)] = name
    seed = seed_name.encode("utf-8")[:31]
    blob[0x50:0x50 + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
    # option flags for patch_arm9, which runs before apply_tokens
    cfg = bytearray(4)
    cfg[0] = CFG_HU_IN_POOL if hu_in_pool else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
