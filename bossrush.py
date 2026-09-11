"""Skip of the BOSS RUSH in the Slither Inc. tower (D-4) - QoL option
`skip_boss_rush`. PURE logic (no Archipelago dependencies) shared by the
client (client.py::_boss_rush_skip_tick) and by the experiments that validate
it in the emulator (work/experiments/618-619).

How the game works (RE 2026-09-09, exp614-618; docs/functions.md, section D-4):

- "Pseudoroid X defeated in the boss rush" = 8 flags of the save block:
  0x021045FF.4-7 (LEFT teleporter of each pair: Hivolt, Lurerre,
  Fistleo, Purprill) and 0x02104600.0-3 (RIGHT: Hurricaune, Leganchor,
  Flammole, Protectos). With the flag set the teleporter becomes INERT
  (UP does nothing), ovl061 draws its capsule as used WHEN LOADING the room
  (0x02194A84 -> FUN_02013328) and unlocks the doors of the pair's room
  (0x02194C84 sets/clears 0x0210462A.7 every frame according to BOTH flags).
- The elevator is ONE single entity (0x02194DEC) placed according to the
  u8 "stage" 0x0212FBA1: 0 bottom of shaft 1, 1 stop 1 (y=2440), 2 rising
  to 2440, 3 top (520), 4 rising to 520, 5 bottom of shaft 2 (2688,4360),
  6 stop 1 (2824), 7 rising to 2824, 8 top (904), 9 rising to 904. The
  fixed stages JUMP straight to their position. The stage is driven by the
  story handler of mission 16 (FUN_0201fc90) from state + flags + rectangles:
  with a pair set AHEAD of time, the elevator jumps to the stop and the
  player falls into the pit (exp614: with all 8 flags at once, stage 8 =
  elevator parked at the top of shaft 2 and the player dies in shaft 1).
- That is why pair k is set ONLY when the elevator is already stopped at
  the pair's stop with the player on it (or the player inside the pair's
  room). On setting it, the handler chains just the next cutscene and the
  elevator keeps rising (exp615/618).
- Checkpoint: the fade doors update the respawn position
  (0x0216047C) but NOT the handler's copy (0x02160554): a death respawned
  with the handler out of sync and the elevator dead (exp617). On setting a
  pair the full COMMIT is done like FUN_0201b384 (position -> persistent
  player block -> descriptor; live block -> canonical; story ->
  queue 1), with the position WITHOUT fraction and only once the elevator has
  arrived (a spawn inside the platform pushes the player out of the map, exp618a).
- Cosmetics: the game only repaints the capsules when loading D-4, so the
  client replicates FUN_02013328: it copies the 5x6 metatile patch (u16) of
  each capsule from ovl061 to the room's metatile map (0x02112B78,
  stride 192 in D-4) and marks the map dirty (u16 0x0212DB54+0x28 = 1).
"""

SUBAREA = 18                     # D-4 (tower)
HANDLER_ID = 16                  # mission "Destroy Model W"
FLAG_LEFT = 0x021045FF           # bit 4+k = pair k, left teleporter
FLAG_RIGHT = 0x02104600          # bit k   = pair k, right teleporter
STAGE = 0x0212FBA1               # elevator stage (u8)

TILEMAP = 0x02112B78             # metatile map of the loaded room (u16 per metatile)
TILEMAP_STRIDE = 192             # D-4: 12 screens x 16 metatiles
TILEMAP_DIRTY = 0x0212DB54 + 0x28   # u16 = 1 -> the engine re-uploads the visible map
# (tx, ty, patch in ovl061) of each capsule: [pair] = (left, right).
# Patch = u16 width (5), s16 height (6), 5x6 u16 (64 B).
PATCHES = {
    0: ((0x10, 0x0E, 0x02195A58), (0x1B, 0x0E, 0x02195B98)),
    1: ((0x30, 0x0E, 0x02195B18), (0x3B, 0x0E, 0x02195B58)),
    2: ((0x10, 0x26, 0x02195A18), (0x1B, 0x26, 0x021959D8)),
    3: ((0x30, 0x26, 0x02195AD8), (0x3B, 0x26, 0x02195A98)),
}
PATCH_W, PATCH_H = 5, 6

SHAFT1 = (1536, 1792)            # elevator shaft 1 (x)
SHAFT2 = (2560, 2816)            # elevator shaft 2 (x)
# pair -> (shaft, max y of the player STANDING at the stop (+1), handler
# state, elevator stage). The player standing on the elevator ends up at
# y = stop + 23 (2463, 543, 2847, 927).
STOPS = {
    0: (SHAFT1, 2464, 2, 2),
    1: (SHAFT1, 544, 4, 4),
    2: (SHAFT2, 2848, 5, 7),
    3: (SHAFT2, 928, 7, 9),
}
# rooms of each pair (x0, x1, y0, y1): A Hivolt/Hurricaune, B Lurerre/Leganchor,
# C Fistleo/Flammole, D Purprill/Protectos.
ROOMS = {
    0: (248, 760, 200, 420),
    1: (760, 1040, 200, 420),
    2: (248, 760, 600, 800),
    3: (760, 1040, 600, 800),
}
PAIR_NAMES = {0: "Hivolt/Hurricaune", 1: "Lurerre/Leganchor",
              2: "Fistleo/Flammole", 3: "Purprill/Protectos"}


def pair_set(flag_left: int, flag_right: int, k: int) -> bool:
    return bool((flag_left >> (4 + k)) & 1 and (flag_right >> k) & 1)


def pairs_to_set(x: int, y: int, hstate: int, stage: int,
                 flag_left: int, flag_right: int) -> list:
    """Pairs to mark as defeated NOW (player in D-4, in game, mission 16
    handler installed and no cutscene in progress). Sorted."""
    out = []
    for k in range(4):
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
    for k in pairs:
        flag_left |= 1 << (4 + k)
        flag_right |= 1 << k
    return flag_left & 0xFF, flag_right & 0xFF


def paint_writes(k: int, patch_bytes) -> list:
    """Writes [(address, bytes)] that paint the two capsules of pair k as
    used. `patch_bytes(addr)` returns the 64 B of the patch at `addr` (they
    are in RAM while D-4 is loaded). Replicates FUN_02013328."""
    out = []
    for tx, ty, src in PATCHES[k]:
        data = patch_bytes(src)
        w = int.from_bytes(data[0:2], "little")
        h = int.from_bytes(data[2:4], "little", signed=True)
        if w != PATCH_W or h != PATCH_H:      # foreign overlay loaded: do not touch
            return []
        for row in range(h):
            out.append((TILEMAP + (tx + (ty + row) * TILEMAP_STRIDE) * 2,
                        data[4 + row * w * 2: 4 + (row + 1) * w * 2]))
    out.append((TILEMAP_DIRTY, (1).to_bytes(2, "little")))
    return out
