"""Console commands for the player (registered by the client on connect)."""

import logging
from typing import TYPE_CHECKING

from ..data import HUB_FLOOR_Y
from .addresses import GAME, HUB_SUBAREA, HUB_X, HUB_Y, NOTIFY_LEVELS, NOTIFY_STYLES
from .items import received_counts
from .warps import hub_pad

if TYPE_CHECKING:
    from . import MMZXClient

logger = logging.getLogger("Client")


def _handler(processor) -> "MMZXClient | None":
    """Our client behind the console, or None when another game is connected."""
    handler = processor.ctx.client_handler
    return handler if getattr(handler, "game", None) == GAME else None


def _cmd_teleport(self, *args) -> None:
    """Anti-softlock teleport: no args for the hub, an area letter for its floor, or sub x y."""
    handler = _handler(self)
    if handler is None:
        return
    if len(args) >= 1 and str(args[0]).strip().upper() in HUB_FLOOR_Y:
        letter = str(args[0]).strip().upper()
        # on the floor's console pad; any lower and the player falls through the floor
        sub, x, y = hub_pad(letter)
        handler.pending_teleport = (sub, x, y)
        logger.info(f"Teleport queued -> hub, floor {letter} ({x},{y}).")
        return
    try:
        sub = int(args[0]) if len(args) >= 1 else HUB_SUBAREA
        x = int(args[1]) if len(args) >= 2 else HUB_X
        y = int(args[2]) if len(args) >= 3 else HUB_Y
    except ValueError:
        logger.error("mmzx_teleport: arguments must be numbers (or an area letter A..X)")
        return
    handler.pending_teleport = (sub, x, y)
    logger.info(f"Teleport queued -> subarea {sub} ({x},{y}).")


def _cmd_where(self, *args) -> None:
    """Diagnostic: log the current subarea, position and state."""
    handler = _handler(self)
    if handler is None:
        return
    handler.pending_where = True
    logger.info("mmzx_where: queued (logged on the next in-game tick).")


def _cmd_accept(self, *args) -> None:
    """Force-accept the mission of the current area or hub floor on the next tick."""
    handler = _handler(self)
    if handler is None:
        return
    handler.force_accept = True
    handler.last_accept_sub = None
    logger.info("mmzx_accept: queued (applied on the next in-game tick).")


def _cmd_start(self, *args) -> None:
    """Re-apply the YAML starting state (model and Transerver), e.g. after a new save."""
    handler = _handler(self)
    if handler is None:
        return
    handler.start_state = 2   # apply on the next eligible tick
    handler.start_confirm = 0
    handler.start_retries = 0
    logger.info("mmzx_start: queued (applied once you are in the hub, in game).")


def _cmd_notify(self, *args) -> None:
    """Notice levels: /mmzx_notify [received|sent] <off|progression|useful|all> | <short|full>."""
    handler = _handler(self)
    if handler is None:
        return
    words = [str(a).lower() for a in args]
    if len(words) == 1 and words[0] in NOTIFY_LEVELS:
        handler.notify_cfg["received"] = handler.notify_cfg["sent"] = NOTIFY_LEVELS.index(words[0])
        handler.notify_user_set = True
    elif len(words) == 1 and words[0] in NOTIFY_STYLES:
        handler.notify_style = words[0]
        handler.notify_style_user = True
    elif len(words) == 2 and words[0] in ("received", "sent") and words[1] in NOTIFY_LEVELS:
        handler.notify_cfg[words[0]] = NOTIFY_LEVELS.index(words[1])
        handler.notify_user_set = True
    elif words:
        logger.error("usage: /mmzx_notify <off|progression|useful|all>  or  "
                     "/mmzx_notify [received|sent] <off|progression|useful|all>  or  "
                     "/mmzx_notify <short|full>")
        return
    logger.info("[mmzx] on-screen notifications: received=%s, sent=%s, style=%s" % (
        NOTIFY_LEVELS[handler.notify_cfg["received"]], NOTIFY_LEVELS[handler.notify_cfg["sent"]],
        handler.notify_style))


def _cmd_icons(self, *args) -> None:
    """Draw each pickup in the world as the item it holds: /mmzx_icons [on|off]."""
    handler = _handler(self)
    if handler is None:
        return
    if args and str(args[0]).lower() in ("on", "off"):
        handler.icons_enabled = str(args[0]).lower() == "on"
    elif args:
        logger.error("usage: /mmzx_icons [on|off]")
        return
    logger.info("[mmzx] in-game item icons: %s" % ("on" if handler.icons_enabled else "off"))


def _cmd_goal(self, *args) -> None:
    """Progress towards the goal requirements: /mmzx_goal."""
    handler = _handler(self)
    if handler is None or handler.goal is None:
        return
    for line in handler.goal.report(received_counts(self.ctx), handler.missions_cleared):
        logger.info("[mmzx] " + line)


def _cmd_debug(self, *args) -> None:
    """Show the client's diagnostic messages: /mmzx_debug [on|off]."""
    handler = _handler(self)
    if handler is None:
        return
    if args and str(args[0]).lower() in ("on", "off"):
        handler.debug_log = str(args[0]).lower() == "on"
    elif args:
        logger.error("usage: /mmzx_debug [on|off]")
        return
    logger.info("[mmzx] diagnostic messages: %s" % ("on" if handler.debug_log else "off"))


COMMANDS = {
    "mmzx_teleport": _cmd_teleport, "mmzx_where": _cmd_where, "mmzx_accept": _cmd_accept,
    "mmzx_start": _cmd_start, "mmzx_notify": _cmd_notify, "mmzx_icons": _cmd_icons,
    "mmzx_goal": _cmd_goal, "mmzx_debug": _cmd_debug,
}
