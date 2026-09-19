"""The goal requirements: what the options ask for, as a rule and as data for the client."""

import logging

from Options import OptionError

from .data import SECRET_DISK_ENTRIES

REQ_BIOMETALS = "Biometals"
REQ_DISKS = "Secret Disks"
DISK_ITEM = "Secret Disk"
# Option keys to item names, in the order the counter and the spoiler list them.
MODEL_ITEM_BY_KEY = {
    "Model X": "Model X", "Model ZX": "Model ZX",
    "Model HX": "Progressive Model HX", "Model FX": "Progressive Model FX",
    "Model LX": "Progressive Model LX", "Model PX": "Progressive Model PX",
    "Model OX": "Model OX",
}
SIX_MODEL_KEYS = tuple(list(MODEL_ITEM_BY_KEY)[:6])
# Up to this many disks in the pool, finding one on a priority location is welcome.
FEW_DISKS = 6
DISK_ENTRIES = len(SECRET_DISK_ENTRIES)


class GoalRequirement:
    """The resolved requirement: which model items count and how many, and the disks."""

    def __init__(self, models: tuple, models_count: int, disks_required: int, disks_total: int):
        self.models = models                 # item names; empty = no model requirement
        self.models_count = models_count
        self.disks_required = disks_required  # 0 = no disk hunt
        self.disks_total = disks_total

    @property
    def wants_models(self) -> bool:
        return bool(self.models)

    @property
    def wants_disks(self) -> bool:
        return self.disks_required > 0


def resolve(options, room: int, reserve: int, player_name: str) -> GoalRequirement:
    """Read the goal options, with the disk total kept between the required count and the pool.

    `room` is the number of free pool slots and `reserve` how many of them must stay
    filler (the player's excluded locations take filler only).
    """
    reqs = set(options.goal_requirements.value)
    models: tuple = ()
    count = 0
    if REQ_BIOMETALS in reqs:
        chosen = set(options.required_models.value)
        models = tuple(MODEL_ITEM_BY_KEY[k] for k in MODEL_ITEM_BY_KEY if k in chosen)
        count = min(int(options.required_models_count.value), len(models))
    required = total = 0
    if REQ_DISKS in reqs:
        required = int(options.required_secret_disks.value)
        total = int(options.total_secret_disks.value)
        if total < required:
            logging.warning("[%s] total_secret_disks %d is below required_secret_disks %d: "
                            "raised to %d" % (player_name, total, required, required))
            total = required
        fit = max(0, room - reserve)
        if required > fit:
            raise OptionError(
                "[%s] required_secret_disks: %d Secret Disks do not fit in the pool (%d free slots "
                "after the excluded locations). Lower the number or turn on a pickup_checks_* option."
                % (player_name, required, fit))
        if total > fit:
            logging.warning("[%s] total_secret_disks %d does not fit in the pool: lowered to %d"
                            % (player_name, total, fit))
            total = fit
    return GoalRequirement(models, count, required, total)


def rule(goal: GoalRequirement, player: int):
    """The requirement as a state rule, or None when nothing is required."""
    parts = []
    if goal.wants_models:
        parts.append(lambda state, _names=list(goal.models), _n=goal.models_count:
                     state.has_from_list_unique(_names, player, _n))
    if goal.wants_disks:
        parts.append(lambda state, _n=goal.disks_required: state.has(DISK_ITEM, player, _n))
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return lambda state: all(p(state) for p in parts)


def describe(goal: GoalRequirement) -> str:
    """One line for the spoiler."""
    parts = []
    if goal.wants_models:
        parts.append("%d of %s" % (goal.models_count, ", ".join(goal.models)))
    if goal.wants_disks:
        parts.append("%d Secret Disks (%d in the pool)" % (goal.disks_required, goal.disks_total))
    return "; ".join(parts) or "none"


def slot_data(goal: GoalRequirement, disk_order: list) -> dict:
    """What the client needs: the resolved requirement and the order the disks light entries in."""
    return {
        "models": list(goal.models),
        "models_count": goal.models_count,
        "secret_disks": goal.disks_required,
        "secret_disks_total": goal.disks_total,
        "secret_disk_order": list(disk_order),
    }
