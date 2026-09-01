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
  (las aristas curadas que faltan en la tabla viven en data.DOORS con
   kind='curated' — las emite gen_ap_data.py, única fuente de verdad)
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

ALL_EDGES = DOORS

# kinds que NO crean transición en el grafo de regiones:
#   internal = puerta dentro de la misma sala (con llave = gate interno)
#   save     = pad save-only (sala DATA: guardar/misiones, sin teleport)
NON_TRANSITION_KINDS = ("internal", "save")

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


# ---------------------------------------------------------------------------
# DSL de requisitos (logic_rules.py). Expresiones con `&` (AND), `|` (OR) y
# paréntesis sobre estos átomos (ver la doctrina de movimiento en
# logic_rules.py):
#   HU X ZX HX FX LX PX OX      posesión del modelo/biometal (HU es siempre
#                               cierto salvo con hu_in_pool)
#   YELLOW GREEN RED BLUE WHITE PURPLE   Card Keys
#   MODEL  = cualquier modelo no-Hu (escala paredes)   ALL6 = X&ZX&HX&FX&LX&PX
#   ANY / TRUE = sin requisito
# ---------------------------------------------------------------------------
import re as _re

ABILITY_ITEM = {
    "X": "Model X", "ZX": "Model ZX", "HX": "Biometal H", "FX": "Biometal F",
    "LX": "Biometal L", "PX": "Biometal P", "OX": "Biometal O", "HU": "Model Hu",
    "YELLOW": "Yellow Card Key", "GREEN": "Green Card Key", "RED": "Red Card Key",
    "BLUE": "Blue Card Key", "WHITE": "White Card Key", "PURPLE": "Purple Card Key",
}
MACROS = {
    "MODEL": "(X|ZX|HX|FX|LX|PX|OX)",
    "ALL6": "(X&ZX&HX&FX&LX&PX)",
    "ANY": "TRUE",
}
_TOK = _re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*|[&|()])")


def _tokens(expr: str):
    out, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOK.match(expr, pos)
        if not m:
            raise ValueError("expresión inválida %r en %d" % (expr, pos))
        out.append(m.group(1))
        pos = m.end()
    return out


def _parse(tokens, i=0):
    """OR-expr := AND-expr ('|' AND-expr)*  — devuelve (ast, i)."""
    node, i = _parse_and(tokens, i)
    while i < len(tokens) and tokens[i] == "|":
        rhs, i = _parse_and(tokens, i + 1)
        node = ("or", node, rhs)
    return node, i


def _parse_and(tokens, i):
    node, i = _parse_atom(tokens, i)
    while i < len(tokens) and tokens[i] == "&":
        rhs, i = _parse_atom(tokens, i + 1)
        node = ("and", node, rhs)
    return node, i


def _parse_atom(tokens, i):
    t = tokens[i]
    if t == "(":
        node, i = _parse(tokens, i + 1)
        if i >= len(tokens) or tokens[i] != ")":
            raise ValueError("falta el cierre de paréntesis en %r" % (tokens,))
        return node, i + 1
    up = t.upper()
    if up in MACROS:
        return _parse(_tokens(MACROS[up]))[0], i + 1
    if up == "TRUE":
        return ("true",), i + 1
    if up in ABILITY_ITEM:
        return ("item", ABILITY_ITEM[up]), i + 1
    raise ValueError("átomo desconocido %r (HU/X/ZX/HX/FX/LX/PX/OX, llaves, MODEL, ALL6, ANY)" % t)


def compile_rule(expr, player: int, hu_in_pool: bool):
    """Compila una expresión del DSL a callable(state)->bool (None = sin regla)."""
    if expr is None:
        return None
    toks = _tokens(expr)
    ast, i = _parse(toks)
    if i != len(toks):
        raise ValueError("tokens sobrantes en %r" % expr)

    def build(node):
        k = node[0]
        if k == "true":
            return None
        if k == "item":
            name = node[1]
            if name == "Model Hu" and not hu_in_pool:
                return None          # Hu siempre disponible sin el parche
            return lambda state: state.has(name, player)
        a, b = build(node[1]), build(node[2])
        if k == "and":
            if a is None:
                return b
            if b is None:
                return a
            return lambda state: a(state) and b(state)
        if a is None or b is None:     # or con un lado siempre cierto
            return None
        return lambda state: a(state) or b(state)
    return build(ast)


def and_rules(*rules):
    """AND de callables (ignora None). Devuelve None si no queda nada."""
    rs = [r for r in rules if r is not None]
    if not rs:
        return None
    if len(rs) == 1:
        return rs[0]
    return lambda state: all(r(state) for r in rs)
