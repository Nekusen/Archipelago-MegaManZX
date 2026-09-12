# What changes in the game

The levels, the rooms and the objects in them are the original ones; nothing is moved. What changes is how the game
starts, what you find and receive, how you get around and a few conveniences.

## Starting out

- New Game skips the whole tutorial. You start in the Transerver hub of the Guardian base with the model and the
  character from your options, on Normal difficulty. Continue works as usual.
- You do not type a slot name: the client logs in on its own.

## What you find and receive

- Biometals, Card Keys, Life Ups, Sub Tanks and ITEM B chips are multiworld items. Beating a Pseudoroid is still a
  check, but its biometal comes to you as an item.
- Model HX, FX, LX and PX come in two halves. The first half lets you use the form; the second completes it, with the
  level 2 charged attack and the full Weapon Energy bar.
- Pickups in the world show the item they hold: the game's own icon for a Life Up, Sub Tank, chip, biometal or Card
  Key, and the Archipelago logo for anything else (an arrow for progression, a cross for useful, grey for filler).
  Picking one up plays the disk chime and gives you what the multiworld sends, not the pickup's usual effect.
- The Secret Disk sprite shows the Archipelago logo.
- With the `pickup_checks_*` options the energy capsules, weapon energy, E-Crystals and 1-Ups of the levels are checks
  too. The first pickup counts; afterwards the object respawns and refills as usual.
- Items you receive and items you send are announced in the game's own popup without stopping play. The `notify_*`
  options and the `/mmzx_notify` command choose which items are announced and how much text is shown.

## Getting around

- The mission of an area is accepted automatically when you enter it, so you can play the
  areas in any order without going back to the hub.
- The MISSION tab of the pause menu gains "Y Button: Go to Transerver". It opens the game's Target Area list wherever
  you are, with the destinations you have unlocked.
- Every area can be reached on foot. Warping from the hub to an area needs that area's Transerver Access item.
- Some story gates are open from the start: the F-3 door, the G-2 door to G-4, the M-1 seal, the D-1 bridge and the
  sand fall that hides the pit from K-1 to K-2. The gate from D-2 into the Slither Inc. tower opens once you hold the
  six biometals.
- Troop Reinforcement can be started from D-1, D-2 or D-3 without the base cutscene. Protect HQ starts by itself, as in
  the original game, when you have completed four area missions.
- With `skip_boss_rush` the Pseudoroid refights of the D-4 tower are skipped and the elevator climbs straight to D-5.

## Cutscenes and menus

- Every story cutscene can be skipped with START, also the first time you see it.
- The DATA SELECT screen shows the biometals you actually own.

## Other

- A form the story would hand you but you do not own yet goes away on the next tick; you keep what your items give you.
- With `hu_in_pool` the human form is an item too, and you cannot switch back to it until you have it.
- With `death_link` your deaths are shared with the other players, and a received death kills you as soon as you have
  control.
- The randomizer plays on Normal difficulty.
