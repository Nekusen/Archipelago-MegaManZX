# Developer reference

The technical reference behind the code, for contributors and reviewers. It is
kept up to date with the code: when a patch, an address or a client stage
changes, the change lands here in the same commit. `docs/` holds the player
documentation instead. This folder and `src/` are left out of the `.apworld`.

| File | Contents |
|---|---|
| [memory_map.md](memory_map.md) | every RAM address, ROM offset and data layout the world uses: the game's own structures, the ones the patch installs (mailbox, notices, icon table), the golden image and the graphics sets |
| [rom_patches.md](rom_patches.md) | the ARM9 patches one by one: why each exists, what it hooks, what data it touches, how the client takes part, and their limits; the patching pipeline and the BLZ encoder |
| [client_protocol.md](client_protocol.md) | the client tick by tick: start-up and ROM validation, the watcher stages in order, check detection, item grants, missions, notices, DeathLink, tracker, persistence and the traps |
| [logic_format.md](logic_format.md) | the `logic.json` format: atoms and DNF requirements, the normal and expert tiers, how `regions.py` consumes it, validation rules, `logic.txt`, the editor and the tools |
| [glossary.md](glossary.md) | the project's own terms |
| [rom_changes.md](rom_changes.md) | the technical version of "what changes in the game" (patch and client); the player's version is [docs/rom_changes.md](../docs/rom_changes.md) |

The assembly sources of the caves and hooks are in [src/asm/](../src/asm/),
with `tools/check_caves.py` proving that the bytes the `rom/` modules ship are
what those sources assemble to.

The reference cites the maintainers' experiments as `expNNN`; they are the
numbered scripts of a private reverse-engineering notebook that needs the game,
an emulator harness and a Ghidra project. Ask in an issue if you need the
details of one.
