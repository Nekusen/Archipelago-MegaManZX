"""Universal Tracker callbacks: map tab and player icon from the position the client publishes."""

from ..data import HUB_FLOOR_Y, HUB_ROOM, ROOM_SUBAREA
from .meta import ROOMS, SUB_TO_ROOM, OVERALL_MAP, OVERALL_POINTS, OVERALL_ROOM_POINTS

PLAYER_ICON = "images/player.png"
HUB_SUB = ROOM_SUBAREA[HUB_ROOM]
HUB_PAD_DY = 17                  # console pad height above the floor
HUB_FLOOR_REACH = 96             # y distance within which a floor claims the player


def _hub_area(y: int):
    """Area letter of the hub floor at player y; M wins over N on a tie."""
    best = None
    for letter, fy in HUB_FLOOR_Y.items():
        d = abs(y - (fy - HUB_PAD_DY))
        if d <= HUB_FLOOR_REACH and (best is None or d < best[0] or (d == best[0] and letter < best[1])):
            best = (d, letter)
    return best[1] if best else None


def _parse(data):
    try:
        sub, x, y = int(data[0]), int(data[1]), int(data[2])
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    return sub, x, y


def map_page_index(data) -> int:
    """Index in maps.json of the current room's map, the overall map in the hub, or 0."""
    p = _parse(data)
    if p is None:
        return 0
    if p[0] == HUB_SUB and OVERALL_MAP is not None:
        return int(OVERALL_MAP)
    info = ROOMS.get(SUB_TO_ROOM.get(p[0], ""))
    if info and info.get("room_map") is not None:
        return int(info["room_map"])
    return 0


def location_icon_coords(index: int, data):
    """(x, y, icon) of the player on map index, or None to hide the icon."""
    p = _parse(data)
    if p is None:
        return None
    if index == OVERALL_MAP and OVERALL_MAP is not None:
        # overall map: the current room's box, or the floor's area badge in the hub
        if p[0] == HUB_SUB:
            pt = OVERALL_POINTS.get(_hub_area(p[2]) or "")
        else:
            room = SUB_TO_ROOM.get(p[0], "")
            pt = OVERALL_ROOM_POINTS.get(room) or OVERALL_POINTS.get(room[:1].upper() if room else "")
        return (int(pt[0]), int(pt[1]), PLAYER_ICON) if pt else None
    info = ROOMS.get(SUB_TO_ROOM.get(p[0], ""))
    if not info:
        return None
    if index == info.get("room_map") and info.get("room_xf"):
        ox, oy, sc = info["room_xf"]
    elif index == info.get("area_map") and info.get("area_xf"):
        ox, oy, sc = info["area_xf"]
    else:
        return None
    return int(ox + p[1] * sc), int(oy + p[2] * sc), PLAYER_ICON
