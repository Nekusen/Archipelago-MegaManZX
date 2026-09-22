"""The goal requirements in game: the gate to the final area, the disks' database entries,
the progress lines of the pause menu and the /mmzx_goal report."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import EVENT_GATES, EVENT_GATES_GOAL, GOAL_LINE_ADDR, GOAL_LINE_GLYPHS, SECRET_DISK_ENTRIES
from ..goal import COUNTED_MISSIONS, MISSION_PREFIX
from ..rom.ui import GOAL_LINE_BUF_LEN, PAUSE_TEXT_LINE_BREAK
from .addresses import DISK_ITEM, DOM, SIX_MODELS
from .notices import encode_text
from .ram import ProgressWindow, Tick, mission_done_bits

if TYPE_CHECKING:
    from . import MMZXClient

PART_GAP = "  "     # between two requirements sharing a line


def mission_label(name: str) -> str:
    return name[len(MISSION_PREFIX):]


def missions_completed(window: ProgressWindow) -> set[str]:
    """The counted missions whose completed bits are all set, by their short name."""
    done = set()
    for name in COUNTED_MISSIONS:
        label = mission_label(name)
        bits = mission_done_bits(label)
        if bits and window.all_set(bits):
            done.add(label)
    return done


class GoalRequirement:
    """The requirement resolved by the generator, read from slot_data."""

    def __init__(self, slot_data: dict) -> None:
        g = slot_data.get("goal_requirements")
        if g is None:      # a seed from before the option: the six models
            g = {"models": list(SIX_MODELS), "models_count": len(SIX_MODELS)}
        self.models = tuple(str(m) for m in g.get("models", ()))
        copies = [int(c) for c in g.get("models_copies", ())]
        self.copies = {m: copies[i] if i < len(copies) else 1 for i, m in enumerate(self.models)}
        self.models_count = min(int(g.get("models_count", len(self.models))), len(self.models))
        self.disks_required = int(g.get("secret_disks", 0))
        self.disks_total = int(g.get("secret_disks_total", 0))
        order = [int(i) for i in g.get("secret_disk_order", ())]
        n = len(SECRET_DISK_ENTRIES)
        self.disk_order = order if sorted(order) == list(range(n)) else list(range(n))
        self.missions_required = int(g.get("missions", 0))

    @property
    def wants_models(self) -> bool:
        return bool(self.models)

    @property
    def wants_disks(self) -> bool:
        return self.disks_required > 0

    @property
    def wants_missions(self) -> bool:
        return self.missions_required > 0

    def models_owned(self, counts: dict[str, int]) -> int:
        return sum(1 for m in self.models if counts.get(m, 0) >= self.copies.get(m, 1))

    def disks_owned(self, counts: dict[str, int]) -> int:
        return counts.get(DISK_ITEM, 0)

    def met(self, counts: dict[str, int], missions: int) -> bool:
        return ((not self.wants_models or self.models_owned(counts) >= self.models_count)
                and (not self.wants_disks or self.disks_owned(counts) >= self.disks_required)
                and (not self.wants_missions or missions >= self.missions_required))

    def gate_bits(self) -> set[tuple[int, int]]:
        """The two flags of the Slither gate, D-2 to D-4."""
        return {tuple(EVENT_GATES[fl]) for fl in EVENT_GATES_GOAL}

    def disk_bits(self, counts: dict[str, int]) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
        """(entries to light, every entry): the first disks received, in the seed's order."""
        n = min(self.disks_owned(counts), len(SECRET_DISK_ENTRIES))
        wanted = {tuple(SECRET_DISK_ENTRIES[i]) for i in self.disk_order[:n]}
        return wanted, {tuple(e) for e in SECRET_DISK_ENTRIES}

    def progress_lines(self, counts: dict[str, int], missions: int) -> tuple[str, str]:
        """(first line, second line) of the pause menu, each at most GOAL_LINE_GLYPHS glyphs.

        Requirements share a line while they fit. A blank first line keeps the vanilla help.
        """
        parts = []
        if self.wants_disks:
            width = len(str(self.disks_required))
            label = "Disks" if (self.wants_models or self.wants_missions) else "Secret Disks"
            parts.append("%s %0*d/%d" % (label, width, self.disks_owned(counts), self.disks_required))
        if self.wants_models:
            parts.append("Models %d/%d" % (self.models_owned(counts), self.models_count))
        if self.wants_missions:
            width = len(str(self.missions_required))
            parts.append("Missions %0*d/%d" % (width, missions, self.missions_required))
        lines: list[str] = []
        for part in parts:
            if lines and len(lines[-1]) + len(PART_GAP) + len(part) <= GOAL_LINE_GLYPHS:
                lines[-1] += PART_GAP + part
            else:
                lines.append(part)
        if len(lines) <= 1:
            return "", (lines[0] if lines else "")[:GOAL_LINE_GLYPHS]
        return lines[0][:GOAL_LINE_GLYPHS], lines[1][:GOAL_LINE_GLYPHS]

    def report(self, counts: dict[str, int], cleared: set[str] | None) -> list[str]:
        """Lines for the console; `cleared` is None until the game's flags have been read."""
        out = []
        if self.wants_disks:
            out.append("Secret Disks: %d of %d received (%d in the multiworld)"
                       % (self.disks_owned(counts), self.disks_required, self.disks_total))
        if self.wants_models:
            def label(m):
                return m + (" (full)" if self.copies.get(m, 1) > 1 else "")
            have = [label(m) for m in self.models if counts.get(m, 0) >= self.copies.get(m, 1)]
            miss = [label(m) for m in self.models if counts.get(m, 0) < self.copies.get(m, 1)]
            out.append("Models: %d of %d owned (have: %s; missing: %s)" % (
                len(have), self.models_count, ", ".join(have) or "none", ", ".join(miss) or "none"))
        if self.wants_missions:
            if cleared is None:
                out.append("Missions: %d of the %d story missions required (progress is read in game)"
                           % (self.missions_required, len(COUNTED_MISSIONS)))
            else:
                miss = [mission_label(m) for m in COUNTED_MISSIONS if mission_label(m) not in cleared]
                out.append("Missions: %d of %d completed (missing: %s)" % (
                    len(cleared), self.missions_required, ", ".join(miss) or "none"))
        if not out:
            out.append("No goal requirement: the gate to the final area is open")
        else:
            gate = self.met(counts, len(cleared) if cleared is not None else 0)
            out.append("Gate to the final area: %s" % ("open" if gate else "closed"))
        return out


def goal_line_bytes(first: str, second: str) -> bytes:
    """The buffer in the message layout: two padded lines with the break between them.

    Without a first line the break is left out, and the cave keeps the vanilla help.
    """
    def line(text: str) -> bytes:
        enc = encode_text(text, terminate=False)[:GOAL_LINE_GLYPHS]
        return enc + bytes(GOAL_LINE_GLYPHS - len(enc))
    sep = bytes([PAUSE_TEXT_LINE_BREAK]) if first else b"\x00"
    data = line(first) + sep + line(second)
    assert len(data) == GOAL_LINE_BUF_LEN
    return data


async def sync_goal_line(client: "MMZXClient", ctx, tick: Tick, counts: dict[str, int]) -> None:
    """Keep the pause menu lines equal to the progress; written only when they change."""
    first, second = client.goal.progress_lines(counts, len(client.missions_cleared or ()))
    data = goal_line_bytes(first, second)
    if data == client.goal_line_written:
        return
    if await bizhawk.guarded_write(ctx.bizhawk_ctx, [(GOAL_LINE_ADDR, data, DOM)], [tick.guard]):
        client.goal_line_written = data
