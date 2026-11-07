"""ITEM A usables: held while their item is received, refilled at every console."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from .addresses import (
    CONSOLE_CLASS, DOM, ENTITY_CLASS_OFF, ENTITY_HITBOX_OFF, INTERACT_HITBOX_PTR, PLAYER_STATE_CONSOLE,
    USABLES_ADDR, USABLES_MARK_VALUE, USABLE_BITS)
from .items import received_counts
from .ram import Tick

if TYPE_CHECKING:
    from . import MMZXClient


def usables_owned(counts: dict[str, int]) -> int:
    """Possession byte the received items call for."""
    owned = 0
    for name, bit in USABLE_BITS.items():
        if counts.get(name, 0):
            owned |= 1 << bit
    return owned


async def at_console(ctx, tick: Tick) -> bool:
    """The player is using a console: the interaction state, targeting a console entity."""
    if tick.player_state != PLAYER_STATE_CONSOLE:
        return False
    hitbox = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(INTERACT_HITBOX_PTR, 4, DOM)]))[0], "little")
    if not hitbox:
        return False
    cls = (await bizhawk.read(ctx.bizhawk_ctx, [(hitbox - ENTITY_HITBOX_OFF + ENTITY_CLASS_OFF, 1, DOM)]))[0][0]
    return cls == CONSOLE_CLASS


async def sync_usables(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Keep the usables held in step with the items received; refill the used ones at a console.

    The menu clears a usable's bit when the player uses it. Opening a console sets
    every held bit again; a boot (the mark byte is clear) and a newly received item
    set theirs. A bit without its item is cleared.
    """
    owned = usables_owned(received_counts(ctx))
    held, mark = (await bizhawk.read(ctx.bizhawk_ctx, [(USABLES_ADDR, 2, DOM)]))[0]
    console = await at_console(ctx, tick)
    refill = console and not client.console_busy
    client.console_busy = console
    if mark != USABLES_MARK_VALUE or refill:
        want = owned
    else:
        want = (held & owned) | (owned & ~client.usables_granted)
    client.usables_granted = owned
    if want == held and mark == USABLES_MARK_VALUE:
        return
    ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, [(USABLES_ADDR, bytes([want, USABLES_MARK_VALUE]), DOM)],
                                     [tick.guard])
    if ok and refill and want != held:
        client._debug("[mmzx] usables refilled at the console")
