#!/usr/bin/env python3
"""test_skip_boss_rush.py — la opción QoL `skip_boss_rush` en la LÓGICA.

Comprueba, con el core de AP (tools/logic_probe.py::load_core) y sin generar
seed, que:
  1. sin la opción, un Pseudoroid con requisito imposible en `boss_logic`
     bloquea la victoria (el juego obliga a superar el boss rush: exige a los
     ocho para pasar de D-4 a D-5) y las 8 puertas a z02 existen;
  2. con la opción, el mismo requisito ya NO bloquea la victoria (solo su
     pelea de historia), z02 (Hub-2) desaparece del grafo y, salvo z02, la
     lógica con todo el pool es idéntica a la de referencia;
  3. con la opción y sin boss_logic, la lógica es idéntica a la de referencia
     salvo z02 (0 locations ganadas o perdidas).

Uso (desde la raíz del apworld): python test/test_skip_boss_rush.py [--verbose]
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
    print("referencia: %d regiones, %d locations, victoria=%s" % (len(base["regions"]), len(base["locs"]), base["victory"]))
    print("skip_boss_rush: %d regiones, %d locations, victoria=%s" % (len(skip["regions"]), len(skip["locs"]), skip["victory"]))
    if hub2 not in base["regions"]:
        fails.append("referencia: z02 (%s) no está en lógica con todo el pool" % hub2)
    if hub2 in skip["regions"]:
        fails.append("skip: z02 (%s) sigue en lógica (los teletransportadores deben estar apagados)" % hub2)
    if (base["regions"] - {hub2}) != skip["regions"]:
        d = (base["regions"] - {hub2}) ^ skip["regions"]
        fails.append("skip: regiones distintas de la referencia (aparte de z02): %s" % sorted(d)[:8])
    if base["locs"] != skip["locs"]:
        d = base["locs"] ^ skip["locs"]
        fails.append("skip: locations distintas de la referencia: %s" % sorted(d)[:8])
    if not skip["victory"]:
        fails.append("skip: no hay victoria con todo el pool")

    # un Pseudoroid con requisito imposible (testigo fuera del inventario)
    for bid in F.PSEUDOROIDS:
        name = F.BOSSES[bid]["name"]
        cfg = {name: WITNESS}
        off = H.run(cfg, without=[WITNESS])
        on = H.run(cfg, without=[WITNESS], options={"skip_boss_rush": True})
        arena = next((F.region_name(r, rid) for (r, rid), b in F.boss_regions(
            sys.modules["worlds.mmzx"].regions.load_document()).items() if b == bid), None)
        if off["victory"]:
            fails.append("%s imposible SIN skip: la victoria sigue en lógica (el boss rush debería exigirlo)" % name)
        if not on["victory"]:
            fails.append("%s imposible CON skip: la victoria NO está en lógica (el boss rush ya no debe exigirlo)" % name)
        if arena and arena in on["regions"]:
            fails.append("%s imposible CON skip: su arena de historia %s sigue en lógica" % (name, arena))
        if a.verbose:
            print("  %-11s sin skip: victoria=%s | con skip: victoria=%s, arena %s en lógica=%s"
                  % (name, off["victory"], on["victory"], arena, arena in on["regions"]))

    for f in fails:
        print("FALLO:", f)
    print("[test_skip_boss_rush] %d fallos" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
