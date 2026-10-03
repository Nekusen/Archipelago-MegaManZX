from BaseClasses import Location

from .data import LOCATIONS


class MMZXLocation(Location):
    game = "Mega Man ZX"


def location_name_to_id() -> dict[str, int]:
    return {name: v["id"] for name, v in LOCATIONS.items()}


# Respawnable pickup category to the option that enables it; all off by default.
PICKUP_OPTION_BY_CATEGORY = {
    "pickup_1up": "pickup_checks_1up",
    "pickup_energy": "pickup_checks_energy",
    "pickup_weapon": "pickup_checks_weapon",
    "pickup_crystal": "pickup_checks_crystals",
}


def pickup_flags_from_options(options) -> dict[str, bool]:
    """{pickup category: enabled} read from the options dataclass."""
    return {cat: bool(getattr(options, opt).value)
            for cat, opt in PICKUP_OPTION_BY_CATEGORY.items()}


# Categories whose detection is not validated in game yet: they stay out of every seed.
DEFERRED_CATEGORIES = ("quest", "level4")

# mission_objectives: the story objects and events are locations in both modes; the events
# that open a gate only when an item opens it instead.
STORY_OFF, STORY_CHECKS, STORY_ITEMS = "off", "checks", "items"
STORY_CATEGORY = "story"
STORY_GATE = "gate"


def story_mode(options) -> str:
    """The mission_objectives option as a key: off, checks or items."""
    return options.mission_objectives.current_key


def locations_for_options(include_undetectable: bool = False,
                          pickups: dict[str, bool] | None = None,
                          story: str = STORY_OFF) -> dict[str, dict]:
    """Subset of LOCATIONS enabled by the options.

    Locations without a detection (detect None) are left out unless
    `include_undetectable` is set, so no check can stay unsent. `pickups` maps
    each pickup category to whether its option is on (pickup_flags_from_options);
    without it no respawnable pickup is included. `story` is the mission_objectives mode.
    """
    pickups = pickups or {}
    out = {}
    for name, v in LOCATIONS.items():
        cat = v["category"]
        if cat in DEFERRED_CATEGORIES:
            continue
        if cat in PICKUP_OPTION_BY_CATEGORY and not pickups.get(cat, False):
            continue
        if cat == STORY_CATEGORY and (story == STORY_OFF
                                      or (v["story"] == STORY_GATE and story != STORY_ITEMS)):
            continue
        if v.get("detect") is None and not include_undetectable:
            continue
        out[name] = v
    return out


def active_locations(options) -> dict[str, dict]:
    """The locations of a world with these options."""
    return locations_for_options(pickups=pickup_flags_from_options(options), story=story_mode(options))


LOCATION_GROUPS = {
    "Secret Disks": {n for n, v in LOCATIONS.items() if v["category"] == "disk"},
    "Life Ups": {n for n, v in LOCATIONS.items() if v["category"] == "life_up"},
    "Sub Tanks": {n for n, v in LOCATIONS.items() if v["category"] == "sub_tank"},
    "Missions": {n for n, v in LOCATIONS.items() if v["category"] == "mission"},
    "Usable Items": {n for n, v in LOCATIONS.items() if v["category"] == "usable"},
    "Mission Objectives": {n for n, v in LOCATIONS.items() if v["category"] == STORY_CATEGORY},
    "Pickups": {n for n, v in LOCATIONS.items() if v["category"] in PICKUP_OPTION_BY_CATEGORY},
    "1-Ups": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_1up"},
    "Energy Capsules": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_energy"},
    "Weapon Energy": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_weapon"},
    "E-Crystals": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_crystal"},
}
