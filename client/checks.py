"""Check detection: progress-block flags, the refills the game recorded and the goal."""

from time import monotonic
from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk
from NetUtils import ClientStatus

from ..data import GOAL_BITS, GOAL_BITS_SERPENT, LOCATIONS
from ..rom.table import BITMAP_LEN
from .addresses import (
    DISK_TAKEN_BITS, DOM, PICKUP_COLLECTED_ADDR, REFILL_SLOTS, RESEND_SECONDS, SLOT_LOCATIONS)
from .ram import ProgressWindow, Tick, bits_by_byte, copies_writes, read_copies
from .notices import queue_sent_notices

if TYPE_CHECKING:
    from . import MMZXClient


async def detect_checks(client: "MMZXClient", ctx, window: ProgressWindow) -> None:
    """Send the locations whose detect recipe holds, plus the refills the game recorded.

    The flags and the game's bitmap are the source of truth, so a reload or a
    reconnect produces the same set. Whatever the server has not confirmed yet
    is sent again every few seconds: a send can be lost while the connection drops.
    """
    detected = set()
    for v in LOCATIONS.values():
        det = v.get("detect")
        if not det:
            continue
        if det[0] == "bit":
            ok = window.bit(det[1], det[2])
        elif det[0] == "all":   # mission completed
            ok = window.all_set(det[1])
        elif det[0] == "any":   # biometal: either boss of the pair
            ok = window.any_set(det[1])
        else:
            continue
        if ok and v["id"] in ctx.server_locations:
            detected.add(v["id"])
    if client.mailbox_enabled:
        detected |= await collected_refills(client, ctx)
    pending = detected - ctx.checked_locations
    if not pending:
        return
    now = monotonic()
    if pending == client.pending_sent and now - client.pending_sent_at < RESEND_SECONDS:
        return
    await ctx.check_locations(list(detected))
    client.pending_sent, client.pending_sent_at = pending, now
    new = pending - client.announced
    if new:
        queue_sent_notices(client, ctx, new)
        client.announced |= new


async def sync_taken_disks(client: "MMZXClient", ctx, window: ProgressWindow, tick: Tick) -> None:
    """Mark as taken the disks the server already has checked, so they leave the world.

    Covers a collect from the server and a save from before the disks became items.
    """
    bits = [DISK_TAKEN_BITS[loc] for loc in ctx.checked_locations
            if loc in DISK_TAKEN_BITS and not window.bit(*DISK_TAKEN_BITS[loc])]
    if not bits:
        return
    masks = bits_by_byte(bits)
    addrs = sorted(masks)
    live, canon = await read_copies(ctx, addrs)
    writes = copies_writes(addrs, live, canon, set_masks=masks)
    if writes:
        await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard])


async def collected_refills(client: "MMZXClient", ctx) -> set[int]:
    """Locations of the refills the game marked in its `collected` bitmap.

    The bitmap lives in RAM and only grows until a reset zeroes it; a refill
    taken again after that is simply seen again.
    """
    raw = (await bizhawk.read(ctx.bizhawk_ctx, [(PICKUP_COLLECTED_ADDR, BITMAP_LEN, DOM)]))[0]
    found = {SLOT_LOCATIONS[slot] for slot in REFILL_SLOTS if raw[slot >> 3] & (1 << (slot & 7))}
    found &= ctx.server_locations
    new = found - client.collected_seen
    if new:
        client.collected_seen |= new
        names = []
        for i in sorted(new):
            try:
                names.append(ctx.location_names.lookup_in_game(i))
            except Exception:
                names.append(str(i))
        client._debug("[mmzx] pickup collected: %s" % ", ".join(names))
    return found


async def report_goal(ctx, window: ProgressWindow) -> None:
    """Send the goal once Serpent is beaten: the epilogue event or both D-5 Serpent bits."""
    if ctx.finished_game:
        return
    if window.all_set(GOAL_BITS) or window.all_set(GOAL_BITS_SERPENT):
        ctx.finished_game = True
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
