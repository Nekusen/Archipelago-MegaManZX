"""Regiones del mundo Mega Man ZX.

v0.1 = NO-LOGIC: una sola región con todas las locations activas
directamente accesibles desde el origen. La lógica de habilidades
(HX altura, LX agua, FX bloques, PX techos, Card Keys) llega en v0.2+.
"""

from BaseClasses import Region

from .locations import MMZXLocation, locations_for_options


def create_regions(world) -> None:
    menu = Region("Menu", world.player, world.multiworld)
    overworld = Region("Mega Man ZX", world.player, world.multiworld)
    world.multiworld.regions += [menu, overworld]
    menu.connect(overworld)

    active = locations_for_options(
        include_quests=bool(world.options.submission_checks.value),
        include_level4=bool(world.options.level4_victories.value),
    )
    for name, v in active.items():
        loc = MMZXLocation(world.player, name, v["id"], overworld)
        overworld.locations.append(loc)

    # location-evento del objetivo (Serpent) en la región
    victory = MMZXLocation(world.player, "Defeat Serpent", None, overworld)
    victory.place_locked_item(world.create_event("Victory"))
    overworld.locations.append(victory)
