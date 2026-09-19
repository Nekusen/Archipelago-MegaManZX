from dataclasses import dataclass

from Options import (Choice, DeathLink, NamedRange, OptionDict, OptionGroup, OptionSet,
                     PerGameCommonOptions, Range, StartInventoryPool, Toggle)

from .goal import MODEL_ITEM_BY_KEY, REQ_BIOMETALS, REQ_DISKS, SIX_MODEL_KEYS


class Character(Choice):
    """Playable character: Vent or Aile."""
    display_name = "Character"
    option_vent = 0
    option_aile = 1
    default = 0


class Goal(Choice):
    """Goal of the seed. Defeat Serpent: beat Serpent at the top of Slither Inc.
    What you need before the gate to its area opens is set by goal_requirements."""
    display_name = "Goal"
    option_defeat_serpent = 0
    default = 0


class GoalRequirements(OptionSet):
    """What you need before the gate to Slither Inc., the final area, opens.
    Every requirement you list must be met; the list cannot be empty.

    Biometals: own the models chosen in required_models.
    Secret Disks: collect Secret Disks, goal items added to the pool
    (required_secret_disks, total_secret_disks)."""
    display_name = "Goal Requirements"
    valid_keys = frozenset({REQ_BIOMETALS, REQ_DISKS})
    default = frozenset({REQ_BIOMETALS})


class RequiredModels(OptionSet):
    """Models that count for the Biometals goal requirement: Model X, Model ZX, Model HX,
    Model FX, Model LX, Model PX, Model OX. A progressive model counts with its first half,
    and your starting model counts if it is listed.
    Only used with Biometals in goal_requirements."""
    display_name = "Required Models"
    valid_keys = frozenset(MODEL_ITEM_BY_KEY)
    default = frozenset(SIX_MODEL_KEYS)


class RequiredModelsCount(NamedRange):
    """How many of the models in required_models you need: all of them, or any lower number
    (with 4, the first four you find open the gate). A number above the size of the list
    means all of them."""
    display_name = "Required Models Count"
    range_start = 1
    range_end = 7
    default = 7
    special_range_names = {"all": 7}


class RequiredSecretDisks(Range):
    """How many Secret Disks you need for the Secret Disks goal requirement.
    Only used with Secret Disks in goal_requirements."""
    display_name = "Required Secret Disks"
    range_start = 1
    range_end = 95
    default = 20


class TotalSecretDisks(Range):
    """How many Secret Disks go into the pool, so the last ones you need are never the only
    ones left. They replace E-Crystals. A total below required_secret_disks is raised to
    match it, and one that does not fit in the pool is lowered; both with a warning."""
    display_name = "Total Secret Disks"
    range_start = 1
    range_end = 95
    default = 30


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


OPTION_GROUPS = [
    OptionGroup("Goal", [Goal, GoalRequirements, RequiredModels, RequiredModelsCount,
                         RequiredSecretDisks, TotalSecretDisks]),
]


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
    goal_requirements: GoalRequirements
    required_models: RequiredModels
    required_models_count: RequiredModelsCount
    required_secret_disks: RequiredSecretDisks
    total_secret_disks: TotalSecretDisks
    starting_model: StartingModel
    hu_in_pool: HuInPool
    starting_transerver: StartingTranserver
    boss_logic: BossLogic
    skip_boss_rush: SkipBossRush
    pickup_checks_1up: PickupChecks1Up
    pickup_checks_energy: PickupChecksEnergy
    pickup_checks_weapon: PickupChecksWeapon
    pickup_checks_crystals: PickupChecksCrystals
    notify_received: NotifyReceived
    notify_sent: NotifySent
    notify_style: NotifyStyle
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
