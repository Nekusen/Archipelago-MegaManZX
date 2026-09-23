"""The goal requirements: which models, how many, the Secret Disk hunt and the mission count."""
import unittest
from collections import Counter

from BaseClasses import ItemClassification
from Options import OptionError
from test.general import setup_multiworld

from .bases import MMZXTestBase
from .test_goal import collect_pool_but
from .. import MMZXWorld
from ..client.goal import GoalRequirement as ClientGoal
from ..goal import DISK_ITEM, MISSION_COUNT, describe

DISKS_ONLY = {"goal_requirements": ["Secret Disks"]}
BOTH = {"goal_requirements": ["Biometals", "Secret Disks"], "required_secret_disks": 4, "total_secret_disks": 6}
MISSIONS_ONLY = {"goal_requirements": ["Missions"], "required_missions": 13}
ALL_THREE = {"goal_requirements": ["Biometals", "Secret Disks", "Missions"],
             "required_secret_disks": 4, "total_secret_disks": 6, "required_missions": 3}


class TestDisksOnly(MMZXTestBase):
    options = DISKS_ONLY

    def test_disks_in_pool(self) -> None:
        """The default hunt puts 30 disks in the pool, all progression that balancing skips."""
        disks = [item for item in self.multiworld.itempool if item.name == DISK_ITEM]
        self.assertEqual(len(disks), 30)
        for item in disks:
            self.assertTrue(item.advancement)
            self.assertTrue(item.classification & ItemClassification.skip_balancing)
            self.assertTrue(item.classification & ItemClassification.deprioritized)

    def test_models_do_not_matter(self) -> None:
        """Without the Biometals requirement the models never close the goal."""
        collect_pool_but(self, ["Model X", "Progressive Model HX"])
        self.assertBeatable(True)

    def test_required_count(self) -> None:
        """19 disks are not enough; the 20th opens the goal."""
        collect_pool_but(self, [DISK_ITEM])
        disks = self.get_items_by_name(DISK_ITEM)
        self.collect(disks[:19])
        self.assertBeatable(False)
        self.collect(disks[19])
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        g = self.world.fill_slot_data()["goal_requirements"]
        self.assertEqual(g["models"], [])
        self.assertEqual((g["secret_disks"], g["secret_disks_total"]), (20, 30))
        self.assertEqual(sorted(g["secret_disk_order"]), list(range(95)))


class TestBoth(MMZXTestBase):
    options = BOTH

    def test_both_needed(self) -> None:
        collect_pool_but(self, [DISK_ITEM, "Model X"])
        disks = self.get_items_by_name(DISK_ITEM)
        self.assertEqual(len(disks), 6)
        self.collect(disks[:4])
        self.assertBeatable(False)
        self.collect_by_name("Model X")
        self.assertBeatable(True)

    def test_disks_alone_do_not_open_the_gate(self) -> None:
        collect_pool_but(self, ["Model X"])
        self.assertBeatable(False)

    def test_few_disks_stay_eligible_for_priority(self) -> None:
        """A small hunt keeps its disks off the deprioritized flag."""
        item = self.get_item_by_name(DISK_ITEM)
        self.assertFalse(item.classification & ItemClassification.deprioritized)


class TestModelsSubset(MMZXTestBase):
    options = {"required_models": ["Model HX", "Model FX", "Model LX", "Model PX"]}

    def test_only_the_listed_models(self) -> None:
        collect_pool_but(self, ["Model X", "Progressive Model FX"])
        self.assertBeatable(False)
        self.collect(self.get_items_by_name("Progressive Model FX")[0])
        self.assertBeatable(True)


class TestAnyFour(MMZXTestBase):
    options = {"required_models_count": 4}

    def test_any_four_of_six(self) -> None:
        """Four models of the six open the gate, whichever they are; ZX is the start."""
        collect_pool_but(self, ["Model X", "Progressive Model HX"])
        self.assertBeatable(True)

    def test_three_are_not_enough(self) -> None:
        collect_pool_but(self, ["Model X", "Progressive Model HX", "Progressive Model FX"])
        self.assertBeatable(False)


class TestOmegaInList(MMZXTestBase):
    options = {"required_models": ["Model X", "Model OX"]}

    def test_ox_counts(self) -> None:
        collect_pool_but(self, ["Model OX"])
        self.assertBeatable(False)
        self.collect_by_name("Model OX")
        self.assertBeatable(True)


class TestEmptyRequirements(unittest.TestCase):
    def test_empty_list_fails(self) -> None:
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"goal_requirements": []})

    def test_biometals_without_models_fails(self) -> None:
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"required_models": []})

    def test_no_disks_without_the_hunt(self) -> None:
        multiworld = setup_multiworld(MMZXWorld)
        self.assertEqual(Counter(item.name for item in multiworld.itempool)[DISK_ITEM], 0)


class TestClamps(unittest.TestCase):
    def test_total_raised_to_required(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={
            "goal_requirements": ["Secret Disks"], "required_secret_disks": 40, "total_secret_disks": 10})
        world = multiworld.worlds[1]
        self.assertEqual((world.goal.disks_required, world.goal.disks_total), (40, 40))
        self.assertEqual(sum(1 for i in multiworld.itempool if i.name == DISK_ITEM), 40)

    def test_total_lowered_to_the_pool(self) -> None:
        """95 required and 95 in the pool exceed the free slots of the default pool: the total shrinks."""
        multiworld = setup_multiworld(MMZXWorld, options={
            "goal_requirements": ["Secret Disks"], "required_secret_disks": 50, "total_secret_disks": 95})
        world = multiworld.worlds[1]
        real = sum(1 for loc in multiworld.get_locations(1) if loc.address is not None)
        free = real - len(world.fixed_items()[0])
        self.assertLess(free, 95)
        self.assertEqual(world.goal.disks_total, free)
        self.assertEqual(len(multiworld.itempool), real)

    def test_count_above_the_list_means_all(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={
            "required_models": ["Model X", "Model ZX"], "required_models_count": 7})
        self.assertEqual(multiworld.worlds[1].goal.models_count, 2)

    def test_pool_still_fits(self) -> None:
        for options in (DISKS_ONLY, BOTH):
            with self.subTest(options=options):
                multiworld = setup_multiworld(MMZXWorld, options=options)
                real = sum(1 for loc in multiworld.get_locations(1) if loc.address is not None)
                self.assertEqual(len(multiworld.itempool), real)


class TestMissionsOnly(MMZXTestBase):
    options = MISSIONS_ONLY

    def test_slot_data(self) -> None:
        g = self.world.fill_slot_data()["goal_requirements"]
        self.assertEqual((g["models"], g["secret_disks"], g["missions"]), ([], 0, 13))

    def test_models_do_not_matter(self) -> None:
        collect_pool_but(self, ["Model X", "Progressive Model HX"])
        self.assertBeatable(True)

    def test_thirteen_reachable_missions_are_enough(self) -> None:
        """Without the Blue Card Key one mission is out of reach: the 13 left are the count."""
        collect_pool_but(self, ["Blue Card Key"])
        self.assertBeatable(True)

    def test_twelve_are_not(self) -> None:
        """Area X's access gates Protect HQ too: two missions out of reach close the goal."""
        collect_pool_but(self, ["Blue Card Key", "Transerver Access - Area X"])
        self.assertBeatable(False)
        self.collect_by_name("Blue Card Key")
        self.assertBeatable(True)


class TestEveryMission(MMZXTestBase):
    options = {"goal_requirements": ["Missions"], "required_missions": "all"}

    def test_all_means_every_counted_mission(self) -> None:
        self.assertEqual(MISSION_COUNT, 14)
        self.assertEqual(self.world.goal.missions_required, MISSION_COUNT)
        collect_pool_but(self, ["Blue Card Key"])
        self.assertBeatable(False)
        self.collect_by_name("Blue Card Key")
        self.assertBeatable(True)


class TestMissionsDefault(MMZXTestBase):
    options = {"goal_requirements": ["Missions"]}

    def test_eight_by_default(self) -> None:
        self.assertEqual(self.world.goal.missions_required, 8)
        self.assertEqual(self.world.fill_slot_data()["goal_requirements"]["missions"], 8)


class TestAllThree(MMZXTestBase):
    options = ALL_THREE

    def test_each_requirement_is_needed(self) -> None:
        collect_pool_but(self, [DISK_ITEM, "Model X"])
        self.assertBeatable(False)
        self.collect(self.get_items_by_name(DISK_ITEM)[:4])
        self.assertBeatable(False)
        self.collect_by_name("Model X")
        self.assertBeatable(True)

    def test_spoiler_line(self) -> None:
        self.assertEqual(describe(self.world.goal),
                         "6 of Model X, Model ZX, Progressive Model HX, Progressive Model FX, "
                         "Progressive Model LX, Progressive Model PX; 4 Secret Disks (6 in the pool); "
                         "3 of the 14 story missions")


class TestProgressLines(unittest.TestCase):
    """The pause menu lines the client writes: what fits shares the reserved line, three take both."""

    @staticmethod
    def lines(slot, counts, missions):
        return ClientGoal({"goal_requirements": slot}).progress_lines(counts, missions)

    def test_two_share_the_reserved_line(self) -> None:
        slot = {"models": ["Model X"], "models_count": 1, "secret_disks": 20, "secret_disks_total": 30}
        self.assertEqual(self.lines(slot, {"Model X": 1, DISK_ITEM: 7}, 0), ("", "Disks 07/20  Models 1/1"))

    def test_three_take_both_lines(self) -> None:
        slot = {"models": ["Model X"], "models_count": 1, "secret_disks": 20, "secret_disks_total": 30,
                "missions": 14}
        first, second = self.lines(slot, {"Model X": 1, DISK_ITEM: 7}, 8)
        self.assertEqual((first, second), ("Disks 07/20  Models 1/1", "Missions 08/14"))

    def test_missions_alone(self) -> None:
        self.assertEqual(self.lines({"missions": 8}, {}, 3), ("", "Missions 3/8"))

    def test_the_widest_texts_fit(self) -> None:
        slot = {"models": list(ClientGoal({}).models) + ["Model OX"], "models_count": 7,
                "secret_disks": 95, "secret_disks_total": 95, "missions": 14}
        for line in self.lines(slot, {DISK_ITEM: 95}, 14):
            self.assertLessEqual(len(line), 30)
