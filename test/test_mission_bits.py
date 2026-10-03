"""The completed bits of the missions: what the client keeps counting after later Reports."""
import unittest

from ..client.addresses import DETECT_WINDOW
from ..client.goal import missions_completed
from ..client.ram import ProgressWindow, mission_done_bits

# What the game holds once each pair is reported in story order: the first mission's
# Report also sets the second one's offer bit, and the second one's Report clears it.
REPORTED_IN_ORDER = {
    ("Find The Survivors", "Recover The Disk"): [(0x021045E1, 7), (0x021045E5, 2)],
    ("Fight The Mavericks", "Attack The Excavators"): [(0x021045E3, 7), (0x021045E5, 6)],
}


def window_with(bits) -> ProgressWindow:
    lo, hi = DETECT_WINDOW
    block = bytearray(hi - lo)
    for addr, bit in bits:
        block[addr - lo] |= 1 << bit
    return ProgressWindow(bytes(block), {})


class TestMissionBits(unittest.TestCase):
    def test_both_missions_of_a_pair_stay_completed(self) -> None:
        for pair, bits in REPORTED_IN_ORDER.items():
            self.assertLessEqual(set(pair), missions_completed(window_with(bits)), pair)

    def test_no_offer_bit_in_a_detection(self) -> None:
        """The offer bits of Recover The Disk and Attack The Excavators belong to no mission's detection."""
        offers = {(0x021045E5, 0), (0x021045E5, 3)}
        for name in ("Find The Survivors", "Fight The Mavericks", "Recover The Disk", "Attack The Excavators"):
            self.assertFalse(offers & set(mission_done_bits(name)), name)
