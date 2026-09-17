from dataclasses import dataclass

from Options import (Choice, DeathLink, OptionDict, PerGameCommonOptions,
                     StartInventoryPool, Toggle)


class Character(Choice):
    """Playable character: Vent or Aile."""
    display_name = "Character"
    option_vent = 0
    option_aile = 1
    default = 0


class Goal(Choice):
    """Goal of the seed. Right now the only available goal is 'Defeat Serpent'."""
    display_name = "Goal"
    option_defeat_serpent = 0
    default = 0


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
    code works as a key too ("E-7"). Bosses you leave out ask just for any model,
    except for Serpent, which requires the 6 main models to access the final area.

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


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
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
