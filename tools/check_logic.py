#!/usr/bin/env python3
"""Validate logic/logic.json against data.py and regenerate logic.txt.

The text twin is rewritten only when there are no errors; --no-txt skips it.
Needs no Archipelago checkout.

Usage (from the apworld root): python tools/check_logic.py [--no-txt] [--quiet]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ap  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-txt", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    F, D = _ap.standalone_modules()
    W = F.build_world(D)
    path = _ap.ROOT / "logic" / "logic.json"
    doc = F.load_logic(path, W)
    rep = F.validate(W, doc, D.HUB_ROOM, F.unavailable_atoms(D))
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
    if not rep["errors"] and not a.no_txt:
        (path.parent / "logic.txt").write_text(F.export_txt(W, doc, D.HUB_ROOM), encoding="utf-8", newline="\n")
    sys.exit(1 if rep["errors"] else 0)


if __name__ == "__main__":
    main()
