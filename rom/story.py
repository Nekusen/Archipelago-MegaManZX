"""Mission objectives as items: a mission is reported only with its object, and Giro's scene, three
doors, the lava of Area K and the ITEM C list follow the items held instead of the game's own flags."""

import struct

from ..data import (
    ITEMS, LIVE_BLOCK, LOCATIONS, STORY_DONE_BITS, STORY_GATE_ITEMS, STORY_LAVA_ITEM, STORY_REPORT_STATES,
    STORY_SWITCH_ITEM)
from .arm9 import Arm9, thumb_bl
from .missions import MISSION_SECTION_LEN, MISSION_SECTION_RAM
from .nds import patch_overlay
from .table import story_addr, story_done_addr, story_flag, story_gate_flag, story_gates_addr
from .ui import ROOM_OVERLAY_SLOT_RAM

# Autoload section after the mission one: `report_gate`, then the table it reads.
STORY_SECTION_RAM = 0x02193200
STORY_SECTION_LEN = 0x80
STORY_SECTION_ENTRIES = {"report_gate": 0x00}
STORY_SECTION_CODE = bytes.fromhex(
    "10b59ef673fb00280fd008490968084a1388002b09d08b4201d00432f8e79378"
    "04490978194200d1002010bdac46100240321902461c1902")
STORY_REPORT_OFF = 0x40            # rows: u16 mission state, u8 mask of the story byte, u8 0; a zero state ends
STORY_REPORT_ROW = "<HBB"
# Who asks whether the objective is met: both consoles, the MISSION page, the HUD. (site, vanilla bl)
STORY_REPORT_HOOKS = [
    (0x020934CE, bytes.fromhex("9ef70dfa")),
    (0x02093C66, bytes.fromhex("9df741fe")),
    (0x02026A8E, bytes.fromhex("0af02dff")),
    (0x0204B904, bytes.fromhex("e5f7f2ff")),
]
# The doors take their flag from a table by door type: the two story gates read the items held
STORY_DOOR_FLAGS_RAM = 0x020E9EC0
STORY_DOOR_FLAGS = (381, 382)
STORY_DOOR_FLAGS_ORIG = bytes.fromhex("7d0100007e010000")
STORY_DOOR_FLAGS_NEW = bytes.fromhex("ddb34600deb34600")
# The ITEM C list of the pause menu shows the story objects held, not the ones picked up
STORY_MENU_FLAGS_RAM = 0x020D97B0
STORY_CHIP_ITEM = "Computer Chip"
STORY_MENU_ITEMS = (STORY_CHIP_ITEM, "Stuffed Animal", "Data Disk 1", "Data Disk 2", "Data Disk 3")
STORY_MENU_FLAGS_ORIG = bytes.fromhex("9702000098020000990200009a0200009b020000b5020000b6020000b7020000")
STORY_MENU_FLAGS_NEW = bytes.fromhex("d0b34600d1b34600d2b34600d3b34600d4b34600d5b34600d6b34600d7b34600")
# Room code that reads the story flags by address: a new literal lands each read on an item's byte.
STORY_OVERLAY_PATCH = {
    # overlay: [(RAM, vanilla, patched)]
    49: [(0x02194B40, "0c461002", "331c1902"),   # B-2, Giro's scene: any chip held, three bits of the story byte
         (0x02194A50, "8020", "0020")],          # ... and its fourth test, on the byte before, masks nothing
    65: [(0x02194748, "cc451002", "481c1902"),   # E-3, the generator: its bit, off the flag the machines read
         (0x021947D0, "cc451002", "481c1902"),
         (0x021949A4, "cc451002", "481c1902")],
    73: [(0x021948EC, "ec451002", "381c1902")],  # F-3, the door tiles: bit 5 of the byte 0x0F past the literal
    95: [(0x02195DA8, "ec451002", "381c1902")],  # K-1, the door to the Sub Tank: bit 7 of that same byte
    98: [(0x02195584, "cc451002", "461c1902"),   # K-4, the two lava walls: bit 0 of the byte after the literal
         (0x021956BC, "cc451002", "461c1902")],
}
STORY_CHIPS_OFF, STORY_CHIPS_BITS = 0x13, [0, 1, 2]
STORY_GENERATOR = "E-3: Generator"
STORY_F3_DOOR_OFF, STORY_F3_DOOR_BIT = 0x0F, 5
STORY_K1_DOOR_OFF, STORY_K1_DOOR_BIT = 0x0F, 7
STORY_LAVA_OFF, STORY_LAVA_BIT = 1, 0


def item_bits(name: str) -> list[int]:
    """Bits of an item in its possession byte, one per copy."""
    return [int(b) for b in ITEMS[name]["grant"][1]]


def report_table() -> bytes:
    """One row per mission whose Report asks for an object: any copy of it will do."""
    rows = b"".join(struct.pack(STORY_REPORT_ROW, state, 1 << item_bits(item)[0], 0)
                    for state, item in sorted(STORY_REPORT_STATES.items()))
    return rows + struct.pack(STORY_REPORT_ROW, 0, 0, 0)


def build_section() -> bytes:
    """The autoload section: the routine, then the table of missions and objects."""
    table = report_table()
    assert len(STORY_SECTION_CODE) <= STORY_REPORT_OFF
    assert STORY_REPORT_OFF + len(table) <= STORY_SECTION_LEN
    out = bytearray(STORY_SECTION_LEN)
    out[0:len(STORY_SECTION_CODE)] = STORY_SECTION_CODE
    out[STORY_REPORT_OFF:STORY_REPORT_OFF + len(table)] = table
    return bytes(out)


def door_flags() -> bytes:
    """The table entries of the two story gates, pointed at their items."""
    return b"".join(story_gate_flag(item_bits(STORY_GATE_ITEMS[flag])[0]).to_bytes(4, "little")
                    for flag in STORY_DOOR_FLAGS)


def menu_flags() -> bytes:
    """The ITEM C rows of the story objects, pointed at the objects held."""
    return b"".join(story_flag(bit).to_bytes(4, "little")
                    for item in STORY_MENU_ITEMS for bit in item_bits(item))


def gate_literal(off: int) -> str:
    """Literal that makes code reading `off` bytes past it land on the gates byte."""
    return (story_gates_addr() - off).to_bytes(4, "little").hex()


def patch_story_items(arm9: Arm9, enabled: bool) -> None:
    """With mission_objectives: items, gate the Reports and point the doors and the menu at the items held."""
    if not enabled:
        return
    assert MISSION_SECTION_RAM + MISSION_SECTION_LEN <= STORY_SECTION_RAM
    assert STORY_SECTION_RAM + STORY_SECTION_LEN <= ROOM_OVERLAY_SLOT_RAM
    assert STORY_DOOR_FLAGS_NEW == door_flags() and STORY_MENU_FLAGS_NEW == menu_flags()
    arm9.add_section(STORY_SECTION_RAM, build_section())
    target = STORY_SECTION_RAM + STORY_SECTION_ENTRIES["report_gate"]
    for ram, orig in STORY_REPORT_HOOKS:
        arm9.write(ram, thumb_bl(ram, target), orig)
    arm9.write(STORY_DOOR_FLAGS_RAM, STORY_DOOR_FLAGS_NEW, STORY_DOOR_FLAGS_ORIG)
    arm9.write(STORY_MENU_FLAGS_RAM, STORY_MENU_FLAGS_NEW, STORY_MENU_FLAGS_ORIG)


def patch_story_rooms(rom: bytearray, enabled: bool) -> None:
    """With mission_objectives: items, make the rooms follow the items: Giro's scene, the generator of E-3,
    the doors of F-3 and K-1 and the lava of K-4."""
    if not enabled:
        return
    assert item_bits(STORY_CHIP_ITEM)[:len(STORY_CHIPS_BITS)] == STORY_CHIPS_BITS
    assert STORY_OVERLAY_PATCH[49][0][2] == (story_addr() - STORY_CHIPS_OFF).to_bytes(4, "little").hex()
    assert LOCATIONS[STORY_GENERATOR]["detect"] == ["bit", LIVE_BLOCK, STORY_DONE_BITS[STORY_GENERATOR]]
    assert all(p[2] == story_done_addr().to_bytes(4, "little").hex() for p in STORY_OVERLAY_PATCH[65])
    assert item_bits(STORY_GATE_ITEMS[STORY_DOOR_FLAGS[0]]) == [STORY_F3_DOOR_BIT]
    assert item_bits(STORY_LAVA_ITEM) == [STORY_LAVA_BIT]
    assert item_bits(STORY_SWITCH_ITEM) == [STORY_K1_DOOR_BIT]
    assert STORY_OVERLAY_PATCH[73][0][2] == gate_literal(STORY_F3_DOOR_OFF)
    assert STORY_OVERLAY_PATCH[95][0][2] == gate_literal(STORY_K1_DOOR_OFF)
    assert all(p[2] == gate_literal(STORY_LAVA_OFF) for p in STORY_OVERLAY_PATCH[98])
    for ovl, patches in STORY_OVERLAY_PATCH.items():
        patch_overlay(rom, ovl, patches)
