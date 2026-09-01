"""Parche de ROM de Mega Man ZX (v0.1: marca AP + slot name).

Enfoque ligero (docs/playbook_ds_ap.md): el cliente opera por RAM, así
que el parche solo marca la ROM como seed AP y embebe el slot name para
validate_rom/set_auth. Se escribe en 0x1000 (zona de padding tras la
cabecera NDS; verificado a ceros en la ROM base, mismo truco que usa
Pokémon Platinum para su versión).

Layout en 0x1000:
  +0x00  b"MZXAP\\x00"          magia (6)
  +0x08  u32 versión del mundo
  +0x10  slot name (64 B utf-8, cero-terminado)
  +0x50  seed name (32 B)
"""

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
WORLD_VERSION_INT = 1  # v0.1

# --- Parche de tutorial-skip (v0.2; RE en docs/v02_notes.md §2c/§2e) ---
# El handler del modo "New Game" (FUN_02022544, entry Thumb en 0x02022544)
# empieza con `push {r4,lr}` = 10 B5. Lo sustituimos por un branch Thumb a
# FUN_0202252c (el handler de LOAD: solo setup gráfico + pedir el modo 0x200):
#   B 0x0202252C desde 0x02022544 = 0xE7F2. Así "New Game" entra a la escena
#   por la ruta de LOAD (limpia, sin armar el script de intro), usando el
#   bloque canónico + descriptor que el cliente deja en 0x021602A8 (imagen
#   dorada). "Continue" (Load real) es un caller DISTINTO del mismo handler y
#   queda INTACTO. Validado E2E en la ROM parcheada (exp192-196).
NEWGAME_HANDLER_RAM = 0x02022544
NEWGAME_REDIRECT_THUMB = b"\xF2\xE7"     # B 0x0202252C
NEWGAME_HANDLER_ORIG = b"\x10\xB5"       # push {r4,lr}

# --- Hu-gate (v0.2 EXPERIMENTAL; RE en docs/v02_notes.md §2f) ---
# Hu está hardcoded: la categoría 0 del chequeo de posesión FUN_0203e414
# tiene lista NULL en 0x020DEB78 → devuelve el count (1) → siempre poseída.
# Para hacerla item: apuntar lists[0] a un array de 1 flag [136] (=bit
# 0x021045DD.0, libre) → Hu exige ese flag. counts[0] ya es 1.
HUGATE_LISTS0_RAM = 0x020DEB78            # lists[0] (u32, hoy 0)
HUGATE_ARRAY_RAM = 0x020CB434             # hueco de ceros en arm9 (0x5A0 B)
HUGATE_FLAG_INDEX = 136                   # 0x021045DD bit0 (VERIFICADO libre)
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"

CFG_HU_IN_POOL = 0x01                     # byte 0 del config: bit0 = hu_in_pool


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Descomprime el ARM9 (BLZ), aplica el redirect del tutorial-skip
        (siempre) y el Hu-gate (si hu_in_pool), recomprime y devuelve la ROM.
        ndspy va vendorizado en worlds/mmzx/ndspy/ (MIT)."""
        from . import ndspy  # noqa: F401  (paquete vendorizado)
        from .ndspy import rom as ndsrom

        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        nds = ndsrom.NintendoDSRom(bytes(rom))
        arm9 = nds.loadArm9()

        def find_sec(ram):
            for sec in arm9.sections:
                if sec.ramAddress <= ram < sec.ramAddress + len(sec.data):
                    return sec
            raise ValueError("MMZX: 0x%08X fuera de las secciones ARM9" % ram)

        def poke(ram, data, orig=None):
            sec = find_sec(ram)
            off = ram - sec.ramAddress
            cur = bytes(sec.data[off:off + len(data)])
            if cur == data:
                return  # idempotente
            if orig is not None and cur != orig:
                raise ValueError(
                    "MMZX: bytes inesperados en 0x%08X (%s, esperado %s). "
                    "¿ROM incorrecta?" % (ram, cur.hex(), orig.hex()))
            buf = bytearray(sec.data)
            buf[off:off + len(data)] = data
            sec.data = bytes(buf)

        # 1) tutorial-skip (siempre)
        poke(NEWGAME_HANDLER_RAM, NEWGAME_REDIRECT_THUMB, NEWGAME_HANDLER_ORIG)
        # 2) Hu-gate (opcional)
        if hu_in_pool:
            poke(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
            poke(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"),
                 HUGATE_LISTS0_ORIG)

        nds.arm9 = arm9.save(compress=True)
        return nds.save()


class MMZXPatch(APProcedurePatch, APTokenMixin):
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    # 1) parche del ARM9 (BLZ): skip + Hu-gate opcional; 2) marca AP + slot.
    procedure = [
        ("patch_arm9", ["mmzx_cfg.bin"]),
        ("apply_tokens", ["token_data.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(get_settings().mmzx_settings.rom_file, "rb") as f:
            return f.read()


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str,
                       hu_in_pool: bool = False) -> None:
    blob = bytearray(0x80)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    blob[0x08:0x0C] = WORLD_VERSION_INT.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:63]
    blob[0x10:0x10 + len(name)] = name
    seed = seed_name.encode("utf-8")[:31]
    blob[0x50:0x50 + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
    # config leído por patch_arm9 (antes de apply_tokens): flags de opciones.
    cfg = bytearray(4)
    cfg[0] = CFG_HU_IN_POOL if hu_in_pool else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
