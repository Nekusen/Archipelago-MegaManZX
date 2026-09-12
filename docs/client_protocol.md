# Client protocol

How the Mega Man ZX client talks to the patched game, for someone who knows Archipelago's
`BizHawkClient` and wants to change the client without re-deriving its contracts. Addresses and
structure layouts are in `memory_map.md`, the ROM patches in `rom_patches.md`, and the project's
vocabulary in `glossary.md`.

## 1. Overview

The client is a `BizHawkClient` (`worlds/_bizhawk`). Every 125 ms the framework calls its watcher,
which reads the game's RAM through the "ARM9 System Bus" domain of the melonDS core, sends new
checks, applies received items and keeps the game in a state the multiworld can live with. Reads
are batched per stage. Every write in gameplay is a guarded write on the game-state word: if a
scene load started in between, the write is dropped and the stage retries on the next tick.

The patched ROM does not place items. It exposes small structures in free RAM that the game and
the client share: a mailbox for collected pickups, a per-room icon table, a notice mailbox for the
on-screen popup and a warp request byte. The client also writes the game's own structures: the
progress block and its canonical copy, the player persistent block, the scene descriptor, the
story block and the mission state. The client grants everything, including local items and the
start inventory, so the world uses `items_handling = 0b111`.

## 2. Startup and validation

`validate_rom` reads the ROM domain: the game code must be `ARZE` and the AP header written in the
padding after the NDS header must start with the `MZXAP` magic. The header also holds the slot
name, a world version and the seed name; the client takes the slot name for `set_auth` and does
not compare the other two. A vanilla ROM is rejected with a message telling the player to open
the `.apmmzx` first. Per-slot options come in slot data and are read once per connection:
`death_link`, `mission_auto_accept`, `skip_boss_rush`, `hu_in_pool`, `starting_model`,
`character`, `starting_transerver`, the four `pickup_checks_*` toggles and the `notify_*` settings.

### The golden image

The tutorial is skipped by handing the game a ready-made save. The ROM patch redirects New Game to
the game's LOAD handler and the client fills the LOAD buffer with the golden image: the save image
of a fresh post-tutorial game (play-time counter, scene word, canonical progress block and its
mirror, player persistent block and its mirror, story script state), placed on hub floor A-2 next
to the console, Normal difficulty with its two lives, no mission in progress and no disk or room
flags. `golden.build_image` patches it per slot: the starting model's possession bit and active
model (Model X is revoked unless the start is X), the character byte in the player block and in
the menu copy, Normal difficulty and lives, and for HX, FX, LX and PX the first boss's victory
level plus a full Weapon Energy bar. Each field goes to the primary copy and to its mirror.
`starting_transerver` offers only the hub.

The image is seeded on every tick while the title screen or its menus are up: title carousel step
3 or 5, and game-state word equal to the gameplay value or a Game Over menu value. That excludes
the boot logos, the title load, the data select of Continue (whose SRAM restore would be
clobbered) and gameplay, where the same buffer is the live scene buffer. The write is guarded on
both values. Exit Game after a Game Over returns to the same carousel, so every New Game lands in
the hub.

A one-shot path applies the same starting state by RAM pokes, driven by the datastore key
`mmzx_start_applied_<team>_<slot>`: request, wait for the reply, apply once the player is in the
hub with the Area A access bit set, confirm the active model holds for four ticks (the LOAD may
force Model X once), then mark the key. If the key is set but the game shows the raw golden
signature (Model X owned without the item while the start is another model), the client re-arms
it: a new save under an old slot. `/mmzx_start` forces it.

### Being in game

Nothing in gameplay is read or written until four signals agree: title carousel step 6 (game
launched), stable subarea not zero, HP above zero and game-state word equal to gameplay. The title
and its menus share the last three, hence the carousel step. The client then waits three in-game
ticks and until the message bank word is initialized, since some structures still hold the boot
fill right after launch.

## 3. The watcher loop

Each stage runs isolated: an exception is logged once per stage and the loop carries on; only a
connector failure aborts the tick. In order:

1. Connection guard (server and slot data), then one-time setup: DeathLink tag, options,
   notice thresholds and console commands.
2. Starting-state resolve: advances the datastore state machine, also in menus.
3. Golden image seeding, title and menus only.
4. In-game guard and startup debounce; if not in game, reset per-tick state and return.
5. Position report to the datastore for Universal Tracker.
6. Check detection: one read of the progress-block window plus the far bytes, one `detect` each.
7. Pickup mailbox poll (if a pickup category is on); its ids join the set. If the set grew,
   `check_locations` gets the whole set and "Sent" notices are queued.
8. Icon table sync for the current subarea, `present` bitmap included, plus the scout requests
   that icons and notices need. After the mailbox, so a just-collected refill reads as sent.
9. Troop Reinforcement unstick.
10. Mission bits restore (open world only): re-set the active mission's extra bits.
11. Diagnostics requested from the console.
12. Starting-state apply, one shot.
13. Grant items: recompute the desired state from `items_received`, write the differences.
14. Notices: queue "Got" for newly received items, push one notice if the popup is free.
15. Revert models the player does not own; after the grant, so a model just received is owned.
16. Auto-accept the mission of the current subarea or hub floor (open world only).
17. Boss rush skip (option only).
18. DeathLink send and receive (option only).
19. "Go to Transerver" request, and the selection it produces.
20. Pending teleport, from a command or from stage 19 in the same tick.
21. Goal: when the goal bits are set, send `CLIENT_GOAL` once.
22. Ending unstick; after the goal, because it only matters once Serpent is dead.

## 4. Detecting checks

Each location in `data.LOCATIONS` carries a `detect` recipe: `bit`, one bit of the live progress
block (Data Disks) or the high nibble of the capacity bytes that the patched game sets when a Life
Up or Sub Tank is picked up; `all`, every listed bit ("mission completed"); `any`, any listed bit
("Obtain Biometal": either Pseudoroid of the pair writes its own bit and the check is the pair);
`mailbox`, a respawnable pickup identified by subarea and coords index; none, no reliable
detection, so the location is not created (some missions, all quests, the Level 4 victories).
The checked set is cumulative in the client and re-sent whole when it grows. Flags are the source
of truth: after a reload the same flags produce the same set.

### The pickup mailbox

Fixed refills (energy, weapon energy, E-Crystals, 1-Ups) have no persistent flag and respawn on
every visit. The ROM keeps a mailbox in free RAM: a 32-bit counter and a ring of eight 32-bit
entries `[subarea, coords index, role, 0]`, entry k in slot k modulo 8, appended each time a
layout refill is collected. The client maps `(subarea, index)` to a location, sends the first
occurrence and ignores repeats. If the counter is lower than the last one seen (the mailbox lives
in RAM, so an emulator reset zeroes it) or this is the first read, only the last eight entries
are processed.

### Pickups replaced by items

A pickup that is a multiworld location is a replacement, so the game must not apply the original
effect. The `present` bitmap of the icon table (`PICKUP_AP`) lists the entities of the room that
are locations not sent yet: those play the disk chime and skip the heal, the extra life, the
"Found a Life Up!" popup and the disk label. Refills are present only until sent and then behave
as vanilla; disks, Life Ups and Sub Tanks are always present, since they never respawn and after
a `!collect` the object is still there. The detection flag is still written by the game.

## 5. Granting items

Every tick the client recomputes what the game should hold from `items_received` and writes only
the bytes that differ. Idempotent grants can be recomputed at any time: models, Card Keys, chips,
Transerver access, event gates, Life Up and Sub Tank capacity, victory levels. Consumables,
E-Crystals (50 each, capped at 99999) and 1-Ups (one life, capped at 99), are applied once per
game and recorded in the datastore.

The progress block exists twice: the live copy the game reads during play, and the canonical copy
that the checkpoint restores on death and that goes to the save. A grant sets its bit in both,
live for the immediate effect and canonical to persist. The `grant` field of `data.ITEMS` names
the recipe: `live_bit`, `progressive` (copy k sets the k-th bit of a list), `transerver`,
`lifeup`, `subtank`, `ecrystals`, `oneup`.

Consumables are stamped with the game's play-time counter: one per frame, never back on death,
back to the save's value on Continue or LOAD, zero on a new game. The key
`mmzx_consumables_<team>_<slot>` holds batches `[cumulative count, play time]`. The count already
present is the highest cumulative count stamped no later than the current play time; later
batches belong to a state the player rewound and are granted again. Nothing is granted until the
datastore reply arrives or while the play time is zero, so a reconnect never adds crystals twice.

### Models

Ownership of a form comes only from its item. The ROM patch makes the game read the ownership of
HX, FX, LX and PX from free flags that only the client sets, one per half: the first copy of the
progressive item makes the form usable, the second completes it (level-2 charged attack, larger
Weapon Energy cap). X, ZX, OX and, with `hu_in_pool`, Hu are single bits. Beating a Pseudoroid
fires the check and grants nothing.

Weapon Energy caps come from the victory levels of the pair's two bosses, which only a real
victory writes, so a model granted by item would start with an empty bar. When the levels do not
add up to the cap the client sets them: with one half, the first boss level is raised so the sum
is 4 and the bar is filled to 16; with both halves, both levels become 4 and the bar is filled to
32. The condition is false afterwards, so it runs once.

Every tick outside cutscenes, once the first `ReceivedItems` has arrived, the client enforces
ownership: an active form the player does not own is reverted to the last legitimate form, else
the YAML starting model, else any owned model, else Hu; any possession bit set without its item is
cleared in both copies, second-half bits included. Boss victories and the Troop megamerge change
the active form, the LOAD may force X, the level shop re-derives the second half; this stage
undoes all of it. With `hu_in_pool` Hu is just another form: the game refuses to transform with a
single owned category, so a scene that ends in Hu would be a softlock.

### Everything else

- Card Keys: the received set is authoritative. Exactly those bits are written, leaving the
  neighbouring flags alone, because the game hands out some keys as mission rewards. The White
  Card Key is not in the pool.
- Chips: one flag each; the player activates them in the ITEM B menu. Their vanilla sources
  (NPCs, quests) still give them.
- Life Ups and Sub Tanks: the low nibble of the capacity byte is exactly the received count (up
  to 4) and max HP follows it, 16 plus 4 per Life Up; the high nibble, the physical collection,
  is left alone. In the patched game the pickup does not raise capacity.
- Transerver access: each "Transerver Access - Area X" item sets its destination's bit in the
  Transport bitfield, so the game's own list offers it. The network is hybrid: walking is always
  allowed by the logic, only a warp leaving the hub needs the item of the destination floor's
  badge, and the starting area's access is pre-granted.
- Event gates: some story gates are opened for everyone (F-3, G-2 to G-4, the M-1 seal, the K-1
  sand fall); the two flags of the Slither gate from D-2 to D-4 are set when the six model items
  are held (X, ZX, HX, FX, LX, PX).

## 6. Missions

With `mission_auto_accept` (the default), entering a mission's subarea accepts it, once per
subarea change and never if it is already active or already completed according to its
"completed" bits (a second Report would pay a second reward). `data.MISSION_ACCEPT` maps subarea
to the mission record: id, state value, start flag, extra bits, initial handler state. Missions
whose only room is the boss room are accepted in the whole area. Protect HQ is not in the table:
the game launches it on any Report once four of the eight area missions are done.

The accept recipe replicates what the console does, in one guarded write:

1. Mission start snapshot: live block to its mirror, scene descriptor 1 to descriptor 2, live
   story block to queue 2. "Abort Mission" restores these; without the snapshot it would bring
   back the golden image contents.
2. Start flag in both copies, mission state value, mission-active flag, and the "mission in
   progress" bit that the game's "is mission X active" query requires.
3. Story handler: a zeroed handler object with no pending cutscene and the mission's initial
   state, plus the mission id. Without it the mission's cutscenes and rectangle flags never run.
4. Extra bits, the "step taken" flags that room scripts check first. Troop needs four of them or
   the X-2 auto-report takes the first-visit dialogue branch.
5. Checkpoint commit: live block to canonical and story block to its checkpoint copy, as the
   game does on a pad; otherwise a death ahead of the first milestone restores a checkpoint
   without the mission.

If the mission is already active only missing extra bits are added, and stage 10 does the same
every tick, so a game that lost them heals on its own.

Hub floors whose door leads to a boss room (E, F, G, I, K, L, M, O) keep the floor door and the
arena shutters locked until the area's mission is accepted or completed. The client accepts it
when the player stands on such a floor and approaches the left door; accepting on arrival would
turn the floor's console into "Abort the mission?".

Troop Reinforcement: the Giro scene at the end of D-2 only triggers with the start flag set and
the megamerge flag clear. While Troop is active and not completed, the player is in D-1, D-2 or
D-3 and no cutscene runs, the client restores the start flag and clears the megamerge flag,
except once the D-2 room script has passed the merge: from there the flag is legitimate and the
X-2 report requires it.

Ending: the credits chain is driven by the story handler of mission 16, not by the D-5 room. If
Serpent's second form dies with that handler missing or behind its waiting state, the screen
stays on the last fade to white. The client watches for that signature in D-5 (both Serpent bits
set, game not marked complete, no cutscene, room script in its terminal state) for five
consecutive ticks and installs the handler at the waiting state; the game continues into the
credits by itself. It runs after the goal and writes only the handler. Installing the handler at
its initial state while already inside D-5 starts a D-4 cutscene that never ends; entering
through D-4 avoids that, a manual teleport into D-5 does not.

Boss rush skip: with `skip_boss_rush`, in D-4 with the mission 16 handler installed and no
cutscene, `bossrush.py` decides which Pseudoroid pairs to mark as beaten: the player must be
standing on the elevator at the pair's stop with the matching handler state and elevator stage,
or inside the pair's room. Marking a pair early makes the elevator jump to its stop and drops the
player into the pit. The write sets the pair's two flags, commits the checkpoint the way the pads
do (spawn without fraction and facing into the player block and scene descriptor, live block to
canonical, story block to queue 1), repaints the two capsules as used and marks the tile map
dirty. The full commit is needed because the tower's fade doors update the respawn position in
the scene descriptor but not the handler's checkpoint copy: a death after a partial commit would
respawn with the handler out of step and the elevator dead. The position is written without its
fraction and only once the elevator has stopped, because a spawn inside the moving platform pushes
the player out of the map. Once the pair is set the handler chains only the next cutscene and the
elevator resumes its climb on its own. With the option on, the logic does not require the eight
Pseudoroids for D-5.

## 7. Talking to the player and the server

### On-screen notices

The `NOTIFY` mailbox in free RAM is `REQ` (u8), `STATE` (u8, owned by the ROM), `DUR` (u16, frames
the text stays) and `BUF` at +4. The client writes `BUF` and `DUR`, then `REQ = 1`, only when `REQ`
is 0; the ROM clears it when the popup closes. Text uses the game's font, ASCII minus 0x20,
terminated by 0xFE; 0xFD separates pages and two-byte color controls switch between white and
green. The popup shows one line of 30 glyphs; `BUF` holds 0xFC bytes. `short` keeps one line,
dropping the player name and then trimming the item; `full` splits the text by words into pages
the popup chains without closing, each page starting with its own color control.

The queue holds 16 notices. "Got <item> from <player>" is queued for items received after
connecting (the backlog is silent); "Sent <item> to <player>" for own checks holding another
player's item, which needs `LocationScouts` of the missing locations, requested without creating
hints and requested again if the server clears the scout info. Thresholds per channel (off,
progression, useful, all) come from the YAML and default to `useful` when the slot data has no
`notify_*` keys; `/mmzx_notify` overrides them per session.

### The icon table

Per subarea the client writes 0xC4 bytes: the subarea, a valid flag, one code per coords index
(`ICON_CODES`, the AP graphics set animation plus one; 0 means no change), a 32-byte "already
sent" bitmap at +0x84 (vanilla look) and the 32-byte `present` bitmap at +0xA4 of section 4. A
location's own item with a sprite gets its icon; anything else gets the Archipelago logo by
classification: arrow for progression, cross for useful, grey for filler. Codes stay 0 until the
scouts arrive. The table is rewritten when the subarea changes, when scouts arrive, when checks
are sent and when the header does not match any more (the ROM lost it after a reset).
`/mmzx_icons off` zeroes the codes but keeps the bitmaps. The ROM retries the sprite override
every frame for pickups spawned while the table was not yet valid (`RETRY`), so the client does
not race the spawner.

### DeathLink

Sending: an HP transition from above zero to zero is a death, unless the client caused it.
Receiving: when the context's last DeathLink advances, the death is pending until the player has
control (HP above zero, no cutscene, player state normal); then the client writes HP 0 and the
player's dying state bytes, which is what the player tick does on a lethal hit. Writing HP alone
does not kill. The result is a full death (animation, one life less, reload at the checkpoint)
and the HP transition it causes is not echoed back.

### Universal Tracker

The key `mmzx_pos_<slot>` holds `[subarea, x, y]` in room pixels, written on every subarea
change and otherwise at most once per second after 48 px of movement, because UT reloads the tab
on every change. `tracker_world` runs in hybrid mode: the map layout JSON ships in `tracker/`,
the images come from the external pack the player points `ut_pack_path` at, and
`tracker_pos.py` turns the position into a map index and icon coordinates. In the hub the icon
sits on the badge of the floor's area on the overall map.

### Go to Transerver and teleports

The ROM adds "Go to Transerver" to the MISSION tab of the pause menu: Y sets the warp request
byte and closes the menu. The client consumes the request by clearing it, setting the Transport
selection to -1 and requesting the game's "Target Area" list state, so the game's own list opens
with every destination whose access bit is set. When gameplay resumes, the selection (a station
index, or -1 for cancel) becomes a teleport to that area's floor of the hub, on top of the
floor's console, where the vanilla Transport leaves the player. The list never moves the player
by itself: at a console the Operator's script does the repositioning and requests the transition
state, so here the client does it.

A teleport writes the scene descriptor (spawn x and y as 8.8 fixed point, subarea, facing) and
requests the scene-load state with its two following words cleared; the game runs its normal
scene load. It is only issued in gameplay. The default destination is the console pad of floor A.
Landing on top of a door does not register the door contact, so the recipe targets pads.

### Console commands

For the player: `/mmzx_teleport` (hub, a floor letter, or subarea and pixels), `/mmzx_where`
(position and state to the log, for bug reports), `/mmzx_accept` (force the mission of the
current area), `/mmzx_start` (re-apply the starting state) and `/mmzx_icons` (item icons on the
pickups on or off).

`/mmzx_notify <level>` sets the notice threshold of both channels and `/mmzx_notify received|sent
<level>` one of them, with the levels `off`, `progression`, `useful` (progression and useful) and
`all` (filler too: E-Crystals, 1-Ups). `/mmzx_notify short|full` picks one trimmed line or the
whole text in chained pages, and with no argument the command prints the current setting. The
values start from the YAML and are not kept between sessions.

`/mmzx_debug on|off` raises the client's diagnostic messages from the debug level to the log the
player sees. It is off by default and meant to be turned on before reproducing a problem.

The client also registers development-only commands that dump RAM regions to the log; they are not
part of the player-facing contract.

## 8. Persistence and synchronization

The client keeps three datastore keys: applied consumables (section 5), starting state applied
(section 2) and the position for UT (section 7). Everything else is derived from the game's RAM
and `items_received` on every tick. The game's save holds the canonical progress block and the
player persistent block, so grants written to the canonical copy survive save and load, and
checks are re-derived from flags after any reload.

On reconnect the client forgets its local checked set and re-sends the whole set (the server
ignores repeats), re-applies every idempotent grant, does not re-add consumables, does not
announce the backlog and requests the scouts again. Loading another save or resetting the
emulator rewinds the play time (consumables are granted again where needed), zeroes the mailbox
(the client resyncs on the last eight entries; older mailbox checks are covered by the server's
checked set) and clears the icon table and the notice mailbox (both are rewritten). A new save
under a slot that already applied its starting state is recognised by the raw golden signature
and re-armed.

Known traps:

- A change in the ROM patch does not reach a game in progress: the ROM must be created again
  from the `.apmmzx`. The client cannot patch code.
- Savestates carry the code and the free-RAM structures of the ROM they were made with.
- Live versus canonical: writing only the live copy is lost at the next checkpoint restore;
  writing only the canonical copy has no immediate effect.
- The LOAD buffer is the live scene buffer during gameplay: never write it then.
- Every gameplay write is guarded on the game-state word; a rejected stage retries next tick, so
  a transition never receives a half-applied recipe.
