"""Mission objectives: the story items held, what one of them does to its area, and the
terminal of F-3 reachable from any entrance."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import MISSION_STATE_ADDR
from .addresses import (
    AREA_OF_SUBAREA, CUTSCENE_FLAG, DOM, MISSION_ACCEPTED_MASK, MISSION_ACTIVE_BYTE, STORY_ADDR,
    STORY_AREA_FLAGS, STORY_BLOCK, STORY_BLOCK_CANON, STORY_BLOCK_LEN, STORY_HANDLER_ID, STORY_HANDLER_STATE,
    STORY_ITEM_BITS, STORY_LEN, SURVIVORS_HANDLER_ID, SURVIVORS_HANDLER_TERMINAL, SURVIVORS_HANDLER_WAITS,
    SURVIVORS_STATE, SURVIVORS_SUBAREA)
from .items import received_counts
from .ram import Tick, bits_by_byte, copies_writes, read_copies, story_handler_writes

if TYPE_CHECKING:
    from . import MMZXClient

MODE_OFF, MODE_CHECKS, MODE_ITEMS = "off", "checks", "items"


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
    want = story_held(received_counts(ctx))
    held = (await bizhawk.read(ctx.bizhawk_ctx, [(STORY_ADDR, STORY_LEN, DOM)]))[0]
    if held != want:
        await bizhawk.guarded_write(ctx.bizhawk_ctx, [(STORY_ADDR, want, DOM)], [tick.guard])


async def hold_area_flags(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Keep set the area flags of the items held, while the player is in their area.

    The game clears them on every change of area, as it did after the event
    each of these items stands in for.
    """
    area = AREA_OF_SUBAREA.get(tick.subarea, "")
    counts = received_counts(ctx)
    bits = [bit for item, (letter, flags) in STORY_AREA_FLAGS.items()
            if letter == area and counts.get(item, 0) for bit in flags]
    if not bits:
        return
    masks = bits_by_byte(bits)
    addrs = list(masks)
    live, canon = await read_copies(ctx, addrs)
    writes = copies_writes(addrs, live, canon, set_masks=masks)
    if writes:
        await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard])


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
