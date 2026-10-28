"""Shared core of the logic document: atoms, requirements, regions, validation and the generated
logic module.

Imports nothing from Archipelago, so the editor and the tools load it on their own.
"""

import json
import re

FORMAT_VERSION = 1
TIERS = ["normal", "expert"]

# Atoms

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
# Both halves of the biometal, which unlock the level 2 charge; plain HX is one half.
FULL_MODEL_ATOMS = {"HX2": "Progressive Model HX", "FX2": "Progressive Model FX",
                    "LX2": "Progressive Model LX", "PX2": "Progressive Model PX"}
# Without progressive models each biometal is one item holding both halves.
FULL_MODEL_ITEMS = {"Progressive Model HX": "Model HX", "Progressive Model FX": "Model FX",
                    "Progressive Model LX": "Model LX", "Progressive Model PX": "Model PX"}

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
# Count atoms NAME>=n: (item or events, copies that exist). Any n >= 1 parses.
COUNT_ATOMS = {"LIFEUP": ("Life Up", 4), "SUBTANK": ("Sub Tank", 4)}
# The eight area missions; the game launches Protect HQ once four are cleared.
AREA_MISSION_EVENTS = ["Cleared: Search The Plant", "Cleared: Find The Survivors",
                       "Cleared: Fight The Mavericks", "Cleared: Secure The Biometal",
                       "Cleared: Save The People", "Cleared: Recover The Disk",
                       "Cleared: Attack The Excavators", "Cleared: Protect The Lab"]
LIST_COUNT_ATOMS = {"MISSIONS": (AREA_MISSION_EVENTS, 8)}
# GOAL is the player's goal requirements, resolved per player from the YAML.
MACRO_ATOMS = ("MODEL", "ALL6", "GOAL")
CONST_TRUE = ("TRUE", "ANY", "FREE")
CONST_FALSE = ("FALSE", "NEVER", "IMPOSSIBLE")

# The lava of Area K set to slow, the door of K-1 unlocked and the bridge of D-1 lowered: an
# item with mission_objectives: locations_and_items, else the event of the Lava Flow Control of K-1, of the
# switch of K-4 and of the switch of D-1; the bridge is down from the start with the option off.
SLOW_LAVA = "SLOW_LAVA"
K_DOOR_SWITCH = "K_DOOR_SWITCH"
D_BRIDGE = "D_BRIDGE"
STORY_ATOMS = {SLOW_LAVA: "Lava Flow Control", K_DOOR_SWITCH: "Area K Door Switch", D_BRIDGE: "Area D Bridge"}

# Routes the game's state hangs on. The lava chase of K-4 only arms when K-4 is entered through its
# door from K-3, and the people of Area G can only be reached while its boss stands, so their checks
# ask for a way in that keeps clear of the arena.
LAVA_CHASE = "LAVA_CHASE"
AVOID_BOSS_ROOM = "AVOID_BOSS_ROOM"
LAVA_CHASE_DOOR = "k03 door (1760,1104)"
ROUTE_ATOMS = (LAVA_CHASE, AVOID_BOSS_ROOM)

# Useful items; progression_items() promotes them when a requirement uses them.
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

# The events that stand for the story atoms while no item does, and the ones the missions, the
# biometal checks and the goal leave behind.
LAVA_EVENT = "Lava Flow Slowed"
SWITCH_EVENT = "K-1 Door Unlocked"
BRIDGE_EVENT = "D-1 Bridge Lowered"
STORY_EVENT = {SLOW_LAVA: LAVA_EVENT, K_DOOR_SWITCH: SWITCH_EVENT, D_BRIDGE: BRIDGE_EVENT}
MISSION_PREFIX = "Mission - "
CLEARED_PREFIX = "Cleared: "
BIOMETAL_PREFIX = "Obtain "
OBTAINED_PREFIX = "Obtained: "
FINAL_MISSION = "Mission - Destroy Model W"
VICTORY_LOCATION = "Defeat Serpent"
OMEGA_VICTORY_LOCATION = "Defeat Omega Zero"
VICTORY = "Victory"
# The Mega Man Zero bosses leave an event the hunt of the goal counts.
DEFEATED_PREFIX = "Defeated: "
# The option classes of the world's options.py the rules filter on, and where the serialized
# rules find them
PROGRESSIVE_OPTION, HU_OPTION, STORY_OPTION = "ProgressiveModels", "HuInPool", "MissionObjectives"
RUSH_OPTION, SEAL_OPTION = "SkipBossRush", "AreaMAccess"
WARPS_OPTION = "IncludeWarpsInLogic"
GOAL_OPTION = "Goal"
STORY_OFF, STORY_CHECKS, STORY_ITEMS = 0, 1, 2
SEAL_BIOMETALS = 1
GOAL_SERPENT, GOAL_OMEGA = 0, 1
# The doors of N-1 to the Mega Man Zero rooms: each opens with its game's option.
ZERO_GATES = {768: "Zero3Bosses", 769: "Zero4Bosses"}
OPTIONS_MODULE = "worlds.mmzx.options"

_COUNT_RE = re.compile(r"^([A-Z_]+)>=(\d+)$")

# Boss anchoring

# A boss's requirement comes from the player's boss_logic YAML, not from the document.
# The document only anchors where the boss is fought: a `boss` tag on its arena region,
# which the world adds to every edge landing there, or a BOSS_<ID> atom where the fight
# is not a region of its own, as with the D-4 boss rush doors. With no YAML the atom is
# free. `index` is the Pseudoroid order the game uses for victory levels and teleporters.
BOSSES = {
    # Giga Aspis is missing on purpose: the randomizer skips the tutorial.
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
    # The eight bosses of Mega Man Zero 3 and 4, in the capsule rooms of N-1; each game's
    # option brings its four in.
    "hellbat_schilt": {"name": "Hellbat Schilt", "room": "n01", "mission": None, "game": 3},
    "blazin_flizard": {"name": "Blazin' Flizard", "room": "n01", "mission": None, "game": 3},
    "deathtanz_mantisk": {"name": "Deathtanz Mantisk", "room": "n01", "mission": None, "game": 3},
    "childre_inarabitta": {"name": "Childre Inarabitta", "room": "n01", "mission": None, "game": 3},
    "fenri_lunaedge": {"name": "Fenri Lunaedge", "room": "n01", "mission": None, "game": 4},
    "noble_mandrago": {"name": "Noble Mandrago", "room": "n01", "mission": None, "game": 4},
    "sol_titanion": {"name": "Sol Titanion", "room": "n01", "mission": None, "game": 4},
    "pegasolta_eclair": {"name": "Pegasolta Eclair", "room": "n01", "mission": None, "game": 4},
}
ZERO_BOSS_OPTION = {3: "Zero3Bosses", 4: "Zero4Bosses"}
BOSS_ATOMS = {"BOSS_" + b.upper(): b for b in BOSSES}
PSEUDOROIDS = [b for b, v in sorted(BOSSES.items(), key=lambda kv: kv[1].get("index", 99))
               if "index" in v]
# The eight D-4 boss rush teleporters, by Pseudoroid index, all lead into the generic
# room z02. The exit to D-5 needs all eight, as in the game, so a boss required by
# boss_logic is required in both of its fights.
BOSS_RUSH_DOORS = {
    "d04 door (288,272)": 0, "d04 door (800,272)": 1,
    "d04 door (288,656)": 2, "d04 door (800,656)": 3,
    "d04 door (480,272)": 4, "d04 door (992,272)": 5,
    "d04 door (480,656)": 6, "d04 door (992,656)": 7,
}
BOSS_RUSH_EXIT = "d04 door (992,736)"        # the tower's exit to D-5
# Anchoring a boss only on these edges would leave its story fight unrestricted.
BOSS_RUSH_EDGES = set(BOSS_RUSH_DOORS) | {BOSS_RUSH_EXIT}


# Retired boss ids, rewritten by normalize_logic so an old tag is not orphaned.
LEGACY_BOSS_IDS = {"giga_aspis": "rayfly"}


def boss_atom(boss_id: str) -> str:
    return "BOSS_" + boss_id.upper()


def boss_regions(doc) -> dict:
    """{(room, rid): boss id} for the regions tagged as arenas."""
    out = {}
    for room, rl in (doc.get("rooms") or {}).items():
        for rid, reg in (rl.get("regions") or {}).items():
            b = reg.get("boss")
            if b:
                out[(room, rid)] = b
    return out


def bosses_anchored(doc) -> set:
    """Bosses anchored to their story fight.

    An arena tag counts; so does a BOSS_<ID> atom anywhere but on a boss rush edge.
    """
    atoms = document_atoms(doc, skip_edges=BOSS_RUSH_EDGES)
    return {BOSS_ATOMS[a] for a in atoms if a in BOSS_ATOMS} | set(boss_regions(doc).values())


def unavailable_atoms(D):
    """Atoms of items the data marks as not pooled; they are never met."""
    out = set()
    items = getattr(D, "ITEMS", {})
    for atom, item in ATOM_ITEM.items():
        v = items.get(item)
        if v is not None and not v.get("pooled", True) and atom != "HU":
            out.add(atom)
    return out


def atom_catalog(exclude=()):
    """Atom list for the editor UI: [{id, group, label}]."""
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
    out.append({"id": "GOAL", "group": "model", "label": "GOAL (the goal requirements of the YAML)"})
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
    out.append({"id": SLOW_LAVA, "group": "story",
                "label": "Lava of Area K set to slow (the control of K-1, or its item)"})
    out.append({"id": K_DOOR_SWITCH, "group": "story",
                "label": "Door of K-1 to its Sub Tank unlocked (the switch of K-4, or its item)"})
    out.append({"id": D_BRIDGE, "group": "story",
                "label": "Bridge of D-1 lowered (its switch, or its item; always with mission_objectives off)"})
    out.append({"id": LAVA_CHASE, "group": "route",
                "label": "Lava chase of K-4 armed (K-4 entered through its door from K-3)"})
    out.append({"id": AVOID_BOSS_ROOM, "group": "route",
                "label": "Reached by a way that keeps clear of this area's boss room"})
    for atom, bid in BOSS_ATOMS.items():
        b = BOSSES[bid]
        out.append({"id": atom, "group": "boss",
                    "label": "%s defeated (%s) - YAML requirement" % (b["name"], room_label(b["room"]))})
    return [a for a in out if a["id"] not in set(exclude)]


def canonical_atom(tok: str):
    """Normalized atom, or None if it does not exist."""
    t = tok.strip().upper().replace(" ", "")
    if (t in ATOM_ITEM or t in MISSION_EVENT or t in MACRO_ATOMS
            or t in FULL_MODEL_ATOMS or t in BOSS_ATOMS or t in STORY_ATOMS or t in ROUTE_ATOMS):
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


# DNF: a list of alternatives, each a list of atoms

def dnf_normalize(dnf):
    """Drops duplicate atoms and alternatives, and any alternative that contains another."""
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
    """Parses a text requirement into a DNF; ValueError on bad syntax or an unknown atom."""
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
    """Renders a DNF as text: 'free', 'never', or alternatives joined by '|'."""
    if not dnf:
        return "never"
    if any(len(alt) == 0 for alt in dnf):
        return "free"
    return " | ".join(" & ".join(alt) for alt in dnf)


# REQ: {tier: DNF}

def req_free():
    return {"normal": [[]]}


def req_from_expr(expr, tier="normal"):
    return {tier: parse_expr(expr)}


def req_alternatives(req, tier="expert"):
    """Effective DNF at tier, tiers being cumulative; None means free."""
    if req is None:
        return DNF_TRUE
    alts = []
    for t in TIERS[:TIERS.index(tier) + 1]:
        alts.extend(req.get(t) or [])
    return dnf_normalize(alts)


def req_is_free(req, tier="normal"):
    return any(len(a) == 0 for a in req_alternatives(req, tier))


def req_is_never(req, tier="expert"):
    """Whether the requirement has no alternative at tier."""
    return len(req_alternatives(req, tier)) == 0


def req_atoms(req):
    out = set()
    for t in TIERS:
        for alt in (req or {}).get(t) or []:
            out.update(alt)
    return out


def document_atoms(doc, skip_edges=()):
    """All atoms used in the document, ignoring the edges named in skip_edges."""
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
    """Useful items that these atoms turn into progression.

    Archipelago only tracks progression items in its state, so anything a rule needs must be one.
    """
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
    return progression_items(document_atoms(doc))


# Intermediate representation (IR) of the rules

# A requirement becomes a tree of plain tuples, (kind, ...), that the compiler to Archipelago rules
# and the exporters of the generated files all consume, so what is read is what is evaluated.
# The node kinds are the cases of ir_to_dict; the named constants expand through MACRO_IR.
IR_TRUE, IR_FALSE = ("true",), ("false",)


def _has_if(item, option, value, count=1, op="eq"):
    """An item held, which counts for nothing unless the option filter holds (an alternative of an OR)."""
    return ("has_if", item, count, option, value, op)


def _needs_if(item, option, value, count=1, op="eq"):
    """An item held, asked for only while the option filter holds (a condition of an AND)."""
    return ("needs_if", item, count, option, value, op)


def _model_ir(half, count=1):
    """A biometal with halves: `count` progressive halves, or the single full item without progressive models."""
    return ("or", (_has_if(half, PROGRESSIVE_OPTION, 1, count), _has_if(FULL_MODEL_ITEMS[half], PROGRESSIVE_OPTION, 0)))


MACRO_IR = {
    "HU": ("or", (_has_if(ATOM_ITEM["HU"], HU_OPTION, 1), ("option_true", HU_OPTION, 0, "eq"))),
}
for _m in ("HX", "FX", "LX", "PX"):
    MACRO_IR[_m] = _model_ir(ATOM_ITEM[_m])
for _m, _half in FULL_MODEL_ATOMS.items():
    MACRO_IR[_m] = _model_ir(_half, 2)
MACRO_IR["MODEL"] = ("or", (("has_any", tuple(ATOM_ITEM[m] for m in ("X", "ZX", "OX"))),
                            *(("macro", m) for m in ("HX", "FX", "LX", "PX"))))
MACRO_IR["ALL6"] = ("and", (("has", ATOM_ITEM["X"], 1), ("has", ATOM_ITEM["ZX"], 1),
                            *(("macro", m) for m in ("HX", "FX", "LX", "PX"))))
MACRO_IR["GOAL"] = ("goal",)
MACRO_IR["LAVA_ITEM"] = _has_if(STORY_ATOMS[SLOW_LAVA], STORY_OPTION, STORY_ITEMS)
MACRO_IR[SLOW_LAVA] = ("or", (("macro", "LAVA_ITEM"), _has_if(LAVA_EVENT, STORY_OPTION, STORY_ITEMS, op="ne")))
MACRO_IR[K_DOOR_SWITCH] = ("or", (_has_if(STORY_ATOMS[K_DOOR_SWITCH], STORY_OPTION, STORY_ITEMS),
                                  _has_if(SWITCH_EVENT, STORY_OPTION, STORY_ITEMS, op="ne")))
MACRO_IR[D_BRIDGE] = ("or", (_has_if(STORY_ATOMS[D_BRIDGE], STORY_OPTION, STORY_ITEMS),
                             _has_if(BRIDGE_EVENT, STORY_OPTION, STORY_CHECKS),
                             ("option_true", STORY_OPTION, STORY_OFF, "eq")))
MACRO_IR["SEAL"] = ("seal",)


def ir_and(nodes):
    """AND of IR nodes, flattened: a false child wins, true children and repeats drop out."""
    out = []
    for n in nodes:
        if n[0] == "false":
            return IR_FALSE
        for c in (n[1] if n[0] == "and" else (n,)):
            if c[0] != "true" and c not in out:
                out.append(c)
    if not out:
        return IR_TRUE
    return out[0] if len(out) == 1 else ("and", tuple(out))


def ir_or(nodes):
    """OR of IR nodes, flattened: a true child wins, false children and repeats drop out."""
    out = []
    for n in nodes:
        if n[0] == "true":
            return IR_TRUE
        for c in (n[1] if n[0] == "or" else (n,)):
            if c[0] != "false" and c not in out:
                out.append(c)
    if not out:
        return IR_FALSE
    return out[0] if len(out) == 1 else ("or", tuple(out))


def atom_ir(atom, site=None):
    """IR of one atom; `site` is where the rule is asked ({"at": region} plus rule_context), which the
    slow lava and the route atoms depend on."""
    site = site or {}
    if atom == SLOW_LAVA and site.get("at"):
        return ("or", (("macro", "LAVA_ITEM"), ("lava", site["at"], site["control"])))
    if atom == LAVA_CHASE:
        return ("reach_entrance", LAVA_CHASE_DOOR, site.get("chase") or "")
    if atom == AVOID_BOSS_ROOM:
        at = site.get("at")
        if not at:
            raise ValueError("%s needs a place: a connection or a placed check" % AVOID_BOSS_ROOM)
        arenas = (site.get("arenas") or {}).get(area_of(at))
        if not arenas:
            raise ValueError("%s: no boss room drawn in area %s" % (AVOID_BOSS_ROOM, area_of(at).upper()))
        return ("avoiding", at, tuple(arenas))
    if atom in MACRO_IR:
        return ("macro", atom)
    if atom in BOSS_ATOMS:
        return ("boss", BOSS_ATOMS[atom])
    if atom in ATOM_ITEM:
        return ("has", ATOM_ITEM[atom], 1)
    if atom in MISSION_EVENT:
        return ("has", MISSION_EVENT[atom], 1)
    m = _COUNT_RE.match(atom)
    if m and m.group(1) in COUNT_ATOMS:
        return ("has", COUNT_ATOMS[m.group(1)][0], int(m.group(2)))
    if m and m.group(1) in LIST_COUNT_ATOMS:
        return ("has_from_list", tuple(LIST_COUNT_ATOMS[m.group(1)][0]), int(m.group(2)))
    raise ValueError("unknown atom %r" % atom)


def req_ir(req, tier, site=None):
    """IR of a requirement at tier: the OR of its alternatives, each the AND of its atoms."""
    return ir_or([ir_and([atom_ir(a, site) for a in alt]) for alt in req_alternatives(req, tier)])


def gate_table(doc, tier) -> dict:
    """{flag: IR} of the event gates the document gives a requirement; the others are open."""
    return {int(flag): req_ir(g["req"], tier) for flag, g in doc.get("gates", {}).items() if g.get("req") is not None}


def ir_expand_gates(ir, table):
    """The IR with every gate replaced by its expansion from table."""
    if ir[0] == "gate":
        return table[ir[1]]
    if ir[0] == "and":
        return ir_and([ir_expand_gates(c, table) for c in ir[1]])
    if ir[0] == "or":
        return ir_or([ir_expand_gates(c, table) for c in ir[1]])
    return ir


def ir_prune(ir, present):
    """The IR with every region outside `present` unreachable: the world leaves out the regions
    nothing leads to."""
    if ir[0] == "reach":
        return ir if ir[1] in present else IR_FALSE
    if ir[0] == "reach_entrance":
        return ir if not ir[2] or ir[2] in present else IR_FALSE
    if ir[0] == "avoiding":
        return ir if ir[1] in present else IR_FALSE
    if ir[0] == "and":
        return ir_and([ir_prune(c, present) for c in ir[1]])
    if ir[0] == "or":
        return ir_or([ir_prune(c, present) for c in ir[1]])
    return ir


def ir_regions(ir) -> set:
    """Regions the IR asks to reach, through its macros."""
    if ir[0] == "reach":
        return {ir[1]}
    if ir[0] == "reach_entrance":
        return {ir[2]} if ir[2] else set()
    if ir[0] == "avoiding":
        return {ir[1], *ir[2]}
    if ir[0] in ("and", "or"):
        return set().union(*(ir_regions(c) for c in ir[1]))
    if ir[0] == "macro":
        return ir_regions(MACRO_IR[ir[1]])
    return set()


# Geometry

def point_in_poly(pt, poly) -> bool:
    """Ray-casting point-in-polygon test."""
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
    """Shoelace area of a polygon."""
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
    """Region id of the smallest polygon containing pt; 'main' if none."""
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


# World data

def room_label(code: str) -> str:
    """Display label of a room code: a01 is A-1, z01 is Hub, z02 is Hub-2."""
    m = re.match(r"^([a-z])(\d{2})$", code)
    if not m:
        return code
    letter, num = m.group(1), int(m.group(2))
    if letter == "z":
        return "Hub" if num == 1 else "Hub-%d" % num
    return "%s-%d" % (letter.upper(), num)


def build_world(D, sites=None):
    """Neutral view of data.py for this module: rooms, labels, locations, edges, hub, the start,
    the seal, the story objects and the door constraint sites (door_data.SITES)."""
    edges = list(D.DOORS)
    rooms = sorted({e["src"] for e in edges} | {e["dst"] for e in edges})
    locs = {}
    for name, v in D.LOCATIONS.items():
        locs[name] = {"category": v.get("category"), "room": v.get("room"),
                      "pos": list(v["pos"]) if v.get("pos") else None,
                      "detect": v.get("detect") is not None, "boss": v.get("boss")}
    starts = list(dict.fromkeys(rec["room"] for rec in getattr(D, "STARTING_TRANSERVERS", {}).values()))
    if len(starts) > 1:
        raise ValueError("the starting points are in several rooms (%s); the logic expects one" % ", ".join(starts))
    return {
        "rooms": rooms,
        "room_label": {r: room_label(r) for r in rooms},
        "locations": locs,
        "edges": edges,
        "hub": D.HUB_ROOM,
        "start_room": starts[0] if starts else D.HUB_ROOM,
        "transerver_access": dict(D.TRANSERVER_ACCESS),
        "transerver_always": list(D.TRANSERVER_ALWAYS),
        "event_gates_open": list(getattr(D, "EVENT_GATES_OPEN", [])),
        "event_gates_goal": list(getattr(D, "EVENT_GATES_GOAL", [])),
        "hub_floor_y": dict(getattr(D, "HUB_FLOOR_Y", {})),
        "seal_rooms": list(getattr(D, "SEAL_ROOMS", [])),
        "site_doors": sorted(door for site in (sites or {}).values() for door in site["doors"]),
        "story": {
            "report_items": dict(getattr(D, "STORY_REPORT_ITEMS", {})),
            "gate_items": {int(flag): item for flag, item in getattr(D, "STORY_GATE_ITEMS", {}).items()},
            "lava_location": getattr(D, "STORY_LAVA_LOCATION", None),
            "switch_location": getattr(D, "STORY_SWITCH_LOCATION", None),
            "bridge_location": getattr(D, "STORY_BRIDGE_LOCATION", None),
            "chains": [list(chain) for chain in getattr(D, "STORY_CHAINS", [])],
            "counts": {name: (int(count), list(group)) for name, (count, group) in getattr(D, "STORY_COUNTS", {}).items()},
            "warps": dict(getattr(D, "MISSION_WARPS", {})),
        },
    }


# Logic document

def empty_room():
    """A room with only its main region."""
    return {"req": None, "note": "",
            "regions": {"main": {"name": "Main", "poly": None, "color": "#8ab4f8", "note": ""}},
            "conns": [], "members": {}}


def empty_logic(world=None):
    """An empty document, with an entry for every room of world."""
    doc = {"format": FORMAT_VERSION, "tiers": list(TIERS), "rooms": {}, "placed": {},
           "edges": {}, "checks": {}, "gates": {}}
    for r in (world or {}).get("rooms", []):
        doc["rooms"][r] = empty_room()
    return doc


# Edge names the data no longer uses; normalize_logic rewrites them in old documents.
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
    """Fills in missing keys and rewrites retired edge names and boss ids, in place."""
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
    """Loads and normalizes a document; a missing file yields an empty one."""
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
    """Archipelago region name: the room code for main, room/rid otherwise."""
    return room if rid == "main" else "%s/%s" % (room, rid)


def edge_endpoints(world, doc, edge):
    """(exit pos, landing pos) of an edge; hand-placed positions win over the data's."""
    ov = doc.get("edges", {}).get(edge["name"], {})
    pos = ov.get("pos") or edge.get("pos")
    dst_pos = ov.get("dst_pos") or edge.get("dst_pos")
    if dst_pos and dst_pos[0] is None:
        dst_pos = None
    return pos, dst_pos


def check_placements(world, doc, name):
    """[(room, pos)] where a location counts: its data position, or its hand placements."""
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
    """(room, pos) of a location's first placement, or (None, None)."""
    pl = check_placements(world, doc, name)
    return pl[0] if pl else (None, None)


def resolve_members(world, doc):
    """{room: {node: rid}} for checks, exits and '<edge>@in' landings, honoring members."""
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
    """[(from, to, kind, ref)] inside a room: connections and internal doors that change region."""
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
    """Regions through which the room is entered from outside; start_room is one room or several."""
    entries = set()
    for e in world["edges"]:
        if e["dst"] == room and e["src"] != room and e["kind"] not in NON_TRANSITION_KINDS:
            entries.add(members[room].get(e["name"] + "@in", "main"))
    starts = {start_room} if isinstance(start_room, str) else set(start_room or ())
    if room in starts or room == world["hub"]:
        entries.add("main")
    return entries


def local_reachability(world, doc, room, members, tier="expert", start_room=None):
    """Regions reachable inside the room by topology alone, ignoring requirements."""
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


# Validation

def validate(world, doc, start_room=None, unavailable=()):
    """Validates the document against the world; returns {errors, warnings, unsure, unplaced}.

    unavailable: atoms whose item is not in the pool; a rule that uses one gets a warning.
    """
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
    for mission, room in sorted(world["story"]["warps"].items()):
        location = MISSION_PREFIX + mission
        if location not in world["locations"] or room not in rooms:
            errors.append("mission warps: unknown mission %r or room %r" % (mission, room))
        elif check_position(world, doc, location)[0] is None:
            warnings.append("%s is not placed: its teleport to %s is left out of the logic" % (location, room_label(room)))
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
                    # an empty unconnected main is a pattern, not a mistake
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
    """Warnings for regions with no way out, isolated regions and unconnected main nodes."""
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
        # only doors to other rooms and no way into the rest of the room: an isolated vestibule,
        # unless it joins two or more other rooms (a passage the room itself never needs to reach)
        if rid != "main" and len(regs) > 1 and nodes and not conn_in[rid] and not conn_out[rid]:
            internal_link = any(
                (n in edges and edges[n]["src"] == edges[n]["dst"] and members[room].get(n + "@in", "main") != rid)
                or (n.endswith("@in") and edges[n[:-3]]["src"] == room and members[room].get(n[:-3], "main") != rid)
                for n in nodes)
            other_rooms = {edges[n[:-3]]["src"] for n in ins} | {edges[n]["dst"] for n in outs}
            if not internal_link and (ins or outs) and len(other_rooms - {room}) < 2:
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


# The rules of the world: entrances and locations

# Logic level the world ships. The document also carries expert alternatives (tricks, tight
# jumps); they are not offered as an option yet.
TIER = "normal"
MENU, FIELD = "Menu", "Field"
START_ENTRANCE = "Start"
FIELD_ACCESS = "Field access"


def area_of(region_name: str) -> str:
    """Area letter of a region: the rooms are named after their area, k04 being K-4."""
    return region_name[0]


def label_room_groups(label, rooms) -> list:
    """Room groups of an area label: OR between groups, AND inside each group."""
    groups = []
    for part in str(label).split("/"):
        pairs = re.findall(r"([A-Za-z])-?(\d+)", part)
        if pairs:
            g = ["%s%02d" % (letter.lower(), int(num)) for letter, num in pairs]
        else:  # bare letter: every room of the area
            letter = part.strip()[:1].lower()
            g = [r for r in rooms if r.startswith(letter)]
        g = [r for r in g if r in rooms]
        if g:
            groups.append(g)
    return groups


def location_events(world) -> dict:
    """{anchor location: [(event location, event item, extra IR)]}: the events placed and ruled
    like their anchor, each with what it adds. Missions leave a Cleared event, biometal checks an
    Obtained one the seal counts, story switches stand in for their item while no option gives one,
    the Mega Man Zero bosses a Defeated one the hunt counts, and the final mission holds the Victory
    behind the goal requirements while Serpent is the goal."""
    out = {}
    for name, v in world["locations"].items():
        if v.get("category") == "mission":
            event = CLEARED_PREFIX + name[len(MISSION_PREFIX):]
            out.setdefault(name, []).append((event, event, IR_TRUE))
        elif v.get("category") == "biometal":
            event = OBTAINED_PREFIX + name[len(BIOMETAL_PREFIX):]
            out.setdefault(name, []).append((event, event, ("option_true", SEAL_OPTION, SEAL_BIOMETALS, "eq")))
        elif v.get("boss") in BOSSES and BOSSES[v["boss"]].get("game"):
            event = DEFEATED_PREFIX + BOSSES[v["boss"]]["name"]
            out.setdefault(name, []).append((event, event, ("option_true", ZERO_BOSS_OPTION[BOSSES[v["boss"]]["game"]], 1, "eq")))
    story = world["story"]
    no_item = ("option_true", STORY_OPTION, STORY_ITEMS, "ne")
    for atom, location, guard in ((SLOW_LAVA, story["lava_location"], no_item),
                                  (K_DOOR_SWITCH, story["switch_location"], no_item),
                                  (D_BRIDGE, story["bridge_location"], ("option_true", STORY_OPTION, STORY_CHECKS, "eq"))):
        if location in world["locations"]:
            out.setdefault(location, []).append((STORY_EVENT[atom], STORY_EVENT[atom], guard))
    out.setdefault(FINAL_MISSION, []).append((VICTORY_LOCATION, VICTORY, ir_and([("macro", "GOAL"), ("option_true", GOAL_OPTION, GOAL_SERPENT, "eq")])))
    return out


def region_events(doc) -> dict:
    """{region: [(event location, event item, IR)]}: the events that sit in a region rather than
    on a location. Omega Zero's arena holds the Victory event while he is the goal."""
    out = {}
    for (room, rid), bid in boss_regions(doc).items():
        if bid == "omega_zero":
            out.setdefault(region_name(room, rid), []).append(
                (OMEGA_VICTORY_LOCATION, VICTORY, ("option_true", GOAL_OPTION, GOAL_OMEGA, "eq")))
    return out


def omega_goal_ir() -> tuple:
    """What entering Omega Zero's arena asks for on top of his boss requirement: the goal
    requirements while he is the goal."""
    return ("or", (("option_true", GOAL_OPTION, GOAL_OMEGA, "ne"), ("macro", "GOAL")))


def _arena_ir(boss_of, room, rid):
    bid = boss_of.get((room, rid))
    if bid == "omega_zero":
        return ir_and([("boss", bid), omega_goal_ir()])
    return ("boss", bid) if bid else IR_TRUE


def transerver_ir(world, edge) -> tuple:
    """IR of a warp leaving the hub: the Transerver Access item of the destination's floor; a
    floor with no Transport destination is never warped to. Any other edge is free here."""
    if edge["kind"] != "warp" or edge["src"] != world["hub"]:
        return IR_TRUE
    if edge["dst"] in world["transerver_always"]:
        return IR_TRUE
    item = world["transerver_access"].get(edge["dst"])
    return ("has", item, 1) if item else IR_FALSE


def mission_warps(world, doc, members) -> list:
    """[(entrance name, mission, source region, landing region)] of the teleports to the Guardian
    Base that end a mission: from the region its check is placed in to the main region of the room
    it lands in. A mission that is not placed has no warp; the validator says so."""
    out = []
    for mission, room in sorted(world["story"]["warps"].items()):
        location = MISSION_PREFIX + mission
        placed = check_placements(world, doc, location)
        if location not in world["locations"] or room not in doc["rooms"] or not placed:
            continue
        src_room = placed[0][0]
        src = region_name(src_room, members[src_room].get(location, "main"))
        out.append(("%s warp after %s" % (src_room, mission), mission, src, region_name(room, "main")))
    return out


def warp_ir(mission) -> tuple:
    """IR of a mission's teleport: only with include_warps_in_logic, once the mission can be cleared."""
    return ir_and([("option_true", WARPS_OPTION, 1, "eq"), ("has", CLEARED_PREFIX + mission, 1)])


def rule_context(world, doc, members) -> dict:
    """What the slow lava and the route atoms resolve against: the region of the lava control, the region
    the K-3 door into K-4 leaves from, and the arena regions of each area."""
    arenas = {}
    for (room, rid), _boss in sorted(boss_regions(doc).items()):
        arenas.setdefault(room[0], []).append(region_name(room, rid))
    chase = None
    if any(e["name"] == LAVA_CHASE_DOOR for e in world["edges"]):
        room = LAVA_CHASE_DOOR.split(" ")[0]
        chase = region_name(room, members.get(room, {}).get(LAVA_CHASE_DOOR, "main"))
    return {"control": lava_control_region(world, doc, members), "chase": chase, "arenas": arenas}


def lava_control_region(world, doc, members):
    """The region of the lava control of Area K, or None while the data has no such location."""
    placed = check_placements(world, doc, world["story"]["lava_location"])
    if not placed:
        return None
    room = placed[0][0]
    return region_name(room, members[room].get(world["story"]["lava_location"], "main"))


def entrance_rules(world, doc, members, tier, faults=None, context=None) -> list:
    """[(name, source region, destination region, IR)] of every entrance: the start, the drawn connections, the
    edges and the mission warps.

    An edge ANDs its key, the destination room's entry requirement, its extra cost, the Transerver rule, its
    event gate (and that gate's item or option), the landing arena's boss and the seal of Area M. What the
    document makes impossible is left out; a rule that cannot be built reads as never, its error in `faults`.
    """
    gates = gate_table(doc, tier)
    boss_of = boss_regions(doc)
    edge_ov, story = doc.get("edges", {}), world["story"]
    seal_rooms, site_doors = set(world["seal_rooms"]), set(world["site_doors"])
    start_room = world["start_room"]
    context = context if context is not None else rule_context(world, doc, members)

    def guarded(name, build):
        try:
            return build()
        except (ValueError, KeyError, TypeError) as e:
            if faults is None:
                raise
            faults[name] = str(e)
            return IR_FALSE

    def site(at):
        return {"at": at, **context}

    def key_ir(d):
        if d["name"] in site_doors:
            return ("door_key", d["name"])
        return ("has", d["key"], 1) if d.get("key") else IR_TRUE

    def door_ir(d, src, dst_rid):
        gate = d.get("gate")
        cost = req_ir(edge_ov.get(d["name"], {}).get("req"), tier, site(src))
        if d["name"] == BOSS_RUSH_EXIT:
            cost = ir_or([cost, ("option_true", RUSH_OPTION, 1, "eq")])
        return ir_and([key_ir(d),
                       req_ir(doc["rooms"][d["dst"]].get("req"), tier, site(src)) if d["src"] != d["dst"] else IR_TRUE,
                       cost,
                       transerver_ir(world, d),
                       ("gate", gate) if gate in gates else IR_TRUE,
                       _needs_if(story["gate_items"][gate], STORY_OPTION, STORY_ITEMS) if gate in story["gate_items"] else IR_TRUE,
                       # the gate of the final area opens only while Serpent is the goal
                       ("option_true", GOAL_OPTION, GOAL_SERPENT, "eq") if gate in world["event_gates_goal"] else IR_TRUE,
                       ("option_true", ZERO_GATES[gate], 1, "eq") if gate in ZERO_GATES else IR_TRUE,
                       _arena_ir(boss_of, d["dst"], dst_rid),
                       ("macro", "SEAL") if d["dst"] in seal_rooms and d["src"] not in seal_rooms else IR_TRUE,
                       ("option_true", RUSH_OPTION, 0, "eq") if d["name"] in BOSS_RUSH_DOORS else IR_TRUE])

    start = region_name(start_room, "main")
    out = [(START_ENTRANCE, MENU, start, guarded(START_ENTRANCE, lambda: ir_and(
        [req_ir(doc["rooms"][start_room].get("req"), tier, site(start)), _arena_ir(boss_of, start_room, "main")])))]
    for room, rl in doc["rooms"].items():
        for c in rl.get("conns", []):
            name, src = connection_name(room, c), region_name(room, c["from"])
            ir = guarded(name, lambda: ir_and([req_ir(c.get("req"), tier, site(src)), _arena_ir(boss_of, room, c["to"])]))
            if ir != IR_FALSE or name in (faults or {}):
                out.append((name, src, region_name(room, c["to"]), ir))
        for d in world["edges"]:
            if d["src"] != room or d["kind"] in NON_TRANSITION_KINDS:
                continue
            src_rid = members[d["src"]].get(d["name"], "main")
            dst_rid = members[d["dst"]].get(d["name"] + "@in", "main")
            if d["src"] == d["dst"] and src_rid == dst_rid:
                continue                   # a door within one region
            src = region_name(d["src"], src_rid)
            ir = guarded(d["name"], lambda: door_ir(d, src, dst_rid))
            if ir != IR_FALSE or d["name"] in (faults or {}):
                out.append((d["name"], src, region_name(d["dst"], dst_rid), ir))
    for name, mission, src, dst in mission_warps(world, doc, members):
        out.append((name, src, dst, warp_ir(mission)))
    return out


def connection_name(room, conn) -> str:
    return "%s: %s -> %s" % (room, conn["from"], conn["to"])


def room_regions(room, needed) -> list:
    """The regions of a room the start can lead to: its main region alone when it is one of them."""
    names = sorted(n for n in needed if n == room or n.startswith(room + "/"))
    return [room] if room in names else names


def location_place(world, doc, members, needed, name) -> tuple:
    """(parent region, IR of getting there) of a location.

    One placement: the region of its point. Several: Field, reaching any of them. None: Field with
    the area label of the data, a room being reached through its main region or, when it has been
    carved up, any of its regions.
    """
    placed = [region_name(room, members[room].get(name, "main")) for room, _ in check_placements(world, doc, name)]
    if len(placed) == 1:
        return placed[0], IR_TRUE
    if placed:
        return FIELD, ir_or([("reach", r) for r in placed])
    groups = label_room_groups(world["locations"][name].get("room"), world["rooms"])
    base = ir_or([ir_and([ir_or([("reach", r) for r in room_regions(room, needed)]) for room in group])
                  for group in groups]) if groups else IR_TRUE
    return FIELD, base


def location_rule(world, doc, members, needed, name, tier, faults=None, context=None) -> tuple:
    """(parent region, IR) of a location: its place, the check requirement of the document, the
    object a mission's Report asks for, and the story locations the game hands out in order or
    after some others. A requirement that cannot be built reads as never and its error goes into
    `faults`.
    """
    parent, base = location_place(world, doc, members, needed, name)
    context = context if context is not None else rule_context(world, doc, members)
    site = {"at": None if parent == FIELD else parent, **context}
    story = world["story"]
    extras = []
    if name.startswith(MISSION_PREFIX) and story["report_items"].get(name[len(MISSION_PREFIX):]):
        extras.append(_needs_if(story["report_items"][name[len(MISSION_PREFIX):]], STORY_OPTION, STORY_ITEMS))
    for chain in story["chains"]:
        extras.extend(("reach_location", earlier, location_place(world, doc, members, needed, earlier)[0])
                      for earlier, later in zip(chain, chain[1:]) if later == name)
    if name in story["counts"]:
        count, group = story["counts"][name]
        extras.append(("reached_at_least", count, tuple(group)))
    try:
        req = req_ir(doc.get("checks", {}).get(name, {}).get("req"), tier, site)
    except (ValueError, KeyError, TypeError) as e:
        if faults is None:
            raise
        faults[name], req = str(e), IR_FALSE
    return parent, ir_and([base, req, *extras])


def global_reachability(world, doc, members, tier="expert"):
    """Regions a new game can ever lead to: connections and room edges whose requirement is not
    never and the warps of the hub with a Transerver Access item. What the world prunes."""
    links = {}
    for room, rl in doc["rooms"].items():
        for c in rl.get("conns", []):
            if not req_is_never(c.get("req"), tier):
                links.setdefault(region_name(room, c["from"]), set()).add(region_name(room, c["to"]))
    edge_ov, gates = doc.get("edges", {}), doc.get("gates", {})
    for d in world["edges"]:
        if d["kind"] in NON_TRANSITION_KINDS:
            continue
        src_rid = members[d["src"]].get(d["name"], "main")
        dst_rid = members[d["dst"]].get(d["name"] + "@in", "main")
        if d["src"] == d["dst"] and src_rid == dst_rid:
            continue
        if transerver_ir(world, d) == IR_FALSE:
            continue
        reqs = (edge_ov.get(d["name"], {}).get("req"),
                gates.get(str(d["gate"]), {}).get("req") if d.get("gate") is not None else None,
                doc["rooms"][d["dst"]].get("req") if d["src"] != d["dst"] else None)
        if any(req is not None and req_is_never(req, tier) for req in reqs):
            continue
        links.setdefault(region_name(d["src"], src_rid), set()).add(region_name(d["dst"], dst_rid))
    for _name, _mission, src, dst in mission_warps(world, doc, members):
        links.setdefault(src, set()).add(dst)
    seen, frontier = set(), [region_name(world["start_room"], "main")]
    while frontier:
        name = frontier.pop()
        if name not in seen:
            seen.add(name)
            frontier.extend(links.get(name, ()))
    return seen


# Generated files: logic/rules.py (the module the world imports) and logic/rules.json (for trackers)

GAME = "Mega Man ZX"
GENERATED_HEADER = (
    "The access logic of Mega Man ZX: the region graph and the rule of every entrance, location and event,\n"
    "room by room, in the syntax of the Archipelago Rule Builder. Generated from logic/logic.json, drawn in the\n"
    "editor under tools/logic_editor/. Do not edit this file by hand: change the logic in the editor, which\n"
    "rewrites it on every save, or run tools/check_logic.py; the tests fail when it falls behind the document.")
JSON_NOTICE = ("Generated from logic/logic.json by the logic editor or tools/check_logic.py: the rules of "
               "logic/rules.py serialized as the Archipelago Rule Builder does (Rule.to_dict). Do not edit by hand; "
               "the tests fail when it falls behind the document.")
EDGE_WORDS = {"door": "door", "internal": "internal", "warp": "warp", "curated": "path", "save": "pad"}
# The rule classes of the Rule Builder and of logic/builder.py the generated module may import, in import order
RULE_CLASSES = ("CanReachEntrance", "CanReachLocation", "CanReachRegion", "False_", "Has", "HasAny", "HasFromList",
                "True_")
BUILDER_CLASSES = ("BossRequirement", "DoorKey", "GoalRequirement", "LavaCarriedTo", "ReachableAvoiding", "ReachedAtLeast",
                   "SealRequirement")
MACRO_NOTES = {
    "HU": "the human form: an item with hu_in_pool, always at hand without it",
    "HX": "one half of the biometal, or the whole item without progressive models",
    "FX": "one half of the biometal, or the whole item without progressive models",
    "LX": "one half of the biometal, or the whole item without progressive models",
    "PX": "one half of the biometal, or the whole item without progressive models",
    "HX2": "both halves, the level 2 charge, or the whole item without progressive models",
    "FX2": "both halves, the level 2 charge, or the whole item without progressive models",
    "LX2": "both halves, the level 2 charge, or the whole item without progressive models",
    "PX2": "both halves, the level 2 charge, or the whole item without progressive models",
    "MODEL": "any model but the human form",
    "ALL6": "the six main biometals",
    "GOAL": "the goal requirements of the YAML, resolved per player",
    "LAVA_ITEM": "the item that slows the lava of Area K, with mission_objectives: locations_and_items",
    SLOW_LAVA: "the slow lava asked at no place in particular: its item, or the event of its control",
    K_DOOR_SWITCH: "the door of K-1 to its Sub Tank: its item, or the event of the switch of K-4",
    D_BRIDGE: "the bridge of D-1: its item, the event of its switch with checks, down from the start when off",
    "SEAL": "the seal of Area M: what area_m_access asks for, resolved per player",
}
WIDTH = 120


def _option_dict(option, value, operator="eq") -> dict:
    return {"option": "%s.%s" % (OPTIONS_MODULE, option), "value": value, "operator": operator}


def _rule_dict(name, args=None, options=(), filtered=False, children=None) -> dict:
    out = {"rule": name, "options": list(options), "filtered_resolution": filtered}
    if children is None:
        out["args"] = args or {}
    else:
        out["children"] = children
    return out


def ir_to_dict(ir, gates=None) -> dict:
    """The IR as the Rule Builder serializes the rule it compiles to (Rule.to_dict), gates and
    macros expanded."""
    kind = ir[0]
    if kind == "true":
        return _rule_dict("True_")
    if kind == "false":
        return _rule_dict("False_")
    if kind in ("and", "or"):
        return _rule_dict("And" if kind == "and" else "Or", children=[ir_to_dict(c, gates) for c in ir[1]])
    if kind == "has":
        return _rule_dict("Has", {"item_name": ir[1], "count": ir[2]})
    if kind in ("has_if", "needs_if"):
        return _rule_dict("Has", {"item_name": ir[1], "count": ir[2]}, [_option_dict(ir[3], ir[4], ir[5])],
                          filtered=kind == "needs_if")
    if kind == "has_any":
        return _rule_dict("HasAny", {"item_names": sorted(set(ir[1]))})
    if kind == "has_from_list":
        return _rule_dict("HasFromList", {"item_names": sorted(set(ir[1])), "count": ir[2]})
    if kind == "reach":
        return _rule_dict("CanReachRegion", {"region_name": ir[1]})
    if kind == "reach_location":
        return _rule_dict("CanReachLocation", {"location_name": ir[1], "parent_region_name": ir[2],
                                               "skip_indirect_connection": False})
    if kind == "reach_entrance":
        return _rule_dict("CanReachEntrance", {"entrance_name": ir[1], "parent_region_name": ir[2]})
    if kind == "avoiding":
        return _rule_dict("ReachableAvoiding", {"region": ir[1], "avoid": list(ir[2])})
    if kind == "reached_at_least":
        return _rule_dict("ReachedAtLeast", {"count": ir[1], "locations": list(ir[2])})
    if kind == "option_true":
        return _rule_dict("True_", options=[_option_dict(ir[1], ir[2], ir[3])])
    if kind == "goal":
        return _rule_dict("GoalRequirement")
    if kind == "seal":
        return _rule_dict("SealRequirement")
    if kind == "boss":
        return _rule_dict("BossRequirement", {"boss_id": ir[1]})
    if kind == "door_key":
        return _rule_dict("DoorKey", {"door": ir[1]})
    if kind == "lava":
        return _rule_dict("LavaCarriedTo", {"region": ir[1], "control": ir[2]},
                          [_option_dict(STORY_OPTION, STORY_ITEMS, "ne")])
    if kind == "gate":
        return ir_to_dict(gates[ir[1]], gates)
    if kind == "macro":
        return ir_to_dict(MACRO_IR[ir[1]], gates)
    raise ValueError("unknown IR node %r" % (ir,))


def _py_str(s) -> str:
    """A Python string literal, double-quoted."""
    return json.dumps(s, ensure_ascii=False)


def _filter(option, value, operator="eq") -> str:
    tail = "" if operator == "eq" else ', operator="%s"' % operator
    return "options=[OptionFilter(%s, %r%s)]" % (option, value, tail)


def _leaf(ir) -> str:
    """A leaf of the IR as a Rule Builder expression; macros and gates by their name."""
    kind = ir[0]
    if kind == "true":
        return "True_()"
    if kind == "false":
        return "False_()"
    if kind == "has":
        return "Has(%s)" % _py_str(ir[1]) if ir[2] == 1 else "Has(%s, %d)" % (_py_str(ir[1]), ir[2])
    if kind in ("has_if", "needs_if"):
        count = "" if ir[2] == 1 else ", %d" % ir[2]
        lifted = ", filtered_resolution=True" if kind == "needs_if" else ""
        return "Has(%s%s, %s%s)" % (_py_str(ir[1]), count, _filter(ir[3], ir[4], ir[5]), lifted)
    if kind == "reach":
        return "CanReachRegion(%s)" % _py_str(ir[1])
    if kind == "reach_location":
        return "CanReachLocation(%s, %s)" % (_py_str(ir[1]), _py_str(ir[2]))
    if kind == "reach_entrance":
        return "CanReachEntrance(%s, %s)" % (_py_str(ir[1]), _py_str(ir[2]))
    if kind == "avoiding":
        return "ReachableAvoiding(%s, (%s,))" % (_py_str(ir[1]), ", ".join(_py_str(r) for r in ir[2]))
    if kind == "option_true":
        return "True_(%s)" % _filter(ir[1], ir[2], ir[3])
    if kind == "goal":
        return "GoalRequirement()"
    if kind == "seal":
        return "SealRequirement()"
    if kind == "boss":
        return "BossRequirement(%s)" % _py_str(ir[1])
    if kind == "door_key":
        return "DoorKey(%s)" % _py_str(ir[1])
    if kind == "lava":
        return "LavaCarriedTo(%s, %s, %s)" % (_py_str(ir[1]), _py_str(ir[2]), _filter(STORY_OPTION, STORY_ITEMS, "ne"))
    if kind == "gate":
        return "GATE_%d" % ir[1]
    if kind == "macro":
        return ir[1]
    raise ValueError("unknown IR node %r" % (ir,))


def _chunks(ir, depth=0) -> list:
    """The expression of an IR node as [[text, depth]] pieces that a line may only break between;
    the depth indents a continuation line."""
    kind = ir[0]
    if kind in ("and", "or"):
        op = "&" if kind == "and" else "|"
        out = []
        for i, c in enumerate(ir[1]):
            paren = kind == "and" and c[0] == "or"
            sub = _chunks(c, depth + 1 if paren else depth)
            if paren:
                sub[0][0] = "(" + sub[0][0]
                sub[-1][0] += ")"
            if i:
                sub[0] = [op + " " + sub[0][0], depth]
            out.extend(sub)
        return out
    if kind in ("has_any", "has_from_list", "reached_at_least"):
        if kind == "reached_at_least":
            head, items, tail = "ReachedAtLeast(%d, [" % ir[1], [_py_str(i) for i in ir[2]], "])"
        else:
            name = "HasAny" if kind == "has_any" else "HasFromList"
            head, items = name + "(", [_py_str(i) for i in sorted(set(ir[1]))]
            tail = ")" if kind == "has_any" else ", count=%d)" % ir[2]
        if len(items) == 1:
            return [[head + items[0] + tail, depth]]
        return ([[head + items[0] + ",", depth]] + [[it + ",", depth + 1] for it in items[1:-1]]
                + [[items[-1] + tail, depth + 1]])
    return [[_leaf(ir), depth]]


def ir_to_py(ir) -> str:
    """The IR as a one-line Rule Builder expression."""
    return " ".join(text for text, _depth in _chunks(ir))


def _statement(head, args, ir, close="", comment="", wrap=False) -> str:
    """`head` + `args` + the expression + `close` on one line when it fits in WIDTH; otherwise the
    head alone, then the rest indented and broken before an operator or an argument. `wrap` adds
    the parentheses a bare assignment needs to continue on the next line."""
    chunks = _chunks(ir)
    expr = " ".join(text for text, _depth in chunks)
    if len(head + args + expr + close) <= WIDTH:
        return head + args + expr + close + comment
    lines, cur = [head + ("(" if wrap else "")], "    " + args
    for i, (text, depth) in enumerate(chunks):
        if i and len(cur) + 1 + len(text) > WIDTH:
            lines.append(cur)
            cur = " " * (4 + 4 * depth) + text
        else:
            cur = cur + text if i == 0 else cur + " " + text
    lines.append(cur + close + (")" if wrap else "") + comment)
    return "\n".join(lines)


def _expert_note(req) -> str:
    """The alternatives the expert tier adds, as text, or ''."""
    extra = list((req or {}).get("expert") or [])
    return "expert adds: " + dnf_to_text(extra) if extra else ""


def _comment(*parts) -> str:
    """A trailing comment out of the parts that are not empty, on one line."""
    text = "   ".join(" ".join(str(p).split()) for p in parts if p)
    return "   # " + text if text else ""


def _bosses_in(ir, gates) -> set:
    """Boss ids the IR names, through its gates and macros."""
    if ir[0] == "boss":
        return {ir[1]}
    if ir[0] in ("and", "or"):
        return set().union(*(_bosses_in(c, gates) for c in ir[1]))
    if ir[0] == "gate":
        return _bosses_in(gates[ir[1]], gates)
    if ir[0] == "macro":
        return _bosses_in(MACRO_IR[ir[1]], gates)
    return set()


def _rules_index(world, doc, tier, errors) -> dict:
    """Everything both exporters write, computed once: regions, entrances, locations, events, arenas,
    counted items and the errors; a rule that cannot be built reads as never and is reported."""
    faults = {}
    members = resolve_members(world, doc)
    try:
        gates = gate_table(doc, tier)
    except (ValueError, KeyError) as e:
        gates, faults["gates"] = {}, str(e)
    context = rule_context(world, doc, members)
    needed = global_reachability(world, doc, members, tier)
    regions = [MENU, FIELD] + [region_name(room, rid) for room, rl in doc["rooms"].items()
                               for rid in ["main"] + sorted(r for r in rl["regions"] if r != "main")
                               if region_name(room, rid) in needed]
    # an entrance out of or into a region the start never leads to would join nothing
    present = set(regions)
    entrances = [e for e in entrance_rules(world, doc, members, tier, faults, context)
                 if e[1] in present and e[2] in present]
    locations = {}
    for name in world["locations"]:
        try:
            locations[name] = location_rule(world, doc, members, needed, name, tier, faults, context)
        except (ValueError, KeyError, TypeError) as e:
            locations[name], faults[name] = (FIELD, IR_FALSE), str(e)
    arenas = {}
    for name, src, dst, ir in entrances:
        for bid in _bosses_in(ir, gates):
            arenas.setdefault(bid, dst)
    for name, (parent, ir) in locations.items():
        for bid in _bosses_in(ir, gates):
            arenas.setdefault(bid, parent)
    for (room, rid), bid in boss_regions(doc).items():
        arenas[bid] = region_name(room, rid)
    events = location_events(world)
    placed_events = {region: held for region, held in region_events(doc).items() if region in present}
    warps = [w for w in mission_warps(world, doc, members) if w[2] in present and w[3] in present]
    return {"members": members, "gates": gates, "entrances": entrances, "needed": needed, "regions": regions,
            "warps": warps, "region_events": placed_events,
            "locations": locations, "events": events, "faults": faults, "control": context["control"],
            "arenas": {bid: arenas[bid] for bid in sorted(arenas)}, "counted": sorted(count_items_used(doc)),
            "errors": list(errors) + ["%s: %s" % (name, msg) for name, msg in faults.items()],
            "start": region_name(world["start_room"], "main")}


def _region_title(doc, room, rid) -> str:
    return doc["rooms"][room]["regions"].get(rid, {}).get("name", rid)


def _edge_comment(world, doc, d, dst_rid) -> str:
    """What an edge of the room graph is, for the reader: kind, destination, gate, transport, site."""
    dst = world["room_label"].get(d["dst"], d["dst"])
    if d["dst"] == d["src"]:
        dst = _region_title(doc, d["dst"], dst_rid)
    elif dst_rid != "main":
        dst += "/" + _region_title(doc, d["dst"], dst_rid)
    text = "%s -> %s" % (EDGE_WORDS.get(d["kind"], d["kind"]), dst)
    if d.get("gate") is not None:
        text += "  gate %d" % d["gate"]
        item = world["story"]["gate_items"].get(d["gate"])
        if item:
            text += " (%s with mission_objectives: locations_and_items)" % item
    if d["kind"] == "warp" and d["src"] == world["hub"]:
        item = world["transerver_access"].get(d["dst"])
        text += "  needs %s" % item if item else "  no Transport destination: never"
    if d["name"] in world["site_doors"]:
        text += "  door constraint site"
    return text


def _event_lines(events, name) -> list:
    """The events anchored to a location, which share its region and rule plus what each adds."""
    out = []
    for event_name, item, extra in events.get(name, []):
        comment = _comment("event" if item == event_name else "the %s event" % item)
        head = "LOCATIONS[%s] = LOCATIONS[%s]" % (_py_str(event_name), _py_str(name))
        if extra == IR_TRUE:
            out.append(head + comment)
        else:
            out.append(_statement(head + ".also(", "", extra, ")", comment))
    return out


def _fault_comment(faults, name) -> str:
    return "ERROR: " + faults[name] if name in faults else ""


def _constants(index, doc) -> list:
    """The module constants: aliases, gates and the tables the world reads besides the rules."""
    L = ["# The atoms the world answers, the model aliases and the seal"]
    for name, ir in MACRO_IR.items():
        L.append(_statement("%s = " % name, "", ir, "", _comment(MACRO_NOTES.get(name)), wrap=True))
    gates = index["gates"]
    if gates:
        L.append("")
        L.append("# Event gates (flag): what the story needs before the game opens them")
        for flag in sorted(gates):
            note = doc.get("gates", {}).get(str(flag), {}).get("note")
            L.append(_statement("GATE_%d = " % flag, "", gates[flag], "", _comment(note), wrap=True))
    L.append("")
    L.append("# Errors of the document the rules were generated from; the world refuses to generate while there are any")
    L.append("ERRORS = [%s]" % ("" if not index["errors"] else "\n    " + ",\n    ".join(_py_str(e) for e in index["errors"]) + ",\n"))
    L.append("# Useful items the rules count, which the world promotes to progression")
    L.append("COUNTED_ITEMS = [%s]" % ", ".join(_py_str(i) for i in index["counted"]))
    L.append("# Boss id -> the region its requirement guards: its tagged arena, or where its atom sits")
    L.append("BOSS_ARENAS = {\n    %s,\n}" % ",\n    ".join("%s: %s" % (_py_str(b), _py_str(r)) for b, r in index["arenas"].items()))
    L.append("# The region a new game begins in, and every region the start can lead to")
    L.append("START = %s" % _py_str(index["start"]))
    L.append("REGIONS = [\n    %s,\n]" % ",\n    ".join(_py_str(r) for r in index["regions"]))
    L.append("# Event location -> the item it holds; each sits where its anchor location does, or in its region")
    items = [(event_name, item) for anchored in index["events"].values() for event_name, item, _extra in anchored]
    items += [(event_name, item) for held in index["region_events"].values() for event_name, item, _ir in held]
    L.append("EVENTS = {\n    %s,\n}" % ",\n    ".join("%s: %s" % (_py_str(e), _py_str(i)) for e, i in items))
    return L


def export_rules_py(world, doc, tier=TIER, errors=()) -> str:
    """The generated logic/rules.py: the region graph and every rule, room by room.

    `errors` are the validation errors of the document; they go into ERRORS so the world refuses
    to generate from a broken document instead of playing an old logic.
    """
    try:
        index = _rules_index(world, doc, tier, errors)
    except Exception as e:  # noqa: BLE001  a document the exporter cannot walk still yields a module that says so
        return _stub_module(list(errors) + ["the exporter failed: %s: %s" % (type(e).__name__, e)])
    members, gates, events, faults = index["members"], index["gates"], index["events"], index["faults"]
    by_src = {}
    for name, src, dst, ir in index["entrances"]:
        by_src.setdefault(src, []).append((name, dst, ir))
    edges = {e["name"]: e for e in world["edges"]}
    warps = {name: (mission, src, dst) for name, mission, src, dst in index["warps"]}
    start_room = world["start_room"]
    placed_rooms = {}
    for name in world["locations"]:
        for room, _ in check_placements(world, doc, name):
            placed_rooms.setdefault(name, []).append(room)

    def entrance(name, src, dst, ir, comment):
        return _statement("ENTRANCES[%s] = Edge(" % _py_str(name), "%s, %s, " % (_py_str(src), _py_str(dst)), ir, ")", comment)

    def location(name, comment):
        parent, ir = index["locations"][name]
        lines = [_statement("LOCATIONS[%s] = Spot(" % _py_str(name), "%s, " % _py_str(parent), ir, ")", comment)]
        return lines + _event_lines(events, name)

    body = ["", "# Start of the game",
            entrance(START_ENTRANCE, MENU, index["start"], index["entrances"][0][3], _comment(_fault_comment(faults, START_ENTRANCE))),
            "ENTRANCES[%s] = Edge(%s, %s, True_())" % (_py_str(FIELD_ACCESS), _py_str(MENU), _py_str(FIELD))
            + _comment("the locations that stand for more than one region")]
    for room in world["rooms"]:
        rl = doc["rooms"][room]
        head = "# --- %s [%s]" % (world["room_label"][room], room)
        if rl.get("req"):
            head += "   entry: " + dnf_to_text(req_alternatives(rl["req"], "expert"))
        if not any(region_name(room, rid) in index["needed"] for rid in rl["regions"]):
            head += "   (nothing leads here from the start: not in the world)"
        body.extend(["", head + _comment(rl.get("note"))])
        regs = rl["regions"]
        for rid in ["main"] + sorted(r for r in regs if r != "main"):
            reg = regs[rid]
            region = region_name(room, rid)
            lines = []
            for name, dst, ir in by_src.get(region, []):
                if name in edges:
                    d, ov = edges[name], doc.get("edges", {}).get(name, {})
                    dst_rid = members[d["dst"]].get(name + "@in", "main")
                    comment = _comment(_fault_comment(faults, name), "?" if ov.get("unsure") else "",
                                       _edge_comment(world, doc, d, dst_rid), _expert_note(ov.get("req")), ov.get("note"))
                elif name in warps:
                    comment = _comment("mission warp -> %s  with include_warps_in_logic" % world["room_label"][dst.split("/")[0]])
                else:
                    c = next(c for c in rl.get("conns", []) if connection_name(room, c) == name)
                    comment = _comment(_fault_comment(faults, name), "?" if c.get("unsure") else "",
                                       "conn -> " + _region_title(doc, room, c["to"]), _expert_note(c.get("req")), c.get("note"))
                lines.append(entrance(name, region, dst, ir, comment))
            landings = [world["room_label"].get(e["src"], e["src"]) for e in world["edges"]
                        if e["dst"] == room and e["src"] != room and e["kind"] not in NON_TRANSITION_KINDS
                        and members[room].get(e["name"] + "@in", "main") == rid]
            landings += [world["room_label"][src.split("/")[0]] + " (mission warp)"
                         for _mission, src, dst in warps.values() if dst == region]
            if landings:
                lines.append("#   <- " + ", ".join(dict.fromkeys(landings)))
            here = sorted(n for n, rooms in placed_rooms.items() if rooms[0] == room and members[room].get(n, "main") == rid)
            for name in here:
                ch = doc.get("checks", {}).get(name, {})
                others = [world["room_label"].get(r, r) for r in placed_rooms[name][1:]]
                comment = _comment(_fault_comment(faults, name), "?" if ch.get("unsure") else "",
                                   "also in %s: any of them counts" % ", ".join(others) if others else "",
                                   _expert_note(ch.get("req")), ch.get("note"))
                lines.extend(location(name, comment))
            for event_name, item, ir in index["region_events"].get(region, []):
                lines.append(_statement("LOCATIONS[%s] = Spot(" % _py_str(event_name), "%s, " % _py_str(region), ir, ")",
                                        _comment("the %s event of the region" % item)))
            title = "# region %s" % reg.get("name", rid)
            if reg.get("boss"):
                title += "   [ARENA: %s]" % BOSSES.get(reg["boss"], {}).get("name", reg["boss"])
            if room == start_room and rid == "main":
                title += "   [START]"
            if lines or reg.get("boss") or reg.get("note") or (room == start_room and rid == "main"):
                body.append(title + _comment(reg.get("note")))
                body.extend(lines)
    unplaced = sorted(n for n in world["locations"] if not placed_rooms.get(n))
    if unplaced:
        body.extend(["", "# --- Unplaced locations: they stand for the rooms of their area label in the data"])
        for name in unplaced:
            v, ch = world["locations"][name], doc.get("checks", {}).get(name, {})
            comment = _comment(_fault_comment(faults, name), "label %s" % v.get("room"),
                               _expert_note(ch.get("req")), ch.get("note"))
            body.extend(location(name, comment))
    constants = "\n".join(_constants(index, doc))
    text = constants + "\n" + "\n".join(body)
    used = [c for c in RULE_CLASSES if re.search(r"\b%s\(" % c, text)]
    custom = [c for c in BUILDER_CLASSES if re.search(r"\b%s\(" % c, text)]
    options = sorted(set(re.findall(r"OptionFilter\((\w+),", text)))
    L = ['"""%s' % GENERATED_HEADER, '"""',
         "from rule_builder.options import OptionFilter",
         "from rule_builder.rules import %s" % ", ".join(used), "",
         "from ..options import %s" % ", ".join(options),
         "from .builder import %s" % ", ".join(custom + ["Edge", "Spot"]), "",
         constants, "",
         "ENTRANCES = {}", "LOCATIONS = {}"]
    L.extend(body)
    return "\n".join(L) + "\n"


def _stub_module(errors) -> str:
    """A rules.py with nothing but its errors, for a document the exporter cannot walk."""
    L = ['"""%s' % GENERATED_HEADER, '"""', "from .builder import Edge, Spot  # noqa: F401", "",
         "ERRORS = [\n    %s,\n]" % ",\n    ".join(_py_str(e) for e in errors),
         "COUNTED_ITEMS = []", "BOSS_ARENAS = {}", 'START = ""', "REGIONS = []", "EVENTS = {}",
         "ENTRANCES = {}", "LOCATIONS = {}"]
    return "\n".join(L) + "\n"


def export_rules_json(world, doc, tier=TIER, errors=()) -> dict:
    """The generated logic/rules.json: the rules serialized as the Rule Builder does, by room."""
    try:
        index = _rules_index(world, doc, tier, errors)
    except Exception as e:  # noqa: BLE001
        return {"generated": JSON_NOTICE, "game": GAME, "tier": tier,
                "errors": list(errors) + ["the exporter failed: %s: %s" % (type(e).__name__, e)], "rooms": {}}
    gates, events = index["gates"], index["events"]
    out = {"generated": JSON_NOTICE, "game": GAME, "tier": tier, "errors": index["errors"], "start": index["start"],
           "regions": index["regions"], "events": {e: i for anchored in events.values() for e, i, _x in anchored},
           "boss_arenas": index["arenas"], "counted_items": index["counted"], "lava_control": index["control"],
           "rooms": {}, "unplaced": {}}
    for room in world["rooms"]:
        out["rooms"][room] = {"label": world["room_label"][room], "entrances": {}, "locations": {}}
    for region, held in index["region_events"].items():
        for event_name, item, ir in held:
            out["events"][event_name] = item
            out["rooms"][region.split("/")[0]]["locations"][event_name] = {"region": region, "rule": ir_to_dict(ir, gates), "event": item}
    for name, src, dst, ir in index["entrances"]:
        room = (dst if src == MENU else src).split("/")[0]
        out["rooms"][room]["entrances"][name] = {"from": src, "to": dst, "rule": ir_to_dict(ir, gates)}
    for name, (parent, ir) in index["locations"].items():
        placed = [room for room, _ in check_placements(world, doc, name)]
        target = out["rooms"][placed[0]]["locations"] if placed else out["unplaced"]
        target[name] = {"region": parent, "rule": ir_to_dict(ir, gates)}
        for event_name, item, extra in events.get(name, []):
            target[event_name] = {"region": parent, "rule": ir_to_dict(ir_and([ir, extra]), gates), "event": item}
    return out


def write_generated(world, doc, folder, errors=()) -> None:
    """Writes logic/rules.py and logic/rules.json next to the document, errors of the document
    included; a module that would not even compile is not written (SyntaxError)."""
    text = export_rules_py(world, doc, errors=errors)
    compile(text, "rules.py", "exec")
    (folder / "rules.py").write_text(text, encoding="utf-8", newline="\n")
    with open(folder / "rules.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(export_rules_json(world, doc, errors=errors), f, ensure_ascii=False, indent=1)
        f.write("\n")
