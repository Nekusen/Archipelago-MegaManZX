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
from ..data import (GOAL_LINE_ADDR, ICON_CODES, LOCATIONS, NOTIFY_ADDR, NOTIFY_BUF_MAX, PICKUP_TABLE_ADDR,
                    STARTING_MODELS, STARTING_TRANSERVERS)
from ..rom import arm9, blz, golden, nds, pickups, sprites, table, ui

PATCH_MODULES = (pickups, sprites, ui)     # the modules that hold patch tables and caves
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
