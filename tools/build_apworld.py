#!/usr/bin/env python3
"""build_apworld.py — empaqueta este apworld en un fichero `mmzx.apworld`
(un zip con el paquete bajo `mmzx/`), listo para la carpeta `custom_worlds/`
de una instalación de Archipelago.

Entra todo el árbol del paquete salvo lo que no debe viajar (los mismos
patrones que `.apignore`: tools/, test/, build/, README, CHANGELOG y los
metadatos de git). Los assets locales que git ignora (tracker/images/,
gfx/, generados o extraídos en tu máquina) SÍ entran si están en disco.

Uso (desde cualquier sitio):
    python tools/build_apworld.py [--out build/mmzx.apworld]
"""

import argparse
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"tools", "test", "build", ".git", ".github", "__pycache__"}
EXCLUDE_FILES = {"README.md", "CHANGELOG.md", ".gitignore", ".apignore", ".gitmodules", ".git"}


def wanted(p: Path) -> bool:
    if not p.is_file() or p.suffix == ".pyc":
        return False
    rel = p.relative_to(PKG)
    if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
        return False
    if len(rel.parts) == 1 and rel.name in EXCLUDE_FILES:
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(PKG / "build" / "mmzx.apworld"))
    a = ap.parse_args()

    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in PKG.rglob("*") if wanted(p))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, "mmzx/" + f.relative_to(PKG).as_posix())
    print("[build_apworld] %d ficheros -> %s" % (len(files), out))
    for f in files:
        print("   mmzx/" + f.relative_to(PKG).as_posix())


if __name__ == "__main__":
    main()
