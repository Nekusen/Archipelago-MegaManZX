"""The pickup table of a filled seed: one entry per pickup location, showing the item placed there."""
from Fill import distribute_items_restrictive

from .bases import MMZXTestBase
from ..data import ICON_CODES, LOCATIONS
from ..rom.table import (ENTRY_OWN_EFFECT, ENTRY_RESPAWNS, ICON_BY_ITEM, MADE_INDEX, PICKUP_SLOTS, build_table,
                         table_entries)

STORY_OBJECTS = {n for n in PICKUP_SLOTS if LOCATIONS[n]["category"] == "story"}


class FilledTestBase(MMZXTestBase):
    run_default_tests = False   # the seed is filled here, once

    def world_setup(self, seed=None) -> None:
        super().world_setup(seed)
        if self.constructed:
            distribute_items_restrictive(self.multiworld)


class TestPickupTableFilled(FilledTestBase):
    options = {"pickup_checks_energy": True}

    def test_every_pickup_location_has_an_entry(self) -> None:
        codes = self.world.pickup_icons()
        created = {loc.name for loc in self.multiworld.get_locations(1) if loc.name in PICKUP_SLOTS}
        self.assertEqual(set(codes), created)
        self.assertTrue(any(LOCATIONS[n]["detect"][0] == "mailbox" for n in codes))
        self.assertTrue(all(1 <= code <= len(ICON_CODES) for code in codes.values()))

    def test_codes_follow_the_placed_items(self) -> None:
        codes = self.world.pickup_icons()
        for loc in self.multiworld.get_locations(1):
            if loc.name not in codes:
                continue
            item = loc.item
            if item.player == 1 and item.name in ICON_BY_ITEM:
                want = ICON_CODES[ICON_BY_ITEM[item.name]]
            elif item.advancement:
                want = ICON_CODES["logo_progression"]
            elif item.useful:
                want = ICON_CODES["logo_useful"]
            else:
                want = ICON_CODES["logo_filler"]
            self.assertEqual(codes[loc.name], want, loc.name)

    def test_table_round_trips(self) -> None:
        codes = self.world.pickup_icons()
        entries = table_entries(build_table(codes))
        self.assertEqual({n: c for n, (_slot, c, _flags) in entries.items()}, codes)
        for name, (slot, _code, flags) in entries.items():
            self.assertEqual(slot, PICKUP_SLOTS[name])
            self.assertEqual(bool(flags & ENTRY_RESPAWNS), LOCATIONS[name]["detect"][0] == "mailbox")
            self.assertEqual(bool(flags & ENTRY_OWN_EFFECT), name in STORY_OBJECTS)


class TestPickupTableWithStoryItems(TestPickupTableFilled):
    options = {"pickup_checks_energy": True, "mission_objectives": "items"}

    def test_story_objects_show_their_item(self) -> None:
        """The chips and the disks the bosses leave are in the table, after every other pickup."""
        self.assertTrue(STORY_OBJECTS)
        self.assertTrue(STORY_OBJECTS <= set(self.world.pickup_icons()))
        first = min(PICKUP_SLOTS[n] for n in STORY_OBJECTS)
        self.assertEqual({n for n, slot in PICKUP_SLOTS.items() if slot >= first}, STORY_OBJECTS)

    def test_objects_made_by_the_game(self) -> None:
        """A pickup with no place in its room's layout takes an index past every real one of that room."""
        made = {n for n in STORY_OBJECTS if LOCATIONS[n]["icon"][1] >= MADE_INDEX}
        self.assertTrue(made)
        for name in made:
            room = LOCATIONS[name]["icon"][0]
            others = [v["icon"][1] for n, v in LOCATIONS.items() if n not in made and v.get("icon", [None])[0] == room]
            self.assertTrue(all(idx < MADE_INDEX for idx in others), name)


class TestPickupTableWithStoryChecks(TestPickupTableWithStoryItems):
    options = {"pickup_checks_energy": True, "mission_objectives": "checks"}


class TestPickupTableWithoutRefills(FilledTestBase):
    def test_refills_have_no_entry(self) -> None:
        codes = self.world.pickup_icons()
        self.assertFalse(any(LOCATIONS[n]["detect"][0] == "mailbox" for n in codes))
        self.assertTrue(any(LOCATIONS[n]["category"] == "disk" for n in codes))
