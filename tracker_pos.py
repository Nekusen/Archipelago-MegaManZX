"""Universal Tracker: auto-tab e icono de posición del jugador.

El cliente escribe en el almacén de datos del servidor la clave
`mmzx_pos_<slot>` = [subárea, x, y] (px de la sala; limitado en frecuencia).
UT vigila esa clave (tracker_world.map_page_setting_key /
location_setting_key) y llama a estas funciones con el valor:
  - map_page_index(data) -> índice del mapa de la SALA actual en maps.json
    (mapa por sala = "zoom"), o 0 si no se conoce.
  - location_icon_coords(index, data) -> (x, y, icono) en píxeles del mapa
    `index` (mapa de sala o de área de esa sala), o None para ocultarlo.
Las transformaciones vienen de tracker_meta.py (generado por
tools/gen_tracker_pack.py).
"""

from .tracker_meta import ROOMS, SUB_TO_ROOM, OVERALL_MAP, OVERALL_POINTS, OVERALL_ROOM_POINTS
from .data import HUB_FLOOR_Y

PLAYER_ICON = "images/player.png"
HUB_SUB = 70


def _hub_area(y: int):
    """Piso del hub (y del jugador) -> letra del área (M antes que N)."""
    best = None
    for letter, fy in HUB_FLOOR_Y.items():
        d = abs(y - (fy - 17))
        if d <= 96 and (best is None or d < best[0] or (d == best[0] and letter < best[1])):
            best = (d, letter)
    return best[1] if best else None


def _parse(data):
    try:
        sub, x, y = int(data[0]), int(data[1]), int(data[2])
    except (TypeError, ValueError, IndexError, KeyError):
        return None
    return sub, x, y


def map_page_index(data) -> int:
    p = _parse(data)
    if p is None:
        return 0
    if p[0] == HUB_SUB and OVERALL_MAP is not None:
        return int(OVERALL_MAP)          # en el hub: mapa general
    info = ROOMS.get(SUB_TO_ROOM.get(p[0], ""))
    if info and info.get("room_map") is not None:
        return int(info["room_map"])
    return 0


def location_icon_coords(index: int, data):
    p = _parse(data)
    if p is None:
        return None
    if index == OVERALL_MAP and OVERALL_MAP is not None:
        # mapa general: icono sobre la caja de la sala actual; en el hub,
        # sobre el badge del área del piso en el que está el jugador
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
