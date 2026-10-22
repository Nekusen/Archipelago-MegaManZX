"""The .apmmzx patch for Mega Man ZX (USA): the ARM9 code patches, the AP icon set and the AP marker.

One module per domain applies its patches to the ARM9 (`pickups`, `sprites`, `ui`, `missions`, `story`, `lives`);
`arm9`, `blz` and `nds` handle the image, its compression and the ROM container.
"""

import struct

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

from . import doors, golden, lives, missions, nds, npc, omega, pickups, sprites, story, table, ui, zero
from .arm9 import Arm9, replace_arm9

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"

# AP marker, written by the token step into the zero padding after the header,
# and the option blob (mmzx_cfg.bin inside the .apmmzx) that patch_arm9 reads
# along with the slot's golden image (golden_image.bin), which it completes
# with the two tables the game copies from its ROM, and the slot's pickup
# table (pickup_table.bin).
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
AP_MARKER_LEN = 0x80
AP_MARKER_VERSION_OFF = 0x08              # u32 major << 16 | minor << 8 | build
AP_MARKER_SLOT_OFF = 0x10
AP_MARKER_SLOT_MAX = 63                   # bytes of UTF-8, then a NUL
AP_MARKER_SEED_OFF = 0x50
AP_MARKER_SEED_MAX = 31
CFG_HU_IN_POOL = 0x01                     # mmzx_cfg.bin byte 0, bit 0
CFG_STORY_ITEMS = 0x02                    # bit 1: mission_objectives is locations_and_items
CFG_STORY_ON = 0x04                       # bit 2: mission_objectives is on, in either mode
CFG_ZERO3 = 0x08                          # bit 3: the Mega Man Zero 3 bosses are checks
CFG_ZERO4 = 0x10                          # bit 4: the Mega Man Zero 4 bosses are checks
CFG_OMEGA_GOAL = 0x20                     # bit 5: the goal is Omega Zero
CFG_INFINITE_LIVES = 0x40                 # bit 6: a death costs no life
CFG_ZERO_GAMES = {zero.ZERO3: CFG_ZERO3, zero.ZERO4: CFG_ZERO4}
# mmzx_cfg.bin byte 1: the floor of the Sub Tank refill operator, by starting_transerver key; 0 = none
CFG_OPERATOR_BYTE = 1
CFG_OPERATOR_FLOORS = {"area_a": 1, "guardian_base": 2}
# The settings that hold the player's Zero 3 and Zero 4 ROMs, read only when the seed asks for them.
ZERO_ROM_SETTINGS = {zero.ZERO3: "zero3_rom_file", zero.ZERO4: "zero4_rom_file"}


def read_zero_roms(games: set[int]) -> dict[int, bytes]:
    """The GBA ROMs of the games whose bosses are in, from the settings; a missing one is asked for."""
    roms = {}
    for game in sorted(games):
        with open(getattr(get_settings().mmzx_settings, ZERO_ROM_SETTINGS[game]), "rb") as f:
            roms[game] = f.read()
        zero.check_rom(roms[game], game)
    return roms


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str, image_file: str,
                   table_file: str, locks_file: str = "") -> bytes:
        """Apply the code patches to the ARM9 and the ROM-level edits; returns the new image."""
        cfg = caller.get_file(cfg_file)
        # a patch made before the door constraints names no such file
        locks = doors.read_locks(caller.get_file(locks_file) if locks_file else None)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False
        story_items = bool(cfg[0] & CFG_STORY_ITEMS) if cfg else False
        story_on = story_items or (bool(cfg[0] & CFG_STORY_ON) if cfg else False)
        zero_games = {game for game, bit in CFG_ZERO_GAMES.items() if cfg and cfg[0] & bit}
        omega_goal = bool(cfg[0] & CFG_OMEGA_GOAL) if cfg else False
        infinite_lives = bool(cfg[0] & CFG_INFINITE_LIVES) if cfg else False
        operator_floor = next((floor for floor, code in CFG_OPERATOR_FLOORS.items()
                               if len(cfg) > CFG_OPERATOR_BYTE and cfg[CFG_OPERATOR_BYTE] == code), None)
        # the player's own Zero 3 / Zero 4 ROMs, asked for here and nowhere else
        zero_sets, zero_entries = zero.build_container(read_zero_roms(zero_games)) if zero_games else (b"", [])
        d = bytearray(rom)
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", d, nds.NDS_HDR_ARM9)
        arm9 = Arm9(bytes(d[arm9_off:arm9_off + arm9_len]), arm9_ram)
        image = golden.add_rom_tables(caller.get_file(image_file), arm9)

        ui.patch_tutorial_skip(arm9, image)
        sprites.patch_oam_loop_guards(arm9)
        pickups.patch_yellow_key_dialogue(arm9)
        pickups.patch_area_x_access(arm9)
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
        sprites.patch_carried_disk_icon(arm9)
        sprites.patch_sprite_guard(arm9)
        pickups.patch_pickup_ap(arm9)
        pickups.patch_refill_cut(arm9)
        pickups.patch_hu_gate(arm9, hu_in_pool)
        pickups.patch_secret_disks(arm9)
        pickups.patch_usables(arm9)
        missions.patch_mission_list(arm9)
        story.patch_story_items(arm9, story_items)
        ui.patch_goal_line(arm9)
        table.patch_pickup_table(arm9, caller.get_file(table_file))
        doors.patch_door_tables(arm9, locks)
        if operator_floor:
            npc.patch_npc_tables(arm9)
        if zero_games:
            zero.patch_loader(arm9, zero_entries)
            zero.patch_capsules(arm9, zero_games)
        if omega_goal:
            omega.patch_door_table(arm9)
        if infinite_lives:
            lives.patch_infinite_lives(arm9)

        # Recompress into the original slot; a rebuilt ROM shifts the layout (melonDS: bad_alloc)
        replace_arm9(d, arm9_off, arm9_len, arm9.pack())
        fnt_start = sprites.install_icon_set(d)
        ui.patch_menu_warp_text(d)
        ui.install_pause_texts(d)
        ui.install_talk_texts(d, npc.NPC_TEXTS if operator_floor else (), npc.NPC_TEXT_FIRST if operator_floor else None)
        ui.install_mission_names(d)
        pickups.patch_usable_rooms(d)
        if operator_floor:
            npc.patch_npc_room(d, operator_floor)
        story.patch_story_rooms(d, story_items)
        story.patch_bridge(d, story_on, story_items)
        sprites.patch_disk_logo(d, fnt_start)
        doors.patch_door_overlays(d, locks)
        if zero_games:
            zero.patch_rooms(d)
            zero.install_container(d, zero_sets)
        if omega_goal:
            omega.patch_door_overlay(d)
        nds.update_header_crc(d)
        return bytes(d)


class MMZXPatch(APProcedurePatch, APTokenMixin):
    """The .apmmzx patch: the ARM9 and ROM edits of patch_arm9, then the AP marker."""
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    procedure = [
        ("patch_arm9", ["mmzx_cfg.bin", "golden_image.bin", "pickup_table.bin", doors.LOCKS_FILE]),
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


# Older versions whose patched ROM a version of this world still plays: nothing in the ROM, or
# in what the client reads from it, changed between them.
PLAYABLE_ROM_VERSIONS = {(0, 2, 1): ((0, 2, 0),)}


def plays_rom(rom_version: int, world_version: tuple[int, int, int]) -> bool:
    """Whether the world of world_version plays a ROM whose marker holds rom_version."""
    patched_by = unpack_version(rom_version)
    return patched_by == tuple(world_version) or patched_by in PLAYABLE_ROM_VERSIONS.get(tuple(world_version), ())


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str,
                       world_version: tuple[int, int, int], golden_image: bytes,
                       pickup_table: bytes, hu_in_pool: bool = False,
                       story_items: bool = False, story_on: bool = False,
                       door_sites: dict[str, str] | None = None, zero_games=(),
                       omega_goal: bool = False, infinite_lives: bool = False,
                       refill_operator: str | None = None) -> None:
    """Write the AP marker (magic, version, slot, seed), the option blob, the golden image, the pickup table and the door locks.

    `world_version` is the world's (major, minor, build), as the core reads it
    from archipelago.json; `golden_image` is the slot's starting save and
    `pickup_table` the slot's table of pickup icons, both baked into the ARM9
    by patch_arm9.
    """
    patch.write_file("golden_image.bin", bytes(golden_image))
    patch.write_file("pickup_table.bin", bytes(pickup_table))
    patch.write_file(doors.LOCKS_FILE, doors.pack_locks(door_sites or {}))
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
    cfg[0] = ((CFG_HU_IN_POOL if hu_in_pool else 0) | (CFG_STORY_ITEMS if story_items else 0)
              | (CFG_STORY_ON if story_on or story_items else 0)
              | (CFG_OMEGA_GOAL if omega_goal else 0)
              | (CFG_INFINITE_LIVES if infinite_lives else 0))
    for game in zero_games:
        cfg[0] |= CFG_ZERO_GAMES[game]
    cfg[CFG_OPERATOR_BYTE] = CFG_OPERATOR_FLOORS[refill_operator] if refill_operator else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
