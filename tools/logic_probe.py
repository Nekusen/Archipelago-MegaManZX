#!/usr/bin/env python3
"""logic_probe.py — sonda LOCAL de la lógica del apworld (sin generar seed).

Carga el core de Archipelago desde un checkout de fuentes (0.6.7; por
defecto $AP_SRC, o ../ArchipelagoDW junto al laboratorio) con el Python del venv, registra
este apworld tal cual está en el árbol de trabajo y construye un multiworld
de 1 jugador con las opciones dadas. Después, con un inventario concreto,
calcula qué salas/regiones y qué locations están EN LÓGICA y cuál es la
FRONTERA: aristas que salen de una región alcanzable hacia una no
alcanzable, con la regla (llave / entrada de sala / coste de arista /
verja / conexión curada / Transerver, leídas de logic/
logic.json) que las bloquea. Responde a "¿por qué no puedo ir a F-5 con
HX?" sin abrir el tracker. Opciones útiles: --opt logic_difficulty=expert,
--world <carpeta de otro apworld>, --json <salida> (comparaciones).

Uso (desde la raíz del workspace):
  .venv/Scripts/python.exe tools/logic_probe.py \
      --opt starting_model=model_hx --opt hu_in_pool=true \
      --items "Blue Card Key" "Transerver Access - Area C" \
      [--all-keys] [--all-models] [--all-access] [--loc "Mission - Find The Survivors"] \
      [--rooms] [--locs] [--frontier] [--ap CHECKOUT_DE_AP]

Sin --rooms/--locs/--frontier se imprime todo. --loc explica una location
concreta (región, regla, salas de su etiqueta que faltan).
"""
import argparse
import contextlib
import importlib.util
import io
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # raíz del apworld (paquete mmzx)


def _default_ap() -> str:
    """Checkout de fuentes de Archipelago: $AP_SRC; si no, ArchipelagoDW
    hermano de la raíz del laboratorio (worlds/mmzx/tools → 4 niveles)."""
    if os.environ.get("AP_SRC"):
        return os.environ["AP_SRC"]
    try:
        cand = Path(__file__).resolve().parents[4] / "ArchipelagoDW"
        if cand.exists():
            return str(cand)
    except IndexError:
        pass
    return ""


DEFAULT_AP = _default_ap()


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=DEFAULT_AP, help="checkout de fuentes de Archipelago (0.6.7)")
    ap.add_argument("--opt", action="append", default=[], metavar="KEY=VALUE",
                    help="opción del YAML (p.ej. starting_model=model_hx, hu_in_pool=true)")
    ap.add_argument("--items", nargs="*", default=[], help="items recibidos (nombres exactos)")
    ap.add_argument("--all-keys", action="store_true", help="añade todas las Card Keys")
    ap.add_argument("--all-models", action="store_true", help="añade todos los modelos/biometales")
    ap.add_argument("--all-access", action="store_true", help="añade todos los Transerver Access")
    ap.add_argument("--loc", action="append", default=[], help="explica esta location")
    ap.add_argument("--rooms", action="store_true")
    ap.add_argument("--locs", action="store_true")
    ap.add_argument("--frontier", action="store_true")
    ap.add_argument("--world", default=None, help="carpeta del apworld a cargar (por defecto este mismo paquete)")
    ap.add_argument("--json", default=None, help="volcar {salas, locations en lógica} como JSON a este fichero (comparaciones)")
    return ap.parse_args()


def load_core(ap_src: str, world_dir=None):
    """Importa el core de AP y registra worlds.mmzx desde el árbol de trabajo.
    El cargador de mundos de AP intenta importar TODOS los mundos del
    checkout (ruido: mundos con deps no instaladas); se silencia.

    El cwd del proceso se cambia al checkout de AP SOLO durante los imports y
    se restaura SIEMPRE al salir. Dejar el proceso "aparcado" dentro de otro
    repo hizo que una salida relativa (--out work/...) cayera en
    ArchipelagoDW/work/ y que la limpieza posterior borrara ese work/ entero
    (incidente 2026-09-03). Las rutas de salida se resuelven ANTES de llamar.
    """
    if not ap_src:
        raise SystemExit("hace falta un checkout de fuentes de Archipelago: --ap RUTA o la variable AP_SRC")
    ap_src = str(Path(ap_src).resolve())
    world_dir = str(Path(world_dir).resolve()) if world_dir else None   # antes del chdir
    sys.path.insert(0, ap_src)
    logging.disable(logging.CRITICAL)
    # worlds/__init__.py importa TODOS los mundos del checkout (75, minutos y
    # ruido por deps ausentes): se filtra os.scandir durante ese import para
    # que solo vea 'generic' (Archipelago core). Se restaura después.
    real_scandir = os.scandir
    worlds_dir = os.path.normcase(os.path.join(ap_src, "worlds"))

    def scandir_only_generic(path=".", *a, **k):
        it = real_scandir(path, *a, **k)
        if os.path.normcase(os.path.abspath(str(path))) != worlds_dir:
            return it
        return iter([e for e in it if e.name == "generic"])

    prev_cwd = os.getcwd()
    os.chdir(ap_src)   # AP resuelve rutas relativas (host.yaml, data/) desde cwd durante el import
    os.scandir = scandir_only_generic
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            import BaseClasses  # noqa: F401
            from worlds.AutoWorld import AutoWorldRegister
        os.scandir = real_scandir
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            wdir = Path(world_dir) if world_dir else (ROOT)
            p = str(wdir / "__init__.py")
            spec = importlib.util.spec_from_file_location(
                "worlds.mmzx", p, submodule_search_locations=[str(wdir)])
            m = importlib.util.module_from_spec(spec)
            sys.modules["worlds.mmzx"] = m
            spec.loader.exec_module(m)
    finally:
        os.scandir = real_scandir
        os.chdir(prev_cwd)   # nunca dejar el proceso dentro del checkout de AP
    logging.disable(logging.NOTSET)
    return AutoWorldRegister.world_types["Mega Man ZX"]


def parse_value(v: str):
    lv = v.lower()
    if lv in ("true", "yes", "on"):
        return True
    if lv in ("false", "no", "off"):
        return False
    try:
        return int(v)
    except ValueError:
        return v


def main():
    a = parse_args()
    show_all = not (a.rooms or a.locs or a.frontier or a.loc)
    world_type = load_core(a.ap, a.world)
    from test.general import setup_multiworld
    from BaseClasses import CollectionState

    opts = {}
    for kv in a.opt:
        k, _, v = kv.partition("=")
        opts[k.strip()] = parse_value(v.strip())
    mw = setup_multiworld(world_type, options=opts)
    world = mw.worlds[1]
    player = 1

    # datos crudos para describir reglas (mismo árbol de trabajo)
    mm = sys.modules["worlds.mmzx"]
    data = mm.data
    logic = mm.logic
    F = mm.logic_format
    doc = mm.regions.load_document()
    tier = world.options.logic_difficulty.current_key
    members = F.resolve_members(logic.WORLD, doc)

    def req_txt(req):
        return F.dnf_to_text(F.req_alternatives(req, tier)) if req is not None else "free"

    items = list(a.items)
    if a.all_keys:
        items += [n for n in data.ITEMS if n.endswith("Card Key")]
    if a.all_models:
        for n, v in data.ITEMS.items():
            if "Model " in n:
                items += [n] * int(v.get("count", 1))   # progresivos: las 2 mitades
    if a.all_access:
        items += [n for n in data.ITEMS if n.startswith("Transerver Access")]

    state = CollectionState(mw)
    for name in items:
        if name not in world.item_name_to_id:
            print("!! item desconocido:", name)
            continue
        state.collect(world.create_item(name), prevent_sweep=True)
    state.sweep_for_advancements()       # recoge eventos ("Cleared: ...") alcanzables
    state.update_reachable_regions(player)
    reach = {r.name for r in state.reachable_regions[player]}

    precollected = [i.name for i in mw.precollected_items[player]]
    print("== opciones:", {k: getattr(world.options, k).current_key
                          if hasattr(getattr(world.options, k), "current_key") else getattr(world.options, k).value
                          for k in opts} or "(por defecto)")
    print("== inventario:", precollected + items)
    events = sorted(i for i in state.prog_items[player] if i.startswith("Cleared: ") or i == "Victory")
    if events:
        print("== eventos alcanzados:", events)

    # sala alcanzable = alguna de sus regiones alcanzable (Main puede estar
    # vacía si todo está en polígonos)
    rooms = sorted(r for r in logic.ROOM_NAMES if r in reach or any(x.startswith(r + "/") for x in reach))
    subs = sorted(r for r in reach if "/" in r)
    if show_all or a.rooms:
        print("\n== salas alcanzables (%d/%d):" % (len(rooms), len(logic.ROOM_NAMES)))
        print("   " + " ".join(rooms))
        if subs:
            print("   sub-regiones: " + " ".join(subs))
        missing = sorted(set(logic.ROOM_NAMES) - set(rooms))
        print("== salas NO alcanzables (%d): %s" % (len(missing), " ".join(missing)))

    def describe_edge(ent):
        """Texto de la regla de una entrance del grafo de regiones."""
        name = ent.name
        parts = []
        for d in data.DOORS:
            if d["name"] == name:
                if d.get("key"):
                    parts.append("llave %s" % d["key"])
                rr = doc["rooms"][d["dst"]].get("req")
                if rr:
                    parts.append("sala %s: %s" % (d["dst"], req_txt(rr)))
                ov = doc.get("edges", {}).get(name, {})
                if ov.get("req") and not F.req_is_free(ov["req"], tier):
                    parts.append("arista: %s" % req_txt(ov["req"]))
                if d.get("gate") is not None:
                    g = doc.get("gates", {}).get(str(d["gate"]), {}).get("req")
                    parts.append("verja de evento %d: %s" % (d["gate"], req_txt(g) if g else "libre (el cliente pone el flag)"))
                if d["kind"] == "warp" and d["src"] == data.HUB_ROOM:
                    if d["dst"] in data.TRANSERVER_ALWAYS:
                        parts.append("warp libre")
                    else:
                        it = data.TRANSERVER_ACCESS.get(d["dst"])
                        parts.append("warp: %s" % (it or "SIN destino de Transport"))
                break
        else:
            # conexión curada "<sala>: <from> -> <to>", o "Start"
            if ": " in name and " -> " in name:
                room, rest = name.split(": ", 1)
                a_, b_ = rest.split(" -> ", 1)
                for c in doc["rooms"].get(room, {}).get("conns", []):
                    if c["from"] == a_ and c["to"] == b_:
                        parts.append("conexión: %s%s" % (req_txt(c.get("req")), " (?)" if c.get("unsure") else ""))
            if name == "Start":
                parts.append("sala inicial: %s" % req_txt(doc["rooms"][ent.connected_region.name.split("/")[0]].get("req")))
        return "; ".join(parts) or "(sin regla; ¿evento?)"

    if show_all or a.frontier:
        print("\n== FRONTERA (arista alcanzable -> destino no alcanzable):")
        seen = set()
        for reg in sorted(state.reachable_regions[player], key=lambda r: r.name):
            for ent in reg.exits:
                dst = ent.connected_region
                if dst is None or dst.name in reach:
                    continue
                key = (reg.name, dst.name)
                if key in seen:
                    continue
                seen.add(key)
                print("   %-4s -> %-12s [%s]  %s" % (reg.name, dst.name, ent.name, describe_edge(ent)))

    locs_in = [l for l in mw.get_locations(player) if l.address is not None and l.can_reach(state)]
    locs_out = [l for l in mw.get_locations(player) if l.address is not None and not l.can_reach(state)]
    if show_all or a.locs:
        print("\n== locations EN LÓGICA (%d):" % len(locs_in))
        for l in sorted(locs_in, key=lambda l: l.name):
            print("   " + l.name)
        print("\n== locations FUERA de lógica (%d):" % len(locs_out))
        for l in sorted(locs_out, key=lambda l: l.name):
            print("   " + l.name)

    for name in a.loc:
        loc = next((l for l in mw.get_locations(player) if l.name == name), None)
        if loc is None:
            print("\n?? location no encontrada:", name)
            continue
        v = data.LOCATIONS.get(name, {})
        print("\n== %s: %s" % (name, "EN LÓGICA" if loc.can_reach(state) else "FUERA"))
        print("   región: %s (%s)" % (loc.parent_region.name,
                                     "alcanzable" if loc.parent_region.name in reach else "NO alcanzable"))
        ch = doc.get("checks", {}).get(name, {})
        print("   regla curada: %s%s" % (req_txt(ch.get("req")) if ch.get("req") else "free",
                                          " (?)" if ch.get("unsure") else ""))
        room, pos = F.check_position(logic.WORLD, doc, name)
        if room:
            rid = members[room].get(name, "main")
            print("   sala: %s (%s), región %s (%s)" % (
                room, "alcanzable" if room in reach else "NO alcanzable",
                F.region_name(room, rid), "alcanzable" if F.region_name(room, rid) in reach else "NO alcanzable"))
        else:
            label = v.get("room")
            for g in logic.label_room_groups(label):
                lack = [r for r in g if r not in reach]
                print("   SIN COLOCAR; etiqueta %r -> salas %s; faltan: %s" % (label, g, lack or "ninguna"))

    if a.json:
        import json
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"rooms": rooms, "regions": sorted(reach), "locs_in": sorted(l.name for l in locs_in),
                       "locs_out": sorted(l.name for l in locs_out), "events": events}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
