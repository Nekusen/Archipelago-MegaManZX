from BaseClasses import Item, ItemClassification

from .data import ITEMS

CLASSIFICATION = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
}


# Grant kinds of the mission_objectives items: story objects, what an event opens, what one does to its area
STORY_GRANTS = ("story", "story_gate", "story_area")


class MMZXItem(Item):
    game = "Mega Man ZX"


def item_name_to_id() -> dict[str, int]:
    return {name: v["id"] for name, v in ITEMS.items()}


def get_classification(name: str) -> ItemClassification:
    return CLASSIFICATION[ITEMS[name]["classification"]]


ONE_UP_GRANT = "oneup"
# Mostly small change: plenty of big fillers would make every price in the game trivial
FILLER_WEIGHTS = {"25 E-Crystals": 3, "50 E-Crystals": 2, "100 E-Crystals": 1,
                  "Energy Refill": 3, "Weapon Energy Refill": 2, "1-Up": 1}


def filler_weights(options) -> dict[str, int]:
    """The fillers a seed hands out and their weights; with infinite lives there are no 1-Ups."""
    return {n: w for n, w in FILLER_WEIGHTS.items()
            if not (options.infinite_lives and ITEMS[n]["grant"][0] == ONE_UP_GRANT)}


# Groups for hints/plando
ITEM_GROUPS = {
    "Biometals": {n for n in ITEMS if "Model " in n},
    "Card Keys": {n for n in ITEMS if n.endswith("Card Key")},
    "Chips": {n for n, v in ITEMS.items() if n.endswith(" Chip") and v["grant"][0] not in STORY_GRANTS},
    "Usable Items": {n for n, v in ITEMS.items() if v["grant"][0] == "usable"},
    "Mission Objectives": {n for n, v in ITEMS.items() if v["grant"][0] in STORY_GRANTS},
    "E-Crystals": {n for n, v in ITEMS.items() if v["grant"][0] == "ecrystals"},
    "Filler": {n for n, v in ITEMS.items() if v["classification"] == "filler"},
}
