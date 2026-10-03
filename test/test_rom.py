"""The ROM patch helpers, without a ROM: BLZ round trips, Thumb `bl` encoding and the patch tables.

The rom package imports the Archipelago core, so a checkout is needed, but no
multiworld is built. TestVanillaBytes reads the player's ROM when MMZX_ROM points
at it (or roms/mmzx_us.nds lies three folders up) and is skipped otherwise.
"""
import hashlib
import os
import random
import struct
import unittest
from pathlib import Path

from .. import rom
from ..apnds import lz
from ..data import (GOAL_LINE_ADDR, ICON_CODES, ITEMS, LIVE_BLOCK, LOCATIONS, MISSION_ACCEPT, MISSION_COMPLETED_BIT,
                    MISSION_REPEAT_BITS, NOTIFY_ADDR, NOTIFY_BUF_MAX, PICKUP_TABLE_ADDR, STARTING_MODELS,
                    STARTING_TRANSERVERS)
from ..rom import arm9, blz, golden, missions, nds, pickups, sprites, table, ui

PATCH_MODULES = (pickups, sprites, ui, missions)     # the modules that hold patch tables and caves
ARM9_RAM = (0x02000000, 0x02400000)
# Zero stretches of the vanilla ARM9 that take the caves.
FREE_STRETCHES = [(0x020CB434, 0x020CB9D4), (0x020C8150, sprites.GFX_CAVES_END)]
ROM_PATH = os.environ.get("MMZX_ROM") or str(Path(__file__).resolve().parents[3] / "roms" / "mmzx_us.nds")
# The post-briefing save the golden image reproduces: with the two ROM tables blank, and complete.
GOLDEN_BASELINE_SHA256 = "6826c4e9e4a77b5531ec5a8e945b34164b0fda862321cd31add7b711b824ef90"
GOLDEN_COMPLETE_SHA256 = "1eaed883e7a443eaf0ccb900a6ffcabbfb6d6863713892b58bf4c00c9393ee11"


def as_bytes(value) -> bytes:
    """Patch tables hold bytes or hex strings."""
    return bytes.fromhex(value) if isinstance(value, str) else bytes(value)


def decode_bl(src: int, code: bytes) -> int:
    """Target of a Thumb `bl` pair placed at src."""
    hi, lo = struct.unpack("<HH", code)
    off = ((hi & arm9.THUMB_BL_OFFSET_MASK) << 12) | ((lo & arm9.THUMB_BL_OFFSET_MASK) << 1)
    if off & (1 << 22):
        off -= 1 << 23
    return src + 4 + off


def decode_b(src: int, code: bytes) -> int:
    """Target of a Thumb unconditional `b` placed at src."""
    (hw,) = struct.unpack("<H", code)
    off = (hw & 0x7FF) << 1
    if off & (1 << 11):
        off -= 1 << 12
    return src + 4 + off


def is_bl(code: bytes) -> bool:
    if len(code) != 4:
        return False
    hi, lo = struct.unpack("<HH", code)
    return (hi & 0xF800) == arm9.THUMB_BL_HIGH and (lo & 0xF800) == arm9.THUMB_BL_LOW


def constants():
    """(module, name, value) of every module-level name of the patch modules."""
    for mod in PATCH_MODULES:
        for name in dir(mod):
            yield mod, name, getattr(mod, name)


def patch_sites():
    """[(table, ram, orig)] of every patch site whose vanilla bytes the patch modules record."""
    out = []
    for mod, name, value in constants():
        if isinstance(value, list) and value and all(isinstance(t, tuple) and isinstance(t[0], int) for t in value):
            for entry in value:
                if len(entry) >= 2 and isinstance(entry[1], (bytes, str)):
                    out.append((name, entry[0], as_bytes(entry[1])))
        elif name.endswith("_ORIG") and isinstance(getattr(mod, name[:-5] + "_RAM", None), int):
            out.append((name, getattr(mod, name[:-5] + "_RAM"), as_bytes(value)))
    for ram in sprites.SPRITEGUARD_SITES:
        out.append(("SPRITEGUARD_SITES", ram, sprites.SPRITEGUARD_ORIG))
    return out


def replacement_pairs():
    """[(table, orig, new)] of every in-place replacement."""
    out = []
    for mod, name, value in constants():
        if isinstance(value, list) and value and all(isinstance(t, tuple) and len(t) == 3 for t in value):
            for _ram, orig, new in value:
                out.append((name, as_bytes(orig), as_bytes(new)))
        elif name.endswith("_ORIG") and hasattr(mod, name[:-5] + "_NEW"):
            out.append((name, as_bytes(value), as_bytes(getattr(mod, name[:-5] + "_NEW"))))
    return out


def caves():
    """{name: (ram, bytes)} of every cave body (X_CAVE, X_CAVES, X_CAVE_A...) with its X_..._RAM address."""
    return {name: (getattr(mod, name + "_RAM"), value)
            for mod, name, value in constants()
            if "_CAVE" in name and isinstance(value, bytes)
            and isinstance(getattr(mod, name + "_RAM", None), int)}


def cave_at(ram: int):
    """(cave name, offset) of a RAM address inside a cave body, or None."""
    for name, (start, body) in caves().items():
        if start <= ram < start + len(body):
            return name, ram - start
    return None


class TestBLZ(unittest.TestCase):
    def round_trip(self, data: bytes) -> bytes:
        body = blz.compress(data)
        self.assertIsNotNone(body, "the data did not compress")
        self.assertLess(len(body), len(data))
        code = bytes(blz.BLZ_HEADER_LEN) + body
        out, rem = lz.decompress_code(code, len(code))
        self.assertEqual(rem, b"")
        self.assertEqual(out[blz.BLZ_HEADER_LEN:], data)
        return body

    def test_text(self) -> None:
        """Repetitive text survives a compress/decompress round trip."""
        self.round_trip(b"the quick brown fox jumps over the lazy dog. " * 200)

    def test_byte_pattern(self) -> None:
        """A long periodic pattern (matches at the maximum distance and length) round-trips."""
        self.round_trip(bytes(range(256)) * 32)

    def test_zeros(self) -> None:
        """A zero block, the shape of the free stretches, round-trips."""
        self.round_trip(bytes(0x1000))

    def test_mixed_chunks(self) -> None:
        """Shuffled repeats of random chunks, like code, round-trip."""
        rng = random.Random(7)
        chunks = [bytes(rng.getrandbits(8) for _ in range(64)) for _ in range(8)]
        self.round_trip(b"".join(rng.choice(chunks) for _ in range(128)))

    def test_incompressible_data_is_refused(self) -> None:
        """Random bytes gain nothing, so the encoder returns None instead of growing the image."""
        rng = random.Random(1)
        self.assertIsNone(blz.compress(bytes(rng.getrandbits(8) for _ in range(4096))))

    def test_stream_layout(self) -> None:
        """The region ends with the footer the DS loader reads: stream length, footer length, growth."""
        data = bytes(0x800) + b"abc" * 100
        body = self.round_trip(data)
        stream_len = int.from_bytes(body[-8:-5], "little")
        footer_len = body[-5]
        growth = int.from_bytes(body[-4:], "little")
        self.assertEqual(len(body) + growth, len(data))
        self.assertLessEqual(stream_len, len(body))
        self.assertIn(footer_len, (8, 9, 10, 11))


class TestThumbBL(unittest.TestCase):
    def test_known_hooks(self) -> None:
        """The recorded `bl` encodings of the hooks match the addresses they join."""
        cases = [
            (pickups.PICKUP_MAILBOX_HOOK_RAM, pickups.PICKUP_MAILBOX_CAVE_RAM, pickups.PICKUP_MAILBOX_HOOK_NEW),
            (ui.NOTIFY_HOOK_RAM, ui.NOTIFY_CAVE_RAM, ui.NOTIFY_HOOK_NEW),
            (ui.MENU_WARP_HOOKS[0][0], ui.MENU_WARP_CAVE_A_RAM, ui.MENU_WARP_HOOKS[0][2]),
            (ui.MENU_WARP_HOOKS[1][0], ui.MENU_WARP_CAVE_B_RAM, ui.MENU_WARP_HOOKS[1][2]),
            (ui.CUTSCENE_SKIP_PATCH[1][0], ui.CUTSCENE_SKIP_CAVE_RAM, ui.CUTSCENE_SKIP_PATCH[1][2]),
            (pickups.DATASELECT_ICON_PATCH[4][0], pickups.DATASELECT_CAVE_RAM,
             as_bytes(pickups.DATASELECT_ICON_PATCH[4][2])[:4]),
        ]
        for src, dst, expected in cases:
            with self.subTest(src=hex(src)):
                self.assertEqual(arm9.thumb_bl(src, dst), as_bytes(expected))

    def test_vanilla_calls_round_trip(self) -> None:
        """Every recorded vanilla `bl` decodes to an even ARM9 address and re-encodes to itself."""
        seen = 0
        for table, ram, orig in patch_sites():
            if not is_bl(orig):
                continue
            seen += 1
            with self.subTest(table=table, ram=hex(ram)):
                target = decode_bl(ram, orig)
                self.assertEqual(target % 2, 0)
                self.assertTrue(ARM9_RAM[0] <= target < ARM9_RAM[1], hex(target))
                self.assertEqual(arm9.thumb_bl(ram, target), orig)
        self.assertGreater(seen, 10)

    def test_backward_and_forward(self) -> None:
        """Both branch directions encode within the 4 MiB range."""
        for src, dst in ((0x02001000, 0x02000000), (0x02000000, 0x023FFFFE), (0x020A30A2, 0x020CB4A0)):
            with self.subTest(src=hex(src), dst=hex(dst)):
                code = arm9.thumb_bl(src, dst)
                self.assertTrue(is_bl(code))
                self.assertEqual(decode_bl(src, code), dst)


class TestPatchTables(unittest.TestCase):
    def test_replacements_keep_their_length(self) -> None:
        pairs = replacement_pairs()
        self.assertGreater(len(pairs), 10)
        for table, orig, new in pairs:
            with self.subTest(table=table, orig=orig.hex()):
                self.assertEqual(len(orig), len(new))
                self.assertGreater(len(orig), 0)

    def test_pickup_ap_hooks(self) -> None:
        """Each PICKUP_AP hook rebuilds exactly the bytes it displaces around a `bl` into a known entry."""
        for ram, orig, entry, pre, post in pickups.PICKUP_AP_HOOKS:
            with self.subTest(ram=hex(ram)):
                self.assertIn(entry, pickups.PICKUP_AP_ENTRIES)
                self.assertEqual(len(pre) + 4 + len(post), len(orig))
        for entry, offset in pickups.PICKUP_AP_ENTRIES.items():
            with self.subTest(entry=entry):
                self.assertEqual(offset % 2, 0)
                self.assertLess(offset, len(pickups.PICKUP_AP_CAVE))

    def test_sites_are_halfword_aligned(self) -> None:
        """Thumb code is patched at even addresses inside the ARM9."""
        for table, ram, _orig in patch_sites():
            with self.subTest(table=table, ram=hex(ram)):
                self.assertEqual(ram % 2, 0)
                self.assertTrue(ARM9_RAM[0] <= ram < ARM9_RAM[1])

    def test_caves_fit_the_free_stretches(self) -> None:
        """Caves and the client's data blocks lie in the zero stretches and never overlap."""
        blocks = {name: (ram, len(body)) for name, (ram, body) in caves().items()}
        blocks["HUGATE_ARRAY"] = (pickups.HUGATE_ARRAY_RAM, 4)
        blocks["MENU_WARP_FLAGS"] = (ui.MENU_WARP_FLAGS_RAM, 2)
        blocks["NOTIFY"] = (NOTIFY_ADDR, NOTIFY_BUF_MAX + 4)
        self.assertGreaterEqual(len(blocks), 16)
        for name, (start, size) in blocks.items():
            with self.subTest(block=name):
                self.assertGreater(size, 0)
                self.assertTrue(any(lo <= start and start + size <= hi for lo, hi in FREE_STRETCHES),
                                "%s at 0x%08X+%d is outside the free stretches" % (name, start, size))
        spans = sorted((start, start + size, name) for name, (start, size) in blocks.items())
        for (_s0, end, a), (start, _e1, b) in zip(spans, spans[1:]):
            self.assertLessEqual(end, start, "%s overlaps %s" % (a, b))

    def test_icon_entry_points(self) -> None:
        """The ATTACH and ANIM entries are inside the icon cave, on a halfword."""
        start, body = caves()["ICON_CAVES"]
        for entry in (sprites.ICON_ATTACH_CAVE_RAM, sprites.ICON_ANIM_CAVE_RAM):
            self.assertTrue(start < entry < start + len(body), hex(entry))
            self.assertEqual(entry % 2, 0)
        start, body = caves()["ICON_CARRIED_CAVE"]
        for entry in (sprites.ICON_CARRIED_ANIM_CAVE_RAM, sprites.ICON_CARRIED_RETRY_CAVE_RAM):
            self.assertTrue(start < entry < start + len(body), hex(entry))
            self.assertEqual(entry % 2, 0)
        self.assertEqual(len(sprites.ICON_CARRIED_HOOKS), 3)

    def test_pickup_table_layout(self) -> None:
        """The section's pieces follow each other on word boundaries, and every location has a slot."""
        self.assertEqual(PICKUP_TABLE_ADDR % 4, 0)
        self.assertLessEqual(len(table.PICKUP_TABLE_CODE), table.CODE_MAX)
        self.assertLessEqual(table.CODE_MAX, table.FLAGS_OFF)
        self.assertLess(table.FLAGS_OFF, table.CHECKED_OFF)
        self.assertLessEqual(table.CHECKED_OFF + table.BITMAP_LEN, table.COLLECTED_OFF)
        self.assertLessEqual(table.COLLECTED_OFF + table.BITMAP_LEN, table.INDEX_OFF)
        self.assertLessEqual(table.INDEX_OFF + 2 * (table.INDEX_SUBAREAS + 1), table.ENTRIES_OFF)
        for off in (table.FLAGS_OFF, table.CHECKED_OFF, table.COLLECTED_OFF, table.INDEX_OFF, table.ENTRIES_OFF):
            self.assertEqual(off % 4, 0, hex(off))
        self.assertLessEqual(len(table.PICKUP_SLOTS), table.MAX_SLOTS)
        self.assertEqual(sorted(table.PICKUP_SLOTS.values()), list(range(len(table.PICKUP_SLOTS))))
        for name in table.PICKUP_SLOTS:
            self.assertLess(int(LOCATIONS[name]["icon"][0]), table.INDEX_SUBAREAS)
        full = table.build_section(table.build_table({n: 1 for n in table.PICKUP_SLOTS}))
        self.assertEqual(len(full) % 4, 0)
        self.assertLessEqual(PICKUP_TABLE_ADDR + len(full), ui.ROOM_OVERLAY_SLOT_RAM)
        self.assertGreaterEqual(PICKUP_TABLE_ADDR, ui.GOLDEN_IMAGE_RAM + golden.GOLDEN_IMAGE_SIZE)

    def test_usable_table(self) -> None:
        """The relocated ITEM A flags all index the possession byte of the pickup table section."""
        self.assertEqual(pickups.USABLE_TABLE_NEW, pickups.usable_table())
        vanilla = struct.unpack("<8I", pickups.USABLE_TABLE_ORIG)
        self.assertEqual(sorted(vanilla), list(range(pickups.USABLE_FLAG_FIRST, pickups.USABLE_FLAG_FIRST + 8)))
        for flag in struct.unpack("<8I", pickups.USABLE_TABLE_NEW):
            self.assertEqual(LIVE_BLOCK + (flag >> 3), PICKUP_TABLE_ADDR + table.USABLES_OFF)
        self.assertGreaterEqual(table.USABLES_OFF, table.COLLECTED_OFF + table.BITMAP_LEN)
        self.assertLess(table.USABLES_MARK_OFF, table.INDEX_OFF)
        # the items' grant bits are the flags' bits
        bits = {name: v["grant"][1] for name, v in ITEMS.items() if v["grant"][0] == "usable"}
        self.assertEqual(sorted(bits.values()), list(range(8)))
        for name, v in LOCATIONS.items():
            if v["category"] == "usable":
                item = name.split(": ", 1)[1]
                flag = (v["detect"][1] - LIVE_BLOCK) * 8 + v["detect"][2]
                self.assertEqual(bits[item], flag - pickups.USABLE_FLAG_FIRST, name)

    def test_usable_texts(self) -> None:
        """The eight pickup popups become the multiworld notice; the rest of the file is untouched."""
        head = ui.USABLE_TEXT_HEAD
        n = ui.USABLE_TEXT_FIRST + ui.USABLE_TEXT_COUNT + 2
        texts = [(ui.REPLAY_TEXTS[k][0] if k in ui.REPLAY_TEXTS else
                  head + bytes([0x21 + k % 26, 0x22]) if ui.USABLE_TEXT_FIRST <= k < n - 2 else
                  bytes([0x30 + k % 10] * (k % 5 + 1)))
                 + bytes([ui.PAUSE_TEXT_END]) for k in range(n)]
        offs, pos = [], 0
        for t in texts:
            offs.append(pos)
            pos += len(t)
        body = b"".join(texts)
        data = struct.pack("<HH", 4 + 2 * n + len(body), 2 * n) + struct.pack("<%dH" % n, *offs) + body + b"\x00\x00"
        out = ui.talk_texts_rebuilt(data)
        total, tsize = struct.unpack_from("<HH", out, 0)
        self.assertEqual(tsize, 2 * n)
        self.assertEqual(total, len(out) - 2)
        new_offs = struct.unpack_from("<%dH" % n, out, 4)
        base = 4 + tsize
        for k in range(n):
            end = out.index(bytes([ui.PAUSE_TEXT_END]), base + new_offs[k])
            text = out[base + new_offs[k]:end]
            if k in ui.REPLAY_TEXTS:
                self.assertEqual(text, ui.REPLAY_TEXTS[k][1], k)
            elif ui.USABLE_TEXT_FIRST <= k < n - 2:
                self.assertEqual(text, ui.USABLE_TEXT_NEW, k)
            else:
                self.assertEqual(text, texts[k][:-1], k)
        self.assertEqual(out[-2:], b"\x00\x00")
        with self.assertRaises(ValueError):
            ui.talk_texts_rebuilt(data.replace(head, b"\x01" * len(head), 1))

    def test_overlay_patches_keep_their_length(self) -> None:
        for ovl, patches in pickups.OVERLAY_USABLE_PATCH.items():
            for ram, orig, new in patches:
                with self.subTest(ovl=ovl, ram=hex(ram)):
                    self.assertEqual(len(as_bytes(orig)), len(as_bytes(new)))
                    self.assertEqual(ram % 2, 0)
                    self.assertGreaterEqual(ram, ui.ROOM_OVERLAY_SLOT_RAM)

    def test_overlay_round_trip(self) -> None:
        """A synthetic overlay survives compress, store, read back and patch."""
        random.seed(5)
        code = bytes(random.choice(b"\x00\x01\x02\xff") for _ in range(600)) * 4 + bytes(range(256)) * 3
        packed = blz.compress(code)
        self.assertIsNotNone(packed)
        self.assertEqual(lz.decompress_code(packed, len(packed))[0][:len(code)], code)
        # a tiny ROM: header fields, one FAT entry, one overlay entry and the file
        rom = bytearray(0x4000)
        table, fat, file_off = 0x800, 0x900, 0x1000
        struct.pack_into("<II", rom, nds.NDS_HDR_OVERLAYS9, table, nds.OVERLAY_ENTRY_LEN)
        struct.pack_into("<II", rom, nds.NDS_HDR_FAT, fat, nds.FAT_ENTRY_LEN)
        struct.pack_into("<8I", rom, table, 0, ui.ROOM_OVERLAY_SLOT_RAM, len(code), 0, 0, 0, 0,
                         nds.OVERLAY_COMPRESSED | len(packed))
        struct.pack_into("<II", rom, fat, file_off, file_off + len(packed))
        rom[file_off:file_off + len(packed)] = packed
        struct.pack_into("<I", rom, nds.NDS_HDR_ROM_SIZE, file_off + len(packed))
        ram, back = nds.overlay_code(rom, 0)
        self.assertEqual((ram, back), (ui.ROOM_OVERLAY_SLOT_RAM, code))
        site = ui.ROOM_OVERLAY_SLOT_RAM + 100
        nds.patch_overlay(rom, 0, [(site, code[100:104], b"\xaa\xbb\xcc\xdd")])
        ram, after = nds.overlay_code(rom, 0)
        self.assertEqual(after[100:104], b"\xaa\xbb\xcc\xdd")
        self.assertEqual(after[:100] + after[104:], code[:100] + code[104:])
        comp = struct.unpack_from("<I", rom, table + nds.OVERLAY_SIZE_OFF)[0]
        start, end = struct.unpack_from("<II", rom, fat)
        self.assertTrue(comp & nds.OVERLAY_COMPRESSED)
        self.assertEqual(comp & nds.OVERLAY_SIZE_MASK, end - start)
        self.assertGreaterEqual(start, file_off + len(packed))   # relocated after the old file
        with self.assertRaises(ValueError):
            nds.patch_overlay(rom, 0, [(site, b"\x00\x00\x00\x00", b"\x01\x02\x03\x04")])

    def test_pickup_table_routines_know_the_layout(self) -> None:
        """The routines' literal pools name the switch, the bitmaps, the index and the entries."""
        code = table.PICKUP_TABLE_CODE
        words = {int.from_bytes(code[i:i + 4], "little") for i in range(0, len(code), 4)}
        for off in (table.FLAGS_OFF, table.CHECKED_OFF, table.COLLECTED_OFF, table.INDEX_OFF, table.ENTRIES_OFF):
            self.assertIn(PICKUP_TABLE_ADDR + off, words, hex(off))
        for name, off in table.PICKUP_TABLE_ENTRIES.items():
            with self.subTest(entry=name):
                self.assertEqual(off % 2, 0)
                self.assertLess(off, len(code))

    def test_caves_jump_into_the_pickup_table(self) -> None:
        """LOOKUP, the AP gate and the mailbox cave hold the Thumb address of their routine."""
        entries = {name: PICKUP_TABLE_ADDR + off + 1 for name, off in table.PICKUP_TABLE_ENTRIES.items()}
        self.assertEqual(int.from_bytes(sprites.ICON_CAVES[4:8], "little"), entries["lookup"])
        self.assertEqual(int.from_bytes(pickups.PICKUP_AP_CAVE[4:8], "little"), entries["gate"])
        self.assertEqual(int.from_bytes(pickups.PICKUP_MAILBOX_CAVE[-4:], "little"), entries["collect"])
        # the retry cave still re-hooks the mailbox cave's first call
        self.assertEqual(pickups.PICKUP_MAILBOX_CAVE[2:6], as_bytes(sprites.ICON_RETRY_HOOKS[0][1]))
        # the cut guard asks the gate, plays the sound it displaced and resumes the think's no-hit path
        pool = pickups.REFILL_CUT_CAVE[-12:]
        self.assertEqual([int.from_bytes(pool[i:i + 4], "little") for i in range(0, 12, 4)],
                         [entries["gate"], pickups.SFX_ROUTINE_RAM + 1, pickups.REFILL_CUT_RESUME_RAM + 1])
        self.assertEqual(decode_bl(pickups.REFILL_CUT_HOOK_RAM, pickups.REFILL_CUT_HOOK_ORIG),
                         pickups.SFX_ROUTINE_RAM)

    def test_build_table_round_trips(self) -> None:
        """Entries come back by name with their slot, code and respawn flag, sorted by room."""
        codes = {"A-2: Disk B-3": ICON_CODES["secret_disk"], "A-1: Disk E-1": ICON_CODES["logo_filler"],
                 "D-1: Life Up": ICON_CODES["chip_Frog"]}
        codes.update({n: ICON_CODES["logo_useful"] for n, v in LOCATIONS.items()
                      if (v.get("detect") or [None])[0] == "mailbox" and v["room"] == "a01"})
        built = table.build_table(codes)
        self.assertEqual(len(built), table.ENTRIES_OFF - table.INDEX_OFF + table.ENTRY_LEN * len(codes))
        starts = struct.unpack_from("<%dH" % (table.INDEX_SUBAREAS + 1), built, 0)
        self.assertEqual(list(starts), sorted(starts))
        self.assertEqual(starts[-1], len(codes))
        entries = table.table_entries(built)
        self.assertEqual({n: c for n, (_slot, c, _flags) in entries.items()}, codes)
        for name, (slot, _code, flags) in entries.items():
            self.assertEqual(slot, table.PICKUP_SLOTS[name])
            self.assertEqual(bool(flags & table.ENTRY_RESPAWNS), LOCATIONS[name]["detect"][0] == "mailbox")
        with self.assertRaises(ValueError):
            table.build_table({"A-2: Disk B-3": 300})

    def test_icon_code(self) -> None:
        """Our items with a sprite get it; everything else the logo of its classification."""
        self.assertEqual(table.icon_code("Life Up", True, False, True), ICON_CODES["lifeup"])
        self.assertEqual(table.icon_code("Progressive Model HX", True, True, False), ICON_CODES["model_HX"])
        self.assertEqual(table.icon_code("Red Card Key", True, True, False), ICON_CODES["card_Red"])
        self.assertEqual(table.icon_code("E-Crystals", True, False, False), ICON_CODES["logo_filler"])
        self.assertEqual(table.icon_code("Life Up", False, False, True), ICON_CODES["logo_useful"])
        self.assertEqual(table.icon_code("Something", False, True, True), ICON_CODES["logo_progression"])
        self.assertEqual(table.icon_code("Something", False, False, False), ICON_CODES["logo_filler"])

    def test_marker_layout(self) -> None:
        """Magic, version, slot name and seed fit the marker, which sits in the ROM header padding."""
        self.assertLessEqual(len(rom.AP_MAGIC), rom.AP_MARKER_VERSION_OFF)
        self.assertLessEqual(rom.AP_MARKER_VERSION_OFF + 4, rom.AP_MARKER_SLOT_OFF)
        self.assertLessEqual(rom.AP_MARKER_SLOT_OFF + rom.AP_MARKER_SLOT_MAX + 1, rom.AP_MARKER_SEED_OFF)
        self.assertLessEqual(rom.AP_MARKER_SEED_OFF + rom.AP_MARKER_SEED_MAX + 1, rom.AP_MARKER_LEN)
        self.assertLessEqual(rom.AP_MAGIC_OFFSET + rom.AP_MARKER_LEN, blz.BLZ_HEADER_LEN)

    def test_client_reads_the_marker_where_the_patch_writes_it(self) -> None:
        from ..client.addresses import ROM_AP_MAGIC, ROM_AP_MAGIC_OFF, ROM_AP_VERSION_OFF, ROM_SLOT_NAME_OFF
        self.assertEqual(ROM_AP_MAGIC, rom.AP_MAGIC)
        self.assertEqual(ROM_AP_MAGIC_OFF, rom.AP_MAGIC_OFFSET)
        self.assertEqual(ROM_AP_VERSION_OFF, rom.AP_MAGIC_OFFSET + rom.AP_MARKER_VERSION_OFF)
        self.assertEqual(ROM_SLOT_NAME_OFF, rom.AP_MAGIC_OFFSET + rom.AP_MARKER_SLOT_OFF)
        for version in ((0, 1, 0), (1, 12, 255)):
            self.assertEqual(rom.unpack_version(rom.pack_version(version)), version)

    def test_patch_tokens(self) -> None:
        """write_patch_tokens stores the marker with the slot name, the option blob, the golden image and the pickup table."""
        image = golden.build_image("model_zx", 0, STARTING_MODELS, STARTING_TRANSERVERS["area_a"])
        pickup_table = table.build_table({"A-2: Disk B-3": ICON_CODES["secret_disk"]})
        patch = rom.MMZXPatch(player=1, player_name="Tester")
        rom.write_patch_tokens(patch, "Tester", "seed-1", (0, 1, 0), image, pickup_table, hu_in_pool=True)
        tokens = patch.get_file("token_data.bin")
        self.assertIn(rom.AP_MAGIC, tokens)
        self.assertIn(b"Tester", tokens)
        self.assertIn(b"seed-1", tokens)
        self.assertEqual(patch.get_file("mmzx_cfg.bin")[0] & rom.CFG_HU_IN_POOL, rom.CFG_HU_IN_POOL)
        self.assertEqual(patch.get_file("golden_image.bin"), image)
        self.assertEqual(patch.get_file("pickup_table.bin"), pickup_table)
        patch = rom.MMZXPatch(player=1, player_name="Tester")
        rom.write_patch_tokens(patch, "Tester", "seed-1", (0, 1, 0), image, pickup_table)
        self.assertEqual(patch.get_file("mmzx_cfg.bin")[0] & rom.CFG_HU_IN_POOL, 0)
        self.assertEqual([name for name, _files in rom.MMZXPatch.procedure],
                         ["patch_arm9", "apply_tokens"])
        self.assertIn("golden_image.bin", rom.MMZXPatch.procedure[0][1])
        self.assertIn("pickup_table.bin", rom.MMZXPatch.procedure[0][1])

    def test_golden_baseline_is_the_recorded_save(self) -> None:
        """The image built from its fields is the save a clean post-briefing game recorded."""
        image = golden.baseline_image()
        self.assertEqual(len(image), golden.GOLDEN_IMAGE_SIZE)
        self.assertEqual(hashlib.sha256(image).hexdigest(), GOLDEN_BASELINE_SHA256)
        self.assertEqual(golden.build_image("model_x", 0, STARTING_MODELS, STARTING_TRANSERVERS["area_a"]),
                         bytes(image))
        for off, length in ((golden.BLOCK_OFF, golden.BLOCK_LEN), (golden.DESC_OFF, golden.DESC_LEN),
                            (golden.QUEUE_OFF, golden.QUEUE_LEN)):
            self.assertEqual(image[off:off + length], image[off + length:off + 2 * length])

    def test_golden_image_section(self) -> None:
        """The image lands in the overlay gap before the pickup table, and the copy cave knows where."""
        self.assertLessEqual(ui.GOLDEN_IMAGE_RAM + golden.GOLDEN_IMAGE_SIZE, PICKUP_TABLE_ADDR)
        self.assertLessEqual(ui.GOLDEN_IMAGE_RAM + golden.GOLDEN_IMAGE_SIZE, ui.ROOM_OVERLAY_SLOT_RAM)
        self.assertEqual(ui.GOLDEN_IMAGE_RAM % 4, 0)
        self.assertEqual(golden.GOLDEN_IMAGE_SIZE % 4, 0)
        words = [int.from_bytes(ui.SKIP_COPY_CAVE[i:i + 4], "little") for i in range(0, len(ui.SKIP_COPY_CAVE), 4)]
        for value in (ui.GOLDEN_IMAGE_RAM, ui.GOLDEN_IMAGE_RAM + golden.GOLDEN_IMAGE_SIZE, golden.GOLDEN_IMAGE_ADDR):
            self.assertIn(value, words, hex(value))
        self.assertIn(ui.SKIP_COPY_CAVE_RAM + 1, [int.from_bytes(ui.SKIP_CAVE[i:i + 4], "little")
                                                 for i in range(0, len(ui.SKIP_CAVE), 4)])


@unittest.skipUnless(os.path.isfile(ROM_PATH), "set MMZX_ROM to the vanilla Mega Man ZX (USA) ROM")
class TestMissionSection(unittest.TestCase):
    """The mission list section: its tables come from data.py and its hooks replace the vanilla calls."""

    def test_layout(self) -> None:
        section = missions.build_section()
        self.assertEqual(len(section), missions.MISSION_SECTION_LEN)
        self.assertEqual(section[:len(missions.MISSION_SECTION_CODE)], missions.MISSION_SECTION_CODE)
        self.assertLessEqual(len(missions.MISSION_SECTION_CODE), missions.MISSION_LIST_OFF)
        listing = missions.mission_list_table()
        self.assertEqual(section[missions.MISSION_LIST_OFF:missions.MISSION_LIST_OFF + len(listing)], listing)
        self.assertEqual(section[missions.MISSION_NEVER_OFF:missions.MISSION_NEVER_OFF + 4], bytes(4))
        states = missions.mission_states()
        self.assertEqual(section[missions.MISSION_STATES_OFF:missions.MISSION_STATES_OFF + len(states)], states)
        index, rows = missions.mission_repeat_table()
        self.assertEqual(section[missions.MISSION_REPEAT_INDEX_OFF:missions.MISSION_REPEAT_INDEX_OFF + len(index)], index)
        self.assertEqual(section[missions.MISSION_REPEAT_OFF:missions.MISSION_REPEAT_OFF + len(rows)], rows)
        for name, off in missions.MISSION_SECTION_ENTRIES.items():
            with self.subTest(entry=name):
                self.assertEqual(off % 2, 0)
                self.assertLess(off, len(missions.MISSION_SECTION_CODE))
        self.assertGreaterEqual(missions.MISSION_SECTION_RAM,
                                PICKUP_TABLE_ADDR + table.ENTRIES_OFF + table.MAX_SLOTS * table.ENTRY_LEN)
        self.assertLessEqual(missions.MISSION_SECTION_RAM + missions.MISSION_SECTION_LEN, ui.ROOM_OVERLAY_SLOT_RAM)

    def test_list_table(self) -> None:
        """Each mission lists on its completed bit, the final mission never, the quests as in vanilla."""
        words = struct.unpack("<%dI" % len(missions.MISSION_LIST_IDS), missions.mission_list_table())
        by_id = dict(zip(missions.MISSION_LIST_IDS, words))
        for mid, (addr, bit) in MISSION_COMPLETED_BIT.items():
            with self.subTest(mission=mid):
                self.assertEqual(by_id[mid], (addr - LIVE_BLOCK) * 8 + bit)
        never = by_id[missions.MISSION_LAST_STORY]
        self.assertEqual(LIVE_BLOCK + (never >> 3), missions.MISSION_SECTION_RAM + missions.MISSION_NEVER_OFF)
        quests = struct.unpack("<%dI" % (len(missions.MISSION_QUEST_FLAGS_ORIG) // 4), missions.MISSION_QUEST_FLAGS_ORIG)
        self.assertEqual(words[-len(quests):], quests)
        self.assertEqual(missions.MISSION_QUEST_FLAGS_RAM, 0x020DAE7C + 4 * (missions.MISSION_LAST_STORY + 1 - 2))

    def test_states(self) -> None:
        """One state byte per listed mission, the value its accept record carries, and no two alike."""
        states = missions.mission_states()
        self.assertEqual(len(states), len(missions.MISSION_REPEAT_IDS))
        by_id = {rec["id"]: rec["state"] for rec in MISSION_ACCEPT.values()}
        for k, mid in enumerate(missions.MISSION_REPEAT_IDS):
            self.assertEqual(states[k], by_id[mid], mid)
        self.assertEqual(len(set(states)), len(states))
        self.assertTrue(all(0 < v < 0x100 for v in states))

    def test_repeat_table(self) -> None:
        """Each mission's row holds its flags in order and ends with the mark; every flag clears the sign test."""
        index, rows = missions.mission_repeat_table()
        self.assertEqual(len(index), len(missions.MISSION_REPEAT_IDS))
        for k, mid in enumerate(missions.MISSION_REPEAT_IDS):
            flags = [(a - LIVE_BLOCK) * 8 + b for a, b in MISSION_REPEAT_BITS[mid]]
            row = struct.unpack_from("<%dH" % (len(flags) + 1), rows, index[k])
            with self.subTest(mission=mid):
                self.assertEqual(list(row[:-1]), flags)
                self.assertEqual(row[-1], missions.MISSION_REPEAT_END)
                self.assertTrue(all(0 < f < 0x8000 for f in flags))
        self.assertEqual(len(rows), sum(2 * (len(MISSION_REPEAT_BITS[m]) + 1) for m in missions.MISSION_REPEAT_IDS))

    def test_hooks(self) -> None:
        """The redirected calls were the vanilla count, accept and pending-story-mission calls."""
        for hooks, target in ((missions.MISSION_COUNT_HOOKS, 0x02008774), (missions.MISSION_TAKE_HOOKS, 0x02094FAC),
                              (missions.MISSION_PENDING_HOOKS, 0x02008A34)):
            for ram, orig in hooks:
                with self.subTest(ram=hex(ram)):
                    self.assertTrue(is_bl(orig))
                    self.assertEqual(decode_bl(ram, orig), target)
        menus = {ram: decode_b(ram, new) for ram, _orig, new in missions.MISSION_MENU_PATCH}
        self.assertEqual(menus, {0x020934F6: 0x02093496, 0x02093C92: 0x02093C28})
        (ram, orig, new), = missions.MISSION_LIST_LITERAL_PATCH
        self.assertEqual(int.from_bytes(orig, "little"), 0x020DAE7C)
        self.assertEqual(int.from_bytes(new, "little"), missions.MISSION_SECTION_RAM + missions.MISSION_LIST_OFF)

    def test_mission_names(self) -> None:
        """The two placeholder names are replaced and every other message keeps its bytes."""
        self.check_text_file(ui.MISSION_NAME_TEXTS, ui.system_texts_with_mission_names)

    def test_replay_texts(self) -> None:
        """The menu texts are replaced only where the vanilla text is what the patch expects."""
        self.check_text_file(ui.REPLAY_TEXTS, ui.talk_texts_rebuilt)
        for orig, new in ui.REPLAY_TEXTS.values():
            self.assertEqual(orig[:5], new[:5])          # the control header stays

    def check_text_file(self, replacements, rebuild) -> None:
        """A synthetic text file rebuilt by `rebuild` has the replacements and nothing else changed."""
        n = max(replacements) + 2
        texts = [(replacements[k][0] if k in replacements else bytes([0x21 + k % 26] * (k % 4 + 1)))
                 + bytes([ui.PAUSE_TEXT_END]) for k in range(n)]
        offs, pos = [], 0
        for t in texts:
            offs.append(pos)
            pos += len(t)
        body = b"".join(texts)
        data = struct.pack("<HH", 4 + 2 * n + len(body), 2 * n) + struct.pack("<%dH" % n, *offs) + body
        out = rebuild(data)
        new_offs = struct.unpack_from("<%dH" % n, out, 4)
        base = 4 + 2 * n
        for k in range(n):
            end = out.index(bytes([ui.PAUSE_TEXT_END]), base + new_offs[k])
            want = replacements[k][1] if k in replacements else texts[k][:-1]
            self.assertEqual(out[base + new_offs[k]:end], want, k)
        first = min(replacements)
        with self.assertRaises(ValueError):
            rebuild(data.replace(replacements[first][0], bytes([1]) * len(replacements[first][0]), 1))


class TestVanillaBytes(unittest.TestCase):
    """The vanilla bytes the patch modules record match the real ROM, and the caves land on zeros."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ROM_PATH, "rb") as f:
            cls.rom = f.read()
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", cls.rom, nds.NDS_HDR_ARM9)
        cls.code = arm9.Arm9(cls.rom[arm9_off:arm9_off + arm9_len], arm9_ram)

    def read(self, ram: int, size: int) -> bytes:
        for base, buf in self.code.sections:
            if base <= ram < base + len(buf):
                return bytes(buf[ram - base:ram - base + size])
        self.fail("0x%08X is outside the ARM9 sections" % ram)

    def test_rom_is_the_usa_release(self) -> None:
        self.assertEqual(hashlib.md5(self.rom).hexdigest(), rom.MMZX_US_MD5)

    def test_patch_sites(self) -> None:
        """Every recorded byte string is what the ARM9 holds at its address, or what the cave there holds."""
        for table, ram, orig in patch_sites():
            with self.subTest(table=table, ram=hex(ram)):
                inside = cave_at(ram)
                if inside:   # a hook chained on another cave's call
                    name, offset = inside
                    self.assertEqual(caves()[name][1][offset:offset + len(orig)], orig)
                else:
                    self.assertEqual(self.read(ram, len(orig)), orig)
        for cnt_a, lst_a, _flag1, orig1, _flag2, orig2 in pickups.BIOMETAL_CAT_PATCH.values():
            with self.subTest(list=hex(lst_a)):
                self.assertEqual(self.read(lst_a, 4), orig1.to_bytes(4, "little"))
                self.assertEqual(self.read(lst_a + 4, 4), orig2.to_bytes(4, "little"))
                self.assertEqual(self.read(cnt_a, 1), bytes([pickups.BIOMETAL_CAT_COUNT]))

    def test_golden_image_completed_from_the_rom(self) -> None:
        """With the weapon and controls tables of the ROM the image is the recorded save, byte for byte."""
        image = golden.add_rom_tables(golden.baseline_image(), self.code)
        self.assertEqual(hashlib.sha256(image).hexdigest(), GOLDEN_COMPLETE_SHA256)

    def test_caves_land_on_zeros(self) -> None:
        for lo, hi in FREE_STRETCHES:
            with self.subTest(stretch=hex(lo)):
                self.assertEqual(self.read(lo, hi - lo), bytes(hi - lo))

    def test_overlay_patch_sites(self) -> None:
        """The room overlays hold the vanilla bytes where the usable patches go, and patch cleanly."""
        rom = bytearray(self.rom)
        for ovl, patches in pickups.OVERLAY_USABLE_PATCH.items():
            ram, code = nds.overlay_code(rom, ovl)
            self.assertEqual(ram, ui.ROOM_OVERLAY_SLOT_RAM)
            for site, orig, _new in patches:
                with self.subTest(ovl=ovl, site=hex(site)):
                    self.assertEqual(code[site - ram:site - ram + len(as_bytes(orig))], as_bytes(orig))
        pickups.patch_usable_rooms(rom)
        for ovl, patches in pickups.OVERLAY_USABLE_PATCH.items():
            ram, code = nds.overlay_code(rom, ovl)
            for site, _orig, new in patches:
                self.assertEqual(code[site - ram:site - ram + len(as_bytes(new))], as_bytes(new))

    def test_usable_texts_of_the_rom(self) -> None:
        """The system text file rebuilds with the eight popups replaced and the menu texts renamed."""
        data = nds.file_bytes(bytearray(self.rom), ui.USABLE_TEXT_FILE_ID)
        out = ui.talk_texts_rebuilt(data)
        self.assertEqual(out.count(ui.USABLE_TEXT_NEW), ui.USABLE_TEXT_COUNT)
        self.assertGreater(len(out), len(data))
        for orig, new in ui.REPLAY_TEXTS.values():
            self.assertEqual(data.count(orig + bytes([ui.PAUSE_TEXT_END])), 1)
            self.assertEqual(out.count(new + bytes([ui.PAUSE_TEXT_END])), 1)

    def test_mission_names_of_the_rom(self) -> None:
        """The Transerver list file rebuilds with the two names in place of the placeholders."""
        data = nds.file_bytes(bytearray(self.rom), ui.MISSION_NAME_FILE_ID)
        out = ui.system_texts_with_mission_names(data)
        for orig, name in ui.MISSION_NAME_TEXTS.values():
            self.assertEqual(data.count(orig + bytes([ui.PAUSE_TEXT_END])), 1)
            self.assertEqual(out.count(name + bytes([ui.PAUSE_TEXT_END])), 1)
        self.assertEqual(self.read(missions.MISSION_QUEST_FLAGS_RAM, len(missions.MISSION_QUEST_FLAGS_ORIG)),
                         missions.MISSION_QUEST_FLAGS_ORIG)

    def test_pause_texts_of_the_rom(self) -> None:
        """The pause menu file rebuilds: one-line BIOMETAL texts and the signature message where the cave reads it."""
        data = nds.file_bytes(bytearray(self.rom), ui.PAUSE_TEXT_FILE_ID)
        out = ui.pause_texts_with_goal_line(data)
        _total, tsize = struct.unpack_from("<HH", out, 0)
        offs = struct.unpack_from("<%dH" % (tsize // 2), out, 4)
        sig = 4 + tsize + offs[ui.PAUSE_SIGNATURE_INDEX]
        self.assertEqual(out[sig:sig + len(ui.PAUSE_SIGNATURE)], ui.PAUSE_SIGNATURE)
        self.assertEqual(sig % 4, 0)
        self.assertEqual(sig, 4 + tsize + ui.GOAL_LINE_MESSAGES * (ui.GOAL_LINE_BUF_LEN + 1))

    def test_rom_level_edits(self) -> None:
        """The help texts and the disk tile have the digests the ROM steps check."""
        for off in ui.MENU_WARP_TEXT_OFFS:
            with self.subTest(text=hex(off)):
                cur = self.rom[ui.MENU_WARP_TEXT_ROM + off:ui.MENU_WARP_TEXT_ROM + off + len(ui.MENU_WARP_TEXT_NEW)]
                self.assertEqual(hashlib.sha256(cur).hexdigest(), ui.MENU_WARP_TEXT_SHA256)
        fat = struct.unpack_from("<I", self.rom, nds.NDS_HDR_FAT)[0]
        fnt_start = struct.unpack_from("<I", self.rom, fat + sprites.ICON_FNT_FILE_ID * nds.FAT_ENTRY_LEN)[0]
        tile = self.rom[fnt_start + sprites.DISK_LOGO_FNT_OFF:
                        fnt_start + sprites.DISK_LOGO_FNT_OFF + len(sprites.DISK_LOGO_NEW)]
        self.assertEqual(hashlib.sha256(tile).hexdigest(), sprites.DISK_LOGO_SHA256)


class TestPauseTexts(unittest.TestCase):
    """The STATUS help texts take the two-line layout the goal line cave checks before writing."""

    @staticmethod
    def bank(texts) -> bytes:
        body = b"".join(t + bytes([ui.PAUSE_TEXT_END]) for t in texts)
        offs, pos = [], 0
        for t in texts:
            offs.append(pos)
            pos += len(t) + 1
        tsize = 2 * len(texts)
        return (struct.pack("<HH", 4 + tsize + len(body), tsize)
                + struct.pack("<%dH" % len(texts), *offs) + body)

    def test_layout(self) -> None:
        first = b"\x23\x48\x4f\x4f" + bytes([0x53]) * 12
        two_lines = ui.PAUSE_SIGNATURE + bytes([0x41]) * 18 + bytes([ui.PAUSE_TEXT_LINE_BREAK]) + bytes([0x41]) * 10
        last = bytes([0x42]) * 5
        texts = [first] + [bytes([0x41 + k]) * 20 for k in range(9)] + [two_lines, last]
        out = ui.pause_texts_with_goal_line(self.bank(texts))
        total, tsize = struct.unpack_from("<HH", out, 0)
        base = 4 + tsize
        offs = struct.unpack_from("<%dH" % (tsize // 2), out, 4)
        for k in range(ui.GOAL_LINE_MESSAGES):
            text = out[base + offs[k]:base + offs[k] + ui.GOAL_LINE_BUF_LEN + 1]
            self.assertEqual(text[:len(texts[k])], texts[k])
            self.assertEqual(set(text[len(texts[k]):ui.GOAL_LINE_GLYPHS]), {0})
            self.assertEqual(text[ui.GOAL_LINE_GLYPHS], ui.PAUSE_TEXT_LINE_BREAK)
            self.assertEqual(set(text[ui.GOAL_LINE_GLYPHS + 1:ui.GOAL_LINE_BUF_LEN]), {0})
            self.assertEqual(text[ui.GOAL_LINE_BUF_LEN], ui.PAUSE_TEXT_END)
        self.assertEqual(out[base + offs[10]:], two_lines + bytes([ui.PAUSE_TEXT_END]) + last + bytes([ui.PAUSE_TEXT_END]))
        self.assertEqual(total, len(out))

    def test_texts_the_layout_cannot_hold_are_refused(self) -> None:
        tail = [b"\x41"] * 9 + [ui.PAUSE_SIGNATURE, b"\x42"]
        with self.assertRaises(ValueError):
            ui.pause_texts_with_goal_line(self.bank([bytes([0x41]) * (ui.GOAL_LINE_GLYPHS + 1)] + tail))
        with self.assertRaises(ValueError):
            ui.pause_texts_with_goal_line(self.bank([b"\x41\xfc\x41"] + tail))
        with self.assertRaises(ValueError):
            ui.pause_texts_with_goal_line(self.bank([b"\x41"] * 12))    # no signature at message 10
        with self.assertRaises(ValueError):
            ui.pause_texts_with_goal_line(self.bank([b"\x41"] + tail[:-1]))  # 11 messages: signature off by two

    def test_cave_knows_the_layout(self) -> None:
        """The cave tests the break and the end at the layout's offsets and reads the client's buffer."""
        cave = ui.GOAL_LINE_CAVE
        halfwords = {int.from_bytes(cave[i:i + 2], "little") for i in range(0, len(cave), 2)}
        self.assertIn(0x2300 | ui.GOAL_LINE_GLYPHS, halfwords)     # movs r3, #glyphs
        self.assertIn(0x2300 | ui.GOAL_LINE_BUF_LEN, halfwords)    # movs r3, #both lines
        words = {int.from_bytes(cave[i:i + 4], "little") for i in range(0, len(cave), 4)}
        self.assertIn(GOAL_LINE_ADDR, words)
        self.assertIn(int.from_bytes(ui.PAUSE_SIGNATURE, "little"), words)
        self.assertIn(0x2400 | 2 * ui.PAUSE_SIGNATURE_INDEX, halfwords)   # movs r4, #index * 2
        self.assertLessEqual(GOAL_LINE_ADDR + ui.GOAL_LINE_BUF_LEN, NOTIFY_ADDR)
