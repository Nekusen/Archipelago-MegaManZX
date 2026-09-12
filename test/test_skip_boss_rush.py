#!/usr/bin/env python3
"""Check that skip_boss_rush changes only the D-4 tower in the logic.

Without the option an unbeatable Pseudoroid blocks the victory through the boss
rush; with it, only the story fight closes, Hub-2 leaves the graph and nothing
else moves. Needs an Archipelago source checkout (--ap or $AP_SRC).

Usage (from the apworld root): python test/test_skip_boss_rush.py [--verbose]
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("mmzx_test_boss_logic", ROOT / "test" / "test_boss_logic.py")
_tbl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tbl)  # type: ignore[union-attr]

WITNESS = _tbl.WITNESS


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=_tbl._probe.DEFAULT_AP)
    ap.add_argument("--world", default=None)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    H = _tbl.Harness(a.ap, a.world)
    F = H.F
    hub2 = F.region_name("z02", "main")
    fails = []

    base = H.run({})
    skip = H.run({}, options={"skip_boss_rush": True})
    print("reference: %d regions, %d locations, victory=%s" % (len(base["regions"]), len(base["locs"]), base["victory"]))
    print("skip_boss_rush: %d regions, %d locations, victory=%s" % (len(skip["regions"]), len(skip["locs"]), skip["victory"]))
    if hub2 not in base["regions"]:
        fails.append("reference: z02 (%s) is not in logic with the whole pool" % hub2)
    if hub2 in skip["regions"]:
        fails.append("skip: z02 (%s) is still in logic (the teleporters must be off)" % hub2)
    if (base["regions"] - {hub2}) != skip["regions"]:
        d = (base["regions"] - {hub2}) ^ skip["regions"]
        fails.append("skip: regions differ from the reference (apart from z02): %s" % sorted(d)[:8])
    if base["locs"] != skip["locs"]:
        d = base["locs"] ^ skip["locs"]
        fails.append("skip: locations differ from the reference: %s" % sorted(d)[:8])
    if not skip["victory"]:
        fails.append("skip: no victory with the whole pool")

    # a Pseudoroid with an unmeetable requirement: the witness is not owned
    for bid in F.PSEUDOROIDS:
        name = F.BOSSES[bid]["name"]
        cfg = {name: WITNESS}
        off = H.run(cfg, without=[WITNESS])
        on = H.run(cfg, without=[WITNESS], options={"skip_boss_rush": True})
        arena = next((F.region_name(r, rid) for (r, rid), b in F.boss_regions(
            sys.modules["worlds.mmzx"].regions.load_document()).items() if b == bid), None)
        if off["victory"]:
            fails.append("%s impossible WITHOUT skip: the victory is still in logic (the boss rush should require it)" % name)
        if not on["victory"]:
            fails.append("%s impossible WITH skip: the victory is NOT in logic (the boss rush must no longer require it)" % name)
        if arena and arena in on["regions"]:
            fails.append("%s impossible WITH skip: its story arena %s is still in logic" % (name, arena))
        if a.verbose:
            print("  %-11s without skip: victory=%s | with skip: victory=%s, arena %s in logic=%s"
                  % (name, off["victory"], on["victory"], arena, arena in on["regions"]))

    for f in fails:
        print("FAIL:", f)
    print("[test_skip_boss_rush] %d failures" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
