"""Patches around picking things up: biometal ownership, Life Up and Sub Tank slots,
the pickup mailbox, pickups that stand for a multiworld item, and Model Hu as an item."""

from .arm9 import Arm9, thumb_bl
from .ui import CUTSCENE_SKIP_CAVE_RAM

# Yellow Card Key dialogue: the Operator re-grants the key while Troop is
# reported and the key unowned. The key comes from the pool, so both console
# dialogue routines (Transerver with Transport, plain computer) skip it for good.
YELLOWKEY_PATCH = [
    # (RAM, vanilla, patched)
    (0x02093BE4, bytes.fromhex("0cd0"), bytes.fromhex("0ce0")),   # Transerver console: beq -> b
    (0x02093462, bytes.fromhex("0dd0"), bytes.fromhex("0de0")),   # computer console: beq -> b
]

# Area X access: reporting the second of Locate Giro and Pass The Test adds X-1
# to the Transport list. X-1 comes from its access item or from reaching the
# hub's X floor, like every other area, so both Reports skip that write.
AREA_X_ACCESS_PATCH = [
    # (RAM, vanilla, patched)
    (0x02031254, bytes.fromhex("4a77"), bytes.fromhex("c046")),   # Locate Giro report: strb -> nop
    (0x0203128C, bytes.fromhex("4277"), bytes.fromhex("c046")),   # Pass The Test report: strb -> nop
]

# Biometal ownership: the game counts set flags of a per-category list, in vanilla
# the two boss victory bits. The list becomes two free flags set only by the item.
# The flags sit one past the end of each Secret Disk series (collected and read),
# the only bits of the progress block that no game code, script or NPC touches.
BIOMETAL_CAT_PATCH = {
    # category: (count addr, list addr, half 1 flag, vanilla list[0], half 2 flag, vanilla list[1])
    3: (0x020DE9AF, 0x020DE9CC, 462, 33, 561, 41),   # H
    4: (0x020DE9B0, 0x020DE9BC, 472, 37, 571, 45),   # F
    5: (0x020DE9B1, 0x020DE9E4, 523, 35, 622, 43),   # L
    6: (0x020DE9B2, 0x020DE9F4, 544, 39, 62, 47),    # P
}
BIOMETAL_CAT_COUNT = 2   # vanilla value; checked, not changed

# Secret Disks are items of the pool: the world's disks record their pickup in the
# game's "read" series, so the "collected" series that Fleuve's database lists is
# the client's alone; the viewer then shows every disk received as read.
SECRET_DISK_PATCH = [
    # (RAM, vanilla, patched)
    (0x020A3AA0, bytes.fromhex("65f766fc"), bytes.fromhex("65f728fc")),   # placed disk pickup: set read
    (0x020A401A, bytes.fromhex("65f7a9f9"), bytes.fromhex("65f76bf9")),   # carried disk pickup: set read
    (0x020A3B76, bytes.fromhex("65f7d9fb"), bytes.fromhex("65f79bfb")),   # placed disk init: taken = read
    (0x020A414E, bytes.fromhex("65f7edf8"), bytes.fromhex("65f7aff8")),   # carrier init: taken = read
    (0x0202AEE2, bytes.fromhex("def707fa"), bytes.fromhex("c046c046")),   # viewer: no "mark read"
    (0x0202B5D2, bytes.fromhex("ddf76dfe"), bytes.fromhex("0120c046")),   # viewer cursor text: read
    (0x0202BE66, bytes.fromhex("ddf723fa"), bytes.fromhex("0120c046")),   # viewer icons: read
    (0x0202BF6E, bytes.fromhex("ddf79ff9"), bytes.fromhex("0120c046")),   # viewer icons: read
]

# Life Up / Sub Tank: the capacity byte doubled as the "slot collected" record.
# The pickup now sets the high nibble (bit 4 + slot): spawn gate and detection.
PICKUP_FLAG_PATCH = [
    # (RAM, vanilla, patched)
    (0x02045014, bytes.fromhex("0121"), bytes.fromhex("1021")),          # grant_life_up: set bit 4 + slot
    (0x0204501E, bytes.fromhex("00f005f8"), bytes.fromhex("c046c046")),  # grant_life_up: no +4 max HP
    (0x02044CAA, bytes.fromhex("0124"), bytes.fromhex("1024")),          # grant_sub_tank: set bit 4 + slot
    (0x02044CD4, bytes.fromhex("0a54"), bytes.fromhex("c046")),          # grant_sub_tank: tank contents untouched
    (0x020A3E30, bytes.fromhex("0121"), bytes.fromhex("1021")),          # Life Up spawn gate: bit 4 + slot
    (0x020A3E86, bytes.fromhex("0121"), bytes.fromhex("1021")),          # Sub Tank spawn gate: bit 4 + slot
]

# Pickup mailbox: layout refills respawn and keep no flag, so the cave hooked into
# the refill think records each one collected in the pickup table's `collected`
# bitmap (table.py), which the client polls.
PICKUP_MAILBOX_HOOK_RAM = 0x020A30A2
PICKUP_MAILBOX_HOOK_ORIG = bytes.fromhex("6cf7b3fd")   # bl animation advance
PICKUP_MAILBOX_HOOK_NEW = bytes.fromhex("28f0fdf9")    # bl PICKUP_MAILBOX_CAVE_RAM
PICKUP_MAILBOX_CAVE_RAM = 0x020CB4A0
PICKUP_MAILBOX_CAVE = bytes.fromhex(
    "10b544f7b3fb94202858c00806d3c0202858002802d028000149884710bdc046"
    "591b1902")

# DATA SELECT icons: the save-slot screen tests raw victory bits for H/F/L/P, so
# it ignored the free flags. Read the first-half flag; hide X when not owned.
DATASELECT_ICON_PATCH = [
    # (RAM, vanilla, patched)
    (0x020361FC, bytes.fromhex("2979022001400029"), bytes.fromhex("a96b890b01200140")),   # H
    (0x02036218, bytes.fromhex("2979202001400029"), bytes.fromhex("a96b090e01200140")),   # F
    (0x02036234, bytes.fromhex("2979082001400029"), bytes.fromhex("296cc90a01200140")),   # L
    (0x02036250, bytes.fromhex("2979802001400029"), bytes.fromhex("696c01200140c046")),   # P
    (0x020361E2, bytes.fromhex("201c0221d9f73dfe"), bytes.fromhex("95f0cdfb64e0c046")),   # X/ZX: bl cave; b end
]
DATASELECT_CAVE_RAM = 0x020CB980
DATASELECT_CAVE = bytes.fromhex(
    "30b5201c022144f76dfae878000603d4a17afe200140a17230bd")

# PICKUP_AP: a pickup standing for a pending multiworld location (the pickup table's
# gate, table.py) skips its vanilla effect, popup and label; it only chimes. The disk
# held by the H-1 balloon has no spawn record and asks about its carrier.
PICKUP_AP_CAVE_RAM = 0x020CB800
PICKUP_AP_CAVE = bytes.fromhex(
    "004b1847311b1902000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000001a203af743f810bd00b52800fff7d0ff"
    "002805d01a203af739f801bc0248004702bc287d00280847ad310a0210b50400"
    "fff7beff002803d12000d8f7d5f810bd04202061607a81000348415820698000"
    "0858a061d4e700bfb0b80e0210b50400fff7a6ff0028cbd124203af70ff80248"
    "5a2146f707fd10bd2904000010b50400fff796ff0028bbd1182039f7ffff0248"
    "5a2146f7f7fc10bd2a04000010b50400206bfff785ff0028cad12000d8f760fb"
    "10bd")
PICKUP_AP_ENTRIES = {'apgate': 0, 'ap_tail': 80, 'refill': 88, 'disk': 124, 'lifeup': 172, 'subtank': 204,
                     'carried': 236}
# (RAM, vanilla code, cave entry, code kept before the bl, code after it)
PICKUP_AP_HOOKS = [
    (0x020A30F4, bytes.fromhex("287d0028"), "refill", b"", b""),
    (0x020A3ADE, bytes.fromhex("fff7abff"), "disk", b"", b""),
    (0x020A3CD4, bytes.fromhex("242061f701fe39485a216ef7f9fa"), "lifeup", bytes.fromhex("201c"),
     bytes.fromhex("c046") * 4),
    (0x020A3CEE, bytes.fromhex("182061f7f4fd33485a216ef7ecfa"), "subtank", bytes.fromhex("201c"),
     bytes.fromhex("c046") * 4),
    (0x020A4058, bytes.fromhex("fff7b2ff"), "carried", b"", b""),
]

# Hu gate (hu_in_pool): Hu is always owned because its category has no flag
# list. Pointing the list at a one-flag array makes Hu an item; the count is 1.
HUGATE_LISTS0_RAM = 0x020DEB78
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"
HUGATE_ARRAY_RAM = 0x020CB434
HUGATE_FLAG_INDEX = 120                   # 0x021045DB bit 0: "visited" slot of the hub itself, never set


def patch_yellow_key_dialogue(arm9: Arm9) -> None:
    """Stop the Operator from re-granting the Yellow Card Key on every visit."""
    for ram, orig, new in YELLOWKEY_PATCH:
        arm9.write(ram, new, orig)


def patch_area_x_access(arm9: Arm9) -> None:
    """Stop the Giro and Pass The Test Reports from unlocking X-1 in Transport."""
    for ram, orig, new in AREA_X_ACCESS_PATCH:
        arm9.write(ram, new, orig)


def patch_biometal_ownership(arm9: Arm9) -> None:
    """Own H/F/L/P through two free flags per model, set by its item, instead of the victory bits."""
    for count_ram, list_ram, flag1, orig1, flag2, orig2 in BIOMETAL_CAT_PATCH.values():
        arm9.write(list_ram, flag1.to_bytes(4, "little"), orig1.to_bytes(4, "little"))
        arm9.write(list_ram + 4, flag2.to_bytes(4, "little"), orig2.to_bytes(4, "little"))
        arm9.write(count_ram, bytes([BIOMETAL_CAT_COUNT]), bytes([BIOMETAL_CAT_COUNT]))


def patch_secret_disks(arm9: Arm9) -> None:
    """The world's disks mark the read series; the collected series belongs to the client."""
    for ram, orig, new in SECRET_DISK_PATCH:
        arm9.write(ram, new, orig)


def patch_life_up_sub_tank(arm9: Arm9) -> None:
    """Record a collected Life Up or Sub Tank in the high nibble instead of raising the capacity."""
    for ram, orig, new in PICKUP_FLAG_PATCH:
        arm9.write(ram, new, orig)


def patch_pickup_mailbox(arm9: Arm9) -> None:
    """Record each collected layout refill in the pickup table's `collected` bitmap."""
    assert PICKUP_MAILBOX_CAVE_RAM + len(PICKUP_MAILBOX_CAVE) <= CUTSCENE_SKIP_CAVE_RAM
    arm9.write(PICKUP_MAILBOX_CAVE_RAM, PICKUP_MAILBOX_CAVE)
    arm9.write(PICKUP_MAILBOX_HOOK_RAM, PICKUP_MAILBOX_HOOK_NEW, PICKUP_MAILBOX_HOOK_ORIG)


def patch_data_select_icons(arm9: Arm9) -> None:
    """Draw the DATA SELECT biometal icons from the free flags; hide X when the slot does not own it."""
    for ram, orig, new in DATASELECT_ICON_PATCH:
        arm9.write(ram, new, orig)
    arm9.write(DATASELECT_CAVE_RAM, DATASELECT_CAVE)


def patch_pickup_ap(arm9: Arm9) -> None:
    """Make a pickup that stands for a pending multiworld location skip its vanilla effect; it only chimes."""
    assert PICKUP_AP_CAVE_RAM + len(PICKUP_AP_CAVE) <= DATASELECT_CAVE_RAM
    arm9.write(PICKUP_AP_CAVE_RAM, PICKUP_AP_CAVE)
    for ram, orig, entry, pre, post in PICKUP_AP_HOOKS:
        new = pre + thumb_bl(ram + len(pre), PICKUP_AP_CAVE_RAM + PICKUP_AP_ENTRIES[entry]) + post
        assert len(new) == len(orig)
        arm9.write(ram, new, orig)


def patch_hu_gate(arm9: Arm9, hu_in_pool: bool) -> None:
    """With hu_in_pool, make Model Hu an item: category 0 counts a single free flag."""
    if not hu_in_pool:
        return
    arm9.write(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
    arm9.write(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"), HUGATE_LISTS0_ORIG)
