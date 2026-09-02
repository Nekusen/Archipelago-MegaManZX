"""Mega Man ZX (Nintendo DS) — mundo de Archipelago. v0.1 no-logic.

RE completo en docs/client_integration.md; puente en worlds/mmzx/data.py.
"""

import os
from typing import ClassVar

import settings
from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from .data import LOCATIONS, ITEMS, STARTING_MODEL_ITEM, START_TRANSERVER_AREA
from .items import MMZXItem, item_name_to_id, get_classification, ITEM_GROUPS
from .locations import location_name_to_id, locations_for_options, LOCATION_GROUPS
from .options import MMZXOptions
from .regions import create_regions
from .rom import MMZXPatch, write_patch_tokens, MMZX_US_MD5
from . import client  # registra el BizHawkClient  # noqa: F401


class MMZXSettings(settings.Group):
    class RomFile(settings.UserFilePath):
        """Ruta a la ROM de Mega Man ZX (USA)."""
        description = "Mega Man ZX (USA) ROM File"
        copy_to = "mmzx_us.nds"
        md5s = [MMZX_US_MD5]

    rom_file: RomFile = RomFile(RomFile.copy_to)


class MMZXWebWorld(WebWorld):
    theme = "ice"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "Guía para jugar Mega Man ZX con Archipelago.",
        "English", "setup_en.md", "setup/en", ["proyecto MMZX"],
    )]


class MMZXWorld(World):
    """Mega Man ZX: metroidvania de Inti Creates/Capcom para Nintendo DS."""

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

    def create_regions(self) -> None:
        create_regions(self)

    def create_item(self, name: str) -> MMZXItem:
        return MMZXItem(name, get_classification(name), self.item_name_to_id[name], self.player)

    def create_event(self, name: str) -> MMZXItem:
        return MMZXItem(name, ItemClassification.progression, None, self.player)

    def get_filler_item_name(self) -> str:
        return "E-Crystals"

    def create_items(self) -> None:
        active_locs = locations_for_options(
            include_quests=bool(self.options.submission_checks.value),
            include_level4=bool(self.options.level4_victories.value),
        )
        n_locations = len(active_locs)  # sin contar el evento Victory

        # progresión + useful fijos (solo los "pooled"); resto filler
        pool: list[MMZXItem] = []
        fixed = [n for n, v in ITEMS.items()
                 if v["classification"] != "filler" and v.get("pooled", True)]

        # Model Hu: solo entra al pool si hu_in_pool (el parche Hu-gate lo
        # convierte en item). Sin la opción, Hu es hardcoded (no es item).
        if self.options.hu_in_pool.value:
            fixed.append("Model Hu")

        # Modelo inicial (tutorial-skip): el item equivalente se pre-concede
        # (start inventory) y sale del pool. Con 'none' no se pre-concede
        # nada y Model X queda en el pool como item encontrable.
        start_key = self.options.starting_model.current_key
        if start_key == "model_hu" and not self.options.hu_in_pool.value:
            start_key = "none"   # Hu no gateada: 'model_hu' == 'none'
        start_item = STARTING_MODEL_ITEM.get(start_key)
        if start_item and start_item in fixed:
            fixed.remove(start_item)
            self.multiworld.push_precollected(self.create_item(start_item))

        # Red de Transervers (modelo híbrido): el acceso del área donde
        # arranca el skip (piso del hub = A-2) se pre-concede; el resto de
        # "Transerver Access - Area X" van a la pool como progresión.
        start_ts = "Transerver Access - Area %s" % START_TRANSERVER_AREA
        if start_ts in fixed:
            fixed.remove(start_ts)
            self.multiworld.push_precollected(self.create_item(start_ts))

        for name in fixed:
            pool.append(self.create_item(name))

        remaining = n_locations - len(pool)
        if remaining < 0:
            # más items fijos que locations: recorta filler-first (no debería
            # pasar en v0.1; los progresión siempre caben)
            pool = pool[:n_locations]
            remaining = 0
        for _ in range(remaining):
            pool.append(self.create_item(self.get_filler_item_name()))

        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        # no-logic: todo accesible. Solo la condición de victoria.
        self.multiworld.completion_condition[self.player] = \
            lambda state: state.has("Victory", self.player)

    def generate_output(self, output_directory: str) -> None:
        patch = MMZXPatch(player=self.player, player_name=self.player_name)
        write_patch_tokens(patch, self.player_name, self.multiworld.seed_name,
                           hu_in_pool=bool(self.options.hu_in_pool.value))
        out_name = self.multiworld.get_out_file_name_base(self.player)
        patch.write(os.path.join(output_directory, out_name + patch.patch_file_ending))

    def fill_slot_data(self) -> dict:
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
            "version": "0.1.0",
        }
