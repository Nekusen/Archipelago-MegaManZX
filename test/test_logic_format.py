"""The logic document format: parser, requirements, intermediate representation, validator and exporters.

logic/document.py, data.py and door_data.py import nothing from Archipelago, so they are loaded
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


F = _load("logic/document")
D = _load("data")
S = _load("door_data")
WORLD = F.build_world(D, S.SITES)
DOC = F.load_logic(PKG / "logic" / "logic.json", WORLD)


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

    def test_atoms_and_promotion(self) -> None:
        """Chips and count atoms name useful items that a rule turns into progression."""
        self.assertEqual(F.req_atoms(self.REQ), {"LX", "MODEL"})
        self.assertEqual(F.progression_items({"CHIP_ABSORBER", "LIFEUP>=2", "HX"}), {"Absorber Chip", "Life Up"})

    def test_intermediate_representation(self) -> None:
        """A requirement is the OR of its alternatives, each the AND of its atoms; the host atoms are macros."""
        self.assertEqual(F.req_ir({"normal": [["HX", "LX"], ["FX"]]}, "normal"),
                         ("or", (("and", (("macro", "HX"), ("macro", "LX"))), ("macro", "FX"))))
        self.assertEqual(F.req_ir({"normal": [["MODEL"]]}, "normal"), ("macro", "MODEL"))
        self.assertEqual(F.req_ir({"normal": [["HX2"]]}, "normal"), ("macro", "HX2"))
        self.assertEqual(F.req_ir({"normal": [["MISSIONS>=2"]]}, "normal"),
                         ("has_from_list", tuple(F.AREA_MISSION_EVENTS), 2))
        self.assertEqual(F.req_ir({"normal": [["LIFEUP>=3"]]}, "normal"), ("has", "Life Up", 3))
        self.assertEqual(F.req_ir({"normal": [["BOSS_HIVOLT"]]}, "normal"), ("boss", "hivolt"))
        self.assertEqual(F.req_ir(self.REQ, "normal"), ("macro", "LX"))
        self.assertEqual(F.req_ir(self.REQ, "expert"), ("or", (("macro", "LX"), ("macro", "MODEL"))))
        self.assertEqual(F.req_ir(None, "normal"), F.IR_TRUE)
        self.assertEqual(F.req_ir({"normal": []}, "normal"), F.IR_FALSE)
        self.assertRaises(ValueError, F.atom_ir, "FOO")

    def test_macros_follow_the_options(self) -> None:
        """The model halves, the human form, the story atoms and the seal expand to option-filtered rules."""
        half, full = F.MACRO_IR["HX"][1]
        self.assertEqual(half, ("has_if", "Progressive Model HX", 1, "ProgressiveModels", 1, "eq"))
        self.assertEqual(full, ("has_if", "Model HX", 1, "ProgressiveModels", 0, "eq"))
        self.assertEqual(F.MACRO_IR["HX2"][1][0], ("has_if", "Progressive Model HX", 2, "ProgressiveModels", 1, "eq"))
        self.assertEqual(F.MACRO_IR["HU"][1][1], ("option_true", "HuInPool", 0, "eq"))
        self.assertEqual(F.MACRO_IR["GOAL"], ("goal",))
        self.assertEqual(F.MACRO_IR["SEAL"], ("seal",))
        self.assertIn(("has_if", F.BRIDGE_EVENT, 1, "MissionObjectives", 1, "eq"), F.MACRO_IR[F.D_BRIDGE][1])
        self.assertIn(("option_true", "MissionObjectives", 0, "eq"), F.MACRO_IR[F.D_BRIDGE][1])
        # the slow lava depends on the place it is asked at; nowhere in particular, on its event
        site = {"at": "k04/lava-chase", "control": "k01/region-7"}
        self.assertEqual(F.atom_ir(F.SLOW_LAVA, site), ("or", (("macro", "LAVA_ITEM"), ("lava", "k04/lava-chase", "k01/region-7"))))
        self.assertEqual(F.atom_ir(F.SLOW_LAVA), ("macro", F.SLOW_LAVA))

    def test_ir_serializes_as_the_rule_builder_does(self) -> None:
        """The dict of a node is Rule.to_dict: rule, options, filtered_resolution and args."""
        self.assertEqual(F.ir_to_dict(("has_if", "Model HX", 1, "ProgressiveModels", 0, "eq")), {
            "rule": "Has", "filtered_resolution": False, "args": {"item_name": "Model HX", "count": 1},
            "options": [{"option": "worlds.mmzx.options.ProgressiveModels", "value": 0, "operator": "eq"}]})
        self.assertTrue(F.ir_to_dict(("needs_if", "Computer Chip", 1, "MissionObjectives", 2, "eq"))["filtered_resolution"])
        self.assertEqual(F.ir_to_dict(("macro", "GOAL")), {"rule": "GoalRequirement", "options": [],
                                                           "filtered_resolution": False, "args": {}})
        self.assertEqual(F.ir_to_py(("and", (("macro", "LX"), ("or", (("macro", "HX"), ("has", "Model X", 1)))))),
                         'LX & (HX | Has("Model X"))')


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

    def test_exporters_need_no_archipelago(self) -> None:
        """The generated module and its JSON come out of the document alone, and the module compiles."""
        text = F.export_rules_py(WORLD, DOC)
        compile(text, "rules.py", "exec")
        self.assertIn('ENTRANCES["Start"] = Edge("Menu", "z01", True_())', text)
        exported = F.export_rules_json(WORLD, DOC)
        self.assertEqual(exported["errors"], [])
        self.assertEqual(exported["start"], "z01")
        self.assertIn("K-1: Sub Tank", exported["rooms"]["k01"]["locations"])

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
