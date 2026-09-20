"""skip_minibosses reaches the client through slot data and leaves the logic alone."""
from test.general import setup_multiworld

from .bases import MMZXTestBase, reach
from .. import MMZXWorld


class TestSkipMinibossesAlways(MMZXTestBase):
    options = {"skip_minibosses": "always"}

    def test_slot_data_carries_the_mode(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["skip_minibosses"], "always")

    def test_logic_is_unchanged(self) -> None:
        """The client skips the fights; the rooms keep asking for what they need."""
        reference = reach(setup_multiworld(MMZXWorld))
        skipped = reach(self.multiworld)
        self.assertEqual(reference["regions"], skipped["regions"])
        self.assertEqual(reference["locs"], skipped["locs"])
        self.assertTrue(skipped["victory"])


class TestSkipMinibossesAfterFirstDefeat(MMZXTestBase):
    options = {"skip_minibosses": "after_first_defeat"}

    def test_slot_data_carries_the_mode(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["skip_minibosses"], "after_first_defeat")


class TestSkipMinibossesOff(MMZXTestBase):
    def test_slot_data_says_off(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["skip_minibosses"], "off")
