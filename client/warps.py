""""Go to Transerver" from the pause menu, and scene-load teleports."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import HUB_FLOOR_Y
from .addresses import (
    DESC_FACING_OFF, DESC_SPAWN_X_OFF, DESC_SPAWN_Y_OFF, DESC_SUBAREA_OFF, DOM, GAME_STATE,
    HUB_PAD_DY, HUB_SUBAREA, HUB_X, SCENE_DESC, STATE_LOAD, STATE_TARGET_AREA, STATION_ROOMS,
    TRANSPORT_SEL, TRANSPORT_SEL_NONE, WARP_REQ)
from .ram import Tick

if TYPE_CHECKING:
    from . import MMZXClient


async def handle_warps(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Serve "Go to Transerver", then any teleport queued by it or by a command."""
    await serve_warp_request(client, ctx, tick.guard)
    if client.pending_teleport is not None:
        sub, x, y = client.pending_teleport
        client.pending_teleport = None
        await teleport(ctx, sub, x, y, tick.guard)


async def serve_warp_request(client: "MMZXClient", ctx, guard) -> None:
    """Open the game's Target Area list on request, then teleport to the pick.

    The request byte comes from the ROM's menu cave; the selection is read
    on the first tick back in gameplay (-1 = cancelled).
    """
    r = await bizhawk.read(ctx.bizhawk_ctx, [(WARP_REQ, 1, DOM), (TRANSPORT_SEL, 4, DOM)])
    req = r[0][0]
    sel = int.from_bytes(r[1], "little", signed=True)
    if client.transport_wait:
        client.transport_wait = False
        if 0 <= sel < len(STATION_ROOMS):
            room = STATION_ROOMS[sel]
            letter = room[0].upper()
            y = HUB_FLOOR_Y.get(letter)
            if y is not None:
                client.pending_teleport = (HUB_SUBAREA, HUB_X, y - HUB_PAD_DY)
                client._debug("[mmzx] Go to Transerver -> Area %s (hub floor %s)"
                              % (letter + "-" + room[1:].lstrip("0"), letter))
        else:
            client._debug("[mmzx] Go to Transerver: list cancelled")
        return
    if req != 1:
        return
    # open the game's list with no current station; retried if the guard fails
    ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, [
        (WARP_REQ, b"\x00", DOM),
        (TRANSPORT_SEL, TRANSPORT_SEL_NONE.to_bytes(4, "little"), DOM),
        (GAME_STATE, STATE_TARGET_AREA.to_bytes(4, "little"), DOM),
        (GAME_STATE + 4, b"\x00\x00\x00\x00", DOM),
        (GAME_STATE + 8, b"\x00\x00\x00\x00", DOM),
    ], [guard])
    if ok:
        client.transport_wait = True
        client._debug("[mmzx] Go to Transerver: opening the Target Area list")


async def teleport(ctx, sub: int, x: int, y: int, guard) -> None:
    """Request a scene load at (sub, x, y), guarded on gameplay."""
    writes = [
        (SCENE_DESC + DESC_SPAWN_X_OFF, (x << 8).to_bytes(4, "little"), DOM),
        (SCENE_DESC + DESC_SPAWN_Y_OFF, (y << 8).to_bytes(4, "little"), DOM),
        (SCENE_DESC + DESC_SUBAREA_OFF, sub.to_bytes(4, "little"), DOM),
        (SCENE_DESC + DESC_FACING_OFF, b"\x01", DOM),
        (GAME_STATE, STATE_LOAD.to_bytes(4, "little"), DOM),
        (GAME_STATE + 4, b"\x00\x00\x00\x00", DOM),
        (GAME_STATE + 8, b"\x00\x00\x00\x00", DOM),
    ]
    await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
