"""Patches on the sprite engine: the AP icon set kept resident, pickups drawn as the item
they hold, the shared palette, the guards that keep the drawers alive, and the disk logo."""

import hashlib
import struct

from ..assets import read as read_asset
from ..data import ICON_SET
from . import icons
from .arm9 import Arm9, thumb_bl
from .nds import FAT_ENTRY_LEN, FILE_ALIGN_MASK, NDS_HDR_FAT, NDS_HDR_FAT_SIZE, NDS_HDR_ROM_SIZE

# OAM drawer guards: two sprite loops exit only through `subs r5,#1; beq`; a zero
# count (frame table overwritten by a boss sheet) sprays RAM. `bls` exits at once.
OAM_LOOP_A_BR_RAM = 0x02009C30
OAM_LOOP_A_BR_ORIG = bytes.fromhex("01d0")   # beq
OAM_LOOP_A_BR_NEW = bytes.fromhex("01d9")    # bls
OAM_LOOP_B_BR_RAM = 0x02009D7C
OAM_LOOP_B_BR_ORIG = bytes.fromhex("01d0")
OAM_LOOP_B_BR_NEW = bytes.fromhex("01d9")

# AP icon set: pickups are drawn as the item placed there. icons.py builds the set
# (data.ICON_SET) from the player's ROM; it goes into obj_fnt/obj_dat and is made
# resident like set 58. The graphics caves share the zero stretch that ends at
# GFX_CAVES_END; which item a pickup shows comes from the pickup table (table.py).
ICON_FNT_FILE_ID, ICON_DAT_FILE_ID = 235, 234     # NitroFS ids of obj_fnt.bin, obj_dat.bin
GFX_CAVES_END = 0x020C8394
ICON_RESIDENT_LIST_PATCH = [
    # (RAM, vanilla, patched)
    (0x020C9C36, bytes.fromhex("0000"), bytes.fromhex("0501")),     # resident list [0, 1, 58] gains 261
    (0x0200BD16, bytes.fromhex("0322"), bytes.fromhex("0422")),     # list length 3 -> 4 (fnt)
    (0x0200BDB6, bytes.fromhex("0322"), bytes.fromhex("0422")),     # list length 3 -> 4 (dat)
]
# The boot cave uploads set 58 and registers set 261 without a palette of its own.
ICON_BOOT_HOOK_RAM = 0x0200BDA8                   # VRAM upload of set 58
ICON_BOOT_HOOK_ORIG = bytes.fromhex("faf7dcf9")
ICON_BOOT_CAVE_RAM = 0x020C8150
ICON_BOOT_CAVE = bytes.fromhex("10b584b000240094019401240294002403940f483a21002200230e4ca04701240094c0460c480d4909680d4a03230d4ca047002400940194012402940024039409480a4900220023094ca04700f074f840571002656100024057100234390f0205010000896a0002405710020501000065610002")

# Icon caves: LOOKUP jumps to the pickup table's lookup; ATTACH and ANIM replace
# the graphics calls of the three pickup inits.
ICON_CAVES_RAM = 0x020C81C4
ICON_CAVES = bytes.fromhex(
    "004b1847011b1902000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000030b504000d00fff7d4ff002808dbe17a0822"
    "9143e172217b0122914321730e4d200029000e4a904730bd30b504000d00428c"
    "0b4b9a4204d1fff7bbff002800db050020002900074a904730bd00bf00000000"
    "000000000000000005010000250601020501000065fe0002")
ICON_ATTACH_CAVE_RAM = 0x020C8212
ICON_ANIM_CAVE_RAM = 0x020C823C
# (RAM, vanilla bl); the patched bl is computed from the addresses
ICON_ATTACH_HOOKS = [(0x020A3BC4, bytes.fromhex("6cf72efd")), (0x020A3EEE, bytes.fromhex("6cf799fb")),
                     (0x020A36F4, bytes.fromhex("6cf796ff"))]
ICON_ANIM_HOOKS = [(0x020A3BCC, bytes.fromhex("6cf74af9")), (0x020A3EF6, bytes.fromhex("6bf7b5ff")),
                   (0x020A3706, bytes.fromhex("6cf7adfb"))]

# PALSHARE: set 261 borrows the palette slot of set 58. With a palette of its own,
# rooms using all 15 OBJ palettes would leave the next set unregistered and crash.
PALSHARE_CAVE_RAM = 0x020C8288
PALSHARE_CAVE = bytes.fromhex("03483a21415c0348017004b010bdc046e45e1002e95f1002")

# RETRY: a pickup born while the icons were switched off keeps its vanilla look;
# re-attach every frame once a code resolves. The refill site belongs to the
# mailbox cave, so RETRY chains on that cave's call.
ICON_RETRY_CAVE_RAM = 0x020C82A0
ICON_RETRY_CAVE = bytes.fromhex("30b50400628c0e4b9a4214d0fff78aff002810db0500e17a08229143e172217b0122914321732000064948f7abf92000290047f7c7fd200047f798fc30bd00bf0501000005010000")
ICON_RETRY_HOOKS = [(0x020CB4A2, bytes.fromhex("44f7b3fb")), (0x020A3A7E, bytes.fromhex("6cf7c5f8")),
                    (0x020A3CAA, bytes.fromhex("6bf7afff"))]

# Carried disk: the H-1 balloon creates Disk E-47 at run time and holds it, so the
# disk has no spawn record; attach, anim and retry look the icon up through the balloon.
ICON_CARRIED_CAVE_RAM = 0x020C82E8
ICON_CARRIED_CAVE = bytes.fromhex(
    "30b504000d00206bfff768ff002802db00f032f81d4d2000290048f78ff930bd"
    "30b504000d00628c184b9a4205d1206bfff754ff002800db05002000290047f7"
    "9dfd30bd30b50400628c104b9a420fd0206bfff743ff00280adb050000f00cf8"
    "20000a4948f76af92000290047f786fd200047f757fc30bde17a08229143e172"
    "217b012291432173704700bf05010000")
ICON_CARRIED_ANIM_CAVE_RAM = 0x020C8308
ICON_CARRIED_RETRY_CAVE_RAM = 0x020C832C
# (RAM, vanilla bl) of the carried disk's attach, anim and animation tick, in that order
ICON_CARRIED_HOOKS = [(0x020A40C6, bytes.fromhex("6cf7adfa")), (0x020A40CE, bytes.fromhex("6bf7c9fe")),
                      (0x020A3FF8, bytes.fromhex("6bf708fe"))]

# Sprite guard: when the registrar rejects a set (palette budget exhausted) ten
# drawers dereference a null slot record and data abort. The cave skips the read.
SPRITEGUARD_CAVE_RAM = 0x020C827C
SPRITEGUARD_CAVE = bytes.fromhex("002800d0408801237047")
SPRITEGUARD_ORIG = bytes.fromhex("40880123")
SPRITEGUARD_SITES = [0x0200F0D4, 0x0200F244, 0x0200F424, 0x0200F85A, 0x0200FA5A,
                     0x0200FC96, 0x0200FFA2, 0x02010236, 0x020104CA, 0x02010756]

# Secret Disk logo: the disk body tile of set 58 becomes the Archipelago logo of
# the Metroid Zero Mission apworld in the disk's palette; vanilla tile by digest.
DISK_LOGO_FNT_OFF = 0x5620C                       # disk body tile inside obj_fnt.bin
DISK_LOGO_SHA256 = "0cf5040681e341af0f130f438c12989c4747f7b7c531792025e6e8f9d9f8c65c"
DISK_LOGO_NEW = bytes.fromhex(
    "000000f00000009f00f0ff9900cfcc9ff0ccccfcf0ccccfcf0fcfffc005f550f"
    "ff000000990f000099f9ff00991f110ff91111f1f91111f1fff1fff1004f440f"
    "f05555f5f05555f5f05555af005ff5aa00f0ffaa0000f0aa000000af000000f0"
    "f04444f4ff4444f4aa4f44f4aafa440faafaff00aafa0000aa0f0000ff000000")


def patch_oam_loop_guards(arm9: Arm9) -> None:
    """Make the two OAM sprite loops exit on a zero count instead of spraying RAM."""
    arm9.write(OAM_LOOP_A_BR_RAM, OAM_LOOP_A_BR_NEW, OAM_LOOP_A_BR_ORIG)
    arm9.write(OAM_LOOP_B_BR_RAM, OAM_LOOP_B_BR_NEW, OAM_LOOP_B_BR_ORIG)


def patch_icon_set(arm9: Arm9) -> None:
    """Keep the AP icon set resident: a fourth entry in the resident list and its upload at boot."""
    assert ICON_BOOT_CAVE_RAM + len(ICON_BOOT_CAVE) <= ICON_CAVES_RAM
    for ram, orig, new in ICON_RESIDENT_LIST_PATCH:
        arm9.write(ram, new, orig)
    arm9.write(ICON_BOOT_CAVE_RAM, ICON_BOOT_CAVE)
    arm9.write(ICON_BOOT_HOOK_RAM, thumb_bl(ICON_BOOT_HOOK_RAM, ICON_BOOT_CAVE_RAM), ICON_BOOT_HOOK_ORIG)


def patch_item_icons(arm9: Arm9) -> None:
    """Draw pickups as the item placed there: LOOKUP, ATTACH and ANIM caves on the three pickup inits."""
    assert ICON_CAVES_RAM + len(ICON_CAVES) <= GFX_CAVES_END
    arm9.write(ICON_CAVES_RAM, ICON_CAVES)
    for ram, orig in ICON_ATTACH_HOOKS:
        arm9.write(ram, thumb_bl(ram, ICON_ATTACH_CAVE_RAM), orig)
    for ram, orig in ICON_ANIM_HOOKS:
        arm9.write(ram, thumb_bl(ram, ICON_ANIM_CAVE_RAM), orig)


def patch_palshare(arm9: Arm9) -> None:
    """Place the cave the boot cave calls to lend set 261 the palette slot of set 58."""
    assert PALSHARE_CAVE_RAM + len(PALSHARE_CAVE) <= GFX_CAVES_END
    arm9.write(PALSHARE_CAVE_RAM, PALSHARE_CAVE)


def patch_icon_retry(arm9: Arm9) -> None:
    """Re-attach the icon every frame to a pickup born before the client's table arrived."""
    assert ICON_RETRY_CAVE_RAM >= PALSHARE_CAVE_RAM + len(PALSHARE_CAVE)
    assert ICON_RETRY_CAVE_RAM + len(ICON_RETRY_CAVE) <= GFX_CAVES_END
    arm9.write(ICON_RETRY_CAVE_RAM, ICON_RETRY_CAVE)
    for ram, orig in ICON_RETRY_HOOKS:
        arm9.write(ram, thumb_bl(ram, ICON_RETRY_CAVE_RAM), orig)


def patch_carried_disk_icon(arm9: Arm9) -> None:
    """Draw the disk the H-1 balloon holds as its item, looked up through the balloon."""
    assert ICON_CARRIED_CAVE_RAM >= ICON_RETRY_CAVE_RAM + len(ICON_RETRY_CAVE)
    assert ICON_CARRIED_CAVE_RAM + len(ICON_CARRIED_CAVE) <= GFX_CAVES_END
    arm9.write(ICON_CARRIED_CAVE_RAM, ICON_CARRIED_CAVE)
    entries = (ICON_CARRIED_CAVE_RAM, ICON_CARRIED_ANIM_CAVE_RAM, ICON_CARRIED_RETRY_CAVE_RAM)
    for (ram, orig), entry in zip(ICON_CARRIED_HOOKS, entries):
        arm9.write(ram, thumb_bl(ram, entry), orig)


def patch_sprite_guard(arm9: Arm9) -> None:
    """Skip a sprite whose set got no VRAM slot instead of reading through a null record."""
    assert SPRITEGUARD_CAVE_RAM + len(SPRITEGUARD_CAVE) <= GFX_CAVES_END
    assert SPRITEGUARD_CAVE_RAM >= ICON_CAVES_RAM + len(ICON_CAVES)
    arm9.write(SPRITEGUARD_CAVE_RAM, SPRITEGUARD_CAVE)
    for ram in SPRITEGUARD_SITES:
        arm9.write(ram, thumb_bl(ram, SPRITEGUARD_CAVE_RAM), SPRITEGUARD_ORIG)


def _insert_set(blob: bytes, setno: int, block: bytes) -> bytes:
    """Insert `block` as the empty set `setno` of an obj_fnt/obj_dat container."""
    n = struct.unpack_from("<I", blob, 0)[0]
    offs = [struct.unpack_from("<I", blob, 4 + i * 4)[0] for i in range(n + 1)]
    if offs[n] != len(blob):
        raise ValueError("MMZX: unexpected offset table in the sprite set file")
    if offs[setno] != offs[setno + 1]:
        raise ValueError("MMZX: sprite set %d is not empty" % setno)
    block = block + bytes((-len(block)) % 4)
    new = bytearray(blob[:4])
    for i in range(n + 1):
        new += struct.pack("<I", offs[i] + (len(block) if i > setno else 0))
    new += blob[4 + (n + 1) * 4:offs[setno]] + block + blob[offs[setno]:]
    return bytes(new)


def install_icon_set(d: bytearray) -> int:
    """Insert the AP icon set into obj_dat/obj_fnt and relocate both files to the end padding.

    Returns the new ROM offset of obj_fnt.bin.
    """
    fat = struct.unpack_from("<I", d, NDS_HDR_FAT)[0]
    fatsize = struct.unpack_from("<I", d, NDS_HDR_FAT_SIZE)[0]
    used = max(struct.unpack_from("<II", d, fat + k * FAT_ENTRY_LEN)[1]
               for k in range(fatsize // FAT_ENTRY_LEN))
    cur = (used + FILE_ALIGN_MASK) & ~FILE_ALIGN_MASK
    files = {}
    for fid in (ICON_DAT_FILE_ID, ICON_FNT_FILE_ID):
        s0, e0 = struct.unpack_from("<II", d, fat + fid * FAT_ENTRY_LEN)
        files[fid] = bytes(d[s0:e0])
    fnt_block, dat_block = icons.build_icon_set(files[ICON_FNT_FILE_ID], files[ICON_DAT_FILE_ID], read_asset)
    fnt_start = None
    for fid, block in ((ICON_DAT_FILE_ID, dat_block), (ICON_FNT_FILE_ID, fnt_block)):
        newfile = _insert_set(files[fid], ICON_SET, block)
        if cur + len(newfile) > len(d) or any(d[cur:cur + len(newfile)]):
            raise ValueError("MMZX: no free padding to relocate file %d" % fid)
        d[cur:cur + len(newfile)] = newfile
        struct.pack_into("<II", d, fat + fid * FAT_ENTRY_LEN, cur, cur + len(newfile))
        if fid == ICON_FNT_FILE_ID:
            fnt_start = cur
        cur = (cur + len(newfile) + FILE_ALIGN_MASK) & ~FILE_ALIGN_MASK
    struct.pack_into("<I", d, NDS_HDR_ROM_SIZE, cur)
    return fnt_start


def patch_disk_logo(rom: bytearray, fnt_start: int) -> None:
    """Replace the Secret Disk body tile of set 58, inside the relocated obj_fnt.bin, with the AP logo."""
    logo_off = fnt_start + DISK_LOGO_FNT_OFF
    cur = bytes(rom[logo_off:logo_off + len(DISK_LOGO_NEW)])
    if cur == DISK_LOGO_NEW:
        return
    if hashlib.sha256(cur).hexdigest() != DISK_LOGO_SHA256:
        raise ValueError("MMZX: unexpected disk tile at ROM 0x%X (%s)" % (logo_off, cur[:8].hex()))
    rom[logo_off:logo_off + len(DISK_LOGO_NEW)] = DISK_LOGO_NEW
