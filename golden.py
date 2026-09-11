"""GENERATED -- golden image v2 of the tutorial-skip (2026-09-02, agent exp400-409).

0x4F4 bytes of RAM 0x021602A8 (LOAD buffer): play time (+0x000, frames) +
scene word (+0x008) + canonical block A (+0x00C..+0x0F0 <-> 0x021045CC) +
block B/descriptor 2/tail 2 (MIRROR: snapshot taken when a mission is
accepted, FUN_02022744) + descriptor 1 = persistent player block
(+0x1D4..+0x240 <-> 0x0214FC5C: spawn, lives, EC, active model, character,
max HP, capacities, WE) + tail 1 = state of the story script (+0x2AC..;
what triggers Fleuve's briefing).

v2 = real post-briefing Continue (no dialogue), time 0, Disk B-3 and room
flags clean, no mission in progress, spawn (384,335) on floor A-2 of the hub
(sub 70), NORMAL difficulty (+0x70 = 1: 0 Easy / 1 Normal / 2 Hard), 2 lives,
mirror = live. build_image() applies the YAML ON TOP (active model, character,
ownership, WE of the starting model). Cold-verified for X/Vent, none/Vent,
HX/Aile, FX/Vent + save/Continue + Game Over -> New Game.
"""

import base64

GOLDEN_IMAGE_ADDR = 0x021602A8
GOLDEN_IMAGE_B64 = (
    "AAAAAAAAAABGEBF6AAAAgAAAGAAAAAAAAAAAAAAAGAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAACAAAAAEA"
    "AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAZAAAAAAAAAAIBwAAAAAAAOgDAAAAAAAA"
    "ZAAAAAAAAACSAAAAAAAAgAAAGAAAAAAAAAAAAAAAGAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAACAAAAAEA"
    "AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAZAAAAAAAAAAIBwAAAAAAAOgDAAAAAAAA"
    "ZAAAAAAAAACSAAAAAIABAABPAQBGEBF6KQAAAAIBAAAUAAAAAQAQAAAAAAAAAAAAAAABAQIDBAUG"
    "BwgICQkKCwAAAAAAAAAAAAD/////////////////////AwAAAAAAQACAACAAEAAACAABAgAAAgAE"
    "AQAAAAEAAIABAABPAQBGEBF6KQAAAAIBAAAUAAAAAQAQAAAAAAAAAAAAAAABAQIDBAUGBwgICQkK"
    "CwAAAAAAAAAAAAD/////////////////////AwAAAAAAQACAACAAEAAACAABAgAAAgAEAQAAAAEA"
    "AAAAAAAAAAB6BgAAAAAAAAD/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAHoGAAAAAAAAAP8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAA="
)
GOLDEN_IMAGE = base64.b64decode(GOLDEN_IMAGE_B64)
assert len(GOLDEN_IMAGE) == 0x4F4

# --- offsets within the image (agent exp400-409; every field has a MIRROR) ---
BLOCK_OFF = 0x0C            # img[0x0C + k] <-> 0x021045CC + k (block A)
BLOCK_BASE = 0x021045CC
BLOCK_MIRROR = 0xE4         # block B = block A + 0xE4
PLAYER_OFF = 0x1D4          # descriptor 1 <-> 0x0214FC5C + k (player block)
PLAYER_BASE = 0x0214FC5C
PLAYER_MIRROR = 0x6C        # descriptor 2 = descriptor 1 + 0x6C
OFF_ACTIVE_MODEL = 0x1EC    # 0x0214FC74
OFF_CHARACTER = 0x1ED       # 0x0214FC75 (the authoritative one); 0x71 = 0x02104631 (menu)
OFF_CHARACTER_BLOCK = 0x71
OFF_DIFFICULTY = 0x70       # 0x02104630: 0 Easy / 1 Normal / 2 Hard
OFF_LIVES = 0x1E4
OFF_WE = 0x20D              # 0x0214FC95 + (model - 3): current WE of HX/FX/LX/PX
OFF_BOSS_LEVELS = 0x74      # 0x02104634..3B: victory levels (WE cap)
MODEL_LEVEL_IDX = {3: 0, 4: 2, 5: 1, 6: 3}   # 1st boss of the pair: HX, FX, LX, PX
DIFFICULTY_NORMAL = 1
LIVES_BY_DIFFICULTY = (4, 2, 2)


def _set_bit(img: bytearray, off: int, bit: int, on: bool, mirror: int) -> None:
    for o in (off, off + mirror):
        img[o] = (img[o] | (1 << bit)) if on else (img[o] & ~(1 << bit) & 0xFF)


def _set_byte(img: bytearray, off: int, val: int, mirror: int) -> None:
    img[off] = val & 0xFF
    img[off + mirror] = val & 0xFF


def build_image(start_key: str, character: int, starting_models: dict) -> bytes:
    """Golden image for a slot: starting model (STARTING_MODELS key),
    character (0 Vent / 1 Aile). Idempotent and pure (no AP)."""
    img = bytearray(GOLDEN_IMAGE)
    rec = starting_models.get(start_key) or starting_models.get("model_x")
    # ownership: X according to revoke_x; grants of the model (block addresses)
    _set_bit(img, BLOCK_OFF + (0x021045CF - BLOCK_BASE), 7, not rec.get("revoke_x", False), BLOCK_MIRROR)
    for addr, bit in rec.get("grant", []):
        if BLOCK_BASE <= addr < BLOCK_BASE + 0xE4:
            _set_bit(img, BLOCK_OFF + (addr - BLOCK_BASE), bit, True, BLOCK_MIRROR)
    active = int(rec.get("active", 1))
    _set_byte(img, OFF_ACTIVE_MODEL, active, PLAYER_MIRROR)
    # character: 0x0214FC75 is authoritative; 0x02104631 for menu consistency
    ch = 1 if int(character or 0) == 1 else 0
    _set_byte(img, OFF_CHARACTER, ch, PLAYER_MIRROR)
    _set_byte(img, OFF_CHARACTER_BLOCK, ch, BLOCK_MIRROR)
    # Normal difficulty + matching lives
    _set_byte(img, OFF_DIFFICULTY, DIFFICULTY_NORMAL, BLOCK_MIRROR)
    _set_byte(img, OFF_LIVES, LIVES_BY_DIFFICULTY[DIFFICULTY_NORMAL], PLAYER_MIRROR)
    # Weapon Energy of the starting model: 1st boss level = 4 (cap 16) and a full bar
    if active in MODEL_LEVEL_IDX:
        _set_byte(img, OFF_BOSS_LEVELS + MODEL_LEVEL_IDX[active], 4, BLOCK_MIRROR)
        _set_byte(img, OFF_WE + (active - 3), 16, PLAYER_MIRROR)
    return bytes(img)
