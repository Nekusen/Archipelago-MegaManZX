"""Door constraints in the ROM: the doors of a seed's sites take their key and its colour."""

import json
import struct

from ..door_data import ROOMS, SITES
from . import nds
from .arm9 import Arm9, thumb_bl
from .ui import ROOM_OVERLAY_SLOT_RAM

# A door is an entity template in its room's overlay. Its role byte carries the key in
# bits 4 to 6 and its modifier byte picks the look; 1 to 5 are the five key colours.
TEMPLATE_LEN = 12
TEMPLATE_ROLE = 3
TEMPLATE_MODIFIER = 4
ROLE_WALKED = 0x01                  # crossed by walking, drawn as a gate; kept
ROLE_KEY_SHIFT = 4
COORD_SLOT_OFF = 6                  # u16 template index inside a coordinates entry
KEY_TYPES = {"Red Card Key": 1, "Blue Card Key": 2, "Purple Card Key": 3, "Yellow Card Key": 4,
             "Green Card Key": 5}
LOCKS_FILE = "door_locks.json"      # {site name: key item} inside the .apmmzx

# Closed sprite of the doors opened with UP: an autoload section between the pickup table
# and the room overlay slot, and its two hooks in the door think.
DOOR_CLOSED_CAVE_RAM = 0x02193800
DOOR_OPENING_CAVE_RAM = 0x0219385C
DOOR_CAVES = bytes.fromhex(
    "10b5041c1c498847207d8221084223d17021084220d0607d401e04281cd81020"
    "20850121201c2a300170617d4a001349895a201c124a9047201c0021114a9047"
    "201c114a9047a17a01200143a172201c617d491e0d4a904710bdc046a07a0121"
    "084202d1102020857047201c0021054a904707480047c0464dee00026c9e0e02"
    "2506010265fe00020dfc0002a5ee0002e1270902")
DOOR_CLOSED_HOOK_RAM = 0x02092508
DOOR_CLOSED_HOOK_ORIG = bytes.fromhex("7cf7a0fc")       # bl release_palette
DOOR_OPENING_HOOK_RAM = 0x020927A0
DOOR_OPENING_HOOK_ORIG = bytes.fromhex("10202085")      # movs r0, #0x10 ; strh r0, [r4, #0x28]


def pack_locks(sites: dict[str, str]) -> bytes:
    """The seed's sites and keys as the file the patch carries."""
    return json.dumps(sites, sort_keys=True).encode("utf-8")


def read_locks(blob: bytes | None) -> dict[str, str]:
    """{site name: key item} from the patch file; a patch without the file locks nothing."""
    locks = json.loads(blob.decode("utf-8")) if blob else {}
    for name, key in locks.items():
        if name not in SITES or key not in KEY_TYPES:
            raise ValueError("MMZX: unknown door constraint %r: %r. The patch needs a newer world." % (name, key))
    return locks


def locked_template(template: bytes, key: str) -> bytes:
    """The template of a door once it asks for `key` and shows its colour."""
    out = bytearray(template)
    out[TEMPLATE_ROLE] = (template[TEMPLATE_ROLE] & ROLE_WALKED) | (KEY_TYPES[key] << ROLE_KEY_SHIFT)
    out[TEMPLATE_MODIFIER] = KEY_TYPES[key]
    return bytes(out)


def room_edits(locks: dict[str, str]) -> dict[str, dict]:
    """Per room: templates rewritten in place, templates to add and the coordinates that move to them.

    A template other entities share cannot change under them, so the door gets a copy
    at the end of a longer table.
    """
    rooms: dict[str, dict] = {}
    for name in sorted(locks):
        for face in SITES[name]["faces"]:
            room = face["room"]
            edit = rooms.setdefault(room, {"writes": [], "templates": [], "moves": []})
            old = bytes.fromhex(face["template"])
            new = locked_template(old, locks[name])
            if face["shared"]:
                index = ROOMS[room]["slot_count"] + len(edit["templates"])
                edit["templates"].append(new)
                edit["moves"].append((face["coord"] + COORD_SLOT_OFF, face["slot"], index))
            else:
                edit["writes"].append((ROOMS[room]["slots"] + face["slot"] * TEMPLATE_LEN, old, new))
    return rooms


def grown_table_ram(room: str) -> int:
    """RAM address of a room's longer template table: after its code and bss, on a word."""
    info = ROOMS[room]
    return ROOM_OVERLAY_SLOT_RAM + ((info["size"] + info["bss"] + 3) & ~3)


def has_up_door(locks: dict[str, str]) -> bool:
    """Whether a locked face opens with UP, the kind that needs the closed sprite."""
    return any(not bytes.fromhex(face["template"])[TEMPLATE_ROLE] & ROLE_WALKED
               for name in locks for face in SITES[name]["faces"])


def patch_door_tables(arm9: Arm9, locks: dict[str, str]) -> None:
    """The ARM9 side: the pointers of the template tables that grow, and the closed sprite."""
    for room, edit in room_edits(locks).items():
        if edit["templates"]:
            info = ROOMS[room]
            arm9.write(info["slots_pointer"], struct.pack("<I", grown_table_ram(room)),
                       struct.pack("<I", info["slots"]))
    if has_up_door(locks):
        assert DOOR_CLOSED_CAVE_RAM % 4 == 0 and len(DOOR_CAVES) % 4 == 0
        assert DOOR_CLOSED_CAVE_RAM < DOOR_OPENING_CAVE_RAM < DOOR_CLOSED_CAVE_RAM + len(DOOR_CAVES)
        assert DOOR_CLOSED_CAVE_RAM + len(DOOR_CAVES) <= ROOM_OVERLAY_SLOT_RAM
        arm9.add_section(DOOR_CLOSED_CAVE_RAM, DOOR_CAVES)
        arm9.write(DOOR_CLOSED_HOOK_RAM, thumb_bl(DOOR_CLOSED_HOOK_RAM, DOOR_CLOSED_CAVE_RAM),
                   DOOR_CLOSED_HOOK_ORIG)
        arm9.write(DOOR_OPENING_HOOK_RAM, thumb_bl(DOOR_OPENING_HOOK_RAM, DOOR_OPENING_CAVE_RAM),
                   DOOR_OPENING_HOOK_ORIG)


def patch_door_overlays(rom: bytearray, locks: dict[str, str]) -> None:
    """The room side: every locked door gets its key and colour in its room's overlay."""
    for room, edit in sorted(room_edits(locks).items()):
        info = ROOMS[room]
        if not edit["templates"]:
            nds.patch_overlay(rom, info["overlay"], edit["writes"])
            continue
        ram, code = nds.overlay_code(rom, info["overlay"])
        if len(code) != info["size"] or nds.overlay_bss_size(rom, info["overlay"]) != info["bss"]:
            raise ValueError("MMZX: overlay %d is not the one of the original ROM. Wrong ROM?" % info["overlay"])
        buf = bytearray(code)
        for addr, old, new in edit["writes"]:
            off = addr - ram
            if bytes(buf[off:off + TEMPLATE_LEN]) != old:
                raise ValueError("MMZX: unexpected door template at 0x%08X. Wrong ROM?" % addr)
            buf[off:off + TEMPLATE_LEN] = new
        table = info["slots"] - ram
        table = bytes(buf[table:table + info["slot_count"] * TEMPLATE_LEN])
        # the old bss becomes zeros of the file, so what the code keeps there still starts clear
        buf += bytes(grown_table_ram(room) - ram - len(buf))
        buf += table + b"".join(edit["templates"])
        for addr, old_slot, new_slot in edit["moves"]:
            off = addr - ram
            if struct.unpack_from("<H", buf, off)[0] != old_slot:
                raise ValueError("MMZX: unexpected door entry at 0x%08X. Wrong ROM?" % addr)
            struct.pack_into("<H", buf, off, new_slot)
        nds.store_overlay(rom, info["overlay"], bytes(buf), bss_size=0)
