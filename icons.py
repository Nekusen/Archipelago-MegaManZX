"""The "AP" sprite set: item icons cut from the player's ROM at patch time.

rom.py inserts the set as set 261 and its icon caves draw it on pickups. Only
the three Archipelago logos in gfx/ ship with the world (MIT, from the Metroid:
Zero Mission apworld); every other icon is a frame of the game's own sets
(ICONS), quantised to the palette of set 58, which the AP set shares in VRAM.

Sprite set formats:
  obj_fnt.bin / obj_dat.bin: u32 count, u32 offset[count + 1]; set i is the
    slice [offset[i], offset[i + 1]).
  fnt set, static: a 0x14-byte header (u32 tile offset = 0x14, u16 tile
    length, u16 0x18, u16 tile length / 4, u16 flags 0x8020 = 4bpp or 0x8040 =
    8bpp, u32 tile length + 8, u16 palette length, u16) + tiles + palette
    (BGR555). Tiles are 8x8, 1D mapped, low nibble = left pixel.
  fnt set, chained (dynamic): N such headers back to back, one per chunk,
    each relative to itself: chunk k's tiles are at k*0x14 + its u32, its
    palette at k*0x14 + (the u32 at +0xC) + 12.
  dat set: u32 8, u32 table length, u32 4, then the frame table at +0xC
    (per frame: u16 offset from the table start, u8 entry count, u8 chunk),
    entries = u16 attr | s8 dx | s8 dy with attr = tile:10 hflip:1 vflip:1
    size:2 shape:2 (one tile index = 128 bytes), then the animation scripts
    at 4 + table length (u16 offset[n]; pairs (frame, ticks), 0xFE loop, 0xFF
    end). The game draws a frame's entries from the last to the first.
"""
import struct

PALETTE_SET = 58                 # the AP set shares this set's palette in VRAM

# The recipe, in animation order of the AP set (animation i = frame i = icon i;
# ICON_CODES in data.py is this order, 1-based): ("logo", gfx file) for an
# Archipelago logo, ("frame", set, frame) for a frame of the player's ROM.
ICONS = [
    ("logo_useful", ("logo", "ap_logo_useful.gfx")),
    ("logo_progression", ("logo", "ap_logo_progression.gfx")),
    ("logo_filler", ("logo", "ap_logo.gfx")),
    ("lifeup", ("frame", 507, 0)),           # Life Up (world pickup, animation 0)
    ("subtank", ("frame", 507, 4)),          # Sub Tank (world pickup, animation 1)
    ("chip_Absorber", ("frame", 178, 0)),    # ITEM B chips (pause menu), flag order
    ("chip_Eraser", ("frame", 178, 2)),
    ("chip_Featherweight", ("frame", 178, 4)),
    ("chip_Extender", ("frame", 178, 6)),
    ("chip_QuickCharger", ("frame", 178, 8)),
    ("chip_IceBoots", ("frame", 178, 10)),
    ("chip_WindBoots", ("frame", 178, 12)),
    ("chip_Frog", ("frame", 178, 14)),
    ("model_Hu", ("frame", 73, 0)),          # biometal badges (STATUS screen)
    ("model_X", ("frame", 73, 3)),
    ("model_ZX", ("frame", 73, 6)),
    ("model_HX", ("frame", 74, 0)),
    ("model_FX", ("frame", 74, 3)),
    ("model_LX", ("frame", 75, 0)),
    ("model_PX", ("frame", 75, 3)),
    ("model_OX", ("frame", 75, 6)),
    ("card_Red", ("frame", 180, 21)),        # Card Keys (ITEM C, quest item set)
    ("card_Blue", ("frame", 180, 25)),
    ("card_Purple", ("frame", 180, 22)),
    ("card_Green", ("frame", 180, 24)),
    ("card_Yellow", ("frame", 180, 23)),
    ("card_White", ("frame", 180, 74)),
]
ICON_NAMES = [name for name, _ in ICONS]

# Sets drawn by the game with the palette of set 58 instead of their own
# (their own palette is the same one up to two greens).
PALETTE_OVERRIDE = {507: PALETTE_SET}

# OBJ shapes the packer may use, smallest first: ((shape, size), (w, h)).
SHAPES = [((0, 1), (16, 16)), ((1, 2), (32, 16)), ((2, 2), (16, 32)), ((0, 2), (32, 32))]
DIMS = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}

# Colours behind the palette indices of the Archipelago logos; the .gfx files
# are indexed, and the colours get quantised to the set 58 palette anyway.
LOGO_COLOURS = [
    (248, 248, 248), (192, 192, 200), (120, 120, 136), (40, 40, 64),
    (232, 48, 48), (144, 24, 64), (240, 136, 32), (248, 216, 48),
    (56, 184, 72), (24, 104, 56), (56, 88, 224), (128, 176, 248),
    (64, 208, 208), (144, 64, 200), (240, 128, 176),
]
# MZM logo index to LOGO_COLOURS index (1-based; 0 = transparent): white
# outline, then the six "islands" of the logo.
LOGO_MAP = {0: 0, 1: 1, 2: 15, 3: 6, 4: 7, 5: 8, 6: 8, 7: 10, 8: 9, 9: 9,
            10: 11, 11: 11, 12: 12, 13: 14, 14: 14, 15: 14}
# The filler logo is all light grey (the medium grey lands on a violet of the
# shared palette and one island came out coloured).
LOGO_MAP_GREY = {k: (0 if k == 0 else 1 if k == 1 else 2) for k in range(16)}


def _bgr555(raw):
    return [((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8)
            for c in struct.unpack("<%dH" % (len(raw) // 2), raw)]


def _set_slices(container):
    """Offsets of every set of an obj_fnt.bin / obj_dat.bin container."""
    n = struct.unpack_from("<I", container, 0)[0]
    return [struct.unpack_from("<I", container, 4 + i * 4)[0] for i in range(n + 1)]


def _set_block(container, setno):
    offs = _set_slices(container)
    return container[offs[setno]:offs[setno + 1]]


def _chunk(fnt_block, k):
    """(tiles, palette as RGB, bits per pixel) of chunk k of a set; k = 0 for a static set."""
    tile_off, tile_len, _, _, flags, pal_ptr, pal_len, _ = \
        struct.unpack_from("<IHHHHIHH", fnt_block, k * 0x14)
    base = k * 0x14
    if tile_off == 0x14 and k == 0:          # static: palette at the very end
        tiles = fnt_block[0x14:0x14 + tile_len]
        pal = fnt_block[len(fnt_block) - pal_len:] if pal_len else b""
    else:
        tiles = fnt_block[base + tile_off:base + tile_off + tile_len]
        pal = fnt_block[base + pal_ptr + 12:base + pal_ptr + 12 + pal_len]
    return tiles, _bgr555(pal), (8 if flags & 0x40 else 4)


def _frame(dat_block, frame):
    """(chunk, [(attr, dx, dy), ...]) of a frame of a set's dat block."""
    off, count, chunk = struct.unpack_from("<HBB", dat_block, 0xC + frame * 4)
    ents = [struct.unpack_from("<Hbb", dat_block, 0xC + off + e * 4) for e in range(count)]
    return chunk, ents


def _draw_entry(canvas, tiles, bpp, pal, attr, dx, dy, ox, oy):
    tile = attr & 0x3FF
    hflip, vflip = (attr >> 10) & 1, (attr >> 11) & 1
    w, h = DIMS[((attr >> 14) & 3, (attr >> 12) & 3)]
    tw = w // 8
    tsz = 32 if bpp == 4 else 64
    px = [[0] * w for _ in range(h)]
    for t in range((w // 8) * (h // 8)):
        tx, ty = (t % tw) * 8, (t // tw) * 8
        base = tile * 128 + t * tsz
        for y in range(8):
            for x in range(8):
                if bpp == 4:
                    i = base + y * 4 + x // 2
                    if i >= len(tiles):
                        continue
                    v = (tiles[i] & 15) if x % 2 == 0 else (tiles[i] >> 4)
                else:
                    i = base + y * 8 + x
                    if i >= len(tiles):
                        continue
                    v = tiles[i]
                px[ty + y][tx + x] = v
    for y in range(h):
        for x in range(w):
            v = px[h - 1 - y if vflip else y][w - 1 - x if hflip else x]
            if v:
                X, Y = ox + dx + x, oy + dy + y
                if 0 <= X < len(canvas[0]) and 0 <= Y < len(canvas):
                    canvas[Y][X] = pal[v % len(pal)]


def render_frame(fnt_file, dat_file, setno, frame, palette=None, size=96):
    """A frame of a set as the game composes it, cropped to its drawn pixels.

    Returns (width, height, rows) with rows[y][x] = (r, g, b) or None.
    """
    fnt_block = _set_block(fnt_file, setno)
    dat_block = _set_block(dat_file, setno)
    chunk, ents = _frame(dat_block, frame)
    tiles, pal, bpp = _chunk(fnt_block, chunk)
    if palette is not None:
        pal = palette
    canvas = [[None] * size for _ in range(size)]
    o = size // 2
    for attr, dx, dy in reversed(ents):
        _draw_entry(canvas, tiles, bpp, pal, attr, dx, dy, o, o)
    return _crop(canvas)


def _crop(canvas):
    ys = [y for y, row in enumerate(canvas) if any(p is not None for p in row)]
    xs = [x for x in range(len(canvas[0])) if any(row[x] is not None for row in canvas)]
    if not ys:
        return 0, 0, []
    y0, y1, x0, x1 = min(ys), max(ys) + 1, min(xs), max(xs) + 1
    return x1 - x0, y1 - y0, [row[x0:x1] for row in canvas[y0:y1]]


def render_logo(gfx, grey=False):
    """Frame 0 of an Archipelago logo .gfx (16x16, 4bpp) as RGB rows."""
    m = LOGO_MAP_GREY if grey else LOGO_MAP
    rows = [[None] * 16 for _ in range(16)]
    for t in range(4):
        tx, ty = (t % 2) * 8, (t // 2) * 8
        for y in range(8):
            for x in range(4):
                b = gfx[t * 32 + y * 4 + x]
                for k, v in ((0, b & 15), (1, b >> 4)):
                    idx = m[v]
                    if idx:
                        rows[ty + y][tx + x * 2 + k] = LOGO_COLOURS[idx - 1]
    return 16, 16, rows


def set_palette(fnt_file, setno=PALETTE_SET):
    """The 15 colours (indices 1..15) of a static set's palette."""
    tiles, pal, bpp = _chunk(_set_block(fnt_file, setno), 0)
    return pal[1:16]


def _quantiser(colours):
    def nearest(c):
        return 1 + min(range(len(colours)),
                       key=lambda k: 2 * (c[0] - colours[k][0]) ** 2
                       + 4 * (c[1] - colours[k][1]) ** 2
                       + 3 * (c[2] - colours[k][2]) ** 2)
    return nearest


def _pick_shape(w, h):
    for (shape, size), (W, H) in SHAPES:
        if w <= W and h <= H:
            return shape, size, W, H
    raise ValueError("MMZX: icon too large (%dx%d)" % (w, h))


def build_icon_set(fnt_file, dat_file, logo_data):
    """Build the AP set from the player's obj_fnt.bin / obj_dat.bin.

    `logo_data(file)` returns the bytes of a logo .gfx from gfx/. Returns
    (fnt block, dat block) ready for rom.py to insert as a new set.
    """
    colours = set_palette(fnt_file)
    nearest = _quantiser(colours)
    tiles = bytearray()
    frames = []
    unit = 0
    for name, src in ICONS:
        if src[0] == "logo":
            w, h, rows = render_logo(logo_data(src[1])[:128], grey=(name == "logo_filler"))
        else:
            _, setno, frame = src
            override = PALETTE_OVERRIDE.get(setno)
            pal = [(0, 0, 0)] + set_palette(fnt_file, override) if override else None
            w, h, rows = render_frame(fnt_file, dat_file, setno, frame, pal)
        shape, size, W, H = _pick_shape(w, h)
        ox, oy = (W - w) // 2, (H - h) // 2
        canvas = [[0] * W for _ in range(H)]
        for y in range(h):
            for x in range(w):
                if rows[y][x] is not None:
                    canvas[oy + y][ox + x] = nearest(rows[y][x])
        tw, th = W // 8, H // 8
        blob = bytearray()
        for t in range(tw * th):
            tx, ty = (t % tw) * 8, (t // tw) * 8
            for y in range(8):
                for x in range(0, 8, 2):
                    blob.append(canvas[ty + y][tx + x] | (canvas[ty + y][tx + x + 1] << 4))
        units = (len(blob) + 127) // 128
        blob += bytes(units * 128 - len(blob))
        # anchored like the Secret Disk: 16x16 at (-8, -13), visual centre (0, -5)
        frames.append((unit | (size << 12) | (shape << 14), -W // 2, -5 - H // 2))
        tiles += blob
        unit += units
    # fnt block: static, 4bpp, one 16-colour palette (index 0 = transparent)
    tile_len = len(tiles)
    header = struct.pack("<IHHHHIHH", 0x14, tile_len, 0x18, tile_len // 4, 0x8020,
                         0x14 + tile_len - 0xC, 0x20, 8)
    palette = b"".join(struct.pack("<H", (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
                       for r, g, b in [(0, 0, 0)] + list(colours))
    fnt_block = header + bytes(tiles) + palette
    # dat block: one single-entry frame per icon, one one-frame animation each
    n = len(frames)
    table = b"".join(struct.pack("<HBB", 4 * n + 4 * i, 1, 0) for i in range(n))
    table += b"".join(struct.pack("<Hbb", attr, dx, dy) for attr, dx, dy in frames)
    scripts = b"".join(struct.pack("<H", 2 * n + 4 * i) for i in range(n))
    scripts += b"".join(struct.pack("<BBBB", i, 1, 0, 0xFF) for i in range(n))
    dat_block = struct.pack("<III", 8, 8 + len(table), 4) + table + scripts
    return fnt_block, dat_block
