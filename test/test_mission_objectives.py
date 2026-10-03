"""mission_objectives: the story objects and events as locations, and as items the game asks for."""
import unittest
from collections import Counter

from BaseClasses import CollectionState

from .bases import MMZXTestBase, reach
from ..client.addresses import STORY_GATE_BITS, STORY_ITEM_BITS, STORY_LEN
from ..client.items import wanted_progress_bits
from ..client.story import parse_mode, story_held
from ..data import (DOORS, EVENT_GATES, ITEMS, LOCATIONS, STORY_CHAINS, STORY_COUNTS, STORY_GATE_ITEMS,
                    STORY_LAVA_ITEM, STORY_LAVA_LOCATION, STORY_REPORT_ITEMS)
from ..goal import cleared_event
from ..items import ITEM_GROUPS, STORY_GRANTS
from ..locations import STORY_CATEGORY, STORY_GATE
from ..regions import LAVA_EVENT

STORY_LOCATIONS = {n for n, v in LOCATIONS.items() if v["category"] == STORY_CATEGORY}
GATE_LOCATIONS = {n for n in STORY_LOCATIONS if LOCATIONS[n]["story"] == STORY_GATE}
STORY_ITEM_COUNTS = {n: int(v.get("count", 1)) for n, v in ITEMS.items() if v["grant"][0] in STORY_GRANTS}


def real_locations(multiworld) -> set[str]:
    return {loc.name for loc in multiworld.get_locations(1) if loc.address is not None}


def event_locations(multiworld) -> set[str]:
    return {loc.name for loc in multiworld.get_locations(1) if loc.address is None}


def state_without(multiworld, item: str | None = None) -> CollectionState:
    """The whole pool collected, but the copies of one item."""
    state = CollectionState(multiworld)
    for it in multiworld.itempool:
        if it.name != item:
            state.collect(it, prevent_sweep=True)
    state.sweep_for_advancements()
    return state


class TestOff(MMZXTestBase):
    def test_nothing_is_added(self) -> None:
        self.assertFalse(real_locations(self.multiworld) & STORY_LOCATIONS)
        self.assertFalse({item.name for item in self.multiworld.itempool} & set(STORY_ITEM_COUNTS))

    def test_story_items_have_their_own_group(self) -> None:
        """The Computer Chip is a mission objective, not one of the chips of the pool."""
        self.assertEqual(ITEM_GROUPS["Mission Objectives"], set(STORY_ITEM_COUNTS))
        self.assertFalse(ITEM_GROUPS["Chips"] & set(STORY_ITEM_COUNTS))

    def test_lava_is_the_event_of_its_control(self) -> None:
        self.assertIn(LAVA_EVENT, event_locations(self.multiworld))


class TestChecks(MMZXTestBase):
    options = {"mission_objectives": "checks"}

    def test_objects_and_events_are_locations(self) -> None:
        """Every story location but the ones that stand for an opened gate; the pool only grows by filler."""
        self.assertEqual(real_locations(self.multiworld) & STORY_LOCATIONS, STORY_LOCATIONS - GATE_LOCATIONS)
        self.assertFalse({item.name for item in self.multiworld.itempool} & set(STORY_ITEM_COUNTS))
        self.assertEqual(len(self.multiworld.itempool), len(real_locations(self.multiworld)))

    def test_everything_stays_open(self) -> None:
        """With the whole pool every location is in logic: nothing asks for an item that does not exist."""
        got = reach(self.multiworld)
        self.assertEqual(got["locs"], real_locations(self.multiworld))
        self.assertTrue(got["victory"])
        self.assertIn(LAVA_EVENT, event_locations(self.multiworld))


    def test_ordered_locations_need_the_earlier_ones(self) -> None:
        """A location the game gives after another is out of logic while that one is."""
        state = state_without(self.multiworld)
        location = self.multiworld.get_location
        for chain in STORY_CHAINS:
            first = location(chain[0], 1)
            rule, first.access_rule = first.access_rule, lambda _state: False
            try:
                for name in chain[1:]:
                    with self.subTest(location=name):
                        self.assertFalse(location(name, 1).can_reach(state))
            finally:
                first.access_rule = rule
            for name in chain:
                with self.subTest(location=name):
                    self.assertTrue(location(name, 1).can_reach(state))


class TestItems(MMZXTestBase):
    options = {"mission_objectives": "items"}

    def test_sprinkler_key_needs_enough_rescues(self) -> None:
        """The key comes with eight people rescued: with fewer within reach it is out of logic."""
        state = state_without(self.multiworld)
        (name, (count, group)), = STORY_COUNTS.items()
        key = self.multiworld.get_location(name, 1)
        self.assertTrue(key.can_reach(state))
        blocked = [self.multiworld.get_location(n, 1) for n in group[:len(group) - count + 1]]
        rules = [loc.access_rule for loc in blocked]
        for loc in blocked:
            loc.access_rule = lambda _state: False
        try:
            self.assertFalse(key.can_reach(state))
        finally:
            for loc, rule in zip(blocked, rules):
                loc.access_rule = rule

    def test_locations_and_items(self) -> None:
        """Every story location, and every story item with its copies."""
        self.assertEqual(real_locations(self.multiworld) & STORY_LOCATIONS, STORY_LOCATIONS)
        counts = Counter(item.name for item in self.multiworld.itempool)
        for name, n in STORY_ITEM_COUNTS.items():
            with self.subTest(item=name):
                self.assertEqual(counts[name], n)
                self.assertTrue(all(item.advancement for item in self.multiworld.itempool if item.name == name))
        self.assertEqual(len(self.multiworld.itempool), len(real_locations(self.multiworld)))

    def test_seed_is_beatable(self) -> None:
        got = reach(self.multiworld)
        self.assertEqual(got["locs"], real_locations(self.multiworld))
        self.assertTrue(got["victory"])

    def test_report_needs_its_object(self) -> None:
        """Without its object a mission is neither a check in logic nor cleared for the rules that ask."""
        for mission, item in STORY_REPORT_ITEMS.items():
            with self.subTest(mission=mission):
                state = state_without(self.multiworld, item)
                self.assertFalse(self.multiworld.get_location("Mission - " + mission, 1).can_reach(state))
                self.assertFalse(state.has(cleared_event("Mission - " + mission), 1))

    def test_story_gates_need_their_item(self) -> None:
        """The doors behind the two story gates open with their item alone."""
        full = state_without(self.multiworld)
        for flag, item in STORY_GATE_ITEMS.items():
            doors = [d["name"] for d in DOORS if d.get("gate") == flag]
            self.assertTrue(doors)
            lacking = state_without(self.multiworld, item)
            for name in doors:
                with self.subTest(door=name):
                    entrance = self.multiworld.get_entrance(name, 1)
                    self.assertTrue(entrance.access_rule(full))
                    self.assertFalse(entrance.access_rule(lacking))

    def test_lava_is_an_item(self) -> None:
        self.assertNotIn(LAVA_EVENT, event_locations(self.multiworld))
        self.assertIn(STORY_LAVA_ITEM, {item.name for item in self.multiworld.itempool})
        self.assertIn(STORY_LAVA_LOCATION, real_locations(self.multiworld))


class TestClientState(unittest.TestCase):
    def test_possession_bytes(self) -> None:
        """One bit per copy held, each item in its own byte and bits."""
        self.assertEqual(story_held({}), bytes(STORY_LEN))
        self.assertEqual(story_held({"Computer Chip": 1}), bytes([0x01, 0x00]))
        self.assertEqual(story_held({"Computer Chip": 3, "Data Disk 2": 1}), bytes([0x47, 0x00]))
        everything = story_held(dict(STORY_ITEM_COUNTS))
        self.assertEqual(everything, bytes([0xFF, 0x61]))
        seen: dict[int, int] = {}
        for byte, bits in STORY_ITEM_BITS.values():
            for bit in bits:
                self.assertFalse(seen.get(byte, 0) & (1 << bit))
                seen[byte] = seen.get(byte, 0) | (1 << bit)

    def test_story_gates_are_left_to_the_game(self) -> None:
        """With the items the client stops opening the two story gates; the other gates stay open."""
        class Goal:
            def met(self, counts, missions):
                return False
        gates = {tuple(EVENT_GATES[flag]) for flag in STORY_GATE_ITEMS}
        self.assertEqual(STORY_GATE_BITS, gates)
        opened, _keys = wanted_progress_bits({}, Goal(), 0)
        self.assertTrue(gates <= opened)
        closed, _keys = wanted_progress_bits({}, Goal(), 0, STORY_GATE_BITS)
        self.assertEqual(opened - closed, gates)

    def test_mode_from_slot_data(self) -> None:
        self.assertEqual(parse_mode(None), "off")
        self.assertEqual(parse_mode("checks"), "checks")
        self.assertEqual(parse_mode("items"), "items")
