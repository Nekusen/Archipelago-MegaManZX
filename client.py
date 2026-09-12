"""BizHawk client for Mega Man ZX (USA).

Reads and writes the game's RAM through the "ARM9 System Bus" domain of the
melonDS core and talks to the structures the ROM patch leaves in free RAM.
See docs/client_protocol.md and docs/memory_map.md.
"""

import collections
import time
from typing import TYPE_CHECKING, Any

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .data import (LOCATIONS, ITEMS, GOAL_BITS, GOAL_BITS_SERPENT, MISSION_ACCEPT,
                   MISSION_STATE_ADDR, MISSION_ACTIVE_FLAG,
                   STARTING_MODELS, STARTING_MODEL_ITEM, STARTING_TRANSERVERS,
                   MODEL_X_POSSESSION, ACTIVE_MODEL_ADDR)
from .data import EVENT_GATES, EVENT_GATES_OPEN, EVENT_GATES_ALL6
from .data import HUB_FLOOR_BOSS, HUB_FLOOR_DOOR_X, HUB_FLOOR_Y, WARP_DESTINATIONS
from .data import PICKUP_MAILBOX_ADDR, PICKUP_MAILBOX_SLOTS
from .data import ICON_TABLE_ADDR, ICON_TABLE_SIZE, ICON_TABLE_PRESENT_OFF, ICON_CODES, NOTIFY_ADDR, NOTIFY_BUF_MAX, NOTIFY_POPUP_GLYPHS
from .golden import GOLDEN_IMAGE, GOLDEN_IMAGE_ADDR, build_image
from . import bossrush as BR
ITEM_ID_TO_NAME = {v["id"]: n for n, v in ITEMS.items()}
# Items with their own sprite in the AP graphics set; anything else is drawn
# as the Archipelago logo of its classification.
ICON_BY_ITEM = {
    "Life Up": "lifeup", "Sub Tank": "subtank",
    "Absorber Chip": "chip_Absorber", "Eraser Chip": "chip_Eraser", "Featherweight Chip": "chip_Featherweight",
    "Extender Chip": "chip_Extender", "Quick Charger Chip": "chip_QuickCharger", "Ice Boots Chip": "chip_IceBoots",
    "Wind Boots Chip": "chip_WindBoots", "Frog Chip": "chip_Frog",
    "Model Hu": "model_Hu", "Model X": "model_X", "Model ZX": "model_ZX", "Model OX": "model_OX",
    "Progressive Model HX": "model_HX", "Progressive Model FX": "model_FX",
    "Progressive Model LX": "model_LX", "Progressive Model PX": "model_PX",
    "Model HX": "model_HX", "Model FX": "model_FX", "Model LX": "model_LX", "Model PX": "model_PX",
    "Yellow Card Key": "card_Yellow", "Green Card Key": "card_Green", "Red Card Key": "card_Red",
    "Blue Card Key": "card_Blue", "White Card Key": "card_White", "Purple Card Key": "card_Purple",
}


if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

DOM = "ARM9 System Bus"

# Progress block
LIVE_BLOCK = 0x021045CC       # live copy
# The game hands out Card Keys as mission rewards, so the received set is
# written as-is over these bits every tick.
CARDKEY_MASKS: dict[int, int] = {}
for _kn, _kv in ITEMS.items():
    if _kn.endswith("Card Key") and _kv["grant"][0] == "live_bit":
        CARDKEY_MASKS[_kv["grant"][1]] = CARDKEY_MASKS.get(_kv["grant"][1], 0) | (1 << _kv["grant"][2])
CANON_BLOCK = 0x021602B4      # canonical copy, restored on death
LIVE_LEN = 0x60
PLAYER_POS = 0x0214FB64      # two u32: x << 8, y << 8
POS_KEY = "mmzx_pos_%d"     # data storage: [subarea, x, y] for UT
POS_INTERVAL = 1.0
POS_MIN_DELTA = 48
PLAYTIME = 0x021602A8        # frames; the game clock for consumables
CONS_KEY = "mmzx_consumables_%s_%s"  # data storage: [[applied, playtime], ...]


def _consumables_present(log, playtime: int) -> int:
    """Consumables already present in a game state at the given play time.

    Batches stamped later than the play time were rewound by a reload.
    """
    return max([int(e[0]) for e in log if int(e[1]) <= playtime], default=0)

# Weapon Energy: a model's cap comes from the victory levels of its two bosses,
# which only a real victory writes, so a model granted by item needs them set.
BOSS_LEVELS = 0x02104634
MODEL_LEVEL_IDX = {3: (0, 4), 4: (2, 6), 5: (1, 5), 6: (3, 7)}   # HX, FX, LX, PX
WE_BASE = 0x0214FC92          # + active model = current WE
WE_FULL = 16
MSG_BANK = 0x02104588         # 0xFFFFFFFF until boot has finished

# Player object
LIFEUP_BYTE = 0x0214FC77
SUBTANK_BYTE = 0x0214FC78
ECRYSTALS = 0x0214FC70        # u24
HP = 0x0214FBB2
MODEL = 0x0214FC74

# Scene and title
SUBAREA_STABLE = 0x02108228
GAME_STATE = 0x0215E6D8
STATE_INGAME = 0x500
STATE_LOAD = 0x400            # scene load (teleport)
# The title and its menus share the gameplay state word; the carousel step
# tells them apart. Steps 3 and 5 are safe to seed the golden image, 6 is a
# launched game.
TITLE_CAROUSEL_STEP = 0x0214CD70
TITLE_STEPS_SEEDABLE = (3, 5)
SCENE_DESC = 0x0216047C       # spawn x, y and subarea
LIVES = 0x0214FC6C
HPMAX = 0x0214FC76

CANON_OFF = CANON_BLOCK - LIVE_BLOCK

# Models: active value to (item, possession bit only that item sets). Owning a
# form comes from its item alone; anything the game sets on its own is undone.
MODEL_POSSESSION = {
    1: ("Model X", 0x021045CF, 7),
    2: ("Model ZX", 0x021045D0, 0),
    3: ("Progressive Model HX", 0x02104627, 0),
    4: ("Progressive Model FX", 0x02104627, 1),
    5: ("Progressive Model LX", 0x02104627, 2),
    6: ("Progressive Model PX", 0x02104627, 3),
    7: ("Model OX", 0x021045D2, 1),
}
# Second copy of a progressive model: level-2 charged attack and the larger WE cap.
MODEL_PART2 = {
    3: (0x02104626, 0), 4: (0x02104626, 1), 5: (0x02104626, 2), 6: (0x02104626, 3),
}

# Missions and story
MISSION_ACTIVE_BYTE = 0x0210462B   # .1 mission accepted, .2 story mission
STORY_BLOCK = 0x0214F6BC           # +4 mission id, +8 handler object
STORY_BLOCK_CANON = 0x02160554     # checkpoint copy, restored on death
# Abort Mission restores these three mirrors, so a forced accept refreshes them
# first or the abort would bring back whatever the golden image held.
BLOCK_MIRROR = 0x02160398
SCENE_DESC_MIRROR = 0x021604E8
STORY_BLOCK_MIRROR = 0x02160670
SCENE_DESC_LEN, STORY_BLOCK_LEN, LIVE_BLOCK_LEN = 0x6C, 0x11C, 0xE4
CUTSCENE_FLAG = 0x0214F502         # bit 0 = cutscene running
# Troop Reinforcement: the Giro scene at the end of D-2 only arms with the
# start flag set and the megamerge flag clear. Dying after the megamerge
# without the Report would leave D-2 empty for good, so the client repairs
# both while Troop is active and not yet completed.
TROOP_STATE = 162                  # mission state "Troop accepted"
TROOP_MERGE = (0x02104602, 1)
TROOP_START = (0x021045E0, 2)
TROOP_ROOMS = (15, 16, 17)         # D-1 to D-3, where the scene arms
TROOP_ROOM_OBJ = 0x0214F3EC        # room script object of the loaded room
TROOP_ROOM_MERGED = 7              # D-2 script state once merged
STORY_HANDLER_ID = 0x0214F6C0
STORY_HANDLER_OBJ = 0x0214F6C4     # +9 cutscene id (0xFF none), +0xB state

# Game ending: the credits are driven by the story handler of mission 16, not
# by the D-5 room. In the open world Serpent can die with that handler missing
# (D-4 never crossed with the mission) and the screen stays white for good,
# so the client installs the handler at the state that waits for Serpent 2.
ENDING_SUBAREA = 19                   # D-5
ENDING_SERPENT = (0x02104602, 0x0C)   # bits 2 and 3: both Serpent forms beaten
GAME_CLEARED = (0x0210462D, 0)
D05_ROOM_TERMINAL = 21                # D-5 room script finished
ENDING_HANDLER_ID = 16                # Destroy Model W
ENDING_HANDLER_STATE = 0x0D           # waiting for Serpent 2 to die
ENDING_UNSTICK_TICKS = 5

# Player object, for the boss rush skip (see bossrush.py) and DeathLink
PLAYER_OBJ = 0x0214FB08
PLAYER_PERSIST = 0x0214FC5C          # spawn position and facing
DEATH_STATE = 0x0A                   # player state byte: dying

BOSS_SUBAREAS = {26, 32, 37, 44, 55, 60, 63, 66, 41, 51, 19}   # unused

ROM_GAME_CODE = b"ARZE"       # MMZX USA

# Hub and warps
# Default teleport: the console pad of floor A, so UP opens the console.
HUB_SUBAREA, HUB_X, HUB_Y = 70, 384, 335

# "Go to Transerver" from the pause menu: the ROM raises WARP_REQ, the client
# opens the game's own Target Area list and reads the chosen station back.
WARP_REQ = 0x020CB9D0          # 1 = pending; the client clears it
PAD_HELD = 0x020F2768          # unused
TRANSPORT_SEL = 0x021046A8     # Target Area selection, -1 = none
STATE_TARGET_AREA = 0x00050700 # opens the Target Area list
STATION_ROOMS = list(WARP_DESTINATIONS) + ["x01"]   # room per station index
HUB_PAD_DY = 17                # console pad height above the floor

FLAG_WATCH_BASE, FLAG_WATCH_LEN = 0x021045C0, 0x84   # /mmzx_flags window

# Pickup mailbox, polled only if the slot enables a pickup category
PICKUP_OPTION_KEYS = ("pickup_checks_1up", "pickup_checks_energy",
                      "pickup_checks_weapon", "pickup_checks_crystals")


# On-screen notices: text left in the NOTIFY mailbox, shown by the ROM in the
# game's small popup
NOTIFY_DUR = 90                 # frames
NOTIFY_LEVELS = ("off", "progression", "useful", "all")
NOTIFY_PUNCT = {ch: ord(ch) - 0x20 for ch in "!\"#$%&'()*+,-./:"}   # glyphs seen on screen
NOTIFY_PUNCT["?"] = 0x1F
NOTIFY_GREEN, NOTIFY_WHITE = b"\xf1\x03", b"\xf1\x00"
NOTIFY_QUEUE_MAX = 16
# `full` splits the text into pages that the popup chains without closing
NOTIFY_STYLES = ("short", "full")
NOTIFY_PAGE = b"\xfd"


def encode_text(text: str, terminate: bool = True) -> bytes:
    """Encode text in the game's font: ASCII minus 0x20, unknown glyphs as spaces."""
    out = bytearray()
    for ch in text:
        if ch == " ":
            out.append(0x00)
        elif "0" <= ch <= "9":
            out.append(0x10 + ord(ch) - 0x30)
        elif "A" <= ch <= "Z":
            out.append(0x21 + ord(ch) - 0x41)
        elif "a" <= ch <= "z":
            out.append(0x41 + ord(ch) - 0x61)
        elif ch in NOTIFY_PUNCT:
            out.append(NOTIFY_PUNCT[ch])
        else:
            out.append(0x00)
    if terminate:
        out.append(0xFE)
    return bytes(out)


def notify_pages(head: str, item: str, tail: str, n: int = NOTIFY_POPUP_GLYPHS) -> list[bytes]:
    """Split head, item (in green) and tail by words into pages of at most n glyphs.

    Each page carries its own color control; a word longer than a line is chopped.
    Returns the encoded pages without 0xFD or 0xFE.
    """
    # keep " from Alice" together so no page ends with a dangling "from"
    tail_words = [tail.strip()] if 0 < len(tail.strip()) <= n else tail.split()
    words = ([(w, False) for w in head.split()] + [(w, True) for w in item.split()]
             + [(w, False) for w in tail_words])
    pages: list[list[tuple[str, bool]]] = []
    line: list[tuple[str, bool]] = []
    used = 0
    for w, green in words:
        while len(w) > n:
            if line:
                pages.append(line)
                line, used = [], 0
            pages.append([(w[:n], green)])
            w = w[n:]
        need = len(w) + (1 if line else 0)
        if used + need > n:
            pages.append(line)
            line, used = [], 0
            need = len(w)
        line.append((w, green))
        used += need
    if line:
        pages.append(line)
    out = []
    for pg in pages:
        buf = bytearray()
        color = None
        for j, (w, green) in enumerate(pg):
            if j:
                buf.append(0x00)
            if green != color:
                buf += NOTIFY_GREEN if green else NOTIFY_WHITE
                color = green
            buf += encode_text(w, False)
        out.append(bytes(buf))
    return out


def notify_bytes(head: str, item: str, tail: str, style: str = "short") -> bytes:
    """Encode a notice in the given style.

    `short` keeps one popup line, dropping the tail and then trimming the item.
    `full` chains pages with 0xFD and drops trailing pages that overflow BUF.
    """
    n = NOTIFY_POPUP_GLYPHS
    if style == "full":
        pages = notify_pages(head, item, tail, n)
        while len(pages) > 1 and sum(len(p) + 1 for p in pages) > NOTIFY_BUF_MAX:
            pages.pop()
        return NOTIFY_PAGE.join(pages) + b"\xfe"
    if len(head) + len(item) + len(tail) > n:
        tail = ""
    if len(head) + len(item) > n:
        item = item[:max(0, n - len(head) - 1)] + "."
    data = (encode_text(head, False) + NOTIFY_GREEN + encode_text(item, False)
            + NOTIFY_WHITE + encode_text(tail, False) + b"\xfe")
    if len(data) > NOTIFY_BUF_MAX:
        data = data[:NOTIFY_BUF_MAX - 1] + b"\xfe"
    return data


def item_level(flags: int) -> int:
    """Level of an item for the notice threshold: 1 progression, 2 useful, 3 the rest."""
    if flags & 0b001:
        return 1
    if flags & 0b010:
        return 2
    return 3


class MMZXClient(BizHawkClient):
    game = "Mega Man ZX"
    system = "NDS"
    patch_suffix = ".apmmzx"

    def __init__(self) -> None:
        super().__init__()
        self.local_checked: set[int] = set()
        self.cons_log = None          # [[cumulative n, playtime]]; None = not loaded
        self.cons_key = None
        self.cons_requested = False
        self.death_link_enabled = False
        self.death_link_setup = False
        self.mission_auto_accept = False   # open-world mode (slot_data)
        self.skip_boss_rush = False        # QoL: skip the D-4 boss rush (slot_data)
        self.mission_setup = False
        self.last_accept_sub = None        # last auto-accepted subarea
        self.ending_ticks = 0              # ticks with the stuck-ending signature
        self.force_accept = False          # /mmzx_accept: force on the next tick
        self._stage_failed: set[str] = set()   # stages whose exception was already traced
        self.pending_where = False         # /mmzx_where: dump position/state to the log
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.death_induced = False       # last death came from DeathLink: no echo
        self.pending_teleport = None   # (subarea, x, y) or None
        self.transport_wait = False    # Target Area list open: read the pick on return
        self.added_commands = False
        self._win: tuple[int, int] | None = None   # detection window (cache)
        # flag diagnostics
        self.flag_watch = False
        self.flag_snap: bytes | None = None
        self.pending_dump = False   # /mmzx_dump
        # starting state: 0 not requested, 1 waiting for the datastore, 2 apply, 3 done
        self.start_state = 0
        self.start_key: str | None = None
        # the LOAD may force Model X once; the model is re-asserted until it holds
        self.start_confirm = 0
        self.start_retries = 0
        self.last_legit_model = 1     # last owned active model seen, to revert to
        # respawnable pickup mailbox
        self.mailbox_count: int | None = None
        self.mailbox_checked: set[int] = set()
        self.mailbox_map: dict[tuple[int, int], int] | None = None
        self.mailbox_enabled: bool | None = None
        self.pos_last = None          # (sub, x, y, t) of the last position send
        # on-screen notices
        self.notify_queue: collections.deque = collections.deque()
        self.notified_items: int | None = None    # None = skip the backlog on connect
        self.notify_cfg = {"received": 2, "sent": 2}      # indices into NOTIFY_LEVELS
        self.notify_setup = False        # YAML thresholds already applied
        self.notify_user_set = False     # /mmzx_notify used (wins over the YAML)
        self.notify_style = "full"       # NOTIFY_STYLES; the YAML sets it on connect
        self.notify_style_user = False   # /mmzx_notify style used (wins over the YAML)
        self.scout_requested: set[int] = set()
        # item icons in the world
        self.icons_enabled = True
        self.debug_log = False           # /mmzx_debug on: diagnostic messages at INFO level
        self.icon_written: tuple[int, bytes] | None = None
        self.icon_by_sub: dict[int, list[tuple[int, int, bool]]] | None = None

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        """Accept only a ROM patched for Archipelago; take the slot name from its header."""
        from CommonClient import logger
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (0x0C, 4, "ROM"),      # game code ARZE
                (0x1000, 6, "ROM"),    # AP magic (rom.py)
                (0x1010, 64, "ROM"),   # slot name
            ])
        except bizhawk.RequestFailedError:
            return False
        if reads[0] != ROM_GAME_CODE:
            return False
        if reads[1] != b"MZXAP\x00":
            logger.info("ERROR: this Mega Man ZX ROM is not patched for "
                        "Archipelago. Generate the .apmmzx patch and open it "
                        "with the launcher to create the patched ROM.")
            return False
        raw = reads[2]
        end = raw.find(b"\x00")
        try:
            self.slot_name = raw[:end if end >= 0 else 64].decode("utf-8")
        except UnicodeDecodeError:
            self.slot_name = None
        ctx.game = self.game
        # the ROM places no items: the client grants everything, start inventory included
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.125
        self.local_checked = set()
        self.ending_ticks = 0
        self.cons_log = None
        self.cons_key = None
        self.cons_requested = False
        self.death_link_setup = False
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.death_induced = False
        self.mailbox_count = None
        self.mailbox_checked = set()
        self.mailbox_enabled = None
        self.pos_last = None
        self.notify_queue.clear()
        self.notified_items = None
        self.notify_setup = False        # re-apply the YAML of the new game
        self.scout_requested = set()
        self.icon_written = None
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        """Log in with the slot name read from the ROM header."""
        if getattr(self, "slot_name", None):
            ctx.auth = self.slot_name

    def _detect_window(self) -> tuple[int, int]:
        """Range [lo, hi) of the progress-block window read once per tick.

        Detect addresses far from the block (the Life Up and Sub Tank capacity
        bytes) go to self._extra_addrs and are read one byte at a time.
        """
        if self._win is not None:
            return self._win
        addrs: list[int] = [a for a, _ in GOAL_BITS] + [a for a, _ in GOAL_BITS_SERPENT]
        for v in LOCATIONS.values():
            det = v.get("detect")
            if not det:
                continue
            if det[0] == "bit":
                addrs.append(det[1])
            elif det[0] in ("all", "any"):
                addrs += [a for a, _ in det[1]]
        near = [a for a in addrs if abs(a - LIVE_BLOCK) < 0x1000]
        self._extra_addrs = sorted({a for a in addrs if abs(a - LIVE_BLOCK) >= 0x1000})
        lo, hi = min(near), max(near) + 1
        self._win = (lo, hi)
        return self._win

    async def _in_game(self, ctx):
        """Return (in_game, state_bytes); the bytes are the guard for every write."""
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (HP, 1, DOM), (GAME_STATE, 4, DOM),
                (TITLE_CAROUSEL_STEP, 1, DOM)])
        except bizhawk.RequestFailedError:
            return False, None
        sub = reads[0][0]
        hp = reads[1][0]
        state_bytes = reads[2]
        state = int.from_bytes(state_bytes, "little")
        # the title and its menus also show gs=0x500, sub=1 and hp=16
        launched = reads[3][0] == 6
        return (launched and sub != 0 and hp > 0 and state == STATE_INGAME), state_bytes

    def _debug(self, msg: str) -> None:
        """Log at INFO after /mmzx_debug on, else at DEBUG (hidden by the client)."""
        from CommonClient import logger
        (logger.info if self.debug_log else logger.debug)(msg)

    async def _stage(self, name: str, coro) -> None:
        """Run one watcher stage and log its first exception.

        The BizHawk framework does not catch exceptions; one would kill the loop.
        """
        try:
            await coro
            self._stage_failed.discard(name)
        except bizhawk.RequestFailedError:
            raise
        except Exception:
            if name not in self._stage_failed:
                self._stage_failed.add(name)
                from CommonClient import logger
                logger.exception("[mmzx] stage '%s' failed (continuing with the rest)" % name)

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        """One tick: seed the title, then detect checks, grant items and repair the game.

        Every gameplay stage runs through _stage; the order and the reason for
        each stage are in docs/client_protocol.md section 3.
        """
        if ctx.server is None or ctx.slot_data is None:
            return

        # DeathLink tag, once per connection
        if not self.death_link_setup:
            self.death_link_setup = True
            self.death_link_enabled = bool(ctx.slot_data.get("death_link", False))
            if self.death_link_enabled:
                await ctx.update_death_link(True)

        # Options
        if not self.mission_setup:
            self.mission_setup = True
            self.mission_auto_accept = bool(ctx.slot_data.get("mission_auto_accept", False))
            self.skip_boss_rush = bool(ctx.slot_data.get("skip_boss_rush", False))
            if self.skip_boss_rush:
                from CommonClient import logger
                logger.info("[mmzx] skip_boss_rush: the D-4 boss rush is skipped (each pair of "
                            "Pseudoroids is marked as beaten when the elevator reaches its stop)")

        # Notice thresholds from the YAML, unless /mmzx_notify already set them
        if not self.notify_setup:
            self.notify_setup = True
            for key in ("received", "sent"):
                val = str(ctx.slot_data.get("notify_" + key, "")).lower()
                if not self.notify_user_set and val in NOTIFY_LEVELS:
                    self.notify_cfg[key] = NOTIFY_LEVELS.index(val)
            style = str(ctx.slot_data.get("notify_style", "")).lower()
            if not self.notify_style_user and style in NOTIFY_STYLES:
                self.notify_style = style
            from CommonClient import logger
            logger.info("[mmzx] on-screen notifications: received=%s, sent=%s, style=%s "
                        "(/mmzx_notify [received|sent] <off|progression|useful|all> | <short|full>)"
                        % (NOTIFY_LEVELS[self.notify_cfg["received"]],
                           NOTIFY_LEVELS[self.notify_cfg["sent"]], self.notify_style))

        # Console commands
        if not self.added_commands:
            self.added_commands = True
            ctx.command_processor.commands["mmzx_teleport"] = _cmd_teleport
            ctx.command_processor.commands["mmzx_flags"] = _cmd_flags
            ctx.command_processor.commands["mmzx_dump"] = _cmd_dump
            ctx.command_processor.commands["mmzx_start"] = _cmd_start
            ctx.command_processor.commands["mmzx_accept"] = _cmd_accept
            ctx.command_processor.commands["mmzx_where"] = _cmd_where
            ctx.command_processor.commands["mmzx_notify"] = _cmd_notify
            ctx.command_processor.commands["mmzx_icons"] = _cmd_icons
            ctx.command_processor.commands["mmzx_debug"] = _cmd_debug

        # Starting state and golden image: both run in the menus too
        await self._start_state_resolve(ctx)
        await self._seed_golden_image(ctx)

        in_game, state_bytes = await self._in_game(ctx)
        if not in_game:
            self.prev_hp = None
            self.ingame_ticks = 0
            return
        guard = (GAME_STATE, state_bytes, DOM)   # only write if still in game
        # Startup debounce: right after launch some structures still hold the boot fill
        self.ingame_ticks = getattr(self, "ingame_ticks", 0) + 1
        if self.ingame_ticks < 3:
            return
        try:
            msg = (await bizhawk.read(ctx.bizhawk_ctx, [(MSG_BANK, 4, DOM)]))[0]
        except bizhawk.RequestFailedError:
            return
        if msg == bytes([0xFF] * 4):
            return

        if self.pending_where:
            self.pending_where = False
            await self._stage("where", self._log_where(ctx))

        # Position for Universal Tracker
        await self._stage("position", self._send_position(ctx))

        # Check detection
        lo, hi = self._detect_window()
        extra = self._extra_addrs
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx,
                                       [(lo, hi - lo, DOM)] + [(a, 1, DOM) for a in extra])
        except bizhawk.RequestFailedError:
            return
        block = reads[0]
        extra_val = {a: reads[1 + i][0] for i, a in enumerate(extra)}

        def bit_set(addr: int, bit: int) -> bool:
            if lo <= addr < hi:
                return bool(block[addr - lo] & (1 << bit))
            if addr in extra_val:
                return bool(extra_val[addr] & (1 << bit))
            return False

        checked = set()
        for name, v in LOCATIONS.items():
            det = v.get("detect")
            if not det:
                continue
            if det[0] == "bit":
                ok = bit_set(det[1], det[2])
            elif det[0] == "all":   # mission completed
                ok = all(bit_set(a, b) for a, b in det[1])
            elif det[0] == "any":   # biometal: either boss of the pair
                ok = any(bit_set(a, b) for a, b in det[1])
            else:
                continue
            if ok:
                loc_id = v["id"]
                if loc_id in ctx.server_locations:
                    checked.add(loc_id)

        # Pickup mailbox
        await self._stage("pickup mailbox", self._poll_pickup_mailbox(ctx))
        checked |= self.mailbox_checked

        if checked != self.local_checked:
            newly = checked - self.local_checked
            if newly:
                await ctx.check_locations(list(checked))
                self._notify_sent(ctx, newly)
            self.local_checked = checked

        # Item icons
        await self._stage("item icons", self._sync_icon_table(ctx))

        # Troop Reinforcement unstick
        await self._stage("troop", self._troop_unstick(ctx, guard))

        # Mission bits restore
        if self.mission_auto_accept:
            await self._stage("mission bits", self._mission_bits_tick(ctx, guard))

        # Diagnostics requested from the console
        if self.flag_watch:
            await self._stage("flags", self._flag_watch_tick(ctx))
        if self.pending_dump:
            self.pending_dump = False
            await self._stage("dump", self._dump_transerver(ctx))

        # Starting state, one shot
        await self._stage("starting state", self._start_state_tick(ctx, guard))

        # Grant items
        await self._stage("items", self._grant_items(ctx, guard))

        # Notices
        await self._stage("notifications", self._notify_tick(ctx))

        # Revert models the player does not own
        await self._stage("models", self._revert_unowned_models(ctx, guard))

        # Mission auto-accept
        if self.mission_auto_accept:
            await self._stage("auto-accept", self._auto_accept_mission(ctx, guard))

        # Boss rush skip
        if self.skip_boss_rush:
            await self._stage("boss rush", self._boss_rush_skip_tick(ctx, guard))

        # DeathLink
        if self.death_link_enabled:
            await self._stage("deathlink", self._handle_death_link(ctx, guard))

        # Go to Transerver
        await self._stage("warp", self._warp_request_tick(ctx, guard))

        # Pending teleport
        if self.pending_teleport is not None:
            sub, x, y = self.pending_teleport
            self.pending_teleport = None
            await self._stage("teleport", self._teleport(ctx, sub, x, y, guard))

        # Goal: Serpent beaten, by the epilogue event or by both D-5 Serpent bits
        if not ctx.finished_game:
            done = (all(bit_set(a, b) for (a, b) in GOAL_BITS)
                    or all(bit_set(a, b) for (a, b) in GOAL_BITS_SERPENT))
            if done:
                from NetUtils import ClientStatus
                ctx.finished_game = True
                await ctx.send_msgs([{"cmd": "StatusUpdate",
                                      "status": ClientStatus.CLIENT_GOAL}])

        # Ending unstick
        await self._stage("ending", self._ending_unstick(ctx, guard))

    async def _log_where(self, ctx) -> None:
        """/mmzx_where: subarea, position, state and mission to the log."""
        from CommonClient import logger
        r = await bizhawk.read(ctx.bizhawk_ctx, [
            (SUBAREA_STABLE, 1, DOM), (PLAYER_POS, 8, DOM), (GAME_STATE, 4, DOM),
            (HP, 1, DOM), (TITLE_CAROUSEL_STEP, 1, DOM), (MISSION_STATE_ADDR, 4, DOM),
            (MISSION_ACTIVE_BYTE, 1, DOM), (0x0214F6C0, 4, DOM), (0x0214FC74, 1, DOM),
            (0x0214F6CF, 1, DOM), (TROOP_MERGE[0], 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
        x = int.from_bytes(r[1][0:4], "little") >> 8
        y = int.from_bytes(r[1][4:8], "little") >> 8
        logger.info("[mmzx] where: sub=%d pos=(%d,%d) gs=%06X hp=%d step=%d mission(state)=%d 462B=%02X handler=%d model=%d auto_accept=%s items=%d"
                    % (r[0][0], x, y, int.from_bytes(r[2], "little"), r[3][0], r[4][0],
                       int.from_bytes(r[5], "little"), r[6][0], int.from_bytes(r[7], "little"), r[8][0],
                       self.mission_auto_accept, len(ctx.items_received)))
        logger.info("[mmzx] where+: handler_state=%02X megamerge(0x02104602.1)=%d cutscene=%d"
                    % (r[9][0], (r[10][0] >> TROOP_MERGE[1]) & 1, r[11][0] & 1))

    async def _send_position(self, ctx) -> None:
        """Publish [subarea, x, y] for Universal Tracker, throttled.

        UT reloads the map tab on every change of the key, so the position goes
        out on a subarea change and otherwise at most once per POS_INTERVAL
        after POS_MIN_DELTA px of movement.
        """
        if not getattr(ctx, "slot", None):
            return
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM), (PLAYER_POS, 8, DOM)])
        except bizhawk.RequestFailedError:
            return
        sub = r[0][0]
        x = int.from_bytes(r[1][0:4], "little") >> 8
        y = int.from_bytes(r[1][4:8], "little") >> 8
        now = time.monotonic()
        last = self.pos_last
        if last is not None and sub == last[0]:
            if now - last[3] < POS_INTERVAL:
                return
            if abs(x - last[1]) < POS_MIN_DELTA and abs(y - last[2]) < POS_MIN_DELTA:
                return
        self.pos_last = (sub, x, y, now)
        await ctx.send_msgs([{
            "cmd": "Set", "key": POS_KEY % ctx.slot, "default": [0, 0, 0],
            "want_reply": False,
            "operations": [{"operation": "replace", "value": [int(sub), int(x), int(y)]}],
        }])

    async def _poll_pickup_mailbox(self, ctx) -> None:
        """Turn new pickup mailbox entries into checks; repeats do nothing.

        The mailbox lives in RAM: when the counter went backwards (emulator
        reset) or on the first read, only the last ring of entries is processed.
        """
        if self.mailbox_enabled is None:
            self.mailbox_enabled = any(bool(ctx.slot_data.get(k, False))
                                       for k in PICKUP_OPTION_KEYS)
        if not self.mailbox_enabled:
            return
        if self.mailbox_map is None:
            self.mailbox_map = {}
            for v in LOCATIONS.values():
                det = v.get("detect")
                if det and det[0] == "mailbox":
                    self.mailbox_map[(int(det[1]), int(det[2]))] = v["id"]
        try:
            raw = (await bizhawk.read(ctx.bizhawk_ctx, [
                (PICKUP_MAILBOX_ADDR, 4 + 4 * PICKUP_MAILBOX_SLOTS, DOM)]))[0]
        except bizhawk.RequestFailedError:
            return
        count = int.from_bytes(raw[:4], "little")
        if self.mailbox_count is None or count < self.mailbox_count:
            start = max(0, count - PICKUP_MAILBOX_SLOTS)      # re-sync
        else:
            start = max(self.mailbox_count, count - PICKUP_MAILBOX_SLOTS)
        new_ids = []
        for k in range(start, count):
            off = 4 + 4 * (k % PICKUP_MAILBOX_SLOTS)
            sub, idx = raw[off], raw[off + 1]
            loc_id = self.mailbox_map.get((sub, idx))
            if loc_id is None or loc_id not in ctx.server_locations:
                continue
            if loc_id not in self.mailbox_checked:
                self.mailbox_checked.add(loc_id)
                new_ids.append(loc_id)
        self.mailbox_count = count
        if new_ids:
            from CommonClient import logger
            names = []
            for i in new_ids:
                try:
                    names.append(ctx.location_names.lookup_in_game(i, "Mega Man ZX"))
                except Exception:
                    names.append(str(i))
            self._debug("[mmzx] pickup collected: %s" % ", ".join(names))

    def _icon_code(self, ctx, loc_id: int) -> int:
        """Icon code of the item scouted at a location, or 0 while unknown.

        Own items with a sprite get it; anything else the logo of its classification.
        """
        info = (getattr(ctx, "locations_info", None) or {}).get(loc_id)
        if info is None:
            return 0
        flags = int(getattr(info, "flags", 0) or 0)
        if getattr(info, "player", None) == ctx.slot:
            name = ITEM_ID_TO_NAME.get(int(info.item))
            icon = ICON_BY_ITEM.get(name)
            if icon:
                return ICON_CODES[icon]
        if flags & 0b001:
            return ICON_CODES["logo_progression"]
        if flags & 0b010:
            return ICON_CODES["logo_useful"]
        return ICON_CODES["logo_filler"]

    async def _sync_icon_table(self, ctx) -> None:
        """Write the icon table of the current subarea: codes and both bitmaps.

        Rewritten when the subarea, the scouts or the checked set change and
        when the ROM lost the header. Refills already sent look vanilla again;
        disks, Life Ups and Sub Tanks stay `present` since they never respawn.
        """
        if self.icon_by_sub is None:
            self.icon_by_sub = {}
            for v in LOCATIONS.values():
                ic = v.get("icon")
                if ic and int(ic[1]) < 128:
                    det = v.get("detect") or [None]
                    self.icon_by_sub.setdefault(int(ic[0]), []).append((v["id"], int(ic[1]), det[0] == "mailbox"))
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM), (ICON_TABLE_ADDR, 2, DOM)])
        except bizhawk.RequestFailedError:
            return
        sub, head = r[0][0], r[1]
        msgs = self._ensure_scouts(ctx)
        if msgs:
            await ctx.send_msgs(msgs)
        done = set(ctx.checked_locations) | self.mailbox_checked
        in_seed = getattr(ctx, "server_locations", None) or set()
        table = bytearray(ICON_TABLE_SIZE)
        table[0], table[1] = sub, 1
        for loc_id, idx, respawns in self.icon_by_sub.get(sub, ()):
            if loc_id in in_seed and not (respawns and loc_id in done):
                table[ICON_TABLE_PRESENT_OFF + (idx >> 3)] |= 1 << (idx & 7)
            if loc_id in done:
                if respawns:
                    table[0x84 + (idx >> 3)] |= 1 << (idx & 7)
                continue
            if self.icons_enabled:
                table[4 + idx] = self._icon_code(ctx, loc_id)
        want = (sub, bytes(table))
        if want == self.icon_written and head[0] == sub and head[1] == 1:
            return
        await bizhawk.write(ctx.bizhawk_ctx, [(ICON_TABLE_ADDR, bytes(table), DOM)])
        self.icon_written = want

    def _ensure_scouts(self, ctx) -> list:
        """Request LocationScouts (no hints) for the locations still missing their info."""
        if self.notify_cfg["sent"] == 0:
            return []
        info = getattr(ctx, "locations_info", None) or {}
        if not info and self.scout_requested:
            self.scout_requested = set()        # the server cleared the info (reconnection)
        pending = set(getattr(ctx, "missing_locations", ())) - set(info) - self.scout_requested
        if not pending:
            return []
        self.scout_requested |= pending
        return [{"cmd": "LocationScouts", "locations": sorted(pending), "create_as_hint": 0}]

    def _notify_sent(self, ctx, newly: set) -> None:
        """Queue "Sent <item> to <player>" for new checks holding another player's item."""
        lvl = self.notify_cfg["sent"]
        if lvl == 0:
            return
        infos = getattr(ctx, "locations_info", None) or {}
        names = getattr(ctx, "player_names", {})
        for loc in sorted(newly):
            info = infos.get(loc)
            if info is None or info.player == ctx.slot or item_level(info.flags) > lvl:
                continue
            if len(self.notify_queue) >= NOTIFY_QUEUE_MAX:
                break
            try:
                item = ctx.item_names.lookup_in_slot(info.item, info.player)
            except Exception:
                item = str(info.item)
            who = names.get(info.player, str(info.player))
            self.notify_queue.append(notify_bytes("Sent ", item, " to " + who, self.notify_style))

    async def _notify_tick(self, ctx) -> None:
        """Queue "Got" notices for new items and push one when the popup is free.

        The backlog present when connecting is not announced.
        """
        msgs = self._ensure_scouts(ctx)
        if msgs and hasattr(ctx, "send_msgs"):
            await ctx.send_msgs(msgs)
        n = len(ctx.items_received)
        if self.notified_items is None:
            self.notified_items = n
        lvl = self.notify_cfg["received"]
        while self.notified_items < n:
            net = ctx.items_received[self.notified_items]
            self.notified_items += 1
            if lvl == 0 or item_level(net.flags) > lvl or len(self.notify_queue) >= NOTIFY_QUEUE_MAX:
                continue
            try:
                item = ctx.item_names.lookup_in_game(net.item, getattr(ctx, "game", "Mega Man ZX"))
            except Exception:
                item = str(net.item)
            tail = ""
            if net.player != ctx.slot:
                tail = " from " + getattr(ctx, "player_names", {}).get(net.player, str(net.player))
            self.notify_queue.append(notify_bytes("Got ", item, tail, self.notify_style))
        if not self.notify_queue:
            return
        try:
            req = (await bizhawk.read(ctx.bizhawk_ctx, [(NOTIFY_ADDR, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        if req != 0:
            return                              # the previous notice is still on screen
        data = self.notify_queue.popleft()
        await bizhawk.write(ctx.bizhawk_ctx, [
            (NOTIFY_ADDR + 4, data, DOM),
            (NOTIFY_ADDR + 2, NOTIFY_DUR.to_bytes(2, "little"), DOM)])
        await bizhawk.write(ctx.bizhawk_ctx, [(NOTIFY_ADDR, b"\x01", DOM)])   # REQ last

    async def _flag_watch_tick(self, ctx) -> None:
        """/mmzx_flags: log the progress-block bits that changed since the snapshot."""
        from CommonClient import logger
        try:
            cur = (await bizhawk.read(
                ctx.bizhawk_ctx, [(FLAG_WATCH_BASE, FLAG_WATCH_LEN, DOM)]))[0]
        except bizhawk.RequestFailedError:
            return
        if self.flag_snap is None:
            self.flag_snap = cur
            return
        changes = []
        for i in range(FLAG_WATCH_LEN):
            diff = cur[i] ^ self.flag_snap[i]
            if diff:
                for b in range(8):
                    if diff & (1 << b):
                        on = bool(cur[i] & (1 << b))
                        changes.append("0x%08X.%d %s" % (
                            FLAG_WATCH_BASE + i, b, "ON" if on else "off"))
        if changes:
            logger.info("[mmzx_flags] changes: " + ", ".join(changes))
            self.flag_snap = cur

    async def _dump_transerver(self, ctx) -> None:
        """/mmzx_dump: log the mission and Transerver flag regions."""
        from CommonClient import logger
        MISSIONS = [  # start flag per mission
            (0x021045DE, 2, "Catch The Maverick"), (0x021045DE, 5, "Locate Giro"),
            (0x021045DF, 1, "Pass The Test"), (0x021045E0, 2, "Troop Reinforcement"),
            (0x021045E1, 3, "Search The Plant"), (0x021045E1, 6, "Find The Survivors"),
            (0x021045E2, 1, "Fight The Mavericks"), (0x021045E4, 1, "Secure The Biometal"),
            (0x021045E4, 5, "Save The People"), (0x021045E5, 1, "Recover The Disk"),
            (0x021045E5, 4, "Attack The Excavators"), (0x021045E6, 0, "Protect The Lab"),
            (0x021045E6, 3, "Protect HQ"), (0x021045E7, 2, "Stop The Dig"),
            (0x021045E7, 5, "Repel The Army"), (0x021045E8, 1, "Destroy Model W"),
        ]
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (0x021045DE, 0x0C, DOM), (0x02104620, 0x14, DOM)])
        except bizhawk.RequestFailedError:
            return
        mis_region, ts_region = r[0], r[1]

        def bit_of(addr, bit):
            base = 0x021045DE
            return bool(mis_region[addr - base] & (1 << bit)) if 0 <= addr - base < len(mis_region) else False

        started = [name for (a, b, name) in MISSIONS if bit_of(a, b)]
        logger.info("[mmzx_dump] mission(0x021045DE): " + mis_region.hex(" "))
        logger.info("[mmzx_dump] transerver(0x02104620): " + ts_region.hex(" "))
        logger.info("[mmzx_dump] idx 0x02104630 = 0x%02X | access 0x02104627/28 = %02X %02X" % (
            ts_region[0x10], ts_region[0x07], ts_region[0x08]))
        logger.info("[mmzx_dump] missions with their start flag set: "
                    + (", ".join(started) if started else "none"))

    @staticmethod
    def _mission_done_bits(name: str):
        """'Completed' bits of a mission (detect 'all' of its location)."""
        v = LOCATIONS.get("Mission - " + name) or {}
        det = v.get("detect")
        if det and det[0] == "all":
            return [(a, b) for a, b in det[1]]
        return []

    async def _mission_bits_tick(self, ctx, guard) -> None:
        """Re-set the extra bits of the active mission if something cleared them."""
        try:
            state = int.from_bytes((await bizhawk.read(
                ctx.bizhawk_ctx, [(MISSION_STATE_ADDR, 4, DOM)]))[0], "little")
        except bizhawk.RequestFailedError:
            return
        rec = next((v for v in MISSION_ACCEPT.values() if v["state"] == state), None)
        extras = (rec or {}).get("extra")
        if not extras:
            return
        done = self._mission_done_bits(rec["name"])
        try:
            cur = await bizhawk.read(ctx.bizhawk_ctx,
                                     [(a, 1, DOM) for a, _ in extras]
                                     + [(a + CANON_OFF, 1, DOM) for a, _ in extras]
                                     + [(a, 1, DOM) for a, _ in done])
        except bizhawk.RequestFailedError:
            return
        n = len(extras)
        if done and all(cur[2 * n + i][0] & (1 << b) for i, (_, b) in enumerate(done)):
            return          # already completed
        writes = []
        for i, (ea, eb) in enumerate(extras):
            if not cur[i][0] & (1 << eb):
                writes.append((ea, bytes([cur[i][0] | (1 << eb)]), DOM))
            if not cur[n + i][0] & (1 << eb):
                writes.append((ea + CANON_OFF, bytes([cur[n + i][0] | (1 << eb)]), DOM))
        if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
            from CommonClient import logger
            self._debug("[mmzx] %s: restored %d mission bits that something had cleared"
                        % (rec["name"], len(writes)))

    async def _troop_unstick(self, ctx, guard) -> None:
        """Re-arm the Giro scene of D-2 while Troop Reinforcement is active.

        The scene needs the start flag set and the megamerge flag clear; dying
        after the megamerge without the Report would leave D-2 empty for good.
        """
        addr, bit = TROOP_MERGE
        saddr, sbit = TROOP_START
        try:
            sub = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        if sub not in TROOP_ROOMS:
            return
        # The start flag is always restored; the megamerge flag only until the
        # D-2 script has passed the merge, since the X-2 report needs it set.
        merged = False
        if sub == 16:
            try:
                rs = (await bizhawk.read(ctx.bizhawk_ctx, [(TROOP_ROOM_OBJ + 0xB, 1, DOM)]))[0][0]
            except bizhawk.RequestFailedError:
                return
            merged = rs >= TROOP_ROOM_MERGED
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (MISSION_STATE_ADDR, 4, DOM), (addr, 1, DOM),
                (addr + CANON_OFF, 1, DOM), (CUTSCENE_FLAG, 1, DOM),
                (saddr, 1, DOM), (saddr + CANON_OFF, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        if int.from_bytes(r[0], "little") != TROOP_STATE or r[3][0] & 1:
            return
        mask = 1 << bit
        smask = 1 << sbit
        stuck_merge = bool((r[1][0] | r[2][0]) & mask) and not merged
        stuck_start = not (r[4][0] & r[5][0] & smask)
        if not (stuck_merge or stuck_start):
            return          # nothing to fix
        done = self._mission_done_bits("Troop Reinforcement")
        if done:
            try:
                vals = await bizhawk.read(ctx.bizhawk_ctx, [(a, 1, DOM) for a, _ in done])
            except bizhawk.RequestFailedError:
                return
            if all(vals[i][0] & (1 << b) for i, (_, b) in enumerate(done)):
                return       # already completed: the bit is legitimate, leave it
        writes, what = [], []
        if stuck_merge:
            if r[1][0] & mask:
                writes.append((addr, bytes([r[1][0] & ~mask]), DOM))
            if r[2][0] & mask:
                writes.append((addr + CANON_OFF, bytes([r[2][0] & ~mask]), DOM))
            if writes:
                what.append("cleared the megamerge flag 0x02104602.1")
        if not (r[4][0] & smask):
            writes.append((saddr, bytes([r[4][0] | smask]), DOM))
        if not (r[5][0] & smask):
            writes.append((saddr + CANON_OFF, bytes([r[5][0] | smask]), DOM))
        if not (r[4][0] & r[5][0] & smask):
            what.append("restored the mission start flag 0x021045E0.2 (the game itself clears it)")
        if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
            from CommonClient import logger
            self._debug("[mmzx] Troop Reinforcement was half done: %s; the Giro scene "
                        "can trigger again" % " and ".join(what))

    async def _ending_unstick(self, ctx, guard) -> None:
        """Install the mission 16 story handler if Serpent died without it.

        Without that handler nobody starts the credits and the screen stays
        white. Runs after the goal, writes only the handler, at the state where
        vanilla waits for Serpent 2's death; the game carries on by itself.
        """
        try:
            sub = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        if sub != ENDING_SUBAREA:
            self.ending_ticks = 0
            return
        saddr, smask = ENDING_SERPENT
        caddr, cbit = GAME_CLEARED
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (saddr, 1, DOM), (caddr, 1, DOM), (CUTSCENE_FLAG, 1, DOM),
                (TROOP_ROOM_OBJ + 0xB, 1, DOM),      # room script of the loaded room
                (STORY_HANDLER_ID, 4, DOM), (STORY_HANDLER_OBJ + 0xB, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        handler_id = int.from_bytes(r[4], "little")
        stuck = ((r[0][0] & smask) == smask                  # Serpent 1 and 2 defeated
                 and not (r[1][0] & (1 << cbit))             # the game has not closed already
                 and not (r[2][0] & 1)                       # no cutscene in progress
                 and r[3][0] == D05_ROOM_TERMINAL            # D-5 script finished
                 and (handler_id != ENDING_HANDLER_ID
                      or r[5][0] < ENDING_HANDLER_STATE))    # handler missing or behind
        if not stuck:
            self.ending_ticks = 0
            return
        self.ending_ticks += 1
        if self.ending_ticks < ENDING_UNSTICK_TICKS:
            return
        obj = bytearray(0x114)
        obj[9] = 0xFF                          # no pending cutscene
        obj[0xB] = ENDING_HANDLER_STATE
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, [
            (STORY_HANDLER_OBJ, bytes(obj), DOM),
            (STORY_HANDLER_ID, ENDING_HANDLER_ID.to_bytes(4, "little"), DOM)], [guard])
        if ok:
            self.ending_ticks = 0
            from CommonClient import logger
            logger.info("[mmzx] the ending had no story handler (white screen after "
                        "Serpent): final cutscene started; the credits follow")

    async def _boss_rush_skip_tick(self, ctx, guard) -> None:
        """Mark Pseudoroid pairs as beaten in the D-4 boss rush (skip_boss_rush).

        A pair is set only once the elevator stands at its stop or the player is
        inside its room: set early, the elevator jumps and drops the player. The
        checkpoint is committed as a pad would, or a death would respawn with
        the handler out of sync and a dead elevator.
        """
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (CUTSCENE_FLAG, 1, DOM),
                (STORY_HANDLER_ID, 4, DOM), (STORY_HANDLER_OBJ + 0xB, 1, DOM),
                (BR.STAGE, 1, DOM), (PLAYER_POS, 8, DOM),
                (BR.FLAG_LEFT, 1, DOM), (BR.FLAG_RIGHT, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        if r[0][0] != BR.SUBAREA or (r[1][0] & 1) or int.from_bytes(r[2], "little") != BR.HANDLER_ID:
            return
        x = int.from_bytes(r[5][0:4], "little") >> 8
        y = int.from_bytes(r[5][4:8], "little") >> 8
        pairs = BR.pairs_to_set(x, y, r[3][0], r[4][0], r[6][0], r[7][0])
        if not pairs:
            return
        # reads for the commit and the repaint (all in one batch)
        reads = [(LIVE_BLOCK, LIVE_BLOCK_LEN, DOM), (STORY_BLOCK, STORY_BLOCK_LEN, DOM),
                 (PLAYER_PERSIST, SCENE_DESC_LEN, DOM), (PLAYER_OBJ + 0xA, 1, DOM),
                 (PLAYER_OBJ + 0x15C, 4, DOM)]
        patch_addrs = [src for k in pairs for (_tx, _ty, src) in BR.PATCHES[k]]
        reads += [(a, 4 + BR.PATCH_W * BR.PATCH_H * 2, DOM) for a in patch_addrs]
        try:
            q = await bizhawk.read(ctx.bizhawk_ctx, reads)
        except bizhawk.RequestFailedError:
            return
        live = bytearray(q[0])
        fl, fr = BR.apply_pairs(r[6][0], r[7][0], pairs)
        live[BR.FLAG_LEFT - LIVE_BLOCK] = fl
        live[BR.FLAG_RIGHT - LIVE_BLOCK] = fr
        persist = bytearray(q[2])
        persist[0:4] = (x << 8).to_bytes(4, "little")       # spawn without fraction, like the doors
        persist[4:8] = (y << 8).to_bytes(4, "little")
        persist[0x11] = (persist[0x11] & 0xFE) | (1 if q[3][0] & 0x10 else 0)
        desc = bytes(persist[:8]) + q[4] + bytes(persist[12:])   # +8 = player's scene word
        patches = {a: q[5 + i] for i, a in enumerate(patch_addrs)}
        writes = [(BR.FLAG_LEFT, bytes([fl]), DOM), (BR.FLAG_RIGHT, bytes([fr]), DOM),
                  (PLAYER_PERSIST, bytes(persist), DOM), (SCENE_DESC, desc, DOM),
                  (CANON_BLOCK, bytes(live), DOM), (STORY_BLOCK_CANON, q[1], DOM)]
        for k in pairs:
            writes += [(a, b, DOM) for a, b in BR.paint_writes(k, patches.get)]
        try:
            ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        except bizhawk.RequestFailedError:
            return
        if ok:
            from CommonClient import logger
            for k in pairs:
                self._debug("[mmzx] boss rush skipped: %s marked as beaten (player at %d,%d); "
                            "checkpoint saved" % (BR.PAIR_NAMES[k], x, y))

    async def _auto_accept_mission(self, ctx, guard) -> None:
        """Accept the mission of the subarea or hub floor just entered (open world).

        Replicates what the console does: snapshot for Abort Mission, start
        flag, state, story handler, extra bits and a checkpoint commit. Never
        re-accepts a completed mission (a second Report would pay again).
        Protect HQ is not in the table; the game launches it on its own.
        """
        try:
            sub = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        if sub == HUB_SUBAREA:
            # Floors whose door leads to a boss room keep it shut until the mission
            # is accepted. Accept near the door, not on arrival, or the floor's
            # console turns into "Abort the mission?".
            try:
                r = await bizhawk.read(ctx.bizhawk_ctx, [(PLAYER_POS, 8, DOM)])
            except bizhawk.RequestFailedError:
                return
            x = int.from_bytes(r[0][0:4], "little") >> 8
            y = int.from_bytes(r[0][4:8], "little") >> 8
            floor = next((fy for fy in HUB_FLOOR_BOSS if abs(y - (fy - 17)) <= 64), None)
            if floor is None or (x > HUB_FLOOR_DOOR_X and not self.force_accept):
                self.last_accept_sub = None
                return
            if self.last_accept_sub == ("hub", floor) and not self.force_accept:
                return
            key = ("hub", floor)
            rec = MISSION_ACCEPT.get(HUB_FLOOR_BOSS[floor])
            from CommonClient import logger
            self._debug("[mmzx] hub floor y=%d (player at %d,%d): mission %s"
                        % (floor, x, y, rec["name"] if rec else "?"))
        else:
            if sub == self.last_accept_sub and not self.force_accept:
                return
            key = sub
            rec = MISSION_ACCEPT.get(sub)
        self.force_accept = False
        if not rec:
            self.last_accept_sub = key
            return
        # already completed: accepting again would allow a second Report
        done_bits = self._mission_done_bits(rec["name"])
        if done_bits:
            try:
                vals = await bizhawk.read(ctx.bizhawk_ctx, [(a, 1, DOM) for a, _ in done_bits])
            except bizhawk.RequestFailedError:
                return
            if all(vals[i][0] & (1 << b) for i, (_, b) in enumerate(done_bits)):
                self.last_accept_sub = key
                from CommonClient import logger
                self._debug("[mmzx] %s already completed: not accepted again" % rec["name"])
                return
        try:
            cur_state = int.from_bytes((await bizhawk.read(
                ctx.bizhawk_ctx, [(MISSION_STATE_ADDR, 4, DOM)]))[0], "little")
        except bizhawk.RequestFailedError:
            return
        if cur_state == rec["state"]:
            self.last_accept_sub = key
            # already active: only heal missing extra bits
            extras = rec.get("extra", [])
            if extras:
                try:
                    cur = await bizhawk.read(ctx.bizhawk_ctx,
                                             [(a, 1, DOM) for a, _ in extras]
                                             + [(a + CANON_OFF, 1, DOM) for a, _ in extras])
                except bizhawk.RequestFailedError:
                    return
                w = []
                for i, (ea, eb) in enumerate(extras):
                    if not cur[i][0] & (1 << eb):
                        w.append((ea, bytes([cur[i][0] | (1 << eb)]), DOM))
                    if not cur[len(extras) + i][0] & (1 << eb):
                        w.append((ea + CANON_OFF, bytes([cur[len(extras) + i][0] | (1 << eb)]), DOM))
                if w and await bizhawk.guarded_write(ctx.bizhawk_ctx, w, [guard]):
                    from CommonClient import logger
                    self._debug("[mmzx] %s was already accepted: restored %d missing mission bits"
                                % (rec["name"], len(w)))
            return
        addr, bit = rec["flag"]
        canon = addr + (CANON_BLOCK - LIVE_BLOCK)
        act, act_c = MISSION_ACTIVE_BYTE, MISSION_ACTIVE_BYTE + (CANON_BLOCK - LIVE_BLOCK)
        cur = await bizhawk.read(ctx.bizhawk_ctx, [
            (addr, 1, DOM), (canon, 1, DOM), (act, 1, DOM), (act_c, 1, DOM),
            (LIVE_BLOCK, LIVE_BLOCK_LEN, DOM), (SCENE_DESC, SCENE_DESC_LEN, DOM),
            (STORY_BLOCK, STORY_BLOCK_LEN, DOM)])
        writes = [
            # mission-start snapshot: what Abort Mission restores
            (BLOCK_MIRROR, cur[4], DOM),
            (SCENE_DESC_MIRROR, cur[5], DOM),
            (STORY_BLOCK_MIRROR, cur[6], DOM),
            (addr, bytes([cur[0][0] | (1 << bit)]), DOM),
            (canon, bytes([cur[1][0] | (1 << bit)]), DOM),
            (MISSION_STATE_ADDR, rec["state"].to_bytes(4, "little"), DOM),
            (MISSION_ACTIVE_FLAG, b"\x01", DOM),
            # "mission in progress" bit, tested by the game's "is mission X active"
            (act, bytes([cur[2][0] | 0x02]), DOM),
            (act_c, bytes([cur[3][0] | 0x02]), DOM),
        ]
        # story handler: without it the mission's cutscenes and flags never run
        obj = bytearray(0x114)
        obj[9] = 0xFF                           # no pending cutscene
        obj[0xB] = int(rec.get("hstate", 0))   # initial handler state
        writes.append((STORY_HANDLER_OBJ, bytes(obj), DOM))
        writes.append((STORY_HANDLER_ID, int(rec["id"]).to_bytes(4, "little"), DOM))
        # extra bits: the "step taken" flags the room scripts test first
        for ea, eb in rec.get("extra", []):
            ecur = await bizhawk.read(ctx.bizhawk_ctx, [(ea, 1, DOM), (ea + CANON_OFF, 1, DOM)])
            writes.append((ea, bytes([ecur[0][0] | (1 << eb)]), DOM))
            writes.append((ea + CANON_OFF, bytes([ecur[1][0] | (1 << eb)]), DOM))
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        from CommonClient import logger
        if ok:
            # Checkpoint commit like a pad, or a death before the first milestone
            # would restore a checkpoint without the mission.
            try:
                cur = await bizhawk.read(ctx.bizhawk_ctx, [
                    (LIVE_BLOCK, 0xE4, DOM), (STORY_BLOCK, 0x11C, DOM)])
                await bizhawk.guarded_write(ctx.bizhawk_ctx, [
                    (CANON_BLOCK, cur[0], DOM), (STORY_BLOCK_CANON, cur[1], DOM)], [guard])
            except bizhawk.RequestFailedError:
                pass
            self.last_accept_sub = key      # only marked if the write went through
            self._debug("[mmzx] open world: mission auto-accepted -> %s" % rec["name"])
        else:
            self._debug("[mmzx] acceptance of %s not applied (game state guard); retrying" % rec["name"])

    async def _start_state_resolve(self, ctx) -> None:
        """Advance the starting-state machine from its datastore key, in menus too.

        0 request, 1 waiting for the reply, 2 apply in gameplay, 3 done.
        """
        if self.start_state >= 2:
            return
        self.start_key = "mmzx_start_applied_%s_%s" % (ctx.team, ctx.slot)
        if self.start_state == 0:
            await ctx.send_msgs([
                {"cmd": "SetNotify", "keys": [self.start_key]},
                {"cmd": "Get", "keys": [self.start_key]},
            ])
            self.start_state = 1
            return
        if self.start_state == 1:
            if self.start_key not in ctx.stored_data:
                return
            self.start_state = 3 if ctx.stored_data[self.start_key] else 2

    async def _seed_golden_image(self, ctx) -> None:
        """Seed the golden image into the LOAD buffer while the title or its menus are up.

        New Game is redirected to LOAD, so every new game starts in the hub,
        also after a Game Over. Only carousel steps 3 and 5 with the state word
        at gameplay or at a Game Over menu are safe: the data select restores
        the SRAM there, and in gameplay the buffer is the live scene. Guarded on both.
        """
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (GAME_STATE, 4, DOM), (TITLE_CAROUSEL_STEP, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        gs = int.from_bytes(r[0], "little")
        step = r[1][0]
        if step not in TITLE_STEPS_SEEDABLE:
            return
        if not (gs == STATE_INGAME or (gs & 0xFF) == 0x07):
            return
        try:
            # the image is patched per slot: starting model and character
            img = build_image(str(ctx.slot_data.get("starting_model", "model_x")),
                              int(ctx.slot_data.get("character", 0) or 0), STARTING_MODELS)
            await bizhawk.guarded_write(
                ctx.bizhawk_ctx,
                [(GOLDEN_IMAGE_ADDR, bytes(img), DOM)],
                [(TITLE_CAROUSEL_STEP, r[1], DOM), (GAME_STATE, r[0], DOM)])
        except bizhawk.RequestFailedError:
            return

    async def _start_state_tick(self, ctx, guard) -> None:
        """Apply the starting state once the player is in the hub (start_state 2).

        Re-asserts the active model until it holds, since the LOAD may force
        Model X once, then marks the datastore key.
        """
        if self.start_state == 3:
            # A new save under an applied slot shows the raw golden signature:
            # Model X owned without its item while the start is another model. Re-arm.
            key = str(ctx.slot_data.get("starting_model", "model_x"))
            rec = STARTING_MODELS.get(key)
            if rec and rec.get("revoke_x"):
                id_to_name = {v["id"]: n for n, v in ITEMS.items()}
                got_x = any(id_to_name.get(net.item) == "Model X" for net in ctx.items_received)
                if not got_x:
                    try:
                        xa, xb = MODEL_X_POSSESSION
                        cf = (await bizhawk.read(ctx.bizhawk_ctx, [(xa, 1, DOM), (SUBAREA_STABLE, 1, DOM)]))
                    except bizhawk.RequestFailedError:
                        return
                    if (cf[0][0] & (1 << xb)) and cf[1][0] == HUB_SUBAREA:
                        from CommonClient import logger
                        logger.info("[mmzx] new save detected (seeded Model X): re-applying the starting state")
                        self.start_state = 2
                        self.start_confirm = 0
                        self.start_retries = 0
        if self.start_state != 2:
            return
        # apply when the game is in the eligible state
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (0x02104627, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        sub, ts_access = r[0][0], r[1][0]
        if sub != HUB_SUBAREA or not (ts_access & 0x10):
            return
        desired_active = await self._apply_start_state(ctx, guard)
        if desired_active is None:
            return   # write did not go through (guard) - retry next tick
        if desired_active == -1:      # unknown model: nothing to confirm
            self.start_confirm = 4
        # the LOAD may overwrite the model once; confirm it holds
        try:
            active_now = (await bizhawk.read(ctx.bizhawk_ctx, [(MODEL, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        self.start_retries += 1
        self.start_confirm = self.start_confirm + 1 if active_now == desired_active else 0
        if self.start_confirm >= 4 or self.start_retries > 600:
            self.start_state = 3
            await ctx.send_msgs([{
                "cmd": "Set", "key": self.start_key, "default": False,
                "want_reply": False,
                "operations": [{"operation": "replace", "value": True}],
            }])

    async def _apply_start_state(self, ctx, guard):
        """Write the starting model's possession and active value; teleport if needed.

        Returns the desired active model, or None if the guard rejected the writes.
        """
        from CommonClient import logger
        key = str(ctx.slot_data.get("starting_model", "model_x"))
        rec = STARTING_MODELS.get(key)
        if rec is None:
            logger.info("[mmzx] unknown starting_model: %r (ignored)" % key)
            return -1   # nothing to confirm; it will be taken as done

        # possessions: revoke X if applicable + grant those of the chosen model
        bit_ops: list[tuple[int, int, bool]] = []   # (addr, bit, on)
        if rec["revoke_x"]:
            xa, xb = MODEL_X_POSSESSION
            bit_ops.append((xa, xb, False))
        for addr, bit in rec["grant"]:
            bit_ops.append((addr, bit, True))

        addrs = sorted({a for a, _, _ in bit_ops})
        writes: list[tuple[int, bytes, str]] = []
        if addrs:
            cur = await bizhawk.read(
                ctx.bizhawk_ctx,
                [(a, 1, DOM) for a in addrs] + [(a + CANON_OFF, 1, DOM) for a in addrs])
            vals = {a: [cur[i][0], cur[len(addrs) + i][0]] for i, a in enumerate(addrs)}
            for addr, bit, on in bit_ops:
                for k in (0, 1):
                    v = vals[addr][k]
                    vals[addr][k] = (v | (1 << bit)) if on else (v & ~(1 << bit))
            for i, a in enumerate(addrs):
                if vals[a][0] != cur[i][0]:
                    writes.append((a, bytes([vals[a][0]]), DOM))
                if vals[a][1] != cur[len(addrs) + i][0]:
                    writes.append((a + CANON_OFF, bytes([vals[a][1]]), DOM))
        writes.append((ACTIVE_MODEL_ADDR, bytes([rec["active"]]), DOM))

        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        if not ok:
            return None

        # a starting Transerver other than the hub means a teleport
        ts_key = str(ctx.slot_data.get("starting_transerver", "guardian_hub"))
        dest = STARTING_TRANSERVERS.get(ts_key)
        if dest and dest[0] != HUB_SUBAREA:
            await self._teleport(ctx, dest[0], dest[1], dest[2], guard)

        if self.start_confirm == 0 and self.start_retries == 0:
            logger.info("[mmzx] starting state applied: model=%s, transerver=%s"
                        % (key, ts_key))
        return rec["active"]

    async def _warp_request_tick(self, ctx, guard) -> None:
        """Serve "Go to Transerver": open the Target Area list, then teleport to the pick.

        The request byte comes from the ROM's menu cave; the selection is read
        on the first tick back in gameplay (-1 = cancelled).
        """
        from CommonClient import logger
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(WARP_REQ, 1, DOM), (TRANSPORT_SEL, 4, DOM)])
        except bizhawk.RequestFailedError:
            return
        req = r[0][0]
        sel = int.from_bytes(r[1], "little", signed=True)
        if self.transport_wait:
            self.transport_wait = False
            if 0 <= sel < len(STATION_ROOMS):
                letter = STATION_ROOMS[sel][0].upper()
                y = HUB_FLOOR_Y.get(letter)
                if y is not None:
                    self.pending_teleport = (HUB_SUBAREA, HUB_X, y - HUB_PAD_DY)
                    self._debug("[mmzx] Go to Transerver -> Area %s (hub floor %s)"
                                % (STATION_ROOMS[sel][0].upper() + "-" + STATION_ROOMS[sel][1:].lstrip("0"), letter))
            else:
                self._debug("[mmzx] Go to Transerver: list cancelled")
            return
        if req != 1:
            return
        # open the game's list with no current station; retried if the guard fails
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, [
            (WARP_REQ, b"\x00", DOM),
            (TRANSPORT_SEL, (0xFFFFFFFF).to_bytes(4, "little"), DOM),
            (GAME_STATE, STATE_TARGET_AREA.to_bytes(4, "little"), DOM),
            (GAME_STATE + 4, b"\x00\x00\x00\x00", DOM),
            (GAME_STATE + 8, b"\x00\x00\x00\x00", DOM),
        ], [guard])
        if ok:
            self.transport_wait = True
            self._debug("[mmzx] Go to Transerver: opening the Target Area list")

    async def _teleport(self, ctx, sub, x, y, guard) -> None:
        """Request a scene load at (sub, x, y), guarded on gameplay."""
        writes = [
            (SCENE_DESC + 0x00, (x << 8).to_bytes(4, "little"), DOM),
            (SCENE_DESC + 0x04, (y << 8).to_bytes(4, "little"), DOM),
            (SCENE_DESC + 0x08, sub.to_bytes(4, "little"), DOM),
            (SCENE_DESC + 0x11, b"\x01", DOM),
            (GAME_STATE, STATE_LOAD.to_bytes(4, "little"), DOM),
            (GAME_STATE + 4, b"\x00\x00\x00\x00", DOM),
            (GAME_STATE + 8, b"\x00\x00\x00\x00", DOM),
        ]
        await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])

    async def _grant_items(self, ctx, guard) -> None:
        """Write the received items into the game.

        Idempotent grants (bits, capacities, levels) are recomputed from the
        whole list every tick; consumables are applied once per game, stamped
        with the play time (see _consumables_resolve).
        """
        id_to_item = {v["id"]: (name, v["grant"]) for name, v in ITEMS.items()}
        # copies received by name (progressive: 1 = 1st half, 2 = both)
        name_count: dict[str, int] = {}
        for net in ctx.items_received:
            entry = id_to_item.get(net.item)
            if entry:
                name_count[entry[0]] = name_count.get(entry[0], 0) + 1

        # count received per grant type
        n_lifeup = n_subtank = 0
        live_bits: set[tuple[int, int]] = set()    # (live_addr, bit) idempotent
        consumables: list[str] = []    # E-Crystals / 1-Up received, in server order
        cardkeys: set[tuple[int, int]] = set()     # (addr, bit) of the received keys
        for net in ctx.items_received:
            entry = id_to_item.get(net.item)
            if not entry:
                continue
            name, grant = entry
            kind = grant[0]
            if kind == "lifeup":
                n_lifeup += 1
            elif kind == "subtank":
                n_subtank += 1
            elif kind == "live_bit":
                if name.endswith("Card Key"):
                    cardkeys.add((grant[1], grant[2]))   # authoritative possession
                else:
                    live_bits.add((grant[1], grant[2]))
            elif kind == "progressive":
                # copy k sets bit k (half 1, half 2...)
                for k, (addr, bit) in enumerate(grant[1]):
                    if name_count.get(name, 0) > k:
                        live_bits.add((addr, bit))
            elif kind == "transerver":
                # the destination's bit in the Transport bitfield (every item has one)
                if len(grant) >= 3:
                    live_bits.add((grant[1], grant[2]))
            elif kind in ("ecrystals", "oneup"):
                consumables.append(kind)

        # Event gates: some story gates open for everyone; the Slither gate
        # (D-2 to D-4) once the six model items are held.
        for fl in EVENT_GATES_OPEN:
            live_bits.add(tuple(EVENT_GATES[fl]))
        received = {id_to_item[net.item][0] for net in ctx.items_received if net.item in id_to_item}
        if all(n in received for n in ("Model X", "Model ZX", "Progressive Model HX",
                                       "Progressive Model FX", "Progressive Model LX",
                                       "Progressive Model PX")):
            for fl in EVENT_GATES_ALL6:
                live_bits.add(tuple(EVENT_GATES[fl]))

        writes: list[tuple[int, bytes, str]] = []

        # Weapon Energy for models granted by item: raise the pair's victory
        # levels to the cap and fill the bar, once (see BOSS_LEVELS).
        owned_models = [m for m, (item, _a, _b) in MODEL_POSSESSION.items()
                        if m in MODEL_LEVEL_IDX and item in received]
        if owned_models:
            lv = await bizhawk.read(ctx.bizhawk_ctx, [(BOSS_LEVELS, 8, DOM)])
            lv = lv[0]
            for m in owned_models:
                i0, i1 = MODEL_LEVEL_IDX[m]
                full = name_count.get(MODEL_POSSESSION[m][0], 0) >= 2
                if full and lv[i0] + lv[i1] < 8:
                    for i in (i0, i1):
                        writes.append((BOSS_LEVELS + i, b"\x04", DOM))
                        writes.append((BOSS_LEVELS + i + CANON_OFF, b"\x04", DOM))
                    writes.append((WE_BASE + m, bytes([WE_FULL * 2]), DOM))
                elif not full and lv[i0] + lv[i1] < 4:
                    v = bytes([4 - lv[i1]])
                    writes.append((BOSS_LEVELS + i0, v, DOM))
                    writes.append((BOSS_LEVELS + i0 + CANON_OFF, v, DOM))
                    writes.append((WE_BASE + m, bytes([WE_FULL]), DOM))

        # idempotent bits go to live (effect now) and canonical (persistence)
        if live_bits:
            by_addr: dict[int, int] = {}
            for addr, bit in live_bits:
                by_addr[addr] = by_addr.get(addr, 0) | (1 << bit)
            addrs = sorted(by_addr)
            cur = await bizhawk.read(ctx.bizhawk_ctx,
                                     [(a, 1, DOM) for a in addrs]
                                     + [(a + CANON_OFF, 1, DOM) for a in addrs])
            for k, a in enumerate(addrs):
                mask = by_addr[a]
                live_v, canon_v = cur[k][0], cur[len(addrs) + k][0]
                if live_v & mask != mask:
                    writes.append((a, bytes([live_v | mask]), DOM))
                if canon_v & mask != mask:
                    writes.append((a + CANON_OFF, bytes([canon_v | mask]), DOM))

        # Card Keys: the game also hands them out as mission rewards, so exactly
        # the received set is written; the neighbouring bits are unrelated flags.
        want_keys = {a: 0 for a in CARDKEY_MASKS}
        for a, b in cardkeys:
            want_keys[a] = want_keys.get(a, 0) | (1 << b)
        kaddrs = sorted(CARDKEY_MASKS)
        kcur = await bizhawk.read(ctx.bizhawk_ctx,
                                  [(a, 1, DOM) for a in kaddrs]
                                  + [(a + CANON_OFF, 1, DOM) for a in kaddrs])
        for k, a in enumerate(kaddrs):
            mask = CARDKEY_MASKS[a]
            for off, cur in ((0, kcur[k][0]), (CANON_OFF, kcur[len(kaddrs) + k][0])):
                new = (cur & ~mask) | (want_keys[a] & mask)
                if new != cur:
                    writes.append((a + off, bytes([new]), DOM))

        # Life Up capacity is exactly the received count; the physical pickup
        # only marks its "collected" nibble (the check) and grants nothing.
        nlu = min(4, n_lifeup)
        lu_mask = (1 << nlu) - 1
        cur_lu, cur_hpmax = (await bizhawk.read(
            ctx.bizhawk_ctx, [(LIFEUP_BYTE, 1, DOM), (HPMAX, 1, DOM)]))
        if (cur_lu[0] & 0x0F) != lu_mask:
            writes.append((LIFEUP_BYTE, bytes([(cur_lu[0] & 0xF0) | lu_mask]), DOM))
        hpmax = min(0x20, 0x10 + 4 * nlu)   # max HP follows the AP count
        if cur_hpmax[0] != hpmax:
            writes.append((HPMAX, bytes([hpmax]), DOM))

        # Sub Tanks: same rule
        nst = min(4, n_subtank)
        st_mask = (1 << nst) - 1
        cur_st = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBTANK_BYTE, 1, DOM)]))[0][0]
        if (cur_st & 0x0F) != st_mask:
            writes.append((SUBTANK_BYTE, bytes([(cur_st & 0xF0) | st_mask]), DOM))

        # Consumables are applied once per game. Each batch is stamped with the
        # play time, which grows every frame, never goes back on death and returns
        # to the save's value on Continue or LOAD: a batch stamped later than the
        # current play time was rewound and is granted again; a reconnect rewinds nothing.
        new_consumables: list[str] = []
        pt = 0
        if consumables:
            if self.cons_log is None:
                await self._consumables_resolve(ctx)
            if self.cons_log is not None:
                pt = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(PLAYTIME, 4, DOM)]))[0], "little")
                if pt > 0:
                    new_consumables = consumables[_consumables_present(self.cons_log, pt):]
        if new_consumables:
            raw = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(ECRYSTALS, 4, DOM)]))[0], "little")
            ec = raw & 0xFFFFFF
            add = sum(50 for k in new_consumables if k == "ecrystals")
            ec = min(99999, ec + add)
            writes.append((ECRYSTALS, ((raw & 0xFF000000) | ec).to_bytes(4, "little"), DOM))
            # 1-Up: one life each, cap 99
            n1 = sum(1 for k in new_consumables if k == "oneup")
            if n1:
                lives = (await bizhawk.read(ctx.bizhawk_ctx, [(LIVES, 1, DOM)]))[0][0]
                writes.append((LIVES, bytes([min(99, lives + n1)]), DOM))

        if writes:
            ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
            # consumables count as applied only if the write went through
            if ok and new_consumables:
                self.cons_log = [e for e in self.cons_log if e[1] <= pt] + [[len(consumables), pt]]
                await ctx.send_msgs([{
                    "cmd": "Set", "key": self.cons_key, "default": [],
                    "want_reply": False,
                    "operations": [{"operation": "replace", "value": self.cons_log}],
                }])

    async def _consumables_resolve(self, ctx) -> None:
        """Load the applied-consumables log from the datastore; None until it arrives.

        Nothing is granted meanwhile, so a reconnect never adds a batch twice.
        """
        if self.cons_key is None:
            self.cons_key = CONS_KEY % (ctx.team, ctx.slot)
        if not self.cons_requested:
            await ctx.send_msgs([
                {"cmd": "SetNotify", "keys": [self.cons_key]},
                {"cmd": "Get", "keys": [self.cons_key]},
            ])
            self.cons_requested = True
            return
        if self.cons_key not in ctx.stored_data:
            return
        val = ctx.stored_data[self.cons_key]
        log = []
        if isinstance(val, list):
            for e in val:
                if isinstance(e, list) and len(e) == 2 and all(isinstance(x, int) for x in e):
                    log.append([e[0], e[1]])
        self.cons_log = log

    def _fallback_model(self, ctx, owned: dict) -> int:
        """Model to revert to: last legitimate, YAML start, any owned, else Hu."""
        if owned.get(self.last_legit_model, False):
            return self.last_legit_model
        key = str((ctx.slot_data or {}).get("starting_model", "model_x"))
        rec = STARTING_MODELS.get(key)
        if rec and owned.get(int(rec.get("active", 0)), False):
            return int(rec["active"])
        for m in sorted(owned):
            if m and owned[m]:
                return m
        return 0

    async def _revert_unowned_models(self, ctx, guard) -> None:
        """Revert an unowned active form and clear possession bits without their item.

        Boss victories, the Troop megamerge and the LOAD change the active model
        or set shared bits; ownership must come from items alone. Skipped during
        cutscenes and until the first ReceivedItems (the list is never empty).
        """
        if not ctx.items_received:
            return
        counts: dict[int, int] = {}
        for net in ctx.items_received:
            counts[net.item] = counts.get(net.item, 0) + 1
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(MODEL, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        if r[1][0] & 1:
            return   # cutscene running: leave the model alone
        active = r[0][0]
        owned = {m: counts.get(ITEMS.get(item, {}).get("id"), 0) >= 1
                 for m, (item, _a, _b) in MODEL_POSSESSION.items()}
        # 2nd half (progressive): only with 2 copies received
        full = {m: counts.get(ITEMS.get(MODEL_POSSESSION[m][0], {}).get("id"), 0) >= 2
                for m in MODEL_PART2}
        # With hu_in_pool Hu is just another form. The game refuses to transform
        # with a single owned category, so a scene that ends in Hu (the M-1 seal
        # one does) would leave the player stuck in Hu for good.
        owned[0] = (not (ctx.slot_data or {}).get("hu_in_pool")
                    or counts.get(ITEMS.get("Model Hu", {}).get("id"), 0) >= 1)
        writes: list[tuple[int, bytes, str]] = []
        notes: list[str] = []
        if owned.get(active, False):
            self.last_legit_model = active   # Hu, or form owned via AP: legitimate
        else:
            fallback = self._fallback_model(ctx, owned)
            if fallback != active:   # with nothing better (Hu gated and 0 biometals) leave it
                writes.append((MODEL, bytes([fallback]), DOM))
                notes.append("model %d not owned -> reverting to %d" % (active, fallback))
        # possession bits without their item are cleared in both copies
        addrs = sorted({a for _i, a, _b in MODEL_POSSESSION.values()}
                       | {a for a, _b in MODEL_PART2.values()})
        try:
            cur = await bizhawk.read(
                ctx.bizhawk_ctx,
                [(a, 1, DOM) for a in addrs] + [(a + CANON_OFF, 1, DOM) for a in addrs])
        except bizhawk.RequestFailedError:
            return
        vals = {a: [cur[i][0], cur[len(addrs) + i][0]] for i, a in enumerate(addrs)}
        for m, (item, a, bit) in MODEL_POSSESSION.items():
            if owned[m]:
                continue
            for k in (0, 1):
                if vals[a][k] & (1 << bit):
                    vals[a][k] &= ~(1 << bit) & 0xFF
                    notes.append("%s owned without its item -> clearing 0x%08X.%d%s"
                                 % (item, a, bit, "" if k == 0 else " (canonical)"))
        for m, (a, bit) in MODEL_PART2.items():
            if full.get(m, False):
                continue
            for k in (0, 1):
                if vals[a][k] & (1 << bit):
                    vals[a][k] &= ~(1 << bit) & 0xFF
                    notes.append("second half of %s without its second copy -> clearing 0x%08X.%d%s"
                                 % (MODEL_POSSESSION[m][0], a, bit, "" if k == 0 else " (canonical)"))
        for i, a in enumerate(addrs):
            if vals[a][0] != cur[i][0]:
                writes.append((a, bytes([vals[a][0]]), DOM))
            if vals[a][1] != cur[len(addrs) + i][0]:
                writes.append((a + CANON_OFF, bytes([vals[a][1]]), DOM))
        if not writes:
            return
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        if ok:
            from CommonClient import logger
            for n in notes:
                self._debug("[mmzx] %s" % n)

    async def _handle_death_link(self, ctx, guard) -> None:
        """Send the game's deaths and apply the received ones.

        A death is HP going from above zero to zero, unless this client caused
        it. A received death is applied the way the game does it (HP 0 plus the
        dying state bytes; HP alone does not kill), once the player has control.
        """
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (HP, 1, DOM), (CUTSCENE_FLAG, 1, DOM), (PLAYER_OBJ + 0x11, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        hp, cut, state = r[0][0], r[1][0], r[2][0]

        if self.prev_death_link is None:
            self.prev_death_link = ctx.last_death_link

        # send: a real death, unless we caused it (no echo)
        if self.prev_hp is not None and self.prev_hp > 0 and hp == 0:
            if self.death_induced:
                self.death_induced = False
            else:
                await ctx.send_death(f"{ctx.player_names[ctx.slot]} ran out of energy.")
            self.prev_death_link = ctx.last_death_link  # do not self-receive our own
        self.prev_hp = hp

        # receive
        if ctx.last_death_link > self.prev_death_link:
            self.prev_death_link = ctx.last_death_link
            self.pending_death = True

        if not self.pending_death:
            return
        if hp == 0 or (cut & 1) or state != 0:
            return                      # no control: retried on the next tick
        writes = [(HP, b"\x00", DOM),
                  (PLAYER_OBJ + 0x11, bytes([DEATH_STATE, 2, 0]), DOM)]
        try:
            ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        except bizhawk.RequestFailedError:
            return
        if ok:
            self.pending_death = False
            self.death_induced = True
            from CommonClient import logger
            logger.info("[mmzx] DeathLink received: death applied")


def _cmd_teleport(self, *args) -> None:
    """Anti-softlock teleport: no args for the hub, an area letter for its floor, or sub x y."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    if len(args) >= 1 and str(args[0]).strip().upper() in HUB_FLOOR_Y:
        letter = str(args[0]).strip().upper()
        # on the floor's console pad; any lower and the player falls through the floor
        y = HUB_FLOOR_Y[letter] - HUB_PAD_DY
        handler.pending_teleport = (HUB_SUBAREA, HUB_X, y)
        logger.info(f"Teleport queued -> hub, floor {letter} ({HUB_X},{y}).")
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
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.pending_where = True
    logger.info("mmzx_where: queued (logged on the next in-game tick).")


def _cmd_accept(self, *args) -> None:
    """Force-accept the mission of the current area or hub floor on the next tick."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.force_accept = True
    handler.last_accept_sub = None
    logger.info("mmzx_accept: queued (applied on the next in-game tick).")


def _cmd_start(self, *args) -> None:
    """Re-apply the YAML starting state (model and Transerver), e.g. after a new save."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.start_state = 2   # apply on the next eligible tick
    handler.start_confirm = 0
    handler.start_retries = 0
    logger.info("mmzx_start: queued (applied once you are in the hub, in game).")


def _cmd_flags(self, *args) -> None:
    """Diagnostic: /mmzx_flags on|off traces the progress-block bits that change."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    arg = (args[0].lower() if args else "on")
    if arg in ("off", "0", "stop"):
        handler.flag_watch = False
        handler.flag_snap = None
        logger.info("mmzx_flags: OFF")
    else:
        handler.flag_watch = True
        handler.flag_snap = None   # re-taken on the next tick
        logger.info("mmzx_flags: ON (snapshot on the next in-game frame; "
                    "now report the mission and watch the bits logged as ON)")


def _cmd_dump(self, *args) -> None:
    """Diagnostic: log the mission and Transerver flag regions."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.pending_dump = True
    logger.info("mmzx_dump: queued (dumped on the next in-game frame).")


def _cmd_notify(self, *args) -> None:
    """Notice levels: /mmzx_notify [received|sent] <off|progression|useful|all> | <short|full>."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
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
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    if args and str(args[0]).lower() in ("on", "off"):
        handler.icons_enabled = str(args[0]).lower() == "on"
        handler.icon_written = None
    elif args:
        logger.error("usage: /mmzx_icons [on|off]")
        return
    logger.info("[mmzx] in-game item icons: %s" % ("on" if handler.icons_enabled else "off"))


def _cmd_debug(self, *args) -> None:
    """Show the client's diagnostic messages: /mmzx_debug [on|off]."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    if args and str(args[0]).lower() in ("on", "off"):
        handler.debug_log = str(args[0]).lower() == "on"
    elif args:
        logger.error("usage: /mmzx_debug [on|off]")
        return
    logger.info("[mmzx] diagnostic messages: %s" % ("on" if handler.debug_log else "off"))
