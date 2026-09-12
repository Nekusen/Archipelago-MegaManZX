"""Locations of the Mega Man ZX world."""

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


def locations_for_options(include_quests: bool, include_level4: bool,
                          include_undetectable: bool = False,
                          pickups: dict[str, bool] | None = None) -> dict[str, dict]:
    """Subset of LOCATIONS enabled by the options.

    Locations without a detection (detect None) are left out unless
    `include_undetectable` is set, so no check can stay unsent. `pickups` maps
    each pickup category to whether its option is on (pickup_flags_from_options);
    without it no respawnable pickup is included.
    """
    pickups = pickups or {}
    out = {}
    for name, v in LOCATIONS.items():
        cat = v["category"]
        if cat == "quest" and not include_quests:
            continue
        if cat == "level4" and not include_level4:
            continue
        if cat in PICKUP_OPTION_BY_CATEGORY and not pickups.get(cat, False):
            continue
        if v.get("detect") is None and not include_undetectable:
            continue
        out[name] = v
    return out


LOCATION_GROUPS = {
    "Secret Disks": {n for n, v in LOCATIONS.items() if v["category"] == "disk"},
    "Life Ups": {n for n, v in LOCATIONS.items() if v["category"] == "life_up"},
    "Sub Tanks": {n for n, v in LOCATIONS.items() if v["category"] == "sub_tank"},
    "Missions": {n for n, v in LOCATIONS.items() if v["category"] == "mission"},
    "Quests": {n for n, v in LOCATIONS.items() if v["category"] == "quest"},
    "Pickups": {n for n, v in LOCATIONS.items() if v["category"] in PICKUP_OPTION_BY_CATEGORY},
    "1-Ups": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_1up"},
    "Energy Capsules": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_energy"},
    "Weapon Energy": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_weapon"},
    "E-Crystals": {n for n, v in LOCATIONS.items() if v["category"] == "pickup_crystal"},
}
