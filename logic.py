"""Lógica de acceso de Mega Man ZX — utilidades del grafo (v0.3).

La lógica curada vive en logic/logic.json (editor visual
tools/logic_editor/, formato docs/logic_format.md, módulo compartido
logic_format.py). Este módulo reúne lo que NO es curable desde el editor:
  - el grafo estático de aristas (data.DOORS) y la regla de llave;
  - la red de Transervers (modelo HÍBRIDO, decisión del usuario 2026-09-02);
  - la regla de etiqueta de área para locations que aún no se han colocado
    en una sala (misiones/quests/biometales con 'B-1B-2', 'E-7/I-3', 'F');
  - la sala inicial según opciones.
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
    """Regla de llave de una arista (o None si es libre)."""
    key = edge.get("key")
    if not key:
        return None
    return lambda state: state.has(key, player)


def transerver_rule(edge: dict, player: int):
    """Modelo HÍBRIDO de la red de Transervers (decisión del usuario,
    2026-09-02): un warp que SALE del hub (sala genérica sub 70, todos los
    pisos conflacionados) hacia una sala exige el item "Transerver Access -
    Area X" del PISO destino (data.TRANSERVER_ACCESS: sala con pad -> item
    del badge de su piso; p.ej. n01 -> Access M, i01 -> Access E). Entrar a
    la red desde una sala (pad) es libre. El acceso a pie (puertas físicas +
    pasillos de piso) no pasa por aquí."""
    if edge.get("kind") != "warp" or edge["src"] != HUB_ROOM:
        return None
    if edge["dst"] in TRANSERVER_ALWAYS:
        return None                  # X-1 Guardian HQ: siempre en la lista (exp271)
    item = TRANSERVER_ACCESS.get(edge["dst"])
    if item is None:
        return lambda state: False   # piso DATA sin destino de Transport: no hay warp
    return lambda state: state.has(item, player)


def label_room_groups(label: str) -> list[list[str]]:
    """Etiqueta de área humana -> [[salas AND]...] en OR entre grupos."""
    groups = []
    for part in str(label).split("/"):
        pairs = re.findall(r"([A-Za-z])-?(\d+)", part)
        if pairs:
            g = ["%s%02d" % (letter.lower(), int(num)) for letter, num in pairs]
        else:  # área sin número ('F', 'G', 'M', 'O'): todas sus salas
            letter = part.strip()[:1].lower()
            g = [r for r in ROOM_NAMES if r.startswith(letter)]
        g = [r for r in g if r in ROOM_NAMES]
        if g:
            groups.append(g)
    return groups


def label_rule(label: str, player: int):
    """Regla para misiones/quests SIN colocar: alcanzar las salas de su
    etiqueta (las regiones 'main' se llaman como la sala)."""
    groups = label_room_groups(label)
    if not groups:
        return None

    def rule(state):
        return any(all(state.can_reach_region(r, player) for r in g)
                   for g in groups)
    return rule


def starting_room(world) -> str:
    """Sala inicial según la opción starting_transerver (data-driven para
    poder randomizar el starting point en el futuro)."""
    key = world.options.starting_transerver.current_key
    sub = STARTING_TRANSERVERS.get(key, STARTING_TRANSERVERS["guardian_hub"])[0]
    for room, s in ROOM_SUBAREA.items():
        if s == sub:
            return room
    return HUB_ROOM


def and_rules(*rules):
    """AND de callables (ignora None). Devuelve None si no queda nada."""
    rs = [r for r in rules if r is not None]
    if not rs:
        return None
    if len(rs) == 1:
        return rs[0]
    return lambda state: all(r(state) for r in rs)
