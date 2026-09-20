"""Mini-bosses treated as beaten (skip_minibosses): all of them, or the ones beaten once."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import MINIBOSS_FLAGS, ROOM_SUBAREA
from .addresses import (
    CUTSCENE_FLAG, DOM, MINIBOSSES_KEY, O02_MINIBOSS_FLAG, O02_SCRIPT_MINIBOSS_BEATEN,
    O02_SCRIPT_MINIBOSS_WAIT, ROOM_SCRIPT_STATE)
from .ram import Tick, bits_by_byte, copies_writes, missing_bits, read_copies

if TYPE_CHECKING:
    from . import MMZXClient

MODE_OFF, MODE_AFTER_FIRST_DEFEAT, MODE_ALWAYS = "off", "after_first_defeat", "always"
AREA_OF_SUBAREA = {sub: room[0].upper() for room, sub in ROOM_SUBAREA.items()}
O02_SUBAREA = ROOM_SUBAREA["o02"]


def parse_mode(value) -> str:
    """The option as the client sees it; older slot data carried a plain toggle."""
    if isinstance(value, bool):
        return MODE_ALWAYS if value else MODE_OFF
    return value if value in (MODE_AFTER_FIRST_DEFEAT, MODE_ALWAYS) else MODE_OFF


async def skip_minibosses(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Keep the "beaten" flag of the current area's mini-bosses set.

    The game clears these flags whenever the player changes area, so they are
    set again on each visit, from any room of the area: a room whose script
    decides at load time then finds them already set. With after_first_defeat
    only the mini-bosses the player has beaten, remembered in the datastore.
    """
    area = AREA_OF_SUBAREA.get(tick.subarea, "")
    bits = [tuple(b) for b in MINIBOSS_FLAGS.get(area, [])]
    if not bits:
        return
    masks = bits_by_byte(bits)
    addrs = list(masks)
    live, canon = await read_copies(ctx, addrs)
    if client.skip_minibosses == MODE_AFTER_FIRST_DEFEAT:
        bits = await remember_beaten(client, ctx, area, bits, live, canon)
        if not bits:
            return
        masks = bits_by_byte(bits)
        addrs = list(masks)
    writes = copies_writes(addrs, live, canon, set_masks=masks)
    if writes:
        if not await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
            return
        client._debug("[mmzx] area %s: mini-bosses marked as beaten (%d flags were clear)"
                      % (area, missing_bits(addrs, live, canon, masks)))
    if tick.subarea == O02_SUBAREA and O02_MINIBOSS_FLAG in bits:
        await unstick_o02(client, ctx, tick)


async def remember_beaten(client: "MMZXClient", ctx, area: str, bits, live, canon) -> list:
    """The mini-bosses of `bits` beaten so far, after recording any the game just marked.

    Only the game sets a flag the client has not recorded, and it does so when
    the mini-boss dies; either copy counts, since an area change clears the
    live one first.
    """
    if client.minibosses_beaten is None:
        await resolve_beaten(client, ctx)
        if client.minibosses_beaten is None:
            return []
    new = [(a, b) for a, b in bits
           if (a, b) not in client.minibosses_beaten and ((live[a] | canon[a]) >> b) & 1]
    if new:
        client.minibosses_beaten.update(new)
        await ctx.send_msgs([{
            "cmd": "Set", "key": client.minibosses_key, "default": [], "want_reply": False,
            "operations": [{"operation": "replace",
                            "value": sorted([a, b] for a, b in client.minibosses_beaten)}],
        }])
        client._debug("[mmzx] area %s: %d mini-boss(es) beaten, they stay beaten" % (area, len(new)))
    return [b for b in bits if b in client.minibosses_beaten]


async def resolve_beaten(client: "MMZXClient", ctx) -> None:
    """Load the beaten mini-bosses from the datastore; None until the reply arrives."""
    if client.minibosses_key is None:
        client.minibosses_key = MINIBOSSES_KEY % (ctx.team, ctx.slot)
    if not client.minibosses_requested:
        await ctx.send_msgs([
            {"cmd": "SetNotify", "keys": [client.minibosses_key]},
            {"cmd": "Get", "keys": [client.minibosses_key]},
        ])
        client.minibosses_requested = True
        return
    if client.minibosses_key not in ctx.stored_data:
        return
    val = ctx.stored_data[client.minibosses_key]
    beaten = set()
    if isinstance(val, list):
        for e in val:
            if isinstance(e, list) and len(e) == 2 and all(isinstance(x, int) for x in e):
                beaten.add((e[0], e[1]))
    client.minibosses_beaten = beaten


async def unstick_o02(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Move the O-2 room script past the mini-boss it is still waiting for."""
    r = await bizhawk.read(ctx.bizhawk_ctx, [(ROOM_SCRIPT_STATE, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
    if r[0][0] != O02_SCRIPT_MINIBOSS_WAIT or r[1][0] & 1:
        return
    writes = [(ROOM_SCRIPT_STATE, bytes([O02_SCRIPT_MINIBOSS_BEATEN]), DOM)]
    if await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        client._debug("[mmzx] O-2: room script moved past the mini-boss (state %d -> %d)"
                      % (O02_SCRIPT_MINIBOSS_WAIT, O02_SCRIPT_MINIBOSS_BEATEN))
