"""The generated logic/rules.py and logic/rules.json: in sync with the document, and what the world builds from."""
import ast
import copy
import json
import unittest
from pathlib import Path

from BaseClasses import CollectionState
from test.general import setup_multiworld

from .. import MMZXWorld
from ..data import LOCATIONS, STORY_COUNTS, STORY_LAVA_ITEM, STORY_SWITCH_ITEM
from ..locations import PICKUP_OPTION_BY_CATEGORY, STORY_ITEMS, locations_for_options
from ..logic import TIER, WORLD, builder, load_document
from ..logic import document as F
from ..logic import rules as R
from ..regions import reachable_regions
from ..logic.builder import (BossRequirement, DoorKey, Edge, GoalRequirement, LavaCarriedTo, ReachedAtLeast,
                             SealRequirement, Spot)
from .bases import MMZXTestBase, WITNESS

LOGIC = Path(__file__).resolve().parents[1] / "logic"
REGENERATE = ("logic/%s is behind logic/logic.json: save the document in the logic editor "
              "(tools/run_logic_editor.bat) or run tools/check_logic.py, and commit the generated files")
LAVA_EDGE = "k04: lava-chase -> hidden-path"
HIVOLT_ARENA_WAY = "e07: e-5-entrance -> boss-room"
RUSH_DOOR = next(iter(F.BOSS_RUSH_DOORS))
SPRINKLER_KEY = next(iter(STORY_COUNTS))


def plain(data):
    """A rule dict as JSON carries it: tuples become lists."""
    return json.loads(json.dumps(data))


def module_rules():
    """Every rule the generated module holds, by the name it is set on."""
    yield from ((name, edge.rule) for name, edge in R.ENTRANCES.items())
    yield from ((name, spot.rule) for name, spot in R.LOCATIONS.items())


def rule_of(world, expr):
    """The resolved rule of a text requirement for a world."""
    return builder.compile_req(F.req_from_expr(expr)).resolve(world)


def world_with(**options):
    return setup_multiworld(MMZXWorld, options=options).worlds[1]


def pool_without(multiworld, *names) -> CollectionState:
    """The whole pool collected, but the named items."""
    state = CollectionState(multiworld)
    for item in multiworld.itempool:
        if item.name not in names:
            state.collect(item, prevent_sweep=True)
    state.sweep_for_advancements()
    return state


class TestGeneratedFiles(unittest.TestCase):
    def test_rules_py_is_in_sync_with_the_document(self):
        self.assertEqual((LOGIC / "rules.py").read_text(encoding="utf-8"), F.export_rules_py(WORLD, load_document()),
                         REGENERATE % "rules.py")

    def test_rules_json_is_in_sync_with_the_document(self):
        self.assertEqual(json.loads((LOGIC / "rules.json").read_text(encoding="utf-8")),
                         plain(F.export_rules_json(WORLD, load_document())), REGENERATE % "rules.json")

    def test_rules_py_is_valid_python(self):
        ast.parse((LOGIC / "rules.py").read_text(encoding="utf-8"))

    def test_the_document_has_no_errors(self):
        self.assertEqual(R.ERRORS, [])

    def test_every_entrance_joins_regions_of_the_module(self):
        regions = set(R.REGIONS)
        self.assertEqual(len(regions), len(R.REGIONS))
        self.assertIn(R.START, regions)
        for name, edge in R.ENTRANCES.items():
            with self.subTest(entrance=name):
                self.assertIsInstance(edge, Edge)
                self.assertIn(edge.src, regions)
                self.assertIn(edge.dst, regions)
        self.assertEqual(R.ENTRANCES[F.START_ENTRANCE].dst, R.START)

    def test_every_location_any_option_turns_on_sits_in_a_region_of_the_module(self):
        regions = set(R.REGIONS)
        every_option_on = locations_for_options(pickups={cat: True for cat in PICKUP_OPTION_BY_CATEGORY}, story=STORY_ITEMS)
        self.assertGreater(len(every_option_on), len(locations_for_options()))
        for name in [*every_option_on, *R.EVENTS]:
            with self.subTest(location=name):
                self.assertIsInstance(R.LOCATIONS[name], Spot)
                self.assertIn(R.LOCATIONS[name].region, regions)
        self.assertEqual(R.EVENTS[F.VICTORY_LOCATION], F.VICTORY)
        self.assertLessEqual(set(LOCATIONS), set(R.LOCATIONS))

    def test_every_rule_serializes_as_the_exporter_writes_it(self):
        """The standalone exporter and the Rule Builder agree on every rule of the document."""
        doc = load_document()
        members = F.resolve_members(WORLD, doc)
        gates = F.gate_table(doc, TIER)
        context = F.rule_context(WORLD, doc, members)
        exported = F.export_rules_json(WORLD, doc)
        present = set(exported["regions"])
        count = 0
        for name, src, dst, ir in F.entrance_rules(WORLD, doc, members, TIER, context=context):
            if src not in present or dst not in present:
                continue        # the rooms the start never leads to are left out of the module
            room = (dst if src == F.MENU else src).split("/")[0]
            with self.subTest(entrance=name):
                self.assertEqual(plain(builder.compile_ir(ir, gates).to_dict()),
                                 plain(exported["rooms"][room]["entrances"][name]["rule"]))
            count += 1
        needed = F.global_reachability(WORLD, doc, members, TIER)
        for name in WORLD["locations"]:
            parent, ir = F.location_rule(WORLD, doc, members, needed, name, TIER, context=context)
            placed = [room for room, _ in F.check_placements(WORLD, doc, name)]
            entry = (exported["rooms"][placed[0]]["locations"] if placed else exported["unplaced"])[name]
            with self.subTest(location=name):
                self.assertEqual(entry["region"], parent)
                self.assertEqual(plain(builder.compile_ir(ir, gates).to_dict()), plain(entry["rule"]))
            count += 1
        self.assertGreater(count, 900)

    def test_a_broken_document_still_generates_a_module_that_says_so(self):
        """An unknown atom makes its rule never and lands in ERRORS; the module still compiles."""
        doc = copy.deepcopy(load_document())
        doc["checks"]["A-3: Apple"] = {"req": {"normal": [["NO_SUCH_ATOM"]]}}
        errors = ["check: unknown atom"]
        text = F.export_rules_py(WORLD, doc, errors=errors)
        compile(text, "rules.py", "exec")
        self.assertIn('ERRORS = [\n    "check: unknown atom",\n    "A-3: Apple: unknown atom \'NO_SUCH_ATOM\'",', text)
        self.assertIn('LOCATIONS["A-3: Apple"] = Spot("a03", False_())   # ERROR: unknown atom', text)
        self.assertEqual(F.export_rules_json(WORLD, doc, errors=errors)["errors"][:1], errors)


class TestRulesModule(MMZXTestBase):
    """The world is built from the module: the very objects of rules.py, resolved for the player."""

    def test_the_world_uses_the_rules_of_the_module(self):
        for entrance in self.multiworld.get_entrances(self.player):
            edge = R.ENTRANCES[entrance.name]
            with self.subTest(entrance=entrance.name):
                self.assertEqual((entrance.parent_region.name, entrance.connected_region.name), (edge.src, edge.dst))
                self.assertIs(entrance.access_rule, edge.rule.resolve(self.world))
        for location in self.multiworld.get_locations(self.player):
            spot = R.LOCATIONS[location.name]
            with self.subTest(location=location.name):
                self.assertEqual(location.parent_region.name, spot.region)
                self.assertIs(location.access_rule, spot.rule.resolve(self.world))
        self.assertEqual({region.name for region in self.multiworld.get_regions(self.player)},
                         set(R.REGIONS) & reachable_regions(self.world))

    def test_every_region_a_rule_names_is_a_region_of_the_module(self):
        regions = set(R.REGIONS)
        for name, rule in module_rules():
            with self.subTest(rule=name):
                self.assertLessEqual(set(rule.resolve(self.world).region_dependencies()), regions)

    def test_the_module_covers_every_location_of_the_data(self):
        self.assertLessEqual(set(WORLD["locations"]), set(R.LOCATIONS))

    def test_the_boss_arenas_anchor_every_boss(self):
        self.assertEqual(set(R.BOSS_ARENAS), set(F.BOSSES))
        self.assertEqual(R.BOSS_ARENAS["hivolt"], "e07/boss-room")
        self.assertEqual(set(R.COUNTED_ITEMS), F.count_items_used(load_document()))

    def test_events_of_other_modes_are_not_created(self):
        """Without mission_objectives: locations_and_items the control, the switch and the bridge stand for their item;
        the bridge only with checks, and the biometal events only behind the biometals seal."""
        events = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is None}
        self.assertIn(F.LAVA_EVENT, events)
        self.assertIn(F.SWITCH_EVENT, events)
        self.assertNotIn(F.BRIDGE_EVENT, events)
        self.assertFalse(events & {F.OBTAINED_PREFIX + "Biometal H"})
        self.assertIn(F.VICTORY_LOCATION, events)


class TestExplanations(MMZXTestBase):
    options = {"boss_logic": {"Hivolt": "Sub Tank x2"}}

    def test_a_boss_arena_says_what_the_yaml_asks(self):
        entrance = self.multiworld.get_entrance(HIVOLT_ARENA_WAY, self.player)
        state = self.multiworld.state
        self.assertIn("Beat Hivolt with Missing 2x Sub Tank", entrance.access_rule.explain_str(state))
        parts = entrance.access_rule.explain_json(state)
        self.assertTrue(any(part.get("text") == "Beat Hivolt with " for part in parts))
        self.assertTrue(any(part.get("text") == "Sub Tank" and part.get("color") == "salmon" for part in parts))
        self.collect_by_name("Sub Tank")
        self.assertIn("Beat Hivolt with Has 2x Sub Tank", entrance.access_rule.explain_str(state))

    def test_a_location_explains_the_model_and_the_event_it_wants(self):
        location = self.multiworld.get_location("K-1: Sub Tank", self.player)
        text = location.access_rule.explain_str(self.multiworld.state)
        self.assertIn("Progressive Model LX", text)
        self.assertIn(F.SWITCH_EVENT, text)

    def test_the_goal_explains_the_requirements_of_the_seed(self):
        victory = self.multiworld.get_location(F.VICTORY_LOCATION, self.player)
        text = victory.access_rule.explain_str(self.multiworld.state)
        self.assertIn("Goal: Has 1/6 unique items from", text)
        self.assertIn("Progressive Model HX", text)


class TestIndirectConditions(MMZXTestBase):
    def test_the_lava_walk_registers_the_regions_of_its_area(self):
        entrance = self.multiworld.get_entrance(LAVA_EDGE, self.player)
        regions = set(entrance.access_rule.region_dependencies())
        self.assertIn("k01/region-7", regions)
        self.assertTrue(all(F.area_of(name) == "k" for name in regions))
        for name in regions:
            region = self.multiworld.get_region(name, self.player)
            self.assertIn(entrance, self.multiworld.indirect_connections[region])

    def test_the_hidden_path_of_k4_needs_the_way_in_from_k3(self):
        """The lava chase only arms through the K-3 door: a lock on that door keeps the hidden path out of logic."""
        edge = self.multiworld.get_entrance(LAVA_EDGE, self.player)
        self.assertIn("Can reach entrance %s" % F.LAVA_CHASE_DOOR, str(edge.access_rule))
        self.assertIn(F.LAVA_CHASE_DOOR, edge.access_rule.entrance_dependencies())
        self.assertTrue(edge.access_rule(pool_without(self.multiworld)))
        self.world.door_keys = {door: "Red Card Key" for door in (F.LAVA_CHASE_DOOR, "k04 door (640,528)")}
        try:
            self.assertFalse(edge.access_rule(pool_without(self.multiworld, "Red Card Key")))
            self.assertTrue(edge.access_rule(pool_without(self.multiworld)))
        finally:
            self.world.door_keys = {}

    def test_every_region_dependency_is_registered(self):
        registered = {(region.name, entrance.name) for region, entrances in self.multiworld.indirect_connections.items()
                      for entrance in entrances if region.player == self.player}
        for entrance in self.multiworld.get_entrances(self.player):
            for name in getattr(entrance.access_rule, "region_dependencies", dict)():
                self.assertIn((name, entrance.name), registered)
        self.assertTrue(registered)


class TestBossRequirementPerPlayer(unittest.TestCase):
    def test_each_player_gets_their_own_boss_logic(self):
        multiworld = setup_multiworld([MMZXWorld, MMZXWorld], options=[{"boss_logic": {"Hivolt": WITNESS}}, {}])
        strict = BossRequirement("hivolt").resolve(multiworld.worlds[1])
        free = BossRequirement("hivolt").resolve(multiworld.worlds[2])
        self.assertIsInstance(strict, BossRequirement.Resolved)
        self.assertTrue(free.always_true)
        state = pool_without(multiworld, WITNESS)
        self.assertFalse(multiworld.get_entrance(HIVOLT_ARENA_WAY, 1).access_rule(state))
        self.assertTrue(multiworld.get_entrance(HIVOLT_ARENA_WAY, 2).access_rule(state))
        self.assertEqual(str(BossRequirement("hivolt")), "BossRequirement(hivolt)")


class TestModelAtoms(unittest.TestCase):
    def test_a_full_model_is_both_halves_or_the_single_item(self):
        progressive, full = world_with(), world_with(progressive_models=False)
        self.assertEqual(str(rule_of(progressive, "HX2")), "Has 2x Progressive Model HX")
        self.assertEqual(str(rule_of(full, "HX2")), "Has Model HX")
        self.assertEqual(str(rule_of(progressive, "HX")), "Has Progressive Model HX")
        self.assertEqual(str(rule_of(full, "HX")), "Has Model HX")

    def test_any_model_resolves_to_one_list_of_the_slots_items(self):
        progressive, full = world_with(), world_with(progressive_models=False)
        self.assertEqual(str(rule_of(progressive, "MODEL")), "Has any of (Model OX, Model X, Model ZX, Progressive Model FX, "
                                                             "Progressive Model HX, Progressive Model LX, Progressive Model PX)")
        self.assertEqual(str(rule_of(full, "MODEL")), "Has any of (Model FX, Model HX, Model LX, Model OX, Model PX, Model X, Model ZX)")
        self.assertEqual(str(rule_of(full, "ALL6")), "Has all of (Model FX, Model HX, Model LX, Model PX, Model X, Model ZX)")

    def test_the_human_form_is_an_item_only_in_the_pool(self):
        self.assertEqual(str(rule_of(world_with(hu_in_pool=True), "HU")), "Has Model Hu")
        self.assertTrue(rule_of(world_with(hu_in_pool=False), "HU").always_true)
        # with no starting model Hu is the only form: never an item, whatever the YAML says
        self.assertTrue(rule_of(world_with(starting_model="none", hu_in_pool=True), "HU").always_true)


class TestMissionObjectiveAtoms(unittest.TestCase):
    def test_the_story_atoms_follow_the_mode(self):
        off, checks, items = (world_with(mission_objectives=mode) for mode in ("off", "locations_only", "locations_and_items"))
        self.assertEqual(str(rule_of(items, "K_DOOR_SWITCH")), "Has " + STORY_SWITCH_ITEM)
        self.assertEqual(str(rule_of(off, "K_DOOR_SWITCH")), "Has " + F.SWITCH_EVENT)
        self.assertEqual(str(rule_of(checks, "K_DOOR_SWITCH")), "Has " + F.SWITCH_EVENT)
        self.assertTrue(rule_of(off, "D_BRIDGE").always_true)
        self.assertEqual(str(rule_of(checks, "D_BRIDGE")), "Has " + F.BRIDGE_EVENT)
        self.assertEqual(str(rule_of(items, "D_BRIDGE")), "Has Area D Bridge")
        self.assertEqual(str(rule_of(items, "SLOW_LAVA")), "Has " + STORY_LAVA_ITEM)
        self.assertEqual(str(rule_of(off, "SLOW_LAVA")), "Has " + F.LAVA_EVENT)

    def test_a_report_asks_for_its_object_only_with_items(self):
        spot = R.LOCATIONS["Mission - Locate Giro"]
        self.assertIn("Computer Chip", str(spot.rule.resolve(world_with(mission_objectives="locations_and_items"))))
        self.assertNotIn("Computer Chip", str(spot.rule.resolve(world_with(mission_objectives="locations_only"))))
        self.assertNotIn("Computer Chip", str(spot.rule.resolve(world_with())))

    def test_the_lava_is_walked_from_its_control_unless_it_is_an_item(self):
        edge = R.ENTRANCES[LAVA_EDGE]
        walked = edge.rule.resolve(world_with())
        self.assertTrue(walked.force_recalculate)
        self.assertIn("Slow lava carried from its control to k04/lava-chase", str(walked))
        carried = edge.rule.resolve(world_with(mission_objectives="locations_and_items"))
        self.assertFalse(carried.force_recalculate)
        self.assertIn(STORY_LAVA_ITEM, str(carried))
        self.assertNotIn("carried", str(carried))

    def test_the_sprinkler_key_counts_the_rescues_in_reach(self):
        multiworld = setup_multiworld(MMZXWorld, options={"mission_objectives": "locations_and_items"})
        rule = multiworld.get_location(SPRINKLER_KEY, 1).access_rule
        count, group = STORY_COUNTS[SPRINKLER_KEY]
        self.assertEqual(set(rule.location_dependencies()), set(group))
        self.assertIn("Reached %d/%d of (" % (len(group), count), rule.explain_str(pool_without(multiworld)))
        carrelet = multiworld.get_location("C-1: Guardian Carrelet", 1).access_rule
        self.assertIn("C-1: Guardian Oeillet", carrelet.location_dependencies())
        self.assertEqual(str(ReachedAtLeast(2, ("a", "b", "c"))), "ReachedAtLeast(2, ['a', 'b', 'c'])")


class TestGoalRequirement(unittest.TestCase):
    def test_each_class_of_goal_resolves_to_its_items(self):
        biometals = GoalRequirement().resolve(world_with())
        self.assertEqual(str(biometals), "Goal: Has 6x unique items from (Model X, Model ZX, Progressive Model FX, "
                                         "Progressive Model HX, Progressive Model LX, Progressive Model PX)")
        disks = GoalRequirement().resolve(world_with(goal_requirements=["Secret Disks"], required_secret_disks=5))
        self.assertEqual(str(disks), "Goal: Has 5x Secret Disk")
        missions = GoalRequirement().resolve(world_with(goal_requirements=["Missions"], required_missions=3))
        self.assertTrue(str(missions).startswith("Goal: Has 3x unique items from (Cleared: "))
        both = GoalRequirement().resolve(world_with(goal_requirements=["Secret Disks", "Missions"], required_secret_disks=2,
                                                    required_missions=2))
        self.assertIn("Secret Disk", str(both))
        self.assertIn("Cleared: ", str(both))

    def test_full_models_count_both_halves(self):
        full = GoalRequirement().resolve(world_with(require_full_models=True))
        self.assertEqual(str(full), "Goal: Has 0/6 models from (Model X, Model ZX, Progressive Model HX x2, "
                                    "Progressive Model FX x2, Progressive Model LX x2, Progressive Model PX x2)")
        multiworld = setup_multiworld(MMZXWorld, options={"goal_requirements": ["Secret Disks"], "required_secret_disks": 3,
                                                          "total_secret_disks": 5})
        goal = GoalRequirement().resolve(multiworld.worlds[1])
        state = CollectionState(multiworld)
        disks = [item for item in multiworld.itempool if item.name == "Secret Disk"]
        for item in disks[:2]:
            state.collect(item, prevent_sweep=True)
        self.assertFalse(goal(state))
        state.collect(disks[2], prevent_sweep=True)
        self.assertTrue(goal(state))
        self.assertEqual(goal.explain_str(state), "Goal: Has 3x Secret Disk")

    def test_the_goal_guards_the_victory_and_the_slither_gate(self):
        world = world_with()
        goal = GoalRequirement().resolve(world)
        self.assertIn(goal, R.LOCATIONS[F.VICTORY_LOCATION].rule.resolve(world).children)
        self.assertIs(R.GATE_225.resolve(world), goal)


class TestSealRequirement(unittest.TestCase):
    def test_each_mode_of_the_seal(self):
        self.assertTrue(SealRequirement().resolve(world_with()).always_true)
        passwords = world_with(area_m_access="passwords", required_passwords=4, total_passwords=6)
        self.assertEqual(str(SealRequirement().resolve(passwords)), "Seal of Area M: Has 4x Password")
        biometals = SealRequirement().resolve(world_with(area_m_access="biometals"))
        self.assertTrue(str(biometals).startswith("Seal of Area M: Has all of (Obtained: Biometal F, "))
        way_in = R.ENTRANCES["z01 transerver to m03"].rule
        self.assertIn(SealRequirement().resolve(passwords), way_in.resolve(passwords).children)
        self.assertNotIn("Seal", str(way_in.resolve(world_with())))


class TestDoorKey(MMZXTestBase):
    options = {"door_constraints_min": 10, "door_constraints_max": 10}

    def test_a_site_door_follows_the_keys_drawn_after_the_regions(self):
        world = self.world
        door, key = next(iter(world.door_keys.items()))
        entrance = self.multiworld.get_entrance(door, self.player)
        self.assertTrue(entrance.access_rule.force_recalculate)
        state = pool_without(self.multiworld, key)
        self.assertFalse(entrance.access_rule(state))
        self.assertEqual(DoorKey(door).resolve(world).explain_str(state), "Door locked: Missing " + key)
        other = next(k for k in ("Red Card Key", "Blue Card Key") if k != key)
        world.door_keys[door] = other
        try:
            self.assertTrue(entrance.access_rule(state))     # the same rule object reads the new key
        finally:
            world.door_keys[door] = key
        self.assertFalse(entrance.access_rule(state))
        state.collect(world.create_item(key), prevent_sweep=True)
        self.assertTrue(entrance.access_rule(state))

    def test_an_unlocked_site_door_is_open(self):
        world = self.world
        door = next(d for d in WORLD["site_doors"] if d not in world.door_keys)
        resolved = DoorKey(door).resolve(world)
        state = CollectionState(self.multiworld)
        self.assertTrue(resolved(state))
        self.assertEqual(resolved.explain_str(state), "Door not locked in this seed")
        self.assertEqual(set(resolved.item_dependencies()), {"Red Card Key", "Blue Card Key", "Purple Card Key",
                                                             "Yellow Card Key", "Green Card Key"})

    def test_the_tracker_rebuilds_the_same_doors_into_the_same_rules(self):
        slot_data = self.world.fill_slot_data()
        again = setup_multiworld(MMZXWorld, steps=(), seed=4321)
        again.re_gen_passthrough = {MMZXWorld.game: MMZXWorld.interpret_slot_data(slot_data)}
        from worlds.AutoWorld import call_all
        for step in ("generate_early", "create_regions", "create_items"):
            call_all(again, step)
        for door, key in self.world.door_keys.items():
            with self.subTest(door=door):
                self.assertFalse(again.get_entrance(door, 1).access_rule(pool_without(again, key)))


class TestSkipBossRush(unittest.TestCase):
    def test_the_teleporters_resolve_to_never_with_the_rush_skipped(self):
        self.assertTrue(R.ENTRANCES[RUSH_DOOR].rule.resolve(world_with(skip_boss_rush=True)).always_false)
        self.assertFalse(R.ENTRANCES[RUSH_DOOR].rule.resolve(world_with()).always_false)
        exit_cost = R.ENTRANCES[F.BOSS_RUSH_EXIT].rule
        self.assertTrue(exit_cost.resolve(world_with(skip_boss_rush=True, boss_logic={"Hivolt": WITNESS})).always_true)
        self.assertFalse(exit_cost.resolve(world_with(boss_logic={"Hivolt": WITNESS})).always_true)


class TestLavaCarriedTo(MMZXTestBase):
    def test_the_rule_explains_its_walk(self):
        entrance = self.multiworld.get_entrance(LAVA_EDGE, self.player)
        state = pool_without(self.multiworld)
        self.assertTrue(entrance.access_rule(state))
        self.assertIn("Slow lava carried from its control to k04/lava-chase", entrance.access_rule.explain_str(state))
        self.assertIn("Slow lava not carried", entrance.access_rule.explain_str(CollectionState(self.multiworld)))
        self.assertEqual(str(LavaCarriedTo("a", "b")), "LavaCarriedTo(a, b)")
