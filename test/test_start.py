"""Where a new game starts: the starting_transerver option and its data."""
import io
import unittest

from .bases import MMZXTestBase
from .test_access import ACCESS_X_LOCATIONS
from .test_regions import RegionsReachable
from ..rom.golden import (BLOCK_MIRROR, BLOCK_OFF, OFF_SCENE_WORD, OFF_SPAWN_X, OFF_SPAWN_Y,
                          PLAYER_MIRROR, TRANSERVER_BITS, build_image)
from ..data import ITEMS, LIVE_BLOCK, ROOM_SUBAREA, SCENE_WORDS, STARTING_MODELS, STARTING_TRANSERVERS
from ..logic.rules import ROOM_NAMES
from ..options import StartingTranserver


def u32(img: bytes, off: int) -> int:
    return int.from_bytes(img[off:off + 4], "little")


class TestStartingPoints(unittest.TestCase):
    """The option and the data table describe the same starting points."""

    def test_option_values_match_the_table(self) -> None:
        self.assertEqual(set(StartingTranserver.name_lookup.values()), set(STARTING_TRANSERVERS))
        self.assertEqual(StartingTranserver.name_lookup[StartingTranserver.default],
                         next(iter(STARTING_TRANSERVERS)))

    def test_old_names_still_work(self) -> None:
        self.assertEqual(StartingTranserver.from_text("guardian_hub").value, StartingTranserver.option_area_a)
        self.assertEqual(StartingTranserver.from_text("area_x").value, StartingTranserver.option_guardian_base)

    def test_records_are_consistent(self) -> None:
        for key, rec in STARTING_TRANSERVERS.items():
            with self.subTest(start=key):
                self.assertIn(rec["room"], ROOM_NAMES)
                self.assertEqual(ROOM_SUBAREA[rec["room"]], rec["sub"])
                if rec["access"]:
                    self.assertEqual(ITEMS[rec["access"]]["grant"][0], "transerver")

    def test_image_spawns_at_the_start_point(self) -> None:
        for key, rec in STARTING_TRANSERVERS.items():
            with self.subTest(start=key):
                img = build_image("model_zx", 0, STARTING_MODELS, rec)
                for off in (OFF_SPAWN_X, OFF_SPAWN_X + PLAYER_MIRROR):
                    self.assertEqual(u32(img, off) >> 8, rec["x"])
                for off in (OFF_SPAWN_Y, OFF_SPAWN_Y + PLAYER_MIRROR):
                    self.assertEqual(u32(img, off) >> 8, rec["y"])
                self.assertEqual(u32(img, OFF_SCENE_WORD), SCENE_WORDS[rec["sub"]])

    def test_image_knows_only_the_starting_destination(self) -> None:
        """Of the Transport destinations, the image sets the starting floor's bit and no other."""
        for key, rec in STARTING_TRANSERVERS.items():
            with self.subTest(start=key):
                img = build_image("model_zx", 0, STARTING_MODELS, rec)
                grant = ITEMS[rec["access"]]["grant"]
                for addr, bit in TRANSERVER_BITS:
                    off = BLOCK_OFF + addr - LIVE_BLOCK
                    for o in (off, off + BLOCK_MIRROR):
                        self.assertEqual(bool(img[o] & (1 << bit)), (addr, bit) == (grant[1], grant[2]),
                                         "0x%08X bit %d" % (addr, bit))


class TestGuardianBaseStart(RegionsReachable, MMZXTestBase):
    options = {"starting_transerver": "guardian_base"}

    def test_area_x_access_is_granted_instead_of_area_a(self) -> None:
        precollected = sorted(item.name for item in self.multiworld.precollected_items[1])
        self.assertEqual(precollected, ["Model ZX", "Transerver Access - Area X"])
        names = {item.name for item in self.multiworld.itempool}
        self.assertIn("Transerver Access - Area A", names)
        self.assertNotIn("Transerver Access - Area X", names)

    def test_only_area_x_in_logic_at_the_start(self) -> None:
        """Sphere 0 is the Guardian base: the hub warp to X-1 is open, every other warp closed."""
        self.assertTrue(self.can_reach_entrance("z01 transerver to x01"))
        self.assertFalse(self.can_reach_entrance("z01 transerver to a02"))
        reachable = {loc.name for loc in self.multiworld.get_locations(1)
                     if loc.address is not None and loc.can_reach(self.multiworld.state)}
        self.assertEqual(reachable, {n for n in ACCESS_X_LOCATIONS if n.startswith("X-")})

    def test_area_a_opens_with_its_access(self) -> None:
        self.assertFalse(self.can_reach_location("A-2: Disk B-3"))
        self.collect_by_name("Transerver Access - Area A")
        self.assertTrue(self.can_reach_entrance("z01 transerver to a02"))
        self.assertTrue(self.can_reach_location("A-2: Disk B-3"))


class TestSpoilerHeader(MMZXTestBase):
    options = {"starting_transerver": "guardian_base", "boss_logic": {"Hivolt": "HX"}}

    def test_header_names_the_start_and_the_boss_logic(self) -> None:
        buf = io.StringIO()
        self.world.write_spoiler_header(buf)
        text = buf.getvalue()
        self.assertIn("Start: guardian_base (", text)
        self.assertIn("Transerver Access - Area X", text)
        self.assertIn("Hivolt: HX", text)
