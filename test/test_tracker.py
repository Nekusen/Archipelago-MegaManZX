"""Universal Tracker rebuilds the world from the slot data: its logic is the seed's, whatever its YAML says."""
import json
import unittest

from BaseClasses import CollectionState
from Options import PerGameCommonOptions
from test.general import setup_multiworld
from worlds.AutoWorld import World, call_all

from .bases import WITNESS
from .. import MMZXWorld, SLOT_DATA_OPTIONS
from ..goal import MODEL_ITEM_BY_KEY, SIX_MODEL_KEYS
from ..logic import bosses
from ..options import MMZXOptions
from ..regions import boss_requirements

# the stages Universal Tracker runs, of those this Archipelago has
TRACKER_STEPS = tuple(step for step in ("generate_early", "create_regions", "create_items", "set_rules",
                                        "connect_entrances", "generate_basic") if hasattr(World, step))
ALL_PICKUPS = {"pickup_checks_1up": True, "pickup_checks_energy": True,
               "pickup_checks_weapon": True, "pickup_checks_crystals": True}
# an option set with nothing left at its default
CHANGED = {"character": "aile", "starting_model": "model_hx", "starting_transerver": "guardian_base",
           "progressive_models": False, "hu_in_pool": True, "skip_boss_rush": True,
           "skip_minibosses": "always", **ALL_PICKUPS, "death_link": True,
           "notify_received": "all", "notify_sent": "off", "notify_style": "short",
           "boss_logic": {"Hivolt": "HX & Life Up x2", "Serpent": "ALL6 | " + WITNESS},
           "goal_requirements": ["Secret Disks", "Missions"], "required_secret_disks": 10,
           "total_secret_disks": 15, "required_missions": 5,
           "mission_objectives": "items", "area_m_access": "passwords", "required_passwords": 3,
           "total_passwords": 5, "door_constraints_min": 6, "door_constraints_max": 9}
# seed options -> the YAML the tracker reads
CASES = {
    "random start rolled none": ({"starting_model": "model_ox", "hu_in_pool": True, **ALL_PICKUPS},
                                 {"starting_model": "none", "hu_in_pool": True, **ALL_PICKUPS}),
    "changed seed, default yaml": (CHANGED, {}),
    "default seed, changed yaml": ({}, CHANGED),
    "full models, biometals goal": ({"progressive_models": False, "required_models_count": 3},
                                    {"progressive_models": True, "require_full_models": True}),
    "objectives as checks, biometals seal": ({"mission_objectives": "checks", "area_m_access": "biometals"},
                                             {"mission_objectives": "items", "area_m_access": "passwords",
                                              "door_constraints_min": 4, "door_constraints_max": 4}),
}
# options the slot data sends resolved, as the goal of the seed
GOAL_OPTIONS = {"goal_requirements", "required_models", "required_models_count", "require_full_models",
                "required_secret_disks", "total_secret_disks", "required_missions"}
# options the slot data sends resolved too: the seal of Area M and the doors a seed locked
SEAL_OPTIONS = {"area_m_access", "required_passwords", "total_passwords"}
DOOR_OPTIONS = {"door_constraints_min", "door_constraints_max"}
# options that change nothing a rebuilt world shows
UNSENT_OPTIONS = {"start_inventory_from_pool"}
# boss_logic travels as the text of each requirement
BOSS_LOGIC = {"Hivolt": "Model HX (full) & Life Up x2", "Lurerre": "any model & Sub Tank x1",
              "Fistleo": "(FX | LX) & " + WITNESS, "Flammole": "Yellow Card Key | HX2 & PX",
              "Serpent": "all biometals & LIFEUP>=4", "Omega Zero": "OX | (ALL6 & SUBTANK>=2)"}


def as_sent(slot_data: dict) -> dict:
    """The slot data as a client receives it."""
    return json.loads(json.dumps(slot_data))


def tracker_multiworld(slot_data: dict, yaml_options: dict):
    """The world as Universal Tracker rebuilds it: its own YAML plus the slot data of the seed."""
    multiworld = setup_multiworld(MMZXWorld, steps=(), options=yaml_options)
    multiworld.generation_is_fake = True
    multiworld.re_gen_passthrough = {MMZXWorld.game: MMZXWorld.interpret_slot_data(as_sent(slot_data))}
    for step in TRACKER_STEPS:
        call_all(multiworld, step)
    return multiworld


def in_logic(multiworld, item_names) -> set:
    """Locations and events a state holding these items reaches; the tracker's inventory is the server's."""
    world = multiworld.worlds[1]
    state = CollectionState(multiworld)
    for item in list(state.prog_items[1].elements()):   # the inventory replaces the precollected items
        state.prog_items[1][item] = 0
    for name in item_names:
        state.collect(world.create_item(name), prevent_sweep=True)
    state.sweep_for_advancements()
    return {loc.name for loc in multiworld.get_locations(1) if loc.can_reach(state)}


def inventories(seed):
    """Named inventories of the seed: the start, the whole pool and the pool without each item."""
    start = [item.name for item in seed.precollected_items[1]]
    pool = start + [item.name for item in seed.itempool]
    yield "start", start
    yield "everything", pool
    for missing in sorted(set(pool)):
        yield "without " + missing, [name for name in pool if name != missing]


class TestTrackerRegeneration(unittest.TestCase):
    def test_logic_is_the_seeds(self) -> None:
        for case, (seed_options, yaml_options) in CASES.items():
            seed = setup_multiworld(MMZXWorld, options=seed_options)
            tracker = tracker_multiworld(seed.worlds[1].fill_slot_data(), yaml_options)
            with self.subTest(case=case):
                self.assertEqual({loc.name for loc in tracker.get_locations(1)},
                                 {loc.name for loc in seed.get_locations(1)})
            for label, items in inventories(seed):
                with self.subTest(case=case, inventory=label):
                    self.assertEqual(in_logic(tracker, items), in_logic(seed, items))

    def test_slot_data_comes_back_the_same(self) -> None:
        """A rebuilt world would send the slot data it was rebuilt from."""
        for case, (seed_options, yaml_options) in CASES.items():
            with self.subTest(case=case):
                slot_data = setup_multiworld(MMZXWorld, options=seed_options).worlds[1].fill_slot_data()
                tracker = tracker_multiworld(slot_data, yaml_options).worlds[1]
                self.assertEqual(as_sent(tracker.fill_slot_data()), as_sent(slot_data))

    def test_options_come_from_the_slot_data(self) -> None:
        seed = setup_multiworld(MMZXWorld, options=CHANGED).worlds[1]
        tracker = tracker_multiworld(seed.fill_slot_data(), {}).worlds[1]
        for key in SLOT_DATA_OPTIONS:
            if key != "boss_logic":   # carried as text, compared below as requirements
                with self.subTest(option=key):
                    self.assertEqual(getattr(tracker.options, key).value, getattr(seed.options, key).value)
        self.assertEqual(boss_requirements(tracker), boss_requirements(seed))
        self.assertEqual(vars(tracker.goal), vars(seed.goal))
        self.assertEqual(vars(tracker.seal), vars(seed.seal))
        self.assertEqual(tracker.options.area_m_access.value, seed.options.area_m_access.value)
        self.assertTrue(seed.door_sites)
        self.assertEqual(tracker.door_sites, seed.door_sites)

    def test_slot_data_carries_every_restored_option(self) -> None:
        slot_data = setup_multiworld(MMZXWorld).worlds[1].fill_slot_data()
        for key in SLOT_DATA_OPTIONS:
            self.assertIn(key, slot_data)

    def test_every_option_is_accounted_for(self) -> None:
        """A new option has to say how a rebuilt world learns its value."""
        own = set(MMZXOptions.type_hints) - set(PerGameCommonOptions.type_hints)
        self.assertEqual(own, set(SLOT_DATA_OPTIONS) | GOAL_OPTIONS | SEAL_OPTIONS | DOOR_OPTIONS | UNSENT_OPTIONS)

    def test_the_yaml_is_not_needed(self) -> None:
        """Universal Tracker builds this world from an empty YAML, which a default one stands for."""
        self.assertTrue(MMZXWorld.ut_can_gen_without_yaml)
        self.assertIsInstance(MMZXWorld.__dict__["interpret_slot_data"], staticmethod)

    def test_slot_data_of_another_game_is_ignored(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, steps=(), options={"starting_model": "model_ox"})
        multiworld.re_gen_passthrough = {"Another Game": {"starting_model": "none"}}
        call_all(multiworld, "generate_early")
        self.assertEqual(multiworld.worlds[1].options.starting_model.current_key, "model_ox")

    def test_boss_logic_reads_back_from_its_text(self) -> None:
        reqs = bosses.parse_boss_logic(BOSS_LOGIC)
        self.assertEqual(len(reqs), len(BOSS_LOGIC))
        self.assertEqual(bosses.parse_boss_logic(as_sent(bosses.describe(reqs))), reqs)

    def test_an_invalid_yaml_does_not_stop_the_tracker(self) -> None:
        """The goal comes resolved in the slot data, so the YAML's goal options are never checked."""
        seed = setup_multiworld(MMZXWorld).worlds[1]
        tracker = tracker_multiworld(seed.fill_slot_data(), {"goal_requirements": []}).worlds[1]
        self.assertEqual(vars(tracker.goal), vars(seed.goal))

    def test_a_seed_from_before_an_option_plays_as_its_default(self) -> None:
        """Slot data that says nothing about an option means its default, not what the YAML rolls."""
        slot_data = setup_multiworld(MMZXWorld).worlds[1].fill_slot_data()
        for key in ("progressive_models", "goal_requirements", "skip_minibosses", "mission_objectives",
                    "area_m_access", "door_constraints"):
            del slot_data[key]
        yaml_options = {"progressive_models": False, "goal_requirements": ["Missions"], "required_missions": 3,
                        "skip_minibosses": "always", "mission_objectives": "items", "area_m_access": "passwords",
                        "door_constraints_min": 5, "door_constraints_max": 5}
        tracker = tracker_multiworld(slot_data, yaml_options).worlds[1]
        self.assertTrue(tracker.options.progressive_models.value)
        self.assertEqual(tracker.options.skip_minibosses.current_key, "off")
        self.assertEqual(tracker.options.mission_objectives.current_key, "off")
        self.assertEqual((tracker.seal.mode, tracker.options.area_m_access.current_key), ("open", "open"))
        self.assertEqual(tracker.door_sites, {})
        self.assertEqual(tracker.goal.models, tuple(MODEL_ITEM_BY_KEY[key] for key in SIX_MODEL_KEYS))
        self.assertEqual((tracker.goal.models_count, tracker.goal.missions_required), (6, 0))

    def test_a_real_generation_ignores_the_hook(self) -> None:
        """Without the tracker's passthrough the options are the YAML's."""
        world = setup_multiworld(MMZXWorld, options={"starting_model": "model_ox"}).worlds[1]
        self.assertEqual(world.options.starting_model.current_key, "model_ox")
