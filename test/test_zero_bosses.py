"""zero3_bosses / zero4_bosses: the Mega Man Zero bosses of N-1 as checks, their rooms in the logic,
boss_logic on them, and the Mutos Reploid Hunting goal requirement."""
import unittest
from collections import Counter

from Options import OptionError
from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS, reach, window_with
from .test_goal import collect_pool_but
from .. import MMZXWorld
from ..client.goal import GoalRequirement as ClientGoal, mutos_beaten
from ..client.items import wanted_progress_bits
from ..data import EVENT_GATES, EVENT_GATES_GOAL, LOCATIONS, ZERO_BOSSES
from ..goal import MUTOS_EVENTS, REQ_MUTOS, defeated_event
from ..locations import ZERO_OPTION_BY_CATEGORY
from ..logic import bosses
from ..logic import document as F
from ..rom import CFG_ZERO3, CFG_ZERO4, zero

ZERO3 = {n for n, v in LOCATIONS.items() if v["category"] == "zero3_boss"}
ZERO4 = {n for n, v in LOCATIONS.items() if v["category"] == "zero4_boss"}
BOTH = {"zero3_bosses": True, "zero4_bosses": True}
ARENAS = {boss: F.region_name(room, rid) for (room, rid), boss in F.boss_regions(F.normalize_logic(
    __import__("json").loads(__import__("pkgutil").get_data("worlds.mmzx.logic", "logic.json").decode("utf-8")))).items()
          if F.BOSSES[boss].get("game")}


def real_locations(multiworld) -> set[str]:
    return {loc.name for loc in multiworld.get_locations(1) if loc.address is not None}


def events(multiworld) -> set[str]:
    return {loc.name for loc in multiworld.get_locations(1) if loc.address is None}


class TestData(unittest.TestCase):
    def test_eight_bosses_four_per_game(self) -> None:
        self.assertEqual(len(ZERO_BOSSES), 8)
        self.assertEqual(Counter(v["game"] for v in ZERO_BOSSES.values()), {3: 4, 4: 4})
        self.assertEqual(len(ZERO3), 4)
        self.assertEqual(len(ZERO4), 4)
        for bid, v in ZERO_BOSSES.items():
            self.assertEqual(LOCATIONS[v["location"]]["boss"], bid)
            self.assertEqual(LOCATIONS[v["location"]]["detect"], ["bit", *v["flag"]])
            self.assertEqual(F.BOSSES[bid]["name"], v["name"])
            self.assertEqual(F.BOSSES[bid]["game"], v["game"])
        self.assertEqual(len({tuple(v["flag"]) for v in ZERO_BOSSES.values()}), 8)

    def test_every_boss_has_an_arena_tagged(self) -> None:
        self.assertEqual(set(ARENAS), set(ZERO_BOSSES))

    def test_the_sets_the_patch_converts(self) -> None:
        """Twelve sets of Zero 3 and twenty of Zero 4, each in one of the two tables."""
        self.assertEqual((len(zero.SETS[zero.ZERO3]), len(zero.SETS[zero.ZERO4])), (12, 20))
        self.assertTrue(all(table in (0, 1) for sets in zero.SETS.values() for table in sets.values()))
        self.assertEqual(len(zero.ROM_MD5S[zero.ZERO3]), 3)
        self.assertEqual(len(zero.ROM_MD5S[zero.ZERO4]), 3)

    def test_loader_and_table_fit_the_converter(self) -> None:
        """The loader, a full table of thirty-two slices and its end mark fit the code they replace."""
        entries = 32 + 1
        self.assertLessEqual(len(zero.ZERO_LOADER) + entries * 20, zero.ZERO_REGION_LEN)
        self.assertEqual(zero.ZERO_TABLE_RAM % 4, 0)
        self.assertEqual(zero.ZERO_TABLE_RAM, zero.ZERO_LOADER_RAM + len(zero.ZERO_LOADER))

    def test_a_rom_of_another_game_is_refused(self) -> None:
        fake = bytearray(zero.ROM_SIZES[zero.ZERO3])
        fake[zero.GAME_CODE_OFF:zero.GAME_CODE_OFF + 4] = b"B4ZE"
        with self.assertRaises(ValueError):
            zero.check_rom(bytes(fake), zero.ZERO3)
        fake[zero.GAME_CODE_OFF:zero.GAME_CODE_OFF + 4] = b"BZ3P"
        zero.check_rom(bytes(fake), zero.ZERO3)


class TestOff(MMZXTestBase):
    def test_no_zero_locations_nor_rooms(self) -> None:
        """Off by default: no boss location, no Defeated event, and the capsule rooms are not regions."""
        self.assertFalse((ZERO3 | ZERO4) & real_locations(self.multiworld))
        self.assertFalse(set(MUTOS_EVENTS) & {loc.item.name for loc in self.multiworld.get_locations(1) if loc.address is None})
        regions = {r.name for r in self.multiworld.get_regions(1)}
        self.assertFalse(set(ARENAS.values()) & regions)
        self.assertNotIn("n01/zero3-capsules", regions)

    def test_slot_data_and_cfg(self) -> None:
        slot = self.world.fill_slot_data()
        self.assertFalse(slot["zero3_bosses"])
        self.assertFalse(slot["zero4_bosses"])


class TestZero3Only(MMZXTestBase):
    options = {"zero3_bosses": True}

    def test_only_the_zero_3_bosses(self) -> None:
        present = real_locations(self.multiworld)
        self.assertTrue(ZERO3 <= present)
        self.assertFalse(ZERO4 & present)
        regions = {r.name for r in self.multiworld.get_regions(1)}
        self.assertIn("n01/zero3-capsules", regions)
        self.assertNotIn("n01/zero4-capsules", regions)

    def test_the_bosses_sit_in_their_arenas(self) -> None:
        """Each location lies in its boss' arena, reached from the capsule room with any model."""
        collect_pool_but(self, [])
        for bid, arena in ARENAS.items():
            if ZERO_BOSSES[bid]["game"] == 3:
                location = self.multiworld.get_location(ZERO_BOSSES[bid]["location"], 1)
                self.assertEqual(location.parent_region.name, arena)
                self.assertTrue(self.can_reach_location(location.name), location.name)

    def test_defeated_events(self) -> None:
        held = events(self.multiworld)
        for bid, v in ZERO_BOSSES.items():
            self.assertEqual(defeated_event(bid) in held, v["game"] == 3, bid)


class TestBothGames(MMZXTestBase):
    options = BOTH

    def test_all_eight(self) -> None:
        self.assertTrue((ZERO3 | ZERO4) <= real_locations(self.multiworld))
        self.assertTrue(set(MUTOS_EVENTS) <= events(self.multiworld))
        self.assertEqual(len(self.multiworld.itempool), len(real_locations(self.multiworld)))

    def test_slot_data(self) -> None:
        slot = self.world.fill_slot_data()
        self.assertTrue(slot["zero3_bosses"] and slot["zero4_bosses"])


class TestBossLogicOnZeroBosses(unittest.TestCase):
    def test_requirement_closes_its_arena_when_on(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={**BOTH, "boss_logic": {"Sol Titanion": WITNESS}})
        off, on = reach(multiworld, without=[WITNESS]), reach(multiworld)
        self.assertNotIn("N-1: Sol Titanion", off["locs"])
        self.assertIn("N-1: Sol Titanion", on["locs"])
        self.assertEqual(len(on["locs"] - off["locs"]), 1)

    def test_requirement_is_ignored_when_off(self) -> None:
        """A requirement on a boss whose option is off is accepted and changes nothing."""
        multiworld = setup_multiworld(MMZXWorld, options={"boss_logic": {"Hellbat Schilt": WITNESS, "Fenri Lunaedge": "OX"}})
        self.assertEqual(reach(multiworld, without=[WITNESS])["locs"], reach(multiworld)["locs"])

    def test_the_room_names_omega_zero_alone(self) -> None:
        self.assertEqual(bosses.resolve_boss("N-1"), "omega_zero")
        self.assertEqual(bosses.resolve_boss("Blazin' Flizard"), "blazin_flizard")
        self.assertEqual(bosses.resolve_boss("deathtanz mantisk"), "deathtanz_mantisk")


class TestMutosHunt(unittest.TestCase):
    def test_needs_the_bosses_on(self) -> None:
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"goal_requirements": [REQ_MUTOS], "required_mutos_reploids": 1})
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"goal_requirements": [REQ_MUTOS], "required_mutos_reploids": 5,
                                                 "zero4_bosses": True})

    def test_four_with_one_game(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={"goal_requirements": [REQ_MUTOS], "required_mutos_reploids": 4,
                                                          "zero3_bosses": True})
        self.assertTrue(reach(multiworld)["victory"])
        self.assertEqual(multiworld.worlds[1].goal.mutos_required, 4)

    def test_the_hunt_counts_in_the_logic(self) -> None:
        """Victory needs the bosses' events, which need their arenas: with every boss behind the
        witness, six of them are beaten only with it."""
        blocked = {v["name"]: WITNESS for v in ZERO_BOSSES.values()}
        multiworld = setup_multiworld(MMZXWorld, options={"goal_requirements": [REQ_MUTOS], "required_mutos_reploids": 6,
                                                          "boss_logic": blocked, **BOTH})
        self.assertTrue(reach(multiworld)["victory"])
        self.assertFalse(reach(multiworld, without=[WITNESS])["victory"])

    def test_the_count_is_what_it_says(self) -> None:
        """Two bosses open and two required: the goal is in; three required: it is not."""
        blocked = {v["name"]: WITNESS for v in ZERO_BOSSES.values() if v["name"] not in ("Hellbat Schilt", "Sol Titanion")}
        for required, expected in ((2, True), (3, False)):
            multiworld = setup_multiworld(MMZXWorld, options={"goal_requirements": [REQ_MUTOS], "required_mutos_reploids": required,
                                                              "boss_logic": blocked, **BOTH})
            self.assertEqual(reach(multiworld, without=[WITNESS])["victory"], expected, required)

    def test_slot_data_round_trip(self) -> None:
        from ..goal import from_slot_data, slot_data
        world = setup_multiworld(MMZXWorld, options={"goal_requirements": [REQ_MUTOS, "Biometals"],
                                                     "required_mutos_reploids": 3, "zero4_bosses": True}).worlds[1]
        goal, _order = from_slot_data(slot_data(world.goal, world.disk_order))
        self.assertEqual(vars(goal), vars(world.goal))
        self.assertEqual(goal.mutos_required, 3)


class TestClientHunt(unittest.TestCase):
    SLOT = {"goal": 0, "goal_requirements": {"models": [], "models_count": 0, "secret_disks": 0, "secret_disks_total": 0,
                                             "secret_disk_order": [], "missions": 0, "mutos": 3}}

    def test_beaten_bosses_from_the_flags(self) -> None:
        flags = [tuple(ZERO_BOSSES[b]["flag"]) for b in ("hellbat_schilt", "sol_titanion")]
        self.assertEqual(mutos_beaten(window_with(flags)), {"Hellbat Schilt", "Sol Titanion"})
        self.assertEqual(mutos_beaten(window_with([])), set())

    def test_the_gate_opens_with_the_count(self) -> None:
        goal = ClientGoal(self.SLOT)
        self.assertTrue(goal.wants_mutos)
        self.assertFalse(goal.met({}, 0, 2))
        self.assertTrue(goal.met({}, 0, 3))
        gate = {tuple(EVENT_GATES[fl]) for fl in EVENT_GATES_GOAL}
        self.assertFalse(gate & wanted_progress_bits({}, goal, 0, mutos=2)[0])
        self.assertTrue(gate <= wanted_progress_bits({}, goal, 0, mutos=3)[0])

    def test_pause_line_and_report(self) -> None:
        goal = ClientGoal(self.SLOT)
        self.assertEqual(goal.progress_lines({}, 0, 1), ("", "Mutos 1/3"))
        four = ClientGoal({"goal": 0, "goal_requirements": {"models": ["Model X"], "models_count": 1, "secret_disks": 20,
                                                              "secret_disks_total": 30, "secret_disk_order": [], "missions": 14, "mutos": 8}})
        first, second = four.progress_lines({}, 14, 8)
        self.assertEqual((first, second), ("Disks 00/20  Models 0/1", "Missions 14/14  Mutos 8/8"))
        self.assertLessEqual(max(len(first), len(second)), 30)
        self.assertIn("Mutos Reploids: 1 of 3 beaten (Sol Titanion)", goal.report({}, set(), {"Sol Titanion"}))
        self.assertIn("Mutos Reploids: 3 of the Mega Man Zero bosses required (progress is read in game)", goal.report({}, None, None))


class TestPatchFlags(unittest.TestCase):
    def test_cfg_bits_are_distinct(self) -> None:
        from ..rom import CFG_HU_IN_POOL, CFG_OMEGA_GOAL, CFG_STORY_ITEMS, CFG_STORY_ON
        bits = [CFG_HU_IN_POOL, CFG_STORY_ITEMS, CFG_STORY_ON, CFG_ZERO3, CFG_ZERO4, CFG_OMEGA_GOAL]
        self.assertEqual(len(set(bits)), len(bits))
        self.assertTrue(all(b & (b - 1) == 0 for b in bits))

    def test_locations_follow_their_option(self) -> None:
        self.assertEqual(set(ZERO_OPTION_BY_CATEGORY.values()), {"zero3_bosses", "zero4_bosses"})
