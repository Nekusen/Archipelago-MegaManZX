"""Regions of the Mega Man ZX world - v0.3: logic from logic/logic.json.

One Archipelago region per ROOM (`a01`, region 'main') plus one per
sub-region drawn in the visual editor (`a01/cueva-e1`). Edges:
  - data.DOORS (doors, warps, corridors, curated ones): from the region
    holding their EXIT to the region where they LAND (geometric membership
    resolved by logic_format.resolve_members); rule = key AND event gate
    AND entry requirement of the destination room AND extra cost of the
    edge AND Transerver rule. Internal doors (src == dst) only create a
    transition if they join different regions.
  - curated region->region connections (rooms[room].conns) with their requirement.
Locations: in the region of their position (data.pos or placed by hand);
those without a room yet go to "Field" with the area-label rule
(logic.label_rule). "Cleared: <mission>" events with the same rule as the
mission's check. Logic tier: logic_difficulty option (normal / cumulative
expert).

Ready for transition randomization in the future: each entrance carries
the stable name of its physical door (data.DOORS[i].name).
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
    """logic/logic.json (bundled in the apworld), normalized; cached."""
    global _DOC
    if _DOC is None:
        raw = pkgutil.get_data(__name__, "logic/logic.json")
        if raw is None:
            raise FileNotFoundError("logic/logic.json not found: "
                                    "create the logic with tools/logic_editor/")
        _DOC = F.normalize_logic(json.loads(raw.decode("utf-8")), WORLD)
    return _DOC


def boss_requirements(world) -> dict:
    """{boss id: REQ} from the player's boss_logic option; cached on the
    world because create_regions, create_item and fill_slot_data query it."""
    reqs = getattr(world, "_mmzx_boss_reqs", None)
    if reqs is None:
        reqs = B.parse_boss_logic(world.options.boss_logic.value)
        world._mmzx_boss_reqs = reqs
    return reqs


def progression_overrides(world) -> set:
    """'useful' items that the logic turns into progression: those required
    by the document (LIFEUP>=n / SUBTANK>=n / CHIP_x) and those required by
    the player's boss YAML."""
    return F.count_items_used(load_document()) | B.items_used(boss_requirements(world))


def create_regions(world) -> None:
    player, mw = world.player, world.multiworld
    hu_in_pool = bool(world.options.hu_in_pool.value)
    tier = world.options.logic_difficulty.current_key
    doc = load_document()
    members = F.resolve_members(WORLD, doc)

    # Boss difficulty from the YAML: {BOSS_<ID>: callable}. Injected as an
    # atom (the 8 boss rush doors use it explicitly) AND ANDed into every
    # edge that lands in a region tagged as its arena, so it is impossible to
    # enter it, cross it or pick anything inside without meeting it.
    boss_reqs = boss_requirements(world)
    boss_rules = B.compile_rules(boss_reqs, tier, player, hu_in_pool)
    boss_of = F.boss_regions(doc)

    def rule(req):
        return F.compile_req(req, tier, player, hu_in_pool, boss_rules)

    def arena_rule(room, rid):
        """Requirement of the boss whose arena is this region (or None)."""
        bid = boss_of.get((room, rid))
        return boss_rules.get(F.boss_atom(bid)) if bid else None

    menu = Region("Menu", player, mw)
    field = Region("Field", player, mw)   # unplaced missions/quests
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

    # curated region -> region connections (inside a room)
    for room, rl in doc["rooms"].items():
        for c in rl.get("conns", []):
            src = regions[F.region_name(room, c["from"])]
            dst = regions[F.region_name(room, c["to"])]
            src.connect(dst, "%s: %s -> %s" % (room, c["from"], c["to"]),
                        and_rules(rule(c.get("req")), arena_rule(room, c["to"])))

    # edges of the static graph
    gates = doc.get("gates", {})
    edge_ov = doc.get("edges", {})
    # QoL `skip_boss_rush`: the D-4 tower is crossed without re-fighting the
    # 8 Pseudoroids (the client marks each pair as defeated on reaching its
    # stop): the exit to D-5 loses its BOSS_* requirement and the 8
    # teleporters towards z02 are switched off (nonexistent edge).
    skip_rush = bool(world.options.skip_boss_rush.value)
    for d in ALL_EDGES:
        if d["kind"] in F.NON_TRANSITION_KINDS:
            continue
        if skip_rush and d["name"] in F.BOSS_RUSH_DOORS:
            continue
        src_rid = members[d["src"]].get(d["name"], "main")
        dst_rid = members[d["dst"]].get(d["name"] + "@in", "main")
        if d["src"] == d["dst"] and src_rid == dst_rid:
            continue                       # internal door within the same region
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
        """(parent region, base rule). One placement: the region of its point.
        Several (biometals: two bosses): Field region + OR of reaching any
        of their regions. None: Field + label rule."""
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

    # "Cleared: <mission>" events (one per mission, whether or not it is
    # active as a check): same access rule as the mission's location. The
    # mission atoms require them (e.g. the E-7 -> E-8 door requires SEARCH_THE_PLANT).
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

    # goal: Victory event anchored to the final mission
    victory = MMZXLocation(player, "Defeat Serpent", None, field)
    victory.place_locked_item(world.create_event("Victory"))
    final = "Mission - Destroy Model W"
    parent, base = place(final, LOCATIONS.get(final, {"room": "D-4D-5"}))
    # Serpent shows up in D-5 with NO mission nor biometal checks (agent
    # exp290-299): physically d02 --Green Key--> d04 -> d05 is enough. As a
    # DESIGN requirement of the goal (equivalent to the M-1 seal / vanilla's
    # "the 6 biometals") ALL6 is required as well.
    if base is None:
        pname = parent.name
        base = lambda state, _p=pname: state.can_reach_region(_p, player)  # noqa: E731
    goal_rule = and_rules(base, rule(checks.get(final, {}).get("req")), rule({"normal": [["ALL6"]]}))
    victory.access_rule = goal_rule
    field.locations.append(victory)
