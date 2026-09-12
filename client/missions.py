"""Missions in the open world: auto-accept, repairs of what the game undoes,
the boss rush skip and the ending.
"""

import logging
from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import (
    CANON_BLOCK, HUB_FLOOR_BOSS, HUB_FLOOR_DOOR_X, LIVE_BLOCK, MISSION_ACCEPT,
    MISSION_ACTIVE_FLAG, MISSION_STATE_ADDR)
from . import bossrush as BR
from .addresses import (
    BLOCK_MIRROR, CANON_OFF, CUTSCENE_FLAG, D02_ROOM_MERGED, D05_ROOM_TERMINAL, DESC_FACING_OFF,
    DOM, ENDING_HANDLER_ID, ENDING_HANDLER_STATE, ENDING_SERPENT, ENDING_SUBAREA,
    ENDING_UNSTICK_TICKS, GAME_CLEARED, HUB_FLOOR_NEAR, HUB_PAD_DY, HUB_SUBAREA, LIVE_BLOCK_LEN,
    MISSION_ACCEPTED_MASK, MISSION_ACTIVE_BYTE, PLAYER_FACING_MASK, PLAYER_FACING_OFF,
    PLAYER_OBJ, PLAYER_PERSIST, PLAYER_POS, PLAYER_SCENE_WORD_OFF, ROOM_SCRIPT_STATE, SCENE_DESC,
    SCENE_DESC_LEN, SCENE_DESC_MIRROR, STORY_BLOCK, STORY_BLOCK_CANON, STORY_BLOCK_LEN,
    STORY_BLOCK_MIRROR, STORY_HANDLER_ID, STORY_HANDLER_STATE, TROOP_MERGE, TROOP_MERGE_SUBAREA,
    TROOP_NAME, TROOP_ROOMS, TROOP_START, TROOP_STATE)
from .ram import (
    ProgressWindow, Tick, bits_by_byte, copies_reads, copies_values, copies_writes,
    decode_position, missing_bits, mission_completed, mission_done_bits, read_copies,
    story_handler_writes)
from .checks import report_goal

if TYPE_CHECKING:
    from . import MMZXClient

logger = logging.getLogger("Client")


async def repair_missions(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Undo what the game does to an active mission: Troop's flags, then the extra bits."""
    await troop_unstick(client, ctx, tick)
    if client.mission_auto_accept:
        await restore_mission_bits(client, ctx, tick.guard)


async def troop_unstick(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Re-arm the Giro scene of D-2 while Troop Reinforcement is active.

    The scene needs the start flag set and the megamerge flag clear; dying
    after the megamerge without the Report would leave D-2 empty for good.
    """
    if tick.subarea not in TROOP_ROOMS:
        return
    # The start flag is always restored; the megamerge flag only until the
    # D-2 script has passed the merge, since the X-2 report needs it set.
    merged = False
    if tick.subarea == TROOP_MERGE_SUBAREA:
        merged = (await bizhawk.read(ctx.bizhawk_ctx, [(ROOM_SCRIPT_STATE, 1, DOM)]))[0][0] >= D02_ROOM_MERGED
    maddr, mbit = TROOP_MERGE
    saddr, sbit = TROOP_START
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (MISSION_STATE_ADDR, 4, DOM), (maddr, 1, DOM), (maddr + CANON_OFF, 1, DOM),
        (CUTSCENE_FLAG, 1, DOM), (saddr, 1, DOM), (saddr + CANON_OFF, 1, DOM)])
    if int.from_bytes(r[0], "little") != TROOP_STATE or r[3][0] & 1:
        return
    live = {maddr: r[1][0], saddr: r[4][0]}
    canon = {maddr: r[2][0], saddr: r[5][0]}
    stuck_merge = bool((live[maddr] | canon[maddr]) & (1 << mbit)) and not merged
    stuck_start = not (live[saddr] & canon[saddr] & (1 << sbit))
    if not (stuck_merge or stuck_start):
        return
    if await mission_completed(ctx, TROOP_NAME):
        return       # the bits are legitimate now
    what = []
    if stuck_merge:
        what.append("cleared the megamerge flag 0x02104602.1")
    if stuck_start:
        what.append("restored the mission start flag 0x021045E0.2 (the game itself clears it)")
    writes = copies_writes([maddr, saddr], live, canon,
                           set_masks={saddr: 1 << sbit},
                           clear_masks={maddr: 1 << mbit} if stuck_merge else None)
    if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        client._debug("[mmzx] Troop Reinforcement was half done: %s; the Giro scene "
                      "can trigger again" % " and ".join(what))


async def restore_mission_bits(client: "MMZXClient", ctx, guard) -> None:
    """Re-set the extra bits of the active mission if something cleared them."""
    state = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(MISSION_STATE_ADDR, 4, DOM)]))[0], "little")
    rec = next((v for v in MISSION_ACCEPT.values() if v["state"] == state), None)
    extras = (rec or {}).get("extra")
    if not extras:
        return
    done = mission_done_bits(rec["name"])
    masks = bits_by_byte(extras)
    addrs = list(masks)
    cur = await bizhawk.read(ctx.bizhawk_ctx, copies_reads(addrs) + [(a, 1, DOM) for a, _ in done])
    n = 2 * len(addrs)
    if done and all(cur[n + i][0] & (1 << b) for i, (_, b) in enumerate(done)):
        return          # already completed
    live, canon = copies_values(addrs, cur)
    writes = copies_writes(addrs, live, canon, set_masks=masks)
    if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
        client._debug("[mmzx] %s: restored %d mission bits that something had cleared"
                      % (rec["name"], missing_bits(addrs, live, canon, masks)))


async def mission_here(client: "MMZXClient", ctx, sub: int):
    """(key, record) of the mission of the current subarea or hub floor, or None.

    Floors whose door leads to a boss room keep it shut until the mission is
    accepted, so it is accepted near the door, not on arrival, or the floor's
    console turns into "Abort the mission?". The key remembers what was handled.
    """
    if sub != HUB_SUBAREA:
        if sub == client.last_accept_sub and not client.force_accept:
            return None
        return sub, MISSION_ACCEPT.get(sub)
    x, y = decode_position((await bizhawk.read(ctx.bizhawk_ctx, [(PLAYER_POS, 8, DOM)]))[0])
    floor = next((fy for fy in HUB_FLOOR_BOSS if abs(y - (fy - HUB_PAD_DY)) <= HUB_FLOOR_NEAR), None)
    if floor is None or (x > HUB_FLOOR_DOOR_X and not client.force_accept):
        client.last_accept_sub = None
        return None
    if client.last_accept_sub == ("hub", floor) and not client.force_accept:
        return None
    rec = MISSION_ACCEPT.get(HUB_FLOOR_BOSS[floor])
    client._debug("[mmzx] hub floor y=%d (player at %d,%d): mission %s"
                  % (floor, x, y, rec["name"] if rec else "?"))
    return ("hub", floor), rec


async def auto_accept_mission(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Accept the mission of the subarea or hub floor just entered (open world).

    Never re-accepts a completed mission (a second Report would pay again); an
    active one only gets its missing extra bits back. Protect HQ is not in the
    table; the game launches it on its own.
    """
    found = await mission_here(client, ctx, tick.subarea)
    if found is None:
        return
    key, rec = found
    guard = tick.guard
    client.force_accept = False
    if not rec:
        client.last_accept_sub = key
        return
    if await mission_completed(ctx, rec["name"]):
        client.last_accept_sub = key
        client._debug("[mmzx] %s already completed: not accepted again" % rec["name"])
        return
    state = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(MISSION_STATE_ADDR, 4, DOM)]))[0], "little")
    if state == rec["state"]:
        client.last_accept_sub = key
        extras = rec.get("extra", [])
        if extras:
            masks = bits_by_byte(extras)
            addrs = list(masks)
            live, canon = await read_copies(ctx, addrs)
            writes = copies_writes(addrs, live, canon, set_masks=masks)
            if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
                client._debug("[mmzx] %s was already accepted: restored %d missing mission bits"
                              % (rec["name"], missing_bits(addrs, live, canon, masks)))
        return
    if await accept_mission(ctx, rec, guard):
        client.last_accept_sub = key      # only marked if the write went through
        client._debug("[mmzx] open world: mission auto-accepted -> %s" % rec["name"])
    else:
        client._debug("[mmzx] acceptance of %s not applied (game state guard); retrying" % rec["name"])


async def accept_mission(ctx, rec: dict, guard) -> bool:
    """Accept a mission the way the console does, in one guarded write.

    Snapshot for Abort Mission, start flag and extra bits composed per byte,
    state, active flags and story handler; then the checkpoint commit a pad
    would do, or a death before the first milestone restores a checkpoint
    without the mission.
    """
    masks = bits_by_byte([tuple(rec["flag"])] + [tuple(e) for e in rec.get("extra", [])])
    flag_addrs = list(masks)
    act = MISSION_ACTIVE_BYTE
    cur = await bizhawk.read(ctx.bizhawk_ctx, copies_reads(flag_addrs) + copies_reads([act]) + [
        (LIVE_BLOCK, LIVE_BLOCK_LEN, DOM), (SCENE_DESC, SCENE_DESC_LEN, DOM),
        (STORY_BLOCK, STORY_BLOCK_LEN, DOM)])
    live, canon = copies_values(flag_addrs, cur)
    act_live, act_canon = copies_values([act], cur, start=2 * len(flag_addrs))
    block, desc, story = cur[2 * len(flag_addrs) + 2:]
    writes = [(BLOCK_MIRROR, block, DOM), (SCENE_DESC_MIRROR, desc, DOM), (STORY_BLOCK_MIRROR, story, DOM)]
    for a in flag_addrs:
        writes.append((a, bytes([live[a] | masks[a]]), DOM))
        writes.append((a + CANON_OFF, bytes([canon[a] | masks[a]]), DOM))
    writes += [
        (MISSION_STATE_ADDR, rec["state"].to_bytes(4, "little"), DOM),
        (MISSION_ACTIVE_FLAG, b"\x01", DOM),
        # "mission in progress" bit, tested by the game's "is mission X active"
        (act, bytes([act_live[act] | MISSION_ACCEPTED_MASK]), DOM),
        (act + CANON_OFF, bytes([act_canon[act] | MISSION_ACCEPTED_MASK]), DOM),
    ]
    writes += story_handler_writes(int(rec["id"]), int(rec.get("hstate", 0)))
    if not await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
        return False
    cur = await bizhawk.read(ctx.bizhawk_ctx, [(LIVE_BLOCK, LIVE_BLOCK_LEN, DOM), (STORY_BLOCK, STORY_BLOCK_LEN, DOM)])
    await bizhawk.guarded_write(ctx.bizhawk_ctx, [
        (CANON_BLOCK, cur[0], DOM), (STORY_BLOCK_CANON, cur[1], DOM)], [guard])
    return True


async def skip_boss_rush(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Mark Pseudoroid pairs as beaten in the D-4 boss rush (skip_boss_rush).

    A pair is set only once the elevator stands at its stop or the player is
    inside its room: set early, the elevator jumps and drops the player. The
    checkpoint is committed as a pad would, or a death would respawn with
    the handler out of sync and a dead elevator.
    """
    if tick.subarea != BR.SUBAREA:
        return
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (CUTSCENE_FLAG, 1, DOM), (STORY_HANDLER_ID, 4, DOM), (STORY_HANDLER_STATE, 1, DOM),
        (BR.STAGE, 1, DOM), (PLAYER_POS, 8, DOM), (BR.FLAG_LEFT, 1, DOM), (BR.FLAG_RIGHT, 1, DOM)])
    if (r[0][0] & 1) or int.from_bytes(r[1], "little") != BR.HANDLER_ID:
        return
    x, y = decode_position(r[4])
    flag_left, flag_right = r[5][0], r[6][0]
    pairs = BR.pairs_to_set(x, y, r[2][0], r[3][0], flag_left, flag_right)
    if not pairs:
        return
    # reads for the commit and the repaint, all in one batch
    reads = [(LIVE_BLOCK, LIVE_BLOCK_LEN, DOM), (STORY_BLOCK, STORY_BLOCK_LEN, DOM),
             (PLAYER_PERSIST, SCENE_DESC_LEN, DOM), (PLAYER_OBJ + PLAYER_FACING_OFF, 1, DOM),
             (PLAYER_OBJ + PLAYER_SCENE_WORD_OFF, 4, DOM)]
    patch_addrs = [src for k in pairs for (_tx, _ty, src) in BR.PATCHES[k]]
    reads += [(a, 4 + BR.PATCH_W * BR.PATCH_H * 2, DOM) for a in patch_addrs]
    q = await bizhawk.read(ctx.bizhawk_ctx, reads)
    live = bytearray(q[0])
    fl, fr = BR.apply_pairs(flag_left, flag_right, pairs)
    live[BR.FLAG_LEFT - LIVE_BLOCK] = fl
    live[BR.FLAG_RIGHT - LIVE_BLOCK] = fr
    persist = bytearray(q[2])
    persist[0:4] = (x << 8).to_bytes(4, "little")       # spawn without fraction, like the doors
    persist[4:8] = (y << 8).to_bytes(4, "little")
    persist[DESC_FACING_OFF] = (persist[DESC_FACING_OFF] & 0xFE) | (1 if q[3][0] & PLAYER_FACING_MASK else 0)
    desc = bytes(persist[:8]) + q[4] + bytes(persist[12:])   # +8 = player's scene word
    patches = {a: q[5 + i] for i, a in enumerate(patch_addrs)}
    writes = [(BR.FLAG_LEFT, bytes([fl]), DOM), (BR.FLAG_RIGHT, bytes([fr]), DOM),
              (PLAYER_PERSIST, bytes(persist), DOM), (SCENE_DESC, desc, DOM),
              (CANON_BLOCK, bytes(live), DOM), (STORY_BLOCK_CANON, q[1], DOM)]
    for k in pairs:
        writes += [(a, b, DOM) for a, b in BR.paint_writes(k, patches.get)]
    if await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        for k in pairs:
            client._debug("[mmzx] boss rush skipped: %s marked as beaten (player at %d,%d); "
                          "checkpoint saved" % (BR.PAIR_NAMES[k], x, y))


async def handle_ending(client: "MMZXClient", ctx, window: ProgressWindow, tick: Tick) -> None:
    """Send the goal, then make sure the credits can start."""
    await report_goal(ctx, window)
    await ending_unstick(client, ctx, tick)


async def ending_unstick(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Install the mission 16 story handler if Serpent died without it.

    Without that handler nobody starts the credits and the screen stays
    white. Runs after the goal, writes only the handler, at the state where
    vanilla waits for Serpent 2's death; the game carries on by itself.
    """
    if tick.subarea != ENDING_SUBAREA:
        client.ending_ticks = 0
        return
    saddr, smask = ENDING_SERPENT
    caddr, cbit = GAME_CLEARED
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (saddr, 1, DOM), (caddr, 1, DOM), (CUTSCENE_FLAG, 1, DOM), (ROOM_SCRIPT_STATE, 1, DOM),
        (STORY_HANDLER_ID, 4, DOM), (STORY_HANDLER_STATE, 1, DOM)])
    handler_id = int.from_bytes(r[4], "little")
    stuck = ((r[0][0] & smask) == smask                  # Serpent 1 and 2 defeated
             and not (r[1][0] & (1 << cbit))             # the game has not closed already
             and not (r[2][0] & 1)                       # no cutscene in progress
             and r[3][0] == D05_ROOM_TERMINAL            # D-5 script finished
             and (handler_id != ENDING_HANDLER_ID
                  or r[5][0] < ENDING_HANDLER_STATE))    # handler missing or behind
    if not stuck:
        client.ending_ticks = 0
        return
    client.ending_ticks += 1
    if client.ending_ticks < ENDING_UNSTICK_TICKS:
        return
    ok = await bizhawk.guarded_write(
        ctx.bizhawk_ctx, story_handler_writes(ENDING_HANDLER_ID, ENDING_HANDLER_STATE), [tick.guard])
    if ok:
        client.ending_ticks = 0
        logger.info("[mmzx] the ending had no story handler (white screen after "
                    "Serpent): final cutscene started; the credits follow")
