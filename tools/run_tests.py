#!/usr/bin/env python3
"""Run the unit tests of this world against an Archipelago source checkout.

Inside an Archipelago tree the tests run like any other world's
(python -m unittest discover -s worlds/mmzx/test -t .). This runner does the
same from the apworld folder: it loads the checkout given by --ap or $AP_SRC
(default: an ArchipelagoDW checkout beside the parent repository), registers
this package as worlds.mmzx and runs every test/test_*.py.

Usage (from the apworld root): python tools/run_tests.py [--ap PATH] [-v] [-k PATTERN]
"""
import argparse
import importlib
import pkgutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ap  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ap", default=_ap.DEFAULT_AP, help="Archipelago source checkout (0.6.7)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-k", "--pattern", default="test_*", help="glob of test modules to run (default: test_*)")
    a = ap.parse_args()

    _ap.load_core(a.ap)
    package = importlib.import_module("worlds.mmzx.test")
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if info.name.startswith("test_") and Path(info.name).match(a.pattern):
            suite.addTests(loader.loadTestsFromModule(importlib.import_module("worlds.mmzx.test." + info.name)))
    result = unittest.TextTestRunner(verbosity=2 if a.verbose else 1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
