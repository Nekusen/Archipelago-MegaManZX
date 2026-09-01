"""Lógica de acceso de Mega Man ZX — v0.2, primer cribado.

Alcance de esta pasada (decisión del usuario, 2026-09-01):
  - Una región por sala; transiciones = aristas DIRIGIDAS de data.DOORS
    (grafo estático extraído del arm9) + EXTRA_EDGES (capa curada a mano
    para transiciones que la tabla de puertas no registra: caídas, etc.).
  - Única regla de acceso: Card Keys. El resto (biometal por movimiento,
    NPCs que exigen Hu, red de Transervers gateada por items) se irá
    añadiendo por iteraciones sobre esta misma estructura.
  - Cada dirección es independiente: una puerta puede exigir llave en un
    sentido y ser libre en el otro (transición unidireccional; el retorno
    lo garantiza el warp anti-softlock del cliente).
  - Preparado para entrance-rando futura (docs AP "entrance
    randomization.md"): los nombres de entrance son estables y describen
    la PUERTA (sala + posición), nunca el destino.

Capas de este módulo:
  EXTRA_EDGES        aristas curadas que faltan en la tabla de puertas.
  internal_gate_rule regla coarse por sala: si una sala tiene puertas
                     INTERNAS con llave (c01/c02/g02/k04/m01/n01), TODA
                     location de esa sala exige esas llaves. Sobre-
                     estricto pero seguro; se afinará partiendo salas
                     con los mapas (interordi) cuando toque.
  label_rule         misiones/quests/biometales usan etiquetas de área
                     humanas ('B-1B-2', 'E-7/I-3', 'F', 'X HQ'):
                     '/' = alternativas (OR); dentro de un grupo, cada
                     par letra-número = sala requerida (AND); letra sin
                     número = TODAS las salas de ese área (AND, coarse).
"""

import re

from .data import DOORS, HUB_ROOM, ROOM_SUBAREA, STARTING_TRANSERVERS

# Transiciones reales sin registro en la tabla de puertas (curadas a mano).
# kind 'fall' = caída unidireccional. status HIPÓTESIS hasta verificarla
# con el harness (teleport + drop); ver docs/v02_notes.md.
EXTRA_EDGES = [
    {"name": "e07 fall to e08", "src": "e07", "dst": "e08",
     "kind": "fall", "key": None, "pos": None},
]

ALL_EDGES = DOORS + EXTRA_EDGES

ROOM_NAMES = sorted({d["src"] for d in ALL_EDGES} | {d["dst"] for d in ALL_EDGES})

# sala -> llaves de sus puertas internas (gate interno coarse)
_tmp: dict[str, list[str]] = {}
for _d in DOORS:
    if _d["kind"] == "internal" and _d["key"] and _d["key"] not in _tmp.setdefault(_d["src"], []):
        _tmp[_d["src"]].append(_d["key"])
_INTERNAL_GATES: dict[str, tuple[str, ...]] = {r: tuple(ks) for r, ks in _tmp.items()}
del _tmp


def internal_gate_rule(room: str, player: int):
    """Regla para locations FÍSICAS de una sala con gate interno (o None)."""
    keys = _INTERNAL_GATES.get(room)
    if not keys:
        return None
    return lambda state: state.has_all(keys, player)


def door_rule(edge: dict, player: int):
    """Regla de acceso de una arista (o None si es libre)."""
    key = edge.get("key")
    if not key:
        return None
    return lambda state: state.has(key, player)


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
    """Regla para misiones/quests: alcanzar las salas de su etiqueta."""
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
