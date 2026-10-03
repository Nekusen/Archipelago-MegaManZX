"""Archipelago regions, entrances, locations and events built from the logic document."""

from BaseClasses import Region

from . import goal as G
from .logic import bosses as B
from .logic import document as F
from .logic import load_document
from .data import (DOORS, LOCATIONS, STORY_CHAINS, STORY_COUNTS, STORY_GATE_ITEMS, STORY_LAVA_ITEM,
                   STORY_LAVA_LOCATION, STORY_REPORT_ITEMS)
from .locations import MMZXLocation, STORY_ITEMS, active_locations, story_mode
from .logic.rules import (TIER, WORLD, and_rules, door_rule, label_rule, starting_room,
                          transerver_rule)

MISSION_PREFIX = "Mission - "
LAVA_EVENT = "Lava Flow Slowed"   # what SLOW_LAVA tests while no item slows the lava


def boss_requirements(world) -> dict:
    """{boss id: REQ} from the boss_logic option, cached on the world for the other hooks."""
    reqs = getattr(world, "_mmzx_boss_reqs", None)
    if reqs is None:
        reqs = B.parse_boss_logic(world.options.boss_logic.value)
        world._mmzx_boss_reqs = reqs
    return reqs


def progression_overrides(world) -> set:
    """Useful items that the document or the player's boss YAML turn into progression."""
    return F.count_items_used(load_document()) | B.items_used(boss_requirements(world))


def create_regions(world) -> None:
    """Creates the regions, entrances, locations and events of one player.

    A door's rule is the AND of its key, the destination room's entry requirement when the
    door changes room, its extra cost, the Transerver rule, its event gate and the landing arena.
    """
    player, mw = world.player, world.multiworld
    hu_in_pool = bool(world.options.hu_in_pool.value)
    full_models = not world.options.progressive_models.value
    tier = TIER
    doc = load_document()
    members = F.resolve_members(WORLD, doc)

    # Boss rules are injected as BOSS_* atoms and added to every edge landing in the boss's arena;
    # the goal requirements of the YAML are the GOAL atom.
    boss_reqs = boss_requirements(world)
    host_atoms = B.compile_rules(boss_reqs, tier, player, hu_in_pool, full_models)
    boss_of = F.boss_regions(doc)
    goal_rule = G.rule(world.goal, player)
    host_atoms["GOAL"] = goal_rule or (lambda state: True)
    # with mission_objectives: items a Report, a story gate and the slow lava each ask for an item
    story_items = story_mode(world.options) == STORY_ITEMS
    lava = STORY_LAVA_ITEM if story_items else LAVA_EVENT
    host_atoms[F.SLOW_LAVA] = lambda state: state.has(lava, player)

    def has(item):
        return (lambda state: state.has(item, player)) if item and story_items else None

    def report_rule(name):
        """Rule of the object a mission's Report asks for, or None."""
        if not name.startswith(MISSION_PREFIX):
            return None
        return has(STORY_REPORT_ITEMS.get(name[len(MISSION_PREFIX):]))

    def rule(req):
        return F.compile_req(req, tier, player, hu_in_pool, host_atoms, full_models)

    def arena_rule(room, rid):
        """Rule of the boss whose arena is this region, or None."""
        bid = boss_of.get((room, rid))
        return host_atoms.get(F.boss_atom(bid)) if bid else None

    start = starting_room(world)
    # skip_boss_rush drops the eight rush teleporters and the extra cost of the exit to D-5;
    # the client marks the pairs as beaten while the player climbs the tower.
    skip_rush = bool(world.options.skip_boss_rush.value)
    active = active_locations(world.options)
    final = G.FINAL_MISSION

    def door_edges():
        """Doors that join two different regions, as (source region, destination region, door, destination region id)."""
        for d in DOORS:
            if d["kind"] in F.NON_TRANSITION_KINDS:
                continue
            if skip_rush and d["name"] in F.BOSS_RUSH_DOORS:
                continue
            src_rid = members[d["src"]].get(d["name"], "main")
            dst_rid = members[d["dst"]].get(d["name"] + "@in", "main")
            if d["src"] == d["dst"] and src_rid == dst_rid:
                continue                   # internal door within the same region
            yield F.region_name(d["src"], src_rid), F.region_name(d["dst"], dst_rid), d, dst_rid

    def placed_regions(name):
        return [F.region_name(room, members[room].get(name, "main"))
                for room, _ in F.check_placements(WORLD, doc, name)]

    # A room's "main" region exists only when a door, a connection, a location or the start
    # uses it; an empty region nothing leads to would be unreachable by construction.
    needed = {F.region_name(start, "main")}
    for room, rl in doc["rooms"].items():
        needed.update(F.region_name(room, rid) for rid in rl["regions"] if rid != "main")
        for c in rl.get("conns", []):
            needed.update((F.region_name(room, c["from"]), F.region_name(room, c["to"])))
    for src_name, dst_name, _d, _rid in door_edges():
        needed.update((src_name, dst_name))
    missions = [n for n, v in LOCATIONS.items() if v.get("category") == "mission"]
    for name in [*active, *missions, final, STORY_LAVA_LOCATION]:
        needed.update(placed_regions(name))

    menu = Region("Menu", player, mw)
    field = Region("Field", player, mw)   # unplaced missions/quests
    regions = {}
    for room, rl in doc["rooms"].items():
        for rid in rl["regions"]:
            name = F.region_name(room, rid)
            if name in needed:
                regions[name] = Region(name, player, mw)
    mw.regions += [menu, field, *regions.values()]

    menu.connect(regions[start], "Start",
                 and_rules(rule(doc["rooms"][start].get("req")), arena_rule(start, "main")))
    menu.connect(field, "Field access")

    # drawn connections inside each room
    for room, rl in doc["rooms"].items():
        for c in rl.get("conns", []):
            src = regions[F.region_name(room, c["from"])]
            dst = regions[F.region_name(room, c["to"])]
            src.connect(dst, "%s: %s -> %s" % (room, c["from"], c["to"]),
                        and_rules(rule(c.get("req")), arena_rule(room, c["to"])))

    # door table edges
    gates = doc.get("gates", {})
    edge_ov = doc.get("edges", {})
    for src_name, dst_name, d, dst_rid in door_edges():
        gate_req = gates.get(str(d["gate"]), {}).get("req") if d.get("gate") is not None else None
        entry_req = doc["rooms"][d["dst"]].get("req") if d["src"] != d["dst"] else None
        edge_req = edge_ov.get(d["name"], {}).get("req")
        if skip_rush and d["name"] == F.BOSS_RUSH_EXIT:
            edge_req = None
        r = and_rules(door_rule(d, player), rule(entry_req), rule(edge_req),
                      transerver_rule(d, player), rule(gate_req), has(STORY_GATE_ITEMS.get(d.get("gate"))),
                      arena_rule(d["dst"], dst_rid))
        regions[src_name].connect(regions[dst_name], d["name"], r)

    # locations
    checks = doc.get("checks", {})

    def place(name, v):
        """(parent region, base rule) of a location.

        One placement: the region of its point. Two: Field with "reach either region".
        None: Field with the area-label rule.
        """
        pl = F.check_placements(WORLD, doc, name)
        if len(pl) == 1:
            room = pl[0][0]
            return regions[F.region_name(room, members[room].get(name, "main"))], None
        if len(pl) > 1:
            names = tuple(F.region_name(room, members[room].get(name, "main")) for room, _ in pl)
            return field, (lambda state, _n=names: any(state.can_reach_region(x, player) for x in _n))
        return field, label_rule(v.get("room"), player)

    for name, v in active.items():
        parent, base = place(name, v)
        loc = MMZXLocation(player, name, v["id"], parent)
        r = and_rules(base, rule(checks.get(name, {}).get("req")), report_rule(name))
        if r:
            loc.access_rule = r
        parent.locations.append(loc)

    # the story locations the game gives in order, or after some others, also need those
    def after(name, earlier, count):
        loc = mw.get_location(name, player)
        own = loc.access_rule
        loc.access_rule = lambda state: (
            own(state) and sum(state.can_reach_location(n, player) for n in earlier) >= count)

    for chain in STORY_CHAINS:
        for earlier, name in zip(chain, chain[1:]):
            if earlier in active and name in active:
                after(name, [earlier], 1)
    for name, (count, group) in STORY_COUNTS.items():
        if name in active:
            after(name, [n for n in group if n in active], count)

    def add_event(ev_name, name, v):
        """An event at a location's place, with its rule, whether the location is a check or not."""
        parent, base = place(name, v)
        ev = MMZXLocation(player, ev_name, None, parent)
        ev.place_locked_item(world.create_event(ev_name))
        r = and_rules(base, rule(checks.get(name, {}).get("req")), report_rule(name))
        if r:
            ev.access_rule = r
        parent.locations.append(ev)

    # one "Cleared" event per mission, active check or not; the mission atoms test these
    for name, v in LOCATIONS.items():
        if v.get("category") != "mission":
            continue
        add_event(G.cleared_event(name), name, v)
    if not story_items:
        add_event(LAVA_EVENT, STORY_LAVA_LOCATION, LOCATIONS[STORY_LAVA_LOCATION])

    # goal: Victory event anchored to the final mission
    victory = MMZXLocation(player, "Defeat Serpent", None, field)
    victory.place_locked_item(world.create_event("Victory"))
    parent, base = place(final, LOCATIONS.get(final, {"room": "D-4D-5"}))
    # Nothing in the game gates Serpent beyond the Green Card Key door into D-4; the goal
    # requirements stand in for the vanilla six-biometal seal, here and on the gate.
    if base is None:
        pname = parent.name
        base = lambda state, _p=pname: state.can_reach_region(_p, player)  # noqa: E731
    victory.access_rule = and_rules(base, rule(checks.get(final, {}).get("req")), goal_rule)
    field.locations.append(victory)
