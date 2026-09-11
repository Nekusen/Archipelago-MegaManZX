#!/usr/bin/env python3
"""tag_bosses.py - migration of the logic document for the YAML-configurable
boss difficulty (boss_logic option, 2026-09-04).

Does three things to logic/logic.json (idempotent):

 1. TAGS as boss arena the drawn region of each of the 15 bosses of the
    roster (`logic_format.BOSSES`). If the editor renames a region, ARENAS
    has to be updated here.
 2. REMOVES the SUBTANK/LIFEUP requirement that was hard-wired on the
    Omega Zero door (n01): that setting is now up to the player.
 3. ANCHORS the D-4 boss rush: each of the 8 doors to z02 requires its
    Pseudoroid, and the exit to D-5 (Serpent) requires all 8 - the game does
    not let you through without beating them, and besides, a required boss
    is required in BOTH of its encounters.

Usage (from the root):  python tools/tag_bosses.py [--dry-run]
Then:                   python tools/check_logic.py     (regenerates logic.txt)
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import logic_format as F  # noqa: E402

# boss -> (room, name of the drawn region that is its arena)
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
# Without a drawn arena (none since 2026-09-04: the user drew B-2, F-5 and
# G-5; Giga Aspis left the roster for being the boss of the skipped tutorial).
PENDING = []
OMEGA_DOOR = "n01 door (3520,512)"      # Omega Zero Door -> Omega Zero Arena


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

    # 1. arena tags
    for boss, (room, region_name) in ARENAS.items():
        regs = doc["rooms"][room]["regions"]
        rid = next((k for k, v in regs.items() if v.get("name") == region_name), None)
        if rid is None:
            print("!! %s: cannot find region %r in %s" % (boss, region_name, room))
            continue
        if regs[rid].get("boss") != boss:
            regs[rid]["boss"] = boss
            changes.append("arena %s/%s = %s" % (room, rid, F.BOSSES[boss]["name"]))

    # 2. Omega Zero: drop the hard-wired SUBTANK/LIFEUP
    ov = doc["edges"].get(OMEGA_DOOR)
    if ov is not None and ov.get("req") != {"normal": [["MODEL"]]}:
        ov["req"] = {"normal": [["MODEL"]]}
        changes.append("%s: requirement -> MODEL (the Sub Tank / Life Up comes from the YAML)" % OMEGA_DOOR)

    # 3. D-4 boss rush
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
