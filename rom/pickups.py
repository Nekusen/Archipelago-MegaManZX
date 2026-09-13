"""Patches around picking things up: biometal ownership, Life Up and Sub Tank slots,
the pickup mailbox, pickups that stand for a multiworld item, and Model Hu as an item."""

from ..data import PICKUP_MAILBOX_ADDR
from .arm9 import Arm9, thumb_bl

# Yellow Card Key dialogue: the Operator re-grants the key while Troop is
# reported and the key unowned. The key comes from the pool, so both console
# dialogue routines (Transerver with Transport, plain computer) skip it for good.
YELLOWKEY_PATCH = [
    # (RAM, vanilla, patched)
    (0x02093BE4, bytes.fromhex("0cd0"), bytes.fromhex("0ce0")),   # Transerver console: beq -> b
    (0x02093462, bytes.fromhex("0dd0"), bytes.fromhex("0de0")),   # computer console: beq -> b
]

# Biometal ownership: the game counts set flags of a per-category list, in vanilla
# the two boss victory bits. The list becomes two free flags set only by the item.
BIOMETAL_CAT_PATCH = {
    # category: (count addr, list addr, half 1 flag, vanilla list[0], half 2 flag, vanilla list[1])
    3: (0x020DE9AF, 0x020DE9CC, 728, 33, 720, 41),   # H
    4: (0x020DE9B0, 0x020DE9BC, 729, 37, 721, 45),   # F
    5: (0x020DE9B1, 0x020DE9E4, 730, 35, 722, 43),   # L
    6: (0x020DE9B2, 0x020DE9F4, 731, 39, 723, 47),   # P
}
BIOMETAL_CAT_COUNT = 2   # vanilla value; checked, not changed

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
# the refill think reports (subarea, coords index, role) to a ring the client polls.
# The mailbox itself is data.PICKUP_MAILBOX_ADDR, right after the cave.
PICKUP_MAILBOX_HOOK_RAM = 0x020A30A2
PICKUP_MAILBOX_HOOK_ORIG = bytes.fromhex("6cf7b3fd")   # bl animation advance
PICKUP_MAILBOX_HOOK_NEW = bytes.fromhex("28f0fdf9")    # bl PICKUP_MAILBOX_CAVE_RAM
PICKUP_MAILBOX_CAVE_RAM = 0x020CB4A0
PICKUP_MAILBOX_CAVE = bytes.fromhex(
    "10b544f7b3fb94202858c0081dd3c0202858002819d00d490968002915d04a68"
    "aa4201d00968f8e70a891202084800780243287d00040243064b186807240440"
    "a400e41862600130186010bdf48110022882100200b50c02")

# DATA SELECT icons: the save-slot screen tests raw victory bits for H/F/L/P, so
# it ignored the free flags. Read the first-half flag; hide X when not owned.
DATASELECT_ICON_PATCH = [
    # (RAM, vanilla, patched)
    (0x020361FC, bytes.fromhex("2979022001400029"), bytes.fromhex("a96d090e01200140")),   # H
    (0x02036218, bytes.fromhex("2979202001400029"), bytes.fromhex("a96d090e02200140")),   # F
    (0x02036234, bytes.fromhex("2979082001400029"), bytes.fromhex("a96d090e04200140")),   # L
    (0x02036250, bytes.fromhex("2979802001400029"), bytes.fromhex("a96d090e08200140")),   # P
    (0x020361E2, bytes.fromhex("201c0221d9f73dfe"), bytes.fromhex("95f0cdfb64e0c046")),   # X/ZX: bl cave; b end
]
DATASELECT_CAVE_RAM = 0x020CB980
DATASELECT_CAVE = bytes.fromhex(
    "30b5201c022144f76dfae878000603d4a17afe200140a17230bd")

# PICKUP_AP: a pickup standing for a multiworld location (the `present` bitmap
# of the icon table) skips its vanilla effect, popup and label; it only chimes.
PICKUP_AP_CAVE_RAM = 0x020CB800
PICKUP_AP_CAVE = bytes.fromhex(
    "10b5104c2178104a1278914217d16178c90714d00d490968002910d04a68824201d00968f8e70a89802a08d2d308a433e35c07211140cb400120184010bd002010bd00bf6014190228821002f48110021a203af743f810bd00b52800fff7d0ff002805d01a203af739f801bc0248004702bc287d00280847ad310a0210b50400fff7beff002803d12000d8f7d5f810bd04202061607a810003484158206980000858a061d4e700bfb0b80e0210b50400fff7a6ff0028cbd124203af70ff802485a2146f707fd10bd2904000010b50400fff796ff0028bbd1182039f7ffff02485a2146f7f7fc10bd2a040000")
PICKUP_AP_ENTRIES = {'apgate': 0, 'ap_tail': 80, 'refill': 88, 'disk': 124, 'lifeup': 172, 'subtank': 204}
# (RAM, vanilla code, cave entry, code kept before the bl, code after it)
PICKUP_AP_HOOKS = [
    (0x020A30F4, bytes.fromhex("287d0028"), "refill", b"", b""),
    (0x020A3ADE, bytes.fromhex("fff7abff"), "disk", b"", b""),
    (0x020A3CD4, bytes.fromhex("242061f701fe39485a216ef7f9fa"), "lifeup", bytes.fromhex("201c"),
     bytes.fromhex("c046") * 4),
    (0x020A3CEE, bytes.fromhex("182061f7f4fd33485a216ef7ecfa"), "subtank", bytes.fromhex("201c"),
     bytes.fromhex("c046") * 4),
]

# Hu gate (hu_in_pool): Hu is always owned because its category has no flag
# list. Pointing the list at a one-flag array makes Hu an item; the count is 1.
HUGATE_LISTS0_RAM = 0x020DEB78
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"
HUGATE_ARRAY_RAM = 0x020CB434
HUGATE_FLAG_INDEX = 136                   # 0x021045DD bit 0, unused by the game


def patch_yellow_key_dialogue(arm9: Arm9) -> None:
    """Stop the Operator from re-granting the Yellow Card Key on every visit."""
    for ram, orig, new in YELLOWKEY_PATCH:
        arm9.write(ram, new, orig)


def patch_biometal_ownership(arm9: Arm9) -> None:
    """Own H/F/L/P through two free flags per model, set by its item, instead of the victory bits."""
    for count_ram, list_ram, flag1, orig1, flag2, orig2 in BIOMETAL_CAT_PATCH.values():
        arm9.write(list_ram, flag1.to_bytes(4, "little"), orig1.to_bytes(4, "little"))
        arm9.write(list_ram + 4, flag2.to_bytes(4, "little"), orig2.to_bytes(4, "little"))
        arm9.write(count_ram, bytes([BIOMETAL_CAT_COUNT]), bytes([BIOMETAL_CAT_COUNT]))


def patch_life_up_sub_tank(arm9: Arm9) -> None:
    """Record a collected Life Up or Sub Tank in the high nibble instead of raising the capacity."""
    for ram, orig, new in PICKUP_FLAG_PATCH:
        arm9.write(ram, new, orig)


def patch_pickup_mailbox(arm9: Arm9) -> None:
    """Report each collected layout refill (subarea, coords index, role) to the ring the client polls."""
    assert len(PICKUP_MAILBOX_CAVE) <= PICKUP_MAILBOX_ADDR - PICKUP_MAILBOX_CAVE_RAM
    arm9.write(PICKUP_MAILBOX_CAVE_RAM, PICKUP_MAILBOX_CAVE)
    arm9.write(PICKUP_MAILBOX_HOOK_RAM, PICKUP_MAILBOX_HOOK_NEW, PICKUP_MAILBOX_HOOK_ORIG)


def patch_data_select_icons(arm9: Arm9) -> None:
    """Draw the DATA SELECT biometal icons from the free flags; hide X when the slot does not own it."""
    for ram, orig, new in DATASELECT_ICON_PATCH:
        arm9.write(ram, new, orig)
    arm9.write(DATASELECT_CAVE_RAM, DATASELECT_CAVE)


def patch_pickup_ap(arm9: Arm9) -> None:
    """Make a pickup that stands for a multiworld location skip its vanilla effect; it only chimes."""
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
