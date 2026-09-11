#!/usr/bin/env python3
"""test_boss_logic.py - HERMETICITY test of the `boss_logic` option.

Checks, boss by boss, that a requirement set in the YAML really closes
everything behind that boss and NOTHING else:

  1. Per-boss scenario: only that boss asks for a "witness" item (a chip not
     needed for anything else) and the inventory has EVERYTHING but the
     witness. Its arena must end up out of logic, and the regions and
     locations it loses are reported (what the boss really gates).
  2. Positive control: with the witness in hand, that same scenario must
     give exactly the same as the logic without `boss_logic` (the requirement
     is an ADDITION: it can never open or close anything on its own).
  3. Hard scenario: all 15 bosses ask for the witness at once and it is not
     owned -> nothing behind a boss is in logic and the goal is unreachable.
  4. The eight Pseudoroids are fought twice: unable to beat one of them, the
     exit of the D-4 boss rush to Serpent must be closed.

Usage (from the apworld root):
  python test/test_boss_logic.py [--verbose]
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("mmzx_logic_probe", ROOT / "tools" / "logic_probe.py")
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)  # type: ignore[union-attr]

WITNESS = "Absorber Chip"       # witness item: no other rule uses it
WITNESS_ATOM = "Absorber Chip"  # written the same way in the YAML


class Harness:
    def __init__(self, ap_src, world_dir=None):
        self.world_type = _probe.load_core(ap_src, world_dir)
        from test.general import setup_multiworld
        from BaseClasses import CollectionState
        self._setup, self._State = setup_multiworld, CollectionState
        self.F = sys.modules["worlds.mmzx"].logic_format

    def run(self, boss_logic, without=(), options=None):
        """Reachability with the WHOLE pool except the items in `without`."""
        opts = dict(options or {})
        opts["boss_logic"] = boss_logic
        mw = self._setup(self.world_type, options=opts)
        world, player = mw.worlds[1], 1
        state = self._State(mw)
        drop = set(without)
        for name, v in sys.modules["worlds.mmzx"].data.ITEMS.items():
            if name in drop or v["classification"] == "filler" or not v.get("pooled", True):
                continue
            for _ in range(int(v.get("count", 1))):
                state.collect(world.create_item(name), prevent_sweep=True)
        state.sweep_for_advancements()
        state.update_reachable_regions(player)
        return {
            "regions": {r.name for r in state.reachable_regions[player]},
            "locs": {l.name for l in mw.get_locations(player)
                     if l.address is not None and l.can_reach(state)},
            "victory": bool(mw.completion_condition[player](state)),
        }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=_probe.DEFAULT_AP)
    ap.add_argument("--world", default=None)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    H = Harness(a.ap, a.world)
    F = H.F
    doc = sys.modules["worlds.mmzx"].regions.load_document()
    arenas = {b: (room, rid) for (room, rid), b in F.boss_regions(doc).items()}
    tagged = sorted(arenas)
    fails, notes = [], []

    # reference: without boss_logic and with everything
    base = H.run({})
    if not base["victory"]:
        fails.append("the reference without boss_logic does not win with all the items")
    print("reference (without boss_logic, whole pool): %d regions, %d locations, victory=%s"
          % (len(base["regions"]), len(base["locs"]), base["victory"]))

    # 1 + 2: one boss at a time
    print("\n== per boss (only that one asks for %r; inventory = everything but the witness)" % WITNESS)
    for bid in tagged:
        name = F.BOSSES[bid]["name"]
        room, rid = arenas[bid]
        arena = F.region_name(room, rid)
        cfg = {name: WITNESS_ATOM}
        off = H.run(cfg, without=[WITNESS])
        on = H.run(cfg)

        if arena in off["regions"]:
            fails.append("%s: its arena %s is STILL in logic without meeting the requirement" % (name, arena))
        lost_r = sorted(base["regions"] - off["regions"])
        lost_l = sorted(base["locs"] - off["locs"])
        if arena not in lost_r:
            fails.append("%s: arena %s does not show up as lost" % (name, arena))
        # positive control: with the witness, identical to the reference
        for key in ("regions", "locs"):
            if on[key] != base[key]:
                d = (base[key] ^ on[key])
                fails.append("%s: with the requirement met the logic is NOT equal to the "
                             "reference (%d different: %s)" % (name, len(d), sorted(d)[:5]))
        if on["victory"] != base["victory"]:
            fails.append("%s: with the requirement met the victory changes" % name)
        print("   %-22s closes %3d regions, %3d locations%s  victory=%s"
              % (name, len(lost_r), len(lost_l), "", off["victory"]))
        if a.verbose:
            print("        regions:   " + ", ".join(lost_r))
            print("        locations: " + ", ".join(lost_l))
        # 4: the Pseudoroids also close the boss rush -> Serpent
        if "index" in F.BOSSES[bid]:
            if off["victory"]:
                fails.append("%s: is a Pseudoroid and the goal is still reachable without beating it "
                             "(the D-4 boss rush should close the way to D-5)" % name)
            if "d05" in off["regions"] or any(r.startswith("d05/") for r in off["regions"]):
                fails.append("%s: D-5 is still reachable without beating it" % name)
        else:
            notes.append("%s: not a Pseudoroid; victory without it = %s" % (name, off["victory"]))

    # 3: all at once
    print("\n== all bosses require the witness and it is not owned")
    cfg_all = {F.BOSSES[b]["name"]: WITNESS_ATOM for b in tagged}
    off_all = H.run(cfg_all, without=[WITNESS])
    on_all = H.run(cfg_all)
    for bid in tagged:
        arena = F.region_name(*arenas[bid])
        if arena in off_all["regions"]:
            fails.append("all: arena %s (%s) is still in logic" % (arena, F.BOSSES[bid]["name"]))
    if off_all["victory"]:
        fails.append("all: the goal is still reachable without beating any boss")
    if on_all["regions"] != base["regions"] or on_all["locs"] != base["locs"]:
        fails.append("all: with the requirement met the logic does not match the reference")
    print("   without the witness: %d regions (%d fewer), %d locations (%d fewer), victory=%s"
          % (len(off_all["regions"]), len(base["regions"]) - len(off_all["regions"]),
             len(off_all["locs"]), len(base["locs"]) - len(off_all["locs"]), off_all["victory"]))
    print("   with the witness: identical to the reference = %s"
          % (on_all["regions"] == base["regions"] and on_all["locs"] == base["locs"]))

    # 5: paired biometals (each one comes from TWO bosses). With one blocked
    # it must stay in logic through the other; with both, out.
    print("\n== biometals: each one comes from two bosses")
    for letter, pair in (("H", ("hivolt", "hurricaune")), ("L", ("lurerre", "leganchor")),
                         ("F", ("fistleo", "flammole")), ("P", ("purprill", "protectos"))):
        loc = "Obtain Biometal " + letter
        if loc not in base["locs"]:
            fails.append("%s is not in logic even in the reference" % loc)
            continue
        if not all(b in arenas for b in pair):
            notes.append("%s: pair not fully anchored (%s)" % (loc, ", ".join(pair)))
            continue
        for b in pair:
            other = pair[0] if b == pair[1] else pair[1]
            r = H.run({F.BOSSES[b]["name"]: WITNESS_ATOM}, without=[WITNESS])
            if loc not in r["locs"]:
                fails.append("%s: blocking only %s takes it out of logic, but %s is still "
                             "available" % (loc, F.BOSSES[b]["name"], F.BOSSES[other]["name"]))
        both = H.run({F.BOSSES[b]["name"]: WITNESS_ATOM for b in pair}, without=[WITNESS])
        if loc in both["locs"]:
            fails.append("%s: still in logic with BOTH bosses (%s) blocked"
                         % (loc, ", ".join(F.BOSSES[b]["name"] for b in pair)))
        print("   %-20s one blocked: in logic | both: %s"
              % (loc, "OUT (ok)" if loc not in both["locs"] else "IN LOGIC (bad)"))

    print()
    for n in notes:
        print("note:", n)
    for f in fails:
        print("FAIL:", f)
    print("[test_boss_logic] %d bosses anchored, %d failures" % (len(tagged), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
