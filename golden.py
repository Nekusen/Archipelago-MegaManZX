"""GENERADO — imagen dorada v2 del tutorial-skip (2026-09-02, agente exp400-409).

0x4F4 bytes de RAM 0x021602A8 (buffer del LOAD): tiempo de juego (+0x000,
frames) + palabra de escena (+0x008) + bloque canónico A (+0x00C..+0x0F0 ↔
0x021045CC) + bloque B/descriptor 2/cola 2 (ESPEJO: snapshot al aceptar
misión, FUN_02022744) + descriptor 1 = bloque persistente del jugador
(+0x1D4..+0x240 ↔ 0x0214FC5C: spawn, vidas, EC, modelo activo, personaje,
HP máx, capacidades, WE) + cola 1 = estado del guion de historia (+0x2AC..;
lo que dispara el briefing de Fleuve).

v2 = Continue real post-briefing (sin diálogo), tiempo 0, Disk B-3 y flags
de sala limpios, sin misión en curso, spawn (384,335) del piso A-2 del hub
(sub 70), dificultad NORMAL (+0x70 = 1: 0 Easy / 1 Normal / 2 Hard), vidas 2,
espejo = vivo. build_image() aplica el YAML ENCIMA (modelo activo, personaje,
posesión, WE del modelo inicial). Verificado en frío para X/Vent, none/Vent,
HX/Aile, FX/Vent + save/Continue + Game Over→New Game.
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

# --- offsets de la imagen (agente exp400-409; cada campo tiene ESPEJO) ---
BLOCK_OFF = 0x0C            # img[0x0C + k] <-> 0x021045CC + k (bloque A)
BLOCK_BASE = 0x021045CC
BLOCK_MIRROR = 0xE4         # bloque B = bloque A + 0xE4
PLAYER_OFF = 0x1D4          # descriptor 1 <-> 0x0214FC5C + k (bloque del jugador)
PLAYER_BASE = 0x0214FC5C
PLAYER_MIRROR = 0x6C        # descriptor 2 = descriptor 1 + 0x6C
OFF_ACTIVE_MODEL = 0x1EC    # 0x0214FC74
OFF_CHARACTER = 0x1ED       # 0x0214FC75 (el que manda); 0x71 = 0x02104631 (menú)
OFF_CHARACTER_BLOCK = 0x71
OFF_DIFFICULTY = 0x70       # 0x02104630: 0 Easy / 1 Normal / 2 Hard
OFF_LIVES = 0x1E4
OFF_WE = 0x20D              # 0x0214FC95 + (modelo - 3): WE actual de HX/FX/LX/PX
OFF_BOSS_LEVELS = 0x74      # 0x02104634..3B: niveles de victoria (tope de WE)
MODEL_LEVEL_IDX = {3: 0, 4: 2, 5: 1, 6: 3}   # 1er jefe del par: HX, FX, LX, PX
DIFFICULTY_NORMAL = 1
LIVES_BY_DIFFICULTY = (4, 2, 2)


def _set_bit(img: bytearray, off: int, bit: int, on: bool, mirror: int) -> None:
    for o in (off, off + mirror):
        img[o] = (img[o] | (1 << bit)) if on else (img[o] & ~(1 << bit) & 0xFF)


def _set_byte(img: bytearray, off: int, val: int, mirror: int) -> None:
    img[off] = val & 0xFF
    img[off + mirror] = val & 0xFF


def build_image(start_key: str, character: int, starting_models: dict) -> bytes:
    """Imagen dorada para un slot: modelo inicial (clave de STARTING_MODELS),
    personaje (0 Vent / 1 Aile). Idempotente y pura (sin AP)."""
    img = bytearray(GOLDEN_IMAGE)
    rec = starting_models.get(start_key) or starting_models.get("model_x")
    # posesión: X según revoke_x; grants del modelo (direcciones del bloque)
    _set_bit(img, BLOCK_OFF + (0x021045CF - BLOCK_BASE), 7, not rec.get("revoke_x", False), BLOCK_MIRROR)
    for addr, bit in rec.get("grant", []):
        if BLOCK_BASE <= addr < BLOCK_BASE + 0xE4:
            _set_bit(img, BLOCK_OFF + (addr - BLOCK_BASE), bit, True, BLOCK_MIRROR)
    active = int(rec.get("active", 1))
    _set_byte(img, OFF_ACTIVE_MODEL, active, PLAYER_MIRROR)
    # personaje: manda 0x0214FC75; 0x02104631 por coherencia del menú
    ch = 1 if int(character or 0) == 1 else 0
    _set_byte(img, OFF_CHARACTER, ch, PLAYER_MIRROR)
    _set_byte(img, OFF_CHARACTER_BLOCK, ch, BLOCK_MIRROR)
    # dificultad Normal + vidas coherentes
    _set_byte(img, OFF_DIFFICULTY, DIFFICULTY_NORMAL, BLOCK_MIRROR)
    _set_byte(img, OFF_LIVES, LIVES_BY_DIFFICULTY[DIFFICULTY_NORMAL], PLAYER_MIRROR)
    # Weapon Energy del modelo inicial: nivel del 1er jefe = 4 (tope 16) y barra llena
    if active in MODEL_LEVEL_IDX:
        _set_byte(img, OFF_BOSS_LEVELS + MODEL_LEVEL_IDX[active], 4, BLOCK_MIRROR)
        _set_byte(img, OFF_WE + (active - 3), 16, PLAYER_MIRROR)
    return bytes(img)
