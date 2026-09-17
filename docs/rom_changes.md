# All (player relevant) base modifications to the ROM (as of 0.1.0)

## Starting point

- Starting point: New Game skips the whole introduction. You start on the Transerver floor chosen in your options
  with the model and the character from your options, on Normal difficulty.

## Items

- Pickups in the world show the item they hold: the game's own icon for a Life Up, Sub Tank, chip, biometal or Card
  Key, and the Archipelago logo for anything else (an arrow for progression, a cross for useful, grey for filler).
- Items you receive and items you send are announced in the game's own popup without stopping play. The `notify_*`
  options and the `/mmzx_notify` command choose which items are announced and how much text is shown.

## The "Open World" state

- The mission of an area is accepted automatically when you enter it (no need to select it from a transerver), so you can play the
  areas in any order without going back to the hub. You DO have to report missions on a transerver.
  - Because of this, do not use the in-game mission select or the "Abort Mission" option.
- All bosses are spawned from the beggining, and you can start the fight with them from both sides.
  - The exception for this rule are Rayfly (B-2) and Giro (D-2).
    - Rayfly requires you to get the nearest "Computer Chip" to the boss area to spawn the boss.
    - Giro requires beating both mini-bosses in the area to spawn
- The MISSION tab of the pause menu gains a fast travel function by pressing "Y". It lets you travel to Transerver locations you've unlocked.
- About Area X:
  - The only way in logic considered to reach Area X is to have it as your starting point or receive the Transerver Access from the multiworld
  - Some story points where the teleport to Area X is granted have been patched
  - The missions "Troop Reinforcement" and "Repel the Army" teleport you to Area X on completion. This teleports are NOT considered in logic.
- Some story gates are open from the start:
  - The F-3 door
    - This means you don't need to beat the mini-boss in this area 
  - The G-2 door to G-4
    - These changes mean you don't have to rescue anyone in area G 
  - The M-1 seal (which normally requires all models)
  - The D-1 bridge
  - The sand fall that hides the pit from K-1 to K-2
  - The D-3 ladder up to the walkway that leads to Area O.
- Troop Reinforcement can be started from D-1, D-2 or D-3 without the base cutscene.
- "Protect HQ" becomes available, when you have completed and reported 4 of the "main" missions (the ones with Pseudoroids in them)
  - To start the mission, teleport to Area X and speak with Prairie (you should have seen the previous cutscene on any transerver when reporting a mission
- The gate from D-2 into the Slither Inc. tower opens once you hold the six main biometals (X, Z, F, H, P, L).
- With `skip_boss_rush` the Pseudoroid refights of the D-4 tower are skipped and the elevator climbs straight to D-5.

## Cutscenes and menus

- Every story cutscene can be skipped with START, even if its the first time you see it.
