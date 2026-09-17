# Mega Man ZX for Archipelago

An [Archipelago](https://archipelago.gg) world for Mega Man ZX (Nintendo DS, 2006), played on BizHawk with the melonDS
core. The game becomes an open world: biometals, Card Keys and Transerver destinations are items, and disks, upgrades,
boss fights and missions are checks.

## Playing

- Setup guide: [docs/setup_en.md](docs/setup_en.md).
- What the randomizer does and how the options work: [docs/en_Mega Man ZX.md](docs/en_Mega%20Man%20ZX.md).

You need Archipelago 0.6.7 or later, BizHawk 2.10 or later with its NDS core, and your own Mega Man ZX (USA) ROM (game code
`ARZE`). Everything the randomizer needs is read from that ROM at patch time; this repository ships no ROM, game code
or game asset. Download `mmzx.apworld` from the
[Releases](https://github.com/Nekusen/Archipelago-MegaManZX/releases) page.

## Universal Tracker

The world ships the map layout for Universal Tracker (the game's world map, one map per area and per room, auto-tab
and player position).
The map images come from the separate [MegaManZX-Tracker](https://github.com/Nekusen/MegaManZX-Tracker) pack, which
UT loads from a zip you download once (`ut_pack_path` in `host.yaml`).

## Project structure

    __init__.py                 World, WebWorld and host settings (ROM path, tracker pack path)
    options.py                  YAML options; their docstrings are the player's option help
    items.py, locations.py      item and location classes, groups and option filters over data.py
    regions.py                  regions, entrances, locations and events from the logic document
    data.py                     generated tables that every package below shares (see below)
    logic/                      the access logic: logic.json (source of truth) and logic.txt (its readable
                                twin); document.py parses, validates and exports it, rules.py holds the
                                rules that are not drawn, bosses.py the boss_logic option
    rom/                        the .apmmzx patch: the patch class and AP marker in __init__.py, one module
                                per domain (pickups, sprites, ui), the ARM9 image (arm9.py), the BLZ
                                encoder (blz.py), the ROM container (nds.py), the icon set cut from
                                the player's ROM (icons.py) and the starting save baked into it (golden.py)
    client/                     the BizHawk client: the watcher in __init__.py, one module per stage group
                                and the boss rush skip (bossrush.py)
    tracker/                    Universal Tracker: map layout (maps.json, locations.json), the callbacks in
                                __init__.py and the generated meta.py
    assets/                     the three Archipelago logos; read() loads them
    apnds/                      vendored apnds (MIT)
    docs/                       player documentation
    src/asm/                    commented assembly sources of every cave and hook
    tools/, test/               maintainer tools (logic editor, checkers, packager); tests

`tools/`, `test/`, `src/` and the git files are left out of the `.apworld` (see `.apignore`).

## Generated files

`data.py` (locations with their detection recipe, items with their grant recipe, the room graph and the RAM structures
shared with the patched ROM), `tracker/meta.py` (map indices and transforms for the tracker),
`tools/logic_editor/data/gimmicks.json` (enemy and switch positions shown in the editor) are generated. The
generators belong to the maintainers' reverse-engineering toolkit, which needs the game, an emulator harness and a
Ghidra project, and are not in this repository. `logic/logic.txt` is regenerated from `logic.json` by the logic
tools. Open an issue for data corrections.

## Documentation for contributors

`docs/` holds the player documentation. For contributors:

- [tools/logic_editor/README.md](tools/logic_editor/README.md): the visual logic editor, how to run it and
  how its modules are laid out.
- [src/asm/](src/asm/README.md): the commented assembly of every cave and hook. `tools/check_caves.py` assembles
  it and checks it byte for byte against the constants the `rom/` modules ship; the Caves workflow runs it on
  every push.
- The module docstrings and the glossary below cover the rest; the maintainers keep the detailed reference of the
  memory map, the ROM patches and the client protocol with their toolkit and share it on request.

## Running from source

Clone this repository into `worlds/mmzx` (or `custom_worlds/mmzx`) of an Archipelago source checkout, 0.6.7 or later. From
the checkout root, `python -m unittest discover -s worlds/mmzx/test -t .` runs the tests (or `python worlds/mmzx/tools/run_tests.py` from anywhere). `tools/` holds the visual logic editor, the
logic validator and probe and the `.apworld` packager; each script documents its usage in its header. The logic is
never written in Python: it is drawn in the editor, which writes `logic/logic.json`. The editor draws rooms on renders
of the game's levels, which are not in the repository; without them it works on a blank canvas.

## Glossary

The terms you will meet first.

- biometal, model: a transformable form. Model X, ZX and OX are single items; HX, FX, LX and PX are progressive items
  whose two copies are the biometal's two halves.
- Card Key: one of the game's coloured keys (Yellow, Green, Red, Blue, Purple); progression items.
- Transerver: the game's teleport and mission console. The hub is the one in the Guardian base, with one floor per
  area; Transerver Access items unlock its destinations.
- Pseudoroid: one of the eight biometal bosses. Pairs share a biometal.
- boss rush: the eight refights in the D-4 tower before Serpent.
- Data Disk, Secret Disk: the game's collectable disks; each one is a check.
- room code: `a01`, `e07`: area letter plus room number. The game's own label is `A-1`, `E-7`.
- tier: a logic level of the document, `normal` or `expert`; expert adds alternatives to normal. Only normal
  ships for now.
- requirement, atom: what an edge or check demands, written as alternatives of atoms such as `HX`, `YELLOW` or
  `LIFEUP>=2`.
- detect recipe, grant recipe: how the client recognises a check in RAM, and how it gives an item.
- live vs canonical: the two copies the game keeps of its progress block; grants are written to both.
- golden image: the save image of a fresh post-tutorial game, built from the options and baked into the patched ROM; New Game loads it.
- cave: a small routine the patch places in unused space of the game's code.
- mailbox: a structure in free RAM where the patched game reports events to the client (collected pickups, notices).

## Credits

Built on [apnds](https://github.com/ljtpetersen/apnds) (MIT) for the ARM9 handling and on the Archipelago logo
sprites of the [Metroid: Zero Mission apworld](https://github.com/lilDavid/Archipelago-Metroid-Zero-Mission) (MIT).
The [Mega Man ZX Editor](https://github.com/AlaryVanEeckhout/Mega_Man_ZX_Editor) and its wiki, published Action
Replay codes, The Cutting Room Floor and the Pokemon Platinum apworld were the main sources. Everyone is listed in
[CREDITS.md](CREDITS.md).

## AI usage disclosure

_To be written by the maintainer before the first release._

## License

MIT, see [LICENSE](LICENSE). Mega Man ZX is a trademark of Capcom Co., Ltd.; this is a fan project, not affiliated
with Capcom or Inti Creates. No game art or data is in this repository or in the `.apworld`: the in-game icons, the
tracker maps and the starting save are produced from the player's own copy of the game. The only bytes of the game's
code in the source are the few instructions each hook replaces, kept so the patcher can check it is looking at the
right ROM.
