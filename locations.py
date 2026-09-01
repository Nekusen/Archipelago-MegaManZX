"""Locations del mundo Mega Man ZX."""

from BaseClasses import Location

from .data import LOCATIONS


class MMZXLocation(Location):
    game = "Mega Man ZX"


def location_name_to_id() -> dict[str, int]:
    return {name: v["id"] for name, v in LOCATIONS.items()}


def locations_for_options(include_quests: bool, include_level4: bool,
                          include_undetectable: bool = False) -> dict[str, dict]:
    """Subconjunto de locations activo según opciones.

    Por defecto se EXCLUYEN las locations sin detección fiable
    (detect=None: 6 misiones + 21 quests cuya 'completada' aún no se
    mapeó) para no meter checks 'muertos' que nunca se envían. El seed de
    v0.1 queda con checks 100%% detectables. `include_undetectable` las
    fuerza (para pruebas)."""
    out = {}
    for name, v in LOCATIONS.items():
        if v["category"] == "quest" and not include_quests:
            continue
        if v["category"] == "level4" and not include_level4:
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
}
