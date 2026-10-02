"""Mission objectives: the story items held, and the terminal of F-3 reachable from any entrance."""

import logging
from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import MISSION_ACCEPT, MISSION_STATE_ADDR, STORY_REPORT_STATES
from .addresses import (
    CUTSCENE_FLAG, DOM, MISSION_ACCEPTED_MASK, MISSION_ACTIVE_BYTE, STORY_ADDR, STORY_BLOCK,
    STORY_BLOCK_CANON, STORY_BLOCK_LEN, STORY_HANDLER_ID, STORY_HANDLER_STATE, STORY_ITEM_BITS, STORY_LEN,
    SURVIVORS_HANDLER_ID, SURVIVORS_HANDLER_TERMINAL, SURVIVORS_HANDLER_WAITS, SURVIVORS_STATE,
    SURVIVORS_SUBAREA)
from .items import received_counts
from .notices import notify_bytes
from .ram import Tick, story_handler_writes

if TYPE_CHECKING:
    from . import MMZXClient

logger = logging.getLogger("Client")

MODE_OFF, MODE_CHECKS, MODE_ITEMS = "off", "checks", "items"
REPORT_NOTICE_HEAD = "Report needs "


def parse_mode(value) -> str:
    """The mission_objectives option as the client sees it; a seed without it has it off."""
    return value if value in (MODE_CHECKS, MODE_ITEMS) else MODE_OFF


def story_held(counts: dict[str, int]) -> bytes:
    """The possession bytes the received items call for: one bit per copy."""
    held = bytearray(STORY_LEN)
    for name, (byte, bits) in STORY_ITEM_BITS.items():
        for bit in bits[:counts.get(name, 0)]:
            held[byte] |= 1 << bit
    return bytes(held)


async def sync_story(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Keep the story items the ROM reads equal to the items received."""
    counts = received_counts(ctx)
    want = story_held(counts)
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (STORY_ADDR, STORY_LEN, DOM), (MISSION_STATE_ADDR, 4, DOM), (MISSION_ACTIVE_BYTE, 1, DOM)])
    if r[0] != want:
        await bizhawk.guarded_write(ctx.bizhawk_ctx, [(STORY_ADDR, want, DOM)], [tick.guard])
    state = int.from_bytes(r[1], "little") if r[2][0] & MISSION_ACCEPTED_MASK else None
    announce_report_item(client, state, counts)


def announce_report_item(client: "MMZXClient", state: int | None, counts: dict[str, int]) -> None:
    """Tell the player, once per mission, which object its Report is waiting for."""
    item = STORY_REPORT_STATES.get(state)
    if not item or counts.get(item, 0):
        client.story_waiting = None
        return
    if client.story_waiting == state:
        return
    client.story_waiting = state
    name = next((v["name"] for v in MISSION_ACCEPT.values() if v["state"] == state), "The mission")
    logger.info("[mmzx] %s can be reported once you have %s" % (name, item))
    client.notify_queue.append(notify_bytes(REPORT_NOTICE_HEAD, item, "", client.notify_style))


async def survivors_unstick(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Arm the terminal of F-3 while Find The Survivors is under way.

    Its story handler only gets there through the entrance scenes of F-1 and F-3,
    in that order; arriving any other way it would wait for them forever.
    """
    if tick.subarea != SURVIVORS_SUBAREA:
        return
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (MISSION_STATE_ADDR, 4, DOM), (STORY_HANDLER_ID, 4, DOM), (STORY_HANDLER_STATE, 1, DOM),
        (CUTSCENE_FLAG, 1, DOM), (MISSION_ACTIVE_BYTE, 1, DOM)])
    if (int.from_bytes(r[0], "little") != SURVIVORS_STATE or not r[4][0] & MISSION_ACCEPTED_MASK
            or int.from_bytes(r[1], "little") != SURVIVORS_HANDLER_ID or r[3][0] & 1):
        return
    state = r[2][0]
    if state not in SURVIVORS_HANDLER_WAITS:
        return
    writes = story_handler_writes(SURVIVORS_HANDLER_ID, SURVIVORS_HANDLER_TERMINAL)
    if not await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        return
    story = (await bizhawk.read(ctx.bizhawk_ctx, [(STORY_BLOCK, STORY_BLOCK_LEN, DOM)]))[0]
    await bizhawk.guarded_write(ctx.bizhawk_ctx, [(STORY_BLOCK_CANON, story, DOM)], [tick.guard])
    client._debug("[mmzx] Find The Survivors: the terminal of F-3 is armed (story handler %d -> %d)"
                  % (state, SURVIVORS_HANDLER_TERMINAL))
