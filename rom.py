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

# --- Parche de tutorial-skip (v0.2; RE en docs/v02_notes.md §2c/§2e/§2h) ---
# El handler de estado FUN_02022544 (entry Thumb 0x02022544) es la ranura 0
# de la tabla de handlers 0x020D8E28 y lo COMPARTEN "New Game" (game_state
# 0x10000) y la demo de attract/intro (game_state 0xB00). Por eso un redirect
# incondicional pisaba también la cinemática de arranque (playtest del
# usuario). Solución: un CODE-CAVE (Thumb) que solo redirige cuando
# game_state (0x0215E6D8) == 0x10000 (New Game real): en ese caso salta al
# handler de LOAD FUN_0202252c (entra a la escena por la ruta de LOAD, limpia,
# usando el bloque de 0x021602A8 que siembra el cliente); en cualquier otro
# caso (attract 0xB00, etc.) replica el prologue original (push{r4,lr};
# mov r4,r0; bl FUN_0202298c) y continúa en 0x0202254C -> intro/attract
# INTACTA. "Continue" (Load real) usa otra ranura y no se toca.
# Entry (8 B) @0x02022544: LDR R3,[PC,#0]; BX R3; .word CAVE|1.
# Bytes ensamblados con keystone (exp206), validados E2E (exp207).
SKIP_ENTRY_RAM = 0x02022544
SKIP_ENTRY = bytes.fromhex("004b184761b40c02")        # -> BX 0x020CB460
SKIP_ENTRY_ORIG = bytes.fromhex("10b5041c00f020fa")   # push;mov r4,r0;bl
SKIP_CAVE_RAM = 0x020CB460                            # hueco de ceros arm9
SKIP_CAVE = bytes.fromhex(
    "06490968064a914205d010b5044657f78dfa044b1847044b1847"
    "00bfd8e61502000001004d2502022d250202")

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

# --- Guarda del dibujador de sprites OAM (exp214-225, 2026-09-02) ---
# FUN_02009b74 (Thumb, 208 B + pool de 24 B) construye las entradas OAM de un
# drawable: hace UN bounds-check antes del bucle y sale del bucle solo con
# `subs r5,#1; beq`. Si el count de sprites del frame es 0 (tabla OAM
# machacada: p.ej. el bloque de 139 KB de un jefe cargado en 0x0224C000
# encima del heap de graficos del nivel mientras hay entidades vivas, al
# aparecer por teleport en la zona del jefe), el bucle da la vuelta y
# escribe sprites por toda la RAM (cursor 0x020F728C) -> soft-lock. Parche
# MINIMO (1 byte): el bucle termina con `subs r5,#1 ; beq exit`
# (0x02009C2E/30); `beq` (D001) -> `bls` (D901): LS = borrow (r5 era 0) OR
# Z (llego a 0), asi que con count==0 sale tras UNA iteracion (acotada por
# el bounds-check previo) en vez de dar la vuelta a 0xFFFFFFFF. Con
# count>=1 el comportamiento es identico. (Una relocalizacion a cueva de
# 240 B tambien funcionaba, exp225, pero rompia el limite del slot BLZ.)
OAMLOOP_BR_RAM = 0x02009C30
OAMLOOP_BR_ORIG = bytes.fromhex("01d0")   # beq +2
OAMLOOP_BR_NEW = bytes.fromhex("01d9")    # bls +2

# --- Posesión de biometales "solo item AP" (H/F/L/P) — exp240, 2026-09-02 ---
# La posesión de un modelo la resuelve FUN_0203e414 sobre tablas de categoría
# (counts @0x020DE9AC, listas @0x020DEB78). Para HX/FX/LX/PX cada lista tiene
# DOS flags: el bit "D0" (0x021045D0.x, que pone la VICTORIA del jefe y que es
# el flag de DETECCIÓN de la location "Obtain Biometal X") y el bit "D1"
# (0x021045D1.x, que concede el ITEM AP). Con count=2 basta CUALQUIERA -> el
# jefe te da el modelo (doble-grant del playtest #2). Parche: dejar la lista
# apuntando SOLO al flag D1 (list[0]=flag D1, count=1) -> la victoria del jefe
# enciende D0.x (dispara el check) pero NO concede posesión; solo el item AP
# (D1.x) la concede. Verificado exp240 (D0-solo -> pos=0; D1 -> pos=1).
# cat -> (count_addr, list0_addr, flag_D1, orig_count, orig_list0_u32)
BIOMETAL_CAT_PATCH = {
    3: (0x020DE9AF, 0x020DE9CC, 41, 33),   # HX
    4: (0x020DE9B0, 0x020DE9BC, 45, 37),   # FX
    5: (0x020DE9B1, 0x020DE9E4, 43, 35),   # LX
    6: (0x020DE9B2, 0x020DE9F4, 47, 39),   # PX
}


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Descomprime el ARM9 (BLZ), aplica el redirect del tutorial-skip
        (siempre) y el Hu-gate (si hu_in_pool), recomprime y recoloca el
        arm9 IN-PLACE en su slot original: el resto de la imagen de 64 MiB
        queda byte-idéntico (solo cambian arm9, su tamaño en cabecera 0x2C y
        el CRC16 0x15E). ⚠️ NO usar el reempaquetado completo de ndspy
        (nds.save()): compacta la ROM a ~44 MB y desplaza el layout, y
        melonDS/BizHawk revienta con std::bad_alloc al cargarla (verificado
        en BizHawk real, exp205). ndspy vendorizado (MIT) solo para el BLZ."""
        import struct

        from . import ndspy  # noqa: F401  (paquete vendorizado)
        from .ndspy import rom as ndsrom

        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        d = bytearray(rom)
        nds = ndsrom.NintendoDSRom(bytes(rom))
        arm9 = nds.loadArm9()

        def poke(ram, data, orig=None):
            for sec in arm9.sections:
                if sec.ramAddress <= ram < sec.ramAddress + len(sec.data):
                    off = ram - sec.ramAddress
                    cur = bytes(sec.data[off:off + len(data)])
                    if cur == data:
                        return  # idempotente
                    if orig is not None and cur != orig:
                        raise ValueError(
                            "MMZX: bytes inesperados en 0x%08X (%s, esperado "
                            "%s). ¿ROM incorrecta?" % (ram, cur.hex(), orig.hex()))
                    buf = bytearray(sec.data)
                    buf[off:off + len(data)] = data
                    sec.data = bytes(buf)
                    return
            raise ValueError("MMZX: 0x%08X fuera de las secciones ARM9" % ram)

        # 1) tutorial-skip (siempre): entry (con guarda de bytes originales)
        #    + code-cave condicional por game_state
        poke(SKIP_ENTRY_RAM, SKIP_ENTRY, SKIP_ENTRY_ORIG)
        poke(SKIP_CAVE_RAM, SKIP_CAVE)
        # 1b) guarda del dibujador OAM (siempre; robustez anti soft-lock):
        #     `beq` -> `bls` al final del bucle de sprites de FUN_02009b74
        poke(OAMLOOP_BR_RAM, OAMLOOP_BR_NEW, OAMLOOP_BR_ORIG)
        # 1c) posesión de biometales "solo item AP" (siempre): la victoria del
        #     jefe deja de conceder el modelo; solo el item AP (D1.x) lo hace
        for cnt_a, lst_a, flag_d1, orig_flag in BIOMETAL_CAT_PATCH.values():
            poke(lst_a, flag_d1.to_bytes(4, "little"),
                 orig_flag.to_bytes(4, "little"))
            poke(cnt_a, b"\x01", b"\x02")
        # 2) Hu-gate (opcional)
        if hu_in_pool:
            poke(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
            poke(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"),
                 HUGATE_LISTS0_ORIG)

        # recomprimir y recolocar in-place en el slot original del arm9
        blob = arm9.save(compress=True)
        post = bytes(nds.arm9PostData)         # footer nitrocode (12 B)
        arm9_off = struct.unpack_from("<I", d, 0x20)[0]
        others = [struct.unpack_from("<I", d, o)[0]
                  for o in (0x30, 0x40, 0x48, 0x50, 0x68)]
        slot_end = min(x for x in others if x > arm9_off)
        if len(blob) + len(post) > slot_end - arm9_off:
            raise ValueError(
                "MMZX: el arm9 recomprimido (0x%X+%d) no cabe en su slot "
                "(0x%X)" % (len(blob), len(post), slot_end - arm9_off))
        d[arm9_off:arm9_off + len(blob)] = blob
        end = arm9_off + len(blob)
        d[end:end + len(post)] = post
        d[end + len(post):slot_end] = b"\x00" * (slot_end - end - len(post))
        struct.pack_into("<I", d, 0x2C, len(blob))

        # CRC16 de cabecera (CRC-16/MODBUS sobre [0:0x15E])
        crc = 0xFFFF
        for b in bytes(d[:0x15E]):
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        struct.pack_into("<H", d, 0x15E, crc)
        return bytes(d)


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
