"""Archipelago source checkout and world loading shared by the tools.

The tools run from the apworld folder, outside any Archipelago tree, so they
cannot import the core the usual way. load_core() puts a checkout on sys.path,
imports the core and registers this package as worlds.mmzx. standalone_modules()
loads logic/document.py and data.py by path for the tools that need no Archipelago
at all. The rest wraps the one-player multiworld the logic tools evaluate.
"""
import contextlib
import importlib.util
import io
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # apworld root
GAME = "Mega Man ZX"


def default_ap_src() -> str:
    """Archipelago source checkout: $AP_SRC, else a checkout beside the parent repository."""
    if os.environ.get("AP_SRC"):
        return os.environ["AP_SRC"]
    try:
        siblings = sorted(Path(__file__).resolve().parents[4].iterdir())
    except (IndexError, OSError):
        return ""
    for cand in siblings:
        if cand.is_dir() and (cand / "BaseClasses.py").is_file():
            return str(cand)
    return ""


DEFAULT_AP = default_ap_src()


def _module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def standalone_modules():
    """(logic.document, data) loaded by path; neither imports anything from Archipelago."""
    return (_module_from_path("mmzx_logic_document", ROOT / "logic" / "document.py"),
            _module_from_path("mmzx_data", ROOT / "data.py"))


def load_core(ap_src: str, world_dir=None):
    """Import the Archipelago core and register this package as worlds.mmzx; returns the world class.

    Only the generic world of the checkout is loaded. The cwd moves to the checkout
    during the imports and is always restored, so resolve any output path before calling.
    """
    if not ap_src:
        raise SystemExit("an Archipelago source checkout is needed: --ap PATH or the AP_SRC variable")
    if not (Path(ap_src) / "BaseClasses.py").is_file():
        raise SystemExit("not an Archipelago source checkout: %s" % ap_src)
    ap_src = str(Path(ap_src).resolve())
    wdir = Path(world_dir).resolve() if world_dir else ROOT   # before the chdir
    sys.path.insert(0, ap_src)
    logging.disable(logging.CRITICAL)
    # worlds/__init__.py imports every world of the checkout: hide all but 'generic'
    real_scandir = os.scandir
    worlds_dir = os.path.normcase(os.path.join(ap_src, "worlds"))

    def scandir_only_generic(path=".", *a, **k):
        it = real_scandir(path, *a, **k)
        if os.path.normcase(os.path.abspath(str(path))) != worlds_dir:
            return it
        return iter([e for e in it if e.name == "generic"])

    prev_cwd = os.getcwd()
    os.chdir(ap_src)   # AP reads host.yaml and data/ from the cwd
    os.scandir = scandir_only_generic
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            import BaseClasses  # noqa: F401
            from worlds.AutoWorld import AutoWorldRegister
        os.scandir = real_scandir
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            spec = importlib.util.spec_from_file_location(
                "worlds.mmzx", str(wdir / "__init__.py"), submodule_search_locations=[str(wdir)])
            module = importlib.util.module_from_spec(spec)
            sys.modules["worlds.mmzx"] = module
            spec.loader.exec_module(module)  # type: ignore[union-attr]
    finally:
        os.scandir = real_scandir
        os.chdir(prev_cwd)   # never leave the process inside the AP checkout
    logging.disable(logging.NOTSET)
    return AutoWorldRegister.world_types[GAME]


def solo_multiworld(world_type, options=None):
    """One-player multiworld of world_type with the given YAML options, generated through pre_fill."""
    from test.general import setup_multiworld
    return setup_multiworld(world_type, options=dict(options or {}))


def collect_state(multiworld, item_names, player=1):
    """State with the named items collected and the events swept; returns (state, unknown names)."""
    from BaseClasses import CollectionState
    world = multiworld.worlds[player]
    state = CollectionState(multiworld)
    unknown = []
    for name in item_names:
        if name in world.item_name_to_id:
            state.collect(world.create_item(name), prevent_sweep=True)
        else:
            unknown.append(name)
    state.sweep_for_advancements()
    state.update_reachable_regions(player)
    return state, unknown


def in_logic(multiworld, state, player=1) -> dict:
    """What a state reaches: sorted region names, locations in and out of logic, victory."""
    locations = [loc for loc in multiworld.get_locations(player) if loc.address is not None]
    return {
        "regions": sorted(r.name for r in state.reachable_regions[player]),
        "locs_in": sorted(loc.name for loc in locations if loc.can_reach(state)),
        "locs_out": sorted(loc.name for loc in locations if not loc.can_reach(state)),
        "victory": bool(multiworld.completion_condition[player](state)),
    }
