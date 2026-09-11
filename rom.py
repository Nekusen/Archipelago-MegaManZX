"""Mega Man ZX ROM patch (v0.1: AP marker + slot name).

Lightweight approach (docs/playbook_ds_ap.md): the client works through RAM,
so the patch only marks the ROM as an AP seed and embeds the slot name for
validate_rom/set_auth. It is written at 0x1000 (padding area after the NDS
header; verified to be zeros in the base ROM, the same trick Pokemon Platinum
uses for its version).

Layout at 0x1000:
  +0x00  b"MZXAP\\x00"          magic (6)
  +0x08  u32 world version
  +0x10  slot name (64 B utf-8, zero-terminated)
  +0x50  seed name (32 B)
"""

import hashlib

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
WORLD_VERSION_INT = 1  # v0.1

# --- Tutorial-skip patch (v0.2; RE in docs/v02_notes.md sec. 2c/2e/2h) ---
# The state handler FUN_02022544 (Thumb entry 0x02022544) is slot 0 of the
# handler table 0x020D8E28 and is SHARED by "New Game" (game_state 0x10000)
# and the attract/intro demo (game_state 0xB00). That is why an unconditional
# redirect also clobbered the boot cinematic (user playtest). Solution: a
# CODE CAVE (Thumb) that only redirects when game_state (0x0215E6D8) ==
# 0x10000 (a real New Game): in that case it jumps to the LOAD handler
# FUN_0202252c (enters the scene through the LOAD path, cleanly, using the
# block at 0x021602A8 that the client seeds); in every other case (attract
# 0xB00, etc.) it replicates the original prologue (push{r4,lr}; mov r4,r0;
# bl FUN_0202298c) and continues at 0x0202254C -> intro/attract INTACT.
# "Continue" (real Load) uses another slot and is left alone.
# Entry (8 B) @0x02022544: LDR R3,[PC,#0]; BX R3; .word CAVE|1.
# Bytes assembled with keystone (exp206), validated E2E (exp207).
SKIP_ENTRY_RAM = 0x02022544
SKIP_ENTRY = bytes.fromhex("004b184761b40c02")        # -> BX 0x020CB460
SKIP_ENTRY_ORIG = bytes.fromhex("10b5041c00f020fa")   # push;mov r4,r0;bl
SKIP_CAVE_RAM = 0x020CB460                            # zero-filled gap in the arm9
# v2 (2026-09-02, agent exp269p + keystone): the New Game mode encodes
# character/difficulty (FUN_02017e68: tbl[character]<<16 | tbl[difficulty]
# <<24; Vent/Easy = 0x10000, AILE/Easy = 0x00000000, Normal adds 0x1000000) --
# the v1 cave compared against exactly 0x10000 and with Aile did NOT redirect
# (title scene as gameplay). v2: redirects if the low 16 bits of the mode are
# 0 (any character/difficulty; the attract 0xB00/0xC00 does not qualify) AND
# the title carousel is at "game launched" (u8 0x0214CD70 == 6; on the logos
# gs=0 but step<3). Assembled with keystone (Thumb @0x020CB460):
#   ldr r1,[pc,#0x1C]; ldr r1,[r1]; lsls r1,r1,#16; bne orig
#   ldr r2,[pc,#0x18]; ldrb r2,[r2]; cmp r2,#6; beq skip
#   orig: push{r4,lr}; mov r4,r0; bl FUN_0202298c; ldr r3,=0x0202254D; bx r3
#   skip: ldr r3,=0x0202252D; bx r3
#   pool: 0x0215E6D8, 0x0214CD70, 0x0202254D, 0x0202252D
SKIP_CAVE = bytes.fromhex(
    "07490968090403d1064a1278062a05d010b5044657f78afa034b1847034b1847"
    "d8e6150270cd14024d2502022d250202")

# --- Hu-gate (v0.2 EXPERIMENTAL; RE in docs/v02_notes.md sec. 2f) ---
# Hu is hardcoded: category 0 of the ownership check FUN_0203e414 has a NULL
# list at 0x020DEB78 -> returns the count (1) -> always owned. To make it an
# item: point lists[0] at a 1-flag array [136] (= bit 0x021045DD.0, free) ->
# Hu requires that flag. counts[0] is already 1.
HUGATE_LISTS0_RAM = 0x020DEB78            # lists[0] (u32, currently 0)
HUGATE_ARRAY_RAM = 0x020CB434             # zero-filled gap in the arm9 (0x5A0 B)
HUGATE_FLAG_INDEX = 136                   # 0x021045DD bit0 (VERIFIED free)
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"

CFG_HU_IN_POOL = 0x01                     # config byte 0: bit0 = hu_in_pool

# --- YELLOW CARD KEY dialogue looping (user playtest 2026-09-06) ---
# `FUN_02093b4c` (dispatcher of the Operator's console), case 1: if *Troop
# Reinforcement* has been reported (0x021045E1.1) and the yellow key is NOT owned
# (0x021045FD.1), it starts script 0x12 (`FUN_02094288`: sfx + msg 1129 "YELLOW CARD
# KEY" + the `orr` that grants it). In the randomizer the key is an ITEM of the pool
# and the client enforces ownership, so the bit never stays set -> the dialogue
# repeated on EVERY entry to the Transerver. The yellow key is NOT a location (no
# check is lost), so the script is disabled: the `beq` that jumps to the normal flow
# (the same path the game takes when you already have it) becomes unconditional.
#   0x02093BE4: beq (D00C) -> b (E00C)
YELLOWKEY_BR_RAM = 0x02093BE4
YELLOWKEY_BR_ORIG = bytes.fromhex("0cd0")
YELLOWKEY_BR_NEW = bytes.fromhex("0ce0")

# --- OAM sprite drawer guard (exp214-225, 2026-09-02) ---
# FUN_02009b74 (Thumb, 208 B + 24 B pool) builds the OAM entries of a
# drawable: it does ONE bounds check before the loop and leaves the loop only
# through `subs r5,#1; beq`. If the frame's sprite count is 0 (OAM table
# clobbered: e.g. the 139 KB block of a boss loaded at 0x0224C000 on top of
# the level's graphics heap while entities are alive, when spawning by
# teleport into the boss area), the loop wraps around and writes sprites all
# over RAM (cursor 0x020F728C) -> soft-lock. MINIMAL patch (1 byte): the loop
# ends with `subs r5,#1 ; beq exit` (0x02009C2E/30); `beq` (D001) -> `bls`
# (D901): LS = borrow (r5 was 0) OR Z (reached 0), so with count==0 it exits
# after ONE iteration (bounded by the previous bounds check) instead of
# wrapping around to 0xFFFFFFFF. With count>=1 the behaviour is identical.
# (Relocating to a 240 B cave also worked, exp225, but broke the BLZ slot
# limit.)
OAMLOOP_BR_RAM = 0x02009C30
OAMLOOP_BR_ORIG = bytes.fromhex("01d0")   # beq +2
OAMLOOP_BR_NEW = bytes.fromhex("01d9")    # bls +2
# TWIN: FUN_02009c5c has the SAME unguarded loop (0x02009D7A `subs r5,#1` /
# 0x02009D7C `beq`), with the same bytes. Unpatched, when the first mini-boss
# of D-2 (Troop) fires the loop wraps around and sprays RAM: 0x021045E0 was
# seen corrupted (the mission start flag was lost, which leaves Giro's scene
# untriggered), as were 0x021045FC (Card Keys) and 0x02104602. With the patch,
# ZERO writes and zero corruption (agent exp521 vs exp523).
OAMLOOP2_BR_RAM = 0x02009D7C
OAMLOOP2_BR_ORIG = bytes.fromhex("01d0")
OAMLOOP2_BR_NEW = bytes.fromhex("01d9")

# --- Sprite drawer guard: SET WITHOUT A VRAM SLOT (exp585, 2026-09-06) ---
# The set registrar `FUN_02006b1c` REJECTS a set when (palettes already assigned +
# the ones the set asks for) > 0x0F (0x02006B86 screen 0 / 0x02006B92 screen 1) or
# when the tile cursor does not fit (0x02006B66): it leaves 0x02105C94[set] = 0xFF.
# The TEN sprite drawers then resolve the slot record as NULL and read it anyway:
#     movs r0,#0 ; ldrh r0,[r0,#2] ; movs r3,#1
# i.e. they READ ADDRESS 0x00000002 -> data abort (pc = 0xFFFF0108) -> grey screen
# and dead game. It is a LATENT bug of the game (several rooms already hit the cap of
# 15 OBJ palettes in vanilla) that the AP icon set exposes: by taking a palette
# permanently, in F-5 the hit effect (set 124) is left unregistered and the first
# blow on the boss kills the game (user playtest 2026-09-06; repro and diagnosis
# with THE USER'S savestate in BizHawk: exp585, docs/v02_notes.md sec. 2k).
# Patch: at every site, `ldrh r0,[r0,#2] ; movs r3,#1` -> `bl cave`; the cave only
# reads if r0 != 0. A sprite without a slot is not drawn instead of hanging the
# console.
SPRITEGUARD_CAVE_RAM = 0x020C827C          # after ICON_CAVES (0x020C81C4 + 184)
SPRITEGUARD_CAVE = bytes.fromhex("002800d0408801237047")   # cmp r0,#0; beq +; ldrh r0,[r0,#2]; movs r3,#1; bx lr
SPRITEGUARD_ORIG = bytes.fromhex("40880123")
SPRITEGUARD_SITES = [0x0200F0D4, 0x0200F244, 0x0200F424, 0x0200F85A, 0x0200FA5A,
                     0x0200FC96, 0x0200FFA2, 0x02010236, 0x020104CA, 0x02010756]


# --- "AP item only" biometal ownership (H/F/L/P) -- exp240 (2026-09-02),
# agent exp380-389, PROGRESSIVE exp444-447c (2026-09-03) ---
# Ownership of a model is resolved by FUN_0203e414 over category tables
# (counts @0x020DE9AC, lists @0x020DEB78): it returns HOW MANY flags of the
# list are set. In vanilla HX/FX/LX/PX have count=2 and list [D0.x, D1.x]:
# the bit written by the victory over the pair's 1st Pseudoroid (D0, =
# detection of the "Obtain Biometal X" location) and the 2nd's (D1). One flag
# = one HALF of the biometal: with 1 the model is usable; with 2
# (model_owned_count >= 2) the model overlays raise the charge counter cap
# from 0x28 to 0x78 (level 2 charged attack: HX 0x0218A3F8, FX 0x02187854,
# LX 0x02187D60, PX 0x02188E48) and the WE cap is 4 x (boss1 lv + boss2 lv).
# Patch: the list becomes [half 1, half 2] with FREE flags that only the AP
# item sets (progressive, 2 copies): the boss victory turns on D0/D1 (fires
# the check) but grants NOTHING; count stays at 2 (vanilla).
#   half 1 = 728-731 = 0x02104627.0-3 (agent exp380-389: 0 across 268
#            savestates, outside every table, ignored by the Transport
#            popcount; persist in the save)
#   half 2 = 720-723 = 0x02104626.0-3 (exp447: only touched by the
#            canonical<->live copy; exp447c: survive save + reset + Continue)
# Verified exp446: with [728,720] and only 728 -> count=1 (cap 0x28); with
# both -> count=2 and the full charge branch (cap 0x78). BEFORE (v0.2) the
# list was [free flag] with count=1: no model could ever be "complete".
# cat -> (count_addr, list0_addr, flag_half1, orig_list0 (D0), flag_half2, orig_list1 (D1))
BIOMETAL_CAT_PATCH = {
    3: (0x020DE9AF, 0x020DE9CC, 728, 33, 720, 41),   # H: Hivolt D0.1 / Hurricaune D1.1 -> 0x02104627.0 / 0x02104626.0
    4: (0x020DE9B0, 0x020DE9BC, 729, 37, 721, 45),   # F: Fistleo D0.5 / Flammole D1.5   -> .1 / .1
    5: (0x020DE9B1, 0x020DE9E4, 730, 35, 722, 43),   # L: Lurerre D0.3 / Leganchor D1.3  -> .2 / .2
    6: (0x020DE9B2, 0x020DE9F4, 731, 39, 723, 47),   # P: Purprill D0.7 / Protectos D1.7 -> .3 / .3
}
BIOMETAL_CAT_COUNT = 2   # vanilla; checked, not changed


# --- Life Ups / Sub Tanks: "collected" != "capacity" (agent exp300-309,
# 2026-09-02; verified in RAM: pickup, spawn, door, death, save+reset+
# Continue). In vanilla the capacity byte 0x0214FC77 (Life Ups) /
# 0x0214FC78 (Sub Tanks) uses bits 0-3 as "slot collected" (= capacity
# and = gate of the pickup's spawn, FUN_020a3dd4) and is persisted in the
# save. In the randomizer the LOW nibble is the count of AP items (client,
# authoritative capacity) and the HIGH nibble (bit 4+idx) becomes
# "physically collected": set by the pickup (patched grant_life_up
# FUN_02045008 / grant_sub_tank FUN_02044ca4), it gates the spawn and is the
# DETECTION of the check. The pickup no longer raises max HP nor touches the
# tank contents. The Energy Packs quest (report -> grant_sub_tank idx 3) sets
# FC78.7: no tank.
PICKUP_FLAG_PATCH = [
    # (RAM, original bytes, new bytes)
    (0x02045014, "0121", "1021"),          # grant_life_up: movs r1,#1 -> #0x10 (bit 4+idx)
    (0x0204501E, "00f005f8", "c046c046"),  # grant_life_up: bl FUN_0204502c(p,4) -> nop nop (no +4 max HP)
    (0x02044CAA, "0124", "1024"),          # grant_sub_tank: movs r4,#1 -> #0x10
    (0x02044CD4, "0a54", "c046"),          # grant_sub_tank: strb (tank contents) -> nop
    (0x020A3E30, "0121", "1021"),          # spawn Life Up (FUN_020a3dd4): gate by bit 4+idx
    (0x020A3E86, "0121", "1021"),          # spawn Sub Tank: gate by bit 4+idx
]


# --- MAILBOX of respawnable pickups (agent exp360-369, 2026-09-02) ---
# The refills placed on the map (health/WE/E-Crystal/1-Up, kind 6 sub 0) are
# OPTIONAL locations: the first pickup of each one sends the check and after
# that they keep respawning. There is no persistent flag: the game instantiates
# them from the room's coords table (0x020C9C7C+0x240) through the spawner
# FUN_0200ca8c, which ties every live entity to a spawn RECORD (pool
# 0x02107FB4, 48 x 12 B: +0 next, +4 entity, +8 u16 coords index, +0xA attr;
# active list at 0x021081F4). Enemy drops (FUN_020a37d8) have no record.
# Patch: the `bl FUN_0200fc0c` in the prologue of the item_entity_update
# think (FUN_020a309c, 0x020A30A2) becomes `bl cave`; the cave (Thumb, 88 B
# in the zero-filled gap of the arm9) calls FUN_0200fc0c and, if entity r5 is
# "collected" (+0x94 & 4 && +0xC0 != 0: the same test as the think), looks up
# its record and writes into the mailbox
#   MAILBOX+0  u32 counter (goes up by 1 per pickup with an identity)
#   MAILBOX+4  ring of 8 x u32 [u8 subarea 0x02108228, u8 coords index,
#              u8 role (+0x14), 0]  (entry = counter & 7)
# The client polls the counter and maps (sub, idx) -> location (data.py
# LOCATIONS detect ['mailbox', sub, idx]); repeats (respawn) are filtered by
# the client. Verified in RAM (exp364/365: 9 pickups in a01/c01 with the
# right index, re-entering writes again, an enemy drop does not write) and
# baked by rom.py (exp366, cold boot through the skip). Gap
# 0x020CB490-0x020CB9D4 with no reads or writes during a session (exp363).
PICKUP_MAILBOX_HOOK_RAM = 0x020A30A2
PICKUP_MAILBOX_HOOK_ORIG = bytes.fromhex("6cf7b3fd")   # bl FUN_0200fc0c
PICKUP_MAILBOX_HOOK_NEW = bytes.fromhex("28f0fdf9")    # bl 0x020CB4A0 (mailbox cave). 2026-09-04..05 it pointed at the grey MARKING cave 0x020CB800 (PICKUP_MARK, agent exp483-491), retired when the item icons arrived (sec. 2c)
PICKUP_MAILBOX_CAVE_RAM = 0x020CB4A0                   # after SKIP_CAVE (0x020CB460+48)
# push{r4,lr}; bl FUN_0200fc0c; ldr r0,[r5,#0x94]; lsrs #3; bcc done;
# ldr r0,[r5,#0xC0]; beq done; r1=[0x021081F4]; loop: beq done; [r1+4]==r5?
# -> found; r1=[r1]; b loop; found: r2=u16[r1+8]<<8 | u8[0x02108228] |
# u8[r5+0x14]<<16; r3=MAILBOX; r0=[r3]; [r3+4+(r0&7)*4]=r2; [r3]=r0+1;
# done: pop{r4,pc}; pool: 0x021081F4, 0x02108228, MAILBOX
PICKUP_MAILBOX_CAVE = bytes.fromhex(
    "10b544f7b3fb94202858c0081dd3c0202858002819d00d490968002915d04a68"
    "aa4201d00968f8e70a891202084800780243287d00040243064b186807240440"
    "a400e41862600130186010bdf48110022882100200b50c02")
PICKUP_MAILBOX_RAM = 0x020CB500          # = data.PICKUP_MAILBOX_ADDR (gen_ap_data)
PICKUP_MAILBOX_SLOTS = 8

# --- On-screen notices from the AP client ("NOTIFY"; agent exp473-480,
# 2026-09-04; docs/v02_notes.md sec. 2a) ---
# The gameplay handler FUN_02021bb0 calls msg_tick FUN_0201242c every frame
# (0x02021DD4). The bl becomes a cave that, if there is a request in the
# mailbox and the message system (0x027E02C4) is free (no cutscene
# 0x0214F502.0 nor console 0x0214F506.1), opens the game's SMALL POPUP (the
# "Found a Life Up!" one: it does not block gameplay) with the mailbox text
# (replicates show_pickup_msg FUN_020122d4 with a direct pointer: OBJ+0x1C =
# BUF, OBJ+0xC = DUR, FUN_020121dc, FUN_02012050, OBJ+0x10 = type) or the
# vanilla message `id` (REQ=2), and finally calls msg_tick. REQ is cleared on
# seeing the closing phase (OBJ+0x11 == 6); if the message is reset earlier
# (room change), it is relaunched. Mailbox: u8 REQ (0/1 text/2 id), u8 STATE
# (cave), u16 DUR (frames with the whole text), +4 BUF (<= 0xFC B, font =
# ASCII-0x20, end 0xFE). Popup = 1 line of 30 glyphs (the 31st overwrites the
# 1st). Verified in RAM and cold (exp475-480).
NOTIFY_HOOK_RAM = 0x02021DD4
NOTIFY_HOOK_ORIG = bytes.fromhex("f0f72afb")   # bl FUN_0201242c
NOTIFY_HOOK_NEW = bytes.fromhex("a9f014fc")    # bl 0x020CB600
NOTIFY_CAVE_RAM = 0x020CB600                   # area 0x020CB600-0x020CB7FF
NOTIFY_CAVE = bytes.fromhex(
    "10b5204c2078002839d01f496078002806d0487e062803d10020207060702ee0"
    "488900282bd18869002828d117480078400824d216480078800820d201206070"
    "2078022804d1a088618846f743fe16e0201d486260884861c889002801d03bf7"
    "61ff0c4846f7bafd0a4846f7f1fc0649087b002801d0012000e00220886146f7"
    "d5fe10bd00b70c02c4027e0202f5140206f51402cc027e02")
NOTIFY_RAM = 0x020CB700        # = data.NOTIFY_ADDR
NOTIFY_BUF_MAX = 0xFC
NOTIFY_POPUP_GLYPHS = 30

# --- Pickups REPLACED by AP items: no vanilla effect (2026-09-07, exp603-604;
# user playtest; docs/v02_notes.md sec. 2m) ---
# On collecting a pickup that is a pending AP location the game still applied the
# effect of the original object (energy/WE/E-Crystals/1-Up, the "Found a Life
# Up!"/"Found a Sub Tank!" popup and the "E-04" label over the player when taking
# a disk). `apgate(ent)` (Thumb, +0x00) returns 1 if the entity is a pending AP
# location according to the client's TABLE (ICON_TABLE: same sub 0x02108228, flags
# bit0, entity in the spawn list 0x021081F4 -> coords index, bit of the NEW
# `present` bitmap at +0xA4 = "multiworld location not sent yet"; the client
# always writes it, with /mmzx_icons off too). Hooks:
#   refill  0x020A30F4 (FUN_020a309c, r5 = ent): if AP -> chime 0x1A and jump to
#           the epilogue 0x020A31AC (no HP/WE/EC/1-Up/flag/popup); otherwise
#           repeats `ldrb r0,[r5,#0x14]; cmp r0,#0` and returns with the flags
#           intact.
#   disk    0x020A3ADE `bl FUN_020a3a38` ("E-04" label + sfx 0x1A): if AP ->
#           chime and state 4 (release, table 0x020EB8B0[kind][4]) as when the
#           label is created; the disk's state 2 handler IS FUN_020a3a38 (retries
#           the label every frame), which is why not calling it is not enough.
#           The disk flag (FUN_02009370) is kept (detection).
#   lifeup  0x020A3CD4 (14 B: sfx 0x24 + popup 1065) and subtank 0x020A3CEE (sfx
#           0x18 + popup 1066): `movs r0,r4; bl cave; 4 nops`; if AP -> chime;
#           otherwise vanilla. grant_* (high nibble, PICKUP_FLAG_PATCH) is kept.
# The mailbox (prologue hook) and the icons do not change. AP sound = disk chime.
PICKUP_AP_CAVE_RAM = 0x020CB800          # free gap (former PICKUP_MARK) up to DATASELECT_CAVE_RAM
PICKUP_AP_CAVE = bytes.fromhex(
    "10b5104c2178104a1278914217d16178c90714d00d490968002910d04a68824201d00968f8e70a89802a08d2d308a433e35c07211140cb400120184010bd002010bd00bf6014190228821002f48110021a203af743f810bd00b52800fff7d0ff002805d01a203af739f801bc0248004702bc287d00280847ad310a0210b50400fff7beff002803d12000d8f7d5f810bd04202061607a810003484158206980000858a061d4e700bfb0b80e0210b50400fff7a6ff0028cbd124203af70ff802485a2146f707fd10bd2904000010b50400fff796ff0028bbd1182039f7ffff02485a2146f7f7fc10bd2a040000")
PICKUP_AP_ENTRIES = {'apgate': 0, 'ap_tail': 80, 'refill': 88, 'disk': 124, 'lifeup': 172, 'subtank': 204}
PICKUP_AP_HOOKS = [   # (RAM, original bytes, entry, prefix, suffix): prefix + bl(entry) + suffix
    (0x020A30F4, "287d0028", "refill", "", ""),
    (0x020A3ADE, "fff7abff", "disk", "", ""),
    (0x020A3CD4, "242061f701fe39485a216ef7f9fa", "lifeup", "201c", "c046" * 4),
    (0x020A3CEE, "182061f7f4fd33485a216ef7ecfa", "subtank", "201c", "c046" * 4),
]
ICON_TABLE_PRESENT_OFF = 0xA4            # `present` bitmap (32 B) read by apgate

# --- Cutscenes ALWAYS skippable (agent exp453-462, 2026-09-04;
# docs/v02_notes.md sec. 2a) ---
# Vanilla: START only skips a cutscene if its unique event (96-bit bitfield
# 0x021045C0) is already set: opcode 0x23 sub 0 of the VM (FUN_0201bfd0,
# "open skippable block") only sets flag 0x10 of 0x0214F502 ("skippable")
# if the bit was already there; the START reader FUN_0201b1c8 requires that
# flag and jumps to the handler's post-cutscene state (same path as "die and
# retry": the flags/warps are replayed by the handler, not by the remaining
# opcodes). Patch: (1) the "event not seen" beq becomes `mov r8,r8` =>
# always skippable; (2) on skipping, a cave does what the block's closing
# would do (FUN_02008624(event) = "seen" + backup) so that the state ends up
# IDENTICAL to having watched the cutscene (0 bits of difference across 8
# cutscenes, exp456-462). Only affects scripts with a block 23 (87 of 292:
# the story ones); boss intros (1-2 messages) do not have it.
CUTSCENE_SKIP_PATCH = [
    (0x0201C00C, "17d0", "c046"),           # FUN_0201bfd0 (op 23 sub 0): beq -> mov r8,r8
    (0x0201B1E4, "1348417f", "b0f0acf9"),   # FUN_0201b1c8: ldr r3,=...; ldrb r1,[r0,#0x1d] -> bl 0x020CB540
]
CUTSCENE_SKIP_CAVE_RAM = 0x020CB540         # area 0x020CB540-0x020CB5FF
# push {r4,lr}; ldr r4,=0x0214F500; ldrb r0,[r4,#3]; bl FUN_02008624;
# ldr r0,=0x0214F6B0; ldrb r1,[r0,#0x1d]; pop {r4,pc}; pool
CUTSCENE_SKIP_CAVE = bytes.fromhex("10b5034ce0783df76df80248417f10bd00f51402b0f61402")

# --- Biometal icons of the DATA SELECT screen (Continue) -- exp429/430,
# 2026-09-03 ---
# The drawer of each slot's icons (FUN_02036104, one sprite per icon; slot
# buffer 0x0215D808 + 0x4F4*slot = copy of the save's 0x021045CC block) does
# NOT use model_owned_count: it tests RAW bits of the slot's D0 byte (bit0
# ZX, bit1 H, bit3 L, bit5 F, bit7 P) and D2.1 (OX), and the first icon
# shows X whenever there is no ZX. With the randomizer's ownership in the
# free flags 0x02104627.0-3 the save only showed [X]. In-place patch (same
# size) per H/F/L/P icon:
#   ldrb r1,[r5,#4]; movs r0,#m; ands r1,r0; cmp r1,#0        (8 B)
#   -> ldr r1,[r5,#0x58]; lsrs r1,r1,#24; movs r0,#m'; ands r1,r0
# (u32 +0x58 aligned; its high byte = +0x5B = 0x02104627; the original `bne`
# still holds because `ands` sets Z). X/ZX icon: the "no ZX" branch becomes
# a cave that sets the X frame and HIDES the sprite (bit0 of +0xA, as the
# other cases do) if the slot does not have X (+0x03 bit7 = 0x021045CF.7).
DATASELECT_ICON_PATCH = [
    # (RAM, original bytes, new bytes)
    (0x020361FC, "2979022001400029", "a96d090e01200140"),   # H: D0.1 -> 0x02104627.0
    (0x02036218, "2979202001400029", "a96d090e02200140"),   # F: D0.5 -> .1
    (0x02036234, "2979082001400029", "a96d090e04200140"),   # L: D0.3 -> .2
    (0x02036250, "2979802001400029", "a96d090e08200140"),   # P: D0.7 -> .3
    # X/ZX icon (no-ZX branch): mov r0,r4; movs r1,#2; bl FUN_0200fe64
    #   -> bl DATASELECT_CAVE; b end_of_switch; nop
    (0x020361E2, "201c0221d9f73dfe", "95f0cdfb64e0c046"),
]
DATASELECT_CAVE_RAM = 0x020CB980     # zero-filled gap of the arm9 (0x020CB434-0x020CB9D4)
# push{r4,r5,lr}; mov r0,r4; movs r1,#2; bl FUN_0200fe64; ldrb r0,[r5,#3];
# lsls r0,r0,#24; bmi ret; ldrb r1,[r4,#0xA]; movs r0,#0xFE; ands r1,r0;
# strb r1,[r4,#0xA]; ret: pop{r4,r5,pc}   (r4 = sprite, r5 = slot block)
DATASELECT_CAVE = bytes.fromhex(
    "30b5201c022144f76dfae878000603d4a17afe200140a17230bd")

# --- "Go to Transerver" from the pause menu (MISSION/map tab) --
# exp434-436, 2026-09-03 ---
# User request: a UI option to return to the Transerver. The pause menu
# (game_state 0x101; struct 0x0215D7F8, page u8 +0x1825 = 0x0215F01D: 0
# STATUS, 1 ITEM, 2 OPTIONS, 3 MISSION/map) dispatches through pointer
# tables. On the map tab the scroll handler FUN_020272ac reads the HELD
# buttons (u16 0x020F2768): D-pad = scroll, A = fast scroll, X = leave the
# scan; Y is unused. START/B close the menu via FUN_02022b0c (called from
# FUN_0202323c @0x02023240).
# Patch: (A) the `ldr r1,=pad; ldrh r1,[r1]` of FUN_020272ac becomes
# `bl CAVE_A`, which returns r1 = held pad and, if Y has just been PRESSED
# (held & ~previous 0x020F276A, bit 11), sets WARP_FLAGS+0 = 1 (request for
# the CLIENT, which consumes it and teleports to the last Transerver
# visited) and WARP_FLAGS+1 = 1 (close menu). (B) the call to FUN_02022b0c
# becomes `bl CAVE_B`: if WARP_FLAGS+1 is set it clears it and returns 1
# (= "close", like START); otherwise it jumps to FUN_02022b0c. The tab's
# help texts (m_sub_en.bin, NitroFS at 0xDFB200, three variants) change
# "<pad>Control Pad:Scan Area Map" to "Y Button:Go to Transerver" (same
# length, in-place).
MENU_WARP_FLAGS_RAM = 0x020CB9D0    # u8 request (client) + u8 close (cave B); zero-filled gap
MENU_WARP_CAVE_A_RAM = 0x020CB99C   # after DATASELECT_CAVE (0x020CB980+26)
# ldr r2,=0x020F2768; ldrh r1,[r2]; ldrh r3,[r2,#2]; mvns r3,r3; ands r3,r1;
# lsls r3,r3,#20; bpl ret; ldr r2,=FLAGS; movs r3,#1; strb r3,[r2]; strb r3,[r2,#1]; ret: bx lr
MENU_WARP_CAVE_A = bytes.fromhex(
    "054a11885388db430b401b0503d5034a012313705370704768270f02d0b90c02")
MENU_WARP_CAVE_B_RAM = 0x020CB438   # gap between HUGATE_ARRAY (4 B) and SKIP_CAVE
# ldr r1,=FLAGS; ldrb r2,[r1,#1]; cmp r2,#0; beq orig; movs r2,#0; strb r2,[r1,#1];
# movs r0,#1; bx lr; orig: ldr r3,=FUN_02022b0c|1; bx r3
MENU_WARP_CAVE_B = bytes.fromhex(
    "04494a78002a03d000224a7001207047014b1847d0b90c020d2b0202")
MENU_WARP_HOOKS = [
    # (RAM, original bytes, new bytes)
    (0x020272B6, "1d490988", "a4f071fb"),   # FUN_020272ac: ldr r1,=pad; ldrh r1,[r1] -> bl CAVE_A
    (0x02023240, "fff764fc", "a8f0faf8"),   # FUN_0202323c: bl FUN_02022b0c -> bl CAVE_B
]
MENU_WARP_TEXT_ROM = 0xDFB200        # m_sub_en.bin (NitroFS, uncompressed; verified byte by byte)
# SHA-256 of the 27 vanilla bytes ("<pad>Control Pad:Scan Area Map"); the
# game text itself is not kept in the repository.
MENU_WARP_TEXT_SHA256 = "86da91168288b97f4ace3c34a86eba342e97e9afec9bb70949110693930c65a0"
MENU_WARP_TEXT_NEW = bytes.fromhex("3900225554544f4e1a274f00544f003452414e5345525645520000")  # Y Button:Go to Transerver
MENU_WARP_TEXT_OFFS = (0xB14, 0xB4B, 0xB85)   # 3 variants (no/1/several servers in the area)

# --- Secret Disk sprite = ARCHIPELAGO LOGO (agent exp463-467,
# 2026-09-04; docs/v02_notes.md sec. 2b) ---
# obj_fnt.bin (NitroFS id 235, ROM 0x00F09000) holds 511 object graphics
# "sets"; the disk body is unit 0x11 (16x16, 4bpp OBJ 1D, 4 tiles
# TL/TR/BL/BR, low nibble = left pixel, 128 B) of set 58 (item atlas:
# refills, 1-Up, disk, sparkles), OBJ palette slot 1. The 4 series (B/M/E/O)
# share the frame. Set 58 is loaded into VRAM once at boot. In-place patch,
# same size, no recompression (outside the header CRC). Logo v1 (circle
# with an "A", exp465) replaced by the adapted official logo (exp495; see
# DISK_LOGO_NEW).
# Cold-verified: VRAM = logo, the A-2/E-1 disk is visible and collectable.
DISK_LOGO_ROM = 0x00F5F20C   # obj_fnt.bin + 0x5620C
# SHA-256 of the 128 vanilla bytes of the disk body tile (the game's
# graphics are not kept in the repository, only their digest).
DISK_LOGO_SHA256 = "0cf5040681e341af0f130f438c12989c4747f7b7c531792025e6e8f9d9f8c65c"
DISK_LOGO_NEW = bytes.fromhex(   # OFFICIAL Archipelago logo (16x16 sprite of the Metroid Zero
    # Mission apworld, mzm/patcher/data/item_sprites/ap_logo.gfx frame 0) with its 6
    # "islands" remapped to the disk's palette 1: maroon 9, orange C, greens 1-3, blue 5,
    # blue-violet 4 (there is no purple), red A (there is no pink), white outline F;
    # transparent centre. Reproducible conversion: work/experiments/495_ap_logo_official.py
    "000000f00000009f00f0ff9900cfcc9ff0ccccfcf0ccccfcf0fcfffc005f550f"
    "ff000000990f000099f9ff00991f110ff91111f1f91111f1fff1fff1004f440f"
    "f05555f5f05555f5f05555af005ff5aa00f0ffaa0000f0aa000000af000000f0"
    "f04444f4ff4444f4aa4f44f4aafa440faafaff00aafa0000aa0f0000ff000000")


# --- ITEM ICONS IN THE WORLD (2026-09-05, exp560-569; docs/v02_notes.md sec. 2c) ---
# Every physical pickup (94 disks, 8 Life Up/Sub Tank, 133 refills) is drawn with
# the icon of the ITEM the randomizer placed there: a graphics SET of our own
# ("AP", built at patch time by icons.py from the player's ROM: 3 Archipelago
# logos useful/progression/filler, Life Up, Sub Tank, 8 chips, 8 model badges from
# the STATUS menu, 6 Card Keys from the ITEM C menu; 4bpp, 1 palette of 16) is
# INSERTED as set ICON_SET (empty in vanilla) into obj_fnt.bin/obj_dat.bin (the
# offsets of the following sets shift; both files are relocated to the final
# padding of the ROM by rewriting the FAT, recipe exp551d/552b) and made RESIDENT
# like set 58: the global set list [0,1,58] of FUN_0200bd04 (u16[3] @0x020C9C30,
# with an alignment gap) becomes [0,1,58,ICON_SET] and its two `movs r2,#3` become
# #4; the boot cave (in place of set 58's `bl FUN_02006164`) registers a static
# VRAM slot + palette slot (FUN_02006a88(mgr, fnt[set], set, 3,1,1) +
# FUN_02006164(mgr, set, 0,0,0,0,1,0)). Verified (exp567b/569b): VRAM slot 3 and
# OBJ palette 2 constant across the 69 rooms + boss; VRAM max 123/128 KB.
# The CLIENT writes the TABLE per subarea (ICON_TABLE_RAM, free RAM between the
# overlay slot 0x02184000 and 0x02194000, never read nor written by the game:
# exp560):
#   +0 u8 sub, +1 u8 flags (bit0 = valid), +4 u8 code[128] (coords index of the
#   entity -> anim+1 of the AP set; 0 = no change), +0x84 u8 checked[32] (bitmap by
#   idx: "already sent" -> vanilla look; refills respawn as what they are).
# Caves (Thumb, HOLE_C8150 = zeroed stretch of the arm9 with no accesses, exp560):
# LOOKUP(ent) finds the entity in the spawn list 0x021081F4 ([+4] = ent, u16[+8] =
# idx; exp566: it is already registered in the three inits) and returns anim or
# -1; ATTACH replaces the 3 `bl FUN_02010624` (disk 0x020A3BC4, Life Up/Sub Tank
# 0x020A3EEE, refill 0x020A36F4) -> with an override it calls FUN_02010624(ent,
# ICON_SET) clearing +0xB.3 (dynamic) and +0xC.0 (palette of another set); ANIM
# replaces the 3 following `bl FUN_0200fe64` (0x020A3BCC / 0x020A3EF6 /
# 0x020A3706) -> if u16[ent+0x22] == ICON_SET it uses the anim from LOOKUP. The
# pickup itself does not change (exp568c).
# Replaces the grey marker PICKUP_MARK (the cave was retired; its gap is free).
ICON_SET = 261
ICON_FNT_FILE_ID, ICON_DAT_FILE_ID = 235, 234     # obj_fnt.bin / obj_dat.bin (NitroFS)
DISK_LOGO_FNT_OFF = 0x5620C                       # = DISK_LOGO_ROM - vanilla start of obj_fnt (0x00F09000)
ICON_TABLE_RAM = 0x02191460
ICON_TABLE_SIZE = 0xC4                            # +0xA4 `present` bitmap (PICKUP_AP, 2026-09-07)
ICON_RESIDENT_LIST_PATCH = [
    (0x020C9C36, "0000", "0501"),     # 4th u16 entry of the list [0,1,58] (alignment gap)
    (0x0200BD16, "0322", "0422"),     # FUN_0200bd04: movs r2,#3 -> #4 (fnt)
    (0x0200BDB6, "0322", "0422"),     # FUN_0200bd04: movs r2,#3 -> #4 (dat)
]
ICON_BOOT_HOOK_RAM = 0x0200BDA8                   # bl FUN_02006164 (VRAM upload of set 58) -> cave
ICON_BOOT_HOOK_ORIG = "faf7dcf9"
ICON_BOOT_CAVE_RAM = 0x020C8150                   # HOLE_C8150 (0x020C8150-0x020C8394 zeroed and with no accesses, exp560)
ICON_BOOT_CAVE = bytes.fromhex("10b584b000240094019401240294002403940f483a21002200230e4ca04701240094c0460c480d4909680d4a03230d4ca047002400940194012402940024039409480a4900220023094ca04700f074f840571002656100024057100234390f0205010000896a0002405710020501000065610002")
# The AP set does NOT ask for its own palette (`str r4,[sp,#4]` -> nop in the boot
# cave) and shares set 58's (resident, always loaded): PALSHARE writes
# 0x02105EE4[261] = 0x02105EE4[58] and returns through the cave's epilogue. If it
# asked for one, the game would sit at 15 of 15 OBJ palettes in the heavy rooms and
# the next dynamic set (e.g. the hit effect of F-5) would not get registered -> NULL
# pointer in the drawer -> data abort (user's crash; exp585-589, docs/v02_notes.md sec. 2k).
PALSHARE_CAVE_RAM = 0x020C8288             # after SPRITEGUARD_CAVE (0x020C827C + 10)
PALSHARE_CAVE = bytes.fromhex("03483a21415c0348017004b010bdc046e45e1002e95f1002")
# RETRY (2026-09-09, exp606-607; user report: "sometimes the pickup came out with the
# generic logo instead of the useful/progression/filler icon"): ATTACH/ANIM decide the
# look only ONCE, in the entity's init, and the spawner instantiates by proximity: a
# pickup near the room entrance is born BEFORE the client (polling every 125 ms)
# writes the table of the new sub, or before the LocationScouts arrive (code 0), and
# keeps its vanilla set, whose tile on the disk is the generic logo (DISK_LOGO_NEW).
# RETRY replaces the `bl FUN_0200fc0c` (animation advance, every frame) of the three
# think handlers (refill: through the mailbox cave, disk 0x020A3A7E, Life Up/Sub Tank
# 0x020A3CAA): if u16[ent+0x22] != 261 and LOOKUP(ent) >= 0 it repeats the init's
# attach (clears +0xB.3/+0xC.0, FUN_02010624(ent,261), FUN_0200fe64(ent,anim)) and
# always calls FUN_0200fc0c(ent). It never downgrades (a sent pickup disappears or
# respawns).
ICON_RETRY_CAVE_RAM = 0x020C82A0           # after PALSHARE_CAVE (0x020C8288 + 24)
ICON_RETRY_CAVE = bytes.fromhex("30b50400628c0e4b9a4214d0fff78aff002810db0500e17a08229143e172217b0122914321732000064948f7abf92000290047f7c7fd200047f798fc30bd00bf0501000005010000")
# refill: the site 0x020A30A2 already belongs to the MAILBOX cave (PICKUP_MAILBOX), so
# RETRY is chained on the `bl FUN_0200fc0c` of THAT cave (0x020CB4A2, r0 = r5 = ent);
# disk and Life Up/Sub Tank in their think. Installed after the mailbox (patch_arm9 order).
ICON_RETRY_HOOKS = [(0x020CB4A2, "44f7b3fb"), (0x020A3A7E, "6cf7c5f8"), (0x020A3CAA, "6bf7afff")]
ICON_CAVES_RAM = 0x020C81C4                       # lookup / attach / anim (after the boot cave)
ICON_CAVES = bytes.fromhex("30b5264c2178264a127891421cd16178c90719d023490968002915d04a68824201d00968f8e70a89802a0dd2d3088433e35c07251540eb40db0705d1231d985c002801d0013830bd0020c04330bd30b504000d00fff7d4ff002808dbe17a08229143e172217b0122914321730e4d200029000e4a904730bd30b504000d00428c0b4b9a4204d1fff7bbff002800db050020002900074a904730bd00bf6014190228821002f481100205010000250601020501000065fe0002")
ICON_ATTACH_CAVE_RAM = 0x020C8212
ICON_ANIM_CAVE_RAM = 0x020C823C
ICON_ATTACH_HOOKS = [(0x020A3BC4, "6cf72efd"), (0x020A3EEE, "6cf799fb"), (0x020A36F4, "6cf796ff")]
ICON_ANIM_HOOKS = [(0x020A3BCC, "6cf74af9"), (0x020A3EF6, "6bf7b5ff"), (0x020A3706, "6cf7adfb")]


def _thumb_bl(src: int, dst: int) -> bytes:
    """Encode a Thumb `bl dst` (4 B) located at src."""
    import struct
    off = dst - (src + 4)
    return struct.pack("<HH", 0xF000 | ((off >> 12) & 0x7FF), 0xF800 | ((off >> 1) & 0x7FF))


def _gfx_data(name: str) -> bytes:
    """Bytes of a file of gfx/ (the Archipelago logo sprites), whether the world
    runs from a directory or from a zipped .apworld."""
    """Binary blob from worlds/mmzx/gfx/ (also inside the .apworld)."""
    import os
    import pkgutil
    try:
        data = pkgutil.get_data(__name__.rsplit(".", 1)[0], "gfx/" + name)
    except Exception:
        data = None
    if data is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gfx", name), "rb") as f:
            data = f.read()
    return data


def _insert_set(blob: bytes, setno: int, block: bytes) -> bytes:
    """Insert `block` as set `setno` (currently empty) into an obj_fnt/obj_dat file
    (u32 count + u32 offset[count+1]; size of set i = off[i+1]-off[i])."""
    import struct
    n = struct.unpack_from("<I", blob, 0)[0]
    offs = [struct.unpack_from("<I", blob, 4 + i * 4)[0] for i in range(n + 1)]
    if offs[n] != len(blob):
        raise ValueError("MMZX: unexpected offset table in the sprite set file")
    if offs[setno] != offs[setno + 1]:
        raise ValueError("MMZX: sprite set %d is not empty" % setno)
    block = block + bytes((-len(block)) % 4)
    new = bytearray(blob[:4])
    for i in range(n + 1):
        new += struct.pack("<I", offs[i] + (len(block) if i > setno else 0))
    new += blob[4 + (n + 1) * 4:offs[setno]] + block + blob[offs[setno]:]
    return bytes(new)


def _install_icon_set(d: bytearray) -> int:
    """Build the AP icon set from the player's own sprite sets (icons.py), insert
    it into obj_dat / obj_fnt and relocate both files to the free padding at the
    end of the ROM (FAT + "used size" at 0x80). Returns the new start of
    obj_fnt.bin."""
    import struct

    from . import icons
    fat = struct.unpack_from("<I", d, 0x48)[0]
    fatsize = struct.unpack_from("<I", d, 0x4C)[0]
    used = max(struct.unpack_from("<II", d, fat + k * 8)[1] for k in range(fatsize // 8))
    cur = (used + 0x1FF) & ~0x1FF
    files = {}
    for fid in (ICON_DAT_FILE_ID, ICON_FNT_FILE_ID):
        s0, e0 = struct.unpack_from("<II", d, fat + fid * 8)
        files[fid] = bytes(d[s0:e0])
    fnt_block, dat_block = icons.build_icon_set(files[ICON_FNT_FILE_ID], files[ICON_DAT_FILE_ID], _gfx_data)
    fnt_start = None
    for fid, block in ((ICON_DAT_FILE_ID, dat_block), (ICON_FNT_FILE_ID, fnt_block)):
        newfile = _insert_set(files[fid], ICON_SET, block)
        if cur + len(newfile) > len(d) or any(d[cur:cur + len(newfile)]):
            raise ValueError("MMZX: no free padding to relocate file %d" % fid)
        d[cur:cur + len(newfile)] = newfile
        struct.pack_into("<II", d, fat + fid * 8, cur, cur + len(newfile))
        if fid == ICON_FNT_FILE_ID:
            fnt_start = cur
        cur = (cur + len(newfile) + 0x1FF) & ~0x1FF
    struct.pack_into("<I", d, 0x80, cur)          # "used ROM size"
    return fnt_start

# --- BLZ (DS code compression) with an optimal parse ---------------------------
# The recompressed ARM9 must fit back into its slot of the ROM (0x8F400 bytes).
# A greedy encoder leaves 76 bytes of headroom and the pickup mailbox cave no
# longer fits, so the tokens are chosen by dynamic programming instead:
# 0x8DB04 bytes instead of 0x8F3A8 (6.3 KB of headroom, ~6 s).
#
# Format, as executed by the game's C runtime (apnds.lz.decompress_code is the
# reference decoder): the data after the 0x4000-byte uncompressed header is
# encoded BACKWARDS. Read from its end, the stream is a sequence of groups:
# one flag byte (MSB first) followed by up to eight tokens. Flag 0 = a literal
# byte; flag 1 = a two-byte reference ((len-3) << 4 | disp >> 8, disp & 0xFF)
# that copies `len` (3..18) bytes from `disp + 3` (3..0x1002) bytes AHEAD of
# the byte being written. The stream is decoded in place, top-down, so the
# start of the region stays uncompressed ("raw prefix") wherever compressing
# it would make the decoder overwrite input it has not read yet. A 12-byte-
# aligned footer closes the region: u24 compressed size including the footer,
# u8 footer size (8 + 0xFF padding), u32 bytes gained by decompressing.
BLZ_HEADER_LEN = 0x4000        # ARM9 bytes never compressed (secure area + crt0)
BLZ_MIN_MATCH = 3
BLZ_MAX_MATCH = 18
BLZ_MAX_DIST = 0x1002          # encoded displacement 0xFFF + 3


def _blz_longest_matches(r):
    """For each position q of `r` (the data reversed, so references point
    backwards), the longest block r[q:q+L], 3 <= L <= 18, that also occurs
    entirely before q and at most 0x1002 bytes back, together with the nearest
    such occurrence. Returns two lists (lengths, positions); length 0 = none."""
    n = len(r)
    lengths = [0] * n
    where = [0] * n
    rfind = r.rfind
    for q in range(n - BLZ_MIN_MATCH + 1):
        lo = q - BLZ_MAX_DIST
        if lo < 0:
            lo = 0
        p = rfind(r[q:q + BLZ_MIN_MATCH], lo, q)
        if p < 0:
            continue
        best_len, best_pos = BLZ_MIN_MATCH, p
        # A longer block matches only if every shorter one does, so the
        # feasible lengths form a prefix of 3..top: bisect it.
        low, high = BLZ_MIN_MATCH + 1, min(BLZ_MAX_MATCH, n - q)
        while low <= high:
            mid = (low + high) >> 1
            p = rfind(r[q:q + mid], lo, q)
            if p < 0:
                high = mid - 1
            else:
                best_len, best_pos = mid, p
                low = mid + 1
        lengths[q] = best_len
        where[q] = best_pos
    return lengths, where


def _blz_parse(r, lengths):
    """Optimal parse: for every position the token (0 = literal, L = reference
    of L bytes) that minimises the size of the rest of the stream, counting a
    literal as 9 bits and a reference as 17 (their bytes plus the flag bit)."""
    n = len(r)
    cost = [0] * (n + 1)
    pick = [0] * n
    for i in range(n - 1, -1, -1):
        best, tok = cost[i + 1] + 9, 0
        for ln in range(BLZ_MIN_MATCH, lengths[i] + 1):
            c = cost[i + ln] + 17
            if c < best:
                best, tok = c, ln
        cost[i] = best
        pick[i] = tok
    return pick


def _blz_compress(data):
    """Compress `data` (the ARM9 minus its BLZ_HEADER_LEN header) into a BLZ
    region: raw prefix + backwards stream + footer. Returns None if the region
    would not be smaller than the data."""
    r = data[::-1]                       # encode the reversed data forwards
    n = len(r)
    lengths, where = _blz_longest_matches(r)
    pick = _blz_parse(r, lengths)

    # Tokens in decoding order; `stream` grows in decoding order too, so the
    # bytes the decoder reads first come first. `gain` tracks how many bytes
    # the decoder is ahead by after each token (output produced minus stream
    # consumed, flag bytes included). The in-place decoder is safe exactly
    # when every remaining part of the stream still has a non-negative gain,
    # i.e. when the stream is cut at a point where `gain` reaches its maximum;
    # the first such point gives the smallest region.
    stream = bytearray()
    i = 0
    tokens = 0
    gain = 0
    best_gain = 0
    cut_stream = 0                       # stream bytes kept
    cut_data = 0                         # reversed-data bytes covered by them
    while i < n:
        flag_at = len(stream)
        stream.append(0)
        gain -= 1
        flags = 0
        for bit in range(7, -1, -1):
            if i >= n:
                break
            ln = pick[i]
            if ln:
                disp = i - where[i] - BLZ_MIN_MATCH
                flags |= 1 << bit
                stream.append(((ln - BLZ_MIN_MATCH) << 4) | (disp >> 8))
                stream.append(disp & 0xFF)
                i += ln
                gain += ln - 2
            else:
                stream.append(r[i])
                i += 1
            tokens += 1
            if gain > best_gain:
                best_gain = gain
                cut_stream = len(stream)
                cut_data = i
        stream[flag_at] = flags
    if best_gain <= 0:
        return None

    raw = data[:n - cut_data]            # forward order: the uncut start
    body = bytes(stream[:cut_stream])[::-1]
    padding = (-(len(raw) + len(body))) & 3
    footer_len = 8 + padding
    total = len(raw) + len(body) + footer_len
    if total >= n:
        return None
    return b"".join((
        raw, body, b"\xFF" * padding,
        (len(body) + footer_len).to_bytes(3, "little"),
        bytes([footer_len]),
        (n - total).to_bytes(4, "little"),
    ))


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Decompress the ARM9 (BLZ), apply the code patches (everything that
        is always on, plus the Hu gate when hu_in_pool), recompress it and put
        it back IN PLACE in its original slot: the rest of the 64 MiB image
        stays byte-identical (only the ARM9, its size in the header at 0x2C
        and the header CRC16 at 0x15E change). Never rebuild the whole ROM
        with a library (apnds Rom.to_bytes and the like): a repacked ~44 MB
        image shifts the layout and melonDS/BizHawk dies with std::bad_alloc
        when loading it (verified on real BizHawk, exp205). apnds (MIT, see
        apnds/LICENSE) is used only to split the ARM9 into its autoload
        sections and to write the start parameters back."""
        import struct

        from .apnds.code import CodeStartParams, START_INFO_SIGNATURE_DS

        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        d = bytearray(rom)
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", d, 0x20)
        code = bytes(d[arm9_off:arm9_off + arm9_len])
        params = CodeStartParams.from_code(code, arm9_ram)
        if params is None or params.compressed_end is None:
            raise ValueError("MMZX: ARM9 start parameters not found. Wrong ROM?")
        if code.find(START_INFO_SIGNATURE_DS) >= BLZ_HEADER_LEN:
            raise ValueError("MMZX: ARM9 start parameters outside the uncompressed header")
        split, rem = params.get_sections(code, arm9_ram)
        if rem:
            raise ValueError("MMZX: unexpected data after the compressed ARM9")
        # (RAM address, data) per piece: the main code, every autoload section
        # at its destination (ITCM / DTCM) and the autoload table after them
        sections = []
        pos = arm9_ram
        for data, info in split:
            sections.append((info.destination if info else pos, bytearray(data)))
            pos += len(data)

        def poke(ram, data, orig=None):
            for base, buf in sections:
                if base <= ram < base + len(buf):
                    off = ram - base
                    cur = bytes(buf[off:off + len(data)])
                    if cur == data:
                        return  # idempotent
                    if orig is not None and cur != orig:
                        raise ValueError(
                            "MMZX: unexpected bytes at 0x%08X (%s, expected "
                            "%s). Wrong ROM?" % (ram, cur.hex(), orig.hex()))
                    buf[off:off + len(data)] = data
                    return
            raise ValueError("MMZX: 0x%08X is outside the ARM9 sections" % ram)

        # 1) tutorial-skip (always): entry (with a guard on the original bytes)
        #    + code cave conditional on game_state
        poke(SKIP_ENTRY_RAM, SKIP_ENTRY, SKIP_ENTRY_ORIG)
        poke(SKIP_CAVE_RAM, SKIP_CAVE)
        # 1b) OAM drawer guard (always; robustness against soft-locks):
        #     `beq` -> `bls` at the end of the sprite loop of FUN_02009b74
        poke(OAMLOOP_BR_RAM, OAMLOOP_BR_NEW, OAMLOOP_BR_ORIG)
        poke(OAMLOOP2_BR_RAM, OAMLOOP2_BR_NEW, OAMLOOP2_BR_ORIG)
        # 1c bis) the Operator's yellow key dialogue no longer repeats
        poke(YELLOWKEY_BR_RAM, YELLOWKEY_BR_NEW, YELLOWKEY_BR_ORIG)
        # 1c) "AP item only" biometal ownership (always): the boss victory no
        #     longer grants the model; each copy of the progressive item sets
        #     one half (list [half 1, half 2]; vanilla count = 2)
        for cnt_a, lst_a, flag1, orig1, flag2, orig2 in BIOMETAL_CAT_PATCH.values():
            poke(lst_a, flag1.to_bytes(4, "little"), orig1.to_bytes(4, "little"))
            poke(lst_a + 4, flag2.to_bytes(4, "little"), orig2.to_bytes(4, "little"))
            poke(cnt_a, bytes([BIOMETAL_CAT_COUNT]), bytes([BIOMETAL_CAT_COUNT]))
        # 1d) Life Ups / Sub Tanks: "collected" = high nibble (always)
        for ram, orig, new in PICKUP_FLAG_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # 1e) mailbox of respawnable pickups (always; the client only uses it
        #     with the pickup_checks_* options): hook + cave + zeroed mailbox
        assert len(PICKUP_MAILBOX_CAVE) <= PICKUP_MAILBOX_RAM - PICKUP_MAILBOX_CAVE_RAM
        poke(PICKUP_MAILBOX_CAVE_RAM, PICKUP_MAILBOX_CAVE,
             bytes(len(PICKUP_MAILBOX_CAVE)))
        poke(PICKUP_MAILBOX_HOOK_RAM, PICKUP_MAILBOX_HOOK_NEW, PICKUP_MAILBOX_HOOK_ORIG)
        # 1f) DATA SELECT biometal icons = the randomizer's ownership
        #     (always): H/F/L/P through 0x02104627.0-3 and X hidden if not owned
        for ram, orig, new in DATASELECT_ICON_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        poke(DATASELECT_CAVE_RAM, DATASELECT_CAVE, bytes(len(DATASELECT_CAVE)))
        # 1g) "Go to Transerver" on the MISSION tab of the pause menu (always)
        assert len(MENU_WARP_CAVE_A) <= MENU_WARP_FLAGS_RAM - MENU_WARP_CAVE_A_RAM
        assert len(MENU_WARP_CAVE_B) <= SKIP_CAVE_RAM - MENU_WARP_CAVE_B_RAM
        poke(MENU_WARP_CAVE_A_RAM, MENU_WARP_CAVE_A, bytes(len(MENU_WARP_CAVE_A)))
        poke(MENU_WARP_CAVE_B_RAM, MENU_WARP_CAVE_B, bytes(len(MENU_WARP_CAVE_B)))
        for ram, orig, new in MENU_WARP_HOOKS:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # 1h) on-screen notices from the client (small popup; always)
        assert len(NOTIFY_CAVE) <= NOTIFY_RAM - NOTIFY_CAVE_RAM
        poke(NOTIFY_CAVE_RAM, NOTIFY_CAVE, bytes(len(NOTIFY_CAVE)))
        poke(NOTIFY_HOOK_RAM, NOTIFY_HOOK_NEW, NOTIFY_HOOK_ORIG)
        # 1i) cutscenes always skippable with START (always)
        assert CUTSCENE_SKIP_CAVE_RAM + len(CUTSCENE_SKIP_CAVE) <= NOTIFY_CAVE_RAM
        poke(CUTSCENE_SKIP_CAVE_RAM, CUTSCENE_SKIP_CAVE, bytes(len(CUTSCENE_SKIP_CAVE)))
        for ram, orig, new in CUTSCENE_SKIP_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # 1j) item icons in the world (always): resident AP set + caves
        for ram, orig, new in ICON_RESIDENT_LIST_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        assert ICON_BOOT_CAVE_RAM + len(ICON_BOOT_CAVE) <= ICON_CAVES_RAM
        assert ICON_CAVES_RAM + len(ICON_CAVES) <= 0x020C8394
        poke(ICON_BOOT_CAVE_RAM, ICON_BOOT_CAVE, bytes(len(ICON_BOOT_CAVE)))
        poke(ICON_BOOT_HOOK_RAM, _thumb_bl(ICON_BOOT_HOOK_RAM, ICON_BOOT_CAVE_RAM),
             bytes.fromhex(ICON_BOOT_HOOK_ORIG))
        poke(ICON_CAVES_RAM, ICON_CAVES, bytes(len(ICON_CAVES)))
        assert PALSHARE_CAVE_RAM + len(PALSHARE_CAVE) <= 0x020C8394
        poke(PALSHARE_CAVE_RAM, PALSHARE_CAVE, bytes(len(PALSHARE_CAVE)))
        assert ICON_RETRY_CAVE_RAM >= PALSHARE_CAVE_RAM + len(PALSHARE_CAVE)
        assert ICON_RETRY_CAVE_RAM + len(ICON_RETRY_CAVE) <= 0x020C8394
        poke(ICON_RETRY_CAVE_RAM, ICON_RETRY_CAVE, bytes(len(ICON_RETRY_CAVE)))
        for ram, orig in ICON_RETRY_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_RETRY_CAVE_RAM), bytes.fromhex(orig))
        for ram, orig in ICON_ATTACH_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_ATTACH_CAVE_RAM), bytes.fromhex(orig))
        for ram, orig in ICON_ANIM_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_ANIM_CAVE_RAM), bytes.fromhex(orig))

        # 1j) drawer guard: a set without a VRAM slot no longer reads address 2
        #     (data abort). Latent bug of the game exposed by the AP set (exp585).
        assert SPRITEGUARD_CAVE_RAM + len(SPRITEGUARD_CAVE) <= 0x020C8394
        assert SPRITEGUARD_CAVE_RAM >= ICON_CAVES_RAM + len(ICON_CAVES)
        poke(SPRITEGUARD_CAVE_RAM, SPRITEGUARD_CAVE, bytes(len(SPRITEGUARD_CAVE)))
        for ram in SPRITEGUARD_SITES:
            poke(ram, _thumb_bl(ram, SPRITEGUARD_CAVE_RAM), SPRITEGUARD_ORIG)
        # 1k) pickups replaced by AP items: no vanilla effect/popup/label
        #     (always; decided by the client's table, `present` bitmap)
        assert PICKUP_AP_CAVE_RAM + len(PICKUP_AP_CAVE) <= DATASELECT_CAVE_RAM
        poke(PICKUP_AP_CAVE_RAM, PICKUP_AP_CAVE, bytes(len(PICKUP_AP_CAVE)))
        for ram, orig, entry, pre, post in PICKUP_AP_HOOKS:
            new = (bytes.fromhex(pre) + _thumb_bl(ram + len(pre) // 2, PICKUP_AP_CAVE_RAM + PICKUP_AP_ENTRIES[entry])
                   + bytes.fromhex(post))
            assert len(new) == len(orig) // 2
            poke(ram, new, bytes.fromhex(orig))
        # 2) Hu-gate (optional)
        if hu_in_pool:
            poke(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
            poke(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"),
                 HUGATE_LISTS0_ORIG)

        # recompress (optimal parse: a greedy encoder no longer fits in the
        # slot once the mailbox cave is in) and put it back in the original slot
        pieces = [(bytes(buf), info) for (_, buf), (_, info) in zip(sections, split)]
        packed = params.pack_code_from_sections((pieces, rem), arm9_ram, "9",
                                                try_compress=False)
        body = _blz_compress(packed[BLZ_HEADER_LEN:])
        if body is None:
            raise ValueError("MMZX: the ARM9 did not compress")
        params.compressed_end = arm9_ram + BLZ_HEADER_LEN + len(body)
        blob = params.write_start_info(packed, arm9_ram)[:BLZ_HEADER_LEN] + body
        # the 12-byte "nitrocode" footer(s) that follow the ARM9 in the ROM
        post_off = post_end = arm9_off + arm9_len
        while bytes(d[post_end:post_end + 4]) == b"\x21\x06\xC0\xDE":
            post_end += 12
        post = bytes(d[post_off:post_end])
        others = [struct.unpack_from("<I", d, o)[0]
                  for o in (0x30, 0x40, 0x48, 0x50, 0x68)]
        slot_end = min(x for x in others if x > arm9_off)
        if len(blob) + len(post) > slot_end - arm9_off:
            raise ValueError(
                "MMZX: the recompressed ARM9 (0x%X+%d) does not fit in its slot "
                "(0x%X)" % (len(blob), len(post), slot_end - arm9_off))
        d[arm9_off:arm9_off + len(blob)] = blob
        end = arm9_off + len(blob)
        d[end:end + len(post)] = post
        d[end + len(post):slot_end] = b"\x00" * (slot_end - end - len(post))
        struct.pack_into("<I", d, 0x2C, len(blob))

        # AP set inserted into obj_dat/obj_fnt and both files relocated to the padding
        fnt_start = _install_icon_set(d)

        # help texts of the MISSION tab (NitroFS in-place, same length)
        for off in MENU_WARP_TEXT_OFFS:
            o = MENU_WARP_TEXT_ROM + off
            cur = bytes(d[o:o + len(MENU_WARP_TEXT_NEW)])
            if cur == MENU_WARP_TEXT_NEW:
                continue
            if hashlib.sha256(cur).hexdigest() != MENU_WARP_TEXT_SHA256:
                raise ValueError("MMZX: unexpected text at m_sub_en.bin+0x%X (%s)" % (off, cur.hex()))
            d[o:o + len(MENU_WARP_TEXT_NEW)] = MENU_WARP_TEXT_NEW

        # Secret Disk sprite = Archipelago logo (128 B in-place inside the already
        # relocated obj_fnt.bin: set 58 comes before the AP set, same offset)
        logo_off = fnt_start + DISK_LOGO_FNT_OFF
        cur = bytes(d[logo_off:logo_off + len(DISK_LOGO_NEW)])
        if cur != DISK_LOGO_NEW:
            if hashlib.sha256(cur).hexdigest() != DISK_LOGO_SHA256:
                raise ValueError("MMZX: unexpected disk tile at ROM 0x%X (%s)" % (logo_off, cur[:8].hex()))
            d[logo_off:logo_off + len(DISK_LOGO_NEW)] = DISK_LOGO_NEW

        # header CRC16 (CRC-16/MODBUS over [0:0x15E])
        crc = 0xFFFF
        for b in bytes(d[:0x15E]):
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        struct.pack_into("<H", d, 0x15E, crc)
        return bytes(d)


class MMZXPatch(APProcedurePatch, APTokenMixin):
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    # 1) ARM9 patch (BLZ): skip + optional Hu-gate; 2) AP marker + slot.
    procedure = [
        ("patch_arm9", ["mmzx_cfg.bin"]),
        ("apply_tokens", ["token_data.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(get_settings().mmzx_settings.rom_file, "rb") as f:
            return f.read()


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str,
                       hu_in_pool: bool = False) -> None:
    blob = bytearray(0x80)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    blob[0x08:0x0C] = WORLD_VERSION_INT.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:63]
    blob[0x10:0x10 + len(name)] = name
    seed = seed_name.encode("utf-8")[:31]
    blob[0x50:0x50 + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
    # config read by patch_arm9 (before apply_tokens): option flags.
    cfg = bytearray(4)
    cfg[0] = CFG_HU_IN_POOL if hu_in_pool else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
