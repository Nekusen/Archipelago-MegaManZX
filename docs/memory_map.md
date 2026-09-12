# Memory map

This document lists the RAM addresses, ROM offsets and data layouts the
Mega Man ZX apworld relies on: what the client reads and writes on every
tick, what the ROM patch changes, and the structures the two share. It is
written for a developer who opens the repository for the first time, knows
Archipelago and has a rough idea of how a Nintendo DS game is laid out. It
is a table of facts, not a tutorial. The "used by" column names the module
that touches each address so the code can be read next to it.

Conventions. Everything refers to the USA ROM (game code ARZE). Addresses
are ARM9 main RAM addresses (0x02xxxxxx) unless marked ROM, which is an
offset into the .nds file. The client reads RAM through the BizHawk domain
"ARM9 System Bus" and the ROM header through the domain "ROM". A "flag" is
an index into the progress bitfield: flag n lives at byte 0x021045CC + n/8,
bit n%8. Bit notation is address.bit, so 0x021045CF.7 is bit 7 of that
byte. Overlays are the game's loadable code modules: 0-32 load at
0x02177E00 (scene and boss code), 33-42 at 0x02184000 (one per model) and
43-116 at 0x02194000 (one per room).

Live and canonical. The game keeps the progress block in two places. The
live copy at 0x021045CC is what the running game reads. The canonical copy
at 0x021602B4 is what survives: the game copies canonical over live on death
and respawn, refreshes canonical from live at checkpoints, and serialises
canonical into the save. A bit set only in the live copy is lost on the next
death; a bit set only in the canonical copy shows up late. The client
therefore writes progress bits to both copies (canonical = live + 0x5BCE8).
A third copy, mirror B at 0x02160398, is the snapshot taken when a mission
is accepted; Abort Mission restores it, so the client refreshes it before
force-accepting a mission.

## 1. Progress block

The block is 0xE4 bytes. The table lists the windows the apworld uses; the
sub-sections below expand the bitfields.

| address | size | name in code | meaning | used by |
|---|---|---|---|---|
| 0x021045C0 | 12 | GOAL_BITS | 96 unique cutscene events; 0x021045CA.5 = Serpent epilogue seen (goal) | client |
| 0x021045CC | 0xE4 | LIVE_BLOCK | progress block, live copy; base of the flag bitfield | both |
| 0x021602B4 | 0xE4 | CANON_BLOCK | canonical copy, same layout | both |
| 0x02160398 | 0xE4 | BLOCK_MIRROR | mirror B, mission-start snapshot of the canonical copy | client |
| 0x021045CF.7 | bit | MODEL_X_POSSESSION | Model X owned (flag 31) | both |
| 0x021045D0.0 | bit | MODEL_POSSESSION | Model ZX owned (flag 32) | client |
| 0x021045D0/D1 | 2 | LOCATIONS detect | boss victory bits, D0 first Pseudoroid of a pair, D1 second (1.1) | client |
| 0x021045D2.1 | bit | MODEL_POSSESSION | Model OX owned (flag 49) | client |
| 0x021045DD.0 | bit | HUGATE_FLAG_INDEX | Model Hu owned (flag 136); only tested with the Hu gate patch | both |
| 0x021045DE..E8 | 11 | MISSION_ACCEPT | mission start flags (1.3) | client |
| 0x021045E0.4-7, E1.0 | bits | MISSION_ACCEPT extra | Troop Reinforcement story chain (1.3) | client |
| 0x021045FB, FD.3, E3.7, E5.5, E8.1 | bits | EVENT_GATES | event gates (1.4) | client |
| 0x021045FC.5-7, FD.0-2 | bits | CARDKEY_MASKS | Card Keys (1.2) | client |
| 0x021045FF.4-7, 0x02104600.0-3 | bits | FLAG_LEFT, FLAG_RIGHT | boss rush pairs beaten (1.8) | client |
| 0x02104602.1 | bit | TROOP_MERGE | Troop megamerge done; blocks the Giro scene while set | client |
| 0x02104602.2-3 | bits | ENDING_SERPENT, GOAL_BITS_ALT | Serpent form 1 and form 2 defeated | client |
| 0x02104603..0F | 13 | LOCATIONS detect | Secret Disk bits (1.7) | client |
| 0x0210461D.5-7, 1E.0-4 | bits | ITEMS grant | ITEM B chips owned (1.6) | client |
| 0x02104626.0-3 | bits | MODEL_PART2 | second half of HX, FX, LX, PX (flags 720-723) | both |
| 0x02104627.0-3 | bits | MODEL_POSSESSION | first half of HX, FX, LX, PX (flags 728-731) | both |
| 0x02104627.4-7, 28, 29.0 | 13 bits | TRANSERVER_UNLOCK_BITS | Transport destinations (1.5) | client |
| 0x0210462B | u8 | MISSION_ACTIVE_BYTE | .1 mission accepted, .2 story mission; the Report clears it | client |
| 0x0210462C.0-1 | bits | EVENT_GATES | N-1 Zero 3 / Zero 4 doors, recomputed from the GBA slot | none |
| 0x0210462D.0 | bit | GAME_CLEARED | game completed, set just before the credits | client |
| 0x02104630 | u8 | OFF_DIFFICULTY | difficulty: 0 Easy, 1 Normal, 2 Hard (block +0x70) | golden |
| 0x02104631 | u8 | OFF_CHARACTER_BLOCK | character copy read by menus: 0 Vent, 1 Aile (+0x71) | golden |
| 0x02104634..3B | 8 | BOSS_LEVELS | boss victory levels 1-4 (1.9) | both |
| 0x021046A8 | u32 | TRANSPORT_SEL | Target Area list selection 0..12, -1 none (+0xDC) | client |
| 0x021046AC | u32 | MISSION_STATE_ADDR | active mission state value (+0xE0; 1.3) | client |

### 1.1 Models and biometals

| model | active value | owned bit | check "Obtain Biometal" (either bit) | second half |
|---|---|---|---|---|
| Hu | 0 | 0x021045DD.0 with the Hu gate; always owned in vanilla | | |
| X | 1 | 0x021045CF.7 | | |
| ZX | 2 | 0x021045D0.0 | | |
| HX | 3 | 0x02104627.0 | 0x021045D0.1 Hivolt, 0x021045D1.1 Hurricaune | 0x02104626.0 |
| FX | 4 | 0x02104627.1 | D0.5 Fistleo, D1.5 Flammole | 0x02104626.1 |
| LX | 5 | 0x02104627.2 | D0.3 Lurerre, D1.3 Leganchor | 0x02104626.2 |
| PX | 6 | 0x02104627.3 | D0.7 Purprill, D1.7 Protectos | 0x02104626.3 |
| OX | 7 | 0x021045D2.1 | | |

The game resolves ownership through category tables (section 3): a model is
owned when at least one flag of its list is set, and the list's set count is
what the model overlays read. The patch replaces the HX/FX/LX/PX lists with
[first half, second half] and keeps the vanilla count of 2. One half makes
the model usable; two halves unlock the level 2 charged attack (charge cap
0x78 instead of 0x28) and a WE cap of 32. The boss bits D0/D1 still fire the
location but grant nothing.

### 1.2 Card Keys

| key | bit | flag | door key type |
|---|---|---|---|
| Red | 0x021045FC.5 | 389 | 1 |
| Blue | 0x021045FC.6 | 390 | 2 |
| Purple | 0x021045FC.7 | 391 | 3 |
| Green | 0x021045FD.0 | 392 | 5 |
| Yellow | 0x021045FD.1 | 393 | 4 |
| White | 0x021045FD.2 | 394 | 7 |

The game hands out Green, Blue, Red and Purple as mission rewards and Yellow
through the Operator's console, so the client writes exactly the received
set into these six bits and leaves the other bits of both bytes alone. A
door's key type is bits 0x70 of its role; the type indexes the flag table at
0x020E9E98. The White key has no source in vanilla and is not in the pool.

### 1.3 Missions

Exx.y below means 0x021045xx bit y. The state value lives at 0x021046AC.
"Completed" is the detection of the mission's location. "Auto-accept" lists
the subareas that trigger the client's force-accept, plus the hub floor y
whose left door leads to the boss room (accepted when the player is at
x <= 368).

| id | mission | start | state | completed | auto-accept |
|---|---|---|---|---|---|
| 1 | Catch The Maverick | DE.2 | 0x92 | | |
| 2 | Locate Giro | DE.5 | 0x95 | DE.7 | 5, 6 |
| 3 | Pass The Test | DF.1 | 0x99 | E0.3 | 9, 10 |
| 4 | Troop Reinforcement | E0.2 | 0xA2 | E1.1 E1.2 E1.5 E2.0 E4.0 | 15, 16, 17 |
| 5 | Search The Plant | E1.3 | 0xAB | E1.4 | 20-27; floor 1888 |
| 6 | Find The Survivors | E1.6 | 0xAE | E1.7 E5.0 | 28-32; floor 2272 |
| 7 | Fight The Mavericks | E2.1 | 0xB1 | E3.7 E5.3 | 33-37; floor 2656 |
| 8 | Secure The Biometal | E4.1 | 0xC1 | E4.3 | 38-41 |
| 9 | Save The People | E4.5 | 0xC5 | E4.7 | 42-46; floor 3424 |
| 10 | Recover The Disk | E5.1 | 0xC9 | E5.2 | 47-51 |
| 11 | Attack The Excavators | E5.4 | 0xCC | E5.6 | 52-56; floor 4192 |
| 12 | Protect The Lab | E6.0 | 0xD0 | E6.1 | 57-60; floor 4576 |
| 13 | Protect HQ | E6.3 | 0xD3 | E7.0 | started by the game on the Report that brings the count of reported area missions to 4 |
| 14 | Stop The Dig | E7.2 | 0xDA | E7.3 E7.4 | 61-63; floor 4960 |
| 15 | Repel The Army | E7.5 | 0xDD | E7.7 E8.0 | 65, 66; floor 5344 |
| 16 | Destroy Model W | E8.1 | 0xE1 | never reported | 18, 19 |

Troop Reinforcement needs four extra bits when forced, E0.5, E0.6, E0.7 and
E1.0: the room scripts of the Guardian base test them before they consider
the auto-report, and its story handler must start in state 6. E0.7 marks
the mission as already launched, so the X-2 command room does not start it
again through the story. Its start flag E0.2 must stay set until the Report,
and 0x02104602.1 must be clear for the Giro scene at the end of D-2 to arm.

Accepting a mission means: start flag in live and canonical, state value at
0x021046AC, 0x02160FA8 = 1, 0x0210462B |= 2, the story handler installed
(below), and a checkpoint commit. The state machine of the active mission:

| address | size | name in code | meaning |
|---|---|---|---|
| 0x02160FA8 | u8 | MISSION_ACTIVE_FLAG | 1 = a mission is active |
| 0x0214F6BC | 0x11C | STORY_BLOCK | story block; +4 mission id, +8 handler object |
| 0x0214F6C0 | u32 | STORY_HANDLER_ID | mission id whose handler runs (0 none) |
| 0x0214F6C4 | 0x114 | STORY_HANDLER_OBJ | handler work area; +9 cutscene id (0xFF none), +0xB state |
| 0x02160554 | 0x11C | STORY_BLOCK_CANON | checkpoint copy, restored on death |
| 0x02160670 | 0x11C | STORY_BLOCK_MIRROR | mission-start snapshot, restored by Abort Mission |
| 0x020CF0F4 | u32[17] | | handler table indexed by mission id (Thumb entries) |

### 1.4 Event gates

Doors whose role has bit 1 set test an event flag instead of a key. The
flag table is at 0x020E9EB8: [395, 395, 381, 382, 191, 225, 768, 769],
indexed by role bits 0x70.

| flag | bit | gate | client |
|---|---|---|---|
| 191 | E3.7 | G-2 inner door (Fight The Mavericks completed) | logic only |
| 205 | E5.5 | K-1 sand cascade over the pit to K-2 | always set |
| 225 | E8.1 | D-2 to D-4 Slither gate (Destroy Model W started) | with all six models |
| 378 | FB.2 | spawn condition of the D-2 to D-4 gate entity | with all six models |
| 379 | FB.3 | D-1 bridge lowered | always set |
| 381 | FB.5 | F-3 to F-4 | always set |
| 382 | FB.6 | G-2 to G-4 | always set |
| 395 | FD.3 | M-1 seal | always set |
| 768, 769 | 0x0210462C.0, .1 | N-1 Zero 3 / Zero 4 doors | never (GBA cart check) |

### 1.5 Transerver destinations

Thirteen bits, one per Transport destination, read through the index table
at 0x020DB0A4. The hub script sets the bit of the floor the player stands
on; the client ORs in the bits of the received access items. Transport is
only offered when more than one bit is set. 0x02104629.1-4 mark the DATA
floors (C-2, C-3, H-4, J-1) and are not part of the list.

| index | destination | bit | index | destination | bit |
|---|---|---|---|---|---|
| 0 | A-2 | 0x02104627.4 | 7 | I-3 | 0x02104628.3 |
| 1 | B-2 | 0x02104627.5 | 8 | K-4 | 0x02104628.4 |
| 2 | C-2 | 0x02104627.6 | 9 | L-4 | 0x02104628.5 |
| 3 | D-2 | 0x02104627.7 | 10 | M-3 | 0x02104628.6 |
| 4 | E-7 | 0x02104628.0 | 11 | O-2 | 0x02104628.7 |
| 5 | F-5 | 0x02104628.1 | 12 | X-1 | 0x02104629.0 |
| 6 | G-5 | 0x02104628.2 | | | |

### 1.6 ITEM B chips

Ownership is a flag; the player activates a chip in the pause menu, which
sets bit i of 0x0214FCAC. The menu list is the flag array at 0x020DEF44.

| chip | flag | bit | i | chip | flag | bit | i |
|---|---|---|---|---|---|---|---|
| Absorber | 653 | 0x0210461D.5 | 0 | Ice Boots | 658 | 0x0210461E.2 | 4 |
| Featherweight | 655 | 0x0210461D.7 | 1 | Wind Boots | 659 | 0x0210461E.3 | 5 |
| Extender | 656 | 0x0210461E.0 | 2 | Frog | 660 | 0x0210461E.4 | 6 |
| Quick Charger | 657 | 0x0210461E.1 | 3 | Eraser | 654 | 0x0210461D.6 | 7 |

### 1.7 Secret Disks

flag = base[series] + number - 1, with bases B 446, M 463, E 473, O 524
(u32 table at 0x020C9A60, limits at 0x020C9A40). The bits run from
0x02104603.6 (Disk B-1) to 0x0210460F. Disk E-31 is flag 503, that is
0x0210460A.7. The setter at 0x02009370 takes (series, number - 1).

### 1.8 Boss rush (D-4, subarea 18)

A pair counts as beaten when both of its bits are set. The elevator is one
entity placed by the stage byte; setting a pair before the elevator has
stopped at the pair's stop makes it jump and drops the player.

| pair | Pseudoroids | left bit | right bit | stop y | handler state | stage |
|---|---|---|---|---|---|---|
| 0 | Hivolt, Hurricaune | 0x021045FF.4 | 0x02104600.0 | 2440 (shaft 1) | 2 | 2 |
| 1 | Lurerre, Leganchor | 0x021045FF.5 | 0x02104600.1 | 520 (shaft 1) | 4 | 4 |
| 2 | Fistleo, Flammole | 0x021045FF.6 | 0x02104600.2 | 2824 (shaft 2) | 5 | 7 |
| 3 | Purprill, Protectos | 0x021045FF.7 | 0x02104600.3 | 904 (shaft 2) | 7 | 9 |

| address | size | name in code | meaning |
|---|---|---|---|
| 0x0212FBA1 | u8 | STAGE | elevator stage 0..9 (struct 0x0212FB94 + 0xD) |
| 0x02112B78 | u16[] | TILEMAP | metatile map of the loaded room; stride 192 in D-4 |
| 0x0212DB54 + 0x28 | u16 | TILEMAP_DIRTY | 1 = re-upload the visible map |
| 0x021959D8..0x02195C38 | 8 x 64 | PATCHES | "used capsule" 5x6 metatile patches in overlay 61 |
| 0x0210462A.7 | bit | | teleporter room lockdown, rewritten every frame from the pair bits |

The fixed stages place the elevator directly at their position when the
room loads; the ascent stages animate the climb and end at the stop. The
story handler of mission 16 picks the stage from its state, the pair bits
and the player's rectangle. A player standing on the elevator at a stop is
at y = stop + 23. With its bit set a teleporter is inert (UP does nothing)
and its capsule is drawn as used only when the room loads.

| stage | elevator |
|---|---|
| 0 | bottom of shaft 1 |
| 1 | stop 1 of shaft 1, y 2440 |
| 2 | ascent to 2440 |
| 3 | top of shaft 1, y 520 |
| 4 | ascent to 520 |
| 5 | bottom of shaft 2, at (2688, 4360) |
| 6 | stop 1 of shaft 2, y 2824 |
| 7 | ascent to 2824 |
| 8 | top of shaft 2, y 904 |
| 9 | ascent to 904 |

### 1.9 Boss victory levels

0x02104634 + i holds the level (1-4) of the victory over Pseudoroid i:
0 Hivolt, 1 Lurerre, 2 Fistleo, 3 Purprill, 4 Hurricaune, 5 Leganchor,
6 Flammole, 7 Protectos. A model's WE cap is 4 x (level of its first boss +
level of its second): HX (0, 4), LX (1, 5), FX (2, 6), PX (3, 7). With the
biometal granted by flag the levels stay 0, so the client sets level0 =
4 - level1 and fills the bar to 16 for one half, and 4 + 4 with a bar of 32
for both halves.

## 2. Player, scene and menus

### 2.1 Player object 0x0214FB08

| address | offset | size | name in code | meaning |
|---|---|---|---|---|
| 0x0214FB12 | +0x0A | u8 | | bit 4 = facing |
| 0x0214FB19 | +0x11 | u8 | DEATH_STATE | state: 0 control, 0x0A hurt or dying, 0x0B interaction, 0x0D cutscene |
| 0x0214FB1A | +0x12 | u8 | | sub-state; 2 together with 0x0A = death in progress |
| 0x0214FB1B | +0x13 | u8 | | animation phase, 0 at the start of a death |
| 0x0214FB64 | +0x5C | u32 | PLAYER_POS | x << 8 |
| 0x0214FB68 | +0x60 | u32 | | y << 8 |
| 0x0214FBB2 | +0xAA | u8 | HP | current HP, 0x10 at the start |
| 0x0214FC5C | +0x154 | 0x6C | PLAYER_PERSIST | persistent block, saved as descriptor 1 (below) |
| 0x0214FC64 | +0x15C | u32 | | scene word: subarea of the current room |

Writing HP = 0 alone does not kill: the death is decided by the player tick
from a lethal hit. The client kills like the game does, HP = 0 plus
+0x11..+0x13 = 0A 02 00, only while the player has control (+0x11 = 0).

Persistent block 0x0214FC5C (0x6C bytes; the same layout appears in the
scene descriptor and in the save image):

| address | offset | size | name in code | meaning |
|---|---|---|---|---|
| 0x0214FC5C | +0x00 | u32 | | spawn x << 8 |
| 0x0214FC60 | +0x04 | u32 | | spawn y << 8 |
| 0x0214FC6C | +0x10 | u8 | LIVES | lives; 4 on Easy, 2 on Normal and Hard |
| 0x0214FC6D | +0x11 | u8 | | bit 0 = spawn facing |
| 0x0214FC70 | +0x14 | u24 | ECRYSTALS | E-Crystals, max 99999; the high byte of the u32 is preserved |
| 0x0214FC74 | +0x18 | u8 | MODEL, ACTIVE_MODEL_ADDR | active model 0..7 (1.1) |
| 0x0214FC75 | +0x19 | u8 | OFF_CHARACTER | character 0 Vent, 1 Aile (the authoritative copy) |
| 0x0214FC76 | +0x1A | u8 | HPMAX | max HP: 0x10 + 4 per Life Up, cap 0x20 |
| 0x0214FC77 | +0x1B | u8 | LIFEUP_BYTE | low nibble capacity (AP count), high nibble slot collected |
| 0x0214FC78 | +0x1C | u8 | SUBTANK_BYTE | same for Sub Tanks; bit 7 = Energy Packs quest tank |
| 0x0214FC79 | +0x1D | 4 u8 | | Sub Tank contents |
| 0x0214FC95 | +0x39 | 4 u8 | WE_BASE + model | current WE of HX, FX, LX, PX |
| 0x0214FCAC | +0x50 | u8 | | chips activated, bit i of the menu order (1.6) |

Life Up slots are 0 D-1, 1 F-2, 2 J-1, 3 I-5; Sub Tank slots 0 A-2, 1 E-4,
2 K-1, 3 quest. In vanilla the low nibble is both capacity and "collected".
The patch moves "collected" to bit 4 + slot, which gates the pickup's spawn
and is the location's detection; the pickup no longer raises max HP.

### 2.2 Scene, game state and menus

| address | size | name in code | meaning | used by |
|---|---|---|---|---|
| 0x0215E6D8 | u32 | GAME_STATE | main state (values below); +4 and +8 are zeroed on a request | both |
| 0x02108228 | u8 | SUBAREA_STABLE | subarea of the loaded room | both |
| 0x0216047C | 0x6C | SCENE_DESC | descriptor 1: +0 spawn x << 8, +4 y << 8, +8 subarea (0x02160484), +0x10 lives, +0x11.0 facing, +0x18 model on entry | client |
| 0x021604E8 | 0x6C | SCENE_DESC_MIRROR | descriptor 2, mission-start snapshot | client |
| 0x021602A8 | u32 | PLAYTIME, GOLDEN_IMAGE_ADDR | play time in frames; start of the save image (section 5) | client |
| 0x0214CD70 | u8 | TITLE_CAROUSEL_STEP | title carousel step (values below); byte +4 of the title object at 0x0214CD6C | both |
| 0x02104588 | u32 | MSG_BANK | last text bank loaded; 0xFFFFFFFF during the first frames after boot | client |
| 0x0214F502 | u8 | CUTSCENE_FLAG | .0 cutscene or dialog running, .4 skippable; 0x0214F503 = event of the open block | both |
| 0x0214F506 | u8 | | .1 console or NPC interaction in progress | rom |
| 0x0214F3EC | obj | TROOP_ROOM_OBJ | room script object of any room; +0xB state (D-2: 7 = megamerge, D-5: 21 = terminal) | client |
| 0x020F2768 | u16 | | buttons held this frame; 0x020F276A previous frame, 0x020F276C pressed | rom |
| 0x0215D7F8 | struct | | pause menu; page u8 at +0x1825 (0x0215F01D): 0 STATUS, 1 ITEM, 2 OPTIONS, 3 MISSION | rom |
| 0x0215D808 | 0x4F4 per slot | | DATA SELECT slot buffers, one save image per slot | rom |
| 0x027E02C4 | struct | | message system (DTCM): +0xC duration, +0x10 type (2 popup), +0x11 phase (6 closing), +0x1C text pointer, +0x24 next page | rom |
| 0x021510AA | u16 | | boss HP | none |

Game state values:

| value | meaning |
|---|---|
| 0x500 | gameplay; also the title screen and its menus |
| 0x400 | scene load (the client's teleport request) |
| 0x600 | door or Transport transition |
| 0x300 | return from Abort Mission |
| 0x101 | pause menu |
| 0x50700 | request to open the Target Area list |
| 0x10000 | New Game request; low 16 bits are 0, the upper bytes encode difficulty and character (Easy/Vent = 0x10000) |
| 0x3, 0x100 | Continue |
| 0x900, then 0x..07 | death and the Game Over screens |
| 0xB00, 0xC00 | attract mode |

Title carousel steps: 0-2 logos and boot, 3 "Press START", 4 attract,
5 menus (New Game, Continue, difficulty, character, and the Game Over "Exit
Game" menu), 6 game launched. The client treats the game as playable when
the step is 6, the subarea is not 0, HP > 0 and the state is 0x500. It seeds
the golden image while the step is 3 or 5 and the state is 0x500 or ends in
0x07.

The step becomes 6 on the frame New Game or Continue is requested and does
not drop below 6 until the next Game Over or return to the title. While the
step is 3 or 5 nothing writes the load buffer at 0x021602A8, which makes
those steps the seeding window; the state test additionally excludes the
title load at step 3, when the game initialises the buffer by DMA, and the
0x..03 states of the data select, where Continue restores the save into it.
The sequences the client sees:

| moment | state word | step |
|---|---|---|
| boot logos | 0 | 0-2 |
| title load | 0xB00 for one frame, 0x200, 0x400; the buffer is initialised by DMA | 3 |
| "Press START" | 0x500 | 3 |
| title menus | 0x500 | 5 |
| attract demo | 0x090700 | 4 |
| New Game | 0x10000 for one frame (0 with Aile), 0x200, 0x400 while LOAD reads the buffer, 0x500 | 6 from the first frame |
| Continue | 0x3, 0x103, 0x0203xx during the data select; SRAM copied into the buffer at 0x140203 and 0x150203; 0x820203, 0x840203, 0x840303, 0x100, 0x200, 0x400, 0x500 | 6 from 0x3 |
| pause | 0x1000700, 0x1, 0x10001, 0x1010001, 0x101; resume 0x800, 0x1000800, 0x500 | 6 |
| death | 0x900, 0x7, 0x107, 0x10107; the Game Over menus keep the low byte 0x07 | 6, then 1, then 5 |
| Game Over, Exit Game | 0x10000, then as New Game | 6 |
| Game Over, Continue | 0x10003, then the data select sequence of Continue | 6 |

Teleport: write descriptor +0 = x << 8, +4 = y << 8, +8 = subarea,
+0x11 = 1, then state 0x400 with +4 and +8 zeroed, all guarded on the state
still being 0x500. Button masks: A 1, B 2, SELECT 4, START 8, RIGHT 0x10,
LEFT 0x20, UP 0x40, DOWN 0x80, R 0x100, L 0x200, X 0x400, Y 0x800.

### 2.3 Hub floors and tracker

The Guardian hub is subarea 70 (room z01), a stack of floors; each floor's
console pad is at (384, y - 17), the boss-room door is reached at x <= 368.
The pad is a raised platform 17 px above the floor surface y. A spawn at
(384, y - 1) lands inside the geometry and drops the player to the floor
below; (288, y - 1) stands on the floor but outside the console's hitbox, so
UP does nothing. Teleports therefore target (384, y - 17).

| area | floor y | area | floor y | area | floor y | area | floor y |
|---|---|---|---|---|---|---|---|
| A | 352 | E | 1888 | I | 3424 | M, N | 4960 |
| B | 736 | F | 2272 | J | 3808 | O | 5344 |
| C | 1120 | G | 2656 | K | 4192 | X | 5728 |
| D | 1504 | H | 3040 | L | 4576 | | |

The client publishes [subarea, x, y] in pixels under the data storage key
mmzx_pos_<slot>, at most once per second or after 48 px of movement, and
immediately on a room change. The tracker maps the subarea to a room map
and the hub y to an area badge.

### 2.4 Subarea ids

Subarea = overlay - 43 up to 64; 65 and above skip two overlays (z01 = 70 is
overlay 115; table at 0x020C7D54). Ids 12-14 do not exist.

| area | rooms | area | rooms |
|---|---|---|---|
| A | a01 1, a02 2, a03 3, a04 4 | I | i01 42, i02 43, i03 44, i04 45, i05 46 |
| B | b01 5, b02 6, b03 7, b04 8 | J | j01 47, j02 48, j03 49, j04 50, j05 51 |
| C | c01 9, c02 10, c03 11 | K | k01 52, k03 54, k04 55, k05 56 |
| D | d01 15, d02 16, d03 17, d04 18, d05 19 | L | l01 57, l02 58, l03 59, l04 60 |
| E | e01 20 .. e08 27 | M | m01 61, m02 62, m03 63 |
| F | f01 28 .. f05 32 | N | n01 64 |
| G | g01 33 .. g05 37 | O | o01 65, o02 66 |
| H | h01 38 .. h04 41 | X, hub | x01 67, x02 68, x03 69, z01 70, z02 71 |

## 3. Game code the apworld hooks or replicates

Addresses are Thumb code in the ARM9 unless an overlay is named.

| address | what the game does there | why the apworld cares |
|---|---|---|
| 0x02022544 | New Game state handler, slot 0 of the handler table at 0x020D8E28; shared with the attract demo | entry rewritten to jump to the skip cave |
| 0x0202252C | LOAD state handler: enters the scene from the save image at 0x021602A8 | the skip cave jumps here for a real New Game |
| 0x020D8E28 | state handler table, index = (state >> 8) & 0xFF | context for the skip |
| 0x02021070 | sets the game state (three stores at 0x0215E6D8) | the client replicates it for teleports and the Target Area list |
| 0x0203E414 | model_owned_count(category): counts set flags of the category's list; counts at 0x020DE9AC, lists at 0x020DEB78 | ownership by AP item (1.1) |
| 0x020DE9CC, BC, E4, F4 | flag lists of categories H, F, L, P; counts at 0x020DE9AF..B2 | patched to [half 1, half 2] |
| 0x020DEB78 | list pointer of category 0 (Hu), NULL in vanilla | Hu gate points it at a one-flag array |
| 0x02045064, 0x020377A8 | owned category count; can_transform requires at least 2 (the compare at 0x020377C8) and otherwise shows "Cannot transform now" | with the Hu gate the client never leaves the player in an unowned form |
| 0x02045084 | weapon level shop; re-derives the category flags from non-zero victory levels | why the client clears an unowned second half every tick |
| 0x0218A3F8, 0x02187854, 0x02187D60, 0x02188E48 | charge cap in the HX, FX, LX, PX overlays: 0x78 with two flags, else 0x28 | why the biometal is progressive |
| 0x02045008, 0x02044CA4 | grant Life Up / grant Sub Tank | patched at 0x02045014, 0x0204501E, 0x02044CAA, 0x02044CD4 to set bit 4 + slot and grant nothing |
| 0x020A3DD4 | Life Up / Sub Tank init, despawns when the slot bit is set | patched at 0x020A3E30, 0x020A3E86 to test bit 4 + slot |
| 0x020A309C | refill think (health, WE, E-Crystals, 1-Up) | 0x020A30A2 calls the mailbox cave; 0x020A30F4 calls the AP gate |
| 0x0200CA8C, 0x02107FB4, 0x021081F4 | room spawner, its record pool (48 records of 12 B: +0 next, +4 entity, +8 u16 coords index, +0xA attributes) and active list head | the caves identify a pickup by its coords index |
| 0x020A37D8 | enemy drop spawner: creates a refill with no spawn record | why drops never reach the mailbox |
| 0x020A3A6C, 0x020A3A38 | Secret Disk pickup and its "X-nn" label (also the disk's state 2 handler) | 0x020A3ADE calls the AP gate instead of the label |
| 0x02009370 | grant_secret_disk(series, index) | detection of disk locations (1.7) |
| 0x020A3B6C | Secret Disk init | 0x020A3BC4 and 0x020A3BCC redirected to the icon attach and anim caves; 0x020A3A7E to the retry cave |
| 0x020A3C98 | Life Up / Sub Tank pickup | 0x020A3CD4, 0x020A3CEE call the AP gate; 0x020A3CAA the retry cave; attach 0x020A3EEE, anim 0x020A3EF6 |
| 0x020A36F4, 0x020A3706 | refill init: attach set, set animation | icon attach and anim hooks |
| 0x02010624, 0x0200FE64 | attach a graphics set to an entity (stored at entity +0x22), set its animation | called by the icon caves |
| 0x0200FC0C | per-frame animation advance of an entity | the retry cave wraps it |
| 0x020EB8B0 | handler tables per pickup kind (0 refill, 1 disk, 2 Life Up / Sub Tank) | the disk stub sets state 4 (release) |
| 0x02021BB0, 0x02021DD4 | gameplay handler; its call to msg_tick (0x0201242C) | rewritten to call the notify cave |
| 0x020122D4, 0x020121DC, 0x02012050, 0x02010F50 | show_pickup_msg, popup prepare and open, popup handler (chains pages at 0xFD) | the notify cave replicates them with a direct text pointer |
| 0x0201BFD0, 0x0201C00C | script VM opcode 0x23 sub 0, "open skippable block" | beq at 0x0201C00C becomes mov r8,r8: always skippable |
| 0x0201B1C8, 0x0201B1E4 | START reader during cutscenes | 0x0201B1E4 calls the cutscene skip cave |
| 0x02008624 | mark a unique event as seen and back it up | called by the skip cave so the state matches watching the scene |
| 0x02009B74, 0x02009C5C | OAM sprite builders with an unguarded count loop | beq at 0x02009C30 and 0x02009D7C become bls |
| 0x02006B1C | graphics set registrar; rejects a set when the 15 OBJ palettes are used up (tests at 0x02006B86 for screen 0 and 0x02006B92 for screen 1) or the tile cursor does not fit (0x02006B66), leaving 0x02105C94[set] = 0xFF | why the AP set shares a palette |
| 0x0200F0D4 .. 0x02010756 | ten sprite drawers that read the slot record without a NULL check | each `ldrh r0,[r0,#2]; movs r3,#1` becomes a call to the sprite guard cave |
| 0x0200BD04 | global set loader; resident list u16[3] [0, 1, 58] at 0x020C9C30 | 0x020C9C36 = 261, counts at 0x0200BD16 and 0x0200BDB6 become 4, 0x0200BDA8 calls the icon boot cave |
| 0x02006A88, 0x02006164 | register a static set (VRAM slot, palette slot), upload its tiles | replicated by the icon boot cave for set 261 |
| 0x02105C94, 0x02105EE4, 0x02105740 | set to VRAM slot table, set to palette slot table, graphics manager | the palette share cave copies slot 58 to slot 261 |
| 0x02036104 | DATA SELECT slot icon drawer; slot buffers at 0x0215D808 + 0x4F4 x slot | patched at 0x020361FC, 218, 234, 250 (H, F, L, P read 0x02104627.0-3) and 0x020361E2 (X hidden without 0x021045CF.7) |
| 0x0202323C, 0x02023240 | pause menu tick; its call to the close routine 0x02022B0C | rewritten to call menu warp cave B |
| 0x020272AC, 0x020272B6 | MISSION tab map scroll; reads the held buttons | rewritten to call menu warp cave A (Y = Go to Transerver) |
| 0x02093B4C, 0x02093BE4 | Operator console dispatcher; beq that skips the Yellow Card Key script (0x02094288) | beq becomes b: the key dialogue never runs |
| 0x02031F10 | accept mission by id: start flag, state, clears the previous mission | replicated by the client's force-accept |
| 0x02009184 | is_mission_active(id): true only with bit 1 or bit 2 of 0x0210462B set | why force-accept writes that byte; without it the boss arena does not arm |
| 0x02032458 | counts the reported area missions (ids 5 to 12); Protect HQ launches on the Report that brings the count to 4 | mission 13 in 1.3 and the MISSIONS atom of the logic |
| 0x02031028 | mission complete on Report: sets the completed bits and rewards | source of the completed bits in 1.3 |
| 0x02022744 | mission start snapshot: live to canonical, then canonical, descriptor and story block to their mirrors | replicated before a force-accept |
| 0x02022630 | Abort Mission restore from the mirrors, then state 0x300; called by the console's Abort handler 0x020946F0 | why the mirrors matter |
| 0x0201B384 | checkpoint commit: position to persistent block and descriptor, live to canonical, story block to its copy | replicated after force-accept and boss rush skips |
| 0x02044878 | copy the player's position into the persistent block and descriptor | part of the commit |
| 0x0201B5EC | install a story handler: zero 0x0214F6C4, +9 = 0xFF, id at 0x0214F6C0 | replicated by force-accept and the ending watchdog |
| 0x0201FC90 | story handler of mission 16: D-4 elevator states 0-7, picking the elevator stage from its state, the pair bits and the player's rectangle; waits for Serpent 2 at state 0x0D, launches the ending script 0x020D30FC at 0x0E, sets game completed at 0x13 | boss rush skip and ending watchdog |
| 0x02020110 | D-2 room script (object 0x0214F3EC): Giro scene; state 10 is the megamerge, which sets 0x02104602.1 and 0x021045D0.0; state 13 triggers the room's final cutscene | Troop unstick reads its state |
| 0x0203D680 | player tick death check | source of the death recipe (2.1) |
| 0x02013328 | copy a metatile patch into the room map and mark it dirty | replicated to repaint used capsules |
| overlay 61: 0x02194A84, 0x02194DEC, 0x02194C84 | D-4 capsule painter (room load only), elevator entity, lockdown from pair bits | boss rush skip |
| 0x020E9E98, 0x020E9EB8 | door flag tables: key type (1.2) and event (1.4) | logic source |

## 4. Structures installed in free ARM9 RAM

The patch uses zero-filled stretches of the ARM9 data section that the game
never reads or writes. The icon table is not part of the patch: the client
writes it into a gap between overlay slots.

| address | size | name in code | purpose |
|---|---|---|---|
| 0x020C8150 | 116 | ICON_BOOT_CAVE | registers set 261 at boot like set 58 |
| 0x020C81C4 | 184 | ICON_CAVES | lookup (+0), attach (0x020C8212), anim (0x020C823C) |
| 0x020C827C | 10 | SPRITEGUARD_CAVE | skips the read when the slot record is NULL |
| 0x020C8288 | 24 | PALSHARE_CAVE | palette slot of set 261 = slot of set 58 |
| 0x020C82A0 | 72 | ICON_RETRY_CAVE | re-attaches the icon every frame until it sticks |
| 0x020CB434 | 4 | HUGATE_ARRAY_RAM | u32 [136], the Hu category list |
| 0x020CB438 | 28 | MENU_WARP_CAVE_B | closes the menu when the request flag is set |
| 0x020CB460 | 48 | SKIP_CAVE | New Game to LOAD when the carousel step is 6 |
| 0x020CB4A0 | 88 | PICKUP_MAILBOX_CAVE | records collected refills |
| 0x020CB500 | 36 | PICKUP_MAILBOX_RAM, PICKUP_MAILBOX_ADDR | pickup mailbox (layout below) |
| 0x020CB540 | 24 | CUTSCENE_SKIP_CAVE | marks the event seen when START skips |
| 0x020CB600 | 152 | NOTIFY_CAVE | opens the popup with the client's text |
| 0x020CB700 | 0x100 | NOTIFY_RAM, NOTIFY_ADDR | notice mailbox (layout below) |
| 0x020CB800 | 236 | PICKUP_AP_CAVE | AP gate (+0) and stubs refill +88, disk +124, Life Up +172, Sub Tank +204 |
| 0x020CB980 | 26 | DATASELECT_CAVE | hides the X icon of a slot without Model X |
| 0x020CB99C | 32 | MENU_WARP_CAVE_A | returns the held pad, sets the flags on Y |
| 0x020CB9D0 | 2 | MENU_WARP_FLAGS_RAM, WARP_REQ | +0 request (client clears), +1 close (cave B clears) |
| 0x02191460 | 0xC4 | ICON_TABLE_RAM, ICON_TABLE_ADDR | per-room pickup table written by the client |

Pickup mailbox (0x020CB500):

| offset | type | field | meaning |
|---|---|---|---|
| 0x00 | u32 | counter | +1 per layout refill collected; entry k is written at 4 + (k & 7) * 4 |
| 0x04 | u32[8] | ring | byte 0 subarea, byte 1 coords index, byte 2 role, byte 3 zero |

Enemy drops have no spawn record and never write. The client maps
(subarea, index) to a location, ignores repeats, and resyncs from the last
eight entries when the counter goes backwards.

Notice mailbox (0x020CB700):

| offset | type | field | meaning |
|---|---|---|---|
| 0x00 | u8 | REQ | 0 free, 1 text in BUF, 2 vanilla message id; the cave clears it when the popup closes |
| 0x01 | u8 | STATE | the cave's own state |
| 0x02 | u16 | DUR | frames the whole text stays (the client uses 90) |
| 0x04 | u8[0xFC] | BUF | text in the game font: ASCII - 0x20, color F1 00 white / F1 03 green, 0xFD next page, 0xFE end |

One popup line holds 30 glyphs; color controls do not count. The client
writes BUF and DUR first and REQ last, and only while REQ is 0.

Icon table (0x02191460), consulted by the caves only when byte 0 equals the
loaded subarea and bit 0 of byte 1 is set:

| offset | type | field | meaning |
|---|---|---|---|
| 0x00 | u8 | sub | subarea the table describes |
| 0x01 | u8 | flags | bit 0 = valid |
| 0x02 | u16 | pad | |
| 0x04 | u8[128] | code | coords index to icon code (ICON_CODES, animation + 1); 0 = vanilla look |
| 0x84 | u8[32] | checked | bitmap by index: refill already sent, keep the vanilla look |
| 0xA4 | u8[32] | present | bitmap by index: multiworld location not sent yet, suppress the vanilla effect |

Menu warp flags (0x020CB9D0): byte 0 is set to 1 by cave A when Y is
pressed on the MISSION tab and cleared by the client, which then opens the
Target Area list; byte 1 is set at the same time and consumed by cave B to
close the menu.

ROM-side data written by the patch:

| ROM offset | size | name in code | content |
|---|---|---|---|
| 0x0C | 4 | ROM_GAME_CODE | "ARZE", checked by the client |
| 0x1000 | 0x80 | AP_MAGIC_OFFSET | +0 "MZXAP\0", +8 u32 world version, +0x10 slot name (63 B + NUL), +0x50 seed name (31 B) |
| 0x2C, 0x15E | u32, u16 | | ARM9 size and header CRC16, refreshed after recompression |
| 0x80 | u32 | | used ROM size, moved past the relocated graphics files |
| 0xDFB200 + 0xB14, 0xB4B, 0xB85 | 27 x 3 | MENU_WARP_TEXT_* | "Y Button:Go to Transerver" in m_sub_en.bin (three variants, same length) |
| obj_fnt.bin + 0x5620C | 128 | DISK_LOGO_* | Secret Disk body tile (set 58, unit 0x11) = Archipelago logo |

The patch file also carries mmzx_cfg.bin, 4 bytes read before the ARM9 is
patched: byte 0 bit 0 = hu_in_pool (CFG_HU_IN_POOL).

## 5. Golden image

The save image is 0x4F4 bytes at 0x021602A8. The LOAD handler enters the
scene from it, and the client seeds it while the title menus are open so
that New Game (redirected to LOAD) starts in the post-tutorial hub. It also
serves the game as DATA SELECT slot content.

| offset | size | field | RAM twin |
|---|---|---|---|
| 0x000 | u32 | play time in frames | 0x021602A8 |
| 0x008 | u32 | scene word, subarea in byte 0 | 0x021602B0 |
| 0x00C | 0xE4 | progress block A (canonical) | 0x021602B4, live 0x021045CC |
| 0x00C + 0x03 | bit 7 | Model X owned | 0x021045CF.7 |
| 0x070 | u8 | difficulty 0 Easy, 1 Normal, 2 Hard | 0x02104630 |
| 0x071 | u8 | character for the menus | 0x02104631 |
| 0x074 | 8 | boss victory levels | 0x02104634 |
| 0x0F0 | 0xE4 | progress block B (mirror) | 0x02160398 |
| 0x1D4 | 0x6C | descriptor 1 = the persistent player block of 2.1, each field at 0x1D4 + its block offset (lives 0x1E4, active model 0x1EC, character 0x1ED, WE 0x20D) | 0x0216047C, live 0x0214FC5C |
| 0x240 | 0x6C | descriptor 2 (mirror) | 0x021604E8 |
| 0x2AC | 0x11C | story queue 1: +4 mission id, +8 handler object; its state decides whether Fleuve's briefing plays on entry | 0x02160554 |
| 0x3C8 | 0x11C | story queue 2 (mirror) | 0x02160670 |

Every field has its mirror at +0xE4 (block) or +0x6C (descriptor); the
builder writes both. The baseline image is a clean post-briefing state:
play time 0, no mission in progress, spawn (384, 335) on floor A of the hub,
Normal difficulty with 2 lives, Model X owned, mirrors equal to the live
copies. On top of it the builder applies the slot options: Model X kept or
revoked, the starting model's ownership bit, the active model, the
character in both copies, and for HX/FX/LX/PX a level 4 for the first boss
of the pair plus a WE bar of 16.

## 6. Graphics sets and icons

Object graphics live in two NitroFS files: obj_fnt.bin (file id 235, tiles
and palettes of 511 sets, vanilla ROM offset 0x00F09000) and obj_dat.bin (file id 234,
frames and animations, 0x00EAEC00). Both start with u32 count and u32
offset[count + 1]; set i is the slice between offset[i] and offset[i + 1].
The set formats are described in icons.py.

| id | set | role for the apworld |
|---|---|---|
| 58 | item atlas: refills, 1-Up, Secret Disk, sparkles; resident from boot | its palette is shared by set 261 and used to render set 507; disk tile at unit 0x11 |
| 261 | empty in vanilla | the AP icon set, inserted at patch time, resident, VRAM slot 3 |
| 507 | Life Up (frame 0) and Sub Tank (frame 4) world sprites | icon sources |
| 178 | ITEM B chip icons, frames 0, 2, .. 14 in flag order | icon sources |
| 73, 74, 75 | STATUS screen model badges: 73 Hu 0, X 3, ZX 6; 74 HX 0, FX 3; 75 LX 0, PX 3, OX 6 | icon sources |
| 180 | ITEM C icons: Red 21, Purple 22, Yellow 23, Green 24, Blue 25, White 74 | icon sources |

Icon codes are the animation index of set 261 plus one, in this order:
1 logo useful, 2 logo progression, 3 logo filler, 4 Life Up, 5 Sub Tank,
6-13 chips (Absorber, Eraser, Featherweight, Extender, Quick Charger, Ice
Boots, Wind Boots, Frog), 14-21 models (Hu, X, ZX, HX, FX, LX, PX, OX),
22-27 Card Keys (Red, Blue, Purple, Green, Yellow, White). Code 0 leaves the
pickup's vanilla look.

| address | meaning |
|---|---|
| 0x020C9C30 | resident set list u16[3] = [0, 1, 58]; the padding word at 0x020C9C36 becomes 261 |
| 0x020C9C38 | second resident list of ten sets, door graphics among them |
| 0x02105740 | graphics manager; +4/+5 = OBJ palettes in use per screen, cap 15 |
| 0x02105C94[set] | VRAM slot of a set (0xFF = none); records at 0x02105754 + slot * 16 |
| 0x02105EE4[set] | palette slot of a set (0xFF = none); records at 0x02105A54 + slot * 12 |
| 0x020F3520[set], 0x020F3D20[set] | fnt and dat block of a set in RAM (0 = not loaded) |
| 0x0224C000 | object graphics heap; a boss sheet loaded here overwrites the room's tables |

Inserting set 261 shifts the offsets of every later set, so the patch
relocates both files to the free padding at the end of the ROM and rewrites
their FAT entries (FAT at the offset stored in the header at 0x48).
