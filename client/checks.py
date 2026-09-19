"""Check detection: progress-block flags, the pickup mailbox and the goal."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk
from NetUtils import ClientStatus

from ..data import (
    GOAL_BITS, GOAL_BITS_SERPENT, LOCATIONS, PICKUP_MAILBOX_ADDR, PICKUP_MAILBOX_SLOTS)
from .addresses import DISK_TAKEN_BITS, DOM, MAILBOX_LOCATIONS
from .ram import ProgressWindow, Tick, bits_by_byte, copies_writes, read_copies
from .notices import queue_sent_notices

if TYPE_CHECKING:
    from . import MMZXClient


async def detect_checks(client: "MMZXClient", ctx, window: ProgressWindow) -> None:
    """Send the locations whose detect recipe holds, plus the pickups of the mailbox.

    The checked set only grows and is re-sent whole when it does; the flags are
    the source of truth, so a reload produces the same set again.
    """
    checked = set()
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
            checked.add(v["id"])
    if client.mailbox_enabled:
        await poll_pickup_mailbox(client, ctx)
    checked |= client.mailbox_checked
    if checked == client.local_checked:
        return
    newly = checked - client.local_checked
    if newly:
        await ctx.check_locations(list(checked))
        queue_sent_notices(client, ctx, newly)
    client.local_checked = checked


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


async def poll_pickup_mailbox(client: "MMZXClient", ctx) -> None:
    """Turn new pickup mailbox entries into checks; repeats do nothing.

    The mailbox lives in RAM: when the counter went backwards (emulator
    reset) or on the first read, only the last ring of entries is processed.
    """
    raw = (await bizhawk.read(ctx.bizhawk_ctx, [
        (PICKUP_MAILBOX_ADDR, 4 + 4 * PICKUP_MAILBOX_SLOTS, DOM)]))[0]
    count = int.from_bytes(raw[:4], "little")
    if client.mailbox_count is None or count < client.mailbox_count:
        start = max(0, count - PICKUP_MAILBOX_SLOTS)      # re-sync
    else:
        start = max(client.mailbox_count, count - PICKUP_MAILBOX_SLOTS)
    new_ids = []
    for k in range(start, count):
        off = 4 + 4 * (k % PICKUP_MAILBOX_SLOTS)
        loc_id = MAILBOX_LOCATIONS.get((raw[off], raw[off + 1]))
        if loc_id is None or loc_id not in ctx.server_locations or loc_id in client.mailbox_checked:
            continue
        client.mailbox_checked.add(loc_id)
        new_ids.append(loc_id)
    client.mailbox_count = count
    if new_ids:
        names = []
        for i in new_ids:
            try:
                names.append(ctx.location_names.lookup_in_game(i))
            except Exception:
                names.append(str(i))
        client._debug("[mmzx] pickup collected: %s" % ", ".join(names))


async def report_goal(ctx, window: ProgressWindow) -> None:
    """Send the goal once Serpent is beaten: the epilogue event or both D-5 Serpent bits."""
    if ctx.finished_game:
        return
    if window.all_set(GOAL_BITS) or window.all_set(GOAL_BITS_SERPENT):
        ctx.finished_game = True
        await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
