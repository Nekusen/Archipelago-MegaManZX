"""The eight Mega Man Zero 3/4 bosses of N-1: their sprites, converted from the player's GBA
ROMs into the patched ROM, their capsules open, and their flags kept once won."""

import hashlib
import struct

from . import nds
from .arm9 import Arm9

ZERO3, ZERO4 = 3, 4
GAME_CODE_OFF = 0xAC
GAME_CODES = {ZERO3: (b"BZ3E", b"BZ3P", b"BZ3J"), ZERO4: (b"B4ZE", b"B4ZP", b"B4ZJ")}
ROM_SIZES = {ZERO3: 8 << 20, ZERO4: 16 << 20}
# Every release of each game: the sets the patch reads are the same bytes in all of them.
ROM_MD5S = {
    ZERO3: ["aa1d5eeffcd5e4577db9ee6d9b1100f9", "9ce73ff9aa1473f250d103c1bdbbd738",
            "aa9aeea52de34b25351e76d70bfbe2b8"],
    ZERO4: ["0d1e88bdb09ff68adf9877a121325f9c", "d3a76f1c92e3044b1a21f1aae84d21ab",
            "d4e3855b1e6630921de0e188ac974ebf"],
}
GBA_BASE = 0x08000000
# The sets the boss code asks for, by game: set number -> which of the two tables holds it.
SETS = {
    ZERO3: {0x24: 1, 0x25: 1, 0x26: 1, 0x36: 1, 0x37: 1, 0xA2: 0, 0xA3: 0, 0xA4: 0, 0xA7: 0, 0xA8: 0, 0xA9: 0, 0xAA: 0},
    ZERO4: {0x3A: 1, 0x3B: 1, 0x3C: 1, 0x3D: 1, 0x3E: 1, 0x3F: 1, 0x45: 1, 0x46: 1, 0x47: 1, 0x48: 1, 0x49: 1,
            0x6A: 1, 0x7D: 1, 0x85: 1, 0xA0: 0, 0xA1: 0, 0xA3: 0, 0xA4: 0, 0xAA: 0, 0xAB: 0},
}
# Where each game keeps its sprite tables, indexed by table then game, as the ARM9 of ZX has them.
FRAME_TABLES = {ZERO3: (0x083A0AE0, 0x085C0874), ZERO4: (0x088A7000, 0x08C1C000)}
GFX_TABLES = {ZERO3: (0x083B8C8C, 0x085D78F8), ZERO4: (0x088CC000, 0x08C44000)}
ANIM_TABLES = {ZERO3: (0x083B54FC, 0x085D2D48), ZERO4: (0x088C7000, 0x08C3C000)}
# Tiles of an OAM piece by its shape and size bits.
TILES_PER_PIECE = bytes.fromhex("010410400204082002040820e00a3a08")
PIECE_TILE_MASK = 0x3FF            # a piece's attribute word: the first tile, then flips, size and shape
PIECE_FLAGS_MASK = 0xFC00
PIECE_SIZE_MASK = 0x3FFF
GROUP_LEN = 0x14
GROUP_FLAGS = 0x180000             # a converted group's flag word: two bits set over the size of its tiles
GROUP_SIZE_MASK = 0x7FFFF
GROUP_OAM_FLAGS = 0x8020           # the halfword the engine keeps after the tile count
TILE_LEN = 0x20
TILE_UNIT = 4                      # the engine counts tiles in groups of four (128 bytes)
HALF = 0xFFFF

# The engine's loader of a Game Pak set, replaced by one that reads the converted set from the
# container file: the code, then the table of slices it searches (src/asm/zero.s).
ZERO_LOADER_RAM = 0x02010A28
ZERO_LOADER = bytes.fromhex(
    "70b596b01c1c4002090208431206120e1043154d154e2988814205d0b14201d0"
    "1435f8e7002614e068461149884768461049114a90476846696800220f4b9847"
    "6846211caa680e4b984768460d498847ae681a980460e96809194160296909198160"
    "301c16b070bdc00a0102ffff000090f00a02b00a010240ed0a029ceb0a0208ec"
    "0a02f8ec0a022f6d5f6c69765f6a702e62696e000000")
ZERO_TABLE_RAM = ZERO_LOADER_RAM + len(ZERO_LOADER)
ZERO_ENTRY = "<HHIIII"               # key, 0, offset, size, frames offset, graphics offset
ZERO_TABLE_END = 0xFFFF
ZERO_REGION_LEN = 0x528             # the loader and the converters it replaces
ZERO_REGION_SHA256 = "6350c7514cc279e4dd9381e8125690ce43969b92b137c0ce9a4a98665ab09e62"
# The container: an unused file of the ROM, opened by the loader by name.
CONTAINER_FILE_ID = 217
# The two routines that stand for "the Game Pak is inserted": true for a game whose sets are in.
INSERTED_RAM = {ZERO3: 0x020109E8, ZERO4: 0x020109B0}
INSERTED_ORIG = bytes.fromhex("00b581b0")
INSERTED_NEW = bytes.fromhex("01207047")
# N-1's overlay: the room script marks a boss as beaten only until the Mysterious Rock is
# taken, and the rock clears the eight marks; both so the bosses can be fought again.
# The marks stay: a beaten boss is a check, and its capsule is gone for good.
ZERO_OVERLAY = 107
ZERO_FLAGS_KEEP = [(addr, "%02xd1" % skip, "c046") for addr, skip in (
    (0x02195210, 3), (0x0219522E, 2), (0x0219524C, 2), (0x0219526A, 1),
    (0x02195320, 3), (0x0219533E, 3), (0x0219535E, 2), (0x02195384, 2))]
ROCK_KEEPS_FLAGS = [(0x02196112, "837d", "1ce0")]


class Gba:
    """A GBA ROM read at bus addresses."""

    def __init__(self, data: bytes):
        self.d = data

    def u32(self, addr: int) -> int:
        return struct.unpack_from("<I", self.d, addr - GBA_BASE)[0]

    def u16(self, addr: int) -> int:
        return struct.unpack_from("<H", self.d, addr - GBA_BASE)[0]

    def u8(self, addr: int) -> int:
        return self.d[addr - GBA_BASE]

    def slice(self, addr: int, n: int) -> bytes:
        return self.d[addr - GBA_BASE:addr - GBA_BASE + n]

    def lz(self, addr: int) -> bytes:
        from ..apnds import lz
        size = self.u32(addr) >> 8
        return lz.decompress(self.slice(addr, min(size * 2 + 16, len(self.d) - (addr - GBA_BASE))))


def check_rom(data: bytes, game: int) -> None:
    """Refuse anything but a release of the game, by size and game code."""
    code = data[GAME_CODE_OFF:GAME_CODE_OFF + 4]
    if len(data) != ROM_SIZES[game] or code not in GAME_CODES[game]:
        raise ValueError("MMZX: not a Mega Man Zero %d ROM (game code %r, %d bytes)." % (game, code, len(data)))


def convert_anims(rom: Gba, table: int, n: int) -> bytes:
    """The animations of a set: a table of 16-bit offsets, then the (frame, duration) lists."""
    base = rom.u32(ANIM_TABLES[rom.game][table] + n * 4)
    count = (rom.u32(base) - base) >> 2
    out = bytearray()
    for i in range(count):
        out += struct.pack("<H", (rom.u32(base + 4 * i) - base - 2 * count) & HALF)
    pos, ends = base + 4 * count, 0
    while count and ends < count:
        word = rom.u16(pos)
        out += struct.pack("<H", word)
        ends += word >> 15
        pos += 2
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def convert_frames(rom: Gba, table: int, n: int) -> tuple[bytes, int]:
    """(the frames, the group descriptors and their tiles and palettes; offset of the descriptors).

    Only the tiles the pieces use are copied, in groups of four, and the pieces are renumbered.
    """
    ftab = rom.u32(FRAME_TABLES[rom.game][table] + n * 4)
    nframes = rom.u16(ftab) >> 2
    frames = [struct.unpack_from("<HBB", rom.d, ftab + 4 * i - GBA_BASE) for i in range(nframes)]
    frames_len = 4 * nframes + 4 * sum(f[1] for f in frames)
    if table == 0:
        entry = GFX_TABLES[rom.game][table] + n * 4
        gtab = entry + rom.u32(entry)
        ngroups = rom.u32(gtab) // GROUP_LEN
    else:
        gtab, ngroups = GFX_TABLES[rom.game][table] + n * GROUP_LEN, 1
    fblock = bytearray(rom.slice(ftab, frames_len))
    descs = bytearray(ngroups * GROUP_LEN)
    data = bytearray()
    used: list[list[int]] = []       # [first tile, tiles, new index] in the order the pieces name them

    def register(tile: int, tiles: int) -> None:
        for e in used:
            if e[0] == tile:
                e[1] = max(e[1], tiles)
                return
        used.append([tile, tiles, 0])

    def convert_group(g: int, first: int, end: int) -> None:
        gdesc = gtab + g * GROUP_LEN
        compressed = (rom.u16(gdesc + 10) & 3) >> 1
        tiles = rom.lz(gdesc + rom.u32(gdesc)) if compressed else rom.slice(gdesc + rom.u32(gdesc), len(rom.d))
        start = frames_len + len(descs) + len(data)
        cur = 0
        for e in used:
            tile, count = e[0], e[1]
            data.extend(tiles[tile * TILE_LEN:(tile + count) * TILE_LEN])
            rounded = (count + TILE_UNIT - 1) // TILE_UNIT * TILE_UNIT
            data.extend(bytes((rounded - count) * TILE_LEN))
            e[2] = (cur // TILE_UNIT) & PIECE_TILE_MASK
            cur += rounded
        tiles_len = frames_len + len(descs) + len(data) - start
        for i in range(first, end):
            off, pieces, _group = frames[i]
            for k in range(pieces):
                p = off + 4 * k
                attr = struct.unpack_from("<H", fblock, p)[0]
                for e in used:
                    if (attr & PIECE_TILE_MASK) == e[0]:
                        struct.pack_into("<H", fblock, p, (attr & PIECE_FLAGS_MASK) | e[2])
                        break
        odesc = g * GROUP_LEN
        palsize = rom.u16(gdesc + 0x10)
        pal_at = gdesc + rom.u32(gdesc + 12) + 0xC
        palette = (rom.lz(pal_at) if rom.u8(gdesc + 0x12) else rom.slice(pal_at, palsize))[:palsize]
        pal_pos = frames_len + len(descs) + len(data)
        struct.pack_into("<IIHHIHBB", descs, odesc, start - (frames_len + odesc), GROUP_FLAGS | (tiles_len & GROUP_SIZE_MASK),
                         (tiles_len >> 2) & HALF, GROUP_OAM_FLAGS, pal_pos - (frames_len + odesc + 12), palsize, 8, 0)
        data.extend(palette)

    group, first = 0, 0
    for i, (off, pieces, frame_group) in enumerate(frames):
        if table == 0 and frame_group != group:
            convert_group(group, first, i)
            used.clear()
            group, first = frame_group, i
        for k in range(pieces):
            attr = struct.unpack_from("<H", fblock, off + 4 * k)[0]
            register(attr & PIECE_TILE_MASK, TILES_PER_PIECE[((attr >> 14) << 2) | ((attr & PIECE_SIZE_MASK) >> 12)])
    convert_group(group, first, nframes)
    return bytes(fblock) + bytes(descs) + bytes(data), frames_len


def convert_set(rom: Gba, table: int, n: int) -> tuple[bytes, int, int]:
    """(the set as the engine keeps it in memory, offset of the frames, offset of the graphics)."""
    anims = convert_anims(rom, table, n)
    frames, gfx = convert_frames(rom, table, n)
    return anims + frames, len(anims), len(anims) + gfx


def build_container(roms: dict[int, bytes]) -> tuple[bytes, list[tuple]]:
    """(the file of every set of the games given, the table entries that find them)."""
    blob, entries = bytearray(), []
    for game in sorted(roms):
        check_rom(roms[game], game)
        rom = Gba(roms[game])
        rom.game = game
        for n, table in sorted(SETS[game].items()):
            data, frames, gfx = convert_set(rom, table, n)
            key = ((game - ZERO3) << 9) | (table << 8) | n
            entries.append((key, 0, len(blob), len(data), frames, gfx))
            blob += data
            while len(blob) % 4:
                blob.append(0)
    return bytes(blob), entries


def patch_loader(arm9: Arm9, entries: list[tuple]) -> None:
    """The loader and its table over the engine's converter."""
    region = arm9.read(ZERO_LOADER_RAM, ZERO_REGION_LEN)
    if hashlib.sha256(region).hexdigest() != ZERO_REGION_SHA256:
        raise ValueError("MMZX: unexpected code at 0x%08X. Wrong ROM?" % ZERO_LOADER_RAM)
    table = b"".join(struct.pack(ZERO_ENTRY, *e) for e in entries) + struct.pack(ZERO_ENTRY, ZERO_TABLE_END, 0, 0, 0, 0, 0)
    blob = ZERO_LOADER + table
    if len(blob) > ZERO_REGION_LEN:
        raise ValueError("MMZX: the Zero set table does not fit")
    arm9.write(ZERO_LOADER_RAM, blob + bytes(ZERO_REGION_LEN - len(blob)), region)


def patch_capsules(arm9: Arm9, games: set[int]) -> None:
    """The Game Pak of each game whose sets are in counts as inserted: its doors and capsules open."""
    for game in sorted(games):
        arm9.write(INSERTED_RAM[game], INSERTED_NEW, INSERTED_ORIG)


def patch_rooms(rom: bytearray) -> None:
    """A beaten boss stays beaten, Mysterious Rock or not."""
    nds.patch_overlay(rom, ZERO_OVERLAY, ZERO_FLAGS_KEEP + ROCK_KEEPS_FLAGS)


def install_container(rom: bytearray, blob: bytes) -> None:
    nds.relocate_file(rom, CONTAINER_FILE_ID, blob)
