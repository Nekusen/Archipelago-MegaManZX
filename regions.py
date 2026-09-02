"""Regiones del mundo Mega Man ZX.

v0.2 — LÓGICA (antes: v0.1 no-logic, una sola región). Una región por
sala; transiciones = aristas dirigidas del grafo estático (data.DOORS:
puertas, warps de Transerver, curadas) con las Card Keys como regla base.
Encima, las REGLAS CURADAS de logic_rules.py (biometal por movimiento,
Hu, gimmicks): por sala (entrada), por transición, por sub-región y por
location, compiladas con el DSL de logic.py.

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
van a la región de su sala (o a su sub-región curada).
"""

from BaseClasses import Region

from .data import LOCATIONS
from .locations import MMZXLocation, locations_for_options
from .logic import (ALL_EDGES, NON_TRANSITION_KINDS, ROOM_NAMES, and_rules,
                    compile_rule, door_rule, internal_gate_rule, label_rule,
                    starting_room, transerver_rule)
from .logic_rules import DOOR_RULES, LOCATION_RULES, ROOM_RULES, SUBREGIONS


def create_regions(world) -> None:
    player, mw = world.player, world.multiworld
    hu_in_pool = bool(world.options.hu_in_pool.value)

    def rule(expr):
        return compile_rule(expr, player, hu_in_pool)

    menu = Region("Menu", player, mw)
    field = Region("Field", player, mw)   # misiones/quests (área difusa)
    rooms = {r: Region(r, player, mw) for r in ROOM_NAMES}
    mw.regions += [menu, field, *rooms.values()]

    start = starting_room(world)
    menu.connect(rooms[start], "Start", rule(ROOM_RULES.get(start)))
    menu.connect(field, "Field access")

    # sub-regiones curadas (partes de una sala con requisito propio). Una
    # sub-región puede además RECIBIR puertas (doors_in: la puerta aterriza
    # en ella, no en la sala) y EMITIR puertas (doors_out: la puerta sale
    # de ella) — p. ej. el lado de una sala que queda detrás de un jefe.
    loc_region = {}   # location -> nombre de sub-región
    door_in, door_out = {}, {}   # "src->dst" o nombre de arista -> sub-región
    for name, s in SUBREGIONS.items():
        sub = Region(name, player, mw)
        mw.regions.append(sub)
        parent = rooms[s["parent"]]
        parent.connect(sub, "%s enter" % name, rule(s.get("req")))
        sub.connect(parent, "%s exit" % name, rule(s.get("back")))
        rooms[name] = sub
        for loc in s.get("locations", []):
            loc_region[loc] = name
        for k in s.get("doors_in", []):
            door_in[k] = name
        for k in s.get("doors_out", []):
            door_out[k] = name

    # transiciones: una entrance por arista dirigida (salvo internas y
    # pads save-only). Regla = llave & regla de entrada a la sala destino
    # & regla curada de la transición.
    for d in ALL_EDGES:
        if d["kind"] in NON_TRANSITION_KINDS:
            continue
        pair = "%s->%s" % (d["src"], d["dst"])
        extra = DOOR_RULES.get(d["name"], DOOR_RULES.get(pair))
        # Red de Transervers (modelo HÍBRIDO, decisión 2026-09-02): salir del
        # hub hacia un destino exige su item "Transerver Access - Area X"
        # (el acceso A PIE sigue existiendo por las puertas físicas y los
        # pasillos de piso). Entrar a la red (sala -> hub) es libre.
        r = and_rules(door_rule(d, player), rule(ROOM_RULES.get(d["dst"])), rule(extra),
                      transerver_rule(d, player))
        src = rooms[door_out.get(d["name"], door_out.get(pair, d["src"]))]
        dst = rooms[door_in.get(d["name"], door_in.get(pair, d["dst"]))]
        src.connect(dst, d["name"], r)

    # locations
    active = locations_for_options(
        include_quests=bool(world.options.submission_checks.value),
        include_level4=bool(world.options.level4_victories.value),
    )
    for name, v in active.items():
        room = v.get("room")
        if room in rooms:
            parent = rooms[loc_region.get(name, room)]
            base = internal_gate_rule(room, player, name)
        else:
            parent, base = field, label_rule(room, player)
        loc = MMZXLocation(player, name, v["id"], parent)
        r = and_rules(base, rule(LOCATION_RULES.get(name)))
        if r:
            loc.access_rule = r
        parent.locations.append(loc)

    # eventos "Cleared: <misión>" (una por misión, esté o no activa como
    # check): misma regla de acceso que la location de la misión (etiqueta
    # de área + regla curada). Los exigen los átomos de logic.MISSION_EVENT
    # (p.ej. la puerta E-7 -> E-8 exige SEARCH_THE_PLANT).
    for name, v in LOCATIONS.items():
        if v.get("category") != "mission":
            continue
        ev_name = "Cleared: " + name[len("Mission - "):]
        ev = MMZXLocation(player, ev_name, None, field)
        ev.place_locked_item(world.create_event(ev_name))
        r = and_rules(label_rule(v.get("room"), player), rule(LOCATION_RULES.get(name)))
        if r:
            ev.access_rule = r
        field.locations.append(ev)

    # objetivo: evento Victory anclado a las salas de la misión final
    victory = MMZXLocation(player, "Defeat Serpent", None, field)
    victory.place_locked_item(world.create_event("Victory"))
    goal_label = LOCATIONS.get("Mission - Destroy Model W", {}).get("room", "D-4D-5")
    goal_rule = label_rule(goal_label, player)
    if goal_rule:
        victory.access_rule = goal_rule
    field.locations.append(victory)
