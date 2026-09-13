"""The item pool: it fills the active locations exactly, whatever the options."""
import unittest
from collections import Counter

from Options import OptionError
from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS
from .. import MMZXWorld
from ..data import ITEMS, STARTING_MODEL_ITEM

# option sets the pool must fit under
OPTION_SETS = {
    "default": {},
    "no_starting_model": {"starting_model": "none"},
    "hu_in_pool": {"hu_in_pool": True},
    "skip_boss_rush": {"skip_boss_rush": True},
    "all_pickups": {"pickup_checks_1up": True, "pickup_checks_energy": True,
                    "pickup_checks_weapon": True, "pickup_checks_crystals": True},
    "boss_logic": {"boss_logic": {"Serpent": "ALL6 & Life Up x2", "Hivolt": WITNESS}},
}
# pickup option: locations it adds, as the option docstrings promise
PICKUP_COUNTS = {"pickup_checks_1up": 7, "pickup_checks_energy": 45,
                 "pickup_checks_weapon": 25, "pickup_checks_crystals": 56}


def real_locations(multiworld) -> int:
    """Number of locations with an id (events excluded)."""
    return sum(1 for loc in multiworld.get_locations(1) if loc.address is not None)


class TestPool(MMZXTestBase):
    def test_pool_fills_the_locations(self) -> None:
        self.assertEqual(len(self.multiworld.itempool), real_locations(self.multiworld))

    def test_progressive_biometals_come_in_halves(self) -> None:
        """Each progressive biometal is two items; the other models are one."""
        counts = Counter(item.name for item in self.multiworld.itempool)
        for letter in "HFLP":
            self.assertEqual(counts["Progressive Model %sX" % letter], 2)
        self.assertEqual(counts["Model X"], 1)
        self.assertEqual(counts["Model OX"], 1)

    def test_starting_items_are_precollected(self) -> None:
        """Model ZX (the default start) and the starting floor's Transerver Access are granted, not in the pool."""
        precollected = sorted(item.name for item in self.multiworld.precollected_items[1])
        self.assertEqual(precollected, ["Model ZX", "Transerver Access - Area A"])
        names = {item.name for item in self.multiworld.itempool}
        self.assertNotIn("Model ZX", names)
        self.assertNotIn("Transerver Access - Area A", names)

    def test_unpooled_items_stay_out(self) -> None:
        """The White Card Key and Model Hu (without hu_in_pool) are not items of the pool."""
        names = {item.name for item in self.multiworld.itempool}
        self.assertNotIn("White Card Key", names)
        self.assertNotIn("Model Hu", names)

    def test_filler(self) -> None:
        """E-Crystals pad the pool and are its only filler item."""
        self.assertEqual(self.world.get_filler_item_name(), "E-Crystals")
        fillers = {item.name for item in self.multiworld.itempool if item.classification.name == "filler"}
        self.assertEqual(fillers, {"E-Crystals"})

    def test_witness_is_useful_by_default(self) -> None:
        """A chip no rule asks for stays a useful item."""
        self.assertFalse(self.get_item_by_name(WITNESS).advancement)


class TestPoolWithBossLogic(MMZXTestBase):
    options = {"boss_logic": {"Hivolt": WITNESS}}

    def test_required_chip_becomes_progression(self) -> None:
        """A chip named in boss_logic is promoted to progression, so the state tracks it."""
        self.assertTrue(self.get_item_by_name(WITNESS).advancement)


class TestPoolCombinations(unittest.TestCase):
    def test_pool_fills_the_locations(self) -> None:
        for name, options in OPTION_SETS.items():
            with self.subTest(options=name):
                multiworld = setup_multiworld(MMZXWorld, options=options)
                self.assertEqual(len(multiworld.itempool), real_locations(multiworld))
                ids = multiworld.worlds[1].item_name_to_id
                for item in multiworld.itempool:
                    self.assertIn(item.name, ids)

    def test_starting_model_leaves_the_pool(self) -> None:
        """The starting model is precollected and one copy fewer is in the pool."""
        for key, item_name in STARTING_MODEL_ITEM.items():
            with self.subTest(starting_model=key):
                multiworld = setup_multiworld(MMZXWorld, options={"starting_model": key})
                precollected = [item.name for item in multiworld.precollected_items[1]]
                self.assertIn(item_name, precollected)
                in_pool = sum(1 for item in multiworld.itempool if item.name == item_name)
                self.assertEqual(in_pool, int(ITEMS[item_name].get("count", 1)) - 1)

    def test_no_starting_model_leaves_model_x_findable(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={"starting_model": "none"})
        precollected = [item.name for item in multiworld.precollected_items[1]]
        self.assertEqual([n for n in precollected if "Model" in n], [])
        self.assertIn("Model X", [item.name for item in multiworld.itempool])

    def test_none_with_hu_in_pool_is_rejected(self) -> None:
        """starting_model none with hu_in_pool would start without any form: generation fails."""
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"starting_model": "none", "hu_in_pool": True})

    def test_pickup_options_add_their_locations(self) -> None:
        """Each pickup option adds as many locations as its description says."""
        base = real_locations(setup_multiworld(MMZXWorld))
        for option, count in PICKUP_COUNTS.items():
            with self.subTest(option=option):
                multiworld = setup_multiworld(MMZXWorld, options={option: True})
                self.assertEqual(real_locations(multiworld) - base, count)
                self.assertEqual(len(multiworld.itempool), real_locations(multiworld))
