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

from .tracker_meta import ROOMS, SUB_TO_ROOM

PLAYER_ICON = "images/player.png"


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
    info = ROOMS.get(SUB_TO_ROOM.get(p[0], ""))
    if info and info.get("room_map") is not None:
        return int(info["room_map"])
    return 0


def location_icon_coords(index: int, data):
    p = _parse(data)
    if p is None:
        return None
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
