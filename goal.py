"""The goal requirements: what the options ask for, as a rule and as data for the client."""

import logging

from Options import OptionError

from .data import LOCATIONS, SECRET_DISK_ENTRIES, ZERO_BOSSES
from .logic.document import CLEARED_PREFIX, DEFEATED_PREFIX, FINAL_MISSION, MISSION_PREFIX

REQ_BIOMETALS = "Biometals"
REQ_DISKS = "Secret Disks"
REQ_MISSIONS = "Missions"
REQ_MUTOS = "Mutos Reploid Hunting"
DISK_ITEM = "Secret Disk"
GOAL_SERPENT, GOAL_OMEGA = 0, 1
# The story missions that count: every check of the category, so neither the skipped
# intro nor the final mission, which is the goal itself.
COUNTED_MISSIONS = tuple(n for n, v in LOCATIONS.items()
                         if v["category"] == "mission" and n != FINAL_MISSION)
MISSION_COUNT = len(COUNTED_MISSIONS)
# The Mega Man Zero 3/4 bosses the hunt counts: four per game, each behind its option.
ZERO_GAME_OPTIONS = {3: "zero3_bosses", 4: "zero4_bosses"}
MUTOS_PER_GAME = 4
MUTOS_MAX = len(ZERO_BOSSES)
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
    return CLEARED_PREFIX + mission[len(MISSION_PREFIX):]


def defeated_event(boss_id: str) -> str:
    """The event item of a Mega Man Zero boss location, what the hunt counts."""
    return DEFEATED_PREFIX + ZERO_BOSSES[boss_id]["name"]


MUTOS_EVENTS = tuple(defeated_event(b) for b in ZERO_BOSSES)


def zero_games(options) -> set[int]:
    """The games whose bosses the options turn on."""
    return {game for game, option in ZERO_GAME_OPTIONS.items() if getattr(options, option).value}


def goal_is_omega(options) -> bool:
    return int(options.goal.value) == GOAL_OMEGA


class GoalRequirement:
    """The resolved requirement: which model items count, with how many copies each, the disks,
    the missions and the Mega Man Zero bosses."""

    def __init__(self, models: tuple, models_count: int, disks_required: int, disks_total: int,
                 copies: dict | None = None, missions_required: int = 0, mutos_required: int = 0):
        self.models = models                 # item names; empty = no model requirement
        self.models_count = models_count
        self.copies = copies or {}           # item name -> copies that make it count (1 unless full)
        self.disks_required = disks_required  # 0 = no disk hunt
        self.disks_total = disks_total
        self.missions_required = missions_required   # 0 = no mission count
        self.mutos_required = mutos_required         # 0 = no boss hunt

    @property
    def wants_models(self) -> bool:
        return bool(self.models)

    @property
    def wants_disks(self) -> bool:
        return self.disks_required > 0

    @property
    def wants_missions(self) -> bool:
        return self.missions_required > 0

    @property
    def wants_mutos(self) -> bool:
        return self.mutos_required > 0


def resolve(options, room: int, reserve: int, player_name: str) -> GoalRequirement:
    """Read the goal options, with the disk total kept between the required count and the pool.

    `room` is the number of free pool slots and `reserve` how many of them must stay
    filler (the player's excluded locations take filler only).
    """
    reqs = set(options.goal_requirements.value)
    if not reqs:
        raise OptionError("[%s] goal_requirements is empty: list at least one of %s, %s, %s, %s"
                          % (player_name, REQ_BIOMETALS, REQ_DISKS, REQ_MISSIONS, REQ_MUTOS))
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
    mutos = 0
    if REQ_MUTOS in reqs:
        mutos = int(options.required_mutos_reploids.value)
        available = MUTOS_PER_GAME * len(zero_games(options))
        if mutos > available:
            raise OptionError(
                "[%s] required_mutos_reploids: %d bosses asked for but %s. Turn on %s (each game "
                "brings four bosses; both need their GBA ROM when the patch is opened) or lower the number."
                % (player_name, mutos, "none of the Mega Man Zero bosses is on" if not available
                   else "only %d are on" % available,
                   " and ".join(ZERO_GAME_OPTIONS[g] for g in sorted(set(ZERO_GAME_OPTIONS) - zero_games(options)))))
    return GoalRequirement(models, count, required, total, copies, missions, mutos)


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
    if goal.wants_mutos:
        parts.append("%d of the Mega Man Zero bosses" % goal.mutos_required)
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
        "mutos": goal.mutos_required,
    }


def from_slot_data(data: dict | None) -> tuple[GoalRequirement, list]:
    """The resolved requirement and the disk order back from their slot data.

    A seed from before the goal requirements sends none: it asked for the six main models.
    """
    if data is None:
        models = tuple(MODEL_ITEM_BY_KEY[k] for k in SIX_MODEL_KEYS)
        return GoalRequirement(models, len(models), 0, 0), list(range(DISK_ENTRIES))
    models = tuple(data.get("models", ()))
    copies = dict(zip(models, data.get("models_copies", ())))
    goal = GoalRequirement(models, int(data.get("models_count", 0)), int(data.get("secret_disks", 0)),
                           int(data.get("secret_disks_total", 0)), copies, int(data.get("missions", 0)),
                           int(data.get("mutos", 0)))
    return goal, list(data.get("secret_disk_order", range(DISK_ENTRIES)))
