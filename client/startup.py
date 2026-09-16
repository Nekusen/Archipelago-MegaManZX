"""The starting state: the golden image seeded into the LOAD buffer while the title is up,
and the one-shot RAM application driven by the datastore key.
"""

import logging
from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import ACTIVE_MODEL_ADDR, ITEMS, MODEL_X_POSSESSION, STARTING_MODELS, STARTING_TRANSERVERS
from .golden import GOLDEN_IMAGE_ADDR, build_image
from .addresses import (
    DOM, GAME_STATE, ITEM_ID_TO_NAME, START_CONFIRM_TICKS, START_MAX_RETRIES,
    STATE_GAME_OVER_LOW, STATE_INGAME, TITLE_CAROUSEL_STEP, TITLE_STEPS_SEEDABLE)
from .ram import Tick, bits_by_byte, copies_writes, read_copies

if TYPE_CHECKING:
    from . import MMZXClient

logger = logging.getLogger("Client")


def starting_point(ctx) -> dict:
    """Record of the slot's starting_transerver; the first one when the key is unknown."""
    key = str(ctx.slot_data.get("starting_transerver", ""))
    return STARTING_TRANSERVERS.get(key) or next(iter(STARTING_TRANSERVERS.values()))


def starting_access_bit(start: dict) -> tuple[int, int] | None:
    """(address, bit) of the Transport destination the start point grants, if any."""
    grant = ITEMS.get(start.get("access") or "", {}).get("grant")
    return (grant[1], grant[2]) if grant else None


async def resolve_start_state(client: "MMZXClient", ctx) -> None:
    """Advance the starting-state machine from its datastore key, in menus too.

    0 request, 1 waiting for the reply, 2 apply in gameplay, 3 done.
    """
    if client.start_state >= 2:
        return
    client.start_key = "mmzx_start_applied_%s_%s" % (ctx.team, ctx.slot)
    if client.start_state == 0:
        await ctx.send_msgs([
            {"cmd": "SetNotify", "keys": [client.start_key]},
            {"cmd": "Get", "keys": [client.start_key]},
        ])
        client.start_state = 1
        return
    if client.start_key in ctx.stored_data:
        client.start_state = 3 if ctx.stored_data[client.start_key] else 2


async def seed_golden_image(client: "MMZXClient", ctx) -> None:
    """Seed the golden image into the LOAD buffer while the title or its menus are up.

    New Game is redirected to LOAD, so every new game starts in the hub,
    also after a Game Over. Only carousel steps 3 and 5 with the state word
    at gameplay or at a Game Over menu are safe: the data select restores
    the SRAM there, and in gameplay the buffer is the live scene. Guarded on both.
    """
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (GAME_STATE, 4, DOM), (TITLE_CAROUSEL_STEP, 1, DOM)])
    gs = int.from_bytes(r[0], "little")
    if r[1][0] not in TITLE_STEPS_SEEDABLE:
        return
    if not (gs == STATE_INGAME or (gs & 0xFF) == STATE_GAME_OVER_LOW):
        return
    img = build_image(str(ctx.slot_data.get("starting_model", "model_zx")),
                      int(ctx.slot_data.get("character", 0) or 0), STARTING_MODELS,
                      starting_point(ctx))
    await bizhawk.guarded_write(
        ctx.bizhawk_ctx,
        [(GOLDEN_IMAGE_ADDR, bytes(img), DOM)],
        [(TITLE_CAROUSEL_STEP, r[1], DOM), (GAME_STATE, r[0], DOM)])


async def apply_start_state(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Apply the starting state once the player is in the starting room (start_state 2).

    Re-asserts the active model until it holds, since the LOAD may force
    Model X once, then marks the datastore key. A save that shows the raw
    golden signature under an applied slot (Model X owned without its item
    while the start is another model) is a new save: the state is re-armed.
    """
    start = starting_point(ctx)
    if client.start_state == 3 and tick.subarea == start["sub"]:
        rec = STARTING_MODELS.get(str(ctx.slot_data.get("starting_model", "model_zx")))
        got_x = any(ITEM_ID_TO_NAME.get(net.item) == "Model X" for net in ctx.items_received)
        if rec and rec.get("revoke_x") and not got_x:
            xa, xb = MODEL_X_POSSESSION
            if (await bizhawk.read(ctx.bizhawk_ctx, [(xa, 1, DOM)]))[0][0] & (1 << xb):
                logger.info("[mmzx] new save detected (seeded Model X): re-applying the starting state")
                client.start_state = 2
                client.start_confirm = 0
                client.start_retries = 0
    if client.start_state != 2 or tick.subarea != start["sub"]:
        return
    # the floor's script sets its own destination bit once the scene has settled
    access = starting_access_bit(start)
    if access:
        v = (await bizhawk.read(ctx.bizhawk_ctx, [(access[0], 1, DOM)]))[0][0]
        if not v & (1 << access[1]):
            return
    guard = tick.guard
    desired_active = await write_start_state(client, ctx, guard)
    if desired_active is None:
        return   # the guard rejected the write: retry next tick
    if desired_active == -1:      # unknown model: nothing to confirm
        client.start_confirm = START_CONFIRM_TICKS
    active_now = (await bizhawk.read(ctx.bizhawk_ctx, [(ACTIVE_MODEL_ADDR, 1, DOM)]))[0][0]
    client.start_retries += 1
    client.start_confirm = client.start_confirm + 1 if active_now == desired_active else 0
    if client.start_confirm >= START_CONFIRM_TICKS or client.start_retries > START_MAX_RETRIES:
        client.start_state = 3
        await ctx.send_msgs([{
            "cmd": "Set", "key": client.start_key, "default": False,
            "want_reply": False,
            "operations": [{"operation": "replace", "value": True}],
        }])


async def write_start_state(client: "MMZXClient", ctx, guard) -> int | None:
    """Write the starting model's possession and active value.

    Returns the desired active model, -1 for an unknown one, or None if the
    guard rejected the writes. The position needs no write: the image spawns
    the player at the start point.
    """
    key = str(ctx.slot_data.get("starting_model", "model_zx"))
    rec = STARTING_MODELS.get(key)
    if rec is None:
        logger.info("[mmzx] unknown starting_model: %r (ignored)" % key)
        return -1
    # possessions: revoke X if applicable, grant those of the chosen model
    clear = bits_by_byte([tuple(MODEL_X_POSSESSION)]) if rec["revoke_x"] else {}
    on = bits_by_byte(tuple(g) for g in rec["grant"])
    addrs = sorted(set(clear) | set(on))
    writes: list[tuple[int, bytes, str]] = []
    if addrs:
        live, canon = await read_copies(ctx, addrs)
        writes = copies_writes(addrs, live, canon, set_masks=on, clear_masks=clear)
    writes.append((ACTIVE_MODEL_ADDR, bytes([rec["active"]]), DOM))
    if not await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
        return None
    if client.start_confirm == 0 and client.start_retries == 0:
        logger.info("[mmzx] starting state applied: model=%s, transerver=%s"
                    % (key, ctx.slot_data.get("starting_transerver")))
    return rec["active"]
