"""Which items open which parts of the map."""
from BaseClasses import CollectionState

from .bases import MMZXTestBase
from ..data import DOORS, HUB_ROOM, TRANSERVER_ACCESS

# Everything behind the Blue Card Key door of A-4: the whole J area.
BLUE_KEY_LOCATIONS = [
    "J-1: Life Up", "J-2: Disk E-7", "J-3: Disk E-36", "J-3: Disk M-7", "J-5: Disk B-16",
    "Mission - Recover The Disk", "Cleared: Recover The Disk",
]
# Behind the Purple Card Key door of H-2: L-1 and L-2 (L-3/L-4 are warped to).
PURPLE_KEY_LOCATIONS = ["L-1: Disk E-18", "L-2: Disk E-41"]
# Behind Yellow Card Key doors: A-3, B-4, the C-2 building and, through A-3, the H area.
YELLOW_KEY_LOCATIONS = [
    "A-3: Disk E-46", "B-4: Disk E-11", "C-2: Disk O-18", "H-3: Disk E-10", "H-3: Disk M-8",
    "H-4: Disk B-7", "L-1: Disk E-18", "Mission - Secure The Biometal",
]
# Area X can only be entered from the hub warp.
ACCESS_X_LOCATIONS = [
    "Mission - Protect Hq", "Cleared: Protect Hq", "X-1: Disk O-1", "X-1: Disk O-10",
    "X-1: Disk O-13", "X-1: Disk O-14", "X-1: Disk O-15", "X-1: Disk O-19", "X-1: Disk O-2",
    "X-1: Disk O-20", "X-1: Disk O-4", "X-1: Disk O-5", "X-1: Disk O-6", "X-1: Disk O-7",
    "X-1: Disk O-8", "X-2: Disk O-16", "X-2: Disk O-3", "X-3: Disk O-11",
]
# L-3 and L-4 hang from the L-4 warp; L-1/L-2 are walked to from H-2.
ACCESS_L_LOCATIONS = ["L-3: Disk E-5", "L-4: Disk B-13", "Mission - Protect The Lab",
                      "Cleared: Protect The Lab"]
TOWER_LOCATIONS = ["D-4: Disk B-5", "D-5: Disk B-6"]
POOL_BIOMETALS = ["Model X", "Progressive Model HX", "Progressive Model FX",
                  "Progressive Model LX", "Progressive Model PX"]


class CardKeyTests:
    def test_blue_card_key(self) -> None:
        """The Blue Card Key alone gates the J area."""
        self.assertAccessDependency(BLUE_KEY_LOCATIONS, [["Blue Card Key"]])

    def test_purple_card_key(self) -> None:
        """The Purple Card Key alone gates L-1 and L-2."""
        self.assertAccessDependency(PURPLE_KEY_LOCATIONS, [["Purple Card Key"]])

    def test_yellow_card_key(self) -> None:
        """The Yellow Card Key gates A-3, B-4, the C-2 building and the H area."""
        self.assertAccessDependency(YELLOW_KEY_LOCATIONS, [["Yellow Card Key"]], only_check_listed=True)

    def test_green_card_key(self) -> None:
        """The Green Card Key opens the C-1 building, which holds no location."""
        self.collect_all_but(["Green Card Key"])
        self.assertFalse(self.can_reach_region("c01/green-card-building"))
        self.collect_by_name("Green Card Key")
        self.assertTrue(self.can_reach_region("c01/green-card-building"))

    def test_red_card_key(self) -> None:
        """The Red Card Key opens the C-3 / K-1 door in both directions."""
        self.collect_all_but(["Red Card Key"])
        self.assertFalse(self.can_reach_entrance("c03 door (2224,720)"))
        self.assertFalse(self.can_reach_entrance("k01 door (288,912)"))
        self.collect_by_name("Red Card Key")
        self.assertTrue(self.can_reach_entrance("c03 door (2224,720)"))
        self.assertTrue(self.can_reach_entrance("k01 door (288,912)"))

    def test_white_card_key_door_stays_closed(self) -> None:
        """The White Card Key is not an item, so its K-4 door is never crossed."""
        self.assertEqual(self.get_items_by_name("White Card Key"), [])
        self.collect_all_but([])
        self.assertFalse(self.can_reach_entrance("k04 door (2704,1136)"))


class TranserverTests:
    def test_area_x_needs_its_access(self) -> None:
        """Area X hangs from the hub warp: its Transerver Access gates every X location."""
        self.assertAccessDependency(ACCESS_X_LOCATIONS, [["Transerver Access - Area X"]])

    def test_area_l_needs_its_access(self) -> None:
        """L-3 and L-4 are only reached through the L-4 warp."""
        self.assertAccessDependency(ACCESS_L_LOCATIONS, [["Transerver Access - Area L"]])

    def test_starting_access_is_granted(self) -> None:
        """The starting hub floor's warp is open from the start; the others need their item."""
        self.assertIn("Transerver Access - Area A", [i.name for i in self.multiworld.precollected_items[1]])
        self.assertTrue(self.can_reach_entrance("z01 transerver to a02"))
        self.assertFalse(self.can_reach_entrance("z01 transerver to b02"))
        self.collect_by_name("Transerver Access - Area B")
        self.assertTrue(self.can_reach_entrance("z01 transerver to b02"))

    def test_every_hub_warp_has_an_access_item(self) -> None:
        """Every warp leaving the hub is tied to a Transerver Access item."""
        for door in DOORS:
            if door["kind"] == "warp" and door["src"] == HUB_ROOM:
                self.assertIn(door["dst"], TRANSERVER_ACCESS, door["name"])


class BiometalTests:
    def test_model_hx(self) -> None:
        """Model HX (the air dash) gates the high ledges of A, B, I and O."""
        self.assertAccessDependency(["A-1: Disk E-31", "A-2: Sub Tank", "O-2: Disk B-14",
                                     "Mission - Repel The Army"],
                                    [["Progressive Model HX"]], only_check_listed=True)

    def test_model_hx_full_charge(self) -> None:
        """I-5's Life Up needs both halves of Model HX (the level-2 charge)."""
        state = CollectionState(self.multiworld)
        self.collect_all_but(["Progressive Model HX"], state)
        first, second = self.get_items_by_name("Progressive Model HX")
        state.collect(first)
        self.assertTrue(state.can_reach("A-1: Disk E-31", "Location", 1))
        self.assertFalse(state.can_reach("I-5: Life Up", "Location", 1))
        state.collect(second)
        self.assertTrue(state.can_reach("I-5: Life Up", "Location", 1))

    def test_model_fx(self) -> None:
        """Model FX (fire) gates the ice cubes of F and the hidden path of K-4."""
        self.assertAccessDependency(["F-2: Life Up", "F-3: Disk E-2", "G-5: Disk B-11", "K-4: Disk B-12"],
                                    [["Progressive Model FX"]], only_check_listed=True)

    def test_model_lx(self) -> None:
        """Model LX (swimming) gates the flooded rooms of F-4 and J."""
        self.assertAccessDependency(["F-4: Disk B-15", "J-5: Disk B-16", "Mission - Recover The Disk"],
                                    [["Progressive Model LX"]], only_check_listed=True)

    def test_model_px(self) -> None:
        """Model PX is one of the four biometals K-1's Sub Tank asks for."""
        self.assertAccessDependency(["K-1: Sub Tank"], [["Progressive Model PX"]], only_check_listed=True)

    def test_six_biometals_open_the_tower(self) -> None:
        """The D-4 tower needs all six biometals: any missing one closes D-4 and D-5."""
        for name in POOL_BIOMETALS:
            with self.subTest(biometal=name):
                self.assertAccessDependency(TOWER_LOCATIONS, [[name]], only_check_listed=True)


class TestCardKeys(CardKeyTests, MMZXTestBase):
    pass


class TestTranserver(TranserverTests, MMZXTestBase):
    pass


class TestBiometals(BiometalTests, MMZXTestBase):
    def test_model_px_dark_rooms(self) -> None:
        """The dark rooms of I-2 and I-4 need Model PX."""
        self.assertAccessDependency(["I-2: Disk E-34", "I-4: Disk E-14", "I-4: Disk M-1"],
                                    [["Progressive Model PX"]], only_check_listed=True)
