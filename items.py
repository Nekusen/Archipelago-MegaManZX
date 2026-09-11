"""Items of the Mega Man ZX world."""

from BaseClasses import Item, ItemClassification

from .data import ITEMS

CLASSIFICATION = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
}


class MMZXItem(Item):
    game = "Mega Man ZX"


def item_name_to_id() -> dict[str, int]:
    return {name: v["id"] for name, v in ITEMS.items()}


def get_classification(name: str) -> ItemClassification:
    return CLASSIFICATION[ITEMS[name]["classification"]]


# Groups for hints/plando
ITEM_GROUPS = {
    "Biometals": {n for n in ITEMS if "Model " in n},
    "Card Keys": {n for n in ITEMS if n.endswith("Card Key")},
    "Chips": {n for n in ITEMS if n.endswith(" Chip")},
    "Filler": {n for n, v in ITEMS.items() if v["classification"] == "filler"},
}
