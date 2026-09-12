#!/usr/bin/env python3
"""Snapshot of the logic over a matrix of option sets and inventories.

Stores the reachable regions and the locations in logic of every cell, so that
--compare can prove that a change alters nothing it should not. Needs an
Archipelago source checkout (--ap or $AP_SRC).

Usage (from the apworld root):
  python tools/logic_snapshot.py --out build/base.json
  python tools/logic_snapshot.py --compare build/base.json build/new.json
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ap  # noqa: E402

# option sets to evaluate: name to YAML options
OPTION_SETS = {
    "default": {},
    "expert": {"logic_difficulty": "expert"},
    "hu_in_pool": {"hu_in_pool": True},
    "no_start_model": {"starting_model": "none"},
}
# items of the fixed inventories; a full biometal is two halves
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
    # deterministic random subsets over the progression pool
    pool = sorted(set(["Model X", "Model ZX", "Model OX"] + HALVES + KEYS + access))
    rng = random.Random(20260904)
    for i in range(8):
        k = rng.randint(2, len(pool) - 2)
        inv["rnd%d" % i] = sorted(rng.sample(pool, k))
    return inv


def snapshot(ap_src, world_dir=None, extra_options=None):
    world_type = _ap.load_core(ap_src, world_dir)
    out = {}
    sets = dict(OPTION_SETS)
    for name, opts in (extra_options or {}).items():
        sets[name] = opts
    for set_name, opts in sets.items():
        mw = _ap.solo_multiworld(world_type, opts)
        world = mw.worlds[1]
        inventories = fixed_inventories(list(world.item_name_to_id))
        cell = {}
        for inv_name, items in inventories.items():
            state, _unknown = _ap.collect_state(mw, items)   # unknown names are skipped
            logic = _ap.in_logic(mw, state)
            cell[inv_name] = {
                "items": sorted(items),
                "regions": logic["regions"],
                "locs_in": logic["locs_in"],
                "victory": logic["victory"],
            }
        # classification of every pool item
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
            diffs.append("option set only in one of them: %s" % set_name)
            continue
        ca, cb = a[set_name], b[set_name]
        for it in sorted(set(ca["classification"]) | set(cb["classification"])):
            xa, xb = ca["classification"].get(it), cb["classification"].get(it)
            if xa != xb:
                diffs.append("[%s] classification of %r: %s -> %s" % (set_name, it, xa, xb))
        for inv in sorted(set(ca["cells"]) | set(cb["cells"])):
            da, db = ca["cells"].get(inv, {}), cb["cells"].get(inv, {})
            for key in ("regions", "locs_in"):
                sa, sb = set(da.get(key, [])), set(db.get(key, []))
                for x in sorted(sa - sb):
                    diffs.append("[%s/%s] %s LOST: %s" % (set_name, inv, key, x))
                for x in sorted(sb - sa):
                    diffs.append("[%s/%s] %s NEW: %s" % (set_name, inv, key, x))
            if da.get("victory") != db.get("victory"):
                diffs.append("[%s/%s] victory: %s -> %s" % (set_name, inv, da.get("victory"), db.get("victory")))
    return diffs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=_ap.DEFAULT_AP)
    ap.add_argument("--world", default=None)
    ap.add_argument("--out", default=None, help="save the snapshot here")
    ap.add_argument("--compare", nargs=2, metavar=("BASE", "NEW"))
    ap.add_argument("--opts", default=None, help="JSON {name: {options}} with extra sets")
    a = ap.parse_args()

    if a.compare:
        base = json.loads(Path(a.compare[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(a.compare[1]).read_text(encoding="utf-8"))
        diffs = compare(base, new)
        for d in diffs:
            print(d)
        print("[logic_snapshot] %d differences" % len(diffs))
        sys.exit(1 if diffs else 0)

    extra = json.loads(a.opts) if a.opts else None
    out_path = Path(a.out).resolve() if a.out else None   # before the loader's chdir
    snap = snapshot(a.ap, a.world, extra)
    text = json.dumps(snap, ensure_ascii=False, indent=1)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
    n = sum(len(v["cells"]) for v in snap.values())
    print("[logic_snapshot] %d option sets x inventories = %d cells%s" % (
        len(snap), n, (" -> " + str(out_path)) if out_path else ""))


if __name__ == "__main__":
    main()
