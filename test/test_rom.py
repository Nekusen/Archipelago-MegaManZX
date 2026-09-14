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
from ..data import NOTIFY_ADDR, NOTIFY_BUF_MAX, PICKUP_MAILBOX_ADDR, PICKUP_MAILBOX_SLOTS
from ..rom import arm9, blz, nds, pickups, sprites, ui

PATCH_MODULES = (pickups, sprites, ui)     # the modules that hold patch tables and caves
ARM9_RAM = (0x02000000, 0x02400000)
# Zero stretches of the vanilla ARM9 that take the caves.
FREE_STRETCHES = [(0x020CB434, 0x020CB9D4), (0x020C8150, sprites.GFX_CAVES_END)]
ROM_PATH = os.environ.get("MMZX_ROM") or str(Path(__file__).resolve().parents[3] / "roms" / "mmzx_us.nds")


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
        blocks["PICKUP_MAILBOX"] = (PICKUP_MAILBOX_ADDR, 4 + 4 * PICKUP_MAILBOX_SLOTS)
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
        """write_patch_tokens stores the marker with the slot name and the option blob."""
        patch = rom.MMZXPatch(player=1, player_name="Tester")
        rom.write_patch_tokens(patch, "Tester", "seed-1", (0, 1, 0), hu_in_pool=True)
        tokens = patch.get_file("token_data.bin")
        self.assertIn(rom.AP_MAGIC, tokens)
        self.assertIn(b"Tester", tokens)
        self.assertIn(b"seed-1", tokens)
        self.assertEqual(patch.get_file("mmzx_cfg.bin")[0] & rom.CFG_HU_IN_POOL, rom.CFG_HU_IN_POOL)
        patch = rom.MMZXPatch(player=1, player_name="Tester")
        rom.write_patch_tokens(patch, "Tester", "seed-1", (0, 1, 0))
        self.assertEqual(patch.get_file("mmzx_cfg.bin")[0] & rom.CFG_HU_IN_POOL, 0)


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

    def test_caves_land_on_zeros(self) -> None:
        for lo, hi in FREE_STRETCHES:
            with self.subTest(stretch=hex(lo)):
                self.assertEqual(self.read(lo, hi - lo), bytes(hi - lo))

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
