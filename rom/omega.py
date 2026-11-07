"""The Omega Zero goal: the door of his arena in N-1 stays locked until the goal requirements are met."""

import struct

from ..data import OMEGA_GATE
from .arm9 import Arm9
from .doors import COORD_SLOT_OFF, ROLE_KEY_SHIFT, TEMPLATE_ROLE, grow_template_table, grown_table_ram

# A door reads the flag of its key type from a table; type 6 is unused by the game and takes
# the flag the client raises once the goal requirements are met.
DOOR_FLAGS_RAM = 0x020E9E98
OMEGA_KEY_TYPE = 6
OMEGA_FLAG_RAM = DOOR_FLAGS_RAM + OMEGA_KEY_TYPE * 4
OMEGA_FLAG_ORIG = bytes(4)
OMEGA_FLAG_NEW = struct.pack("<I", OMEGA_GATE)
# N-1 and its template table; the arena's door shares its template with three other doors,
# so it gets a copy of its own at the end of a longer table.
OMEGA_ROOM = {"overlay": 107, "slots_pointer": 0x020CA0DC, "slots": 0x021966C0, "slot_count": 47,
              "size": 17248, "bss": 32}
OMEGA_DOOR_COORD = 0x021966B0
OMEGA_DOOR_SLOT = 1
OMEGA_DOOR_TEMPLATE = bytes.fromhex("010513001400ffffff000000")


def locked_template() -> bytes:
    out = bytearray(OMEGA_DOOR_TEMPLATE)
    out[TEMPLATE_ROLE] |= OMEGA_KEY_TYPE << ROLE_KEY_SHIFT
    return bytes(out)


def patch_door_table(arm9: Arm9) -> None:
    """The ARM9 side: the flag of key type 6, and the pointer to N-1's longer template table."""
    arm9.write(OMEGA_FLAG_RAM, OMEGA_FLAG_NEW, OMEGA_FLAG_ORIG)
    arm9.write(OMEGA_ROOM["slots_pointer"], struct.pack("<I", grown_table_ram(OMEGA_ROOM)),
               struct.pack("<I", OMEGA_ROOM["slots"]))


def patch_door_overlay(rom: bytearray) -> None:
    """The room side: the arena's door takes the locked template."""
    grow_template_table(rom, OMEGA_ROOM, [], [locked_template()],
                        [(OMEGA_DOOR_COORD + COORD_SLOT_OFF, OMEGA_DOOR_SLOT, OMEGA_ROOM["slot_count"])])
