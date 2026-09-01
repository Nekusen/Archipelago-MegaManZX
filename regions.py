"""Regiones del mundo Mega Man ZX.

v0.2 — primer cribado de LÓGICA (antes: v0.1 no-logic, una sola región).
Una región por sala; transiciones = aristas dirigidas del grafo estático
(data.DOORS + logic.EXTRA_EDGES) con las Card Keys como única regla.

Diseño preparado para randomizar transiciones en el futuro (patrón del
core de AP, docs "entrance randomization.md"): cada entrance tiene nombre
estable ligado a la puerta física (sala + posición), y cada dirección es
una arista independiente. Para activar ER bastará con
disconnect_entrance_for_randomization + randomize_entrances en
connect_entrances sobre el subconjunto kind=='door'.

Las misiones/quests/biometales no viven en una sala concreta (su etiqueta
de área es difusa: 'B-1B-2', 'E-7/I-3', 'F'): van a la región holder
"Field" con regla can_reach_region sobre las salas de su etiqueta
(logic.label_rule). Las locations físicas (disks, Life Ups, Sub Tanks)
van a la región de su sala.
"""

from BaseClasses import Region

from .data import LOCATIONS
from .locations import MMZXLocation, locations_for_options
from .logic import (ALL_EDGES, NON_TRANSITION_KINDS, ROOM_NAMES, door_rule,
                    internal_gate_rule, label_rule, starting_room)


def create_regions(world) -> None:
    player, mw = world.player, world.multiworld

    menu = Region("Menu", player, mw)
    field = Region("Field", player, mw)   # misiones/quests (área difusa)
    rooms = {r: Region(r, player, mw) for r in ROOM_NAMES}
    mw.regions += [menu, field, *rooms.values()]

    menu.connect(rooms[starting_room(world)], "Start")
    menu.connect(field, "Field access")

    # transiciones: una entrance por arista dirigida (salvo internas y
    # pads save-only, que no llevan a ninguna parte)
    for d in ALL_EDGES:
        if d["kind"] in NON_TRANSITION_KINDS:
            continue
        rooms[d["src"]].connect(rooms[d["dst"]], d["name"], door_rule(d, player))

    # locations
    active = locations_for_options(
        include_quests=bool(world.options.submission_checks.value),
        include_level4=bool(world.options.level4_victories.value),
    )
    for name, v in active.items():
        room = v.get("room")
        if room in rooms:
            parent, rule = rooms[room], internal_gate_rule(room, player)
        else:
            parent, rule = field, label_rule(room, player)
        loc = MMZXLocation(player, name, v["id"], parent)
        if rule:
            loc.access_rule = rule
        parent.locations.append(loc)

    # objetivo: evento Victory anclado a las salas de la misión final
    victory = MMZXLocation(player, "Defeat Serpent", None, field)
    victory.place_locked_item(world.create_event("Victory"))
    goal_label = LOCATIONS.get("Mission - Destroy Model W", {}).get("room", "D-4D-5")
    goal_rule = label_rule(goal_label, player)
    if goal_rule:
        victory.access_rule = goal_rule
    field.locations.append(victory)
