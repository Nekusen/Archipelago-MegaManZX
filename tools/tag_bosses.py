#!/usr/bin/env python3
"""Tag the boss arenas of logic/logic.json and anchor the D-4 boss rush.

Tags the drawn region of each boss in ARENAS as its arena, leaves the Omega Zero
door with a bare model requirement, and makes each boss rush door require its
Pseudoroid and the exit to D-5 require all eight. Idempotent; the current
document already has all of it. Run check_logic.py afterwards for logic.txt.

Usage (from the apworld root): python tools/tag_bosses.py [--dry-run]
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import logic_format as F  # noqa: E402

# boss id: (room, name of the drawn region that is its arena)
ARENAS = {
    "rayfly": ("b02", "Boss Arena"),
    "lurerre": ("f05", "Boss Arena"),
    "fistleo": ("g05", "Boss Area"),
    "model_z": ("d02", "Boss Room"),
    "serpent": ("d05", "Boss Room"),
    "hivolt": ("e07", "Boss Room"),
    "purprill": ("h04", "Boss Room"),
    "hurricaune": ("i03", "Boss Room"),
    "leganchor": ("j05", "Boss Room"),
    "flammole": ("k04", "Boss Room"),
    "protectos": ("l04", "Boss Room"),
    "pandora": ("m03", "Boss Room"),
    "prometheus_pandora": ("o02", "Boss Room"),
    "prometheus": ("x03", "Boss Room"),
    "omega_zero": ("n01", "Omega Zero Arena"),
}
# bosses of the roster without a drawn arena
PENDING = []
OMEGA_DOOR = "n01 door (3520,512)"


def load_data():
    spec = importlib.util.spec_from_file_location("mmzx_data_tag", ROOT / "data.py")
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)  # type: ignore[union-attr]
    return D


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    D = load_data()
    world = F.build_world(D)
    path = ROOT / "logic" / "logic.json"
    doc = F.load_logic(path, world)
    changes = []

    # arena tags
    for boss, (room, region_name) in ARENAS.items():
        regs = doc["rooms"][room]["regions"]
        rid = next((k for k, v in regs.items() if v.get("name") == region_name), None)
        if rid is None:
            print("!! %s: cannot find region %r in %s" % (boss, region_name, room))
            continue
        if regs[rid].get("boss") != boss:
            regs[rid]["boss"] = boss
            changes.append("arena %s/%s = %s" % (room, rid, F.BOSSES[boss]["name"]))

    # Omega Zero door: drop the hard-wired Sub Tank / Life Up
    ov = doc["edges"].get(OMEGA_DOOR)
    if ov is not None and ov.get("req") != {"normal": [["MODEL"]]}:
        ov["req"] = {"normal": [["MODEL"]]}
        changes.append("%s: requirement -> MODEL (the Sub Tank / Life Up comes from the YAML)" % OMEGA_DOOR)

    # D-4 boss rush
    by_index = {F.BOSSES[b]["index"]: b for b in F.PSEUDOROIDS}
    for door, idx in F.BOSS_RUSH_DOORS.items():
        boss = by_index[idx]
        req = {"normal": [[F.boss_atom(boss)]]}
        cur = doc["edges"].setdefault(door, {"req": None, "note": "", "unsure": False,
                                             "pos": None, "dst_pos": None})
        if cur.get("req") != req:
            cur["req"] = req
            cur["note"] = cur.get("note") or "boss rush rematch (teleporter arg %02X)" % idx
            changes.append("%s: %s" % (door, F.BOSSES[boss]["name"]))
    exit_req = {"normal": [[F.boss_atom(b) for b in F.PSEUDOROIDS]]}
    cur = doc["edges"].setdefault(F.BOSS_RUSH_EXIT, {"req": None, "note": "", "unsure": False,
                                                     "pos": None, "dst_pos": None})
    if cur.get("req") != exit_req:
        cur["req"] = exit_req
        cur["note"] = cur.get("note") or ("the tower only lets you through to D-5 after the boss rush: "
                                          "requires all 8 Pseudoroids")
        changes.append("%s: all 8 Pseudoroids" % F.BOSS_RUSH_EXIT)

    for c in changes:
        print("  -", c)
    print("[tag_bosses] %d changes%s" % (len(changes), " (dry-run, nothing written)" if a.dry_run else ""))
    if PENDING:
        print("[tag_bosses] no drawn arena (pending in the editor): %s" % ", ".join(
            "%s (%s)" % (F.BOSSES[b]["name"], F.BOSSES[b]["room"]) for b in PENDING))
    if changes and not a.dry_run:
        F.save_logic(path, doc)


if __name__ == "__main__":
    main()
