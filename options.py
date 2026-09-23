from dataclasses import dataclass

from Options import (Accessibility, Choice, DeathLink, NamedRange, OptionDict, OptionGroup, OptionSet,
                     PerGameCommonOptions, ProgressionBalancing, Range, StartInventoryPool, Toggle)

from .goal import (MISSION_COUNT, MODEL_ITEM_BY_KEY, REQ_BIOMETALS, REQ_DISKS, REQ_MISSIONS,
                   SIX_MODEL_KEYS)


class Character(Choice):
    """Playable character: Vent or Aile."""
    display_name = "Character"
    option_vent = 0
    option_aile = 1
    default = 0


class Goal(Choice):
    """Goal of the seed."""
    display_name = "Goal"
    option_defeat_serpent = 0
    default = 0


class GoalRequirements(OptionSet):
    """What you need before the gate to Slither Inc., the final area, opens.

    Biometals: own the models chosen in required_models.
    Secret Disks: collect an ammount of Secret Disks.
    Missions: complete a number of story missions."""
    display_name = "Goal Requirements"
    valid_keys = frozenset({REQ_BIOMETALS, REQ_DISKS, REQ_MISSIONS})
    default = frozenset({REQ_BIOMETALS})


class RequiredModels(OptionSet):
    """Models that count for the Biometals goal requirement: 
    Model X, Model ZX, Model HX, Model FX, Model LX, Model PX, Model OX.
    Only used with Biometals in goal_requirements."""
    display_name = "Required Models"
    valid_keys = frozenset(MODEL_ITEM_BY_KEY)
    default = frozenset(SIX_MODEL_KEYS)


class RequiredModelsCount(NamedRange):
    """How many of the models in required_models you need: 6 by default (the six main biometals),
    any other number, or all for every model in the list.
    A number above the size of the list means all of them."""
    display_name = "Required Models Count"
    range_start = 1
    range_end = 7
    default = 6
    special_range_names = {"all": 7}


class RequireFullModels(Toggle):
    """For the Biometals goal requirement, a progressive model counts only with both halves
    (its level 2 charge). Off: the first half is enough. Ignored without progressive_models."""
    display_name = "Require Full Models"
    default = 0


class RequiredSecretDisks(Range):
    """How many Secret Disks you need for the Secret Disks goal requirement.
    Only used with Secret Disks in goal_requirements. Depending on your configuration, generation may fail if the number of required disks is too high"""
    display_name = "Required Secret Disks"
    range_start = 1
    range_end = 95
    default = 20


class TotalSecretDisks(Range):
    """How many Secret Disks go into the pool.
    A total below required_secret_disks is raised to match it, and one that does not fit in the pool is lowered."""
    display_name = "Total Secret Disks"
    range_start = 1
    range_end = 95
    default = 30


class RequiredMissions(NamedRange):
    """How many story missions you need to complete for the Missions goal requirement: 8 by default,
    any other number, or all. Every mission counts except the skipped intro and the final one (14).
    Only used with Missions in goal_requirements."""
    display_name = "Required Missions"
    range_start = 1
    range_end = MISSION_COUNT
    default = 8
    special_range_names = {"all": MISSION_COUNT}


class StartingModel(Choice):
    """The model you start with"""
    display_name = "Starting Model"
    option_none = 0
    option_model_x = 1
    option_model_zx = 2
    option_model_hx = 3
    option_model_fx = 4
    option_model_lx = 5
    option_model_px = 6
    option_model_ox = 7
    default = option_model_zx


class ProgressiveModels(Toggle):
    """Biometals H, F, L and P come as two Progressive Model items each: the first half makes
    the form usable, the second unlocks its level 2 charged attack. Off: each is a single Model
    item that gives the whole biometal at once."""
    display_name = "Progressive Models"
    default = 1


class HuInPool(Toggle):
    """The human form (Hu) becomes an item of the pool instead of being always
    available. Ignored when starting_model is none."""
    display_name = "Human Form (Hu) In Pool"
    default = 0


class StartingTranserver(Choice):
    """Transerver floor of the hub where a new game starts. Only that area's
    Transerver Access is yours from the start; every other destination is an item like the rest."""
    display_name = "Starting Transerver"
    option_area_a = 0
    option_guardian_base = 1
    alias_guardian_hub = 0
    alias_area_x = 1
    default = 0

class SkipBossRush(Toggle):
    """Skips the boss rush of the Slither Inc. tower: you do not have to beat the 8 Pseudoroids again before Serpent.
    As you climb the tower, the rooms of each pair of bosses appear as already cleared."""
    display_name = "Skip Boss Rush"
    default = 0


class SkipMinibosses(Choice):
    """QoL change so that you don't have to fight the mini bosses in each area every time.
    - after_first_defeat: Only have to fight them once. Next time you leave and come back to the area, the boss stays defeated.
    - always: all of them count as beaten from the start, so their fights never start."""
    display_name = "Skip Mini-Bosses"
    option_off = 0
    option_after_first_defeat = 1
    option_always = 2
    default = 0


class PickupChecks1Up(Toggle):
    """The 1-Ups placed in the world (7) count as checks: the first time you
    pick each one up it sends its location; afterwards it keeps respawning
    and giving a life as usual."""
    display_name = "Pickup Checks: 1-Ups"
    default = 0


class PickupChecksEnergy(Toggle):
    """The energy capsules placed in the world (45) count
    as checks: the first pickup of each one sends its location; afterwards
    they keep respawning and healing."""
    display_name = "Pickup Checks: Energy Capsules"
    default = 0


class PickupChecksWeapon(Toggle):
    """The weapon energy refills placed in the world (25)
    count as checks: the first pickup of each one sends its location;
    afterwards they keep respawning."""
    display_name = "Pickup Checks: Weapon Energy"
    default = 0


class PickupChecksCrystals(Toggle):
    """The E-Crystal pickups placed in the world (56) count as checks: the
    first pickup of each one sends its location; afterwards they keep
    respawning and giving crystals."""
    display_name = "Pickup Checks: E-Crystals"
    default = 0

class BossLogic(OptionDict):
    """Per-boss difficulty, your call: what you must be carrying before the
    logic considers you able to beat each story boss.

    It only restricts the logic: in game you can fight with whatever you
    have. What it guarantees is that the seed never forces you through a boss
    you are not equipped for by your own standard.
    The eight Pseudoroids are fought twice (their own area and the boss rush
    of the D-4 tower, which the game requires before D-5): the requirement
    applies to both encounters (unless skip_boss_rush is on).

    Bosses: Rayfly (B-2), Model Z (D-2), Hivolt (E-7), Lurerre (F-5),
    Fistleo (G-5), Purprill (H-4), Hurricaune (I-3), Leganchor (J-5),
    Flammole (K-4), Protectos (L-4), Prometheus (X-3), Pandora (M-3),
    Prometheus & Pandora (O-2), Serpent (D-5), Omega Zero (N-1). The room
    code works as a key too ("E-7"). Bosses you leave out ask just for any model;
    the gate to Serpent's area follows goal_requirements.

    Requirements: models (X ZX HX FX LX PX OX; "HX2" or "Model HX (full)" =
    both halves of the progressive item, i.e. the level-2 charge), ALL6 (the six main biometals),
    "Life Up x2" (or LIFEUP>=2), "Sub Tank x1" (or SUBTANK>=1) and ITEM B chips by name ("Absorber Chip"),
    combined with & (and), | (or) and parentheses. A required chip is promoted from useful to progression automatically.

    Example:
      boss_logic:
        Hivolt: "HX & Life Up x2"
        Flammole: "Model FX (full) & Absorber Chip"
        Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
        Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
    """
    display_name = "Boss Logic"
    default = {}


class NotifyReceived(Choice):
    """On-screen notifications (the game's small popup) when you receive an
    item: which item classes are shown. off: none; progression: progression
    only; useful: progression and useful; all: also filler (E-Crystals,
    1-Up). Can be changed in game with /mmzx_notify."""
    display_name = "On-screen Notifications: Received Items"
    option_off = 0
    option_progression = 1
    option_useful = 2
    option_all = 3
    default = 2


class NotifySent(Choice):
    """On-screen notifications when you send an item to another player (one of
    your checks holds their item): which classes are shown (off,
    progression, useful, all). Can be changed in game with /mmzx_notify."""
    display_name = "On-screen Notifications: Sent Items"
    option_off = 0
    option_progression = 1
    option_useful = 2
    option_all = 3
    default = 2


class NotifyStyle(Choice):
    """Format of the on-screen notification. short: a single line of 30
    characters (the player name is dropped and the item name cut if it does
    not fit). full: the whole text ("Got <item> from <player>") split by
    words into pages the same popup shows one after another. Can be changed
    in game with /mmzx_notify short|full."""
    display_name = "On-screen Notifications: Style"
    option_short = 0
    option_full = 1
    default = 1


# Every option sits in a named group, in the order the template and the web page show them:
# the two common ones first, then the goal; the core would otherwise open with a "Game
# Options" group of whatever is left out, and would drop what is left out once it is defined.
OPTION_GROUPS = [
    OptionGroup("Game Options", [ProgressionBalancing, Accessibility]),
    OptionGroup("Goal", [Goal, GoalRequirements, RequiredModels, RequiredModelsCount, RequireFullModels,
                         RequiredSecretDisks, TotalSecretDisks, RequiredMissions]),
    OptionGroup("Start", [Character, StartingModel, StartingTranserver]),
    OptionGroup("Items and Logic", [ProgressiveModels, HuInPool, BossLogic]),
    OptionGroup("Pickup Checks", [PickupChecks1Up, PickupChecksEnergy, PickupChecksWeapon, PickupChecksCrystals]),
    OptionGroup("Quality of Life", [SkipBossRush, SkipMinibosses]),
    OptionGroup("Notifications", [NotifyReceived, NotifySent, NotifyStyle]),
    OptionGroup("Death Link", [DeathLink]),
]


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
    goal_requirements: GoalRequirements
    required_models: RequiredModels
    required_models_count: RequiredModelsCount
    require_full_models: RequireFullModels
    required_secret_disks: RequiredSecretDisks
    total_secret_disks: TotalSecretDisks
    required_missions: RequiredMissions
    starting_model: StartingModel
    progressive_models: ProgressiveModels
    hu_in_pool: HuInPool
    starting_transerver: StartingTranserver
    boss_logic: BossLogic
    skip_boss_rush: SkipBossRush
    skip_minibosses: SkipMinibosses
    pickup_checks_1up: PickupChecks1Up
    pickup_checks_energy: PickupChecksEnergy
    pickup_checks_weapon: PickupChecksWeapon
    pickup_checks_crystals: PickupChecksCrystals
    notify_received: NotifyReceived
    notify_sent: NotifySent
    notify_style: NotifyStyle
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
