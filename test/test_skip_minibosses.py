"""skip_minibosses reaches the client through slot data and leaves the logic alone."""
from test.general import setup_multiworld

from .bases import MMZXTestBase, reach
from .. import MMZXWorld


class TestSkipMinibosses(MMZXTestBase):
    options = {"skip_minibosses": True}

    def test_slot_data_carries_the_option(self) -> None:
        self.assertTrue(self.world.fill_slot_data()["skip_minibosses"])

    def test_logic_is_unchanged(self) -> None:
        """The client skips the fights; the rooms keep asking for what they need."""
        reference = reach(setup_multiworld(MMZXWorld))
        skipped = reach(self.multiworld)
        self.assertEqual(reference["regions"], skipped["regions"])
        self.assertEqual(reference["locs"], skipped["locs"])
        self.assertTrue(skipped["victory"])


class TestSkipMinibossesOff(MMZXTestBase):
    def test_slot_data_says_off(self) -> None:
        self.assertFalse(self.world.fill_slot_data()["skip_minibosses"])
