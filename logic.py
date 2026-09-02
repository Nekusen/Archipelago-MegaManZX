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

from .data import (DOORS, HUB_ROOM, ROOM_SUBAREA, STARTING_TRANSERVERS,
                   TRANSERVER_ACCESS, TRANSERVER_ALWAYS)

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
# sala -> flags de VERJA DE EVENTO de sus puertas internas (tabla 2 de
# FUN_020924d0; regla por flag en logic_rules.GATE_RULES)
_tmp_g: dict[str, list[int]] = {}
for _d in DOORS:
    if _d["kind"] == "internal" and _d.get("gate") is not None \
            and _d["gate"] not in _tmp_g.setdefault(_d["src"], []):
        _tmp_g[_d["src"]].append(_d["gate"])
_INTERNAL_GATE_FLAGS: dict[str, tuple[int, ...]] = {r: tuple(v) for r, v in _tmp_g.items()}
del _tmp_g


def gate_expr(edge: dict):
    """Expresión DSL de la verja de evento de una arista (o None si no tiene
    o si es libre = el cliente abre la verja)."""
    g = edge.get("gate")
    if g is None:
        return None
    from .logic_rules import GATE_RULES
    return GATE_RULES.get(g)


def internal_gate_rule(room: str, player: int, location: str = None, hu_in_pool: bool = False):
    """Regla coarse para locations FÍSICAS de una sala con gate interno (o
    None): llaves de sus puertas internas Y verjas de evento internas. Las
    locations listadas en logic_rules.INTERNAL_GATE_EXEMPT quedan fuera (ya
    analizadas: el gate interno no las afecta)."""
    keys = _INTERNAL_GATES.get(room)
    flags = _INTERNAL_GATE_FLAGS.get(room)
    if not keys and not flags:
        return None
    if location is not None:
        from .logic_rules import INTERNAL_GATE_EXEMPT
        if location in INTERNAL_GATE_EXEMPT:
            return None
    rules = []
    if keys:
        rules.append(lambda state: state.has_all(keys, player))
    if flags:
        from .logic_rules import GATE_RULES
        for f in flags:
            expr = GATE_RULES.get(f)
            if expr:
                rules.append(compile_rule(expr, player, hu_in_pool))
    return and_rules(*rules)


def door_rule(edge: dict, player: int):
    """Regla de acceso de una arista (o None si es libre)."""
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
    "X": "Model X", "ZX": "Model ZX", "HX": "Model HX", "FX": "Model FX",
    "LX": "Model LX", "PX": "Model PX", "OX": "Model OX", "HU": "Model Hu",
    "YELLOW": "Yellow Card Key", "GREEN": "Green Card Key", "RED": "Red Card Key",
    "BLUE": "Blue Card Key", "WHITE": "White Card Key", "PURPLE": "Purple Card Key",
}
MACROS = {
    "MODEL": "(X|ZX|HX|FX|LX|PX|OX)",
    "ALL6": "(X&ZX&HX&FX&LX&PX)",
    "ANY": "TRUE",
}
# Átomos de EVENTO de misión: "misión X completada" (jefe vencido + Report).
# regions.py crea para cada misión un evento "Cleared: <misión>" en la
# región Field con la misma regla de acceso que la location de la misión;
# estos átomos lo exigen (p.ej. la puerta E-7 -> E-8 exige SEARCH_THE_PLANT:
# bits 0x021045E1.4 && 0x021045FD.4, exp285-287 agente seams).
MISSION_EVENT = {
    "LOCATE_GIRO": "Cleared: Locate Giro",
    "PASS_THE_TEST": "Cleared: Pass The Test",
    "TROOP_REINFORCEMENT": "Cleared: Troop Reinforcement",
    "SEARCH_THE_PLANT": "Cleared: Search The Plant",
    "FIND_THE_SURVIVORS": "Cleared: Find The Survivors",
    "FIGHT_THE_MAVERICKS": "Cleared: Fight The Mavericks",
    "SECURE_THE_BIOMETAL": "Cleared: Secure The Biometal",
    "SAVE_THE_PEOPLE": "Cleared: Save The People",
    "RECOVER_THE_DISK": "Cleared: Recover The Disk",
    "ATTACK_THE_EXCAVATORS": "Cleared: Attack The Excavators",
    "PROTECT_THE_LAB": "Cleared: Protect The Lab",
    "PROTECT_HQ": "Cleared: Protect Hq",
    "STOP_THE_DIG": "Cleared: Stop The Dig",
    "REPEL_THE_ARMY": "Cleared: Repel The Army",
    "DESTROY_MODEL_W": "Cleared: Destroy Model W",
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
    if up in ("FALSE", "NEVER"):
        return ("false",), i + 1
    if up in ABILITY_ITEM:
        return ("item", ABILITY_ITEM[up]), i + 1
    if up in MISSION_EVENT:
        return ("item", MISSION_EVENT[up]), i + 1     # evento "Cleared: <misión>"
    raise ValueError("átomo desconocido %r (HU/X/ZX/HX/FX/LX/PX/OX, llaves, MODEL, ALL6, ANY, "
                     "eventos de misión SEARCH_THE_PLANT...)" % t)


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
        if k == "false":
            return lambda state: False
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
