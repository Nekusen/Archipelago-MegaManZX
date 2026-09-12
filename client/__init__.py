"""BizHawk client for Mega Man ZX (USA).

Reads and writes the game's RAM through the "ARM9 System Bus" domain of the
melonDS core and talks to the structures the ROM patch leaves in free RAM.
The watcher and its stage order live here; each stage is a function
(client, ctx, ...) in a module of its own.
"""

import collections
import logging
from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .addresses import (
    BOOT_FILL, GAME, NOTIFY_LEVELS, NOTIFY_STYLES, PICKUP_OPTION_KEYS, ROM_AP_MAGIC,
    ROM_AP_MAGIC_LEN, ROM_AP_MAGIC_OFF, ROM_GAME_CODE, ROM_GAME_CODE_OFF, ROM_SLOT_NAME_LEN,
    ROM_SLOT_NAME_OFF, STARTUP_TICKS)
from .ram import ProgressWindow, Tick
from .notices import push_notices, sync_icon_table
from .startup import apply_start_state, resolve_start_state, seed_golden_image
from .checks import detect_checks
from .items import grant_items, revert_unowned_models
from .missions import auto_accept_mission, handle_ending, repair_missions, skip_boss_rush
from .tracker import log_where, receive_death_link, report_death, send_position
from .warps import handle_warps
from .commands import COMMANDS

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

logger = logging.getLogger("Client")


class MMZXClient(BizHawkClient):
    game = GAME
    system = "NDS"
    patch_suffix = ".apmmzx"

    def __init__(self) -> None:
        super().__init__()
        # slot options, read once per connection (_setup)
        self.death_link_enabled = False
        self.mission_auto_accept = False   # open-world mode
        self.skip_boss_rush = False        # QoL: skip the D-4 boss rush
        self.mailbox_enabled = False       # some pickup category is a check
        # settings the player changes from the console; they outlive a reconnect
        self.notify_cfg = {"received": 2, "sent": 2}      # indices into NOTIFY_LEVELS
        self.notify_user_set = False     # /mmzx_notify used (wins over the YAML)
        self.notify_style = "full"       # NOTIFY_STYLES; the YAML sets it on connect
        self.notify_style_user = False   # /mmzx_notify style used (wins over the YAML)
        self.icons_enabled = True
        self.debug_log = False           # /mmzx_debug on: diagnostic messages at INFO level
        # requests queued by console commands, served on the next in-game tick
        self.pending_where = False
        self.pending_teleport: tuple[int, int, int] | None = None   # (subarea, x, y)
        self.force_accept = False
        # starting state: 0 not requested, 1 waiting for the datastore, 2 apply, 3 done;
        # the LOAD may force Model X once, so the model is re-asserted until it holds
        self.start_state = 0
        self.start_key: str | None = None
        self.start_confirm = 0
        self.start_retries = 0
        # what the watcher remembers between ticks
        self.last_accept_sub = None        # subarea or hub floor whose mission was handled
        self.last_legit_model = 1          # last owned active model seen, to revert to
        self.transport_wait = False        # Target Area list open: read the pick on return
        self._stage_failed: set[str] = set()   # stages whose exception was already logged
        self.slot_name: str | None = None
        self._forget_game()

    def _forget_game(self) -> None:
        """Reset everything tied to one game; a newly validated ROM starts clean."""
        self.setup_done = False
        self.ingame_ticks = 0
        # checks
        self.local_checked: set[int] = set()
        self.mailbox_count: int | None = None
        self.mailbox_checked: set[int] = set()
        # consumables log: [[cumulative n, playtime]]; None until the datastore answers
        self.cons_log: list[list[int]] | None = None
        self.cons_key: str | None = None
        self.cons_requested = False
        # DeathLink
        self.prev_alive: bool | None = None      # last tick's player state; None = unknown (title, reload)
        self.prev_death_link: float | None = None
        self.pending_death = False
        self.death_induced = False       # last death came from DeathLink: no echo
        # tracker, notices and icons
        self.pos_last: tuple[int, int, int, float] | None = None   # (sub, x, y, t) last sent
        self.notify_queue: collections.deque = collections.deque()
        self.notified_items: int | None = None    # None = skip the backlog on connect
        self.scout_requested: set[int] = set()
        self.icon_written: tuple[int, bytes] | None = None
        self.ending_ticks = 0             # ticks with the stuck-ending signature

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        """Accept only a ROM patched for Archipelago; take the slot name from its header."""
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (ROM_GAME_CODE_OFF, 4, "ROM"),
                (ROM_AP_MAGIC_OFF, ROM_AP_MAGIC_LEN, "ROM"),
                (ROM_SLOT_NAME_OFF, ROM_SLOT_NAME_LEN, "ROM"),
            ])
        except bizhawk.RequestFailedError:
            return False
        if reads[0] != ROM_GAME_CODE:
            return False
        if reads[1] != ROM_AP_MAGIC:
            logger.info("ERROR: this Mega Man ZX ROM is not patched for "
                        "Archipelago. Generate the .apmmzx patch and open it "
                        "with the launcher to create the patched ROM.")
            return False
        raw = reads[2]
        end = raw.find(b"\x00")
        try:
            self.slot_name = raw[:end if end >= 0 else ROM_SLOT_NAME_LEN].decode("utf-8")
        except UnicodeDecodeError:
            self.slot_name = None
        ctx.game = self.game
        # the ROM places no items: the client grants everything, start inventory included
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.125
        self._forget_game()
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        """Log in with the slot name read from the ROM header."""
        if self.slot_name:
            ctx.auth = self.slot_name

    def _debug(self, msg: str) -> None:
        """Log at INFO after /mmzx_debug on, else at DEBUG (hidden by the client)."""
        (logger.info if self.debug_log else logger.debug)(msg)

    async def _setup(self, ctx) -> None:
        """Read the slot options once per connection and register the console commands."""
        self.setup_done = True
        opts = ctx.slot_data
        self.death_link_enabled = bool(opts.get("death_link", False))
        if self.death_link_enabled:
            await ctx.update_death_link(True)
        self.mission_auto_accept = bool(opts.get("mission_auto_accept", False))
        self.skip_boss_rush = bool(opts.get("skip_boss_rush", False))
        if self.skip_boss_rush:
            logger.info("[mmzx] skip_boss_rush: the D-4 boss rush is skipped (each pair of "
                        "Pseudoroids is marked as beaten when the elevator reaches its stop)")
        self.mailbox_enabled = any(bool(opts.get(k, False)) for k in PICKUP_OPTION_KEYS)
        # notice thresholds from the YAML, unless /mmzx_notify already set them
        for key in ("received", "sent"):
            val = str(opts.get("notify_" + key, "")).lower()
            if not self.notify_user_set and val in NOTIFY_LEVELS:
                self.notify_cfg[key] = NOTIFY_LEVELS.index(val)
        style = str(opts.get("notify_style", "")).lower()
        if not self.notify_style_user and style in NOTIFY_STYLES:
            self.notify_style = style
        logger.info("[mmzx] on-screen notifications: received=%s, sent=%s, style=%s "
                    "(/mmzx_notify [received|sent] <off|progression|useful|all> | <short|full>)"
                    % (NOTIFY_LEVELS[self.notify_cfg["received"]],
                       NOTIFY_LEVELS[self.notify_cfg["sent"]], self.notify_style))
        for name, fn in COMMANDS.items():
            ctx.command_processor.commands[name] = fn

    async def _stage(self, name: str, coro) -> None:
        """Run one watcher stage; a bug in one stage is logged once and the rest still run.

        A connector failure is not a bug: it propagates and aborts the tick.
        """
        try:
            await coro
            self._stage_failed.discard(name)
        except bizhawk.RequestFailedError:
            raise
        except Exception:
            if name not in self._stage_failed:
                self._stage_failed.add(name)
                logger.exception("[mmzx] stage '%s' failed (continuing with the rest)" % name)

    def _in_play(self, tick: "Tick") -> bool:
        """Whether the gameplay stages may run this tick.

        In game means: game launched from the title (carousel step 6), a subarea,
        HP above zero and the gameplay state word; the title and its menus share
        the last three. Then a few ticks and an initialized message bank, since
        some structures still hold the boot fill right after launch.
        """
        if not tick.in_game:
            self.ingame_ticks = 0
            return False
        self.ingame_ticks += 1
        return self.ingame_ticks >= STARTUP_TICKS and tick.msg_bank != BOOT_FILL

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        """One tick: seed the title, then detect checks, grant items and repair the game.

        """
        if ctx.server is None or ctx.slot_data is None:
            return
        if not self.setup_done:
            await self._setup(ctx)
        try:
            await self._stage("start key", resolve_start_state(self, ctx))
            await self._stage("golden image", seed_golden_image(self, ctx))
            tick = Tick(await bizhawk.read(ctx.bizhawk_ctx, Tick.READS))
            if self.death_link_enabled:
                await self._stage("deathlink send", report_death(self, ctx, tick))
            if not self._in_play(tick):
                return
            if self.pending_where:
                self.pending_where = False
                await self._stage("where", log_where(self, ctx))
            await self._stage("position", send_position(self, ctx, tick))
            window = await ProgressWindow.read(ctx)
            await self._stage("checks", detect_checks(self, ctx, window))
            await self._stage("item icons", sync_icon_table(self, ctx, tick))
            await self._stage("missions repair", repair_missions(self, ctx, tick))
            await self._stage("starting state", apply_start_state(self, ctx, tick))
            await self._stage("items", grant_items(self, ctx, tick))
            await self._stage("notifications", push_notices(self, ctx))
            await self._stage("models", revert_unowned_models(self, ctx, tick))
            if self.mission_auto_accept:
                await self._stage("auto-accept", auto_accept_mission(self, ctx, tick))
            if self.skip_boss_rush:
                await self._stage("boss rush", skip_boss_rush(self, ctx, tick))
            if self.death_link_enabled:
                await self._stage("deathlink receive", receive_death_link(self, ctx, tick))
            await self._stage("warps", handle_warps(self, ctx, tick))
            await self._stage("ending", handle_ending(self, ctx, window, tick))
        except bizhawk.RequestFailedError:
            pass    # the connector dropped: the framework reconnects and the next tick retries
