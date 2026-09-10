"""Formato de lógica de Mega Man ZX (worlds/mmzx/logic/logic.json).

Módulo COMPARTIDO por el apworld (regions.py), el editor visual
(tools/logic_editor/) y la migración/validación. No importa nada de
Archipelago: solo Python estándar. Especificación en docs/logic_format.md.

Modelo (estructura de Randovania + requisitos en texto estilo Ori):
  sala -> regiones (polígonos dibujados; "main" = el resto de la sala)
       -> nodos: checks (locations), extremos de arista (salida en la sala
          origen, aterrizaje en la destino), warps
       -> conexiones dirigidas región->región con requisito por nivel.
  La pertenencia de un nodo a una región es GEOMÉTRICA (el polígono que lo
  contiene; el más pequeño si están anidados) salvo override explícito.

Requisito (REQ) = {"normal": DNF, "expert": DNF}; DNF = lista de
alternativas (OR), cada alternativa lista de átomos (AND). [[]] = libre,
[] = imposible. Los niveles son ACUMULATIVOS: en expert valen las
alternativas de normal + las de expert.
"""

import json
import re

FORMAT_VERSION = 1
TIERS = ["normal", "expert"]

# --------------------------------------------------------------------------
# Átomos
# --------------------------------------------------------------------------

ATOM_ITEM = {
    "X": "Model X", "ZX": "Model ZX", "HX": "Progressive Model HX", "FX": "Progressive Model FX",
    "LX": "Progressive Model LX", "PX": "Progressive Model PX", "OX": "Model OX", "HU": "Model Hu",
    "YELLOW": "Yellow Card Key", "GREEN": "Green Card Key", "RED": "Red Card Key",
    "BLUE": "Blue Card Key", "WHITE": "White Card Key", "PURPLE": "Purple Card Key",
}
ACCESS_AREAS = "ABCDEFGIKLMOX"
for _a in ACCESS_AREAS:
    ATOM_ITEM["ACCESS_" + _a] = "Transerver Access - Area " + _a
MODELS_NONHU = ["X", "ZX", "HX", "FX", "LX", "PX", "OX"]
ALL6 = ["X", "ZX", "HX", "FX", "LX", "PX"]
# Biometal COMPLETO (las dos mitades = 2 copias del item progresivo): ataque
# cargado de nivel 2 (p.ej. el huracán de HX que eleva la plataforma del Life
# Up de I-5). `HX` a secas = al menos una mitad.
FULL_MODEL_ATOMS = {"HX2": "Progressive Model HX", "FX2": "Progressive Model FX",
                    "LX2": "Progressive Model LX", "PX2": "Progressive Model PX"}

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
# átomos con conteo: NAME>=n  -> (item, máximo razonable)
COUNT_ATOMS = {"LIFEUP": ("Life Up", 4), "SUBTANK": ("Sub Tank", 4)}
# átomos de conteo sobre una LISTA de eventos: NAME>=n -> (eventos, máximo).
# MISSIONS = misiones de ÁREA completadas (ids 5-12: las 8 que cuenta el juego
# en FUN_02032458; exp449, 2026-09-03). "Protect HQ" se auto-lanza en el
# Report (consola) que deja ese conteo en >= 4 (la misión reportada cuenta).
AREA_MISSION_EVENTS = ["Cleared: Search The Plant", "Cleared: Find The Survivors",
                       "Cleared: Fight The Mavericks", "Cleared: Secure The Biometal",
                       "Cleared: Save The People", "Cleared: Recover The Disk",
                       "Cleared: Attack The Excavators", "Cleared: Protect The Lab"]
LIST_COUNT_ATOMS = {"MISSIONS": (AREA_MISSION_EVENTS, 8)}
MACRO_ATOMS = ("MODEL", "ALL6")
CONST_TRUE = ("TRUE", "ANY", "FREE")
CONST_FALSE = ("FALSE", "NEVER", "IMPOSSIBLE")

# Chips de ITEM B: `useful` por defecto, suben a PROGRESIÓN si algún
# requisito (documento o YAML de jefes) los exige. Ver progression_items().
CHIP_ATOMS = {
    "CHIP_ABSORBER": "Absorber Chip",
    "CHIP_FEATHERWEIGHT": "Featherweight Chip",
    "CHIP_EXTENDER": "Extender Chip",
    "CHIP_QUICK_CHARGER": "Quick Charger Chip",
    "CHIP_ICE_BOOTS": "Ice Boots Chip",
    "CHIP_WIND_BOOTS": "Wind Boots Chip",
    "CHIP_FROG": "Frog Chip",
    "CHIP_ERASER": "Eraser Chip",
}
ATOM_ITEM.update(CHIP_ATOMS)

_COUNT_RE = re.compile(r"^([A-Z_]+)>=(\d+)$")

# --------------------------------------------------------------------------
# Jefes — dificultad configurable por el jugador (opción YAML boss_logic)
# --------------------------------------------------------------------------
# El requisito de cada jefe NO vive en el documento de lógica: lo escribe el
# jugador en su YAML y el mundo lo inyecta como `extra_atoms` al compilar
# (worlds/mmzx/bosses.py + regions.py). En el documento solo se ANCLA dónde
# está cada jefe, de dos maneras:
#   - etiqueta de región `rooms[sala].regions[rid].boss = "<id>"` (preferida:
#     el mundo hace AND del requisito en TODA arista que aterriza en esa
#     región, así que es imposible entrar, cruzar o coger nada de dentro sin
#     cumplirlo, y no depende de acordarse de anotar arista por arista);
#   - átomo `BOSS_<ID>` en cualquier requisito (para lo que no es una región:
#     las 8 puertas del boss rush de D-4 comparten la sala genérica z02).
# Sin YAML el átomo compila a LIBRE: la lógica por defecto es la de siempre.
# `index` = orden canónico del Pseudoroid (niveles de victoria
# 0x02104634..3B y arg del teletransportador del boss rush).
BOSSES = {
    # Giga Aspis (el jefe del TUTORIAL) no está: el randomizer se salta el
    # tutorial entero, así que no se pelea nunca (usuario, 2026-09-04).
    "rayfly": {"name": "Rayfly", "room": "b02", "mission": "Locate Giro"},
    "model_z": {"name": "Model Z", "room": "d02", "mission": "Troop Reinforcement"},
    "hivolt": {"name": "Hivolt", "room": "e07", "mission": "Search The Plant", "index": 0},
    "lurerre": {"name": "Lurerre", "room": "f05", "mission": "Find The Survivors", "index": 1},
    "fistleo": {"name": "Fistleo", "room": "g05", "mission": "Fight The Mavericks", "index": 2},
    "purprill": {"name": "Purprill", "room": "h04", "mission": "Secure The Biometal", "index": 3},
    "hurricaune": {"name": "Hurricaune", "room": "i03", "mission": "Save The People", "index": 4},
    "leganchor": {"name": "Leganchor", "room": "j05", "mission": "Recover The Disk", "index": 5},
    "flammole": {"name": "Flammole", "room": "k04", "mission": "Attack The Excavators", "index": 6},
    "protectos": {"name": "Protectos", "room": "l04", "mission": "Protect The Lab", "index": 7},
    "prometheus": {"name": "Prometheus", "room": "x03", "mission": "Protect Hq"},
    "pandora": {"name": "Pandora", "room": "m03", "mission": "Stop The Dig"},
    "prometheus_pandora": {"name": "Prometheus & Pandora", "room": "o02", "mission": "Repel The Army"},
    "serpent": {"name": "Serpent", "room": "d05", "mission": "Destroy Model W"},
    "omega_zero": {"name": "Omega Zero", "room": "n01", "mission": None},
}
BOSS_ATOMS = {"BOSS_" + b.upper(): b for b in BOSSES}
PSEUDOROIDS = [b for b, v in sorted(BOSSES.items(), key=lambda kv: kv[1].get("index", 99))
               if "index" in v]
# Boss rush de D-4 (torre de Slither Inc.): 8 teletransportadores (entidad
# 5.4B con arg = índice del Pseudoroid, docs/entity_catalog.md §d04) hacia la
# sala genérica z02. Como z02 no tiene checks, lo que de verdad importa es la
# SALIDA a D-5: el JUEGO no deja pasar sin vencer a los ocho (confirmado por
# el usuario, 2026-09-04), así que se exige siempre — y encaja con que un jefe
# exigido en `boss_logic` lo sea en sus DOS encuentros.
BOSS_RUSH_DOORS = {
    "d04 door (288,272)": 0, "d04 door (800,272)": 1,
    "d04 door (288,656)": 2, "d04 door (800,656)": 3,
    "d04 door (480,272)": 4, "d04 door (992,272)": 5,
    "d04 door (480,656)": 6, "d04 door (992,656)": 7,
}
BOSS_RUSH_EXIT = "d04 door (992,736)"        # Boss Rush -> D-5 (Serpent)
# Aristas que SOLO cubren la re-pelea: no valen como anclaje de la pelea
# de historia de un jefe (ver bosses_anchored).
BOSS_RUSH_EDGES = set(BOSS_RUSH_DOORS) | {BOSS_RUSH_EXIT}


# Ids de jefe renombrados: se migran al normalizar el documento (igual que
# LEGACY_EDGE_NAMES), para que una etiqueta antigua no quede huérfana.
LEGACY_BOSS_IDS = {"giga_aspis": "rayfly"}


def boss_atom(boss_id: str) -> str:
    return "BOSS_" + boss_id.upper()


def boss_regions(doc) -> dict:
    """{(sala, rid): id de jefe} de las regiones etiquetadas como arena."""
    out = {}
    for room, rl in (doc.get("rooms") or {}).items():
        for rid, reg in (rl.get("regions") or {}).items():
            b = reg.get("boss")
            if b:
                out[(room, rid)] = b
    return out


def bosses_anchored(doc) -> set:
    """Jefes anclados a su pelea de HISTORIA: etiqueta de arena, o átomo
    BOSS_<ID> en algún requisito que NO sea una puerta del boss rush de D-4
    (esas solo cubren la re-pelea: un jefe anclado solo ahí dejaría su pelea
    original sin requisito, que es justo lo que no puede pasar)."""
    atoms = document_atoms(doc, skip_edges=BOSS_RUSH_EDGES)
    return {BOSS_ATOMS[a] for a in atoms if a in BOSS_ATOMS} | set(boss_regions(doc).values())


def unavailable_atoms(D):
    """Átomos cuyo item NO está en el pool (data.ITEMS pooled=False, p. ej.
    White Card Key): nunca se satisfacen; el validador avisa si se usan."""
    out = set()
    items = getattr(D, "ITEMS", {})
    for atom, item in ATOM_ITEM.items():
        v = items.get(item)
        if v is not None and not v.get("pooled", True) and atom != "HU":
            out.add(atom)
    return out


def atom_catalog(exclude=()):
    """Lista de átomos para la UI: [{id, group, label}]."""
    out = []
    labels = {"HU": "Hu (forma humana)", "X": "Model X", "ZX": "Model ZX", "HX": "Model HX",
              "FX": "Model FX", "LX": "Model LX", "PX": "Model PX", "OX": "Model OX"}
    for m in ["HU"] + MODELS_NONHU:
        out.append({"id": m, "group": "modelo", "label": labels[m]})
    for m in FULL_MODEL_ATOMS:
        out.append({"id": m, "group": "modelo",
                    "label": "Model %s completo (2 mitades: carga nivel 2)" % m[:2]})
    out.append({"id": "MODEL", "group": "modelo", "label": "MODEL (cualquier modelo no-Hu)"})
    out.append({"id": "ALL6", "group": "modelo", "label": "ALL6 (los seis biometales)"})
    for k in ["YELLOW", "GREEN", "RED", "BLUE", "WHITE", "PURPLE"]:
        out.append({"id": k, "group": "llave", "label": ATOM_ITEM[k]})
    for n in range(1, 5):
        out.append({"id": "LIFEUP>=%d" % n, "group": "vida", "label": "Life Up x%d" % n})
    for n in range(1, 5):
        out.append({"id": "SUBTANK>=%d" % n, "group": "vida", "label": "Sub Tank x%d" % n})
    for k, v in MISSION_EVENT.items():
        out.append({"id": k, "group": "misión", "label": v[len("Cleared: "):] + " (completada)"})
    for n in range(1, 9):
        out.append({"id": "MISSIONS>=%d" % n, "group": "misión",
                    "label": "Misiones de área completadas x%d (de las 8: E-7…L-4)" % n})
    for a in ACCESS_AREAS:
        out.append({"id": "ACCESS_" + a, "group": "transerver", "label": "Transerver Access - Area " + a})
    for k, item in CHIP_ATOMS.items():
        out.append({"id": k, "group": "chip", "label": item})
    for atom, bid in BOSS_ATOMS.items():
        b = BOSSES[bid]
        out.append({"id": atom, "group": "jefe",
                    "label": "%s vencido (%s) — requisito del YAML" % (b["name"], room_label(b["room"]))})
    return [a for a in out if a["id"] not in set(exclude)]


def canonical_atom(tok: str):
    """Normaliza un átomo; devuelve None si no existe."""
    t = tok.strip().upper().replace(" ", "")
    if (t in ATOM_ITEM or t in MISSION_EVENT or t in MACRO_ATOMS
            or t in FULL_MODEL_ATOMS or t in BOSS_ATOMS):
        return t
    m = _COUNT_RE.match(t)
    if m and (m.group(1) in COUNT_ATOMS or m.group(1) in LIST_COUNT_ATOMS):
        n = int(m.group(2))
        if n < 1:
            return None
        return "%s>=%d" % (m.group(1), n)
    return None


def is_valid_atom(tok: str) -> bool:
    return isinstance(tok, str) and canonical_atom(tok) is not None


# --------------------------------------------------------------------------
# DNF: lista de alternativas (OR) de listas de átomos (AND)
# --------------------------------------------------------------------------

def dnf_normalize(dnf):
    """Dedupe de átomos y alternativas; absorción (A ⊂ B => B sobra)."""
    alts = []
    for alt in dnf:
        s = []
        for a in alt:
            if a not in s:
                s.append(a)
        alts.append(s)
    keep = []
    for i, a in enumerate(alts):
        sa = set(a)
        absorbed = False
        for j, b in enumerate(alts):
            if i == j:
                continue
            sb = set(b)
            if sb < sa or (sb == sa and j < i):
                absorbed = True
                break
        if not absorbed:
            keep.append(a)
    return keep


def dnf_and(a, b):
    return dnf_normalize([x + y for x in a for y in b])


def dnf_or(a, b):
    return dnf_normalize(list(a) + list(b))


DNF_TRUE = [[]]
DNF_FALSE = []

_TOK = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*>=\s*\d+)?|&&|\|\||[&|()+,])")


def _tokens(expr: str):
    out, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOK.match(expr, pos)
        if not m:
            raise ValueError("invalid expression %r at position %d" % (expr, pos))
        out.append(m.group(1).replace(" ", ""))
        pos = m.end()
    return out


def parse_expr(expr: str):
    """Expresión de texto -> DNF. Sintaxis: átomos, & (o AND, +, ','),
    | (u OR), paréntesis; TRUE/ANY/FREE y FALSE/NEVER."""
    if expr is None:
        return DNF_TRUE
    toks = _tokens(expr)
    if not toks:
        return DNF_TRUE
    dnf, i = _parse_or(toks, 0)
    if i != len(toks):
        raise ValueError("unexpected trailing tokens in %r" % expr)
    return dnf


def _is_and(t):
    return t in ("&", "&&", "+", ",") or t.upper() == "AND"


def _is_or(t):
    return t in ("|", "||") or t.upper() == "OR"


def _parse_or(toks, i):
    node, i = _parse_and(toks, i)
    while i < len(toks) and _is_or(toks[i]):
        rhs, i = _parse_and(toks, i + 1)
        node = dnf_or(node, rhs)
    return node, i


def _parse_and(toks, i):
    node, i = _parse_atom(toks, i)
    while i < len(toks) and _is_and(toks[i]):
        rhs, i = _parse_atom(toks, i + 1)
        node = dnf_and(node, rhs)
    return node, i


def _parse_atom(toks, i):
    if i >= len(toks):
        raise ValueError("incomplete expression")
    t = toks[i]
    if t == "(":
        node, i = _parse_or(toks, i + 1)
        if i >= len(toks) or toks[i] != ")":
            raise ValueError("missing ')'")
        return node, i + 1
    up = t.upper()
    if up in CONST_TRUE:
        return DNF_TRUE, i + 1
    if up in CONST_FALSE:
        return DNF_FALSE, i + 1
    a = canonical_atom(t)
    if a is None:
        raise ValueError("unknown atom %r" % t)
    return [[a]], i + 1


def dnf_to_text(dnf) -> str:
    if not dnf:
        return "never"
    if any(len(alt) == 0 for alt in dnf):
        return "free"
    return " | ".join(" & ".join(alt) for alt in dnf)


# --------------------------------------------------------------------------
# REQ: {tier: DNF}
# --------------------------------------------------------------------------

def req_free():
    return {"normal": [[]]}


def req_from_expr(expr, tier="normal"):
    return {tier: parse_expr(expr)}


def req_alternatives(req, tier="expert"):
    """DNF efectiva en `tier` (acumulativa). None = libre."""
    if req is None:
        return DNF_TRUE
    alts = []
    for t in TIERS[:TIERS.index(tier) + 1]:
        alts.extend(req.get(t) or [])
    return dnf_normalize(alts)


def req_is_free(req, tier="normal"):
    return any(len(a) == 0 for a in req_alternatives(req, tier))


def req_is_never(req, tier="expert"):
    return len(req_alternatives(req, tier)) == 0


def req_to_lines(req):
    """['normal: HX & LX', 'expert: FX'] (una línea por alternativa; los
    niveles sin alternativas se omiten; 'never' si no hay ninguna)."""
    lines = []
    if req is None:
        return ["free"]
    total = 0
    for t in TIERS:
        for alt in req.get(t) or []:
            total += 1
            lines.append("%s: %s" % (t, " & ".join(alt) if alt else "free"))
    if total == 0:
        lines.append("never")
    return lines


def req_atoms(req):
    out = set()
    for t in TIERS:
        for alt in (req or {}).get(t) or []:
            out.update(alt)
    return out


def document_atoms(doc, skip_edges=()):
    """Todos los átomos usados en el documento (checks, conexiones, aristas,
    salas, verjas). `skip_edges`: nombres de arista a ignorar."""
    out = set()
    skip = set(skip_edges)
    for rl in doc.get("rooms", {}).values():
        out |= req_atoms(rl.get("req"))
        for c in rl.get("conns", []):
            out |= req_atoms(c.get("req"))
    for coll in ("checks", "edges", "gates"):
        for name, v in doc.get(coll, {}).items():
            if coll == "edges" and name in skip:
                continue
            out |= req_atoms(v.get("req"))
    return out


def progression_items(atoms):
    """Items `useful` que un conjunto de átomos convierte en PROGRESIÓN:
    Life Up / Sub Tank (átomos de conteo) y chips de ITEM B. Archipelago solo
    cuenta en el estado los items de progresión, así que si algún requisito
    los exige tienen que reclasificarse (worlds/mmzx/__init__.create_item)."""
    used = set()
    for a in atoms:
        if a in CHIP_ATOMS:
            used.add(CHIP_ATOMS[a])
            continue
        m = _COUNT_RE.match(a)
        if m and m.group(1) in COUNT_ATOMS:
            used.add(COUNT_ATOMS[m.group(1)][0])
    return used


def count_items_used(doc):
    """progression_items() de los átomos usados en el documento de lógica."""
    return progression_items(document_atoms(doc))


def req_and(a, b):
    """AND de dos REQ nivel a nivel (acumulativo correcto: se combinan las
    DNF efectivas de cada nivel y se restan las heredadas)."""
    if a is None:
        return b
    if b is None:
        return a
    out = {}
    prev = []
    for t in TIERS:
        eff = dnf_and(req_alternatives(a, t), req_alternatives(b, t))
        out[t] = [alt for alt in eff if alt not in prev]
        prev = eff
    return out


# --------------------------------------------------------------------------
# Compilación a callable(state) -> bool (Archipelago)
# --------------------------------------------------------------------------

def compile_req(req, tier, player, hu_in_pool=False, extra_atoms=None):
    """DNF efectiva -> callable (None = sin regla / siempre cierto).
    extra_atoms: {átomo: callable(state)->bool} para átomos del anfitrión."""
    alts = req_alternatives(req, tier)
    if any(len(a) == 0 for a in alts):
        return None
    if not alts:
        return lambda state: False
    compiled = []
    for alt in alts:
        preds = [p for p in (atom_predicate(a, player, hu_in_pool, extra_atoms) for a in alt)
                 if p is not None]
        compiled.append(preds)
    if any(len(p) == 0 for p in compiled):
        return None

    def rule(state):
        for preds in compiled:
            ok = True
            for p in preds:
                if not p(state):
                    ok = False
                    break
            if ok:
                return True
        return False
    return rule


def atom_predicate(atom, player, hu_in_pool=False, extra_atoms=None):
    if extra_atoms and atom in extra_atoms:
        return extra_atoms[atom]
    if atom == "HU":
        if not hu_in_pool:
            return None
        return lambda state: state.has("Model Hu", player)
    if atom == "MODEL":
        items = [ATOM_ITEM[m] for m in MODELS_NONHU]
        return lambda state: state.has_any(items, player)
    if atom == "ALL6":
        items = [ATOM_ITEM[m] for m in ALL6]
        return lambda state: state.has_all(items, player)
    if atom in BOSS_ATOMS:
        # Sin requisito en el YAML el jefe no pide nada: libre (None). El
        # anfitrion (regions.py) lo pasa en extra_atoms cuando lo hay.
        return None
    if atom in ATOM_ITEM:
        name = ATOM_ITEM[atom]
        return lambda state: state.has(name, player)
    if atom in FULL_MODEL_ATOMS:
        name = FULL_MODEL_ATOMS[atom]
        return lambda state: state.has(name, player, 2)
    if atom in MISSION_EVENT:
        name = MISSION_EVENT[atom]
        return lambda state: state.has(name, player)
    m = _COUNT_RE.match(atom)
    if m and m.group(1) in COUNT_ATOMS:
        name, n = COUNT_ATOMS[m.group(1)][0], int(m.group(2))
        return lambda state: state.has(name, player, n)
    if m and m.group(1) in LIST_COUNT_ATOMS:
        names, n = list(LIST_COUNT_ATOMS[m.group(1)][0]), int(m.group(2))
        return lambda state: state.has_from_list(names, player, n)
    raise ValueError("unknown atom %r" % atom)


# --------------------------------------------------------------------------
# Geometría
# --------------------------------------------------------------------------

def point_in_poly(pt, poly) -> bool:
    if not poly or len(poly) < 3:
        return False
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xc = (xj - xi) * (y - yi) / float(yj - yi) + xi
            if x < xc:
                inside = not inside
        j = i
    return inside


def poly_area(poly) -> float:
    if not poly or len(poly) < 3:
        return 0.0
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def region_of_point(room_logic, pt):
    """rid del polígono más pequeño que contiene pt; 'main' si ninguno."""
    best, best_area = "main", None
    for rid, r in (room_logic.get("regions") or {}).items():
        poly = r.get("poly")
        if rid == "main" or not poly:
            continue
        if point_in_poly(pt, poly):
            a = poly_area(poly)
            if best_area is None or a < best_area:
                best, best_area = rid, a
    return best


# --------------------------------------------------------------------------
# Datos del mundo (data.py) en forma neutra
# --------------------------------------------------------------------------

def room_label(code: str) -> str:
    m = re.match(r"^([a-z])(\d{2})$", code)
    if not m:
        return code
    letter, num = m.group(1), int(m.group(2))
    if letter == "z":
        return "Hub" if num == 1 else "Hub-%d" % num
    return "%s-%d" % (letter.upper(), num)


def build_world(D):
    """Vista neutra de worlds/mmzx/data.py para este módulo."""
    edges = list(D.DOORS)
    rooms = sorted({e["src"] for e in edges} | {e["dst"] for e in edges})
    locs = {}
    for name, v in D.LOCATIONS.items():
        locs[name] = {"category": v.get("category"), "room": v.get("room"),
                      "pos": list(v["pos"]) if v.get("pos") else None,
                      "detect": v.get("detect") is not None}
    return {
        "rooms": rooms,
        "room_label": {r: room_label(r) for r in rooms},
        "locations": locs,
        "edges": edges,
        "hub": D.HUB_ROOM,
        "transerver_access": dict(D.TRANSERVER_ACCESS),
        "transerver_always": list(D.TRANSERVER_ALWAYS),
        "event_gates_open": list(getattr(D, "EVENT_GATES_OPEN", [])),
        "hub_floor_y": dict(getattr(D, "HUB_FLOOR_Y", {})),
    }


# --------------------------------------------------------------------------
# Documento de lógica
# --------------------------------------------------------------------------

def empty_room():
    return {"req": None, "note": "",
            "regions": {"main": {"name": "Main", "poly": None, "color": "#8ab4f8", "note": ""}},
            "conns": [], "members": {}}


def empty_logic(world=None):
    doc = {"format": FORMAT_VERSION, "tiers": list(TIERS), "rooms": {}, "placed": {},
           "edges": {}, "checks": {}, "gates": {}}
    for r in (world or {}).get("rooms", []):
        doc["rooms"][r] = empty_room()
    return doc


# Aristas renombradas en data.DOORS: las curadas sin posición sustituidas por
# su PUERTA DE VUELTA sintetizada (RE 2026-09-03, docs/v02_notes.md §1t). Los
# documentos antiguos (o un editor abierto con los datos viejos) se migran al
# normalizar.
LEGACY_EDGE_NAMES = {
    "a04 curated to j01": "a04 door (2016,752)",
    "b02 curated to d01": "b02 door (5088,496)",
    "e07 curated to e08": "e07 door (1760,720)",
    "k03 door to k04": "k03 door (1760,1104)",
}


def _migrate_edge_names(doc):
    edges = doc.get("edges", {})
    for old, new in LEGACY_EDGE_NAMES.items():
        if old in edges:
            v = edges.pop(old)
            v["pos"], v["dst_pos"] = None, None      # la nueva arista ya trae posición
            edges.setdefault(new, v)
        for rl in doc.get("rooms", {}).values():
            m = rl.get("members", {})
            for k in list(m):
                if k == old or k == old + "@in":
                    m.setdefault(k.replace(old, new), m.pop(k))


def normalize_logic(doc, world=None):
    """Rellena claves ausentes (documento parcial o antiguo) y migra nombres
    de aristas retirados."""
    base = empty_logic()
    for k, v in base.items():
        if k not in doc:
            doc[k] = v
    _migrate_edge_names(doc)
    for r in (world or {}).get("rooms", []):
        doc["rooms"].setdefault(r, empty_room())
    for r in doc["rooms"].values():
        for reg in (r.get("regions") or {}).values():
            if reg.get("boss") in LEGACY_BOSS_IDS:
                reg["boss"] = LEGACY_BOSS_IDS[reg["boss"]]
        r.setdefault("regions", {})
        r["regions"].setdefault("main", empty_room()["regions"]["main"])
        r.setdefault("conns", [])
        r.setdefault("members", {})
        r.setdefault("req", None)
        r.setdefault("note", "")
    return doc


def load_logic(path, world=None):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return empty_logic(world)
    return normalize_logic(doc, world)


def save_logic(path, doc):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def region_name(room, rid):
    return room if rid == "main" else "%s/%s" % (room, rid)


def edge_endpoints(world, doc, edge):
    """(pos de salida en src, pos de aterrizaje en dst) con las posiciones
    colocadas a mano del documento por encima de las de data."""
    ov = doc.get("edges", {}).get(edge["name"], {})
    pos = ov.get("pos") or edge.get("pos")
    dst_pos = ov.get("dst_pos") or edge.get("dst_pos")
    if dst_pos and dst_pos[0] is None:
        dst_pos = None
    return pos, dst_pos


def check_placements(world, doc, name):
    """[(sala, pos)] de una location: su data.pos, o las colocadas a mano en
    `placed` (un objeto {room, pos} o una LISTA de ellos: los biometales se
    obtienen en cualquiera de dos jefes -> dos salas, regla OR)."""
    v = world["locations"].get(name)
    if v is None:
        return []
    if v.get("pos") and v.get("room") in doc["rooms"]:
        return [(v["room"], v["pos"])]
    p = doc.get("placed", {}).get(name)
    items = p if isinstance(p, list) else ([p] if p else [])
    return [(q["room"], q.get("pos")) for q in items
            if isinstance(q, dict) and q.get("room") in doc["rooms"] and q.get("pos")]


def check_position(world, doc, name):
    """(sala, pos) de la PRIMERA colocación de una location; (None, None) si no."""
    pl = check_placements(world, doc, name)
    return pl[0] if pl else (None, None)


def resolve_members(world, doc):
    """{sala: {nodo: rid}} para checks, salidas ('<arista>') y aterrizajes
    ('<arista>@in'); respeta overrides (rooms[r].members)."""
    out = {r: {} for r in doc["rooms"]}

    def put(room, node, pos):
        if room not in out:
            return
        ov = doc["rooms"][room].get("members", {}).get(node)
        if ov and ov in doc["rooms"][room]["regions"]:
            out[room][node] = ov
        elif pos:
            out[room][node] = region_of_point(doc["rooms"][room], pos)
        else:
            out[room][node] = "main"

    for name in world["locations"]:
        for room, pos in check_placements(world, doc, name):
            put(room, name, pos)
    for e in world["edges"]:
        pos, dst_pos = edge_endpoints(world, doc, e)
        put(e["src"], e["name"], pos)
        put(e["dst"], e["name"] + "@in", dst_pos)
    return out


NON_TRANSITION_KINDS = ("save",)


def room_graph(world, doc, room, members, tier="expert"):
    """Aristas región->región dentro de una sala: conexiones curadas +
    puertas internas (si unen regiones distintas). [(from, to, kind, ref)]."""
    rl = doc["rooms"][room]
    edges = []
    for c in rl.get("conns", []):
        if req_is_never(c.get("req"), tier):
            continue
        edges.append((c["from"], c["to"], "conn", c))
    for e in world["edges"]:
        if e["src"] != room or e["dst"] != room or e["kind"] in NON_TRANSITION_KINDS:
            continue
        a = members[room].get(e["name"], "main")
        b = members[room].get(e["name"] + "@in", "main")
        if a != b:
            edges.append((a, b, "internal", e))
    return edges


def room_entries(world, doc, room, members, start_room=None):
    """Regiones por las que se ENTRA a la sala desde fuera."""
    entries = set()
    for e in world["edges"]:
        if e["dst"] == room and e["src"] != room and e["kind"] not in NON_TRANSITION_KINDS:
            entries.add(members[room].get(e["name"] + "@in", "main"))
    if start_room == room or room == world["hub"]:
        entries.add("main")
    return entries


def local_reachability(world, doc, room, members, tier="expert", start_room=None):
    """Regiones alcanzables dentro de la sala ignorando requisitos (solo
    topología): detecta regiones sin ninguna entrada posible."""
    reach = set(room_entries(world, doc, room, members, start_room))
    graph = room_graph(world, doc, room, members, tier)
    changed = True
    while changed:
        changed = False
        for a, b, _k, _r in graph:
            if a in reach and b not in reach:
                reach.add(b)
                changed = True
    return reach


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------

def validate(world, doc, start_room=None, unavailable=()):
    """unavailable: átomos de items fuera del pool (unavailable_atoms): las
    reglas que los usan nunca se cumplen -> aviso."""
    errors, warnings = [], []
    unavailable = set(unavailable)
    boss_tags = {}

    def chk_unavail(req, where):
        used = req_atoms(req) & unavailable
        if used:
            warnings.append("%s: usa %s, que no está en el pool (nunca se cumple)" % (where, ", ".join(sorted(used))))
    rooms = doc["rooms"]
    for r in world["rooms"]:
        if r not in rooms:
            errors.append("falta la sala %s en el documento" % r)
    for r, rl in rooms.items():
        if r not in world["rooms"]:
            errors.append("sala desconocida %r" % r)
            continue
        regs = rl.get("regions", {})
        if "main" not in regs:
            errors.append("%s: falta la región main" % r)
        for rid, reg in regs.items():
            if rid != "main" and (not reg.get("poly") or len(reg["poly"]) < 3):
                errors.append("%s/%s: la región no tiene polígono (mínimo 3 vértices)" % (r, rid))
            b = reg.get("boss")
            if b is not None:
                if b not in BOSSES:
                    errors.append("%s/%s: jefe desconocido %r (ids: %s)" % (
                        r, rid, b, ", ".join(sorted(BOSSES))))
                elif b in boss_tags:
                    errors.append("%s/%s: el jefe %r ya está etiquetado en %s/%s "
                                  "(una arena por jefe)" % (r, rid, b, *boss_tags[b]))
                else:
                    boss_tags[b] = (r, rid)
                    if BOSSES[b]["room"] != r:
                        warnings.append("%s/%s: el jefe %s se esperaba en %s" % (
                            r, rid, BOSSES[b]["name"], BOSSES[b]["room"]))
        seen = set()
        for c in rl.get("conns", []):
            if c.get("from") not in regs or c.get("to") not in regs:
                errors.append("%s: conexión %s->%s con región desconocida" % (r, c.get("from"), c.get("to")))
            if c.get("from") == c.get("to"):
                errors.append("%s: conexión de %s a sí misma" % (r, c.get("from")))
            k = (c.get("from"), c.get("to"))
            if k in seen:
                errors.append("%s: conexión duplicada %s->%s" % (r, k[0], k[1]))
            seen.add(k)
            _check_req(c.get("req"), "%s conexión %s->%s" % (r, k[0], k[1]), errors)
            chk_unavail(c.get("req"), "%s conexión %s->%s" % (r, regs.get(k[0], {}).get("name", k[0]), regs.get(k[1], {}).get("name", k[1])))
        for node, rid in rl.get("members", {}).items():
            if rid not in regs:
                errors.append("%s: override de %r a región desconocida %r" % (r, node, rid))
        _check_req(rl.get("req"), "%s (entrada)" % r, errors, allow_none=True)
        chk_unavail(rl.get("req"), "%s (entrada)" % r)
    for name, p in doc.get("placed", {}).items():
        if name not in world["locations"]:
            errors.append("placed: location desconocida %r" % name)
            continue
        for q in (p if isinstance(p, list) else [p]):
            if not isinstance(q, dict) or q.get("room") not in rooms:
                errors.append("placed: %r en sala desconocida %r" % (name, q.get("room") if isinstance(q, dict) else q))
    edge_names = {e["name"] for e in world["edges"]}
    for name, ov in doc.get("edges", {}).items():
        if name not in edge_names:
            errors.append("edges: arista desconocida %r" % name)
        _check_req(ov.get("req"), "arista %s" % name, errors, allow_none=True)
        chk_unavail(ov.get("req"), "arista %s" % name)
    for name, ch in doc.get("checks", {}).items():
        if name not in world["locations"]:
            errors.append("checks: location desconocida %r" % name)
        _check_req(ch.get("req"), "check %s" % name, errors, allow_none=True)
        chk_unavail(ch.get("req"), "check %s" % name)
    for flag, g in doc.get("gates", {}).items():
        _check_req(g.get("req"), "verja %s" % flag, errors, allow_none=True)
        chk_unavail(g.get("req"), "verja %s" % flag)

    anchored = bosses_anchored(doc)
    loose = [b for b in BOSSES if b not in anchored]
    if loose:
        warnings.append("%d jefes sin anclar en el documento (la opción boss_logic no puede "
                        "aplicarles nada; dibuja su arena y etiquétala): %s" % (
                            len(loose), ", ".join("%s (%s)" % (BOSSES[b]["name"], BOSSES[b]["room"])
                                                  for b in loose)))
    if unavailable:
        for e in world["edges"]:
            key = e.get("key")
            atom = next((a for a, it in ATOM_ITEM.items() if it == key), None)
            if atom in unavailable and e["kind"] not in NON_TRANSITION_KINDS:
                warnings.append("%s: la puerta %s exige %s, que no está en el pool: cerrada en la lógica" % (
                    e["src"], e["name"], key))
    members = resolve_members(world, doc) if not errors else None
    unplaced = [n for n, v in world["locations"].items()
                if check_position(world, doc, n)[0] is None]
    if unplaced:
        warnings.append("%d locations sin colocar (usan la regla de etiqueta de área): %s" % (
            len(unplaced), ", ".join(sorted(unplaced))))
    if members:
        for r in world["rooms"]:
            reach = local_reachability(world, doc, r, members, "expert", start_room)
            conns_of = {}
            for c in rooms[r].get("conns", []):
                conns_of.setdefault(c["from"], []).append(c)
                conns_of.setdefault(c["to"], []).append(c)
            for rid in rooms[r]["regions"]:
                nodes = [n for n, m in members[r].items() if m == rid]
                if rid not in reach and (nodes or conns_of.get(rid)):
                    # (Main vacía y sin conexiones = patrón "todo en polígonos": no se avisa)
                    warnings.append("%s/%s: región sin entrada posible (%d nodos: %s)" % (
                        r, rid, len(nodes), ", ".join(sorted(nodes)[:6]) + ("…" if len(nodes) > 6 else "")))
                if rid != "main" and not nodes and not conns_of.get(rid):
                    warnings.append("%s/%s: región vacía (sin checks, puertas ni conexiones)" % (r, rid))
            warnings.extend(_region_flow_warnings(world, doc, r, members))
    unsure = 0
    for rl in rooms.values():
        unsure += sum(1 for c in rl.get("conns", []) if c.get("unsure"))
    unsure += sum(1 for v in doc.get("checks", {}).values() if v.get("unsure"))
    unsure += sum(1 for v in doc.get("edges", {}).values() if v.get("unsure"))
    return {"errors": errors, "warnings": warnings, "unsure": unsure, "unplaced": len(unplaced)}


def _region_flow_warnings(world, doc, room, members):
    """Avisos de flujo por región: (a) región con entradas pero SIN SALIDA
    (callejón: en el juego siempre se puede volver); (b) nodos en Main sin
    conexión con las otras regiones de la sala (extremos de arista sin
    colocar o fuera de los polígonos) cuando la sala tiene regiones."""
    out = []
    rl = doc["rooms"][room]
    regs = rl["regions"]
    edges = {e["name"]: e for e in world["edges"]}
    per = {rid: [] for rid in regs}
    for node, rid in members[room].items():
        per.setdefault(rid, []).append(node)
    conn_in = {rid: [c for c in rl.get("conns", []) if c["to"] == rid] for rid in regs}
    conn_out = {rid: [c for c in rl.get("conns", []) if c["from"] == rid] for rid in regs}

    def label(node):
        if node.endswith("@in"):
            e = edges[node[:-3]]
            return "llegada de %s" % world["room_label"].get(e["src"], e["src"])
        if node in edges:
            e = edges[node]
            return "salida a %s" % world["room_label"].get(e["dst"], e["dst"])
        return node

    for rid, nodes in per.items():
        ins, outs = [], []
        for n in nodes:
            if n.endswith("@in"):
                e = edges[n[:-3]]
                if e["kind"] in NON_TRANSITION_KINDS:
                    continue
                if e["src"] != room or members[room].get(n[:-3], "main") != rid:
                    ins.append(n)          # llega desde otra sala u otra región
            elif n in edges:
                e = edges[n]
                if e["kind"] in NON_TRANSITION_KINDS:
                    continue
                if e["dst"] != room or members[room].get(n + "@in", "main") != rid:
                    outs.append(n)         # sale a otra sala u otra región
        has_in = bool(ins) or bool(conn_in[rid]) or (rid == "main" and room == world["hub"])
        has_out = bool(outs) or bool(conn_out[rid])
        if has_in and not has_out:
            out.append("%s/%s: región SIN SALIDA (se entra por %s pero no hay puerta ni conexión de vuelta)" % (
                room, rid, ", ".join(label(n) for n in ins[:3]) or "una conexión"))
        # vestíbulo aislado: solo puertas a OTRAS salas, sin conexiones ni puertas
        # internas hacia el resto de la sala (se entra y se sale por la misma
        # puerta; el resto de la sala queda inalcanzable desde ahí)
        if rid != "main" and len(regs) > 1 and nodes and not conn_in[rid] and not conn_out[rid]:
            internal_link = any(
                (n in edges and edges[n]["src"] == edges[n]["dst"] and members[room].get(n + "@in", "main") != rid)
                or (n.endswith("@in") and edges[n[:-3]]["src"] == room and members[room].get(n[:-3], "main") != rid)
                for n in nodes)
            if not internal_link and (ins or outs):
                out.append("%s/%s: región AISLADA del resto de la sala (solo %s; sin conexiones ni puertas internas)" % (
                    room, rid, ", ".join(label(n) for n in (ins + outs)[:3])))
        if rid == "main" and len(regs) > 1 and nodes and not conn_in[rid] and not conn_out[rid] \
                and not any(n in edges and edges[n]["src"] == edges[n]["dst"]
                            and members[room].get(n + "@in", "main") != "main" for n in nodes) \
                and not any(n.endswith("@in") and edges[n[:-3]]["src"] == room
                            and members[room].get(n[:-3], "main") != "main" for n in nodes):
            unplaced = [n for n in nodes if (n.endswith("@in") and not edge_endpoints(world, doc, edges[n[:-3]])[1])
                        or (n in edges and not edge_endpoints(world, doc, edges[n])[0])]
            out.append("%s/main: nodos en Main sin conexión con las otras regiones (%s)%s" % (
                room, ", ".join(label(n) for n in nodes[:6]) + ("…" if len(nodes) > 6 else ""),
                "; sin colocar: " + ", ".join(label(n) for n in unplaced) if unplaced else ""))
    return out


def _check_req(req, where, errors, allow_none=False):
    if req is None:
        if not allow_none:
            errors.append("%s: sin requisito" % where)
        return
    if not isinstance(req, dict):
        errors.append("%s: requisito con forma inválida" % where)
        return
    for t, dnf in req.items():
        if t not in TIERS:
            errors.append("%s: nivel desconocido %r" % (where, t))
            continue
        if not isinstance(dnf, list):
            errors.append("%s: DNF inválida en %s" % (where, t))
            continue
        for alt in dnf:
            if not isinstance(alt, list):
                errors.append("%s: alternativa inválida en %s" % (where, t))
                continue
            for a in alt:
                if not is_valid_atom(a):
                    errors.append("%s: átomo desconocido %r" % (where, a))


# --------------------------------------------------------------------------
# Gemelo de texto (legible; GENERADO)
# --------------------------------------------------------------------------

def _req_block(L, req, unsure, note, indent="      "):
    for rq in req_to_lines(req):
        L.append("%s%s%s" % (indent, "? " if unsure else "", rq))
    if note:
        L[-1] += "   # " + note


def export_txt(world, doc, start_room=None):
    L = []
    members = resolve_members(world, doc)
    L.append("# Lógica de Mega Man ZX — GENERADO por tools/logic_editor (no editar a mano:")
    L.append("#   edita con el editor; este fichero es la vista legible de logic.json).")
    L.append("# Requisitos: una línea por alternativa y nivel; 'free' = sin requisito,")
    L.append("#   'never' = imposible. expert AMPLÍA normal (en expert valen las alternativas")
    L.append("#   de ambos niveles). '?' = sin confirmar in-game.")
    L.append("# Átomos: HU X ZX HX FX LX PX OX MODEL ALL6 · YELLOW GREEN RED BLUE WHITE PURPLE ·")
    L.append("#   LIFEUP>=n SUBTANK>=n · <MISION> (completada) · ACCESS_<área> · CHIP_<chip> ·")
    L.append("#   BOSS_<JEFE> (requisito que pone el jugador en su YAML; libre si no lo pone).")
    L.append("")
    gates = doc.get("gates", {})
    if gates:
        L.append("gates:  # verjas de evento (flag): requisito o 'free' (el cliente la abre)")
        for flag in sorted(gates, key=lambda f: int(f)):
            g = gates[flag]
            req = g.get("req")
            line = "  %s: %s" % (flag, "free" if req is None else " | ".join(req_to_lines(req)))
            if g.get("note"):
                line += "   # " + g["note"]
            L.append(line)
        L.append("")
    by_room_checks = {}
    n_places = {}
    for name in world["locations"]:
        pl = check_placements(world, doc, name)
        n_places[name] = [r for r, _ in pl]
        for room, _ in pl:
            by_room_checks.setdefault(room, []).append(name)

    def reg_title(room, rid):
        return doc["rooms"][room]["regions"].get(rid, {}).get("name", rid)

    for room in world["rooms"]:
        rl = doc["rooms"][room]
        head = "room %s [%s]" % (world["room_label"][room], room)
        if rl.get("req"):
            head += "   entry: " + " | ".join(req_to_lines(rl["req"]))
        if rl.get("note"):
            head += "   # " + rl["note"]
        L.append(head)
        regs = rl["regions"]
        order = ["main"] + sorted(r for r in regs if r != "main")
        for rid in order:
            reg = regs[rid]
            title = "  region %s" % reg.get("name", rid)
            if rid != "main" and reg.get("poly"):
                title += "  (%d vértices)" % len(reg["poly"])
            if reg.get("boss"):
                title += "   [ARENA: %s]" % BOSSES.get(reg["boss"], {}).get("name", reg["boss"])
            if reg.get("note"):
                title += "   # " + reg["note"]
            L.append(title)
            # aristas que SALEN de esta región
            for e in world["edges"]:
                if e["src"] != room or members[room].get(e["name"], "main") != rid:
                    continue
                pos, _ = edge_endpoints(world, doc, e)
                dst_rid = members.get(e["dst"], {}).get(e["name"] + "@in", "main")
                dst = world["room_label"].get(e["dst"], e["dst"])
                if e["dst"] == room:
                    kind, dst = "internal", reg_title(room, dst_rid)
                else:
                    kind = {"warp": "warp", "save": "pad(save)", "curated": "path"}.get(e["kind"], "door")
                    if dst_rid != "main":
                        dst += "/" + reg_title(e["dst"], dst_rid)
                line = "    %s -> %s" % (kind, dst)
                if pos:
                    line += " @(%d,%d)" % (pos[0], pos[1])
                if e.get("key"):
                    line += "  key " + e["key"]
                if e.get("gate") is not None:
                    line += "  gate %d" % e["gate"]
                if e["kind"] == "warp" and e["src"] == world["hub"]:
                    acc = world["transerver_access"].get(e["dst"])
                    line += "  needs %s" % (acc or "NADA (sin destino de Transport)")
                ov = doc.get("edges", {}).get(e["name"], {})
                L.append(line)
                if ov.get("req") and not req_is_free(ov["req"]):
                    _req_block(L, ov["req"], ov.get("unsure"), ov.get("note"))
                elif ov.get("note"):
                    L[-1] += "   # " + ov["note"]
            # aterrizajes en esta región desde OTRAS salas
            for e in world["edges"]:
                if e["dst"] != room or e["src"] == room or e["kind"] in NON_TRANSITION_KINDS:
                    continue
                if members[room].get(e["name"] + "@in", "main") != rid:
                    continue
                _, dpos = edge_endpoints(world, doc, e)
                line = "    <- %s" % world["room_label"].get(e["src"], e["src"])
                if dpos:
                    line += " @(%d,%d)" % (dpos[0], dpos[1])
                L.append(line)
            # checks
            for name in sorted(by_room_checks.get(room, [])):
                if members[room].get(name, "main") != rid:
                    continue
                ch = doc.get("checks", {}).get(name, {})
                req = ch.get("req")
                others = [world["room_label"].get(r, r) for r in n_places.get(name, []) if r != room]
                L.append("    check %s%s" % (name, ("   (también en %s: vale cualquiera)" % ", ".join(others)) if others else ""))
                if req is not None and not (req_is_free(req) and len(req_alternatives(req)) == 1):
                    _req_block(L, req, ch.get("unsure"), ch.get("note"))
                elif ch.get("note"):
                    L[-1] += "   # " + ch["note"]
            # conexiones
            for c in rl.get("conns", []):
                if c["from"] != rid:
                    continue
                L.append("    conn -> %s" % reg_title(room, c["to"]))
                _req_block(L, c.get("req"), c.get("unsure"), c.get("note"))
        L.append("")
    unplaced = sorted(n for n in world["locations"] if check_position(world, doc, n)[0] is None)
    if unplaced:
        L.append("unplaced:  # sin sala: usan la regla de etiqueta de área (data.room)")
        for n in unplaced:
            ch = doc.get("checks", {}).get(n, {})
            line = "  %s  [%s]" % (n, world["locations"][n].get("room"))
            if ch.get("req") and not req_is_free(ch["req"]):
                line += "  " + " | ".join(req_to_lines(ch["req"]))
            L.append(line)
        L.append("")
    return "\n".join(L)
