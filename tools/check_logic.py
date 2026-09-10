#!/usr/bin/env python3
"""check_logic.py — valida logic/logic.json del apworld contra data.py
(regiones, conexiones, átomos, colocaciones, regiones sin entrada) y
regenera logic.txt si no hay errores.
Uso (desde la raíz del apworld): python tools/check_logic.py [--no-txt]"""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))   # appended last: vendored packages must not shadow the venv
import logic_format as F  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-txt", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location("mmzx_data_chk", ROOT / "data.py")
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)  # type: ignore[union-attr]
    W = F.build_world(D)
    path = ROOT / "logic" / "logic.json"
    doc = F.load_logic(path, W)
    rep = F.validate(W, doc, D.HUB_ROOM, F.unavailable_atoms(D))
    for e in rep["errors"]:
        print("ERROR:", e)
    if not a.quiet:
        for w in rep["warnings"]:
            print("aviso:", w)
    n_regions = sum(len(r["regions"]) - 1 for r in doc["rooms"].values())
    n_conns = sum(len(r["conns"]) for r in doc["rooms"].values())
    print("[check_logic] %d salas, %d regiones, %d conexiones, %d checks con regla, %d aristas con coste; "
          "%d errores, %d avisos, %d sin confirmar, %d sin colocar" % (
              len(doc["rooms"]), n_regions, n_conns, len(doc["checks"]), len(doc["edges"]),
              len(rep["errors"]), len(rep["warnings"]), rep["unsure"], rep["unplaced"]))
    if not rep["errors"] and not a.no_txt:
        (path.parent / "logic.txt").write_text(F.export_txt(W, doc, D.HUB_ROOM), encoding="utf-8", newline="\n")
    sys.exit(1 if rep["errors"] else 0)


if __name__ == "__main__":
    main()
