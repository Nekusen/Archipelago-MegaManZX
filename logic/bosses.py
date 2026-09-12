"""Per-boss requirements from the player's boss_logic option.

A logic-only restriction: the seed never routes the player through a boss they are not
equipped for by their own standard. The YAML uses the same syntax as the logic editor.
"""

import re

from . import document as F

# YAML keys: boss name, id, room code or room label, compared without case, spaces or punctuation.


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


BOSS_BY_KEY = {}
for _bid, _v in F.BOSSES.items():
    for _alias in (_bid, _v["name"], _v["room"], F.room_label(_v["room"])):
        BOSS_BY_KEY[_norm(_alias)] = _bid
BOSS_NAMES = [v["name"] for v in F.BOSSES.values()]

# Plain-language aliases rewritten to atoms before parsing.
_CHIP_BY_WORD = {_n.split(" Chip")[0].lower(): _a for _a, _n in F.CHIP_ATOMS.items()}
_CHIP_NOSPACE = {k.replace(" ", ""): v for k, v in _CHIP_BY_WORD.items()}
_KEY_COLORS = "yellow|green|red|blue|purple|white"
_SUBS = [
    (r"\ball\s+biometals?\b", lambda m: "ALL6"),
    (r"\blos\s+seis\s+biometales\b", lambda m: "ALL6"),
    (r"\bany\s+model\b", lambda m: "MODEL"),
    (r"\bcualquier\s+modelo\b", lambda m: "MODEL"),
    # "Model HX (full)": both halves of the progressive item
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

# A boss requirement may not name another boss or a mission event: the events depend on
# regions this very requirement may be closing off.
_FORBIDDEN = set(F.BOSS_ATOMS) | set(F.MISSION_EVENT)


def friendly_to_dsl(expr: str) -> str:
    """Rewrites the plain-language aliases of a YAML requirement to atoms."""
    out = str(expr)
    for pat, rep in _SUBS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


def resolve_boss(key: str) -> str:
    """Boss id of a YAML key; ValueError if it is unknown."""
    bid = BOSS_BY_KEY.get(_norm(key))
    if bid is None:
        raise ValueError("unknown boss %r. Valid names: %s" % (key, ", ".join(BOSS_NAMES)))
    return bid


def parse_boss_logic(value) -> dict:
    """{boss id: REQ} from the option value; empty and 'free' entries are dropped."""
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
    """{BOSS_<ID> atom: rule} for the bosses with a real requirement."""
    rules = {}
    for bid, req in (reqs or {}).items():
        r = F.compile_req(req, tier, player, hu_in_pool)
        if r is not None:
            rules[F.boss_atom(bid)] = r
    return rules


def items_used(reqs) -> set:
    """Useful items that these requirements turn into progression."""
    atoms = set()
    for req in (reqs or {}).values():
        atoms |= F.req_atoms(req)
    return F.progression_items(atoms)


def describe(reqs) -> dict:
    """{boss name: requirement text} for the slot data."""
    return {F.BOSSES[b]["name"]: F.dnf_to_text(F.req_alternatives(r, "expert"))
            for b, r in sorted((reqs or {}).items())}


def unanchored(doc, reqs) -> list:
    """Names of the bosses that have a requirement but no anchor in the document."""
    anchored = F.bosses_anchored(doc)
    return [F.BOSSES[b]["name"] for b in sorted(reqs or {}) if b not in anchored]
