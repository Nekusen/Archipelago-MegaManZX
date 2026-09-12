"""Client-side skip of the D-4 boss rush: which Pseudoroid pairs to mark as beaten, and when.

Pure functions with no Archipelago imports. Marking a pair before the elevator has stopped at
its stop makes the elevator jump and drops the player, hence the position checks. The RAM
contract is shared with the client package.
"""

SUBAREA = 18                     # D-4 (tower)
HANDLER_ID = 16                  # mission "Destroy Model W"
PAIR_COUNT = 4                   # Pseudoroid pairs k = 0..3
FLAG_LEFT = 0x021045FF           # bit 4+k = pair k, left teleporter
FLAG_RIGHT = 0x02104600          # bit k   = pair k, right teleporter
LEFT_PAIR_BIT = 4                # pair 0 is bit 4 of FLAG_LEFT and bit 0 of FLAG_RIGHT
STAGE = 0x0212FBA1               # elevator stage (u8)

TILEMAP = 0x02112B78             # metatile map of the loaded room
TILEMAP_STRIDE = 192             # D-4: 12 screens x 16 metatiles
TILEMAP_DIRTY = 0x0212DB54 + 0x28   # 1 = re-upload the visible map
TILE_BYTES = 2                   # one u16 per metatile
# [pair] = (left, right) capsules as (tx, ty, patch address in overlay 61).
PATCHES = {
    0: ((0x10, 0x0E, 0x02195A58), (0x1B, 0x0E, 0x02195B98)),
    1: ((0x30, 0x0E, 0x02195B18), (0x3B, 0x0E, 0x02195B58)),
    2: ((0x10, 0x26, 0x02195A18), (0x1B, 0x26, 0x021959D8)),
    3: ((0x30, 0x26, 0x02195AD8), (0x3B, 0x26, 0x02195A98)),
}
PATCH_W, PATCH_H = 5, 6
PATCH_HEADER = 4                 # u16 width and s16 height, then the rows

SHAFT1 = (1536, 1792)            # elevator shaft 1 (x)
SHAFT2 = (2560, 2816)            # elevator shaft 2 (x)
# [pair] = (shaft, max player y when standing at the stop, handler state, elevator stage).
STOPS = {
    0: (SHAFT1, 2464, 2, 2),
    1: (SHAFT1, 544, 4, 4),
    2: (SHAFT2, 2848, 5, 7),
    3: (SHAFT2, 928, 7, 9),
}
# [pair] = (x0, x1, y0, y1) of the pair's teleporter room.
ROOMS = {
    0: (248, 760, 200, 420),
    1: (760, 1040, 200, 420),
    2: (248, 760, 600, 800),
    3: (760, 1040, 600, 800),
}
PAIR_NAMES = {0: "Hivolt/Hurricaune", 1: "Lurerre/Leganchor",
              2: "Fistleo/Flammole", 3: "Purprill/Protectos"}


def pair_set(flag_left: int, flag_right: int, k: int) -> bool:
    """Whether both teleporters of pair k are flagged as beaten."""
    return bool((flag_left >> (LEFT_PAIR_BIT + k)) & 1 and (flag_right >> k) & 1)


def pairs_to_set(x: int, y: int, hstate: int, stage: int,
                 flag_left: int, flag_right: int) -> list:
    """Pairs to mark as beaten now, sorted.

    The caller checks that the player is in D-4 with the mission 16 handler and no cutscene.
    """
    out = []
    for k in range(PAIR_COUNT):
        if pair_set(flag_left, flag_right, k):
            continue
        x0, x1, y0, y1 = ROOMS[k]
        if x0 <= x < x1 and y0 <= y < y1:
            out.append(k)
            continue
        (sx0, sx1), ymax, state, stg = STOPS[k]
        if sx0 <= x < sx1 and y <= ymax and hstate == state and stage == stg:
            out.append(k)
    return out


def apply_pairs(flag_left: int, flag_right: int, pairs) -> tuple:
    """The two flag bytes with the given pairs set."""
    for k in pairs:
        flag_left |= 1 << (LEFT_PAIR_BIT + k)
        flag_right |= 1 << k
    return flag_left & 0xFF, flag_right & 0xFF


def paint_writes(k: int, patch_bytes) -> list:
    """[(address, bytes)] that paint both capsules of pair k as used and mark the map dirty.

    patch_bytes(addr) returns the 64-byte patch at addr; it is only in RAM while D-4 is loaded.
    """
    out = []
    for tx, ty, src in PATCHES[k]:
        data = patch_bytes(src)
        w = int.from_bytes(data[0:2], "little")
        h = int.from_bytes(data[2:4], "little", signed=True)
        if w != PATCH_W or h != PATCH_H:      # foreign overlay loaded: do not touch
            return []
        for row in range(h):
            out.append((TILEMAP + (tx + (ty + row) * TILEMAP_STRIDE) * TILE_BYTES,
                        data[PATCH_HEADER + row * w * TILE_BYTES: PATCH_HEADER + (row + 1) * w * TILE_BYTES]))
    out.append((TILEMAP_DIRTY, (1).to_bytes(2, "little")))
    return out
