"""The logic document format: parser, requirements, validator and text twin.

logic_format.py and data.py import nothing from Archipelago, so they are loaded
by path and these tests run without a checkout.
"""
import copy
import importlib.util
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location("mmzx_test_" + name, PKG / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


F = _load("logic_format")
D = _load("data")
WORLD = F.build_world(D)
DOC = F.load_logic(PKG / "logic" / "logic.json", WORLD)


class FakeState:
    """Enough of CollectionState for compiled rules: item counts of one player."""

    def __init__(self, **counts):
        self.counts = counts

    def has(self, name, player, count=1):
        return self.counts.get(name, 0) >= count

    def has_any(self, names, player):
        return any(self.has(n, player) for n in names)

    def has_all(self, names, player):
        return all(self.has(n, player) for n in names)

    def has_from_list(self, names, player, count):
        return sum(1 for n in names if self.has(n, player)) >= count


class TestParser(unittest.TestCase):
    def test_and_or_precedence(self) -> None:
        """AND binds tighter than OR; the result is a DNF."""
        self.assertEqual(F.parse_expr("HX & LX | FX"), [["HX", "LX"], ["FX"]])
        self.assertEqual(F.parse_expr("(HX | FX) & YELLOW"), [["HX", "YELLOW"], ["FX", "YELLOW"]])

    def test_spellings(self) -> None:
        """Words, symbols and case all parse to the same atoms."""
        self.assertEqual(F.parse_expr("hx and lx"), [["HX", "LX"]])
        self.assertEqual(F.parse_expr("HX && LX"), [["HX", "LX"]])
        self.assertEqual(F.parse_expr("HX || LX"), [["HX"], ["LX"]])
        self.assertEqual(F.parse_expr("LIFEUP >= 2"), [["LIFEUP>=2"]])

    def test_constants(self) -> None:
        """TRUE is the free alternative, NEVER has none, and both simplify away."""
        self.assertEqual(F.parse_expr("TRUE"), F.DNF_TRUE)
        self.assertEqual(F.parse_expr(""), F.DNF_TRUE)
        self.assertEqual(F.parse_expr("NEVER"), F.DNF_FALSE)
        self.assertEqual(F.parse_expr("HX & NEVER"), F.DNF_FALSE)
        self.assertEqual(F.parse_expr("HX | TRUE"), F.DNF_TRUE)

    def test_errors(self) -> None:
        """Unknown atoms, dangling operators and unbalanced parentheses are ValueErrors."""
        for bad in ("FOO", "HX &", "(HX", "LIFEUP>=0", "HX LX"):
            with self.subTest(expr=bad):
                self.assertRaises(ValueError, F.parse_expr, bad)

    def test_canonical_atoms(self) -> None:
        """Atoms are normalized to upper case without spaces; counts keep their number."""
        self.assertEqual(F.canonical_atom(" lifeup>=3 "), "LIFEUP>=3")
        self.assertEqual(F.canonical_atom("model"), "MODEL")
        self.assertEqual(F.canonical_atom("hx2"), "HX2")
        self.assertEqual(F.canonical_atom("boss_hivolt"), "BOSS_HIVOLT")
        self.assertIsNone(F.canonical_atom("foo"))

    def test_dnf_normalize_absorbs(self) -> None:
        """Duplicates go and an alternative that contains another is dropped."""
        self.assertEqual(F.dnf_normalize([["HX", "LX"], ["HX"], ["HX", "HX"]]), [["HX"]])

    def test_dnf_to_text(self) -> None:
        """The text form names free and never, else joins the alternatives."""
        self.assertEqual(F.dnf_to_text([["HX", "LX"], ["FX"]]), "HX & LX | FX")
        self.assertEqual(F.dnf_to_text(F.DNF_FALSE), "never")
        self.assertEqual(F.dnf_to_text(F.DNF_TRUE), "free")


class TestRequirements(unittest.TestCase):
    REQ = {"normal": [["LX"]], "expert": [["MODEL"]]}

    def test_tiers_are_cumulative(self) -> None:
        """Expert adds its alternatives to the normal ones."""
        self.assertEqual(F.req_alternatives(self.REQ, "normal"), [["LX"]])
        self.assertEqual(F.req_alternatives(self.REQ, "expert"), [["LX"], ["MODEL"]])
        self.assertEqual(F.req_alternatives(None, "normal"), F.DNF_TRUE)

    def test_free_and_never(self) -> None:
        """A missing requirement is free; an empty one is never met."""
        self.assertTrue(F.req_is_free(None))
        self.assertTrue(F.req_is_free(F.req_free()))
        self.assertFalse(F.req_is_free(self.REQ))
        self.assertTrue(F.req_is_never({"normal": []}))
        self.assertFalse(F.req_is_never(self.REQ))

    def test_lines(self) -> None:
        """One text line per alternative, tagged with its tier."""
        self.assertEqual(F.req_to_lines(self.REQ), ["normal: LX", "expert: MODEL"])
        self.assertEqual(F.req_to_lines({"normal": []}), ["never"])
        self.assertEqual(F.req_to_lines(None), ["free"])

    def test_atoms_and_promotion(self) -> None:
        """Chips and count atoms name useful items that a rule turns into progression."""
        self.assertEqual(F.req_atoms(self.REQ), {"LX", "MODEL"})
        self.assertEqual(F.progression_items({"CHIP_ABSORBER", "LIFEUP>=2", "HX"}), {"Absorber Chip", "Life Up"})

    def test_compiled_rules(self) -> None:
        """Compiled rules read item counts: any model, both halves, mission counts."""
        rule = F.compile_req({"normal": [["MODEL"]]}, "normal", 1)
        self.assertFalse(rule(FakeState(**{"Model Hu": 1})))
        self.assertTrue(rule(FakeState(**{"Model FX": 1})) or rule(FakeState(**{"Progressive Model FX": 1})))
        rule = F.compile_req({"normal": [["HX2"]]}, "normal", 1)
        self.assertFalse(rule(FakeState(**{"Progressive Model HX": 1})))
        self.assertTrue(rule(FakeState(**{"Progressive Model HX": 2})))
        rule = F.compile_req({"normal": [["MISSIONS>=2"]]}, "normal", 1)
        self.assertFalse(rule(FakeState(**{"Cleared: Search The Plant": 1})))
        self.assertTrue(rule(FakeState(**{"Cleared: Search The Plant": 1, "Cleared: Save The People": 1})))

    def test_hu_and_bosses_are_free_unless_configured(self) -> None:
        """HU without hu_in_pool and a BOSS_* atom without a YAML rule compile to no rule."""
        self.assertIsNone(F.compile_req({"normal": [["HU"]]}, "normal", 1))
        self.assertIsNotNone(F.compile_req({"normal": [["HU"]]}, "normal", 1, hu_in_pool=True))
        self.assertIsNone(F.compile_req({"normal": [["BOSS_HIVOLT"]]}, "normal", 1))
        rule = F.compile_req({"normal": [["BOSS_HIVOLT"]]}, "normal", 1,
                             extra_atoms={"BOSS_HIVOLT": lambda state: state.has("Absorber Chip", 1)})
        self.assertFalse(rule(FakeState()))
        self.assertTrue(rule(FakeState(**{"Absorber Chip": 1})))
        # an unconfigured boss alternative frees the whole requirement at the tier that has it
        req = {"normal": [["LX"]], "expert": [["BOSS_HIVOLT"]]}
        self.assertIsNotNone(F.compile_req(req, "normal", 1))
        self.assertIsNone(F.compile_req(req, "expert", 1))


class TestWorldData(unittest.TestCase):
    def test_room_labels(self) -> None:
        """Room codes read as area-number labels, the hub floors as Hub and Hub-2."""
        self.assertEqual(F.room_label("a01"), "A-1")
        self.assertEqual(F.room_label("z01"), "Hub")
        self.assertEqual(F.room_label("z02"), "Hub-2")
        self.assertEqual(F.region_name("e07", "main"), "e07")
        self.assertEqual(F.region_name("e07", "boss-room"), "e07/boss-room")

    def test_unavailable_atoms(self) -> None:
        """Only the White Card Key is an unpooled item with an atom."""
        self.assertEqual(F.unavailable_atoms(D), {"WHITE"})

    def test_point_in_polygon(self) -> None:
        """Ray casting on a square."""
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(F.point_in_poly((5, 5), square))
        self.assertFalse(F.point_in_poly((15, 5), square))


class TestDocument(unittest.TestCase):
    def test_validates_without_errors(self) -> None:
        """The bundled logic.json is consistent with data.py."""
        report = F.validate(WORLD, DOC, D.HUB_ROOM, F.unavailable_atoms(D))
        self.assertEqual(report["errors"], [])

    def test_text_twin_is_current(self) -> None:
        """logic.txt is exactly what the document exports; run tools/check_logic.py otherwise."""
        expected = (PKG / "logic" / "logic.txt").read_text(encoding="utf-8")
        self.assertEqual(F.export_txt(WORLD, DOC, D.HUB_ROOM), expected)

    def test_every_room_is_drawn(self) -> None:
        """Every room of the door table has an entry with a main region."""
        self.assertEqual(set(DOC["rooms"]), set(WORLD["rooms"]))
        for room, entry in DOC["rooms"].items():
            self.assertIn("main", entry["regions"], room)

    def test_every_boss_is_anchored(self) -> None:
        """All fifteen bosses have exactly one arena tagged."""
        self.assertEqual(F.bosses_anchored(DOC), set(F.BOSSES))
        arenas = F.boss_regions(DOC)
        self.assertEqual(len(arenas), len(F.BOSSES))
        self.assertEqual(set(arenas.values()), set(F.BOSSES))

    def test_biometals_have_two_placements(self) -> None:
        """Each biometal location counts in both rooms where its boss pair is fought."""
        for letter, rooms in (("H", {"e07", "i03"}), ("L", {"f05", "j05"}),
                              ("F", {"g05", "k04"}), ("P", {"h04", "l04"})):
            placements = F.check_placements(WORLD, DOC, "Obtain Biometal " + letter)
            self.assertEqual({room for room, _ in placements}, rooms)

    def test_validator_catches_mistakes(self) -> None:
        """A missing room, an unknown atom and a boss tagged twice are errors."""
        doc = copy.deepcopy(DOC)
        del doc["rooms"]["a01"]
        doc["rooms"]["b01"]["conns"].append({"from": "main", "to": "main", "req": {"normal": [["FOO"]]}})
        doc["rooms"]["b01"]["regions"]["main"]["boss"] = "hivolt"
        errors = F.validate(WORLD, doc, D.HUB_ROOM)["errors"]
        self.assertTrue(any("a01 is missing" in e for e in errors), errors)
        self.assertTrue(any("FOO" in e for e in errors), errors)
        self.assertTrue(any("to itself" in e for e in errors), errors)
        self.assertTrue(any("already tagged" in e for e in errors), errors)

    def test_empty_document_normalizes(self) -> None:
        """An empty document gains every room with a bare main region."""
        doc = F.normalize_logic({}, WORLD)
        self.assertEqual(set(doc["rooms"]), set(WORLD["rooms"]))
        self.assertEqual(F.validate(WORLD, doc, D.HUB_ROOM)["errors"], [])
