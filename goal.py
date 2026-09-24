"""The goal requirements: what the options ask for, as a rule and as data for the client."""

import logging

from Options import OptionError

from .data import LOCATIONS, SECRET_DISK_ENTRIES

REQ_BIOMETALS = "Biometals"
REQ_DISKS = "Secret Disks"
REQ_MISSIONS = "Missions"
DISK_ITEM = "Secret Disk"
MISSION_PREFIX = "Mission - "
FINAL_MISSION = "Mission - Destroy Model W"
# The story missions that count: every check of the category, so neither the skipped
# intro nor the final mission, which is the goal itself.
COUNTED_MISSIONS = tuple(n for n, v in LOCATIONS.items()
                         if v["category"] == "mission" and n != FINAL_MISSION)
MISSION_COUNT = len(COUNTED_MISSIONS)
# Option keys to item names, in the order the counter and the spoiler list them.
MODEL_ITEM_BY_KEY = {
    "Model X": "Model X", "Model ZX": "Model ZX",
    "Model HX": "Progressive Model HX", "Model FX": "Progressive Model FX",
    "Model LX": "Progressive Model LX", "Model PX": "Progressive Model PX",
    "Model OX": "Model OX",
}
SIX_MODEL_KEYS = tuple(list(MODEL_ITEM_BY_KEY)[:6])
# Without progressive_models the two halves are one item each.
FULL_MODEL_OF = {"Progressive Model HX": "Model HX", "Progressive Model FX": "Model FX",
                 "Progressive Model LX": "Model LX", "Progressive Model PX": "Model PX"}
FULL_MODEL_COPIES = 2
# Up to this many disks in the pool, finding one on a priority location is welcome.
FEW_DISKS = 6
DISK_ENTRIES = len(SECRET_DISK_ENTRIES)


def model_item(name: str, progressive: bool) -> str:
    """The pool's item for a model: the progressive one or its single full item."""
    return name if progressive else FULL_MODEL_OF.get(name, name)


def cleared_event(mission: str) -> str:
    """The event item of a mission location: its Cleared atom in the logic and the count test."""
    return "Cleared: " + mission[len(MISSION_PREFIX):]


class GoalRequirement:
    """The resolved requirement: which model items count, with how many copies each, the disks
    and the missions."""

    def __init__(self, models: tuple, models_count: int, disks_required: int, disks_total: int,
                 copies: dict | None = None, missions_required: int = 0):
        self.models = models                 # item names; empty = no model requirement
        self.models_count = models_count
        self.copies = copies or {}           # item name -> copies that make it count (1 unless full)
        self.disks_required = disks_required  # 0 = no disk hunt
        self.disks_total = disks_total
        self.missions_required = missions_required   # 0 = no mission count

    @property
    def wants_models(self) -> bool:
        return bool(self.models)

    @property
    def wants_disks(self) -> bool:
        return self.disks_required > 0

    @property
    def wants_missions(self) -> bool:
        return self.missions_required > 0


def resolve(options, room: int, reserve: int, player_name: str) -> GoalRequirement:
    """Read the goal options, with the disk total kept between the required count and the pool.

    `room` is the number of free pool slots and `reserve` how many of them must stay
    filler (the player's excluded locations take filler only).
    """
    reqs = set(options.goal_requirements.value)
    if not reqs:
        raise OptionError("[%s] goal_requirements is empty: list at least one of %s, %s, %s"
                          % (player_name, REQ_BIOMETALS, REQ_DISKS, REQ_MISSIONS))
    progressive = bool(options.progressive_models.value)
    models: tuple = ()
    count = 0
    copies: dict = {}
    if REQ_BIOMETALS in reqs:
        chosen = set(options.required_models.value)
        models = tuple(model_item(MODEL_ITEM_BY_KEY[k], progressive)
                       for k in MODEL_ITEM_BY_KEY if k in chosen)
        if not models:
            raise OptionError("[%s] required_models is empty while goal_requirements asks for %s: "
                              "list at least one model" % (player_name, REQ_BIOMETALS))
        count = min(int(options.required_models_count.value), len(models))
        full = progressive and bool(options.require_full_models.value)
        copies = {m: FULL_MODEL_COPIES if full and m in FULL_MODEL_OF else 1 for m in models}
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
    missions = 0
    if REQ_MISSIONS in reqs:
        missions = min(int(options.required_missions.value), MISSION_COUNT)
    return GoalRequirement(models, count, required, total, copies, missions)


def rule(goal: GoalRequirement, player: int):
    """The requirement as a state rule, or None when nothing is required."""
    parts = []
    if goal.wants_models:
        needs = [(m, goal.copies.get(m, 1)) for m in goal.models]
        parts.append(lambda state, _needs=needs, _n=goal.models_count:
                     sum(1 for m, c in _needs if state.has(m, player, c)) >= _n)
    if goal.wants_disks:
        parts.append(lambda state, _n=goal.disks_required: state.has(DISK_ITEM, player, _n))
    if goal.wants_missions:
        events = [cleared_event(m) for m in COUNTED_MISSIONS]
        parts.append(lambda state, _ev=events, _n=goal.missions_required:
                     state.has_from_list_unique(_ev, player, _n))
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return lambda state: all(p(state) for p in parts)


def describe(goal: GoalRequirement) -> str:
    """One line for the spoiler."""
    parts = []
    if goal.wants_models:
        names = [m + (" (full)" if goal.copies.get(m, 1) > 1 else "") for m in goal.models]
        parts.append("%d of %s" % (goal.models_count, ", ".join(names)))
    if goal.wants_disks:
        parts.append("%d Secret Disks (%d in the pool)" % (goal.disks_required, goal.disks_total))
    if goal.wants_missions:
        parts.append("%d of the %d story missions" % (goal.missions_required, MISSION_COUNT))
    return "; ".join(parts) or "none"


def slot_data(goal: GoalRequirement, disk_order: list) -> dict:
    """What the client needs: the resolved requirement and the order the disks light entries in."""
    return {
        "models": list(goal.models),
        "models_copies": [goal.copies.get(m, 1) for m in goal.models],
        "models_count": goal.models_count,
        "secret_disks": goal.disks_required,
        "secret_disks_total": goal.disks_total,
        "secret_disk_order": list(disk_order),
        "missions": goal.missions_required,
    }
