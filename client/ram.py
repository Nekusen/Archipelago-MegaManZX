"""Helpers over the game's RAM: the per-tick snapshot, the progress-block window
and the live-plus-canonical writes of progress bits.
"""

import worlds._bizhawk as bizhawk

from ..data import LOCATIONS
from .addresses import (
    CANON_OFF, CUTSCENE_NONE, DEATH_STATE, DEATH_SUBSTATE, DETECT_FAR, DETECT_WINDOW, DOM,
    GAME_STATE, HP, MSG_BANK, PLAYER_OBJ, PLAYER_STATE_OFF, SCRIPT_CUTSCENE_OFF,
    SCRIPT_STATE_OFF, STATE_INGAME, STORY_HANDLER_ID, STORY_HANDLER_LEN, STORY_HANDLER_OBJ,
    SUBAREA_STABLE, TITLE_CAROUSEL_STEP, TITLE_STEP_LAUNCHED)


def decode_position(raw: bytes) -> tuple[int, int]:
    """Pixel (x, y) from the two 8.8 fixed-point words of PLAYER_POS."""
    return int.from_bytes(raw[0:4], "little") >> 8, int.from_bytes(raw[4:8], "little") >> 8


def bits_by_byte(bits) -> dict[int, int]:
    """Group (address, bit) pairs into one mask per address, in first-seen order."""
    masks: dict[int, int] = {}
    for addr, bit in bits:
        masks[addr] = masks.get(addr, 0) | (1 << bit)
    return masks


def copies_reads(addrs) -> list[tuple[int, int, str]]:
    """Read list for the live byte of each address followed by its canonical copy."""
    return [(a, 1, DOM) for a in addrs] + [(a + CANON_OFF, 1, DOM) for a in addrs]


def copies_values(addrs, reads, start: int = 0) -> tuple[dict[int, int], dict[int, int]]:
    """Split the result of copies_reads (at `start` in a larger batch) into live and canonical bytes."""
    n = len(addrs)
    live = {a: reads[start + i][0] for i, a in enumerate(addrs)}
    canon = {a: reads[start + n + i][0] for i, a in enumerate(addrs)}
    return live, canon


async def read_copies(ctx, addrs) -> tuple[dict[int, int], dict[int, int]]:
    """Live and canonical bytes of some progress-block addresses."""
    return copies_values(addrs, await bizhawk.read(ctx.bizhawk_ctx, copies_reads(addrs)))


def copies_writes(addrs, live: dict[int, int], canon: dict[int, int],
                  set_masks: dict[int, int] | None = None,
                  clear_masks: dict[int, int] | None = None) -> list[tuple[int, bytes, str]]:
    """Writes that set and clear the masks in both copies, one per byte that changes.

    Every bit of one byte is composed before writing, so several bits of the same
    address never overwrite each other inside one batch. Live before canonical.
    """
    writes: list[tuple[int, bytes, str]] = []
    for a in addrs:
        on = (set_masks or {}).get(a, 0)
        off = (clear_masks or {}).get(a, 0)
        for offset, cur in ((0, live[a]), (CANON_OFF, canon[a])):
            new = (cur | on) & ~off & 0xFF
            if new != cur:
                writes.append((a + offset, bytes([new]), DOM))
    return writes


def missing_bits(addrs, live: dict[int, int], canon: dict[int, int], masks: dict[int, int]) -> int:
    """How many of the wanted bits are clear, counting both copies."""
    return sum(bin(masks[a] & ~live[a] & 0xFF).count("1") + bin(masks[a] & ~canon[a] & 0xFF).count("1")
               for a in addrs)


class ProgressWindow:
    """One read of the progress-block window plus the far detect bytes, queried by bit."""

    def __init__(self, block: bytes, far: dict[int, int]) -> None:
        self.block = block
        self.far = far

    @classmethod
    async def read(cls, ctx) -> "ProgressWindow":
        lo, hi = DETECT_WINDOW
        r = await bizhawk.read(ctx.bizhawk_ctx, [(lo, hi - lo, DOM)] + [(a, 1, DOM) for a in DETECT_FAR])
        return cls(r[0], {a: r[1 + i][0] for i, a in enumerate(DETECT_FAR)})

    def bit(self, addr: int, bit: int) -> bool:
        lo, hi = DETECT_WINDOW
        if lo <= addr < hi:
            return bool(self.block[addr - lo] & (1 << bit))
        if addr in self.far:
            return bool(self.far[addr] & (1 << bit))
        return False

    def all_set(self, bits) -> bool:
        return all(self.bit(a, b) for a, b in bits)

    def any_set(self, bits) -> bool:
        return any(self.bit(a, b) for a, b in bits)


class Tick:
    """The signals every stage checks first, read once per tick."""

    READS = [(SUBAREA_STABLE, 1, DOM), (HP, 1, DOM), (GAME_STATE, 4, DOM),
             (TITLE_CAROUSEL_STEP, 1, DOM), (MSG_BANK, 4, DOM), (PLAYER_OBJ + PLAYER_STATE_OFF, 2, DOM)]

    def __init__(self, r) -> None:
        self.subarea: int = r[0][0]
        self.hp: int = r[1][0]
        self.state_bytes: bytes = r[2]
        self.title_step: int = r[3][0]
        self.msg_bank: bytes = r[4]
        self.player_state: int = r[5][0]      # 0 = the player has control
        self.player_substate: int = r[5][1]
        # every gameplay write is guarded on the state word: a scene load drops it
        self.guard = (GAME_STATE, self.state_bytes, DOM)

    @property
    def launched(self) -> bool:
        """A game is running (the title and its menus share the other signals)."""
        return self.title_step == TITLE_STEP_LAUNCHED and self.subarea != 0

    @property
    def in_game(self) -> bool:
        return self.launched and self.hp > 0 and int.from_bytes(self.state_bytes, "little") == STATE_INGAME

    @property
    def dead(self) -> bool:
        """The player is dead or dying: no HP, or the death animation is running."""
        return self.launched and (self.hp == 0 or (self.player_state == DEATH_STATE
                                                   and self.player_substate == DEATH_SUBSTATE))


def mission_done_bits(name: str) -> list[tuple[int, int]]:
    """'Completed' bits of a mission (detect 'all' of its location)."""
    det = (LOCATIONS.get("Mission - " + name) or {}).get("detect")
    if det and det[0] == "all":
        return [(a, b) for a, b in det[1]]
    return []


async def mission_completed(ctx, name: str) -> bool:
    """Whether every 'completed' bit of the mission is set (False for missions without them)."""
    done = mission_done_bits(name)
    if not done:
        return False
    vals = await bizhawk.read(ctx.bizhawk_ctx, [(a, 1, DOM) for a, _ in done])
    return all(vals[i][0] & (1 << b) for i, (_, b) in enumerate(done))


def story_handler_writes(mission_id: int, state: int) -> list[tuple[int, bytes, str]]:
    """A zeroed story handler with no pending cutscene at the given state, plus its mission id."""
    obj = bytearray(STORY_HANDLER_LEN)
    obj[SCRIPT_CUTSCENE_OFF] = CUTSCENE_NONE
    obj[SCRIPT_STATE_OFF] = state
    return [(STORY_HANDLER_OBJ, bytes(obj), DOM),
            (STORY_HANDLER_ID, mission_id.to_bytes(4, "little"), DOM)]
