"""include_warps_in_logic: the teleports to the Guardian Base that end two missions count as ways into Area X."""
import unittest

from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS, reach
from .. import MMZXWorld
from ..data import MISSION_WARPS
from ..logic import document as F
from ..logic import rules as R

ACCESS_X = "Transerver Access - Area X"
AREA_X = {region for region in R.REGIONS if F.area_of(region) == "x"}
# the boss each mission's warp lies behind
BOSS_OF = {"Troop Reinforcement": "Model Z", "Repel The Army": "Prometheus & Pandora"}


def warps_of(multiworld) -> set:
    return {entrance.name for entrance in multiworld.get_entrances(1) if " warp after " in entrance.name}


class TestWarpsOff(MMZXTestBase):
    def test_area_x_needs_its_access(self) -> None:
        """Off, the default: no warp entrance exists and Area X is out of logic without its Transerver Access."""
        self.assertEqual(warps_of(self.multiworld), set())
        self.assertFalse(AREA_X & reach(self.multiworld, without=[ACCESS_X])["regions"])
        self.assertTrue(AREA_X <= reach(self.multiworld)["regions"])


class TestWarpsOn(MMZXTestBase):
    options = {"include_warps_in_logic": True}

    def test_each_warp_leads_from_its_mission_into_its_landing_room(self) -> None:
        self.assertEqual(len(warps_of(self.multiworld)), len(MISSION_WARPS))
        for name in warps_of(self.multiworld):
            entrance = self.multiworld.get_entrance(name, 1)
            mission = name.split(" warp after ")[1]
            with self.subTest(mission=mission):
                check = self.multiworld.get_location(F.MISSION_PREFIX + mission, 1)
                self.assertEqual(entrance.parent_region.name, check.parent_region.name)
                self.assertEqual(entrance.connected_region.name, MISSION_WARPS[mission])

    def test_area_x_is_in_logic_without_its_access(self) -> None:
        self.assertTrue(AREA_X <= reach(self.multiworld, without=[ACCESS_X])["regions"])

    def test_nothing_else_changes(self) -> None:
        reference = reach(setup_multiworld(MMZXWorld))
        with_warps = reach(self.multiworld)
        self.assertEqual(reference["regions"], with_warps["regions"])
        self.assertEqual(reference["locs"], with_warps["locs"])


class TestWarpsNeedTheMission(unittest.TestCase):
    def test_a_warp_needs_its_mission_and_one_mission_is_enough(self) -> None:
        """With neither boss beatable the warps give nothing; with one of them Area X is in logic."""
        blocked = {boss: WITNESS for boss in BOSS_OF.values()}
        seed = setup_multiworld(MMZXWorld, options={"include_warps_in_logic": True, "boss_logic": blocked})
        self.assertFalse(AREA_X & reach(seed, without=[ACCESS_X, WITNESS])["regions"])
        for mission, boss in BOSS_OF.items():
            with self.subTest(blocked=mission):
                seed = setup_multiworld(MMZXWorld, options={"include_warps_in_logic": True, "boss_logic": {boss: WITNESS}})
                self.assertTrue(AREA_X <= reach(seed, without=[ACCESS_X, WITNESS])["regions"])
