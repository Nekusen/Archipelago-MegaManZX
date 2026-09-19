"""progressive_models off (one full item per biometal) and require_full_models for the goal."""
import unittest
from collections import Counter

from BaseClasses import CollectionState

from .bases import MMZXTestBase
from .test_goal import collect_pool_but
from ..data import ITEMS, LIVE_BLOCK, STARTING_MODELS
from ..rom.golden import BLOCK_OFF, build_image


class TestGoldenImageFullModels(unittest.TestCase):
    def test_starting_hx_owns_both_halves(self) -> None:
        """Without progressive models the starting save holds the second half of HX too."""
        half2 = ITEMS["Progressive Model HX"]["grant"][1][1]
        off, bit = BLOCK_OFF + (half2[0] - LIVE_BLOCK), half2[1]
        halves = build_image("model_hx", 0, STARTING_MODELS)
        full = build_image("model_hx", 0, STARTING_MODELS, full_models=True)
        self.assertFalse(halves[off] & (1 << bit))
        self.assertTrue(full[off] & (1 << bit))

FULL = {"progressive_models": False}


class TestFullModels(MMZXTestBase):
    options = FULL

    def test_pool_has_single_models(self) -> None:
        counts = Counter(item.name for item in self.multiworld.itempool)
        for letter in "HFLP":
            self.assertEqual(counts["Model %sX" % letter], 1)
            self.assertEqual(counts["Progressive Model %sX" % letter], 0)
        self.assertEqual(len(self.multiworld.itempool),
                         sum(1 for loc in self.multiworld.get_locations(1) if loc.address is not None))

    def test_one_item_is_the_full_biometal(self) -> None:
        """I-5's Life Up needs the level-2 charge of HX: the single item gives it."""
        state = CollectionState(self.multiworld)
        for item in self.multiworld.itempool:
            if item.name != "Model HX":
                state.collect(item, prevent_sweep=True)
        state.sweep_for_advancements()
        self.assertFalse(state.can_reach("I-5: Life Up", "Location", 1))
        state.collect(self.get_item_by_name("Model HX"))
        self.assertTrue(state.can_reach("A-1: Disk E-31", "Location", 1))
        self.assertTrue(state.can_reach("I-5: Life Up", "Location", 1))

    def test_goal_counts_full_items(self) -> None:
        collect_pool_but(self, ["Model HX"])
        self.assertBeatable(False)
        self.collect_by_name("Model HX")
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        sd = self.world.fill_slot_data()
        self.assertFalse(sd["progressive_models"])
        self.assertIn("Model HX", sd["goal_requirements"]["models"])


class TestFullModelsStart(MMZXTestBase):
    options = {"progressive_models": False, "starting_model": "model_hx"}

    def test_start_is_the_full_item(self) -> None:
        precollected = [item.name for item in self.multiworld.precollected_items[1]]
        self.assertIn("Model HX", precollected)
        self.assertNotIn("Model HX", [item.name for item in self.multiworld.itempool])


class TestFullModelsBossLogic(MMZXTestBase):
    options = {"progressive_models": False, "boss_logic": {"Hivolt": "HX2"}}

    def test_hx2_is_the_single_item(self) -> None:
        collect_pool_but(self, ["Model HX"])
        self.assertFalse(self.can_reach_region("e07/boss-room"))
        self.collect_by_name("Model HX")
        self.assertTrue(self.can_reach_region("e07/boss-room"))


class TestRequireFullModels(MMZXTestBase):
    options = {"require_full_models": True}

    def test_one_half_is_not_enough(self) -> None:
        collect_pool_but(self, ["Progressive Model HX"])
        first, second = self.get_items_by_name("Progressive Model HX")
        self.collect(first)
        self.assertBeatable(False)
        self.collect(second)
        self.assertBeatable(True)

    def test_slot_data_copies(self) -> None:
        g = self.world.fill_slot_data()["goal_requirements"]
        copies = dict(zip(g["models"], g["models_copies"]))
        self.assertEqual(copies["Progressive Model HX"], 2)
        self.assertEqual(copies["Model X"], 1)


class TestRequireFullModelsIgnoredWithoutProgressive(MMZXTestBase):
    options = {"require_full_models": True, "progressive_models": False}

    def test_single_items_count_once(self) -> None:
        g = self.world.fill_slot_data()["goal_requirements"]
        self.assertEqual(set(g["models_copies"]), {1})
        collect_pool_but(self, ["Model HX"])
        self.collect_by_name("Model HX")
        self.assertBeatable(True)
