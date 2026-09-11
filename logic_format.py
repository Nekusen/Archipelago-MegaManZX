"""Mega Man ZX logic format (worlds/mmzx/logic/logic.json).

Module SHARED by the apworld (regions.py), the visual editor
(tools/logic_editor/) and migration/validation. It imports nothing from
Archipelago: standard Python only. Specification in docs/logic_format.md.

Model (Randovania's structure + Ori-style text requirements):
  room -> regions (drawn polygons; "main" = the rest of the room)
       -> nodes: checks (locations), edge endpoints (exit in the source
          room, landing in the destination one), warps
       -> directed region->region connections with a requirement per tier.
  A node's membership in a region is GEOMETRIC (the polygon containing it;
  the smallest one if nested) unless explicitly overridden.

Requirement (REQ) = {"normal": DNF, "expert": DNF}; DNF = list of
alternatives (OR), each alternative a list of atoms (AND). [[]] = free,
[] = impossible. Tiers are CUMULATIVE: in expert the alternatives of
normal + those of expert apply.
"""

import json
import re

FORMAT_VERSION = 1
TIERS = ["normal", "expert"]

# --------------------------------------------------------------------------
# Atoms
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
# FULL biometal (both halves = 2 copies of the progressive item): level 2
# charged attack (e.g. HX's hurricane that raises the I-5 Life Up platform).
# Plain `HX` = at least one half.
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
# count atoms: NAME>=n  -> (item, reasonable maximum)
COUNT_ATOMS = {"LIFEUP": ("Life Up", 4), "SUBTANK": ("Sub Tank", 4)}
# count atoms over a LIST of events: NAME>=n -> (events, maximum).
# MISSIONS = AREA missions cleared (ids 5-12: the 8 the game counts in
# FUN_02032458; exp449, 2026-09-03). "Protect HQ" auto-launches on the
# Report (console) that leaves that count at >= 4 (the reported mission counts).
AREA_MISSION_EVENTS = ["Cleared: Search The Plant", "Cleared: Find The Survivors",
                       "Cleared: Fight The Mavericks", "Cleared: Secure The Biometal",
                       "Cleared: Save The People", "Cleared: Recover The Disk",
                       "Cleared: Attack The Excavators", "Cleared: Protect The Lab"]
LIST_COUNT_ATOMS = {"MISSIONS": (AREA_MISSION_EVENTS, 8)}
MACRO_ATOMS = ("MODEL", "ALL6")
CONST_TRUE = ("TRUE", "ANY", "FREE")
CONST_FALSE = ("FALSE", "NEVER", "IMPOSSIBLE")

# ITEM B chips: `useful` by default, promoted to PROGRESSION if some
# requirement (document or boss YAML) demands them. See progression_items().
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
# Bosses - difficulty configurable by the player (boss_logic YAML option)
# --------------------------------------------------------------------------
# Each boss's requirement does NOT live in the logic document: the player
# writes it in their YAML and the world injects it as `extra_atoms` when
# compiling (worlds/mmzx/bosses.py + regions.py). The document only ANCHORS
# where each boss is, in two ways:
#   - region tag `rooms[room].regions[rid].boss = "<id>"` (preferred: the
#     world ANDs the requirement into EVERY edge that lands in that region,
#     so it is impossible to enter, cross or pick anything inside without
#     meeting it, and it does not rely on remembering to annotate edge by edge);
#   - `BOSS_<ID>` atom in any requirement (for what is not a region: the 8
#     doors of the D-4 boss rush share the generic room z02).
# Without a YAML the atom compiles to FREE: the default logic is the usual one.
# `index` = canonical order of the Pseudoroid (victory levels
# 0x02104634..3B and arg of the boss rush teleporter).
BOSSES = {
    # Giga Aspis (the TUTORIAL boss) is not here: the randomizer skips the
    # whole tutorial, so it is never fought (user, 2026-09-04).
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
# D-4 boss rush (Slither Inc. tower): 8 teleporters (entity 5.4B with
# arg = Pseudoroid index, docs/entity_catalog.md, section d04) towards the
# generic room z02. Since z02 has no checks, what really matters is the
# EXIT to D-5: the GAME does not let you through without beating all eight
# (confirmed by the user, 2026-09-04), so it is always required - and it fits
# that a boss required in `boss_logic` is required in BOTH of its encounters.
BOSS_RUSH_DOORS = {
    "d04 door (288,272)": 0, "d04 door (800,272)": 1,
    "d04 door (288,656)": 2, "d04 door (800,656)": 3,
    "d04 door (480,272)": 4, "d04 door (992,272)": 5,
    "d04 door (480,656)": 6, "d04 door (992,656)": 7,
}
BOSS_RUSH_EXIT = "d04 door (992,736)"        # Boss Rush -> D-5 (Serpent)
# Edges that ONLY cover the re-fight: not valid as anchor for a boss's
# story fight (see bosses_anchored).
BOSS_RUSH_EDGES = set(BOSS_RUSH_DOORS) | {BOSS_RUSH_EXIT}


# Renamed boss ids: migrated when normalizing the document (like
# LEGACY_EDGE_NAMES), so that an old tag is not left orphaned.
LEGACY_BOSS_IDS = {"giga_aspis": "rayfly"}


def boss_atom(boss_id: str) -> str:
    return "BOSS_" + boss_id.upper()


def boss_regions(doc) -> dict:
    """{(room, rid): boss id} of the regions tagged as arena."""
    out = {}
    for room, rl in (doc.get("rooms") or {}).items():
        for rid, reg in (rl.get("regions") or {}).items():
            b = reg.get("boss")
            if b:
                out[(room, rid)] = b
    return out


def bosses_anchored(doc) -> set:
    """Bosses anchored to their STORY fight: arena tag, or BOSS_<ID> atom
    in some requirement that is NOT a D-4 boss rush door (those only cover
    the re-fight: a boss anchored only there would leave its original fight
    without requirement, which is exactly what must not happen)."""
    atoms = document_atoms(doc, skip_edges=BOSS_RUSH_EDGES)
    return {BOSS_ATOMS[a] for a in atoms if a in BOSS_ATOMS} | set(boss_regions(doc).values())


def unavailable_atoms(D):
    """Atoms whose item is NOT in the pool (data.ITEMS pooled=False, e.g.
    White Card Key): never satisfied; the validator warns if they are used."""
    out = set()
    items = getattr(D, "ITEMS", {})
    for atom, item in ATOM_ITEM.items():
        v = items.get(item)
        if v is not None and not v.get("pooled", True) and atom != "HU":
            out.add(atom)
    return out


def atom_catalog(exclude=()):
    """Atom list for the UI: [{id, group, label}]."""
    out = []
    labels = {"HU": "Hu (human form)", "X": "Model X", "ZX": "Model ZX", "HX": "Model HX",
              "FX": "Model FX", "LX": "Model LX", "PX": "Model PX", "OX": "Model OX"}
    for m in ["HU"] + MODELS_NONHU:
        out.append({"id": m, "group": "model", "label": labels[m]})
    for m in FULL_MODEL_ATOMS:
        out.append({"id": m, "group": "model",
                    "label": "Model %s full (2 halves: level 2 charge)" % m[:2]})
    out.append({"id": "MODEL", "group": "model", "label": "MODEL (any non-Hu model)"})
    out.append({"id": "ALL6", "group": "model", "label": "ALL6 (the six biometals)"})
    for k in ["YELLOW", "GREEN", "RED", "BLUE", "WHITE", "PURPLE"]:
        out.append({"id": k, "group": "key", "label": ATOM_ITEM[k]})
    for n in range(1, 5):
        out.append({"id": "LIFEUP>=%d" % n, "group": "life", "label": "Life Up x%d" % n})
    for n in range(1, 5):
        out.append({"id": "SUBTANK>=%d" % n, "group": "life", "label": "Sub Tank x%d" % n})
    for k, v in MISSION_EVENT.items():
        out.append({"id": k, "group": "mission", "label": v[len("Cleared: "):] + " (cleared)"})
    for n in range(1, 9):
        out.append({"id": "MISSIONS>=%d" % n, "group": "mission",
                    "label": "Area missions cleared x%d (out of the 8: E-7..L-4)" % n})
    for a in ACCESS_AREAS:
        out.append({"id": "ACCESS_" + a, "group": "transerver", "label": "Transerver Access - Area " + a})
    for k, item in CHIP_ATOMS.items():
        out.append({"id": k, "group": "chip", "label": item})
    for atom, bid in BOSS_ATOMS.items():
        b = BOSSES[bid]
        out.append({"id": atom, "group": "boss",
                    "label": "%s defeated (%s) - YAML requirement" % (b["name"], room_label(b["room"]))})
    return [a for a in out if a["id"] not in set(exclude)]


def canonical_atom(tok: str):
    """Normalizes an atom; returns None if it does not exist."""
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
# DNF: list of alternatives (OR) of lists of atoms (AND)
# --------------------------------------------------------------------------

def dnf_normalize(dnf):
    """Dedupe of atoms and alternatives; absorption (A subset of B => B is redundant)."""
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
    """Text expression -> DNF. Syntax: atoms, & (or AND, +, ','),
    | (or OR), parentheses; TRUE/ANY/FREE and FALSE/NEVER."""
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
    """Effective DNF at `tier` (cumulative). None = free."""
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
    """['normal: HX & LX', 'expert: FX'] (one line per alternative; tiers
    without alternatives are omitted; 'never' if there is none)."""
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
    """All atoms used in the document (checks, connections, edges, rooms,
    gates). `skip_edges`: edge names to ignore."""
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
    """`useful` items that a set of atoms turns into PROGRESSION:
    Life Up / Sub Tank (count atoms) and ITEM B chips. Archipelago only
    counts progression items in the state, so if some requirement demands
    them they must be reclassified (worlds/mmzx/__init__.create_item)."""
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
    """progression_items() of the atoms used in the logic document."""
    return progression_items(document_atoms(doc))


def req_and(a, b):
    """AND of two REQs tier by tier (correctly cumulative: the effective
    DNFs of each tier are combined and the inherited ones subtracted)."""
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
# Compilation to callable(state) -> bool (Archipelago)
# --------------------------------------------------------------------------

def compile_req(req, tier, player, hu_in_pool=False, extra_atoms=None):
    """Effective DNF -> callable (None = no rule / always true).
    extra_atoms: {atom: callable(state)->bool} for the host's atoms."""
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
        # Without a requirement in the YAML the boss asks for nothing: free
        # (None). The host (regions.py) passes it in extra_atoms when there is one.
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
# Geometry
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
    """rid of the smallest polygon containing pt; 'main' if none."""
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
# World data (data.py) in neutral form
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
    """Neutral view of worlds/mmzx/data.py for this module."""
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
# Logic document
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


# Edges renamed in data.DOORS: the curated ones without position replaced by
# their synthesized RETURN DOOR (RE 2026-09-03, docs/v02_notes.md, section
# 1t). Old documents (or an editor open with the old data) are migrated when
# normalizing.
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
            v["pos"], v["dst_pos"] = None, None      # the new edge already carries a position
            edges.setdefault(new, v)
        for rl in doc.get("rooms", {}).values():
            m = rl.get("members", {})
            for k in list(m):
                if k == old or k == old + "@in":
                    m.setdefault(k.replace(old, new), m.pop(k))


def normalize_logic(doc, world=None):
    """Fills in missing keys (partial or old document) and migrates retired
    edge names."""
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
    """(exit pos in src, landing pos in dst) with the document's hand-placed
    positions taking precedence over data's."""
    ov = doc.get("edges", {}).get(edge["name"], {})
    pos = ov.get("pos") or edge.get("pos")
    dst_pos = ov.get("dst_pos") or edge.get("dst_pos")
    if dst_pos and dst_pos[0] is None:
        dst_pos = None
    return pos, dst_pos


def check_placements(world, doc, name):
    """[(room, pos)] of a location: its data.pos, or the ones hand-placed in
    `placed` (a {room, pos} object or a LIST of them: biometals are obtained
    from either of two bosses -> two rooms, OR rule)."""
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
    """(room, pos) of a location's FIRST placement; (None, None) if none."""
    pl = check_placements(world, doc, name)
    return pl[0] if pl else (None, None)


def resolve_members(world, doc):
    """{room: {node: rid}} for checks, exits ('<edge>') and landings
    ('<edge>@in'); honors overrides (rooms[r].members)."""
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
    """Region->region edges inside a room: curated connections + internal
    doors (if they join different regions). [(from, to, kind, ref)]."""
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
    """Regions through which the room is ENTERED from outside."""
    entries = set()
    for e in world["edges"]:
        if e["dst"] == room and e["src"] != room and e["kind"] not in NON_TRANSITION_KINDS:
            entries.add(members[room].get(e["name"] + "@in", "main"))
    if start_room == room or room == world["hub"]:
        entries.add("main")
    return entries


def local_reachability(world, doc, room, members, tier="expert", start_room=None):
    """Regions reachable inside the room ignoring requirements (topology
    only): detects regions with no possible entry."""
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
# Validation
# --------------------------------------------------------------------------

def validate(world, doc, start_room=None, unavailable=()):
    """unavailable: atoms of items outside the pool (unavailable_atoms): the
    rules using them are never met -> warning."""
    errors, warnings = [], []
    unavailable = set(unavailable)
    boss_tags = {}

    def chk_unavail(req, where):
        used = req_atoms(req) & unavailable
        if used:
            warnings.append("%s: uses %s, which is not in the pool (never met)" % (where, ", ".join(sorted(used))))
    rooms = doc["rooms"]
    for r in world["rooms"]:
        if r not in rooms:
            errors.append("room %s is missing from the document" % r)
    for r, rl in rooms.items():
        if r not in world["rooms"]:
            errors.append("unknown room %r" % r)
            continue
        regs = rl.get("regions", {})
        if "main" not in regs:
            errors.append("%s: main region is missing" % r)
        for rid, reg in regs.items():
            if rid != "main" and (not reg.get("poly") or len(reg["poly"]) < 3):
                errors.append("%s/%s: the region has no polygon (at least 3 vertices)" % (r, rid))
            b = reg.get("boss")
            if b is not None:
                if b not in BOSSES:
                    errors.append("%s/%s: unknown boss %r (ids: %s)" % (
                        r, rid, b, ", ".join(sorted(BOSSES))))
                elif b in boss_tags:
                    errors.append("%s/%s: boss %r is already tagged in %s/%s "
                                  "(one arena per boss)" % (r, rid, b, *boss_tags[b]))
                else:
                    boss_tags[b] = (r, rid)
                    if BOSSES[b]["room"] != r:
                        warnings.append("%s/%s: boss %s was expected in %s" % (
                            r, rid, BOSSES[b]["name"], BOSSES[b]["room"]))
        seen = set()
        for c in rl.get("conns", []):
            if c.get("from") not in regs or c.get("to") not in regs:
                errors.append("%s: connection %s->%s with unknown region" % (r, c.get("from"), c.get("to")))
            if c.get("from") == c.get("to"):
                errors.append("%s: connection from %s to itself" % (r, c.get("from")))
            k = (c.get("from"), c.get("to"))
            if k in seen:
                errors.append("%s: duplicate connection %s->%s" % (r, k[0], k[1]))
            seen.add(k)
            _check_req(c.get("req"), "%s connection %s->%s" % (r, k[0], k[1]), errors)
            chk_unavail(c.get("req"), "%s connection %s->%s" % (r, regs.get(k[0], {}).get("name", k[0]), regs.get(k[1], {}).get("name", k[1])))
        for node, rid in rl.get("members", {}).items():
            if rid not in regs:
                errors.append("%s: override of %r to unknown region %r" % (r, node, rid))
        _check_req(rl.get("req"), "%s (entry)" % r, errors, allow_none=True)
        chk_unavail(rl.get("req"), "%s (entry)" % r)
    for name, p in doc.get("placed", {}).items():
        if name not in world["locations"]:
            errors.append("placed: unknown location %r" % name)
            continue
        for q in (p if isinstance(p, list) else [p]):
            if not isinstance(q, dict) or q.get("room") not in rooms:
                errors.append("placed: %r in unknown room %r" % (name, q.get("room") if isinstance(q, dict) else q))
    edge_names = {e["name"] for e in world["edges"]}
    for name, ov in doc.get("edges", {}).items():
        if name not in edge_names:
            errors.append("edges: unknown edge %r" % name)
        _check_req(ov.get("req"), "edge %s" % name, errors, allow_none=True)
        chk_unavail(ov.get("req"), "edge %s" % name)
    for name, ch in doc.get("checks", {}).items():
        if name not in world["locations"]:
            errors.append("checks: unknown location %r" % name)
        _check_req(ch.get("req"), "check %s" % name, errors, allow_none=True)
        chk_unavail(ch.get("req"), "check %s" % name)
    for flag, g in doc.get("gates", {}).items():
        _check_req(g.get("req"), "gate %s" % flag, errors, allow_none=True)
        chk_unavail(g.get("req"), "gate %s" % flag)

    anchored = bosses_anchored(doc)
    loose = [b for b in BOSSES if b not in anchored]
    if loose:
        warnings.append("%d bosses not anchored in the document (the boss_logic option cannot "
                        "apply anything to them; draw their arena and tag it): %s" % (
                            len(loose), ", ".join("%s (%s)" % (BOSSES[b]["name"], BOSSES[b]["room"])
                                                  for b in loose)))
    if unavailable:
        for e in world["edges"]:
            key = e.get("key")
            atom = next((a for a, it in ATOM_ITEM.items() if it == key), None)
            if atom in unavailable and e["kind"] not in NON_TRANSITION_KINDS:
                warnings.append("%s: door %s requires %s, which is not in the pool: closed in the logic" % (
                    e["src"], e["name"], key))
    members = resolve_members(world, doc) if not errors else None
    unplaced = [n for n, v in world["locations"].items()
                if check_position(world, doc, n)[0] is None]
    if unplaced:
        warnings.append("%d unplaced locations (they use the area-label rule): %s" % (
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
                    # (empty Main with no connections = "all in polygons" pattern: no warning)
                    warnings.append("%s/%s: region with no possible entry (%d nodes: %s)" % (
                        r, rid, len(nodes), ", ".join(sorted(nodes)[:6]) + ("..." if len(nodes) > 6 else "")))
                if rid != "main" and not nodes and not conns_of.get(rid):
                    warnings.append("%s/%s: empty region (no checks, doors or connections)" % (r, rid))
            warnings.extend(_region_flow_warnings(world, doc, r, members))
    unsure = 0
    for rl in rooms.values():
        unsure += sum(1 for c in rl.get("conns", []) if c.get("unsure"))
    unsure += sum(1 for v in doc.get("checks", {}).values() if v.get("unsure"))
    unsure += sum(1 for v in doc.get("edges", {}).values() if v.get("unsure"))
    return {"errors": errors, "warnings": warnings, "unsure": unsure, "unplaced": len(unplaced)}


def _region_flow_warnings(world, doc, room, members):
    """Per-region flow warnings: (a) region with entries but NO EXIT (dead
    end: in the game you can always go back); (b) nodes in Main with no
    connection to the other regions of the room (edge endpoints unplaced or
    outside the polygons) when the room has regions."""
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
            return "arrival from %s" % world["room_label"].get(e["src"], e["src"])
        if node in edges:
            e = edges[node]
            return "exit to %s" % world["room_label"].get(e["dst"], e["dst"])
        return node

    for rid, nodes in per.items():
        ins, outs = [], []
        for n in nodes:
            if n.endswith("@in"):
                e = edges[n[:-3]]
                if e["kind"] in NON_TRANSITION_KINDS:
                    continue
                if e["src"] != room or members[room].get(n[:-3], "main") != rid:
                    ins.append(n)          # arrives from another room or another region
            elif n in edges:
                e = edges[n]
                if e["kind"] in NON_TRANSITION_KINDS:
                    continue
                if e["dst"] != room or members[room].get(n + "@in", "main") != rid:
                    outs.append(n)         # leaves to another room or another region
        has_in = bool(ins) or bool(conn_in[rid]) or (rid == "main" and room == world["hub"])
        has_out = bool(outs) or bool(conn_out[rid])
        if has_in and not has_out:
            out.append("%s/%s: region with NO EXIT (entered through %s but there is no door or connection back)" % (
                room, rid, ", ".join(label(n) for n in ins[:3]) or "a connection"))
        # isolated vestibule: only doors to OTHER rooms, no connections or
        # internal doors towards the rest of the room (you enter and leave
        # through the same door; the rest of the room is unreachable from there)
        if rid != "main" and len(regs) > 1 and nodes and not conn_in[rid] and not conn_out[rid]:
            internal_link = any(
                (n in edges and edges[n]["src"] == edges[n]["dst"] and members[room].get(n + "@in", "main") != rid)
                or (n.endswith("@in") and edges[n[:-3]]["src"] == room and members[room].get(n[:-3], "main") != rid)
                for n in nodes)
            if not internal_link and (ins or outs):
                out.append("%s/%s: region ISOLATED from the rest of the room (only %s; no connections or internal doors)" % (
                    room, rid, ", ".join(label(n) for n in (ins + outs)[:3])))
        if rid == "main" and len(regs) > 1 and nodes and not conn_in[rid] and not conn_out[rid] \
                and not any(n in edges and edges[n]["src"] == edges[n]["dst"]
                            and members[room].get(n + "@in", "main") != "main" for n in nodes) \
                and not any(n.endswith("@in") and edges[n[:-3]]["src"] == room
                            and members[room].get(n[:-3], "main") != "main" for n in nodes):
            unplaced = [n for n in nodes if (n.endswith("@in") and not edge_endpoints(world, doc, edges[n[:-3]])[1])
                        or (n in edges and not edge_endpoints(world, doc, edges[n])[0])]
            out.append("%s/main: nodes in Main with no connection to the other regions (%s)%s" % (
                room, ", ".join(label(n) for n in nodes[:6]) + ("..." if len(nodes) > 6 else ""),
                "; unplaced: " + ", ".join(label(n) for n in unplaced) if unplaced else ""))
    return out


def _check_req(req, where, errors, allow_none=False):
    if req is None:
        if not allow_none:
            errors.append("%s: no requirement" % where)
        return
    if not isinstance(req, dict):
        errors.append("%s: malformed requirement" % where)
        return
    for t, dnf in req.items():
        if t not in TIERS:
            errors.append("%s: unknown tier %r" % (where, t))
            continue
        if not isinstance(dnf, list):
            errors.append("%s: invalid DNF in %s" % (where, t))
            continue
        for alt in dnf:
            if not isinstance(alt, list):
                errors.append("%s: invalid alternative in %s" % (where, t))
                continue
            for a in alt:
                if not is_valid_atom(a):
                    errors.append("%s: unknown atom %r" % (where, a))


# --------------------------------------------------------------------------
# Text twin (readable; GENERATED)
# --------------------------------------------------------------------------

def _req_block(L, req, unsure, note, indent="      "):
    for rq in req_to_lines(req):
        L.append("%s%s%s" % (indent, "? " if unsure else "", rq))
    if note:
        L[-1] += "   # " + note


def export_txt(world, doc, start_room=None):
    L = []
    members = resolve_members(world, doc)
    L.append("# Mega Man ZX logic - GENERATED by tools/logic_editor (do not edit by hand:")
    L.append("#   edit with the editor; this file is the readable view of logic.json).")
    L.append("# Requirements: one line per alternative and tier; 'free' = no requirement,")
    L.append("#   'never' = impossible. expert EXTENDS normal (in expert the alternatives")
    L.append("#   of both tiers apply). '?' = not confirmed in-game.")
    L.append("# Atoms: HU X ZX HX FX LX PX OX MODEL ALL6 ; YELLOW GREEN RED BLUE WHITE PURPLE ;")
    L.append("#   LIFEUP>=n SUBTANK>=n ; <MISSION> (cleared) ; ACCESS_<area> ; CHIP_<chip> ;")
    L.append("#   BOSS_<BOSS> (requirement set by the player in their YAML; free if unset).")
    L.append("")
    gates = doc.get("gates", {})
    if gates:
        L.append("gates:  # event gates (flag): requirement or 'free' (the client opens it)")
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
                title += "  (%d vertices)" % len(reg["poly"])
            if reg.get("boss"):
                title += "   [ARENA: %s]" % BOSSES.get(reg["boss"], {}).get("name", reg["boss"])
            if reg.get("note"):
                title += "   # " + reg["note"]
            L.append(title)
            # edges LEAVING this region
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
                    line += "  needs %s" % (acc or "NOTHING (no Transport destination)")
                ov = doc.get("edges", {}).get(e["name"], {})
                L.append(line)
                if ov.get("req") and not req_is_free(ov["req"]):
                    _req_block(L, ov["req"], ov.get("unsure"), ov.get("note"))
                elif ov.get("note"):
                    L[-1] += "   # " + ov["note"]
            # landings in this region from OTHER rooms
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
                L.append("    check %s%s" % (name, ("   (also in %s: any of them counts)" % ", ".join(others)) if others else ""))
                if req is not None and not (req_is_free(req) and len(req_alternatives(req)) == 1):
                    _req_block(L, req, ch.get("unsure"), ch.get("note"))
                elif ch.get("note"):
                    L[-1] += "   # " + ch["note"]
            # connections
            for c in rl.get("conns", []):
                if c["from"] != rid:
                    continue
                L.append("    conn -> %s" % reg_title(room, c["to"]))
                _req_block(L, c.get("req"), c.get("unsure"), c.get("note"))
        L.append("")
    unplaced = sorted(n for n in world["locations"] if check_position(world, doc, n)[0] is None)
    if unplaced:
        L.append("unplaced:  # no room: they use the area-label rule (data.room)")
        for n in unplaced:
            ch = doc.get("checks", {}).get(n, {})
            line = "  %s  [%s]" % (n, world["locations"][n].get("room"))
            if ch.get("req") and not req_is_free(ch["req"]):
                line += "  " + " | ".join(req_to_lines(ch["req"]))
            L.append(line)
        L.append("")
    return "\n".join(L)
