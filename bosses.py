"""Dificultad de jefes configurable desde el YAML (opción `boss_logic`).

El jugador decide qué necesita tener para que la lógica lo considere capaz
de vencer a cada jefe de la historia. Es una restricción SOLO de lógica: en
el juego puede pelear con lo que quiera; lo que se garantiza es que la seed
nunca le OBLIGUE a pasar por un jefe para el que no tiene lo que él mismo ha
pedido — ni a cruzar su arena, ni a coger lo que hay dentro, ni a completar
su misión, ni a obtener su biometal (los biometales salen de dos jefes: si
solo se puede con uno, la lógica cuenta ese camino y no el otro).

El requisito se escribe con la MISMA sintaxis del editor de lógica
(docs/logic_format.md), más unos alias en castellano/inglés natural:

    Mega Man ZX:
      boss_logic:
        Hivolt: "HX & LIFEUP>=2"
        Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
        Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
        Flammole: "Model FX (full) & Absorber Chip"

El anclaje de cada jefe en el grafo vive en el documento de lógica
(logic_format.BOSSES, etiqueta `boss` de la región o átomo BOSS_<ID>).
"""

import re

from . import logic_format as F

# --------------------------------------------------------------------------
# Nombres aceptados como clave del YAML: nombre del jefe, id, sala ("O-2",
# "o02"). Se comparan sin mayúsculas, espacios ni puntuación.
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

# Alias "en cristiano" -> átomos del DSL, aplicados antes de parsear.
_CHIP_BY_WORD = {_n.split(" Chip")[0].lower(): _a for _a, _n in F.CHIP_ATOMS.items()}
_CHIP_NOSPACE = {k.replace(" ", ""): v for k, v in _CHIP_BY_WORD.items()}
_KEY_COLORS = "yellow|green|red|blue|purple|white"
_SUBS = [
    (r"\ball\s+biometals?\b", lambda m: "ALL6"),
    (r"\blos\s+seis\s+biometales\b", lambda m: "ALL6"),
    (r"\bany\s+model\b", lambda m: "MODEL"),
    (r"\bcualquier\s+modelo\b", lambda m: "MODEL"),
    # "Model HX (full)" / "HX completo" = las dos mitades del progresivo
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

# Átomos prohibidos dentro de un requisito de jefe: otro jefe (recursión) y
# los eventos de misión (dependen de alcanzar regiones que este mismo
# requisito puede estar cerrando; la lógica se vuelve ilegible).
_FORBIDDEN = set(F.BOSS_ATOMS) | set(F.MISSION_EVENT)


def friendly_to_dsl(expr: str) -> str:
    out = str(expr)
    for pat, rep in _SUBS:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


def resolve_boss(key: str) -> str:
    """Clave del YAML -> id de jefe. ValueError si no existe."""
    bid = BOSS_BY_KEY.get(_norm(key))
    if bid is None:
        raise ValueError("unknown boss %r. Valid names: %s" % (key, ", ".join(BOSS_NAMES)))
    return bid


def parse_boss_logic(value) -> dict:
    """{clave del YAML: expresión} -> {id de jefe: REQ}. Las entradas vacías
    ('', None, 'free') se ignoran: ese jefe no pide nada."""
    out, seen = {}, {}
    for key, expr in dict(value or {}).items():
        bid = resolve_boss(key)
        if bid in seen:
            raise ValueError("boss %s appears twice in boss_logic (%r and %r)"
                             % (F.BOSSES[bid]["name"], seen[bid], key))
        seen[bid] = key
        if expr is None or (isinstance(expr, str) and not expr.strip()):
            continue
        if isinstance(expr, (list, tuple)):        # lista = AND de requisitos
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
    """{id: REQ} -> {átomo BOSS_<ID>: callable(state)}. Solo los jefes con
    requisito real; el resto los resuelve logic_format como libres."""
    rules = {}
    for bid, req in (reqs or {}).items():
        r = F.compile_req(req, tier, player, hu_in_pool)
        if r is not None:
            rules[F.boss_atom(bid)] = r
    return rules


def items_used(reqs) -> set:
    """Items `useful` que estos requisitos convierten en progresión."""
    atoms = set()
    for req in (reqs or {}).values():
        atoms |= F.req_atoms(req)
    return F.progression_items(atoms)


def describe(reqs) -> dict:
    """{nombre del jefe: texto del requisito} para slot_data y depuración."""
    return {F.BOSSES[b]["name"]: F.dnf_to_text(F.req_alternatives(r, "expert"))
            for b, r in sorted((reqs or {}).items())}


def unanchored(doc, reqs) -> list:
    """Jefes CON requisito que no están anclados en el documento: su
    requisito no se aplicaría a nada. Es un error de generación."""
    anchored = F.bosses_anchored(doc)
    return [F.BOSSES[b]["name"] for b in sorted(reqs or {}) if b not in anchored]
