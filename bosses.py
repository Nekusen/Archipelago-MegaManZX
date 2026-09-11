"""Boss difficulty configurable from the YAML (`boss_logic` option).

The player decides what they need to have for the logic to consider them
able to beat each story boss. It is a LOGIC-only restriction: in the game
they can fight with whatever they want; what is guaranteed is that the seed
never FORCES them through a boss for which they lack what they themselves
asked for - neither crossing its arena, nor picking what is inside, nor
completing its mission, nor obtaining its biometal (biometals come from two
bosses: if only one is possible, the logic counts that path and not the other).

The requirement is written with the SAME syntax as the logic editor
(docs/logic_format.md), plus some natural Spanish/English aliases:

    Mega Man ZX:
      boss_logic:
        Hivolt: "HX & LIFEUP>=2"
        Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
        Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
        Flammole: "Model FX (full) & Absorber Chip"

Where each boss is anchored in the graph lives in the logic document
(logic_format.BOSSES, `boss` tag of the region or BOSS_<ID> atom).
"""

import re

from . import logic_format as F

# --------------------------------------------------------------------------
# Names accepted as YAML key: boss name, id, room ("O-2",
# "o02"). Compared ignoring case, spaces and punctuation.
# --------------------------------------------------------------------------


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


BOSS_BY_KEY = {}
for _bid, _v in F.BOSSES.items():
    for _alias in (_bid, _v["name"], _v["room"], F.room_label(_v["room"])):
        BOSS_BY_KEY[_norm(_alias)] = _bid
BOSS_NAMES = [v["name"] for v in F.BOSSES.values()]
VALID_KEYS = frozenset(
    [b["name"] for b in F.BOSSES.values()] + list(F.BOSSES)
    + [F.room_label(b["room"]) for b in F.BOSSES.values()])

# Plain-language aliases -> DSL atoms, applied before parsing.
_CHIP_BY_WORD = {_n.split(" Chip")[0].lower(): _a for _a, _n in F.CHIP_ATOMS.items()}
_CHIP_NOSPACE = {k.replace(" ", ""): v for k, v in _CHIP_BY_WORD.items()}
_KEY_COLORS = "yellow|green|red|blue|purple|white"
_SUBS = [
    (r"\ball\s+biometals?\b", lambda m: "ALL6"),
    (r"\blos\s+seis\s+biometales\b", lambda m: "ALL6"),
    (r"\bany\s+model\b", lambda m: "MODEL"),
    (r"\bcualquier\s+modelo\b", lambda m: "MODEL"),
    # "Model HX (full)" / "HX completo" = both halves of the progressive item
    (r"\b(?:model\s+)?([hflp])x?\s*\(?\s*(?:full|complete|completo|entero)\s*\)?",
     lambda m: m.group(1).upper() + "X2"),
    (r"\bmodel\s+(x|zx|ox|hu|hx|fx|lx|px)\b", lambda m: m.group(1).upper()),
    (r"\bmodel\s+([hflp])\b", lambda m: m.group(1).upper() + "X"),
    (r"\blife\s*ups?\s*(?:x\s*)?(\d+)", lambda m: "LIFEUP>=" + m.group(1)),
    (r"\bsub\s*tanks?\s*(?:x\s*)?(\d+)", lambda m: "SUBTANK>=" + m.group(1)),
    (r"\b(%s)\s+chip\b" % "|".join(sorted(_CHIP_BY_WORD, key=len, reverse=True)).replace(" ", r"\s*"),
     lambda m: _CHIP_NOSPACE[re.sub(r"\s+", "", m.group(1).lower())]),
    (r"\b(%s)\s+card\s*key\b" % _KEY_COLORS, lambda m: m.group(1).upper()),
]

# Atoms forbidden inside a boss requirement: another boss (recursion) and
# the mission events (they depend on reaching regions that this very
# requirement may be closing off; the logic becomes unreadable).
_FORBIDDEN = set(F.BOSS_ATOMS) | set(F.MISSION_EVENT)


def friendly_to_dsl(expr: str) -> str:
    out = str(expr)
    for pat, rep in _SUBS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


def resolve_boss(key: str) -> str:
    """YAML key -> boss id. ValueError if it does not exist."""
    bid = BOSS_BY_KEY.get(_norm(key))
    if bid is None:
        raise ValueError("unknown boss %r. Valid names: %s" % (key, ", ".join(BOSS_NAMES)))
    return bid


def parse_boss_logic(value) -> dict:
    """{YAML key: expression} -> {boss id: REQ}. Empty entries
    ('', None, 'free') are ignored: that boss requires nothing."""
    out, seen = {}, {}
    for key, expr in dict(value or {}).items():
        bid = resolve_boss(key)
        if bid in seen:
            raise ValueError("boss %s appears twice in boss_logic (%r and %r)"
                             % (F.BOSSES[bid]["name"], seen[bid], key))
        seen[bid] = key
        if expr is None or (isinstance(expr, str) and not expr.strip()):
            continue
        if isinstance(expr, (list, tuple)):        # list = AND of requirements
            expr = " & ".join(str(x) for x in expr)
        try:
            dnf = F.parse_expr(friendly_to_dsl(str(expr)))
        except ValueError as e:
            raise ValueError("boss_logic[%s]: %s" % (key, e)) from None
        req = {"normal": dnf}
        bad = sorted(a for a in F.req_atoms(req) if a in _FORBIDDEN)
        if bad:
            raise ValueError("boss_logic[%s]: %s cannot be required (neither another boss nor a mission)"
                             % (key, ", ".join(bad)))
        if F.req_is_free(req):
            continue
        out[bid] = req
    return out


def compile_rules(reqs, tier, player, hu_in_pool=False) -> dict:
    """{id: REQ} -> {BOSS_<ID> atom: callable(state)}. Only bosses with a
    real requirement; logic_format resolves the rest as free."""
    rules = {}
    for bid, req in (reqs or {}).items():
        r = F.compile_req(req, tier, player, hu_in_pool)
        if r is not None:
            rules[F.boss_atom(bid)] = r
    return rules


def items_used(reqs) -> set:
    """`useful` items that these requirements turn into progression."""
    atoms = set()
    for req in (reqs or {}).values():
        atoms |= F.req_atoms(req)
    return F.progression_items(atoms)


def describe(reqs) -> dict:
    """{boss name: requirement text} for slot_data and debugging."""
    return {F.BOSSES[b]["name"]: F.dnf_to_text(F.req_alternatives(r, "expert"))
            for b, r in sorted((reqs or {}).items())}


def unanchored(doc, reqs) -> list:
    """Bosses WITH a requirement that are not anchored in the document: their
    requirement would apply to nothing. It is a generation error."""
    anchored = F.bosses_anchored(doc)
    return [F.BOSSES[b]["name"] for b in sorted(reqs or {}) if b not in anchored]
