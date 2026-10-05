"""mission_objectives: the story objects and events as locations, and as items the game asks for."""
import unittest
from collections import Counter
from contextlib import contextmanager

from BaseClasses import CollectionState

from .bases import MMZXTestBase, reach
from ..client.addresses import (DETECT_FAR, STORY_AREA_FLAGS, STORY_DONE_ADDR, STORY_DONE_DETECT, STORY_GATE_BITS,
                                STORY_ITEM_BITS, STORY_LEN)
from ..client.items import wanted_progress_bits
from ..client.story import parse_mode, story_held
from ..data import (DOORS, EVENT_GATES, ITEMS, LOCATIONS, STORY_CHAINS, STORY_COUNTS, STORY_DONE_BITS,
                    STORY_GATE_ITEMS, STORY_LAVA_ITEM, STORY_LAVA_LOCATION, STORY_REPORT_ITEMS, STORY_SWITCH_ITEM,
                    STORY_SWITCH_LOCATION)
from ..goal import cleared_event
from ..items import ITEM_GROUPS, STORY_GRANTS
from ..locations import STORY_CATEGORY, STORY_GATE
from ..logic import document as F
from ..logic import load_document
from ..regions import LAVA_EVENT, SWITCH_EVENT, area_of

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


def lava_edges(multiworld) -> list:
    """The entrances whose rule in the document asks for the slow lava."""
    asking = {(F.region_name(room, conn["from"]), F.region_name(room, conn["to"]))
              for room, layout in load_document()["rooms"].items() for conn in layout.get("conns", [])
              if any(F.SLOW_LAVA in clause for clauses in (conn.get("req") or {}).values() for clause in clauses)}
    return [entrance for entrance in multiworld.get_entrances(1)
            if (entrance.parent_region.name, entrance.connected_region.name) in asking]


def switch_locations(multiworld) -> list:
    """The locations whose rule in the document asks for the door the switch of K-4 unlocks."""
    asking = {name for name, check in load_document().get("checks", {}).items()
              if any(F.K_DOOR_SWITCH in clause for clauses in (check.get("req") or {}).values() for clause in clauses)}
    return [loc for loc in multiworld.get_locations(1) if loc.name in asking]


def ways_in_from_its_area(multiworld, region) -> list:
    """The entrances into the room of a region from the other rooms of its area."""
    room = region.name.split("/")[0]
    return [entrance for entrance in multiworld.get_entrances(1)
            if entrance.connected_region.name.split("/")[0] == room
            and entrance.parent_region.name.split("/")[0] != room
            and area_of(entrance.parent_region.name) == area_of(room)]


@contextmanager
def shut(entrances):
    """The entrances closed for the length of the block."""
    rules = [entrance.access_rule for entrance in entrances]
    for entrance in entrances:
        entrance.access_rule = lambda _state: False
    try:
        yield
    finally:
        for entrance, rule in zip(entrances, rules):
            entrance.access_rule = rule


class LavaByItsControl:
    """With no item for the slow lava, it is set at its control and lost on leaving the area."""

    def test_slow_lava_needs_the_room_of_its_control(self) -> None:
        edges = lava_edges(self.multiworld)
        if not edges:
            self.skipTest("no rule of the document asks for the slow lava")
        control = self.multiworld.get_location(LAVA_EVENT, 1).parent_region
        with shut(control.entrances):
            cut_off = state_without(self.multiworld)
        reached = state_without(self.multiworld)
        for edge in edges:
            with self.subTest(edge=edge.name):
                self.assertFalse(edge.access_rule(cut_off))
                self.assertTrue(edge.access_rule(reached))

    def test_slow_lava_has_to_be_walked_from_its_control(self) -> None:
        """A way shut inside the area closes the edge, though its control and its room stay in reach."""
        edges = lava_edges(self.multiworld)
        if not edges:
            self.skipTest("no rule of the document asks for the slow lava")
        for edge in edges:
            with self.subTest(edge=edge.name), shut(ways_in_from_its_area(self.multiworld, edge.parent_region)):
                state = state_without(self.multiworld)
                self.assertTrue(state.has(LAVA_EVENT, 1))
                self.assertTrue(state.can_reach_region(edge.parent_region.name, 1))
                self.assertFalse(edge.access_rule(state))


class DoorByItsSwitch:
    """With no item for the door of K-1, pressing the switch of K-4 once is what unlocks it."""

    def test_door_needs_the_room_of_its_switch(self) -> None:
        behind = switch_locations(self.multiworld)
        if not behind:
            self.skipTest("no rule of the document asks for the door switch")
        switch = self.multiworld.get_location(SWITCH_EVENT, 1).parent_region
        with shut(switch.entrances):
            cut_off = state_without(self.multiworld)
        reached = state_without(self.multiworld)
        for loc in behind:
            with self.subTest(location=loc.name):
                self.assertFalse(loc.can_reach(cut_off))
                self.assertTrue(loc.can_reach(reached))


class TestOff(LavaByItsControl, DoorByItsSwitch, MMZXTestBase):
    def test_nothing_is_added(self) -> None:
        self.assertFalse(real_locations(self.multiworld) & STORY_LOCATIONS)
        self.assertFalse({item.name for item in self.multiworld.itempool} & set(STORY_ITEM_COUNTS))

    def test_story_items_have_their_own_group(self) -> None:
        """The Computer Chip is a mission objective, not one of the chips of the pool."""
        self.assertEqual(ITEM_GROUPS["Mission Objectives"], set(STORY_ITEM_COUNTS))
        self.assertFalse(ITEM_GROUPS["Chips"] & set(STORY_ITEM_COUNTS))

    def test_lava_is_the_event_of_its_control(self) -> None:
        self.assertIn(LAVA_EVENT, event_locations(self.multiworld))


class TestChecks(LavaByItsControl, DoorByItsSwitch, MMZXTestBase):
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
                progression = ITEMS[name]["classification"] == "progression"
                self.assertTrue(all(item.advancement == progression
                                    for item in self.multiworld.itempool if item.name == name))
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

    def test_slow_lava_needs_its_item(self) -> None:
        """Reaching the control is not enough here, and the item needs no walk from it."""
        edges = lava_edges(self.multiworld)
        if not edges:
            self.skipTest("no rule of the document asks for the slow lava")
        full, lacking = state_without(self.multiworld), state_without(self.multiworld, STORY_LAVA_ITEM)
        self.assertTrue(self.multiworld.get_location(STORY_LAVA_LOCATION, 1).can_reach(lacking))
        for edge in edges:
            with self.subTest(edge=edge.name):
                self.assertTrue(edge.access_rule(full))
                self.assertFalse(edge.access_rule(lacking))
                with shut(ways_in_from_its_area(self.multiworld, edge.parent_region)):
                    self.assertTrue(edge.access_rule(state_without(self.multiworld)))

    def test_door_needs_its_item(self) -> None:
        """The switch is a check here, and the door it unlocks waits for the item."""
        behind = switch_locations(self.multiworld)
        if not behind:
            self.skipTest("no rule of the document asks for the door switch")
        self.assertNotIn(SWITCH_EVENT, event_locations(self.multiworld))
        full, lacking = state_without(self.multiworld), state_without(self.multiworld, STORY_SWITCH_ITEM)
        self.assertTrue(self.multiworld.get_location(STORY_SWITCH_LOCATION, 1).can_reach(lacking))
        for loc in behind:
            with self.subTest(location=loc.name):
                self.assertTrue(loc.can_reach(full))
                self.assertFalse(loc.can_reach(lacking))


class TestClientState(unittest.TestCase):
    def test_possession_bytes(self) -> None:
        """One bit per copy held, each item in its own byte and bits."""
        self.assertEqual(story_held({}), bytes(STORY_LEN))
        self.assertEqual(story_held({"Computer Chip": 1}), bytes([0x01, 0x00]))
        self.assertEqual(story_held({"Computer Chip": 3, "Data Disk 2": 1}), bytes([0x47, 0x00]))
        everything = story_held(dict(STORY_ITEM_COUNTS))
        self.assertEqual(everything, bytes([0xFF, 0xE1]))
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

    def test_event_whose_effect_is_an_item(self) -> None:
        """The game marks the event in a byte of its own, and the item holds the area flag of that event."""
        for name, bit in STORY_DONE_BITS.items():
            with self.subTest(location=name):
                flag = tuple(LOCATIONS[name]["detect"][1:])
                self.assertEqual(STORY_DONE_DETECT[LOCATIONS[name]["id"]], ["bit", STORY_DONE_ADDR, bit])
                held = [(item, area) for item, (area, flags) in STORY_AREA_FLAGS.items() if flags == [flag]]
                self.assertEqual(len(held), 1)
                item, area = held[0]
                self.assertEqual(area, name[0])
                self.assertEqual(ITEMS[item]["classification"], "useful")
        self.assertIn(STORY_DONE_ADDR, DETECT_FAR)
        self.assertEqual(len(STORY_AREA_FLAGS), len(STORY_DONE_BITS))

    def test_mode_from_slot_data(self) -> None:
        self.assertEqual(parse_mode(None), "off")
        self.assertEqual(parse_mode("checks"), "checks")
        self.assertEqual(parse_mode("items"), "items")
