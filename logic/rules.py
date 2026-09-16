"""Logic not drawn in the editor: door keys, the Transerver rule, area labels, start room."""

import re

from .. import data as _data
from . import document as F
from ..data import HUB_ROOM, STARTING_TRANSERVERS, TRANSERVER_ACCESS, TRANSERVER_ALWAYS

# Logic level the world ships. The document also carries expert alternatives (tricks,
# tight jumps); they are not offered as an option yet.
TIER = "normal"

WORLD = F.build_world(_data)
ROOM_NAMES = WORLD["rooms"]


def door_rule(edge: dict, player: int):
    """Key rule of an edge, or None if it has no key."""
    key = edge.get("key")
    if not key:
        return None
    return lambda state: state.has(key, player)


def transerver_rule(edge: dict, player: int):
    """Access rule of a warp leaving the hub, or None for any other edge.

    Warping to a room needs the Transerver Access item of that room's hub floor; a floor with
    no Transport destination cannot be warped to. Walking and stepping on a pad are always free.
    """
    if edge.get("kind") != "warp" or edge["src"] != HUB_ROOM:
        return None
    if edge["dst"] in TRANSERVER_ALWAYS:
        return None                  # destinations that never need an item
    item = TRANSERVER_ACCESS.get(edge["dst"])
    if item is None:
        return lambda state: False   # floor with no Transport destination
    return lambda state: state.has(item, player)


def label_room_groups(label: str) -> list[list[str]]:
    """Room groups of an area label: OR between groups, AND inside each group."""
    groups = []
    for part in str(label).split("/"):
        pairs = re.findall(r"([A-Za-z])-?(\d+)", part)
        if pairs:
            g = ["%s%02d" % (letter.lower(), int(num)) for letter, num in pairs]
        else:  # bare letter: every room of the area
            letter = part.strip()[:1].lower()
            g = [r for r in ROOM_NAMES if r.startswith(letter)]
        g = [r for r in g if r in ROOM_NAMES]
        if g:
            groups.append(g)
    return groups


def label_rule(label: str, player: int):
    """Rule for an unplaced location: reach the main region of the rooms in its label."""
    groups = label_room_groups(label)
    if not groups:
        return None

    def rule(state):
        return any(all(state.can_reach_region(r, player) for r in g)
                   for g in groups)
    return rule


def starting_point(world) -> dict:
    """Record of the starting_transerver option: spawn, room and pre-granted access item."""
    key = world.options.starting_transerver.current_key
    return STARTING_TRANSERVERS.get(key) or next(iter(STARTING_TRANSERVERS.values()))


def starting_room(world) -> str:
    """Room the logic starts in."""
    return starting_point(world)["room"]


def and_rules(*rules):
    """AND of callables, ignoring None; None if nothing is left."""
    rs = [r for r in rules if r is not None]
    if not rs:
        return None
    if len(rs) == 1:
        return rs[0]
    return lambda state: all(r(state) for r in rs)
