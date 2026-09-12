"""Position for Universal Tracker, DeathLink and the /mmzx_where dump."""

import logging
import time
from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import ACTIVE_MODEL_ADDR, MISSION_STATE_ADDR
from .addresses import (
    CUTSCENE_FLAG, DEATH_STATE, DEATH_SUBSTATE, DOM, GAME_STATE, HP, MISSION_ACTIVE_BYTE,
    PLAYER_OBJ, PLAYER_POS, PLAYER_STATE_OFF, POS_INTERVAL, POS_KEY, POS_MIN_DELTA,
    STORY_HANDLER_ID, STORY_HANDLER_STATE, SUBAREA_STABLE, TITLE_CAROUSEL_STEP, TROOP_MERGE)
from .ram import Tick, decode_position

if TYPE_CHECKING:
    from . import MMZXClient

logger = logging.getLogger("Client")


async def send_position(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Publish [subarea, x, y] for Universal Tracker, throttled.

    UT reloads the map tab on every change of the key, so the position goes
    out on a subarea change and otherwise at most once per POS_INTERVAL
    after POS_MIN_DELTA px of movement.
    """
    if not ctx.slot:
        return
    sub = tick.subarea
    x, y = decode_position((await bizhawk.read(ctx.bizhawk_ctx, [(PLAYER_POS, 8, DOM)]))[0])
    now = time.monotonic()
    last = client.pos_last
    if last is not None and sub == last[0]:
        if now - last[3] < POS_INTERVAL:
            return
        if abs(x - last[1]) < POS_MIN_DELTA and abs(y - last[2]) < POS_MIN_DELTA:
            return
    client.pos_last = (sub, x, y, now)
    await ctx.send_msgs([{
        "cmd": "Set", "key": POS_KEY % ctx.slot, "default": [0, 0, 0],
        "want_reply": False,
        "operations": [{"operation": "replace", "value": [int(sub), int(x), int(y)]}],
    }])


async def log_where(client: "MMZXClient", ctx) -> None:
    """/mmzx_where: subarea, position, state and mission to the log."""
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (SUBAREA_STABLE, 1, DOM), (PLAYER_POS, 8, DOM), (GAME_STATE, 4, DOM),
        (HP, 1, DOM), (TITLE_CAROUSEL_STEP, 1, DOM), (MISSION_STATE_ADDR, 4, DOM),
        (MISSION_ACTIVE_BYTE, 1, DOM), (STORY_HANDLER_ID, 4, DOM), (ACTIVE_MODEL_ADDR, 1, DOM),
        (STORY_HANDLER_STATE, 1, DOM), (TROOP_MERGE[0], 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
    x, y = decode_position(r[1])
    logger.info("[mmzx] where: sub=%d pos=(%d,%d) gs=%06X hp=%d step=%d mission(state)=%d 462B=%02X handler=%d model=%d auto_accept=%s items=%d"
                % (r[0][0], x, y, int.from_bytes(r[2], "little"), r[3][0], r[4][0],
                   int.from_bytes(r[5], "little"), r[6][0], int.from_bytes(r[7], "little"), r[8][0],
                   client.mission_auto_accept, len(ctx.items_received)))
    logger.info("[mmzx] where+: handler_state=%02X megamerge(0x02104602.1)=%d cutscene=%d"
                % (r[9][0], (r[10][0] >> TROOP_MERGE[1]) & 1, r[11][0] & 1))


async def report_death(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Send a DeathLink when the player goes from alive to dead, unless this client caused it.

    Runs before the in-game guard, which a dead player fails. The title and a
    reload leave the state unknown, so the first tick after them never counts.
    """
    alive = (not tick.dead) if tick.launched else None
    if client.prev_alive and alive is False:
        if client.death_induced:
            client.death_induced = False      # the death we applied: no echo
        else:
            await ctx.send_death(f"{ctx.player_names[ctx.slot]} ran out of energy.")
        client.prev_death_link = ctx.last_death_link  # do not self-receive our own
    client.prev_alive = alive


async def receive_death_link(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Apply a received death the way the game does it, once the player has control.

    HP 0 plus the dying state bytes; HP alone does not kill. The death stays
    pending through cutscenes and interactions.
    """
    if client.prev_death_link is None:
        client.prev_death_link = ctx.last_death_link
    if ctx.last_death_link > client.prev_death_link:
        client.prev_death_link = ctx.last_death_link
        client.pending_death = True
    if not client.pending_death:
        return
    cutscene = (await bizhawk.read(ctx.bizhawk_ctx, [(CUTSCENE_FLAG, 1, DOM)]))[0][0] & 1
    if cutscene or tick.player_state != 0:
        return                      # no control: retried on the next tick
    writes = [(HP, b"\x00", DOM),
              (PLAYER_OBJ + PLAYER_STATE_OFF, bytes([DEATH_STATE, DEATH_SUBSTATE, 0]), DOM)]
    if await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        client.pending_death = False
        client.death_induced = True
        logger.info("[mmzx] DeathLink received: death applied")
