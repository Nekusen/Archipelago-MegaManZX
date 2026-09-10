#!/usr/bin/env python3
"""logic_snapshot.py — instantánea REPRODUCIBLE de la lógica del apworld.

Recorre una MATRIZ de (opciones × inventarios) y guarda, para cada celda,
las regiones alcanzables y las locations en lógica. Sirve como línea base
para comprobar que un cambio en la lógica no altera nada donde no debe
(`--compare base.json nuevo.json`).

Comparte el cargador con tools/logic_probe.py (checkout de AP 0.6.7:
--ap o $AP_SRC).

Uso (desde la raíz del apworld):
  python tools/logic_snapshot.py --out build/base.json
  python tools/logic_snapshot.py --out build/nuevo.json
  python tools/logic_snapshot.py --compare build/base.json build/nuevo.json
"""
import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("mmzx_logic_probe", Path(__file__).resolve().parent / "logic_probe.py")
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)  # type: ignore[union-attr]

# Conjuntos de opciones evaluados (nombre -> dict de opciones del YAML).
OPTION_SETS = {
    "default": {},
    "expert": {"logic_difficulty": "expert"},
    "hu_in_pool": {"hu_in_pool": True},
    "no_start_model": {"starting_model": "none"},
}
# Inventarios fijos (nombre -> lista de items). Los progresivos se dan por
# mitades: "Progressive Model HX" dos veces = biometal completo.
KEYS = ["Yellow Card Key", "Green Card Key", "Red Card Key", "Blue Card Key", "Purple Card Key"]
HALVES = ["Progressive Model HX", "Progressive Model FX", "Progressive Model LX", "Progressive Model PX"]


def fixed_inventories(all_items):
    access = [n for n in all_items if n.startswith("Transerver Access")]
    inv = {
        "empty": [],
        "zx": ["Model ZX"],
        "zx+keys": ["Model ZX"] + KEYS,
        "half_models": ["Model ZX"] + HALVES,
        "full_models": ["Model ZX"] + HALVES * 2,
        "models+keys": ["Model ZX"] + HALVES * 2 + KEYS,
        "access": ["Model ZX"] + access,
        "everything": ["Model X", "Model ZX", "Model OX"] + HALVES * 2 + KEYS + access
                      + ["Life Up"] * 4 + ["Sub Tank"] * 4
                      + [n for n in all_items if n.endswith(" Chip")],
    }
    # subconjuntos aleatorios deterministas sobre el pool de progresión
    pool = sorted(set(["Model X", "Model ZX", "Model OX"] + HALVES + KEYS + access))
    rng = random.Random(20260904)
    for i in range(8):
        k = rng.randint(2, len(pool) - 2)
        inv["rnd%d" % i] = sorted(rng.sample(pool, k))
    return inv


def snapshot(ap_src, world_dir=None, extra_options=None):
    world_type = _probe.load_core(ap_src, world_dir)
    from test.general import setup_multiworld
    from BaseClasses import CollectionState

    out = {}
    sets = dict(OPTION_SETS)
    for name, opts in (extra_options or {}).items():
        sets[name] = opts
    for set_name, opts in sets.items():
        mw = setup_multiworld(world_type, options=opts)
        world, player = mw.worlds[1], 1
        inventories = fixed_inventories(list(world.item_name_to_id))
        cell = {}
        for inv_name, items in inventories.items():
            state = CollectionState(mw)
            for it in items:
                if it in world.item_name_to_id:
                    state.collect(world.create_item(it), prevent_sweep=True)
            state.sweep_for_advancements()
            state.update_reachable_regions(player)
            reach = sorted(r.name for r in state.reachable_regions[player])
            locs = sorted(l.name for l in mw.get_locations(player)
                          if l.address is not None and l.can_reach(state))
            cell[inv_name] = {
                "items": sorted(items),
                "regions": reach,
                "locs_in": locs,
                "victory": bool(mw.completion_condition[player](state)),
            }
        # clasificación de los items del pool (progresión/useful/filler)
        cls = {}
        for it in sorted(world.item_name_to_id):
            try:
                cls[it] = str(world.create_item(it).classification)
            except Exception:                                  # noqa: BLE001
                pass
        out[set_name] = {"options": opts, "classification": cls, "cells": cell}
    return out


def compare(a, b):
    diffs = []
    for set_name in sorted(set(a) | set(b)):
        if set_name not in a or set_name not in b:
            diffs.append("conjunto de opciones solo en uno: %s" % set_name)
            continue
        ca, cb = a[set_name], b[set_name]
        for it in sorted(set(ca["classification"]) | set(cb["classification"])):
            xa, xb = ca["classification"].get(it), cb["classification"].get(it)
            if xa != xb:
                diffs.append("[%s] clasificación de %r: %s -> %s" % (set_name, it, xa, xb))
        for inv in sorted(set(ca["cells"]) | set(cb["cells"])):
            da, db = ca["cells"].get(inv, {}), cb["cells"].get(inv, {})
            for key in ("regions", "locs_in"):
                sa, sb = set(da.get(key, [])), set(db.get(key, []))
                for x in sorted(sa - sb):
                    diffs.append("[%s/%s] %s PERDIDO: %s" % (set_name, inv, key, x))
                for x in sorted(sb - sa):
                    diffs.append("[%s/%s] %s NUEVO: %s" % (set_name, inv, key, x))
            if da.get("victory") != db.get("victory"):
                diffs.append("[%s/%s] victoria: %s -> %s" % (set_name, inv, da.get("victory"), db.get("victory")))
    return diffs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=_probe.DEFAULT_AP)
    ap.add_argument("--world", default=None)
    ap.add_argument("--out", default=None, help="guardar la instantánea aquí")
    ap.add_argument("--compare", nargs=2, metavar=("BASE", "NUEVO"))
    ap.add_argument("--opts", default=None, help="JSON {nombre: {opciones}} con conjuntos extra")
    a = ap.parse_args()

    if a.compare:
        base = json.loads(Path(a.compare[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(a.compare[1]).read_text(encoding="utf-8"))
        diffs = compare(base, new)
        for d in diffs:
            print(d)
        print("[logic_snapshot] %d diferencias" % len(diffs))
        sys.exit(1 if diffs else 0)

    extra = json.loads(a.opts) if a.opts else None
    out_path = Path(a.out).resolve() if a.out else None   # antes del chdir del cargador
    snap = snapshot(a.ap, a.world, extra)
    text = json.dumps(snap, ensure_ascii=False, indent=1)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
    n = sum(len(v["cells"]) for v in snap.values())
    print("[logic_snapshot] %d conjuntos de opciones × inventarios = %d celdas%s" % (
        len(snap), n, (" -> " + str(out_path)) if out_path else ""))


if __name__ == "__main__":
    main()
