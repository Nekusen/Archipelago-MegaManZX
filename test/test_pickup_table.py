"""The pickup table of a filled seed: one entry per pickup location, showing the item placed there."""
from Fill import distribute_items_restrictive

from .bases import MMZXTestBase
from ..data import ICON_CODES, LOCATIONS
from ..rom.table import ENTRY_RESPAWNS, ICON_BY_ITEM, PICKUP_SLOTS, build_table, table_entries


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


class TestPickupTableWithoutRefills(FilledTestBase):
    def test_refills_have_no_entry(self) -> None:
        codes = self.world.pickup_icons()
        self.assertFalse(any(LOCATIONS[n]["detect"][0] == "mailbox" for n in codes))
        self.assertTrue(any(LOCATIONS[n]["category"] == "disk" for n in codes))
