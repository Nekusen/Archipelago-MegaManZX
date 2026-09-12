"""boss_logic closes exactly what lies behind each boss, and rejects bad YAML early."""
import unittest

from Options import OptionError
from test.general import setup_multiworld

from .bases import WITNESS, reach
from .. import MMZXWorld
from ..logic import bosses, load_document
from ..logic import document as F

# Blocking these bosses also closes the goal: the Pseudoroids through the D-4
# boss rush, Model Z because D-2 is the only way into the tower, Serpent himself.
GOAL_BOSSES = set(F.PSEUDOROIDS) | {"model_z", "serpent"}
BIOMETAL_PAIRS = {"H": ("hivolt", "hurricaune"), "L": ("lurerre", "leganchor"),
                  "F": ("fistleo", "flammole"), "P": ("purprill", "protectos")}


def arenas() -> dict:
    """{boss id: region name of its arena} from the bundled document."""
    return {boss: F.region_name(room, rid) for (room, rid), boss in F.boss_regions(load_document()).items()}


def with_requirement(boss_ids, **options):
    """Multiworld where each named boss requires the witness item."""
    options["boss_logic"] = {F.BOSSES[b]["name"]: WITNESS for b in boss_ids}
    return setup_multiworld(MMZXWorld, options=options)


class TestBossLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.arenas = arenas()
        cls.base = reach(setup_multiworld(MMZXWorld))

    def test_all_bosses_are_anchored(self) -> None:
        """Every boss of the roster has an arena tagged in the document."""
        self.assertEqual(F.bosses_anchored(load_document()), set(F.BOSSES))
        self.assertEqual(len(self.arenas), 15)

    def test_reference_wins(self) -> None:
        """Without boss_logic the whole pool reaches every arena and the goal."""
        self.assertTrue(self.base["victory"])
        for boss, arena in self.arenas.items():
            self.assertIn(arena, self.base["regions"], boss)

    def test_each_boss_closes_its_arena(self) -> None:
        """One boss' requirement closes its arena, and nothing at all once the requirement is met."""
        for boss, arena in sorted(self.arenas.items()):
            with self.subTest(boss=F.BOSSES[boss]["name"]):
                multiworld = with_requirement([boss])
                off = reach(multiworld, without=[WITNESS])
                on = reach(multiworld)
                self.assertNotIn(arena, off["regions"])
                self.assertEqual(on["regions"], self.base["regions"])
                self.assertEqual(on["locs"], self.base["locs"])
                self.assertTrue(on["victory"])
                self.assertEqual(off["victory"], boss not in GOAL_BOSSES)
                if boss in F.PSEUDOROIDS:
                    self.assertFalse(any(r.split("/")[0] == "d05" for r in off["regions"]),
                                     "D-5 is reachable without the boss rush")

    def test_all_bosses_at_once(self) -> None:
        """With every boss requiring the witness, no arena is in logic until it is owned."""
        multiworld = with_requirement(self.arenas)
        off = reach(multiworld, without=[WITNESS])
        on = reach(multiworld)
        for boss, arena in self.arenas.items():
            self.assertNotIn(arena, off["regions"], boss)
        self.assertFalse(off["victory"])
        self.assertEqual(on["regions"], self.base["regions"])
        self.assertEqual(on["locs"], self.base["locs"])

    def test_biometal_from_either_boss(self) -> None:
        """A biometal stays in logic while one of its two bosses is open, and leaves with both blocked."""
        for letter, pair in BIOMETAL_PAIRS.items():
            location = "Obtain Biometal " + letter
            with self.subTest(biometal=letter):
                self.assertIn(location, self.base["locs"])
                for boss in pair:
                    self.assertIn(location, reach(with_requirement([boss]), without=[WITNESS])["locs"], boss)
                self.assertNotIn(location, reach(with_requirement(pair), without=[WITNESS])["locs"])


class TestBossLogicOption(unittest.TestCase):
    def test_unknown_boss(self) -> None:
        """A boss name the roster does not know fails generation with an OptionError."""
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"boss_logic": {"Nobody": "HX"}})

    def test_bad_expression(self) -> None:
        """A requirement that does not parse fails generation."""
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"boss_logic": {"Hivolt": "HX &"}})

    def test_another_boss_cannot_be_required(self) -> None:
        """A boss may not depend on another boss or on a mission event."""
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"boss_logic": {"Hivolt": "BOSS_LURERRE"}})

    def test_impossible_requirement(self) -> None:
        """A requirement the pool cannot meet (five Life Ups) fails before the fill."""
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={"boss_logic": {"Serpent": "Life Up x5"}})

    def test_aliases(self) -> None:
        """Room codes, plain-language items and lists are accepted spellings."""
        parsed = bosses.parse_boss_logic({
            "E-7": "Model HX (full) & Life Up x2",
            "Serpent": "all biometals | Absorber Chip",
            "Rayfly": None,                    # empty entries are dropped
            "Flammole": ["Yellow Card Key", "Sub Tank x1"],
        })
        self.assertEqual(parsed, {
            "hivolt": {"normal": [["HX2", "LIFEUP>=2"]]},
            "serpent": {"normal": [["ALL6"], ["CHIP_ABSORBER"]]},
            "flammole": {"normal": [["YELLOW", "SUBTANK>=1"]]},
        })
        self.assertEqual(bosses.describe(parsed)["Serpent"], "ALL6 | CHIP_ABSORBER")

    def test_duplicate_boss(self) -> None:
        """The same boss under two spellings is an error."""
        with self.assertRaises(ValueError):
            bosses.parse_boss_logic({"Hivolt": "HX", "E-7": "LX"})
