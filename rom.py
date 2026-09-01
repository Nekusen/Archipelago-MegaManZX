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
from worlds.Files import APProcedurePatch, APTokenMixin, APTokenTypes

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
WORLD_VERSION_INT = 1  # v0.1


class MMZXPatch(APProcedurePatch, APTokenMixin):
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    procedure = [("apply_tokens", ["token_data.bin"])]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(get_settings().mmzx_settings.rom_file, "rb") as f:
            return f.read()


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str) -> None:
    blob = bytearray(0x80)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    blob[0x08:0x0C] = WORLD_VERSION_INT.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:63]
    blob[0x10:0x10 + len(name)] = name
    seed = seed_name.encode("utf-8")[:31]
    blob[0x50:0x50 + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
