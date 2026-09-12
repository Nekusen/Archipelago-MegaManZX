"""Mega Man ZX (Nintendo DS) for Archipelago."""

import os
from typing import ClassVar

import settings
from BaseClasses import ItemClassification, Tutorial
from Options import OptionError
from worlds.AutoWorld import WebWorld, World

from .logic import bosses
from .data import LOCATIONS, ITEMS, STARTING_MODEL_ITEM, START_TRANSERVER_AREA
from .items import MMZXItem, item_name_to_id, get_classification, ITEM_GROUPS
from .locations import (location_name_to_id, locations_for_options, LOCATION_GROUPS,
                        pickup_flags_from_options)
from .options import MMZXOptions
from .logic import load_document
from .regions import boss_requirements, create_regions, progression_overrides
from .rom import MMZXPatch, write_patch_tokens, MMZX_US_MD5
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
        """Parses boss_logic first, so a YAML mistake fails with a clear message."""
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
        """Builds the regions and entrances from the logic document."""
        create_regions(self)

    def create_item(self, name: str) -> MMZXItem:
        """Creates an item, promoting a useful one to progression when a rule needs it."""
        cls = get_classification(name)
        # the AP state only counts progression items
        if name in progression_overrides(self):
            cls = ItemClassification.progression
        return MMZXItem(name, cls, self.item_name_to_id[name], self.player)

    def create_event(self, name: str) -> MMZXItem:
        """Progression event item with no id."""
        return MMZXItem(name, ItemClassification.progression, None, self.player)

    def get_filler_item_name(self) -> str:
        """E-Crystals, the only filler."""
        return "E-Crystals"

    def create_items(self) -> None:
        """Fills the pool: every fixed item minus the pre-granted start items, then filler."""
        active_locs = locations_for_options(
            include_quests=bool(self.options.submission_checks.value),
            include_level4=bool(self.options.level4_victories.value),
            pickups=pickup_flags_from_options(self.options),
        )
        n_locations = len(active_locs)  # not counting the Victory event

        # every pooled non-filler item, count copies each; progressive biometals are two
        pool: list[MMZXItem] = []
        fixed: list[str] = []
        for n, v in ITEMS.items():
            if v["classification"] != "filler" and v.get("pooled", True):
                fixed += [n] * int(v.get("count", 1))

        # without hu_in_pool the Hu-gate patch is off and Hu is not an item
        if self.options.hu_in_pool.value:
            fixed.append("Model Hu")

        # the starting model is pre-granted and leaves the pool; 'none' leaves Model X findable
        start_key = self.options.starting_model.current_key
        if start_key == "model_hu" and not self.options.hu_in_pool.value:
            start_key = "none"   # Hu not gated: 'model_hu' == 'none'
        start_item = STARTING_MODEL_ITEM.get(start_key)
        if start_item and start_item in fixed:
            fixed.remove(start_item)   # one copy: the first half of a progressive item
            self.multiworld.push_precollected(self.create_item(start_item))

        # the starting hub floor's Transerver Access is pre-granted; the rest go to the pool
        start_ts = "Transerver Access - Area %s" % START_TRANSERVER_AREA
        if start_ts in fixed:
            fixed.remove(start_ts)
            self.multiworld.push_precollected(self.create_item(start_ts))

        for name in fixed:
            pool.append(self.create_item(name))

        remaining = n_locations - len(pool)
        if remaining < 0:
            # more fixed items than locations; progression always fits
            pool = pool[:n_locations]
            remaining = 0
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
        rules = bosses.compile_rules(reqs, self.options.logic_difficulty.current_key,
                                     self.player, bool(self.options.hu_in_pool.value))
        from .logic import document as F
        blocked = [F.BOSSES[b]["name"] for b in sorted(reqs)
                   if not rules.get(F.boss_atom(b), lambda s: True)(state)]
        raise OptionError(
            "[%s] boss_logic: the seed cannot be completed even with EVERY item. "
            "Bosses whose requirement is still unmet: %s. Check that you do not ask for more "
            "Life Ups / Sub Tanks than exist (4 of each) or for an item outside the pool."
            % (self.player_name, ", ".join(blocked) or "none (check the rest of the logic)"))

    def generate_output(self, output_directory: str) -> None:
        """Writes the .apmmzx patch of this player."""
        patch = MMZXPatch(player=self.player, player_name=self.player_name)
        write_patch_tokens(patch, self.player_name, self.multiworld.seed_name, self.world_version,
                           hu_in_pool=bool(self.options.hu_in_pool.value))
        out_name = self.multiworld.get_out_file_name_base(self.player)
        patch.write(os.path.join(output_directory, out_name + patch.patch_file_ending))

    def fill_slot_data(self) -> dict:
        """Options the client needs, plus the boss requirements as text."""
        return {
            "character": self.options.character.value,
            "goal": self.options.goal.value,
            "death_link": bool(self.options.death_link.value),
            "level4_victories": bool(self.options.level4_victories.value),
            "submission_checks": bool(self.options.submission_checks.value),
            "mission_auto_accept": bool(self.options.mission_auto_accept.value),
            "starting_model": self.options.starting_model.current_key,
            "starting_transerver": self.options.starting_transerver.current_key,
            "hu_in_pool": bool(self.options.hu_in_pool.value),
            "logic_difficulty": self.options.logic_difficulty.current_key,
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
