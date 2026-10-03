"""Missions taken again from the Transerver: the Mission Requests list offers the missions
already completed, taking one clears what would end it at once, and the consoles offer
Abort only to what the player chose there."""

import struct

from ..data import LIVE_BLOCK, MISSION_ACCEPT, MISSION_COMPLETED_BIT, MISSION_REPEAT_BITS, PICKUP_TABLE_ADDR
from .arm9 import Arm9, thumb_bl
from .table import ENTRIES_OFF, ENTRY_LEN, MAX_SLOTS
from .ui import ROOM_OVERLAY_SLOT_RAM

# Autoload section after the pickup table: `count` (entries of the list), `take` (accept the chosen
# id, then clear its repeat flags), `pending` (zero when what is under way came from the list), tables.
MISSION_SECTION_RAM = 0x02193000
MISSION_SECTION_LEN = 0x200
MISSION_SECTION_ENTRIES = {"count": 0x00, "take": 0x30, "pending": 0x70}
MISSION_SECTION_CODE = bytes.fromhex(
    "70b4094c0949002027252368da108a5c0726334001269e40324200d001300434"
    "013df2d170bc7047c0301902cc45100270b5040001f7baff023c0d2c11d8094d"
    "2c5d094d2d19094e2b881a0409d4da08b05c07210b40012199408843b0540235"
    "f2e770bd7031190280311902cc45100230b40f4b5f21585c400716d4e0215c58"
    "0c4a0025505da04204d001350e2df9d301200be0084aad005159ca089a5c0720"
    "0140ca400120904300e0002030bc7047cc45100260311902c0301902")
MISSION_LIST_OFF = 0xC0            # u32[39]: the flag that lists each id 2 to 40
MISSION_LIST_IDS = range(2, 41)
MISSION_LAST_STORY = 16            # ids above it are quests, listed as in vanilla
MISSION_NEVER_OFF = 0x15C          # a zero word: the "flag" of a story mission the list never shows
MISSION_STATES_OFF = 0x160         # u8[14]: the state value of ids 2 to 15
MISSION_REPEAT_IDS = range(2, 16)
MISSION_REPEAT_INDEX_OFF = 0x170   # u8[14]: where each id's row starts inside the rows
MISSION_REPEAT_OFF = 0x180         # u16 flags to clear, 0xFFFF ends each id's row
MISSION_REPEAT_END = 0xFFFF

# Entries of the quests (ids 17 to 40) in the vanilla table of offered flags, kept as they are
MISSION_QUEST_FLAGS_RAM = 0x020DAEB8
MISSION_QUEST_FLAGS_ORIG = bytes.fromhex(
    "e3000000e9000000f700000001010000070100000e01000012010000180100001c010000"
    "2001000024010000280100002c01000030010000350100003b010000410100004701000"
    "04e010000540100005c010000600100006501000069010000")
# The list builder reads its table through this literal
MISSION_LIST_LITERAL_PATCH = [
    (0x02027FEC, bytes.fromhex("7cae0d02"), bytes.fromhex("c0301902")),    # .word table
]
# The two consoles count the offered flags before their menu, and accept the id chosen in the list
MISSION_COUNT_HOOKS = [(0x02093496, bytes.fromhex("75f76df9")), (0x02093C28, bytes.fromhex("74f7a4fd"))]
MISSION_TAKE_HOOKS = [(0x02093604, bytes.fromhex("01f0d2fc")), (0x02093E0A, bytes.fromhex("01f0cff8"))]
# "Story mission pending" hid Abort during Troop Reinforcement and Protect HQ; `pending` replaces it
MISSION_PENDING_HOOKS = [
    (0x020934EE, bytes.fromhex("75f7a1fa")),
    (0x02093C8A, bytes.fromhex("74f7d3fe")),
    (0x0202C522, bytes.fromhex("dcf787fa")),
]
# With a mission under way that did not come from the list, the consoles show their normal menu
MISSION_MENU_PATCH = [
    (0x020934F6, bytes.fromhex("6348"), bytes.fromhex("cee7")),    # b 0x02093496
    (0x02093C92, bytes.fromhex("6900"), bytes.fromhex("c9e7")),    # b 0x02093C28
]


def flag_index(addr: int, bit: int) -> int:
    """Flag number of a bit, counted from the progress block like the game's flag lists do."""
    return (addr - LIVE_BLOCK) * 8 + bit


def mission_list_table() -> bytes:
    """The flag that lists each id: the 'completed' bit of a mission, the vanilla flag of a quest."""
    never = flag_index(MISSION_SECTION_RAM + MISSION_NEVER_OFF, 0)
    flags = [flag_index(*MISSION_COMPLETED_BIT[mid]) if mid in MISSION_COMPLETED_BIT else never
             for mid in MISSION_LIST_IDS if mid <= MISSION_LAST_STORY]
    quests = struct.unpack("<%dI" % (len(MISSION_QUEST_FLAGS_ORIG) // 4), MISSION_QUEST_FLAGS_ORIG)
    if len(flags) + len(quests) != len(MISSION_LIST_IDS):
        raise ValueError("MMZX: the mission list table needs one flag per id")
    return struct.pack("<%dI" % len(MISSION_LIST_IDS), *flags, *quests)


def mission_states() -> bytes:
    """The state value each mission of the list runs under, in id order."""
    states = {rec["id"]: rec["state"] for rec in MISSION_ACCEPT.values()}
    return bytes(states[mid] for mid in MISSION_REPEAT_IDS)


def mission_repeat_table() -> tuple[bytes, bytes]:
    """(index, rows): where each mission's row starts, and the rows of flags `take` clears."""
    index, rows = bytearray(), bytearray()
    for mid in MISSION_REPEAT_IDS:
        index.append(len(rows))
        flags = [flag_index(a, b) for a, b in MISSION_REPEAT_BITS.get(mid, [])]
        rows += struct.pack("<%dH" % (len(flags) + 1), *flags, MISSION_REPEAT_END)
    if len(rows) > 0xFF:
        raise ValueError("MMZX: the repeat rows do not fit a byte index")
    return bytes(index), bytes(rows)


def build_section() -> bytes:
    """The autoload section: the routines, the list table, the zero word, the states and the rows."""
    listing, states = mission_list_table(), mission_states()
    index, rows = mission_repeat_table()
    pieces = [(0, MISSION_SECTION_CODE), (MISSION_LIST_OFF, listing), (MISSION_STATES_OFF, states),
              (MISSION_REPEAT_INDEX_OFF, index), (MISSION_REPEAT_OFF, rows)]
    ends = [off + len(data) for off, data in pieces]
    assert ends[0] <= MISSION_LIST_OFF and ends[1] <= MISSION_NEVER_OFF < MISSION_NEVER_OFF + 4 <= MISSION_STATES_OFF
    assert ends[2] <= MISSION_REPEAT_INDEX_OFF and ends[3] <= MISSION_REPEAT_OFF and ends[4] <= MISSION_SECTION_LEN
    out = bytearray(MISSION_SECTION_LEN)
    for off, data in pieces:
        out[off:off + len(data)] = data
    return bytes(out)


def patch_mission_list(arm9: Arm9) -> None:
    """Bake the section, point the list builder at it and route the consoles through it."""
    assert PICKUP_TABLE_ADDR + ENTRIES_OFF + MAX_SLOTS * ENTRY_LEN <= MISSION_SECTION_RAM
    assert MISSION_SECTION_RAM + MISSION_SECTION_LEN <= ROOM_OVERLAY_SLOT_RAM
    quests = arm9.read(MISSION_QUEST_FLAGS_RAM, len(MISSION_QUEST_FLAGS_ORIG))
    if quests != MISSION_QUEST_FLAGS_ORIG:
        raise ValueError("MMZX: unexpected quest flags at 0x%08X (%s). Wrong ROM?"
                         % (MISSION_QUEST_FLAGS_RAM, quests.hex()))
    arm9.add_section(MISSION_SECTION_RAM, build_section())
    for ram, orig, new in MISSION_LIST_LITERAL_PATCH + MISSION_MENU_PATCH:
        arm9.write(ram, new, orig)
    for hooks, entry in ((MISSION_COUNT_HOOKS, "count"), (MISSION_TAKE_HOOKS, "take"),
                         (MISSION_PENDING_HOOKS, "pending")):
        for ram, orig in hooks:
            arm9.write(ram, thumb_bl(ram, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES[entry]), orig)
