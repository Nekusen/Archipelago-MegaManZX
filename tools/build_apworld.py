#!/usr/bin/env python3
"""build_apworld.py - packs this apworld into a `mmzx.apworld` file
(a zip with the package under `mmzx/`), ready for the `custom_worlds/` folder
of an Archipelago installation.

The whole package tree goes in except what must not travel (the same
patterns as `.apignore`: tools/, test/, build/, README, CHANGELOG and the
git metadata). Local assets ignored by git (tracker/images/, gfx/,
generated or extracted on your machine) DO go in if they are on disk.

Usage (from anywhere):
    python tools/build_apworld.py [--out build/mmzx.apworld]
"""

import argparse
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"tools", "test", "build", ".git", ".github", "__pycache__", "tracker/images"}
EXCLUDE_FILES = {"README.md", "CHANGELOG.md", ".gitignore", ".apignore", ".gitmodules", ".git"}


def wanted(p: Path) -> bool:
    if not p.is_file() or p.suffix == ".pyc":
        return False
    rel = p.relative_to(PKG)
    dirs = rel.parts[:-1]
    if any(part in EXCLUDE_DIRS for part in dirs):
        return False
    if any("/".join(dirs[:n]) in EXCLUDE_DIRS for n in range(2, len(dirs) + 1)):
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
    print("[build_apworld] %d files -> %s" % (len(files), out))
    for f in files:
        print("   mmzx/" + f.relative_to(PKG).as_posix())


if __name__ == "__main__":
    main()
