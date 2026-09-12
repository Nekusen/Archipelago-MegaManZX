"""Patches on the game's flow and screens: New Game through the LOAD handler, skippable
cutscenes, the warp on the pause menu and the notice popup."""

import hashlib

from ..data import NOTIFY_ADDR
from .arm9 import Arm9

# Tutorial skip: New Game enters the scene through the LOAD handler, from the
# image the client seeds. The handler also serves the attract demo, so the cave
# checks the game mode (low 16 bits zero) and the title carousel step first.
SKIP_ENTRY_RAM = 0x02022544
SKIP_ENTRY_ORIG = bytes.fromhex("10b5041c00f020fa")
SKIP_ENTRY_NEW = bytes.fromhex("004b184761b40c02")    # jump to SKIP_CAVE_RAM
SKIP_CAVE_RAM = 0x020CB460
SKIP_CAVE = bytes.fromhex(
    "07490968090403d1064a1278062a05d010b5044657f78afa034b1847034b1847"
    "d8e6150270cd14024d2502022d250202")

# Go to Transerver: Y on the MISSION tab. Cave A replaces the pad read and raises
# two flags on Y; cave B closes the menu on its flag. The client serves the warp.
MENU_WARP_FLAGS_RAM = 0x020CB9D0    # +0 request (client), +1 close (cave B)
MENU_WARP_CAVE_A_RAM = 0x020CB99C
MENU_WARP_CAVE_A = bytes.fromhex(
    "054a11885388db430b401b0503d5034a012313705370704768270f02d0b90c02")
MENU_WARP_CAVE_B_RAM = 0x020CB438
MENU_WARP_CAVE_B = bytes.fromhex(
    "04494a78002a03d000224a7001207047014b1847d0b90c020d2b0202")
MENU_WARP_HOOKS = [
    # (RAM, vanilla, patched)
    (0x020272B6, bytes.fromhex("1d490988"), bytes.fromhex("a4f071fb")),   # map scroll pad read: bl cave A
    (0x02023240, bytes.fromhex("fff764fc"), bytes.fromhex("a8f0faf8")),   # menu close call: bl cave B
]
MENU_WARP_TEXT_ROM = 0xDFB200        # m_sub_en.bin (NitroFS, uncompressed)
MENU_WARP_TEXT_SHA256 = "86da91168288b97f4ace3c34a86eba342e97e9afec9bb70949110693930c65a0"
MENU_WARP_TEXT_NEW = bytes.fromhex("3900225554544f4e1a274f00544f003452414e5345525645520000")
MENU_WARP_TEXT_OFFS = (0xB14, 0xB4B, 0xB85)   # three variants of the help text

# NOTIFY: the client's text in the game's small non-blocking popup. The cave
# wraps the message tick; it opens the popup when the message system is idle.
# The notice buffer itself is data.NOTIFY_ADDR, right after the cave.
NOTIFY_HOOK_RAM = 0x02021DD4
NOTIFY_HOOK_ORIG = bytes.fromhex("f0f72afb")   # bl message tick
NOTIFY_HOOK_NEW = bytes.fromhex("a9f014fc")    # bl NOTIFY_CAVE_RAM
NOTIFY_CAVE_RAM = 0x020CB600
NOTIFY_CAVE = bytes.fromhex(
    "10b5204c2078002839d01f496078002806d0487e062803d10020207060702ee0"
    "488900282bd18869002828d117480078400824d216480078800820d201206070"
    "2078022804d1a088618846f743fe16e0201d486260884861c889002801d03bf7"
    "61ff0c4846f7bafd0a4846f7f1fc0649087b002801d0012000e00220886146f7"
    "d5fe10bd00b70c02c4027e0202f5140206f51402cc027e02")

# Cutscene skip: START skips a story cutscene only on a replay. The "event seen"
# test becomes a no-op and the cave marks the event seen, as watching it would.
CUTSCENE_SKIP_PATCH = [
    # (RAM, vanilla, patched)
    (0x0201C00C, bytes.fromhex("17d0"), bytes.fromhex("c046")),           # open skippable block: beq -> nop
    (0x0201B1E4, bytes.fromhex("1348417f"), bytes.fromhex("b0f0acf9")),   # START reader: bl CUTSCENE_SKIP_CAVE_RAM
]
CUTSCENE_SKIP_CAVE_RAM = 0x020CB540
CUTSCENE_SKIP_CAVE = bytes.fromhex("10b5034ce0783df76df80248417f10bd00f51402b0f61402")


def patch_tutorial_skip(arm9: Arm9) -> None:
    """Send New Game through the LOAD handler, so a slot starts from the image the client seeds."""
    arm9.write(SKIP_ENTRY_RAM, SKIP_ENTRY_NEW, SKIP_ENTRY_ORIG)
    arm9.write(SKIP_CAVE_RAM, SKIP_CAVE)


def patch_menu_warp(arm9: Arm9) -> None:
    """Y on the MISSION tab raises the warp request flag and closes the menu; the client warps."""
    assert len(MENU_WARP_CAVE_A) <= MENU_WARP_FLAGS_RAM - MENU_WARP_CAVE_A_RAM
    assert len(MENU_WARP_CAVE_B) <= SKIP_CAVE_RAM - MENU_WARP_CAVE_B_RAM
    arm9.write(MENU_WARP_CAVE_A_RAM, MENU_WARP_CAVE_A)
    arm9.write(MENU_WARP_CAVE_B_RAM, MENU_WARP_CAVE_B)
    for ram, orig, new in MENU_WARP_HOOKS:
        arm9.write(ram, new, orig)


def patch_notify(arm9: Arm9) -> None:
    """Show the client's notices in the game's small popup, from the per-frame message tick."""
    assert len(NOTIFY_CAVE) <= NOTIFY_ADDR - NOTIFY_CAVE_RAM
    arm9.write(NOTIFY_CAVE_RAM, NOTIFY_CAVE)
    arm9.write(NOTIFY_HOOK_RAM, NOTIFY_HOOK_NEW, NOTIFY_HOOK_ORIG)


def patch_cutscene_skip(arm9: Arm9) -> None:
    """Let START skip every story cutscene; the cave marks the event seen, as watching it would."""
    assert CUTSCENE_SKIP_CAVE_RAM + len(CUTSCENE_SKIP_CAVE) <= NOTIFY_CAVE_RAM
    arm9.write(CUTSCENE_SKIP_CAVE_RAM, CUTSCENE_SKIP_CAVE)
    for ram, orig, new in CUTSCENE_SKIP_PATCH:
        arm9.write(ram, new, orig)


def patch_menu_warp_text(rom: bytearray) -> None:
    """Replace the three MISSION tab help texts in m_sub_en.bin, in place and of the same length."""
    for off in MENU_WARP_TEXT_OFFS:
        o = MENU_WARP_TEXT_ROM + off
        cur = bytes(rom[o:o + len(MENU_WARP_TEXT_NEW)])
        if cur == MENU_WARP_TEXT_NEW:
            continue
        if hashlib.sha256(cur).hexdigest() != MENU_WARP_TEXT_SHA256:
            raise ValueError("MMZX: unexpected text at m_sub_en.bin+0x%X (%s)" % (off, cur.hex()))
        rom[o:o + len(MENU_WARP_TEXT_NEW)] = MENU_WARP_TEXT_NEW
