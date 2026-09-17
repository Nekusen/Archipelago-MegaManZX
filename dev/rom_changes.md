# Changes to the game

What the Mega Man ZX patch changes in your copy of the game, and what the client changes while you play. The rooms,
their layout and the objects in them are the original ones: the patch places no items and carries no seed-specific
logic. Everything that depends on your seed is done by the client through the emulator. The technical description of
each patch is in `rom_patches.md`.

## Starting the game

- New Game skips the whole tutorial. You start on the Transerver floor of the hub chosen by `starting_transerver`
  (floor A by default, floor X for the Guardian base) with the model and the character of your options, on Normal
  difficulty, ready to play. Only that floor's destination bit is set; the others come as items. The starting save
  is baked into the patched ROM (an autoload section the skip cave copies into the load buffer), so New Game needs
  no client. Continue works as usual.
- The game code stores your slot name, so the client logs in on its own.

## Items

- Biometals come only from items. Beating a Pseudoroid is still a check, but it no longer gives you its biometal.
  Model HX, FX, LX and PX come in two halves: the first makes the form usable, the second completes the biometal
  (level 2 charged attack, full Weapon Energy bar).
- Life Ups and Sub Tanks found in the world no longer raise your capacity; the items do. The pickups stay in the world
  until you collect them, whatever your capacity is.
- The Operator no longer hands out the Yellow Card Key after Troop Reinforcement. Every Card Key is an item.
- Reporting Locate Giro and Pass The Test no longer adds Area X-1 to the Transport list. X-1 is unlocked like every
  other area: by its Transerver Access item or by reaching its Transerver floor.
- With the `hu_in_pool` option the human form is also an item, and you cannot transform back to it until you have it.

## Pickups

- Every pickup that holds a multiworld item is drawn as that item: Life Ups, Sub Tanks, chips, biometals and
  Card Keys with their own icons from the game, anything else with the Archipelago logo coloured by importance
  (arrow: progression, cross: useful, grey: filler). `/mmzx_icons off` restores the original look.
- Collecting such a pickup plays the disk chime and nothing else: no healing, no extra life, no "Found a Life Up!"
  popup and no disk label. The client then grants what was actually there.
- The Secret Disk sprite shows the Archipelago logo.
- With the `pickup_checks_*` options, the energy capsules, weapon energy, E-Crystals and 1-Ups placed in the levels
  are checks. The first pickup of each sends its location; afterwards it respawns and refills as usual.

## Menus and cutscenes

- The MISSION tab of the pause menu (the area map) gains "Y Button: Go to Transerver". It closes the menu and opens
  the game's own Target Area list with every Transerver you have unlocked; you arrive on that area's floor of the
  hub, as with the console's Transport.
- Every story cutscene can be skipped with START, also the first time you see it.
- The DATA SELECT screen shows the biometals you own through items instead of the ones the story would have given.
- Items received and sent are announced in the game's small popup, in the game's font, without stopping play. The
  `notify_*` options and `/mmzx_notify` choose which items are announced and whether the text is cut to one line.

## Stability

- Two crashes of the original game that the open world makes reachable are guarded: a sprite loop that could
  overwrite memory after a teleport into a boss area, and a grey screen when a room ran out of sprite palettes.

## What the client changes while you play

These are not in the ROM; they happen through the emulator while the client is connected.

- The mission of the area you enter is accepted automatically. On hub floors whose door leads
  straight to a boss, it is accepted when you approach the door.
- Some story gates are open for everyone: the F-3 door, the G-2 door to G-4, the M-1 seal, the D-1 bridge and the
  sand fall that hides the pit from K-1 to K-2. The gate from D-2 into the Slither Inc. tower opens when you hold the
  six biometals.
- Troop Reinforcement runs from D-1, D-2 or D-3 without the base cutscene. Protect HQ starts by itself, as in the
  original game, when you report a mission with four of the eight area missions completed.
- With `skip_boss_rush`, each pair of Pseudoroid rooms in the D-4 tower appears already cleared as the elevator
  reaches it, and the elevator keeps climbing to D-5.
- A form you do not own is reverted, so a model given by a cutscene goes away on the next client tick.
- With `death_link`, your deaths are sent and a received death kills you once you have control.
- If the ending does not start after Serpent falls, the client starts it.
