#!/usr/bin/env python3
"""Validate logic/logic.json against data.py and regenerate logic/rules.py and logic/rules.json.

The generated files are rewritten errors included, so the world never generates from an old
logic in silence; --no-write skips them. Needs no Archipelago checkout.

Usage (from the apworld root): python tools/check_logic.py [--no-write] [--quiet]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ap  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    F, D, S = _ap.standalone_modules()
    W = F.build_world(D, S.SITES)
    path = _ap.ROOT / "logic" / "logic.json"
    doc = F.load_logic(path, W)
    rep = F.validate(W, doc, W["start_room"], F.unavailable_atoms(D))
    for e in rep["errors"]:
        print("ERROR:", e)
    if not a.quiet:
        for w in rep["warnings"]:
            print("warning:", w)
    n_regions = sum(len(r["regions"]) - 1 for r in doc["rooms"].values())
    n_conns = sum(len(r["conns"]) for r in doc["rooms"].values())
    print("[check_logic] %d rooms, %d regions, %d connections, %d checks with a rule, %d edges with a cost; "
          "%d errors, %d warnings, %d unsure, %d unplaced" % (
              len(doc["rooms"]), n_regions, n_conns, len(doc["checks"]), len(doc["edges"]),
              len(rep["errors"]), len(rep["warnings"]), rep["unsure"], rep["unplaced"]))
    if not a.no_write:
        try:
            F.write_generated(W, doc, path.parent, rep["errors"])
        except SyntaxError as e:
            print("ERROR: the generated rules.py does not compile and was not written:", e)
            sys.exit(1)
    sys.exit(1 if rep["errors"] else 0)


if __name__ == "__main__":
    main()
