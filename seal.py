"""The seal of Area M: what area_m_access asks for, as a rule and as data for the client."""

import logging

from Options import OptionError

from .data import SEAL_BOSS_BITS, SEAL_GIRO_MISSION, SEAL_ROOMS, SEAL_TRANSERVER
from .goal import MISSION_PREFIX, cleared_event
from .logic import document as F

MODE_OPEN, MODE_BOSSES, MODE_PASSWORDS = "open", "bosses", "passwords"
PASSWORD_ITEM = "Password"
TRANSERVER_ITEM = SEAL_TRANSERVER     # out of the pool unless the seal starts open
# Beating Giro ends in the mission's own Report, so its Cleared event stands for the fight.
GIRO_EVENT = cleared_event(MISSION_PREFIX + SEAL_GIRO_MISSION)


def defeated_event(boss: str) -> str:
    """The event item of a Pseudoroid beaten in its own room."""
    return "Defeated: " + F.BOSSES[boss]["name"]


PSEUDOROIDS = tuple(SEAL_BOSS_BITS)
BOSS_EVENTS = (GIRO_EVENT, *(defeated_event(b) for b in PSEUDOROIDS))


class Seal:
    """The resolved option: how the seal opens, the Passwords it asks for and the pool holds."""

    def __init__(self, mode: str = MODE_OPEN, passwords_required: int = 0, passwords_total: int = 0):
        self.mode = mode
        self.passwords_required = passwords_required
        self.passwords_total = passwords_total


def resolve(options, room: int, reserve: int, player_name: str) -> Seal:
    """Read the options, with the Password total kept between the required count and the pool.

    `room` is the number of free pool slots and `reserve` how many of them must stay
    filler (the player's excluded locations take filler only).
    """
    mode = options.area_m_access.current_key
    if mode != MODE_PASSWORDS:
        return Seal(mode)
    required = int(options.required_passwords.value)
    total = int(options.total_passwords.value)
    if total < required:
        logging.warning("[%s] total_passwords %d is below required_passwords %d: raised to %d"
                        % (player_name, total, required, required))
        total = required
    fit = max(0, room - reserve)
    if required > fit:
        raise OptionError(
            "[%s] required_passwords: %d Passwords do not fit in the pool (%d free slots after "
            "the excluded locations). Lower the number or turn on a pickup_checks_* option."
            % (player_name, required, fit))
    if total > fit:
        logging.warning("[%s] total_passwords %d does not fit in the pool: lowered to %d"
                        % (player_name, total, fit))
        total = fit
    return Seal(mode, required, total)


def rule(seal: Seal, player: int):
    """The seal as a state rule, or None when it is open from the start."""
    if seal.mode == MODE_PASSWORDS:
        return lambda state: state.has(PASSWORD_ITEM, player, seal.passwords_required)
    if seal.mode == MODE_BOSSES:
        return lambda state: state.has_all(BOSS_EVENTS, player)
    return None


def behind(edge: dict) -> bool:
    """Whether an edge leads into the rooms the seal closes off, on foot or by Transerver."""
    return edge["dst"] in SEAL_ROOMS and edge["src"] not in SEAL_ROOMS


def describe(seal: Seal) -> str:
    """One line for the spoiler."""
    if seal.mode == MODE_PASSWORDS:
        return "%d Passwords (%d in the pool)" % (seal.passwords_required, seal.passwords_total)
    if seal.mode == MODE_BOSSES:
        return "the eight Pseudoroids and Giro beaten"
    return "open"


def slot_data(seal: Seal) -> dict:
    """What the client needs to keep the seal closed and to open it."""
    return {"mode": seal.mode, "passwords": seal.passwords_required,
            "passwords_total": seal.passwords_total}
