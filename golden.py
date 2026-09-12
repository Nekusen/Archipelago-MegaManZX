"""Golden image: the save image the client seeds for the tutorial skip.

GOLDEN_IMAGE is a dump of the game's own LOAD buffer in a clean post-briefing
state (Normal difficulty, hub floor, no mission in progress); build_image
applies the slot's starting model and character on top. Layout in
docs/memory_map.md, section 5.
"""

import pkgutil

from .data import LIVE_BLOCK, MODEL_X_POSSESSION

GOLDEN_IMAGE_ADDR = 0x021602A8
GOLDEN_IMAGE_SIZE = 0x4F4
GOLDEN_IMAGE = pkgutil.get_data(__name__, "assets/golden_image.bin")
assert len(GOLDEN_IMAGE) == GOLDEN_IMAGE_SIZE

# Offsets within the image; every field has a mirror copy.
BLOCK_OFF = 0x0C            # progress block A, RAM 0x021045CC
BLOCK_LEN = 0xE4
BLOCK_MIRROR = BLOCK_LEN    # block B follows block A
PLAYER_MIRROR = 0x6C        # descriptor 2 = descriptor 1 (0x1D4, RAM 0x0214FC5C) + 0x6C
OFF_ACTIVE_MODEL = 0x1EC    # 0x0214FC74
OFF_CHARACTER = 0x1ED       # 0x0214FC75, the copy the game reads
OFF_CHARACTER_BLOCK = 0x71  # 0x02104631, the copy the menus read
OFF_DIFFICULTY = 0x70       # 0x02104630: 0 Easy, 1 Normal, 2 Hard
OFF_LIVES = 0x1E4
OFF_WE = 0x20D              # 0x0214FC95 + (model - MODEL_HX): WE of HX/FX/LX/PX
OFF_BOSS_LEVELS = 0x74      # 0x02104634..3B: victory levels, WE cap
MODEL_X_ADDR = MODEL_X_POSSESSION[0]
MODEL_X_BIT = MODEL_X_POSSESSION[1]
MODEL_HX = 3                # model ids 3..6 are HX, FX, LX, PX
MODEL_LEVEL_IDX = {3: 0, 4: 2, 5: 1, 6: 3}   # first boss of the pair: HX, FX, LX, PX
VICTORY_LEVEL_MAX = 4       # a level 4 win over the first boss caps the WE at WE_FULL
WE_FULL = 16
DIFFICULTY_NORMAL = 1
LIVES_BY_DIFFICULTY = (4, 2, 2)


def _set_bit(img: bytearray, off: int, bit: int, on: bool, mirror: int) -> None:
    for o in (off, off + mirror):
        img[o] = (img[o] | (1 << bit)) if on else (img[o] & ~(1 << bit) & 0xFF)


def _set_byte(img: bytearray, off: int, val: int, mirror: int) -> None:
    img[off] = val & 0xFF
    img[off + mirror] = val & 0xFF


def build_image(start_key: str, character: int, starting_models: dict) -> bytes:
    """Golden image for a slot: starting model key and character (0 Vent, 1 Aile).

    Pure and idempotent; no Archipelago objects involved.
    """
    img = bytearray(GOLDEN_IMAGE)
    rec = starting_models.get(start_key) or starting_models.get("model_x")
    # Model X unless revoked, plus the starting model's ownership bits
    _set_bit(img, BLOCK_OFF + (MODEL_X_ADDR - LIVE_BLOCK), MODEL_X_BIT, not rec.get("revoke_x", False), BLOCK_MIRROR)
    for addr, bit in rec.get("grant", []):
        if LIVE_BLOCK <= addr < LIVE_BLOCK + BLOCK_LEN:
            _set_bit(img, BLOCK_OFF + (addr - LIVE_BLOCK), bit, True, BLOCK_MIRROR)
    active = int(rec.get("active", 1))
    _set_byte(img, OFF_ACTIVE_MODEL, active, PLAYER_MIRROR)
    # character in the player block and in the menu copy
    ch = 1 if int(character or 0) == 1 else 0
    _set_byte(img, OFF_CHARACTER, ch, PLAYER_MIRROR)
    _set_byte(img, OFF_CHARACTER_BLOCK, ch, BLOCK_MIRROR)
    # Normal difficulty + matching lives
    _set_byte(img, OFF_DIFFICULTY, DIFFICULTY_NORMAL, BLOCK_MIRROR)
    _set_byte(img, OFF_LIVES, LIVES_BY_DIFFICULTY[DIFFICULTY_NORMAL], PLAYER_MIRROR)
    # Weapon Energy of the starting model: 1st boss level = 4 (cap 16) and a full bar
    if active in MODEL_LEVEL_IDX:
        _set_byte(img, OFF_BOSS_LEVELS + MODEL_LEVEL_IDX[active], VICTORY_LEVEL_MAX, BLOCK_MIRROR)
        _set_byte(img, OFF_WE + (active - MODEL_HX), WE_FULL, PLAYER_MIRROR)
    return bytes(img)
