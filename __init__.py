"""Mega Man ZX (Nintendo DS) — mundo de Archipelago. v0.1 no-logic.

RE completo en docs/client_integration.md; puente en worlds/mmzx/data.py.
"""

from typing import ClassVar

from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from .data import LOCATIONS, ITEMS
from .items import MMZXItem, item_name_to_id, get_classification, ITEM_GROUPS
from .locations import location_name_to_id, locations_for_options, LOCATION_GROUPS
from .options import MMZXOptions
from .regions import create_regions
from . import client  # registra el BizHawkClient  # noqa: F401


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

        # progresión + useful fijos; el resto se rellena con filler
        pool: list[MMZXItem] = []
        fixed = [n for n, v in ITEMS.items() if v["classification"] != "filler"]
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

    def fill_slot_data(self) -> dict:
        return {
            "character": self.options.character.value,
            "goal": self.options.goal.value,
            "death_link": bool(self.options.death_link.value),
            "level4_victories": bool(self.options.level4_victories.value),
            "submission_checks": bool(self.options.submission_checks.value),
            "version": "0.1.0",
        }
