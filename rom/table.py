"""The pickup table: which pickups stand for a location and which item each one shows, baked per seed.

The table travels in the .apmmzx and becomes an autoload section the boot code places in
free RAM, next to two bitmaps: `checked`, written by the client for the locations the server
already has, and `collected`, written by the game when a refill is taken. The icon, PICKUP_AP
and mailbox caves ask the routines at the start of the section, so the game draws the icons
and remembers a pickup with no client attached.
"""

import struct

from ..data import ICON_CODES, ITEMS, LOCATIONS, PICKUP_TABLE_ADDR
from ..goal import DISK_ITEM
from .golden import GOLDEN_IMAGE_SIZE
from .ui import GOLDEN_IMAGE_RAM, ROOM_OVERLAY_SLOT_RAM

# Section layout, as offsets from PICKUP_TABLE_ADDR
CODE_OFF = 0x000            # the routines; PICKUP_TABLE_ENTRIES names their entry points
CODE_MAX = 0x100
FLAGS_OFF = 0x100           # u8: 1 = icons off, written by the client
CHECKED_OFF = 0x104         # u8[BITMAP_LEN] by slot: the server has the location, written by the client
COLLECTED_OFF = 0x124       # u8[BITMAP_LEN] by slot: the pickup was taken since boot, written by the game
INDEX_OFF = 0x160           # u16[INDEX_SUBAREAS + 1]: first entry of each subarea
INDEX_SUBAREAS = 128
ENTRIES_OFF = 0x264         # entries of ENTRY_LEN bytes, sorted by subarea then coords index
ENTRY_LEN = 4               # coords index, slot, icon code, flags
ENTRY_RESPAWNS = 0x01       # flags bit 0: a refill, back on every visit
BITMAP_LEN = 32
MAX_SLOTS = 8 * BITMAP_LEN

# The routines: lookup(entity) -> animation of the AP set or -1, gate(entity) -> 1 for a pending
# location, collect(entity) -> sets the entity's bit in `collected`. The icon, PICKUP_AP and
# mailbox caves jump here.
PICKUP_TABLE_CODE = bytes.fromhex(
    "10b500f03df800280cd0040007480078002807d1607800f05df8002802d1a078"
    "013810bd0020c04310bdc046001c190210b500f025f800280bd00400e0784008"
    "05d3607800f046f80121484010bd012010bd002010bdc04610b500f011f80028"
    "0ad04178054acb08d21807230b400121994013780b43137010bdc046241c1902"
    "30b51049096800291ad04a68824201d00968f8e70a890c4b1b78802b10d20b4c"
    "5b00e05a0233e55a094c80000019ad002d19a84204d20378934202d00430f8e7"
    "002030bdf481100228821002601c1902641d1902044ac308d25c07230340da40"
    "012010407047c046041c1902")
PICKUP_TABLE_ENTRIES = {"lookup": 0x00, "gate": 0x30, "collect": 0x58}

# Every physical location in id order; its slot numbers the two bitmaps.
PICKUP_SLOTS: dict[str, int] = {
    name: slot for slot, name in enumerate(
        sorted((n for n, v in LOCATIONS.items() if v.get("icon")), key=lambda n: LOCATIONS[n]["id"]))}

# Items with their own sprite in the AP graphics set (ICON_CODES); anything else
# is drawn as the Archipelago logo of its classification.
ICON_BY_ITEM: dict[str, str] = {}
for _n in ITEMS:
    _w = _n.split()
    if _n in ("Life Up", "Sub Tank"):
        ICON_BY_ITEM[_n] = _n.replace(" ", "").lower()
    elif _n == DISK_ITEM:
        ICON_BY_ITEM[_n] = "secret_disk"
    elif _w[-1] == "Chip":
        ICON_BY_ITEM[_n] = "chip_" + "".join(_w[:-1])
    elif _w[-2:] == ["Card", "Key"]:
        ICON_BY_ITEM[_n] = "card_" + _w[0]
    elif len(_w) >= 2 and _w[-2] == "Model":
        ICON_BY_ITEM[_n] = "model_" + _w[-1]


def icon_code(item: str, own: bool, advancement: bool, useful: bool) -> int:
    """Icon of the item placed at a location: its own sprite for one of ours, else the logo of its class."""
    if own and item in ICON_BY_ITEM:
        return ICON_CODES[ICON_BY_ITEM[item]]
    if advancement:
        return ICON_CODES["logo_progression"]
    if useful:
        return ICON_CODES["logo_useful"]
    return ICON_CODES["logo_filler"]


def build_table(codes: dict[str, int]) -> bytes:
    """The index and the entries of the locations in `codes` (name to icon code).

    A pickup whose location is not in the seed (a refill category left off) gets no
    entry and stays vanilla.
    """
    entries = []
    for name, code in codes.items():
        v = LOCATIONS[name]
        sub, idx = int(v["icon"][0]), int(v["icon"][1])
        if not (0 <= sub < INDEX_SUBAREAS and 0 <= idx < 256 and 0 <= code < 256):
            raise ValueError("MMZX: pickup table entry out of range for %r" % name)
        flags = ENTRY_RESPAWNS if v["detect"][0] == "mailbox" else 0
        entries.append((sub, idx, PICKUP_SLOTS[name], code, flags))
    entries.sort()
    starts = [sum(1 for e in entries if e[0] < sub) for sub in range(INDEX_SUBAREAS + 1)]
    out = bytearray(ENTRIES_OFF - INDEX_OFF)
    struct.pack_into("<%dH" % (INDEX_SUBAREAS + 1), out, 0, *starts)
    for _sub, idx, slot, code, flags in entries:
        out += bytes((idx, slot, code, flags))
    return bytes(out)


def table_entries(table: bytes) -> dict[str, tuple[int, int, int]]:
    """Name to (slot, code, flags) of every entry of a built table; the reverse of build_table."""
    by_place = {(int(v["icon"][0]), int(v["icon"][1])): n for n, v in LOCATIONS.items() if v.get("icon")}
    starts = struct.unpack_from("<%dH" % (INDEX_SUBAREAS + 1), table, 0)
    body = table[ENTRIES_OFF - INDEX_OFF:]
    out = {}
    for sub in range(INDEX_SUBAREAS):
        for k in range(starts[sub], starts[sub + 1]):
            idx, slot, code, flags = body[k * ENTRY_LEN:(k + 1) * ENTRY_LEN]
            out[by_place[(sub, idx)]] = (slot, code, flags)
    return out


def build_section(table: bytes) -> bytes:
    """The autoload section: the routines, the switch and the two bitmaps zeroed, then the table."""
    assert len(PICKUP_TABLE_CODE) <= CODE_MAX
    return PICKUP_TABLE_CODE + bytes(INDEX_OFF - len(PICKUP_TABLE_CODE)) + table


def patch_pickup_table(arm9, table: bytes) -> None:
    """Bake the seed's pickup table as an autoload section, after the golden image."""
    section = build_section(table)
    assert PICKUP_TABLE_ADDR % 4 == 0 and len(section) % 4 == 0
    assert PICKUP_TABLE_ADDR >= GOLDEN_IMAGE_RAM + GOLDEN_IMAGE_SIZE
    if PICKUP_TABLE_ADDR + len(section) > ROOM_OVERLAY_SLOT_RAM:
        raise ValueError("MMZX: the pickup table does not fit before the room overlay slot")
    arm9.add_section(PICKUP_TABLE_ADDR, section)
