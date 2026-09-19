"""Golden image: the starting save the patch bakes into the ROM for the tutorial skip.

It is the game's own LOAD buffer for a clean post-briefing game, built here
from named fields; the two tables every new save copies from the ROM come from
the player's copy at patch time. build_image applies the slot's options on top.
"""

import struct

from ..data import (ITEMS, LIVE_BLOCK, MODEL_BOSS_LEVEL_IDX, MODEL_X_POSSESSION, SCENE_WORDS,
                    STARTING_MODEL_ITEM, STARTING_TRANSERVERS)

GOLDEN_IMAGE_ADDR = 0x021602A8
GOLDEN_IMAGE_SIZE = 0x4F4

# Layout: a header, then three structures that each carry a mirror copy right after them.
OFF_SCENE_WORD = 0x08       # 0x021602B0: scene word of the room the LOAD enters
BLOCK_OFF = 0x0C            # progress block A, RAM 0x021045CC
BLOCK_LEN = 0xE4
BLOCK_MIRROR = BLOCK_LEN    # block B follows block A
DESC_OFF = 0x1D4            # player descriptor 1, RAM 0x0214FC5C
DESC_LEN = 0x6C
PLAYER_MIRROR = DESC_LEN    # descriptor 2 follows descriptor 1
QUEUE_OFF = 0x2AC           # story queue 1, RAM 0x02160554
QUEUE_LEN = 0x11C
QUEUE_MIRROR = QUEUE_LEN    # story queue 2 follows story queue 1

# Fields of the progress block (offsets within the block)
BLK_DIFFICULTY = 0x64       # 0x02104630: 0 Easy, 1 Normal, 2 Hard
BLK_CHARACTER = 0x65        # 0x02104631, the copy the menus read
BLK_BOSS_LEVELS = 0x68      # 0x02104634..3B: victory levels, WE cap
BLK_MISSION_STATE = 0xE0    # 0x021046AC
# Story flags a fresh post-briefing game has set: the intro, the briefing and the first hub visit.
BLK_STORY_FLAGS = (51, 52, 147, 148, 152, 428, 771, 816)
# Values the game's New Game writes and the randomizer never reads, kept so the save is the game's own.
BLK_NEWGAME_DEFAULTS = ((0xC0, b"\x64"), (0xC8, b"\x08\x07"), (0xD0, b"\xe8\x03"), (0xD8, b"\x64"))
MISSION_STATE_NONE = 0x92   # "No missions underway"

# Fields of the player descriptor (offsets within the descriptor)
DSC_SPAWN_X = 0x00          # 0x0216047C: spawn x << 8, then y << 8
DSC_SPAWN_Y = 0x04
DSC_SCENE_WORD = 0x08
DSC_CHECKPOINT = 0x0C
DSC_LIVES = 0x10
DSC_FACING = 0x11
DSC_ECRYSTALS = 0x14
DSC_ACTIVE_MODEL = 0x18     # 0x0214FC74
DSC_CHARACTER = 0x19        # 0x0214FC75, the copy the game reads
DSC_HP_MAX = 0x1A
DSC_WEAPONS = 0x24          # 0x0214FC80: the weapon of each model, a table of the ROM
DSC_WE = 0x39               # 0x0214FC95 + (model - MODEL_HX): WE of HX/FX/LX/PX
DSC_CONTROLS = 0x54         # 0x0214FCB0: the default button layout, a table of the ROM
DSC_NEWGAME_DEFAULTS = ((0x3E, b"\xff" * 16 + b"\x03"), (0x6A, b"\x01"))
CHECKPOINT_HUB_PAD = 0x29
FACING_RIGHT = 1
STARTING_ECRYSTALS = 20
HP_BASE = 0x10
# An idle story queue: no mission in progress, so nothing plays on entering the room.
QUEUE_IDLE = ((0x08, (0x67A).to_bytes(4, "little")), (0x11, b"\xff"))

# The two tables the game copies into every new save, read from the player's ROM at patch time.
ROM_WEAPON_TABLE = (0x020DF794, 16)
ROM_CONTROLS_TABLE = (0x020DF708, 20)

# Absolute offsets the tests and the patch share
OFF_SPAWN_X = DESC_OFF + DSC_SPAWN_X
OFF_SPAWN_Y = DESC_OFF + DSC_SPAWN_Y
OFF_ACTIVE_MODEL = DESC_OFF + DSC_ACTIVE_MODEL
OFF_CHARACTER = DESC_OFF + DSC_CHARACTER
OFF_CHARACTER_BLOCK = BLOCK_OFF + BLK_CHARACTER
OFF_DIFFICULTY = BLOCK_OFF + BLK_DIFFICULTY
OFF_LIVES = DESC_OFF + DSC_LIVES
OFF_WE = DESC_OFF + DSC_WE
OFF_BOSS_LEVELS = BLOCK_OFF + BLK_BOSS_LEVELS
MODEL_X_ADDR = MODEL_X_POSSESSION[0]
MODEL_X_BIT = MODEL_X_POSSESSION[1]
MODEL_HX = 3                # model ids 3..6 are HX, FX, LX, PX
VICTORY_LEVEL_MAX = 4       # a level 4 win over the first boss caps the WE at WE_FULL
WE_FULL = 16
DIFFICULTY_NORMAL = 1
LIVES_BY_DIFFICULTY = (4, 2, 2)
# The Transport destination bits, one per Transerver Access item; the baseline holds the default start's
TRANSERVER_BITS = [(v["grant"][1], v["grant"][2]) for v in ITEMS.values() if v["grant"][0] == "transerver"]
DEFAULT_START = next(iter(STARTING_TRANSERVERS.values()))


def _set_u32(img: bytearray, off: int, val: int, mirror: int) -> None:
    for o in (off, off + mirror):
        struct.pack_into("<I", img, o, val)


def _set_bit(img: bytearray, off: int, bit: int, on: bool, mirror: int) -> None:
    for o in (off, off + mirror):
        img[o] = (img[o] | (1 << bit)) if on else (img[o] & ~(1 << bit) & 0xFF)


def _set_byte(img: bytearray, off: int, val: int, mirror: int) -> None:
    img[off] = val & 0xFF
    img[off + mirror] = val & 0xFF


def _set_transerver_bits(img: bytearray, start: dict) -> None:
    """Of the Transport destinations, only the start point's is known from the beginning."""
    access = ITEMS.get(start.get("access") or "", {}).get("grant")
    for addr, bit in TRANSERVER_BITS:
        on = access is not None and (addr, bit) == (access[1], access[2])
        _set_bit(img, BLOCK_OFF + (addr - LIVE_BLOCK), bit, on, BLOCK_MIRROR)


def _set_start(img: bytearray, start: dict) -> None:
    """Spawn, scene word and Transport destination of a start point, in every copy that holds them."""
    _set_u32(img, OFF_SPAWN_X, int(start["x"]) << 8, PLAYER_MIRROR)
    _set_u32(img, OFF_SPAWN_Y, int(start["y"]) << 8, PLAYER_MIRROR)
    word = SCENE_WORDS.get(start["sub"], start["sub"])
    struct.pack_into("<I", img, OFF_SCENE_WORD, word)
    _set_u32(img, DESC_OFF + DSC_SCENE_WORD, word, PLAYER_MIRROR)
    _set_transerver_bits(img, start)


def baseline_image() -> bytearray:
    """A clean post-briefing save on Normal with Model X, standing on the default start point."""
    img = bytearray(GOLDEN_IMAGE_SIZE)
    block = bytearray(BLOCK_LEN)
    block[MODEL_X_ADDR - LIVE_BLOCK] |= 1 << MODEL_X_BIT
    for flag in BLK_STORY_FLAGS:
        byte, bit = divmod(flag, 8)
        block[byte] |= 1 << bit
    block[BLK_DIFFICULTY] = DIFFICULTY_NORMAL
    block[BLK_MISSION_STATE] = MISSION_STATE_NONE
    for off, data in BLK_NEWGAME_DEFAULTS:
        block[off:off + len(data)] = data
    desc = bytearray(DESC_LEN)
    desc[DSC_CHECKPOINT] = CHECKPOINT_HUB_PAD
    desc[DSC_LIVES] = LIVES_BY_DIFFICULTY[DIFFICULTY_NORMAL]
    desc[DSC_FACING] = FACING_RIGHT
    struct.pack_into("<I", desc, DSC_ECRYSTALS, STARTING_ECRYSTALS)
    desc[DSC_ACTIVE_MODEL] = 1   # Model X
    desc[DSC_HP_MAX] = HP_BASE
    for off, data in DSC_NEWGAME_DEFAULTS:
        desc[off:off + len(data)] = data
    queue = bytearray(QUEUE_LEN)
    for off, data in QUEUE_IDLE:
        queue[off:off + len(data)] = data
    for off, length, data in ((BLOCK_OFF, BLOCK_LEN, block), (DESC_OFF, DESC_LEN, desc), (QUEUE_OFF, QUEUE_LEN, queue)):
        img[off:off + length] = data
        img[off + length:off + 2 * length] = data
    _set_start(img, DEFAULT_START)
    return img


def second_half_bit(start_key: str) -> tuple[int, int] | None:
    """The second-half flag of a progressive starting model, or None for the others."""
    grant = ITEMS.get(STARTING_MODEL_ITEM.get(start_key, ""), {}).get("grant")
    if grant and grant[0] == "progressive":
        return int(grant[1][1][0]), int(grant[1][1][1])
    return None


def build_image(start_key: str, character: int, starting_models: dict, start: dict | None = None,
                full_models: bool = False) -> bytes:
    """Golden image for a slot: starting model key, character (0 Vent, 1 Aile) and start point.

    Pure and idempotent; no Archipelago objects involved. The start point
    (a STARTING_TRANSERVERS record) sets the spawn, the scene word and the one
    Transport destination known from the start. With full_models a progressive
    starting model owns both halves.
    """
    img = baseline_image()
    if start:
        _set_start(img, start)
    rec = starting_models.get(start_key) or starting_models.get("model_zx")
    # Model X unless revoked, plus the starting model's ownership bits
    _set_bit(img, BLOCK_OFF + (MODEL_X_ADDR - LIVE_BLOCK), MODEL_X_BIT, not rec.get("revoke_x", False), BLOCK_MIRROR)
    grants = list(rec.get("grant", []))
    if full_models and second_half_bit(start_key):
        grants.append(second_half_bit(start_key))
    for addr, bit in grants:
        if LIVE_BLOCK <= addr < LIVE_BLOCK + BLOCK_LEN:
            _set_bit(img, BLOCK_OFF + (addr - LIVE_BLOCK), bit, True, BLOCK_MIRROR)
    active = int(rec.get("active", 1))
    _set_byte(img, OFF_ACTIVE_MODEL, active, PLAYER_MIRROR)
    ch = 1 if int(character or 0) == 1 else 0
    _set_byte(img, OFF_CHARACTER, ch, PLAYER_MIRROR)
    _set_byte(img, OFF_CHARACTER_BLOCK, ch, BLOCK_MIRROR)
    # Normal difficulty + matching lives
    _set_byte(img, OFF_DIFFICULTY, DIFFICULTY_NORMAL, BLOCK_MIRROR)
    _set_byte(img, OFF_LIVES, LIVES_BY_DIFFICULTY[DIFFICULTY_NORMAL], PLAYER_MIRROR)
    # Weapon Energy of the starting model: 1st boss level = 4 (cap 16) and a full bar
    if active in MODEL_BOSS_LEVEL_IDX:
        first_boss = MODEL_BOSS_LEVEL_IDX[active][0]
        _set_byte(img, OFF_BOSS_LEVELS + first_boss, VICTORY_LEVEL_MAX, BLOCK_MIRROR)
        _set_byte(img, OFF_WE + (active - MODEL_HX), WE_FULL, PLAYER_MIRROR)
    return bytes(img)


def add_rom_tables(image: bytes, arm9) -> bytes:
    """Complete a slot's image with the two tables the game copies from its ROM into a new save."""
    img = bytearray(image)
    for dsc_off, (ram, size) in ((DSC_WEAPONS, ROM_WEAPON_TABLE), (DSC_CONTROLS, ROM_CONTROLS_TABLE)):
        table = arm9.read(ram, size)
        for off in (DESC_OFF + dsc_off, DESC_OFF + PLAYER_MIRROR + dsc_off):
            img[off:off + size] = table
    return bytes(img)
