# Mega Man ZX for Archipelago

An [Archipelago](https://archipelago.gg) world for Mega Man ZX (Nintendo DS, 2006)

## Playing

- Setup guide: [docs/setup_en.md](docs/setup_en.md).
- What the randomizer does and how the options work: [docs/en_Mega Man ZX.md](docs/en_Mega%20Man%20ZX.md).

You need Archipelago 0.6.7 or later, BizHawk 2.10 or later with its NDS core, and your own Mega Man ZX (USA) ROM. 
Download `mmzx.apworld` from the
[Releases](https://github.com/Nekusen/Archipelago-MegaManZX/releases) page.

## Universal Tracker

The world ships the map layout for Universal Tracker (the game's world map, one map per area and per room, auto-tab
and player position).
The map images come from the separate [MegaManZX-Tracker](https://github.com/Nekusen/MegaManZX-Tracker) pack, which
UT loads from a zip you download once (`ut_pack_path` in `host.yaml`).

## Running from source

Clone this repository into `worlds/mmzx` (or `custom_worlds/mmzx`) of an Archipelago source checkout, 0.6.7 or later. From
the checkout root, `python -m unittest discover -s worlds/mmzx/test -t .` runs the tests (or `python worlds/mmzx/tools/run_tests.py` from anywhere). `tools/` holds the visual logic editor, the
logic validator and probe and the `.apworld` packager; each script documents its usage in its header.

The access logic is not written in Python: it is drawn room by room in the visual editor of
`tools/logic_editor/` (see its README), which writes `logic/logic.json` and two generated files:
`logic/rules.py`, the region graph and every rule in the syntax of the Archipelago Rule Builder,
which is what `regions.py` imports and builds the world from, and `logic/rules.json`, the same rules
serialized for trackers. Rules carry their explanation, so Universal Tracker's `/explain` can say what
a location needs. `tools/check_logic.py` validates the document and regenerates both files;
`tools/logic_probe.py` shows what an inventory reaches. The generated files are committed and the
tests fail when they fall behind the document: after a merge conflict in one of them, regenerate it
(save in the editor or run `tools/check_logic.py`), never resolve it by hand. The `.apworld` ships
`rules.py` alone; the document and the JSON twin stay in the repository. The editor draws rooms on renders
of the game's levels, which are not in this repository; without them it works on a blank canvas.

## Credits

See [CREDITS.md](CREDITS.md).

## AI Usage Disclosure

- AI has been used for the following things in this project:
  - Developing and writing almost all the codebase
  - Understanding the NDS architecture and patching process
  - Reverse engineering the game using Ghidra
  - Test game patching live and read memory addresses using py-desmume
  - Assist in analyzing best AP practices and standards from other projects
  - Assist in setting up the project and write the documentation
  - Developing a "logic editor" tool to speed-up logic definition
- This project does **not** contain AI art
- While AI has made a major part of this project, every change is reviewed and playtested by me, and since the first release nothing reaches develop or main without my approval. The code has already been refactored many times, and I've done several small changes here and there when I've noticed things I didn't like.
- Every design decision on **how** things should work functionality wise has been done by me
- Each new feature has been thoroughly playtested by me.

## License

MIT, see [LICENSE](LICENSE). Mega Man ZX is a trademark of Capcom Co., Ltd.; this is a fan project, not affiliated
with Capcom or Inti Creates. No game art or data is in this repository or in the `.apworld`: the in-game icons, the
tracker maps and the starting save are produced from the player's own copy of the game. The only bytes of the game's
code in the source are the few instructions each hook replaces, kept so the patcher can check it is looking at the
right ROM.
