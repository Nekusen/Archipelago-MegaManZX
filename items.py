from BaseClasses import Item, ItemClassification

from .data import ITEMS

CLASSIFICATION = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
}


# Grant kinds of the mission_objectives items: the story objects and what the story events open
STORY_GRANTS = ("story", "story_gate")


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
    "Chips": {n for n, v in ITEMS.items() if n.endswith(" Chip") and v["grant"][0] not in STORY_GRANTS},
    "Usable Items": {n for n, v in ITEMS.items() if v["grant"][0] == "usable"},
    "Mission Objectives": {n for n, v in ITEMS.items() if v["grant"][0] in STORY_GRANTS},
    "Filler": {n for n, v in ITEMS.items() if v["classification"] == "filler"},
}
