#!/usr/bin/env python3
"""tag_bosses.py — migración del documento de lógica para la dificultad de
jefes configurable desde el YAML (opción boss_logic, 2026-09-04).

Hace tres cosas sobre logic/logic.json (idempotente):

 1. ETIQUETA como arena de jefe la región dibujada de cada uno de los 15
    jefes del roster (`logic_format.BOSSES`). Si el editor cambia el nombre
    de una región hay que actualizar ARENAS aquí.
 2. QUITA el requisito SUBTANK/LIFEUP que estaba cableado a mano en la
    puerta de Omega Zero (n01): ese ajuste pasa a ser del jugador.
 3. ANCLA el boss rush de D-4: cada una de las 8 puertas al z02 exige su
    Pseudoroid, y la salida a D-5 (Serpent) exige los 8 — el juego no deja
    pasar sin vencerlos, y además un jefe exigido lo es en sus DOS
    encuentros.

Uso (desde la raíz):  python tools/tag_bosses.py [--dry-run]
Después:              python tools/check_logic.py     (regenera logic.txt)
"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
import logic_format as F  # noqa: E402

# jefe -> (sala, nombre de la región dibujada que es su arena)
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
# Sin arena dibujada (ninguna desde 2026-09-04: el usuario dibujó B-2, F-5
# y G-5; Giga Aspis salió del roster por ser el jefe del tutorial saltado).
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

    # 1. etiquetas de arena
    for boss, (room, region_name) in ARENAS.items():
        regs = doc["rooms"][room]["regions"]
        rid = next((k for k, v in regs.items() if v.get("name") == region_name), None)
        if rid is None:
            print("!! %s: no encuentro la región %r en %s" % (boss, region_name, room))
            continue
        if regs[rid].get("boss") != boss:
            regs[rid]["boss"] = boss
            changes.append("arena %s/%s = %s" % (room, rid, F.BOSSES[boss]["name"]))

    # 2. Omega Zero: fuera el SUBTANK/LIFEUP cableado
    ov = doc["edges"].get(OMEGA_DOOR)
    if ov is not None and ov.get("req") != {"normal": [["MODEL"]]}:
        ov["req"] = {"normal": [["MODEL"]]}
        changes.append("%s: requisito -> MODEL (el Sub Tank / Life Up lo pone el YAML)" % OMEGA_DOOR)

    # 3. boss rush de D-4
    by_index = {F.BOSSES[b]["index"]: b for b in F.PSEUDOROIDS}
    for door, idx in F.BOSS_RUSH_DOORS.items():
        boss = by_index[idx]
        req = {"normal": [[F.boss_atom(boss)]]}
        cur = doc["edges"].setdefault(door, {"req": None, "note": "", "unsure": False,
                                             "pos": None, "dst_pos": None})
        if cur.get("req") != req:
            cur["req"] = req
            cur["note"] = cur.get("note") or "re-pelea del boss rush (teletransportador arg %02X)" % idx
            changes.append("%s: %s" % (door, F.BOSSES[boss]["name"]))
    exit_req = {"normal": [[F.boss_atom(b) for b in F.PSEUDOROIDS]]}
    cur = doc["edges"].setdefault(F.BOSS_RUSH_EXIT, {"req": None, "note": "", "unsure": False,
                                                     "pos": None, "dst_pos": None})
    if cur.get("req") != exit_req:
        cur["req"] = exit_req
        cur["note"] = cur.get("note") or ("la torre solo deja pasar a D-5 tras el boss rush: "
                                          "exige los 8 Pseudoroids")
        changes.append("%s: los 8 Pseudoroids" % F.BOSS_RUSH_EXIT)

    for c in changes:
        print("  ·", c)
    print("[tag_bosses] %d cambios%s" % (len(changes), " (dry-run, sin escribir)" if a.dry_run else ""))
    if PENDING:
        print("[tag_bosses] sin arena dibujada (pendientes en el editor): %s" % ", ".join(
            "%s (%s)" % (F.BOSSES[b]["name"], F.BOSSES[b]["room"]) for b in PENDING))
    if changes and not a.dry_run:
        F.save_logic(path, doc)


if __name__ == "__main__":
    main()
