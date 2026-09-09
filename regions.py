"""Regiones del mundo Mega Man ZX — v0.3: lógica desde logic/logic.json.

Una región de Archipelago por SALA (`a01`, región 'main') y una más por
cada sub-región dibujada en el editor visual (`a01/cueva-e1`). Aristas:
  - data.DOORS (puertas, warps, pasillos, curadas): de la región donde
    está su SALIDA a la región donde ATERRIZA (pertenencia geométrica
    resuelta por logic_format.resolve_members); regla = llave ∧ verja de
    evento ∧ requisito de entrada de la sala destino ∧ coste extra de la
    arista ∧ regla de Transerver. Las puertas internas (src == dst) solo
    crean transición si unen regiones distintas.
  - conexiones curadas región→región (rooms[sala].conns) con su requisito.
Locations: en la región de su posición (data.pos o colocada a mano);
las que aún no tienen sala van a "Field" con la regla de etiqueta de
área (logic.label_rule). Eventos "Cleared: <misión>" con la misma regla
que el check de la misión. Nivel de lógica: opción logic_difficulty
(normal / expert acumulativo).

Preparado para randomizar transiciones en el futuro: cada entrance lleva
el nombre estable de su puerta física (data.DOORS[i].name).
"""

import json
import pkgutil

from BaseClasses import Region

from . import bosses as B
from . import logic_format as F
from .data import LOCATIONS
from .locations import MMZXLocation, locations_for_options, pickup_flags_from_options
from .logic import (ALL_EDGES, WORLD, and_rules, door_rule, label_rule,
                    starting_room, transerver_rule)

_DOC = None


def load_document():
    """logic/logic.json (empaquetado en el apworld) normalizado; cacheado."""
    global _DOC
    if _DOC is None:
        raw = pkgutil.get_data(__name__, "logic/logic.json")
        if raw is None:
            raise FileNotFoundError("worlds/mmzx/logic/logic.json no encontrado: "
                                    "genera la lógica con tools/logic_editor/")
        _DOC = F.normalize_logic(json.loads(raw.decode("utf-8")), WORLD)
    return _DOC


def boss_requirements(world) -> dict:
    """{id de jefe: REQ} de la opción boss_logic del jugador; cacheado en el
    mundo porque lo consultan create_regions, create_item y fill_slot_data."""
    reqs = getattr(world, "_mmzx_boss_reqs", None)
    if reqs is None:
        reqs = B.parse_boss_logic(world.options.boss_logic.value)
        world._mmzx_boss_reqs = reqs
    return reqs


def progression_overrides(world) -> set:
    """Items 'useful' que la lógica convierte en progresión: los que exige el
    documento (LIFEUP>=n / SUBTANK>=n / CHIP_x) y los que exige el YAML de
    jefes del jugador."""
    return F.count_items_used(load_document()) | B.items_used(boss_requirements(world))


def create_regions(world) -> None:
    player, mw = world.player, world.multiworld
    hu_in_pool = bool(world.options.hu_in_pool.value)
    tier = world.options.logic_difficulty.current_key
    doc = load_document()
    members = F.resolve_members(WORLD, doc)

    # Dificultad de jefes del YAML: {BOSS_<ID>: callable}. Se inyecta como
    # átomo (las 8 puertas del boss rush lo usan explícitamente) Y se hace AND
    # en toda arista que aterriza en una región etiquetada como su arena, así
    # que es imposible entrar, cruzarla o coger nada de dentro sin cumplirlo.
    boss_reqs = boss_requirements(world)
    boss_rules = B.compile_rules(boss_reqs, tier, player, hu_in_pool)
    boss_of = F.boss_regions(doc)

    def rule(req):
        return F.compile_req(req, tier, player, hu_in_pool, boss_rules)

    def arena_rule(room, rid):
        """Requisito del jefe cuya arena es esta región (o None)."""
        bid = boss_of.get((room, rid))
        return boss_rules.get(F.boss_atom(bid)) if bid else None

    menu = Region("Menu", player, mw)
    field = Region("Field", player, mw)   # misiones/quests sin colocar
    regions = {}
    for room, rl in doc["rooms"].items():
        for rid in rl["regions"]:
            name = F.region_name(room, rid)
            regions[name] = Region(name, player, mw)
    mw.regions += [menu, field, *regions.values()]

    start = starting_room(world)
    menu.connect(regions[start], "Start",
                 and_rules(rule(doc["rooms"][start].get("req")), arena_rule(start, "main")))
    menu.connect(field, "Field access")

    # conexiones curadas región -> región (dentro de una sala)
    for room, rl in doc["rooms"].items():
        for c in rl.get("conns", []):
            src = regions[F.region_name(room, c["from"])]
            dst = regions[F.region_name(room, c["to"])]
            src.connect(dst, "%s: %s -> %s" % (room, c["from"], c["to"]),
                        and_rules(rule(c.get("req")), arena_rule(room, c["to"])))

    # aristas del grafo estático
    gates = doc.get("gates", {})
    edge_ov = doc.get("edges", {})
    # QoL `skip_boss_rush`: la torre de D-4 se cruza sin re-pelear a los 8
    # Pseudoroids (el cliente marca cada par como vencido al llegar a su
    # parada): la salida a D-5 pierde su requisito BOSS_* y los 8
    # teletransportadores hacia z02 quedan apagados (arista inexistente).
    skip_rush = bool(world.options.skip_boss_rush.value)
    for d in ALL_EDGES:
        if d["kind"] in F.NON_TRANSITION_KINDS:
            continue
        if skip_rush and d["name"] in F.BOSS_RUSH_DOORS:
            continue
        src_rid = members[d["src"]].get(d["name"], "main")
        dst_rid = members[d["dst"]].get(d["name"] + "@in", "main")
        if d["src"] == d["dst"] and src_rid == dst_rid:
            continue                       # puerta interna dentro de la misma región
        gate_req = gates.get(str(d["gate"]), {}).get("req") if d.get("gate") is not None else None
        entry_req = doc["rooms"][d["dst"]].get("req") if d["src"] != d["dst"] else None
        edge_req = edge_ov.get(d["name"], {}).get("req")
        if skip_rush and d["name"] == F.BOSS_RUSH_EXIT:
            edge_req = None
        r = and_rules(door_rule(d, player), rule(entry_req), rule(edge_req),
                      transerver_rule(d, player), rule(gate_req),
                      arena_rule(d["dst"], dst_rid))
        regions[F.region_name(d["src"], src_rid)].connect(
            regions[F.region_name(d["dst"], dst_rid)], d["name"], r)

    # locations
    checks = doc.get("checks", {})

    def place(name, v):
        """(región padre, regla base). Una colocación: la región de su punto.
        Varias (biometales: dos jefes): región Field + OR de alcanzar
        cualquiera de sus regiones. Ninguna: Field + regla de etiqueta."""
        pl = F.check_placements(WORLD, doc, name)
        if len(pl) == 1:
            room = pl[0][0]
            return regions[F.region_name(room, members[room].get(name, "main"))], None
        if len(pl) > 1:
            names = tuple(F.region_name(room, members[room].get(name, "main")) for room, _ in pl)
            return field, (lambda state, _n=names: any(state.can_reach_region(x, player) for x in _n))
        return field, label_rule(v.get("room"), player)

    active = locations_for_options(
        include_quests=bool(world.options.submission_checks.value),
        include_level4=bool(world.options.level4_victories.value),
        pickups=pickup_flags_from_options(world.options),
    )
    for name, v in active.items():
        parent, base = place(name, v)
        loc = MMZXLocation(player, name, v["id"], parent)
        r = and_rules(base, rule(checks.get(name, {}).get("req")))
        if r:
            loc.access_rule = r
        parent.locations.append(loc)

    # eventos "Cleared: <misión>" (una por misión, esté o no activa como
    # check): misma regla de acceso que la location de la misión. Los exigen
    # los átomos de misión (p.ej. la puerta E-7 -> E-8 exige SEARCH_THE_PLANT).
    for name, v in LOCATIONS.items():
        if v.get("category") != "mission":
            continue
        ev_name = "Cleared: " + name[len("Mission - "):]
        parent, base = place(name, v)
        ev = MMZXLocation(player, ev_name, None, parent)
        ev.place_locked_item(world.create_event(ev_name))
        r = and_rules(base, rule(checks.get(name, {}).get("req")))
        if r:
            ev.access_rule = r
        parent.locations.append(ev)

    # objetivo: evento Victory anclado a la misión final
    victory = MMZXLocation(player, "Defeat Serpent", None, field)
    victory.place_locked_item(world.create_event("Victory"))
    final = "Mission - Destroy Model W"
    parent, base = place(final, LOCATIONS.get(final, {"room": "D-4D-5"}))
    # Serpent aparece en D-5 SIN misión ni checks de biometal (agente
    # exp290-299): físicamente basta d02 --Green Key--> d04 -> d05. Como
    # requisito de DISEÑO del goal (equivalente al sello de M-1 / "los 6
    # biometales" de vanilla) se exige además ALL6.
    if base is None:
        pname = parent.name
        base = lambda state, _p=pname: state.can_reach_region(_p, player)  # noqa: E731
    goal_rule = and_rules(base, rule(checks.get(final, {}).get("req")), rule({"normal": [["ALL6"]]}))
    victory.access_rule = goal_rule
    field.locations.append(victory)
