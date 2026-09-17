# Assembly sources of the ROM patches

Commented Thumb (ARMv5TE, little endian) sources of every code patch that the
`rom/` package applies to the ARM9 of Mega Man ZX (USA): the caves (small
routines placed in zero-filled stretches of the binary) and the hooks (one to
three instructions rewritten in place, usually a `bl` into a cave). What each
patch does and why is in the header of each file and in the `rom/` modules; this
folder is the readable form.

## What ships, and how these sources are checked

The bytes that reach players are the `bytes.fromhex(...)` constants in
`rom/pickups.py`, `rom/sprites.py` and `rom/ui.py`; the `bl` encodings of most
hooks are computed there at patch time. These sources are not read by the
world at runtime and are left out of the `.apworld` (see `.apignore`).

`tools/check_caves.py` assembles every block here with
[keystone](https://www.keystone-engine.org/) and compares it byte for byte with
its constant; the Caves workflow runs it on every push. A change to a cave is
made here first, assembled (`python tools/check_caves.py --emit` prints the
constants in the module form), and the resulting constant pasted into its module.
The script needs `pip install keystone-engine capstone`; neither library is part
of the world.

## Layout of a file

One file per patch, named after the constant prefix (`notify.s` for
`NOTIFY_*`, `icon_caves.s` for `ICON_CAVES` / `ICON_ATTACH_*` / `ICON_ANIM_*`).
Each file has a header saying which patch it is and where its pieces load, a
preamble with `.thumb` and `.equ` names for the game addresses and routines it
uses, and one block per piece:

    .org    0x020CB600          @ load address of the block
    @ rom: NOTIFY_CAVE        @ the constant (or expression) holding its bytes
    ...code...

`.org` is the load address in the flat-binary sense of armips: the script
assembles each block separately at that address, with the file's preamble in
front. Labels are local to a block, so a hook that targets the middle of a
cave uses an `.equ` with the address. Literal pools are written out as
labelled `.word` entries in the order the bytes have them; `nop` (0xBF00) and
`mov r8, r8` (0x46C0) appear only where the binary has them as padding.
Every hook block notes the vanilla instructions it replaces (`was:`).

Thumb-2 does not exist on the ARM9: a large immediate is written with an
offset register (`movs r0, #0x94; ldr r0, [r5, r0]`), as the bytes have it;
keystone would otherwise emit a `.w` encoding that the comparison catches.
