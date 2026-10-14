"""goal: defeat_omega_zero closes Slither Inc. for good and puts the goal requirements on Omega Zero's door."""
import unittest

from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS, reach, window_with
from .test_goal import collect_pool_but
from .. import MMZXWorld
from ..client.goal import GoalRequirement as ClientGoal
from ..client.items import wanted_progress_bits
from ..data import EVENT_GATES, EVENT_GATES_GOAL, GOAL_BITS_OMEGA, LOCATIONS, OMEGA_GATE
from ..goal import GOAL_OMEGA, GOAL_SERPENT
from ..locations import FINAL_AREA_LOCATIONS, PICKUP_OPTION_BY_CATEGORY
from ..logic import document as F
from ..rom import CFG_OMEGA_GOAL, omega

OMEGA = {"goal": "defeat_omega_zero"}
ARENA = "n01/omega-zero-arena"


def real_locations(multiworld) -> set[str]:
    return {loc.name for loc in multiworld.get_locations(1) if loc.address is not None}


def events(multiworld) -> dict[str, str]:
    return {loc.name: loc.item.name for loc in multiworld.get_locations(1) if loc.address is None}


class TestFinalArea(unittest.TestCase):
    def test_what_the_goal_drops(self) -> None:
        """Every location of D-4 and D-5 and the final mission; nothing of N-1."""
        self.assertIn(F.FINAL_MISSION, FINAL_AREA_LOCATIONS)
        self.assertTrue(all(LOCATIONS[n]["room"] in ("d04", "d05") for n in FINAL_AREA_LOCATIONS - {F.FINAL_MISSION}))
        self.assertEqual(len(FINAL_AREA_LOCATIONS), 10)
        self.assertFalse({n for n, v in LOCATIONS.items() if v["room"] == "n01"} & FINAL_AREA_LOCATIONS)


class TestSerpentGoal(MMZXTestBase):
    def test_victory_sits_on_the_final_mission(self) -> None:
        held = events(self.multiworld)
        self.assertEqual(held.get(F.VICTORY_LOCATION), F.VICTORY)
        self.assertNotIn(F.OMEGA_VICTORY_LOCATION, held)
        always = {n for n in FINAL_AREA_LOCATIONS
                  if LOCATIONS[n]["category"] not in PICKUP_OPTION_BY_CATEGORY and LOCATIONS[n].get("detect")}
        self.assertTrue(always and always <= real_locations(self.multiworld))

    def test_omega_zero_needs_only_a_model(self) -> None:
        """With Serpent as the goal, Omega Zero's arena ignores the goal requirements."""
        collect_pool_but(self, ["Model X"])
        self.assertTrue(self.can_reach_region(ARENA))
        self.assertFalse(self.can_reach_region("d04/d-2-entrance"))

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["goal"], GOAL_SERPENT)


class TestOmegaGoal(MMZXTestBase):
    options = OMEGA

    def test_slither_inc_is_gone(self) -> None:
        present = real_locations(self.multiworld)
        self.assertFalse(FINAL_AREA_LOCATIONS & present)
        regions = {r.name for r in self.multiworld.get_regions(1)}
        self.assertFalse({r for r in regions if r.split("/")[0] in ("d04", "d05")})
        self.assertEqual(len(self.multiworld.itempool), len(present))

    def test_victory_sits_in_the_arena(self) -> None:
        held = events(self.multiworld)
        self.assertEqual(held.get(F.OMEGA_VICTORY_LOCATION), F.VICTORY)
        self.assertNotIn(F.VICTORY_LOCATION, held)
        self.assertEqual(self.multiworld.get_location(F.OMEGA_VICTORY_LOCATION, 1).parent_region.name, ARENA)

    def test_the_door_follows_the_goal_requirements(self) -> None:
        """The six biometals by default: without Model X the arena, and the goal, stay closed."""
        collect_pool_but(self, ["Model X"])
        self.assertFalse(self.can_reach_region(ARENA))
        self.assertBeatable(False)
        self.collect_by_name("Model X")
        self.assertTrue(self.can_reach_region(ARENA))
        self.assertBeatable(True)

    def test_the_rest_of_area_n_is_open(self) -> None:
        collect_pool_but(self, ["Model X"])
        self.assertTrue(self.can_reach_location("N-1: Disk B-2"))
        self.assertTrue(self.can_reach_region("n01/omega-zero-door"))

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["goal"], GOAL_OMEGA)


class TestOmegaGoalOptions(unittest.TestCase):
    def test_boss_logic_on_omega_adds_up(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={**OMEGA, "boss_logic": {"Omega Zero": WITNESS}})
        self.assertFalse(reach(multiworld, without=[WITNESS])["victory"])
        self.assertTrue(reach(multiworld)["victory"])

    def test_disks_and_missions_count_too(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={**OMEGA, "goal_requirements": ["Secret Disks", "Missions"],
                                                          "required_secret_disks": 5, "total_secret_disks": 8,
                                                          "required_missions": 3})
        self.assertTrue(reach(multiworld)["victory"])
        self.assertFalse(reach(multiworld, without=["Secret Disk"])["victory"])

    def test_the_hunt_with_omega(self) -> None:
        """Omega Zero's door asks for the beaten bosses: with the Zero 3 ones behind the witness, no witness, no goal."""
        blocked = {"Hellbat Schilt": WITNESS, "Blazin' Flizard": WITNESS, "Deathtanz Mantisk": WITNESS, "Childre Inarabitta": WITNESS}
        multiworld = setup_multiworld(MMZXWorld, options={**OMEGA, "goal_requirements": ["Mutos Reploid Hunting"],
                                                          "required_mutos_reploids": 2, "zero3_bosses": True, "boss_logic": blocked})
        self.assertTrue(reach(multiworld)["victory"])
        self.assertFalse(reach(multiworld, without=[WITNESS])["victory"])

    def test_skip_boss_rush_changes_nothing(self) -> None:
        a = setup_multiworld(MMZXWorld, options=OMEGA)
        b = setup_multiworld(MMZXWorld, options={**OMEGA, "skip_boss_rush": True})
        self.assertEqual(real_locations(a), real_locations(b))
        self.assertEqual(reach(a)["locs"], reach(b)["locs"])


class TestClientOmega(unittest.TestCase):
    SLOT = {"goal": GOAL_OMEGA, "goal_requirements": {"models": ["Model X"], "models_count": 1, "secret_disks": 0,
                                                       "secret_disks_total": 0, "secret_disk_order": [], "missions": 0, "mutos": 0}}

    def test_the_door_bit_not_the_slither_gate(self) -> None:
        goal = ClientGoal(self.SLOT)
        self.assertTrue(goal.omega)
        self.assertEqual(goal.gate_bits(), {tuple(EVENT_GATES[OMEGA_GATE])})
        slither = {tuple(EVENT_GATES[fl]) for fl in EVENT_GATES_GOAL}
        opened, _keys = wanted_progress_bits({"Model X": 1}, goal, 0)
        self.assertIn(tuple(EVENT_GATES[OMEGA_GATE]), opened)
        self.assertFalse(slither & opened)
        closed, _keys = wanted_progress_bits({}, goal, 0)
        self.assertNotIn(tuple(EVENT_GATES[OMEGA_GATE]), closed)
        self.assertEqual(goal.open_notice()[1], "Omega Zero door open")
        self.assertIn("Door of Omega Zero's arena: closed", goal.report({}, set(), set()))

    def test_serpent_keeps_the_slither_gate(self) -> None:
        goal = ClientGoal({**self.SLOT, "goal": GOAL_SERPENT})
        self.assertFalse(goal.omega)
        self.assertEqual(goal.gate_bits(), {tuple(EVENT_GATES[fl]) for fl in EVENT_GATES_GOAL})
        self.assertEqual(goal.open_notice()[1], "final area open")

    def test_the_goal_flag(self) -> None:
        self.assertTrue(window_with(GOAL_BITS_OMEGA).all_set(GOAL_BITS_OMEGA))
        self.assertFalse(window_with([]).all_set(GOAL_BITS_OMEGA))


class TestOmegaPatch(unittest.TestCase):
    def test_door_key_type_and_flag(self) -> None:
        """Key type 6 of the door table takes the door flag; the arena's door gets a template of its own."""
        self.assertEqual(omega.OMEGA_FLAG_RAM, omega.DOOR_FLAGS_RAM + 6 * 4)
        self.assertEqual(int.from_bytes(omega.OMEGA_FLAG_NEW, "little"), OMEGA_GATE)
        locked = omega.locked_template()
        self.assertEqual(len(locked), 12)
        self.assertEqual(locked[3], 0x60)
        self.assertEqual(locked[:3] + locked[4:], omega.OMEGA_DOOR_TEMPLATE[:3] + omega.OMEGA_DOOR_TEMPLATE[4:])
        self.assertTrue(CFG_OMEGA_GOAL)
