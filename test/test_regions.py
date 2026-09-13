from .bases import MMZXTestBase


class RegionsReachable:
    """Every region of the world is reachable with the whole pool, as the core's own
    reachability test requires; an empty region nothing leads to would fail it."""

    def test_every_region_reachable_with_everything(self):
        state = self.multiworld.get_all_state(False)
        for region in self.multiworld.get_regions(self.player):
            with self.subTest(region=region.name):
                self.assertTrue(state.can_reach_region(region.name, self.player))

    def test_no_empty_unconnected_region(self):
        for region in self.multiworld.get_regions(self.player):
            with self.subTest(region=region.name):
                self.assertTrue(region.entrances or region.exits or region.locations)


class TestRegions(RegionsReachable, MMZXTestBase):
    pass
