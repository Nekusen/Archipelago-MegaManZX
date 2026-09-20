"""Mini-bosses treated as already beaten (skip_minibosses)."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import MINIBOSS_FLAGS, ROOM_SUBAREA
from .addresses import (
    CUTSCENE_FLAG, DOM, O02_SCRIPT_MINIBOSS_BEATEN, O02_SCRIPT_MINIBOSS_WAIT, ROOM_SCRIPT_STATE)
from .ram import Tick, bits_by_byte, copies_writes, missing_bits, read_copies

if TYPE_CHECKING:
    from . import MMZXClient

AREA_OF_SUBAREA = {sub: room[0].upper() for room, sub in ROOM_SUBAREA.items()}
O02_SUBAREA = ROOM_SUBAREA["o02"]


async def skip_minibosses(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Keep the "beaten" flag of every mini-boss of the current area set.

    The game clears these flags whenever the player changes area, so they are
    set again on each visit, from any room of the area: a room whose script
    decides at load time then finds them already set.
    """
    area = AREA_OF_SUBAREA.get(tick.subarea, "")
    bits = MINIBOSS_FLAGS.get(area)
    if not bits:
        return
    masks = bits_by_byte([tuple(b) for b in bits])
    addrs = list(masks)
    live, canon = await read_copies(ctx, addrs)
    writes = copies_writes(addrs, live, canon, set_masks=masks)
    if writes:
        if not await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
            return
        client._debug("[mmzx] area %s: mini-bosses marked as beaten (%d flags were clear)"
                      % (area, missing_bits(addrs, live, canon, masks)))
    if tick.subarea == O02_SUBAREA:
        await unstick_o02(client, ctx, tick)


async def unstick_o02(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Move the O-2 room script past the mini-boss it is still waiting for."""
    r = await bizhawk.read(ctx.bizhawk_ctx, [(ROOM_SCRIPT_STATE, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
    if r[0][0] != O02_SCRIPT_MINIBOSS_WAIT or r[1][0] & 1:
        return
    writes = [(ROOM_SCRIPT_STATE, bytes([O02_SCRIPT_MINIBOSS_BEATEN]), DOM)]
    if await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        client._debug("[mmzx] O-2: room script moved past the mini-boss (state %d -> %d)"
                      % (O02_SCRIPT_MINIBOSS_WAIT, O02_SCRIPT_MINIBOSS_BEATEN))
