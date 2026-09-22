"""On-screen notices (the NOTIFY mailbox and the game's font) and the pickup state the game reads.

Scout requests live here too: the "Sent" notices need to know what each location holds.
"""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import NOTIFY_ADDR, NOTIFY_BUF_MAX, NOTIFY_POPUP_GLYPHS
from .addresses import (
    DISK_ITEM_ID, DOM, LOCATION_SLOTS, NOTIFY_BUF_OFF, NOTIFY_DUR, NOTIFY_DUR_OFF, NOTIFY_GREEN,
    NOTIFY_PAGE, NOTIFY_PUNCT, NOTIFY_QUEUE_MAX, NOTIFY_WHITE, PICKUP_CHECKED_REL, PICKUP_ICONS_OFF,
    PICKUP_STATE_ADDR, PICKUP_STATE_LEN)

if TYPE_CHECKING:
    from . import MMZXClient


def encode_text(text: str, terminate: bool = True) -> bytes:
    """Encode text in the game's font: ASCII minus 0x20, unknown glyphs as spaces."""
    out = bytearray()
    for ch in text:
        if ch == " ":
            out.append(0x00)
        elif "0" <= ch <= "9":
            out.append(0x10 + ord(ch) - 0x30)
        elif "A" <= ch <= "Z":
            out.append(0x21 + ord(ch) - 0x41)
        elif "a" <= ch <= "z":
            out.append(0x41 + ord(ch) - 0x61)
        elif ch in NOTIFY_PUNCT:
            out.append(NOTIFY_PUNCT[ch])
        else:
            out.append(0x00)
    if terminate:
        out.append(0xFE)
    return bytes(out)


def notify_pages(head: str, item: str, tail: str, n: int = NOTIFY_POPUP_GLYPHS) -> list[bytes]:
    """Split head, item (in green) and tail by words into pages of at most n glyphs.

    Each page carries its own color control; a word longer than a line is chopped.
    Returns the encoded pages without 0xFD or 0xFE.
    """
    # keep " from Alice" together so no page ends with a dangling "from"
    tail_words = [tail.strip()] if 0 < len(tail.strip()) <= n else tail.split()
    words = ([(w, False) for w in head.split()] + [(w, True) for w in item.split()]
             + [(w, False) for w in tail_words])
    pages: list[list[tuple[str, bool]]] = []
    line: list[tuple[str, bool]] = []
    used = 0
    for w, green in words:
        while len(w) > n:
            if line:
                pages.append(line)
                line, used = [], 0
            pages.append([(w[:n], green)])
            w = w[n:]
        need = len(w) + (1 if line else 0)
        if used + need > n:
            pages.append(line)
            line, used = [], 0
            need = len(w)
        line.append((w, green))
        used += need
    if line:
        pages.append(line)
    out = []
    for pg in pages:
        buf = bytearray()
        color = None
        for j, (w, green) in enumerate(pg):
            if j:
                buf.append(0x00)
            if green != color:
                buf += NOTIFY_GREEN if green else NOTIFY_WHITE
                color = green
            buf += encode_text(w, False)
        out.append(bytes(buf))
    return out


def notify_bytes(head: str, item: str, tail: str, style: str = "short") -> bytes:
    """Encode a notice in the given style.

    `short` keeps one popup line, dropping the tail and then trimming the item.
    `full` chains pages with 0xFD and drops trailing pages that overflow BUF.
    """
    n = NOTIFY_POPUP_GLYPHS
    if style == "full":
        pages = notify_pages(head, item, tail, n)
        while len(pages) > 1 and sum(len(p) + 1 for p in pages) > NOTIFY_BUF_MAX:
            pages.pop()
        return NOTIFY_PAGE.join(pages) + b"\xfe"
    if len(head) + len(item) + len(tail) > n:
        tail = ""
    if len(head) + len(item) > n:
        item = item[:max(0, n - len(head) - 1)] + "."
    data = (encode_text(head, False) + NOTIFY_GREEN + encode_text(item, False)
            + NOTIFY_WHITE + encode_text(tail, False) + b"\xfe")
    if len(data) > NOTIFY_BUF_MAX:
        data = data[:NOTIFY_BUF_MAX - 1] + b"\xfe"
    return data


def item_level(flags: int) -> int:
    """Level of an item for the notice threshold: 1 progression, 2 useful, 3 the rest."""
    if flags & 0b001:
        return 1
    if flags & 0b010:
        return 2
    return 3


async def sync_pickup_state(client: "MMZXClient", ctx) -> None:
    """Keep the icons switch and the `checked` bitmap of the pickup table equal to the server's view.

    Read back every tick and rewritten when they differ, since a reset zeroes
    them. A refill already sent looks and heals as vanilla again; disks, Life
    Ups and Sub Tanks never respawn, so the game keeps treating them as AP pickups.
    """
    want = bytearray(PICKUP_STATE_LEN)
    want[0] = 0 if client.icons_enabled else PICKUP_ICONS_OFF
    for loc in ctx.checked_locations:
        slot = LOCATION_SLOTS.get(loc)
        if slot is not None:
            want[PICKUP_CHECKED_REL + (slot >> 3)] |= 1 << (slot & 7)
    cur = (await bizhawk.read(ctx.bizhawk_ctx, [(PICKUP_STATE_ADDR, PICKUP_STATE_LEN, DOM)]))[0]
    if cur != bytes(want):
        await bizhawk.write(ctx.bizhawk_ctx, [(PICKUP_STATE_ADDR, bytes(want), DOM)])


def scout_requests(client: "MMZXClient", ctx) -> list:
    """LocationScouts (no hints) for the locations still missing their info, if any."""
    if client.notify_cfg["sent"] == 0:
        return []
    info = ctx.locations_info or {}
    if not info and client.scout_requested:
        client.scout_requested = set()        # the server cleared the info (reconnection)
    pending = set(ctx.missing_locations) - set(info) - client.scout_requested
    if not pending:
        return []
    client.scout_requested |= pending
    return [{"cmd": "LocationScouts", "locations": sorted(pending), "create_as_hint": 0}]


def queue_sent_notices(client: "MMZXClient", ctx, newly: set) -> None:
    """Queue "Sent <item> to <player>" for new checks holding another player's item."""
    lvl = client.notify_cfg["sent"]
    if lvl == 0:
        return
    infos = ctx.locations_info or {}
    for loc in sorted(newly):
        info = infos.get(loc)
        if info is None or info.player == ctx.slot or item_level(info.flags) > lvl:
            continue
        if len(client.notify_queue) >= NOTIFY_QUEUE_MAX:
            break
        try:
            item = ctx.item_names.lookup_in_slot(info.item, info.player)
        except Exception:
            item = str(info.item)
        who = ctx.player_names.get(info.player, str(info.player))
        client.notify_queue.append(notify_bytes("Sent ", item, " to " + who, client.notify_style))


async def push_notices(client: "MMZXClient", ctx) -> None:
    """Queue "Got" notices for new items and push one when the popup is free.

    The backlog present when connecting is not announced.
    """
    msgs = scout_requests(client, ctx)
    if msgs:
        await ctx.send_msgs(msgs)
    n = len(ctx.items_received)
    if client.notified_items is None:
        client.notified_items = n
    lvl = client.notify_cfg["received"]
    while client.notified_items < n:
        net = ctx.items_received[client.notified_items]
        client.notified_items += 1
        if lvl == 0 or item_level(net.flags) > lvl or len(client.notify_queue) >= NOTIFY_QUEUE_MAX:
            continue
        try:
            item = ctx.item_names.lookup_in_game(net.item)
        except Exception:
            item = str(net.item)
        tail = ""
        if net.item == DISK_ITEM_ID and client.goal.wants_disks:
            got = sum(1 for it in ctx.items_received[:client.notified_items] if it.item == DISK_ITEM_ID)
            tail = " (%d/%d)" % (got, client.goal.disks_required)
        if net.player != ctx.slot:
            tail += " from " + ctx.player_names.get(net.player, str(net.player))
        client.notify_queue.append(notify_bytes("Got ", item, tail, client.notify_style))
    if not client.notify_queue:
        return
    req = (await bizhawk.read(ctx.bizhawk_ctx, [(NOTIFY_ADDR, 1, DOM)]))[0][0]
    if req != 0:
        return                              # the previous notice is still on screen
    data = client.notify_queue.popleft()
    await bizhawk.write(ctx.bizhawk_ctx, [
        (NOTIFY_ADDR + NOTIFY_BUF_OFF, data, DOM),
        (NOTIFY_ADDR + NOTIFY_DUR_OFF, NOTIFY_DUR.to_bytes(2, "little"), DOM)])
    await bizhawk.write(ctx.bizhawk_ctx, [(NOTIFY_ADDR, b"\x01", DOM)])   # REQ last
