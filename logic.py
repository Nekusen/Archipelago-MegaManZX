"""Mega Man ZX access logic - graph utilities (v0.3).

The curated logic lives in logic/logic.json (visual editor
tools/logic_editor/, format docs/logic_format.md, shared module
logic_format.py). This module gathers what is NOT curable from the editor:
  - the static edge graph (data.DOORS) and the key rule;
  - the Transerver network (HYBRID model, user decision 2026-09-02);
  - the area-label rule for locations that have not been placed in a room
    yet (missions/quests/biometals with 'B-1B-2', 'E-7/I-3', 'F');
  - the starting room according to the options.
"""

import re

from . import data as _data
from . import logic_format as F
from .data import (DOORS, HUB_ROOM, ROOM_SUBAREA, STARTING_TRANSERVERS,
                   TRANSERVER_ACCESS, TRANSERVER_ALWAYS)

ALL_EDGES = DOORS
WORLD = F.build_world(_data)
ROOM_NAMES = WORLD["rooms"]


def door_rule(edge: dict, player: int):
    """Key rule of an edge (or None if it is free)."""
    key = edge.get("key")
    if not key:
        return None
    return lambda state: state.has(key, player)


def transerver_rule(edge: dict, player: int):
    """HYBRID model of the Transerver network (user decision,
    2026-09-02): a warp LEAVING the hub (generic room sub 70, all floors
    conflated) towards a room requires the "Transerver Access - Area X"
    item of the destination FLOOR (data.TRANSERVER_ACCESS: room with pad ->
    item of its floor's badge; e.g. n01 -> Access M, i01 -> Access E).
    Entering the network from a room (pad) is free. Access on foot (physical
    doors + floor corridors) does not go through here."""
    if edge.get("kind") != "warp" or edge["src"] != HUB_ROOM:
        return None
    if edge["dst"] in TRANSERVER_ALWAYS:
        return None                  # X-1 Guardian HQ: always in the list (exp271)
    item = TRANSERVER_ACCESS.get(edge["dst"])
    if item is None:
        return lambda state: False   # DATA floor with no Transport destination: no warp
    return lambda state: state.has(item, player)


def label_room_groups(label: str) -> list[list[str]]:
    """Human area label -> [[rooms AND]...] with OR between groups."""
    groups = []
    for part in str(label).split("/"):
        pairs = re.findall(r"([A-Za-z])-?(\d+)", part)
        if pairs:
            g = ["%s%02d" % (letter.lower(), int(num)) for letter, num in pairs]
        else:  # area without a number ('F', 'G', 'M', 'O'): all its rooms
            letter = part.strip()[:1].lower()
            g = [r for r in ROOM_NAMES if r.startswith(letter)]
        g = [r for r in g if r in ROOM_NAMES]
        if g:
            groups.append(g)
    return groups


def label_rule(label: str, player: int):
    """Rule for UNPLACED missions/quests: reach the rooms of their label
    (the 'main' regions are named after the room)."""
    groups = label_room_groups(label)
    if not groups:
        return None

    def rule(state):
        return any(all(state.can_reach_region(r, player) for r in g)
                   for g in groups)
    return rule


def starting_room(world) -> str:
    """Starting room according to the starting_transerver option (data-driven
    so the starting point can be randomized in the future)."""
    key = world.options.starting_transerver.current_key
    sub = STARTING_TRANSERVERS.get(key, STARTING_TRANSERVERS["guardian_hub"])[0]
    for room, s in ROOM_SUBAREA.items():
        if s == sub:
            return room
    return HUB_ROOM


def and_rules(*rules):
    """AND of callables (ignores None). Returns None if nothing is left."""
    rs = [r for r in rules if r is not None]
    if not rs:
        return None
    if len(rs) == 1:
        return rs[0]
    return lambda state: all(r(state) for r in rs)
