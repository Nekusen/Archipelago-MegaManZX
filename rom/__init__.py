"""The .apmmzx patch for Mega Man ZX (USA): the ARM9 code patches, the AP icon set and the AP marker.

One module per domain applies its patches to the ARM9 (`pickups`, `sprites`, `ui`);
`arm9`, `blz` and `nds` handle the image, its compression and the ROM container.
"""

import struct

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

from . import nds, pickups, sprites, ui
from .arm9 import Arm9, replace_arm9

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"

# AP marker, written by the token step into the zero padding after the header,
# and the option blob (mmzx_cfg.bin inside the .apmmzx) that patch_arm9 reads.
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
AP_MARKER_LEN = 0x80
AP_MARKER_VERSION_OFF = 0x08              # u32 major << 16 | minor << 8 | build
AP_MARKER_SLOT_OFF = 0x10
AP_MARKER_SLOT_MAX = 63                   # bytes of UTF-8, then a NUL
AP_MARKER_SEED_OFF = 0x50
AP_MARKER_SEED_MAX = 31
CFG_HU_IN_POOL = 0x01                     # mmzx_cfg.bin byte 0, bit 0


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Apply the code patches to the ARM9 and the ROM-level edits; returns the new image."""
        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        d = bytearray(rom)
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", d, nds.NDS_HDR_ARM9)
        arm9 = Arm9(bytes(d[arm9_off:arm9_off + arm9_len]), arm9_ram)

        ui.patch_tutorial_skip(arm9)
        sprites.patch_oam_loop_guards(arm9)
        pickups.patch_yellow_key_dialogue(arm9)
        pickups.patch_biometal_ownership(arm9)
        pickups.patch_life_up_sub_tank(arm9)
        pickups.patch_pickup_mailbox(arm9)
        pickups.patch_data_select_icons(arm9)
        ui.patch_menu_warp(arm9)
        ui.patch_notify(arm9)
        ui.patch_cutscene_skip(arm9)
        sprites.patch_icon_set(arm9)
        sprites.patch_item_icons(arm9)
        sprites.patch_palshare(arm9)
        sprites.patch_icon_retry(arm9)
        sprites.patch_sprite_guard(arm9)
        pickups.patch_pickup_ap(arm9)
        pickups.patch_hu_gate(arm9, hu_in_pool)

        # Recompress into the original slot; a rebuilt ROM shifts the layout (melonDS: bad_alloc)
        replace_arm9(d, arm9_off, arm9_len, arm9.pack())
        fnt_start = sprites.install_icon_set(d)
        ui.patch_menu_warp_text(d)
        sprites.patch_disk_logo(d, fnt_start)
        nds.update_header_crc(d)
        return bytes(d)


class MMZXPatch(APProcedurePatch, APTokenMixin):
    """The .apmmzx patch: the ARM9 and ROM edits of patch_arm9, then the AP marker."""
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    procedure = [
        ("patch_arm9", ["mmzx_cfg.bin"]),
        ("apply_tokens", ["token_data.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(get_settings().mmzx_settings.rom_file, "rb") as f:
            return f.read()


def pack_version(version: tuple[int, int, int]) -> int:
    """The world's (major, minor, build) as the u32 stored in the AP marker."""
    major, minor, build = version
    return major << 16 | minor << 8 | build


def unpack_version(word: int) -> tuple[int, int, int]:
    return word >> 16, (word >> 8) & 0xFF, word & 0xFF


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str,
                       world_version: tuple[int, int, int], hu_in_pool: bool = False) -> None:
    """Write the AP marker (magic, version, slot, seed) and the option blob read by patch_arm9.

    `world_version` is the world's (major, minor, build), as the core reads it
    from archipelago.json.
    """
    blob = bytearray(AP_MARKER_LEN)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    version = pack_version(world_version)
    blob[AP_MARKER_VERSION_OFF:AP_MARKER_VERSION_OFF + 4] = version.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:AP_MARKER_SLOT_MAX]
    blob[AP_MARKER_SLOT_OFF:AP_MARKER_SLOT_OFF + len(name)] = name
    seed = seed_name.encode("utf-8")[:AP_MARKER_SEED_MAX]
    blob[AP_MARKER_SEED_OFF:AP_MARKER_SEED_OFF + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
    # option flags for patch_arm9, which runs before apply_tokens
    cfg = bytearray(4)
    cfg[0] = CFG_HU_IN_POOL if hu_in_pool else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
