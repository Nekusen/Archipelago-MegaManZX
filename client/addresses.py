"""RAM addresses, structure layouts and the tables derived from data.py.

Everything the client reads or writes is named here.
"""

from ..data import (
    CANON_BLOCK, GOAL_BITS, GOAL_BITS_SERPENT, ITEMS, LIVE_BLOCK, LOCATIONS, PICKUP_TABLE_ADDR,
    WARP_DESTINATIONS)
from ..goal import DISK_ITEM
from ..rom.table import BITMAP_LEN, CHECKED_OFF, COLLECTED_OFF, FLAGS_OFF, PICKUP_SLOTS


GAME = "Mega Man ZX"
DOM = "ARM9 System Bus"

# Items by id, and the recipes derived from data.ITEMS
ITEM_ID_TO_NAME = {v["id"]: n for n, v in ITEMS.items()}
ITEM_BY_ID = {v["id"]: (n, v["grant"]) for n, v in ITEMS.items()}
# Active model value to its item; the possession bit (and the second-half bit of
# a progressive model) comes from the item's grant recipe.
MODEL_ITEMS = {1: "Model X", 2: "Model ZX", 3: "Progressive Model HX", 4: "Progressive Model FX",
               5: "Progressive Model LX", 6: "Progressive Model PX", 7: "Model OX"}
MODEL_POSSESSION: dict[int, tuple[str, int, int]] = {}   # active value: (item, address, bit)
MODEL_SECOND_HALF: dict[int, tuple[int, int]] = {}       # level-2 charged attack and the larger WE cap
for _m, _item in MODEL_ITEMS.items():
    _g = ITEMS[_item]["grant"]
    if _g[0] == "progressive":
        MODEL_POSSESSION[_m] = (_item, int(_g[1][0][0]), int(_g[1][0][1]))
        MODEL_SECOND_HALF[_m] = (int(_g[1][1][0]), int(_g[1][1][1]))
    else:
        MODEL_POSSESSION[_m] = (_item, int(_g[1]), int(_g[2]))
# Without progressive_models the pool holds one full item per progressive model instead.
FULL_MODEL_ITEMS = {3: "Model HX", 4: "Model FX", 5: "Model LX", 6: "Model PX"}
# With hu_in_pool the human form is owned through this bit of the progress block.
HU_POSSESSION = (int(ITEMS["Model Hu"]["grant"][1]), int(ITEMS["Model Hu"]["grant"][2]))
# The vanilla seal of the final area, for a seed without goal requirements in its slot data
SIX_MODELS = ("Model X", "Model ZX", "Progressive Model HX", "Progressive Model FX",
              "Progressive Model LX", "Progressive Model PX")
DISK_ITEM_ID = ITEMS[DISK_ITEM]["id"]
# Disk locations to their "taken" bit, which the client also sets for disks collected elsewhere
DISK_TAKEN_BITS = {v["id"]: (int(v["detect"][1]), int(v["detect"][2]))
                   for v in LOCATIONS.values() if v["category"] == "disk" and v.get("detect")}
# The game hands out Card Keys as mission rewards, so the received set is
# written as-is over these bits every tick.
CARDKEY_MASKS: dict[int, int] = {}
for _kn, _kv in ITEMS.items():
    if _kn.endswith("Card Key") and _kv["grant"][0] == "live_bit":
        CARDKEY_MASKS[_kv["grant"][1]] = CARDKEY_MASKS.get(_kv["grant"][1], 0) | (1 << _kv["grant"][2])
# Slots of the pickup table (rom/table.py): the bit of each physical location in
# the `checked` and `collected` bitmaps; refills are the ones the game records
SLOT_LOCATIONS = {slot: LOCATIONS[n]["id"] for n, slot in PICKUP_SLOTS.items()}
LOCATION_SLOTS = {loc: slot for slot, loc in SLOT_LOCATIONS.items()}
REFILL_SLOTS = frozenset(slot for n, slot in PICKUP_SLOTS.items() if LOCATIONS[n]["detect"][0] == "mailbox")

# Progress block (LIVE_BLOCK and its canonical copy CANON_BLOCK come from data.py)
CANON_OFF = CANON_BLOCK - LIVE_BLOCK
LIVE_BLOCK_LEN = 0xE4
# Detect bits this close to the block share one read per tick; the far ones (the
# Life Up and Sub Tank capacity bytes) are read one byte at a time.
DETECT_WINDOW_RADIUS = 0x1000
_detect_addrs = [a for a, _ in GOAL_BITS] + [a for a, _ in GOAL_BITS_SERPENT]
for _v in LOCATIONS.values():
    _det = _v.get("detect")
    if _det and _det[0] == "bit":
        _detect_addrs.append(_det[1])
    elif _det and _det[0] in ("all", "any"):
        _detect_addrs += [a for a, _ in _det[1]]
_near = [a for a in _detect_addrs if abs(a - LIVE_BLOCK) < DETECT_WINDOW_RADIUS]
DETECT_WINDOW = (min(_near), max(_near) + 1)             # [lo, hi)
DETECT_FAR = sorted({a for a in _detect_addrs if abs(a - LIVE_BLOCK) >= DETECT_WINDOW_RADIUS})
PLAYER_POS = 0x0214FB64      # two u32: x << 8, y << 8
POS_KEY = "mmzx_pos_%d"     # data storage: [subarea, x, y] for UT
POS_INTERVAL = 1.0
POS_MIN_DELTA = 48
PLAYTIME = 0x021602A8        # frames; the game clock for consumables
CONS_KEY = "mmzx_consumables_%s_%s"  # data storage: [[applied, playtime], ...]

# Weapon Energy: a model's cap comes from the victory levels of its two bosses
# (data.MODEL_BOSS_LEVEL_IDX), which only a real victory writes.
BOSS_LEVELS = 0x02104634
WE_BASE = 0x0214FC92          # + active model = current WE
WE_FULL = 16
MSG_BANK = 0x02104588         # 0xFFFFFFFF until boot has finished

# Player object (the active model byte is data.ACTIVE_MODEL_ADDR)
PLAYER_OBJ = 0x0214FB08
PLAYER_FACING_OFF = 0x0A        # bit 4 = facing
PLAYER_FACING_MASK = 0x10
PLAYER_STATE_OFF = 0x11         # 0 = the player has control
DEATH_STATE = 0x0A              # state byte while hurt or dying
DEATH_SUBSTATE = 2              # with DEATH_STATE: the death animation is running
# The hit flags of the frame; a lethal one makes the model code turn the hurt
# state into the death sequence. Forcing the death substate by hand skips that
# and leaves the human form hanging.
LETHAL_HIT_OFF = 0x13B
LETHAL_HIT_MASK = 0x78
PLAYER_SCENE_WORD_OFF = 0x15C   # subarea of the current room
HP = 0x0214FBB2
# Persistent block; the scene descriptor uses the same layout
PLAYER_PERSIST = 0x0214FC5C
DESC_SPAWN_X_OFF = 0x00         # x << 8
DESC_SPAWN_Y_OFF = 0x04         # y << 8
DESC_SUBAREA_OFF = 0x08
DESC_FACING_OFF = 0x11          # bit 0
LIVES = 0x0214FC6C
LIVES_CAP = 99
ECRYSTALS = 0x0214FC70          # u24; the high byte of the word is kept
ECRYSTALS_MASK = 0x00FFFFFF
ECRYSTALS_HIGH_MASK = 0xFF000000
ECRYSTALS_PER_ITEM = 50
ECRYSTALS_CAP = 99999
HPMAX = 0x0214FC76
HP_BASE = 0x10
HP_PER_LIFEUP = 4
HP_CAP = 0x20
LIFEUP_BYTE = 0x0214FC77        # low nibble capacity, high nibble slots collected
SUBTANK_BYTE = 0x0214FC78
CAPACITY_NIBBLE = 0x0F
COLLECTED_NIBBLE = 0xF0
LIFEUP_SLOTS = 4
SUBTANK_SLOTS = 4

# Scene and title
SUBAREA_STABLE = 0x02108228
GAME_STATE = 0x0215E6D8
STATE_INGAME = 0x500
STATE_LOAD = 0x400            # scene load (teleport)
STARTUP_TICKS = 3             # in-game ticks to wait before the first read
BOOT_FILL = b"\xff\xff\xff\xff"
# The title and its menus share the gameplay state word; the carousel step
# tells them apart: 6 is a launched game.
TITLE_CAROUSEL_STEP = 0x0214CD70
TITLE_STEP_LAUNCHED = 6
SCENE_DESC = 0x0216047C       # spawn x, y and subarea; layout of PLAYER_PERSIST
SCENE_DESC_LEN = 0x6C

# Missions and story
MISSION_ACTIVE_BYTE = 0x0210462B   # .1 mission accepted, .2 story mission
MISSION_ACCEPTED_MASK = 0x02
# Boss room scripts set these while a fight runs and clear them when the boss
# dies; doors everywhere check them. Leaving the fight by teleport carries them
# out of the room, so the client releases them once the player is elsewhere.
BOSS_LOCKDOWN = (0x0210462A, 7)
BOSS_ACTIVE = (0x0210462B, 0)
STORY_BLOCK = 0x0214F6BC           # +4 mission id, +8 handler object
STORY_BLOCK_LEN = 0x11C
STORY_BLOCK_CANON = 0x02160554     # checkpoint copy, restored on death
# Abort Mission restores these three mirrors, so a forced accept refreshes them
# first or the abort would bring back whatever the golden image held.
BLOCK_MIRROR = 0x02160398
SCENE_DESC_MIRROR = 0x021604E8
STORY_BLOCK_MIRROR = 0x02160670
CUTSCENE_FLAG = 0x0214F502         # bit 0 = cutscene running
# Script objects: the room script and the story handler share the layout
ROOM_SCRIPT_OBJ = 0x0214F3EC       # room script object of the loaded room
STORY_HANDLER_ID = 0x0214F6C0
STORY_HANDLER_OBJ = 0x0214F6C4
STORY_HANDLER_LEN = 0x114
SCRIPT_CUTSCENE_OFF = 9            # pending cutscene id
SCRIPT_STATE_OFF = 0xB
CUTSCENE_NONE = 0xFF
STORY_HANDLER_STATE = STORY_HANDLER_OBJ + SCRIPT_STATE_OFF
ROOM_SCRIPT_STATE = ROOM_SCRIPT_OBJ + SCRIPT_STATE_OFF
# O-2's room script reads its mini-boss flag only when the room loads: it waits
# for the fight in one state and skips ahead with the flag set, so a flag set
# after the load (an arrival from another area) needs the state moved as well.
O02_SCRIPT_MINIBOSS_WAIT = 1
O02_SCRIPT_MINIBOSS_BEATEN = 4
O02_MINIBOSS_FLAG = (0x021045CE, 1)
MINIBOSSES_KEY = "mmzx_minibosses_%s_%s"  # data storage: [[addr, bit], ...] beaten once
# Troop Reinforcement: the Giro scene at the end of D-2 only arms with the
# start flag set and the megamerge flag clear. Dying after the megamerge
# without the Report would leave D-2 empty for good, so the client repairs
# both while Troop is active and not yet completed.
TROOP_NAME = "Troop Reinforcement"
TROOP_STATE = 162                  # mission state "Troop accepted"
TROOP_MERGE = (0x02104602, 1)
TROOP_START = (0x021045E0, 2)
TROOP_ROOMS = (15, 16, 17)         # D-1 to D-3, where the scene arms
TROOP_MERGE_SUBAREA = 16           # D-2
D02_ROOM_MERGED = 7                # D-2 script state once merged
# Save The People: the cell and prisoners of I-3 exist only after the handler's
# cell scene, which needs the I-1 entrance first; from the I-3 pad the client
# moves the handler along itself (missions.people_unstick).
PEOPLE_NAME = "Save The People"
PEOPLE_STATE = 197                 # mission state "Save The People accepted"
PEOPLE_HANDLER_ID = 9
PEOPLE_SUBAREA = 44                # I-3
PEOPLE_HURRICAUNE = (0x021045FE, 0)   # Hurricaune beaten (set by the I-3 room script)
PEOPLE_FREED = (0x021045FB, 4)        # cell broken (set by the cell object)
PEOPLE_HANDLER_ENTRANCE_DONE = 3   # I-1 entrance scene seen: the cell scene can trigger
PEOPLE_HANDLER_CELL_WAIT = 7       # cell scene played, waiting for the cell to break

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

# ROM header
ROM_GAME_CODE = b"ARZE"       # MMZX USA
ROM_GAME_CODE_OFF = 0x0C
ROM_AP_MAGIC = b"MZXAP\x00"   # start of the AP header written by rom.py
ROM_AP_MAGIC_OFF = 0x1000
ROM_AP_MAGIC_LEN = len(ROM_AP_MAGIC)
ROM_AP_VERSION_OFF = 0x1008   # u32 of the apworld version that patched the ROM (rom.pack_version)
ROM_SLOT_NAME_OFF = 0x1010    # 63 bytes plus NUL
ROM_SLOT_NAME_LEN = 64

# Hub and warps
# Default teleport: the console pad of floor A, so UP opens the console.
HUB_SUBAREA, HUB_X, HUB_Y = 70, 384, 335
HUB_FLOOR_NEAR = 64            # px around a pad's y that still count as that floor
START_CONFIRM_TICKS = 4        # ticks the starting model must hold
START_MAX_RETRIES = 600

# "Go to Transerver" from the pause menu: the ROM raises WARP_REQ, the client
# opens the game's own Target Area list and reads the chosen station back.
WARP_REQ = 0x020CB9D0          # 1 = pending; the client clears it
TRANSPORT_SEL = 0x021046A8     # Target Area selection, -1 = none
TRANSPORT_SEL_NONE = 0xFFFFFFFF
STATE_TARGET_AREA = 0x00050700 # opens the Target Area list
STATION_ROOMS = list(WARP_DESTINATIONS) + ["x01"]   # room per station index

# The game's `collected` bitmap is polled only if the slot enables a pickup category
PICKUP_OPTION_KEYS = ("pickup_checks_1up", "pickup_checks_energy",
                      "pickup_checks_weapon", "pickup_checks_crystals")
# Pickup state the client keeps in the pickup table section: the icons switch,
# then the `checked` bitmap (rom/table.py); the game's `collected` bitmap follows
PICKUP_STATE_ADDR = PICKUP_TABLE_ADDR + FLAGS_OFF
PICKUP_STATE_LEN = CHECKED_OFF - FLAGS_OFF + BITMAP_LEN
PICKUP_CHECKED_REL = CHECKED_OFF - FLAGS_OFF
PICKUP_ICONS_OFF = 1            # value of the switch that turns the icons off
PICKUP_COLLECTED_ADDR = PICKUP_TABLE_ADDR + COLLECTED_OFF
# A check the server has not confirmed yet is sent again after this many seconds
RESEND_SECONDS = 2.0
# Items are granted once the connection's ReceivedItems arrived, or after this wait
INVENTORY_WAIT_SECONDS = 1.0

# On-screen notices: text left in the NOTIFY mailbox, shown by the ROM in the
# game's small popup
NOTIFY_DUR = 90                 # frames
NOTIFY_DUR_OFF = 2              # u16 in the mailbox
NOTIFY_BUF_OFF = 4
NOTIFY_LEVELS = ("off", "progression", "useful", "all")
NOTIFY_PUNCT = {ch: ord(ch) - 0x20 for ch in "!\"#$%&'()*+,-./:"}   # glyphs seen on screen
NOTIFY_PUNCT["?"] = 0x1F
NOTIFY_GREEN, NOTIFY_WHITE = b"\xf1\x03", b"\xf1\x00"
NOTIFY_QUEUE_MAX = 16
# `full` splits the text into pages that the popup chains without closing
NOTIFY_STYLES = ("short", "full")
NOTIFY_PAGE = b"\xfd"
