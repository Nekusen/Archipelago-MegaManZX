# Mega Man ZX

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export a
config file.

## What does randomization do to this game?

Mega Man ZX becomes an open world. The tutorial is skipped: a new game starts in the Transerver hub of the Guardian
base with the model you chose in your options, on Normal difficulty. The biometals, the Card Keys and the Transerver
destinations are items placed somewhere in the multiworld, and the game's collectables, boss fights and missions are
checks. Missions are accepted automatically when you enter their area, so they can be done in any order. Areas can
always be reached on foot; a Transerver Access item lets you warp to the area from the hub.

## What is the goal?

Defeat Serpent at the top of Slither Inc. (D-5). The gate from D-2 into the tower opens once you hold the six
biometals (Model X, ZX, HX, FX, LX and PX). Unless `skip_boss_rush` is on, the tower's boss rush is cleared as usual.

## What items and locations get randomized?

Items:

- Biometals: Model X, Model ZX, Model OX, and the progressive Model HX, FX, LX and PX. The first copy of a progressive
  model gives you the form; the second is the biometal's other half, which unlocks the level 2 charged attack and the
  full Weapon Energy bar.
- The Yellow, Green, Red, Blue and Purple Card Keys.
- Transerver Access for each of the 13 areas with a Transerver (A, B, C, D, E, F, G, I, K, L, M, O and X).
- Four Life Ups, four Sub Tanks and the eight ITEM B chips.
- E-Crystals and 1-Ups as filler.

Locations:

- The 94 Secret Disks.
- The four Life Ups and the three Sub Tanks found in the world.
- Obtaining each of the four biometals, from either Pseudoroid of its pair.
- Completing 14 of the 15 story missions (Destroy Model W is the goal itself).
- Optionally, the 133 refill pickups of the levels (energy capsules, weapon energy, E-Crystals and 1-Ups): the first
  pickup sends the check, then the object respawns and refills as usual.

Quests and Level 4 victories have options in the template but are not implemented yet; turning them on adds nothing.

## What other changes are made to the game?

The patch changes only what the randomizer needs; the rooms and the objects in them are the original ones. Pickups
that hold a multiworld item are drawn as that item, play the disk chime and have no other effect. Beating a Pseudoroid
no longer gives you its biometal. Items are announced in the game's small popup, every story cutscene can be skipped
with START, and the pause menu's MISSION tab has "Go to Transerver" on Y. Full list: [rom_changes.md](rom_changes.md).

## When the player receives an item, what happens?

The client applies it within a fraction of a second, while you are in gameplay. A biometal appears in the transform
menu with its Weapon Energy filled; a Card Key opens its doors at once; a Transerver Access adds its destination to
the Transport list; a Life Up or Sub Tank raises your capacity; a chip appears in the ITEM B tab of the pause menu,
where you activate it. E-Crystals (50 per item) and 1-Ups are added once per save. Depending on `notify_received`,
the game's popup shows "Got <item> from <player>" without stopping play; `/mmzx_notify` changes it mid-game.

## Which difficulties and logic levels exist?

The game always runs on Normal difficulty. What varies is the logic:

- `logic_difficulty`: `normal` only uses safe routes. `expert` adds the alternatives marked as expert in the logic: a
  few passages and checks that normal reserves for a specific model (HX's air dash, PX's wall climb, LX's swimming)
  are allowed with any model or with none, through tight jumps, damage boosts and swimming between spikes.
- `boss_logic`: for each story boss, what you must be carrying before the logic considers you able to beat it, for
  example `Hivolt: "HX & Life Up x2"`. It never restricts what you may fight in the game; it only keeps the seed from
  forcing you through a boss you are not equipped for by your own standard. A Life Up, Sub Tank or chip named in a
  requirement becomes a progression item.
- `skip_boss_rush`: the D-4 tower marks each pair of Pseudoroids as beaten while you climb, so you never refight them.
  The logic then stops requiring the eight bosses to reach Serpent.

## Can I play offline?

No. The patched ROM places no items and does not know your options: the BizHawk Client grants every item, including
your own, starts the game in the hub, accepts missions and performs the teleports. Keep it connected to the server
while you play, also in a single-player game. If the connection drops, nothing is lost: checks are read back from the
game's own flags and items are re-applied when you reconnect.

## Is DeathLink supported?

Yes, with the `death_link` option. Your deaths are sent, and a received death kills you as soon as you have control,
like any other death: one life is lost and you return to the last checkpoint.

## Is there a tracker?

Universal Tracker shows a map tab with one map per area and one per room, switches to the room you are in and marks
your position. The world ships the map layout; the images come from the separate
[Mega Man ZX tracker pack](https://github.com/Nekusen/MegaManZX-Tracker/releases) (`mmzx_tracker.zip`, kept zipped).
UT asks for the file the first time it needs it; the [setup guide](setup_en.md) says where to set its path.
