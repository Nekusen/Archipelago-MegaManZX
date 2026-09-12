# ROM patches

Developer reference for every change the Mega Man ZX apworld makes to the
player's ROM. Addresses are ARM9 RAM addresses unless a ROM offset is
stated. The layouts of the blocks the patches install and of the tables the
client writes for them are in memory_map.md; this document explains what
each patch does and why it exists.

## Overview

`rom.py` builds the patched ROM from the player's own copy of Mega Man ZX
(USA), checked against its MD5 by the host settings and by the patch class.
The ARM9 is split into its autoload sections with apnds and decompressed;
every code patch goes through one helper that compares the bytes it is about
to overwrite with the expected vanilla bytes and aborts on a mismatch, so a
wrong or already modified ROM fails early, while bytes already in place are
a no-op. The sections are recompressed with the BLZ encoder described at the
end and put back into the original ARM9 slot, followed by the 12-byte
"nitrocode" footers that trail the ARM9 in the ROM, with the rest of the slot
zeroed; only the ARM9, its length in the header and the header CRC-16 change
and the rest of the 64 MiB image stays byte for byte identical. A compacted
image would shift the layout and melonDS fails with std::bad_alloc when
loading it. Three ROM-level edits follow: the AP icon set is
inserted into the object graphics files, which move to the free padding at
the end of the ROM; the pause menu help text and the Secret Disk tile are
replaced in place. The generic token step then writes the AP marker.

A cave is a small Thumb routine placed in a stretch of the ARM9 that is
zero-filled in the vanilla binary and never read or written by the game:
0x020CB434 to 0x020CB9D4 holds the gameplay caves and the two data blocks
the client talks to, the pickup mailbox and the notice buffer; 0x020C8150 to
0x020C8394 holds the graphics caves. A hook is one instruction, usually a
`bl`, redirected into a cave, which does its work and then re-executes the
displaced instruction or jumps back. The `bl` encodings are computed at
patch time from the addresses; the cave bodies are fixed byte strings.

Generation adds two small files to the .apmmzx: a 4-byte configuration blob
whose first bit enables the optional Hu gate, read by the ARM9 step, and the
token stream with the AP marker written at ROM offset 0x1000, zero padding
after the header. The patch places no items in the ROM, edits no room layout
and carries no other per-seed logic: item grants, location detection,
teleports, the starting state and every other dynamic effect are done by the
client through RAM. The table marks the patches the client drives.

## Summary

| Patch | Purpose | Hooks (address) | Installs (cave/data) | Client |
|---|---|---|---|---|
| Tutorial skip | New Game enters the game through the LOAD path | 0x02022544 | cave 0x020CB460 | yes |
| OAM drawer guards | Sprite loop with a zero count no longer sprays RAM | 0x02009C30, 0x02009D7C | none | no |
| Yellow Card Key dialogue | Operator stops re-granting the key on every visit | 0x02093BE4 | none | no |
| Biometal ownership | H/F/L/P owned through free flags, two progressive halves | tables at 0x020DE9AC and 0x020DEB78 | none | yes |
| Life Up / Sub Tank | Pickup marks "collected" without raising capacity | 0x02045014, 0x0204501E, 0x02044CAA, 0x02044CD4, 0x020A3E30, 0x020A3E86 | none | yes |
| Pickup mailbox | Reports which respawnable refill was collected | 0x020A30A2 | cave 0x020CB4A0, data 0x020CB500 | yes |
| DATA SELECT icons | Save slots show the randomizer's biometals | 0x020361E2, 0x020361FC, 0x02036218, 0x02036234, 0x02036250 | cave 0x020CB980 | no |
| Go to Transerver | Y on the MISSION tab requests a warp | 0x020272B6, 0x02023240; text at ROM 0xDFB200 | caves 0x020CB99C and 0x020CB438, flags 0x020CB9D0 | yes |
| NOTIFY | Client text in the game's small popup | 0x02021DD4 | cave 0x020CB600, data 0x020CB700 | yes |
| Cutscene skip | START skips every story cutscene | 0x0201C00C, 0x0201B1E4 | cave 0x020CB540 | no |
| AP icon set | Set 261 built from the player's ROM, kept resident | 0x020C9C36, 0x0200BD16, 0x0200BDB6, 0x0200BDA8 | cave 0x020C8150, set 261 in obj_fnt/obj_dat | no |
| Icon caves | Pickups drawn as the item they hold | 0x020A3BC4, 0x020A3EEE, 0x020A36F4, 0x020A3BCC, 0x020A3EF6, 0x020A3706 | cave 0x020C81C4 | yes |
| PALSHARE | AP set borrows the item palette instead of taking one | inside the boot cave | cave 0x020C8288 | no |
| RETRY | Late table writes still recolour a spawned pickup | 0x020A3A7E, 0x020A3CAA, 0x020CB4A2 | cave 0x020C82A0 | yes |
| Sprite guard | Drawers skip a set that has no VRAM slot | ten sites, 0x0200F0D4 to 0x02010756 | cave 0x020C827C | no |
| PICKUP_AP | AP pickups skip their vanilla effect | 0x020A30F4, 0x020A3ADE, 0x020A3CD4, 0x020A3CEE | cave 0x020CB800 | yes |
| Hu gate (optional) | Model Hu becomes an item | 0x020DEB78 | array 0x020CB434 | yes |
| Secret Disk logo | Disk tile shows the Archipelago logo | obj_fnt.bin + 0x5620C | none | no |
| AP marker | Identifies the seed and the slot | ROM 0x1000 | none | yes |

## Tutorial skip

- **Why.** A new game arms the opening script, Giro's cutscene and the A-1
  tutorial, whatever the progress block contains, so RAM seeding alone cannot
  start a slot in the hub. The LOAD path used by Continue enters a scene from
  a buffer without arming it.
- **What it changes.** The first eight bytes of the New Game state handler
  load the cave address and `bx` to it. The cave reads the game mode at
  0x0215E6D8 and the title carousel step at 0x0214CD70: when the low half of
  the mode is zero, which is how New Game encodes every character and
  difficulty, and the carousel says a game was launched (step 6), it jumps
  into the LOAD handler, which enters the scene from the 0x4F4-byte load
  buffer at 0x021602A8. Otherwise, including the attract demo that shares
  the handler, it re-executes the displaced prologue and resumes at
  0x0202254C. Continue uses another handler and is untouched.
- **Data.** Mode word, carousel step and the load buffer, whose layout is the
  golden image in memory_map.md.
- **Interaction with the client.** The ROM carries no starting state: while
  the title and its menus are shown the client keeps writing the golden image
  from golden.py, adjusted to the slot's starting model and character.
- **Limits.** New Game without the client loads whatever the title left in
  the buffer. The LOAD path forces Model X active on entry; the client
  re-asserts the chosen starting model until it sticks.

## OAM drawer guards

- **Why.** Two sprite drawers build a drawable's OAM entries with one bounds
  check ahead of the loop and leave it only through `subs r5,#1; beq`; with a
  sprite count of zero the counter wraps and the loop sprays sprite data
  across RAM. The count is zero when a live entity's frame table has been
  overwritten, as when a boss sprite sheet lands on the object graphics heap
  while level entities are still alive after a teleport into the boss area;
  the second drawer misfires in D-2 when the first mini-boss fires and
  corrupts the mission start flag and the Card Key byte.
- **What it changes.** One byte per loop: the closing `beq` becomes `bls`,
  so a count of zero exits after one bounded iteration; any other count
  behaves identically. `bls` branches when the carry is clear or Z is set,
  and `subs` clears the carry when it borrows, so a counter that was already
  zero leaves the loop after its first pass while a counter that reaches
  zero leaves as before.
- **Data.** The OAM write cursor is at 0x020F728C. Without the guard the D-2
  misfire corrupts 0x021045E0 (mission start flags), 0x021045FC (Card Keys)
  and 0x02104602.
- **Limits.** It prevents the crash, not the situation: a teleport into a
  boss area with the mission active can still leave the player outside a
  closed shutter, which the client's warp resolves.

## Yellow Card Key dialogue

- **Why.** When Troop Reinforcement has been reported and the Yellow Card
  Key is not owned, the Operator's console runs the script that announces and
  grants the key. The key is a pool item whose ownership the client enforces,
  so the bit never stays set and the dialogue replayed on every visit. The
  key is not a location, so nothing is lost.
- **What it changes.** The branch that skips the script when the key is
  already owned becomes unconditional.
- **Data.** The vanilla test reads 0x021045E1 bit 1 and 0x021045FD bit 1.
  The script is case 1 of the console dispatcher: a sound, message 1129 and
  the write that sets the key bit.
- **Limits.** The vanilla grant is gone: the key comes only from the pool.

## Biometal ownership through free flags

- **Why.** The game resolves "is model M owned" by counting the set flags of
  a per-category list; for HX, FX, LX and PX the list holds the two victory
  bits of the pair of Pseudoroids, so a boss victory grants the model. The
  victory must stay a location and the model must come from the pool in two
  halves: one flag makes the model usable, two raise the charge counter cap
  of its overlay and the Weapon Energy cap, which some locations require.
- **What it changes.** The lists of categories 3 to 6 point at two free
  flags of the progress block: the first half is flags 728 to 731
  (0x02104627 bits 0 to 3), the second flags 720 to 723 (0x02104626 bits 0
  to 3). The counts keep their vanilla value of two. A victory still sets its
  D0 or D1 bit, the "Obtain Biometal" detection, but grants nothing.
- **Data.** Counts at 0x020DE9AF to 0x020DE9B2; lists at 0x020DE9CC (H),
  0x020DE9BC (F), 0x020DE9E4 (L), 0x020DE9F4 (P), with vanilla values 33/41,
  37/45, 35/43 and 39/47.
- **Interaction with the client.** Copy k of a Progressive Model item sets
  half k in the live and canonical blocks. The Weapon Energy cap derives from
  victory levels a flag-granted model never earns, so the client also writes
  the levels and fills the bar, and clears any half without its item.
- **Limits.** The weapon-level shop re-derives category flags from non-zero
  victory levels, hence the client's per-tick check. DATA SELECT reads raw
  bits and has its own patch.

## Life Up and Sub Tank: collected versus capacity

- **Why.** In vanilla the capacity bytes double as the "slot collected"
  record: one bit raises the maximum, gates the pickup's spawn and is saved.
  With capacities granted as items the low bits would despawn pickups never
  collected, and a collected pickup would raise the capacity by itself.
- **What it changes.** Six instructions in the grant routines and spawn
  gates: the pickup sets bit 4 plus the slot index, the high nibble, instead
  of the low bit; both spawn gates test that high bit; the Life Up no longer
  adds four points of maximum HP and the Sub Tank no longer initialises the
  tank contents.
- **Data.** 0x0214FC77 (Life Ups) and 0x0214FC78 (Sub Tanks): low nibble =
  capacity from items, high nibble = pickups collected.
- **Interaction with the client.** The high nibble is the detection of the
  eight locations; the client owns the low nibble and preserves the high one.
- **Limits.** The Energy Packs quest reports through the Sub Tank grant with
  index 3, so it sets bit 7 of 0x0214FC78 and gives no tank.

## Pickup mailbox

- **Why.** Refills placed in the room layouts (health, weapon energy,
  E-Crystals, 1-Ups) are optional locations: the first pickup sends the
  check and the object keeps respawning. The game keeps no persistent record
  and a live entity does not know its layout index; only its spawn record
  holds the coords index, and enemy drops have no record.
- **What it changes.** The animation-advance call in the prologue of the
  refill think handler goes through the cave, which calls the original and,
  when the entity has just been collected (the same test the think uses:
  bit 2 of its byte +0x94 set and its word +0xC0 non-zero), walks the active
  spawn list at 0x021081F4 to find its record and appends
  subarea, coords index and role to the mailbox: a counter and a ring of
  eight entries.
- **Data.** Mailbox at 0x020CB500; spawn record pool at 0x02107FB4. Layouts
  in memory_map.md.
- **Interaction with the client.** The client polls the counter only when a
  pickup_checks option is on, maps each new (subarea, index) pair to its
  location, ignores repeats and resynchronises when the counter goes
  backwards after an emulator reset.
- **Limits.** Eight entries: more collections than that between two polls
  lose the oldest. The mailbox is RAM and starts at zero on every boot.
  Enemy and NPC drops are never reported, by design.

## DATA SELECT biometal icons

- **Why.** The save-slot screen draws one icon per owned biometal by testing
  raw bits of the slot's copy of the progress block, not through the
  ownership routine: with ownership in the free flags a save showed only
  Model X, and would show a model after the first boss of its pair without
  the item.
- **What it changes.** Per H, F, L and P icon an 8-byte in-place sequence
  reads the u32 at slot offset 0x58, whose high byte is 0x02104627, shifts
  it down and masks the first-half bit; the `ands` still sets the Z flag the
  original branch depends on. For the X/ZX icon the branch taken when ZX is
  absent calls the cave, which selects the X frame and, when the slot does
  not own X (0x021045CF bit 7), hides the sprite by clearing bit 0 of its
  byte +0xA.
- **Data.** Slot buffers at 0x0215D808, 0x4F4 bytes each, copies of the
  saved progress block.
- **Limits.** Only the first half of each biometal is shown. The ZX and OX
  icons keep their vanilla tests, the same bits the randomizer uses.

## Go to Transerver from the pause menu

- **Why.** A way back to the Transerver network from anywhere, as a menu
  action in the game's own UI rather than a client command.
- **What it changes.** On the MISSION tab the scroll handler reads the held
  buttons: the D-pad scrolls the map, A scrolls fast, X leaves the scan and
  Y is unused. Cave A replaces the pad read: it returns the held
  pad and, when Y has just been pressed, sets two flag bytes, "warp
  requested" for the client and "close menu" for cave B. Cave B replaces the
  call to the menu-closing routine: with the close flag set it clears it and
  returns "close", like START; otherwise it tail-calls the original. The
  three variants of the help text "Control Pad:Scan Area Map" in
  m_sub_en.bin (offsets 0xB14, 0xB4B, 0xB85 from ROM 0xDFB200), one each for
  an area with no Transerver, with one and with several, become "Y
  Button:Go to Transerver", same length; the vanilla text is recognised by a
  SHA-256 digest instead of being stored in the repository.
- **Data.** Flags at 0x020CB9D0 (request) and 0x020CB9D1 (close); pad state
  at 0x020F2768, previous frame at 0x020F276A.
- **Interaction with the client.** The client consumes the request, opens
  the game's Target Area list with no current station and, when the list
  closes, teleports the player to the hub floor of the chosen area.
- **Limits.** Without the client the menu closes and nothing else happens.

## NOTIFY: on-screen notices

- **Why.** Received and sent items are announced in game, without stopping
  play, with the game's own font and popup.
- **What it changes.** The gameplay handler's per-frame call to the message
  tick goes through the cave. When the notice buffer has a request and the
  message system is idle, with no cutscene (0x0214F502 bit 0) and no console
  or NPC dialogue (0x0214F506 bit 1), the cave opens the small non-blocking
  popup the game uses for "Found a Life Up!" with a direct pointer to the
  buffer, or with a vanilla message id when the request says so, then calls
  the tick. The request is cleared when the popup reaches its closing phase;
  if a scene change resets the message system first, the notice is
  relaunched.
- **Data.** Notice block at 0x020CB700: request, state, duration and a text
  buffer in the game's encoding (ASCII minus 0x20, colour controls, 0xFD
  page break, 0xFE end). Layout in memory_map.md.
- **Interaction with the client.** The client writes text and duration, then
  the request byte last and only when the previous one is cleared; it splits
  long texts into 0xFD pages, which the popup shows in turn without closing.
- **Limits.** One line of 30 glyphs per page; a longer line wraps onto its
  own first glyph. A vanilla pickup popup fired over a notice replaces the
  text without restarting the phase. Notices wait during pause, transitions
  and cutscenes.

## Cutscenes always skippable

- **Why.** START skips a story cutscene only when its unique event bit is
  already set, that is, on a replay; in a randomizer every cutscene is a
  first viewing for the save.
- **What it changes.** The script VM opcode that opens a skippable block
  sets the "skippable" flag only if the event was seen; that branch becomes
  a no-op. The START reader jumps to the handler's post-cutscene state, the
  path used after dying and retrying, where the handler replays flags and
  warps itself; two of its instructions become a call into the cave, which
  marks the event as seen with its backup, what the closing opcode would
  have done, and re-executes the displaced instructions. The resulting state
  equals having watched the scene.
- **Data.** Event bitfield at 0x021045C0 (96 bits); skippable flag at
  0x0214F502 bit 4; current event id at 0x0214F503.
- **Limits.** Only scripts that open a skippable block, the story
  cutscenes, 87 of the game's 292 scripts; boss introductions and a few
  short room scripts have none. In
  the hub the skip path performs a checkpoint the full viewing does not;
  harmless.

## AP icon set

- **Why.** Every physical pickup (94 disks, 8 Life Ups and Sub Tanks, 133
  refills) should look like the item placed there. Biometals, Card Keys and
  chips have no world sprites in vanilla, so a new graphics set is needed,
  and it must be in VRAM in every room.
- **What it changes.** At patch time icons.py builds the "AP" set from the
  player's ROM: the three Archipelago logos shipped in gfx/, the Life Up and
  Sub Tank, the eight ITEM B chips, the eight STATUS model badges and the
  six ITEM C Card Keys, packed as a static 4bpp set with one palette. It is
  inserted as set 261, empty in vanilla, into obj_fnt.bin and obj_dat.bin;
  the following offsets shift, so both files are relocated to the free
  padding at the end of the ROM by rewriting their FAT entries and the
  used-size field at header 0x80. The set is made resident like the item
  atlas, set 58: the global resident list [0, 1, 58] gains a fourth entry,
  its two length constants become four, and the boot cave replaces the VRAM
  upload of set 58 with that upload plus the registration and upload of set
  261 into a static VRAM slot.
- **Data.** Resident list at 0x020C9C30; obj_fnt.bin and obj_dat.bin are
  NitroFS files 235 and 234; set format in the icons.py docstring.
- **Limits.** Icons are quantised to the 15 colours of the item palette.

## Icon caves

- **Why.** A pickup's graphics are decided when its entity is created, so
  the choice of icon is made in the ROM from a per-subarea table the client
  provides.
- **What it changes.** LOOKUP finds the entity in the spawn list for its
  coords index and returns the code from the client's table, or -1 when the
  table is for another subarea, the entry is empty or the location is marked
  sent. ATTACH replaces the graphics-attach calls of disks, Life Up/Sub Tank
  and refills and, given a code, attaches set 261 while clearing the entity's
  "dynamic set" and "foreign palette" bits. ANIM replaces the following
  animation calls and uses the LOOKUP code when the entity carries set 261.
  Collection logic is untouched.
- **Data.** Icon table at 0x02191460 (0xC4 bytes), free RAM between the
  model overlay slot and the room overlay slot; spawn list at 0x021081F4.
  Table layout and icon codes in memory_map.md. Entity fields: u16 +0x22
  holds the attached set, bit 3 of +0xB marks a dynamic set and bit 0 of
  +0xC a palette borrowed from another set.
- **Interaction with the client.** The table for the current subarea is
  written on room change, on scout arrival, on sending checks and when the
  ROM lost it, one code per coords index: the item's own sprite when it is
  one of ours, otherwise a logo by classification; sent locations are marked
  so the pickup keeps its vanilla look.
- **Limits.** A location sent while its pickup remains, as after a collect
  command, shows the vanilla disk tile.

## PALSHARE

- **Why.** The game hands out 15 of the 16 OBJ palette slots and several
  rooms use all of them. A resident set with a palette of its own pushes the
  next dynamic set in such rooms, for example the hit effect in the Lurerre
  arena, set 124, out of the budget; that set is never registered and the drawers
  dereference a null slot record on its first use.
- **What it changes.** The boot cave asks for no palette when it registers
  set 261 and, on its way out, copies the palette slot of set 58 into the
  slot table entry of set 261. The AP set is drawn with the resident item
  palette and every room's palette budget is back to vanilla; icons.py
  quantises the icons to that palette.
- **Data.** Palette slot table at 0x02105EE4, indexed by set number.
- **Limits.** Icon colours are bounded by the item palette.

## RETRY

- **Why.** ATTACH and ANIM run once, at entity creation, and the spawner
  creates entities by proximity to the camera. A pickup near the room
  entrance is born during the room load, ahead of the client's table for the
  new subarea or of the item scouts, and would keep its vanilla graphics.
- **What it changes.** The per-frame animation-advance call of the disk
  think, of the Life Up/Sub Tank think and, for refills, inside the mailbox
  cave (the think's own site belongs to the mailbox hook) goes through the
  cave. If the entity does not yet carry set 261 and LOOKUP now resolves a
  code, the cave repeats the attach and animation of the init; it always
  calls the original routine and never downgrades an icon to the vanilla set.
- **Data.** Same table and spawn list as the icon caves.
- **Interaction with the client.** None beyond the table; it is what makes
  the client's asynchronous writes sufficient.
- **Limits.** Every pickup without an override walks the spawn list once per
  frame while alive.

## Sprite guard: set without a VRAM slot

- **Why.** When the set registrar rejects a set because the palette or tile
  budget is exhausted, the set's slot entry stays at 0xFF. Ten sprite
  drawers then resolve the slot record to a null pointer and read a halfword
  from address 2: a data abort and a grey screen. It is a latent bug of the
  game that any extra resident graphics make reachable.
- **What it changes.** At the ten sites `ldrh r0,[r0,#2]; movs r3,#1`
  becomes a call into the cave, which performs both instructions only when
  the record pointer is non-zero; a sprite whose set has no slot is skipped
  instead of hanging the console.
- **Data.** Slot table at 0x02105C94, indexed by set number.
- **Limits.** Dozens of other sites follow the same null-record pattern with
  other load instructions; only the ten identical `ldrh` sites are guarded.
  The real protection is not exhausting the palette budget, which PALSHARE
  does.

## PICKUP_AP: pickups replaced by AP items

- **Why.** A pickup that stands for a multiworld location must not also
  apply the vanilla object's effect: healing, weapon energy, E-Crystals, an
  extra life, the "Found a Life Up!" popup or the disk label over the player.
- **What it changes.** The cave's entry routine decides whether an entity is
  a pending multiworld location: table for the current subarea and valid,
  entity found in the spawn list, and its coords index set in the "present"
  bitmap. Four hooks use it. In the refill think an AP pickup plays the disk
  chime and jumps to the handler's epilogue, skipping the effect switch;
  otherwise the displaced instructions are re-executed with the flags
  intact. For disks the call that creates the label and plays the chime is
  diverted: an AP disk chimes and goes straight to the release state, and
  its flag is still written because it is the detection; skipping the call
  alone is not enough, since that routine is also the disk's next state
  handler and retries the label every frame. For Life Ups and Sub Tanks the
  jingle and popup sequence becomes a call that only chimes for AP pickups;
  the high-nibble grant is kept.
- **Data.** The "present" bitmap at offset 0xA4 of the icon table; state
  tables per entity kind at 0x020EB8B0. Sound ids: 0x1A disk chime, 0x24
  Life Up jingle, 0x18 Sub Tank jingle; popup messages 1065 (Life Up) and
  1066 (Sub Tank); the refill think's epilogue is at 0x020A31AC.
- **Interaction with the client.** The bitmap is written even with icons
  off: refills only while their location is unsent, since they respawn and
  should heal afterwards; disks, Life Ups and Sub Tanks always.
- **Limits.** After a collect command the physical pickup stays and only
  chimes. Every AP pickup uses the disk chime.

## Hu gate (optional)

- **Why.** With hu_in_pool the human form is an item. In vanilla category 0
  of the ownership check has a null flag list, so the check returns the
  category count, one, and Hu is always owned.
- **What it changes.** Only when the configuration blob asks for it, the
  category 0 list pointer is pointed at a one-entry array in the cave area
  holding flag 136 (0x021045DD bit 0, unused by the game). The count is
  already one, so Hu is owned exactly when that flag is set.
- **Data.** Flag 136 of the progress block; byte 0 bit 0 of mmzx_cfg.bin.
- **Interaction with the client.** The Model Hu item sets the flag in the
  live and canonical blocks. With the gate on the client treats Hu as a
  normal non-owned form and reverts a scene that leaves the player in Hu.
- **Limits.** The transformation wheel needs two owned categories: with the
  gate on and a single biometal the transform button does nothing, and a
  story scene that ends in Hu depends on the client to restore the form.

## Secret Disk logo

- **Why.** Disks are the most common pickup and their tile is what a pickup
  shows when no icon override applies, so the tile itself carries the logo.
- **What it changes.** The disk body is unit 0x11 of set 58 in obj_fnt.bin:
  a 16 by 16 pixel 4bpp sprite of four 8 by 8 tiles in the order top-left,
  top-right, bottom-left, bottom-right, low nibble first, 128 bytes at file
  offset 0x5620C, drawn with OBJ palette slot 1 and shared by the four disk series.
  The bytes are replaced in place inside the relocated file with the official
  16 by 16 Archipelago logo from the Metroid Zero Mission apworld, its six
  coloured islands remapped to the indices of palette 1 (maroon 9, orange
  0xC, greens 1 to 3, blue 5, blue-violet 4 for purple, red 0xA for pink,
  white outline 0xF) and the centre left transparent. The vanilla tile is
  recognised by a SHA-256 digest rather than stored.
- **Data.** obj_fnt.bin is NitroFS file 235; set 58 is uploaded to VRAM once
  at boot.
- **Limits.** The 8 by 8 sparkle drawn behind the disk shows through the
  transparent centre now and then.

## AP marker and configuration blob

- **Why.** The client must recognise a patched ROM and learn the slot name
  to log in; the ARM9 step must know which options change code.
- **What it changes.** The token step writes a 0x80-byte block at ROM offset
  0x1000, zero padding in the vanilla image: the magic `MZXAP`, the world
  version, the slot name and the seed name. The configuration blob is a file
  inside the .apmmzx, not written to the ROM; its only bit is hu_in_pool.
  Layout in memory_map.md.
- **Interaction with the client.** On connection the client reads the game
  code at ROM 0x0C, the magic and the slot name; the slot name becomes the
  login.
- **Limits.** Nothing in the game reads the marker.

## Assembly sources

The cave bodies live in `rom.py` as hexadecimal byte strings next to the
constants of their patch, with the cave address and the addresses of the
hooks that call them. Hook encodings are not stored: the Thumb `bl` for each
site is computed at patch time from source and destination. The commented
assembly sources of every cave will be published in `src/asm/`, kept in the
repository and excluded from the .apworld; until then the byte strings in
`rom.py` are the reference and this document describes each routine.

## Compression

The recompressed ARM9 must fit back into its original slot of 0x8F400 bytes
and a greedy BLZ encoder leaves too little headroom for the caves, so `rom.py` carries its
own encoder that chooses the tokens by dynamic programming: for every
position it knows the longest match available, found by bisection inside a
bounded window, and picks the token that minimises the size of the rest of
the stream, counting a literal as nine bits and a reference as seventeen.
The result is several kilobytes smaller than the greedy output.

The format is the one the game's start-up code decodes in place from the
end of the region towards its start: after the uncompressed 0x4000-byte
header, groups of one flag byte followed by up to eight tokens, each a
literal byte or a two-byte reference: the high nibble of the first byte is
the length minus 3, the remaining twelve bits are the displacement, and the
token copies 3 to 18 bytes from displacement + 3 bytes ahead of the write
position, up to 0x1002. The start of the region stays
uncompressed wherever compressing it would make the in-place decoder
overwrite input it has not read yet; the encoder cuts the stream where the
decoder's lead is largest, which gives the smallest safe region. A footer
aligned to four bytes closes it: a u24 compressed size that includes the
footer, a u8 footer length (8 plus 0xFF padding) and a u32 count of the
bytes gained by decompressing. The decoder in the vendored apnds package is
the reference for the format. If the region does not shrink or the
blob does not fit the slot, patching fails with an error rather than
producing a ROM that will not boot.
