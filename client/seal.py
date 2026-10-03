"""The seal of Area M in game: kept closed until the biometal checks are done or the
Passwords collected, with its own scene saved for the moment it opens."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import EVENT_GATES, ITEMS, LOCATIONS, SEAL_GATE, SEAL_TRANSERVER
from ..seal import BIOMETAL_LOCATIONS, MODE_BIOMETALS, MODE_OPEN, MODE_PASSWORDS, PASSWORD_ITEM
from .addresses import (CUTSCENE_FLAG, DOM, STORY_BLOCK, STORY_BLOCK_CANON, STORY_BLOCK_LEN,
                        STORY_HANDLER_ID, STORY_HANDLER_STATE)
from .ram import ProgressWindow, Tick

if TYPE_CHECKING:
    from . import MMZXClient


def _bit(pair) -> tuple[int, int]:
    return int(pair[0]), int(pair[1])


GATE_BIT = _bit(EVENT_GATES[SEAL_GATE])
# Held down while the seal is closed: its gate and the Transport destination of the rooms past it
CLOSED_BITS = frozenset({GATE_BIT, _bit(ITEMS[SEAL_TRANSERVER]["grant"][1:])})
# What `biometals` counts, by biometal letter: its location and the flags that detect it
BIOMETAL_CHECKS = {name[-1]: (LOCATIONS[name]["id"], [_bit(b) for b in LOCATIONS[name]["detect"][1]])
                   for name in BIOMETAL_LOCATIONS}
PASSWORD_ITEM_ID = ITEMS[PASSWORD_ITEM]["id"]
# The seal's scene belongs to the story handler of Stop The Dig: it waits for the player
# in front of the seal, plays the scene and opens the seal; past the scene it does nothing.
SCENE_HANDLER_ID = 14
SCENE_HANDLER_WAIT = 0
SCENE_HANDLER_DONE = 5
OPEN_NOTICE = ("Area M: ", "seal open", "")


class Seal:
    """The option resolved by the generator, read from slot_data, and the progress towards it."""

    def __init__(self, slot_data: dict) -> None:
        s = slot_data.get("area_m_access") or {}      # a seed from before the option: open
        mode = s.get("mode")
        self.mode = mode if mode in (MODE_BIOMETALS, MODE_PASSWORDS) else MODE_OPEN
        self.passwords_required = int(s.get("passwords", 0))
        self.passwords_total = int(s.get("passwords_total", 0))
        self.obtained: set[str] | None = None   # biometal checks done; None until the flags are read
        self.rearm = False                    # the seal just opened: its scene is due

    @property
    def gated(self) -> bool:
        return self.mode != MODE_OPEN

    def read_biometals(self, window: ProgressWindow, checked: set[int]) -> None:
        """A biometal counts with its check detected in the game or already on the server."""
        self.obtained = {letter for letter, (loc, bits) in BIOMETAL_CHECKS.items()
                         if loc in checked or window.any_set(bits)}

    def progress(self, counts: dict[str, int]) -> tuple[int, int]:
        """(done, needed) of what the seal counts."""
        if self.mode == MODE_PASSWORDS:
            return counts.get(PASSWORD_ITEM, 0), self.passwords_required
        return len(self.obtained or ()), len(BIOMETAL_CHECKS)

    def is_open(self, counts: dict[str, int]) -> bool:
        if not self.gated:
            return True
        done, needed = self.progress(counts)
        return done >= needed

    def closed_bits(self, counts: dict[str, int]) -> frozenset:
        """The progress bits to keep down: none once the seal is open."""
        return frozenset() if self.is_open(counts) else CLOSED_BITS

    def report(self, counts: dict[str, int]) -> list[str]:
        """Lines for the console."""
        if not self.gated:
            return []
        state = "open" if self.is_open(counts) else "closed"
        done, needed = self.progress(counts)
        if self.mode == MODE_PASSWORDS:
            return ["Area M seal: %d of %d Passwords received (%d in the multiworld): %s"
                    % (done, needed, self.passwords_total, state)]
        if self.obtained is None:
            return ["Area M seal: the five Obtain Biometal checks (progress is read in game)"]
        missing = [letter for letter in BIOMETAL_CHECKS if letter not in self.obtained]
        return ["Area M seal: %d of %d Obtain Biometal checks done (missing: %s): %s"
                % (done, needed, ", ".join(missing) or "none", state)]


async def track_biometals(client: "MMZXClient", ctx, window: ProgressWindow) -> None:
    """Refresh which biometal checks the seal counts, before the items stage reads them."""
    client.seal.read_biometals(window, ctx.checked_locations)


async def hold_seal_scene(client: "MMZXClient", ctx, tick: Tick, counts: dict[str, int]) -> None:
    """Keep the seal's scene for the moment the seal opens.

    The story handler of Stop The Dig plays it in front of the seal and opens the seal
    by itself. While the seal is closed the handler is parked past the scene; when the
    seal opens it goes back to waiting, so the scene still plays.
    """
    seal = client.seal
    closed = not seal.is_open(counts)
    if not closed and not seal.rearm:
        return
    r = await bizhawk.read(ctx.bizhawk_ctx, [
        (STORY_HANDLER_ID, 4, DOM), (STORY_HANDLER_STATE, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
    if r[2][0] & 1:
        return
    has, want = SCENE_HANDLER_WAIT, SCENE_HANDLER_DONE
    if not closed:
        has, want = want, has
    if int.from_bytes(r[0], "little") != SCENE_HANDLER_ID or r[1][0] != has:
        seal.rearm = False     # nothing parked: a later accept starts the handler waiting
        return
    write = [(STORY_HANDLER_STATE, bytes([want]), DOM)]
    if not await bizhawk.guarded_write(ctx.bizhawk_ctx, write, [tick.guard]):
        return
    seal.rearm = False
    # the checkpoint copy too, or a death would bring the old state back
    story = (await bizhawk.read(ctx.bizhawk_ctx, [(STORY_BLOCK, STORY_BLOCK_LEN, DOM)]))[0]
    await bizhawk.guarded_write(ctx.bizhawk_ctx, [(STORY_BLOCK_CANON, story, DOM)], [tick.guard])
    client._debug("[mmzx] Area M seal %s: its scene is %s (story handler %d -> %d)"
                  % ("closed" if closed else "open", "held back" if closed else "armed", has, want))
