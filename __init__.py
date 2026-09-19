"""Mega Man ZX (Nintendo DS) for Archipelago."""

import os
from typing import ClassVar

import settings
from BaseClasses import ItemClassification, Tutorial
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from . import goal as G
from .logic import bosses
from .data import LOCATIONS, ITEMS, STARTING_MODEL_ITEM, STARTING_MODELS
from .items import MMZXItem, item_name_to_id, get_classification, ITEM_GROUPS
from .locations import (location_name_to_id, locations_for_options, LOCATION_GROUPS,
                        pickup_flags_from_options)
from .options import MMZXOptions, OPTION_GROUPS
from .logic import load_document
from .logic.document import room_label
from .logic.rules import TIER, starting_point
from .regions import boss_requirements, create_regions, progression_overrides
from .rom import MMZXPatch, write_patch_tokens, MMZX_US_MD5
from .rom.golden import build_image
from . import client  # registers the BizHawkClient  # noqa: F401
from . import tracker  # auto-tab / position icon for Universal Tracker


class MMZXSettings(settings.Group):
    class RomFile(settings.UserFilePath):
        """Path to the Mega Man ZX (USA) ROM."""
        description = "Mega Man ZX (USA) ROM File"
        copy_to = "mmzx_us.nds"
        md5s = [MMZX_US_MD5]

    rom_file: RomFile = RomFile(RomFile.copy_to)

    class UTPackPath(settings.FilePath):
        """Path to the Mega Man ZX tracker pack (mmzx_tracker.zip): Universal
        Tracker loads the map images from it. Leave it empty and UT will ask
        for the file the first time it needs it."""
        description = "Mega Man ZX Tracker Pack (zip)"
        required = False
        ut_dialog_name = "Select the Mega Man ZX tracker pack (mmzx_tracker.zip)"

    ut_pack_path: UTPackPath | str = UTPackPath()


class MMZXWebWorld(WebWorld):
    theme = "ice"
    option_groups = OPTION_GROUPS
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up and playing Mega Man ZX with Archipelago.",
        "English", "setup_en.md", "setup/en", ["Nekusen"],
    )]


class MMZXWorld(World):
    """Mega Man ZX is a 2006 Nintendo DS action platformer by Inti Creates and
    Capcom. Explore the interconnected areas, collect biometals, Card Keys and
    upgrades, complete missions and defeat Serpent."""

    game = "Mega Man ZX"
    web = MMZXWebWorld()
    topology_present = True

    settings_key = "mmzx_settings"
    settings: ClassVar[MMZXSettings]  # type: ignore

    options_dataclass = MMZXOptions
    options: MMZXOptions  # type: ignore

    item_name_to_id = item_name_to_id()
    location_name_to_id = location_name_to_id()
    item_name_groups = ITEM_GROUPS
    location_name_groups = LOCATION_GROUPS

    origin_region_name = "Menu"

    # resolved in generate_early; the defaults serve a world used without it
    goal = G.GoalRequirement((), 0, 0, 0)
    disk_order: list[int] = list(range(G.DISK_ENTRIES))

    # Universal Tracker runs in hybrid mode: the map layout ships here in tracker/, while the
    # images come from the external pack the player points ut_pack_path at, so no game graphics
    # enter the repository. UT evaluates this very world for the logic and ignores the attribute
    # when it is not installed. The client publishes mmzx_pos_<slot> for the position icon.
    tracker_world = {
        "map_page_folder": "tracker",
        "external_pack_key": "ut_pack_path",
        "map_page_maps": "maps.json",
        "map_page_locations": "locations.json",
        "map_page_setting_key": "mmzx_pos_{player}",
        "map_page_index": tracker.map_page_index,
        "location_setting_key": "mmzx_pos_{player}",
        "location_icon_coords": tracker.location_icon_coords,
    }

    def generate_early(self) -> None:
        """Checks the option combinations and parses boss_logic first, so a YAML mistake fails
        with a clear message."""
        # with no starting biometal Hu is the only form, so it cannot be an item; ignored
        # rather than rejected, so a random starting_model may land on none
        if self.options.starting_model.current_key == "none":
            self.options.hu_in_pool.value = 0
        active = locations_for_options(pickups=pickup_flags_from_options(self.options))
        room = len(active) - len(self.fixed_items()[0])
        reserve = len(set(self.options.exclude_locations.value) & set(active))
        self.goal = G.resolve(self.options, room, reserve, self.player_name)
        # the order the disks received light the database entries in
        self.disk_order = self.random.sample(range(G.DISK_ENTRIES), G.DISK_ENTRIES)
        try:
            reqs = boss_requirements(self)
        except ValueError as e:
            raise OptionError("[%s] boss_logic: %s" % (self.player_name, e)) from None
        loose = bosses.unanchored(load_document(), reqs)
        if loose:
            # failing beats applying the requirement to nothing
            raise OptionError(
                "[%s] boss_logic: %s has no arena anchored in the logic yet, so the "
                "requirement would apply to nothing. Remove it from the YAML or draw the "
                "arena in tools/logic_editor/." % (self.player_name, ", ".join(loose)))

    def create_regions(self) -> None:
        create_regions(self)

    def create_item(self, name: str) -> MMZXItem:
        """Creates an item, promoting a useful one to progression when a rule needs it."""
        cls = get_classification(name)
        # the AP state only counts progression items
        if name in progression_overrides(self):
            cls = ItemClassification.progression
        elif name == G.DISK_ITEM:
            # goal items: any copy counts, so balancing leaves them alone; a big hunt keeps
            # them off priority locations
            cls = ItemClassification.progression_skip_balancing
            if self.goal.disks_total > G.FEW_DISKS:
                cls |= ItemClassification.deprioritized
        return MMZXItem(name, cls, self.item_name_to_id[name], self.player)

    def create_event(self, name: str) -> MMZXItem:
        return MMZXItem(name, ItemClassification.progression, None, self.player)

    def get_filler_item_name(self) -> str:
        """E-Crystals, the only filler."""
        return "E-Crystals"

    def fixed_items(self) -> tuple[list[str], list[str]]:
        """(pool items, pre-granted items) before the goal items and the filler.

        Every pooled non-filler item, count copies each; the starting model and the
        starting floor's Transerver Access are pre-granted instead. 'none' leaves
        Model X findable, and without hu_in_pool Hu is not an item.
        """
        progressive = bool(self.options.progressive_models.value)
        fixed: list[str] = []
        for n, v in ITEMS.items():
            if v["classification"] != "filler" and v.get("pooled", True):
                if not progressive and n in G.FULL_MODEL_OF:
                    fixed.append(G.FULL_MODEL_OF[n])   # one full item instead of two halves
                else:
                    fixed += [n] * int(v.get("count", 1))
        if self.options.hu_in_pool.value:
            fixed.append("Model Hu")
        granted: list[str] = []
        start_item = STARTING_MODEL_ITEM.get(self.options.starting_model.current_key)
        start_item = G.model_item(start_item, progressive) if start_item else None
        if start_item and start_item in fixed:
            fixed.remove(start_item)   # one copy: the first half of a progressive item
            granted.append(start_item)
        start_ts = starting_point(self).get("access")
        if start_ts in fixed:
            fixed.remove(start_ts)
            granted.append(start_ts)
        return fixed, granted

    def create_items(self) -> None:
        """Fills the pool: the fixed items, the Secret Disks of the goal, then filler."""
        active_locs = locations_for_options(pickups=pickup_flags_from_options(self.options))
        n_locations = len(active_locs)  # not counting the Victory event

        fixed, granted = self.fixed_items()
        for name in granted:
            self.multiworld.push_precollected(self.create_item(name))
        pool: list[MMZXItem] = [self.create_item(name) for name in fixed]
        pool += [self.create_item(G.DISK_ITEM) for _ in range(self.goal.disks_total)]

        remaining = n_locations - len(pool)
        if remaining < 0:
            raise OptionError("[%s] %d fixed items for %d locations: turn on a pickup_checks_* "
                              "option or drop an item" % (self.player_name, len(pool), n_locations))
        for _ in range(remaining):
            pool.append(self.create_item(self.get_filler_item_name()))

        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        """Only the completion condition; the access rules live on the entrances."""
        self.multiworld.completion_condition[self.player] = \
            lambda state: state.has("Victory", self.player)

    def pre_fill(self) -> None:
        """Fails early when boss_logic makes the goal unreachable even with the whole pool."""
        reqs = boss_requirements(self)
        if not reqs:
            return
        state = self.multiworld.get_all_state()
        if self.multiworld.completion_condition[self.player](state):
            return
        rules = bosses.compile_rules(reqs, TIER, self.player, bool(self.options.hu_in_pool.value),
                                     not self.options.progressive_models.value)
        from .logic import document as F
        blocked = [F.BOSSES[b]["name"] for b in sorted(reqs)
                   if not rules.get(F.boss_atom(b), lambda s: True)(state)]
        raise OptionError(
            "[%s] boss_logic: the seed cannot be completed even with every item. "
            "Bosses whose requirement is still unmet: %s. Check that you do not ask for more "
            "Life Ups / Sub Tanks than exist (4 of each) or for an item outside the pool."
            % (self.player_name, ", ".join(blocked) or "none (check the rest of the logic)"))

    def generate_output(self, output_directory: str) -> None:
        """Writes the .apmmzx patch of this player, with the starting save built from the options."""
        patch = MMZXPatch(player=self.player, player_name=self.player_name)
        image = build_image(self.options.starting_model.current_key, self.options.character.value,
                            STARTING_MODELS, starting_point(self),
                            full_models=not self.options.progressive_models.value)
        write_patch_tokens(patch, self.player_name, self.multiworld.seed_name, self.world_version,
                           image, hu_in_pool=bool(self.options.hu_in_pool.value))
        out_name = self.multiworld.get_out_file_name_base(self.player)
        patch.write(os.path.join(output_directory, out_name + patch.patch_file_ending))

    def write_spoiler_header(self, spoiler_handle) -> None:
        """The start point and the boss requirements as the generator understood them."""
        start = starting_point(self)
        pre = [name for name in (STARTING_MODEL_ITEM.get(self.options.starting_model.current_key),
                                 start.get("access")) if name]
        spoiler_handle.write("Start: %s (%s), pre-granted: %s\n" % (
            self.options.starting_transerver.current_key, room_label(start["room"]),
            ", ".join(pre) or "nothing"))
        spoiler_handle.write("Goal: %s; requirements: %s\n" % (
            self.options.goal.current_key, G.describe(self.goal)))
        reqs = bosses.describe(boss_requirements(self))
        spoiler_handle.write("Boss logic: %s\n" % (
            "; ".join("%s: %s" % kv for kv in reqs.items()) if reqs else "none"))

    def fill_slot_data(self) -> dict:
        """Options the client needs, plus the boss requirements as text."""
        return {
            "character": self.options.character.value,
            "goal": self.options.goal.value,
            # the client opens the gate to the final area on these, and lights the
            # database entries of the disks received in this order
            "goal_requirements": G.slot_data(self.goal, self.disk_order),
            "death_link": bool(self.options.death_link.value),
            "starting_model": self.options.starting_model.current_key,
            "starting_transerver": self.options.starting_transerver.current_key,
            "progressive_models": bool(self.options.progressive_models.value),
            "hu_in_pool": bool(self.options.hu_in_pool.value),
            "boss_logic": bosses.describe(boss_requirements(self)),
            # the client marks the rush pairs as beaten; the logic stops requiring them
            "skip_boss_rush": bool(self.options.skip_boss_rush.value),
            # the client polls the pickup mailbox only if a category is on
            "pickup_checks_1up": bool(self.options.pickup_checks_1up.value),
            "pickup_checks_energy": bool(self.options.pickup_checks_energy.value),
            "pickup_checks_weapon": bool(self.options.pickup_checks_weapon.value),
            "pickup_checks_crystals": bool(self.options.pickup_checks_crystals.value),
            # notice thresholds, applied on connect unless /mmzx_notify was used
            "notify_received": self.options.notify_received.current_key,
            "notify_sent": self.options.notify_sent.current_key,
            "notify_style": self.options.notify_style.current_key,
            "version": ".".join(str(n) for n in self.world_version),
        }
