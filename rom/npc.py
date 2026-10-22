"""The Sub Tank refill operator: a Guardian beside the starting Transerver who fills every Sub Tank held for E-Crystals."""

import struct

from . import nds
from .arm9 import Arm9
from .ui import ROOM_OVERLAY_SLOT_RAM

# The operator is a Guardian (class 5.48) of role 4 with a new modifier, 6. The game picks a
# Guardian's init and update from two tables per role, so role 4's tables live one entry longer
# in an autoload section with the update routine, and the role's two pointers point there.
NPC_SECTION_RAM = 0x02193A00
NPC_SECTION_LEN = 0x200
NPC_INIT_TABLE_OFF = 0x1C0
NPC_UPDATE_TABLE_OFF = 0x1E0
NPC_SECTION_CODE = bytes.fromhex(
    "10b5041ca17c01290fd0022917d005293bd0062940d0002944d100217cf622fa"
    "00f083f80120a0743ce000f047f8002838d0564800f03af80220a07432e008f7"
    "61fb00282ed04948007800095349012815d14a4a12684b4810584e49c8280ed3"
    "101c00f04df84c49002808d0262071f635ff42480068c821b1f682f94449081c"
    "00f014f80520a0740ce008f73bfb002808d00620a07405e008f71efb002801d0"
    "0120a074201c7cf6b1f810bd20b5051c00f03bf8281c7ef6b1fb20bd00b52a48"
    "408900281ad12b480078002816d02a480168201c7c30814210d1886aa0420dd1"
    "27490a78012082430a70a17a090901200140201cc9300170012000bd002000bd"
    "60b5051cb1f6b8f8061c1f4969180023002e08d00a781e2a02da1e220a700123"
    "491c761ef4e7181c60bd14480068c06de16d0022814200da0122a37a10208343"
    "10010343a372211c54310a70211c3c318b7d10208343100103438b7501235340"
    "03480380704700bfc4027e02d7027e023a037e02708b1002588b10029c8b1002"
    "69f6140268010000710100008104000082040000830400008404000085040000")
NPC_INIT_TABLE = bytes.fromhex("05c3090205c3090205c30902e9ab090231aa090279a8090205c30902")
NPC_UPDATE_TABLE = bytes.fromhex("d5af0902d5af0902d5af0902f5bf0902659b0902f5990902013a1902")
NPC_ROLE_INIT_POINTER_RAM = 0x020EAD38
NPC_ROLE_INIT_POINTER_ORIG = bytes.fromhex("e4aa0e02")
NPC_ROLE_INIT_POINTER_NEW = bytes.fromhex("c03b1902")
NPC_ROLE_UPDATE_POINTER_RAM = 0x020EAD50
NPC_ROLE_UPDATE_POINTER_ORIG = bytes.fromhex("a8aa0e02")
NPC_ROLE_UPDATE_POINTER_NEW = bytes.fromhex("e03b1902")

# The hub room, overlay 115: a room's three entity tables (sprite preloads, coordinates, templates)
# sit at the end of its overlay, pointed to per subarea from the ARM9. The operator needs an
# entry in each, so the three grow and move past the overlay's code.
HUB_OVERLAY = 115
HUB_OVERLAY_SIZE = 6368
HUB_OVERLAY_BSS = 0
HUB_SUBAREA = 70
ENTITY_TABLES_RAM = 0x020C9C7C            # per kind, u32[subarea] pointers
ENTITY_TABLE_STRIDE = 0x120
PRELOADS_KIND, COORDS_KIND, TEMPLATES_KIND = 1, 2, 3
HUB_TABLES_RAM = {PRELOADS_KIND: 0x02194660, COORDS_KIND: 0x021946E4, TEMPLATES_KIND: 0x02194690}
HUB_TABLE_COUNTS = {PRELOADS_KIND: 5, COORDS_KIND: 41, TEMPLATES_KIND: 7}   # the coordinates count their header entry
ENTRY_LEN = {PRELOADS_KIND: 8, COORDS_KIND: 8, TEMPLATES_KIND: 12}
TABLE_END = {PRELOADS_KIND: bytes.fromhex("ffffffffffff0000"), COORDS_KIND: bytes.fromhex("ffffff7fff7f0000"),
             TEMPLATES_KIND: bytes(12)}      # the templates end where the coordinates begin; the zeros only pad
# The operator: the sprite set of the operators, a Guardian template of role 4 modifier 6, and
# a place to the right of the Transerver of the starting floor, by starting_transerver key
NPC_PRELOAD = bytes.fromhex("cc00cc0000ff0000")
NPC_TEMPLATE = bytes.fromhex("410548040600ffff00000000")
NPC_PLACES = {"area_a": (472, 344), "guardian_base": (472, 5720)}

# The five messages, appended to talk_sys_en.bin: the offer, which ends in a two-line choice,
# and the replies to a yes with the tanks filled, to a yes without enough E-Crystals, to a yes
# with nothing to fill and to a no
NPC_TEXT_FIRST = 129                      # messages the file holds; the offer is message 129, id 0x481
NPC_TEXTS = [
    bytes.fromhex("f202f302f855290043414e00524546494c4c00594f5552fc3355420034414e4b5300464f52001210100025230efd"
                  "f202f663f302f855324546494c4c005448454d00464f52001210100025231ffc0000394553fc00002e4f"),
    bytes.fromhex("f202f302f8553355420034414e4b5300524546494c4c45440efc234f4d45004241434b00414e5954494d4501"),
    bytes.fromhex("f202f302f8552e4f5400454e4f55474800250d2352595354414c530efc295400434f535453001210100025230e"),
    bytes.fromhex("f202f302f8553448455245004953004e4f5448494e4700544ffc524546494c4c005249474854004e4f570e"),
    bytes.fromhex("f202f302f855234f4d45004241434b00414e5954494d4501"),
]


def section() -> bytes:
    """The autoload section: the update routine, then the two tables of role 4."""
    out = bytearray(NPC_SECTION_LEN)
    out[0:len(NPC_SECTION_CODE)] = NPC_SECTION_CODE
    out[NPC_INIT_TABLE_OFF:NPC_INIT_TABLE_OFF + len(NPC_INIT_TABLE)] = NPC_INIT_TABLE
    out[NPC_UPDATE_TABLE_OFF:NPC_UPDATE_TABLE_OFF + len(NPC_UPDATE_TABLE)] = NPC_UPDATE_TABLE
    return bytes(out)


def table_pointer_ram(kind: int) -> int:
    """RAM address of the ARM9 pointer to the hub's table of `kind`."""
    return ENTITY_TABLES_RAM + kind * ENTITY_TABLE_STRIDE + HUB_SUBAREA * 4


def grown_table_sizes() -> dict[int, int]:
    """Bytes of each hub table once the operator is in: entries plus the end mark."""
    added = {PRELOADS_KIND: 1, COORDS_KIND: 1, TEMPLATES_KIND: 1}
    return {kind: (HUB_TABLE_COUNTS[kind] + added[kind] + 1) * ENTRY_LEN[kind] for kind in ENTRY_LEN}


def grown_tables_ram() -> dict[int, int]:
    """RAM address of each grown table: after the overlay's code, one after the other, on words."""
    out = {}
    ram = ROOM_OVERLAY_SLOT_RAM + ((HUB_OVERLAY_SIZE + HUB_OVERLAY_BSS + 3) & ~3)
    for kind, size in grown_table_sizes().items():
        out[kind] = ram
        ram += (size + 3) & ~3
    return out


def hub_tables(ram: int, code: bytes) -> dict[int, list[bytes]]:
    """The entries of the hub's three tables as the overlay holds them, checked against the original."""
    out = {}
    for kind, table_ram in HUB_TABLES_RAM.items():
        off = table_ram - ram
        step = ENTRY_LEN[kind]
        count = HUB_TABLE_COUNTS[kind]
        entries = [bytes(code[off + i * step:off + (i + 1) * step]) for i in range(count)]
        # the templates have no end mark: the coordinates follow them
        end = bytes(code[off + count * step:off + (count + 1) * step])
        if kind != TEMPLATES_KIND and end != TABLE_END[kind] or TABLE_END[kind] in entries:
            raise ValueError("MMZX: the entity tables of the hub are not the original ones. Wrong ROM?")
        out[kind] = entries
    return out


def grown_tables(tables: dict[int, list[bytes]], floor: str) -> dict[int, bytes]:
    """The three tables with the operator in: its sprite set, its template and its place on `floor`, in x order."""
    preloads = tables[PRELOADS_KIND] + [NPC_PRELOAD]
    templates = tables[TEMPLATES_KIND] + [NPC_TEMPLATE]
    slot = len(templates) - 1
    coords = list(tables[COORDS_KIND])
    x, y = NPC_PLACES[floor]
    entry = struct.pack("<IHH", x, y, slot)
    # the first entry is the table's header and stays first; the rest are in x order
    at = next((i for i, c in enumerate(coords) if i and struct.unpack_from("<I", c)[0] > x), len(coords))
    coords.insert(at, entry)
    return {PRELOADS_KIND: b"".join(preloads) + TABLE_END[PRELOADS_KIND],
            COORDS_KIND: b"".join(coords) + TABLE_END[COORDS_KIND],
            TEMPLATES_KIND: b"".join(templates) + TABLE_END[TEMPLATES_KIND]}


def patch_npc_tables(arm9: Arm9) -> None:
    """The ARM9 side: the section with the operator's routine and role tables, and the pointers to them and to the hub's grown tables."""
    assert len(NPC_SECTION_CODE) <= NPC_INIT_TABLE_OFF
    assert NPC_INIT_TABLE_OFF + len(NPC_INIT_TABLE) <= NPC_UPDATE_TABLE_OFF
    assert NPC_UPDATE_TABLE_OFF + len(NPC_UPDATE_TABLE) <= NPC_SECTION_LEN
    assert NPC_SECTION_RAM + NPC_SECTION_LEN <= ROOM_OVERLAY_SLOT_RAM
    arm9.add_section(NPC_SECTION_RAM, section())
    arm9.write(NPC_ROLE_INIT_POINTER_RAM, NPC_ROLE_INIT_POINTER_NEW, NPC_ROLE_INIT_POINTER_ORIG)
    arm9.write(NPC_ROLE_UPDATE_POINTER_RAM, NPC_ROLE_UPDATE_POINTER_NEW, NPC_ROLE_UPDATE_POINTER_ORIG)
    for kind, ram in grown_tables_ram().items():
        arm9.write(table_pointer_ram(kind), struct.pack("<I", ram), struct.pack("<I", HUB_TABLES_RAM[kind]))


def patch_npc_room(rom: bytearray, floor: str) -> None:
    """The room side: the hub's overlay with its three entity tables grown by the operator of `floor`, after its code."""
    ram, code = nds.overlay_code(rom, HUB_OVERLAY)
    if len(code) != HUB_OVERLAY_SIZE or nds.overlay_bss_size(rom, HUB_OVERLAY) != HUB_OVERLAY_BSS:
        raise ValueError("MMZX: overlay %d is not the one of the original ROM. Wrong ROM?" % HUB_OVERLAY)
    tables = grown_tables(hub_tables(ram, code), floor)
    buf = bytearray(code)
    for kind, table_ram in grown_tables_ram().items():
        buf += bytes(table_ram - ram - len(buf))
        buf += tables[kind]
    buf += bytes((-len(buf)) & 3)
    nds.store_overlay(rom, HUB_OVERLAY, bytes(buf), bss_size=0)
