"""skip_boss_rush changes only the D-4 tower in the logic."""
import unittest

from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS, reach
from .. import MMZXWorld
from .. import logic_format as F
from ..regions import load_document

HUB2 = F.region_name("z02", "main")     # the tower's teleporter floor


class TestSkipBossRush(MMZXTestBase):
    options = {"skip_boss_rush": True}

    def test_only_hub2_leaves_the_graph(self) -> None:
        """Skipping the rush removes the teleporter floor and changes nothing else."""
        reference = reach(setup_multiworld(MMZXWorld))
        skipped = reach(self.multiworld)
        self.assertIn(HUB2, reference["regions"])
        self.assertNotIn(HUB2, skipped["regions"])
        self.assertEqual(reference["regions"] - {HUB2}, skipped["regions"])
        self.assertEqual(reference["locs"], skipped["locs"])
        self.assertTrue(skipped["victory"])


class TestSkipBossRushRequirements(unittest.TestCase):
    def test_unmet_pseudoroid_blocks_only_the_rush(self) -> None:
        """A Pseudoroid the player cannot beat blocks the goal only while the rush is required."""
        arenas = {boss: F.region_name(room, rid) for (room, rid), boss in F.boss_regions(load_document()).items()}
        for boss in F.PSEUDOROIDS:
            name = F.BOSSES[boss]["name"]
            with self.subTest(boss=name):
                required = reach(setup_multiworld(MMZXWorld, options={"boss_logic": {name: WITNESS}}),
                                 without=[WITNESS])
                skipped = reach(setup_multiworld(MMZXWorld, options={"boss_logic": {name: WITNESS},
                                                                     "skip_boss_rush": True}),
                                without=[WITNESS])
                self.assertFalse(required["victory"])
                self.assertTrue(skipped["victory"])
                self.assertNotIn(arenas[boss], skipped["regions"])
