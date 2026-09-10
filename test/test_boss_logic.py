#!/usr/bin/env python3
"""test_boss_logic.py — prueba de HERMETICIDAD de la opción `boss_logic`.

Comprueba, jefe por jefe, que un requisito puesto en el YAML de verdad cierra
todo lo que está detrás de ese jefe y NADA más:

  1. Escenario por jefe: solo ese jefe pide un item "testigo" (un chip que no
     hace falta para ninguna otra cosa) y el inventario lo tiene TODO menos el
     testigo. Se exige que su arena quede fuera de lógica y se informa de qué
     regiones y locations pierde (lo que el jefe gatea de verdad).
  2. Control positivo: con el testigo en la mano, ese mismo escenario tiene
     que dar exactamente lo mismo que la lógica sin `boss_logic` (el requisito
     es un AÑADIDO: nunca puede abrir ni cerrar nada por su cuenta).
  3. Escenario duro: los 15 jefes piden el testigo a la vez y no se tiene ->
     nada que esté detrás de un jefe está en lógica y la meta es inalcanzable.
  4. Los ocho Pseudoroids se pelean dos veces: sin poder con uno de ellos, la
     salida del boss rush de D-4 a Serpent tiene que estar cerrada.

Uso (desde la raíz del apworld):
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

WITNESS = "Absorber Chip"       # item testigo: ninguna otra regla lo usa
WITNESS_ATOM = "Absorber Chip"  # se escribe igual en el YAML


class Harness:
    def __init__(self, ap_src, world_dir=None):
        self.world_type = _probe.load_core(ap_src, world_dir)
        from test.general import setup_multiworld
        from BaseClasses import CollectionState
        self._setup, self._State = setup_multiworld, CollectionState
        self.F = sys.modules["worlds.mmzx"].logic_format

    def run(self, boss_logic, without=(), options=None):
        """Alcanzabilidad con TODO el pool salvo los items de `without`."""
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

    # referencia: sin boss_logic y con todo
    base = H.run({})
    if not base["victory"]:
        fails.append("la referencia sin boss_logic no gana con todos los items")
    print("referencia (sin boss_logic, todo el pool): %d regiones, %d locations, victoria=%s"
          % (len(base["regions"]), len(base["locs"]), base["victory"]))

    # 1 + 2: un jefe cada vez
    print("\n== por jefe (solo ese pide %r; inventario = todo menos el testigo)" % WITNESS)
    for bid in tagged:
        name = F.BOSSES[bid]["name"]
        room, rid = arenas[bid]
        arena = F.region_name(room, rid)
        cfg = {name: WITNESS_ATOM}
        off = H.run(cfg, without=[WITNESS])
        on = H.run(cfg)

        if arena in off["regions"]:
            fails.append("%s: su arena %s SIGUE en lógica sin cumplir el requisito" % (name, arena))
        lost_r = sorted(base["regions"] - off["regions"])
        lost_l = sorted(base["locs"] - off["locs"])
        if arena not in lost_r:
            fails.append("%s: la arena %s no aparece como perdida" % (name, arena))
        # control positivo: con el testigo, idéntico a la referencia
        for key in ("regions", "locs"):
            if on[key] != base[key]:
                d = (base[key] ^ on[key])
                fails.append("%s: con el requisito cumplido la lógica NO es igual a la de "
                             "referencia (%d de diferencia: %s)" % (name, len(d), sorted(d)[:5]))
        if on["victory"] != base["victory"]:
            fails.append("%s: con el requisito cumplido cambia la victoria" % name)
        print("   %-22s cierra %3d regiones, %3d locations%s  victoria=%s"
              % (name, len(lost_r), len(lost_l), "", off["victory"]))
        if a.verbose:
            print("        regiones:  " + ", ".join(lost_r))
            print("        locations: " + ", ".join(lost_l))
        # 4: los Pseudoroids también cierran el boss rush -> Serpent
        if "index" in F.BOSSES[bid]:
            if off["victory"]:
                fails.append("%s: es un Pseudoroid y la meta sigue alcanzable sin poder con él "
                             "(el boss rush de D-4 debería cerrar el paso a D-5)" % name)
            if "d05" in off["regions"] or any(r.startswith("d05/") for r in off["regions"]):
                fails.append("%s: D-5 sigue alcanzable sin poder con él" % name)
        else:
            notes.append("%s: no es Pseudoroid; victoria sin él = %s" % (name, off["victory"]))

    # 3: todos a la vez
    print("\n== todos los jefes exigen el testigo y no se tiene")
    cfg_all = {F.BOSSES[b]["name"]: WITNESS_ATOM for b in tagged}
    off_all = H.run(cfg_all, without=[WITNESS])
    on_all = H.run(cfg_all)
    for bid in tagged:
        arena = F.region_name(*arenas[bid])
        if arena in off_all["regions"]:
            fails.append("todos: la arena %s (%s) sigue en lógica" % (arena, F.BOSSES[bid]["name"]))
    if off_all["victory"]:
        fails.append("todos: la meta sigue alcanzable sin poder con ningún jefe")
    if on_all["regions"] != base["regions"] or on_all["locs"] != base["locs"]:
        fails.append("todos: con el requisito cumplido la lógica no coincide con la de referencia")
    print("   sin el testigo: %d regiones (%d menos), %d locations (%d menos), victoria=%s"
          % (len(off_all["regions"]), len(base["regions"]) - len(off_all["regions"]),
             len(off_all["locs"]), len(base["locs"]) - len(off_all["locs"]), off_all["victory"]))
    print("   con el testigo: idéntico a la referencia = %s"
          % (on_all["regions"] == base["regions"] and on_all["locs"] == base["locs"]))

    # 5: biometales de par (cada uno sale de DOS jefes). Con uno bloqueado
    # tiene que seguir en lógica por el otro; con los dos, fuera.
    print("\n== biometales: cada uno sale de dos jefes")
    for letter, pair in (("H", ("hivolt", "hurricaune")), ("L", ("lurerre", "leganchor")),
                         ("F", ("fistleo", "flammole")), ("P", ("purprill", "protectos"))):
        loc = "Obtain Biometal " + letter
        if loc not in base["locs"]:
            fails.append("%s no está en lógica ni en la referencia" % loc)
            continue
        if not all(b in arenas for b in pair):
            notes.append("%s: par sin anclar del todo (%s)" % (loc, ", ".join(pair)))
            continue
        for b in pair:
            other = pair[0] if b == pair[1] else pair[1]
            r = H.run({F.BOSSES[b]["name"]: WITNESS_ATOM}, without=[WITNESS])
            if loc not in r["locs"]:
                fails.append("%s: bloqueando solo a %s deja de estar en lógica, pero %s sigue "
                             "disponible" % (loc, F.BOSSES[b]["name"], F.BOSSES[other]["name"]))
        both = H.run({F.BOSSES[b]["name"]: WITNESS_ATOM for b in pair}, without=[WITNESS])
        if loc in both["locs"]:
            fails.append("%s: sigue en lógica con los DOS jefes (%s) bloqueados"
                         % (loc, ", ".join(F.BOSSES[b]["name"] for b in pair)))
        print("   %-20s uno bloqueado: en lógica · los dos: %s"
              % (loc, "FUERA (ok)" if loc not in both["locs"] else "EN LÓGICA (mal)"))

    print()
    for n in notes:
        print("nota:", n)
    for f in fails:
        print("FALLO:", f)
    print("[test_boss_logic] %d jefes anclados, %d fallos" % (len(tagged), len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
