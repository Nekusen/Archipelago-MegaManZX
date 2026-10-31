# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `sub_tank_refill_operator` (on by default): a Guardian next to your starting Transerver who, for 200 E-Crystals,
  refills every Sub Tank you hold. Talk to him with UP; with nothing to fill he charges nothing.
- Added `infinite_lives`: a death never costs a life and there is no Game Over. With it on, the 1-Up item is not in
  the filler pool.
- Added the goal `defeat_omega_zero`: beat Omega Zero in N-1. The door of his arena opens with your `goal_requirements`
  (the rest of Area N is open as always); Slither Inc. stays closed and its checks are not in the game.
- Added `zero3_bosses` and `zero4_bosses`: the eight Mega Man Zero 3/4 bosses of N-1 are in the game from the start, no
  Game Pak needed, and each one beaten is a check. A beaten boss stays beaten, Mysterious Rock or not. They can be named in
  `boss_logic`; a name whose option is off is simply ignored.
  - IMPORTANT: each option needs your own Mega Man Zero 3 or Zero 4 (GBA) ROM, USA, Europe or Japan: the game keeps the
    sprites of those bosses in the cartridge, so the launcher asks for the ROM when you open the `.apmmzx` and converts
    them from it. With the option off no ROM is ever asked for.
- Added the goal requirement `Mutos Reploid Hunting`: beat `required_mutos_reploids` of those bosses (1 to 8; 5 or more
  need both games on). The pause menu, the "Goal" notice and `/mmzx_goal` count them like the other requirements.
- Added the location `Obtain Biometal Z`, sent when you beat Giro in D-2.
- Added `area_m_access`: what opens the seal at the entrance of Area M.
  - `open`: the seal is open from the start, as before.
  - `biometals`: get the five `Obtain Biometal` checks of your game (Z, H, F, L and P).
  - `passwords`: collect `required_passwords` Passwords out of the `total_passwords` in the pool.
  - With `biometals` or `passwords` the Transerver Access of Area M is not in the pool.
- Added `mission_objectives`: the objects and events of the story missions can be checks, and items too.
  - `locations_only`: the four Computer Chips, the four guardians of Pass The Test and their Stuffed Animal, the three Data Disks, the thirteen people trapped in Area G, the generator of E-3 and the lava control of K-1 are locations. The game plays as before.
  - `locations_and_items`: the same locations, plus the terminal of F-3 and the sprinkler key of G-2, and the objects are items of the pool. A mission is reported only with its object, Rayfly shows up only with a Computer Chip, the F-3 and G-2 doors open with their own items, the lava of Area K is slow only with its item and the machines of Area E stop only with theirs.
  - The Computer Chips and the Data Disks of J-5 and L-4 show the item they hold, like any other pickup.
- Missions can be played again: "Replay Missions" in the Transerver consoles lists the missions you have already reported (plus the quests, as before), and picking one brings back its objective and its boss.
  - While a mission picked there is under way, entering an area does not accept that area's mission; report or abort the one you picked to go back to normal.
  - "Abort Mission" is offered only for a mission or quest picked from that list. With the mission of an area under way the consoles show their normal menu instead, and picking a mission there replaces it.
  - Troop Reinforcement replays like any other mission: no briefing, head to Area D and play it through.
- Troop Reinforcement and Protect HQ show their names in that list instead of "Mission 4" and "Mission D".
- `mission_objectives` also covers the switch of K-4 that unlocks the door of K-1 on the way to its Sub Tank: stepping on it is a check, and with `locations_and_items` that door opens with the Area K Door Switch instead.
- `mission_objectives` also covers the bridge of D-1: with `locations_only` it starts raised and a shot at its switch lowers it; with `locations_and_items` the shot is only a check, and the bridge is down while you hold the Area D Bridge.
- Added "door constraints": each seed can lock some of the doors between rooms behind a Card Key, so the map opens in smaller steps instead of most of it at once. A locked door shows the colour of its key.
  - `door_constraints_min` and `door_constraints_max`: how many doors a seed locks (0 to 15, both 0 by default).
- Added `include_warps_in_logic`: the teleports to the Guardian Base at the end of Troop Reinforcement and Repel The Army count as a way into Area X, so a check there may expect you to clear one of those missions instead of holding its Transerver Access. Off by default: Area X stays in logic only with its Transerver Access or as your starting point.

- Universal Tracker explains the logic: `/explain <location>` says which models, Card Keys, Transerver Access, events or boss requirements a check or a door still needs, with your `boss_logic`, goal and door constraints spelled out for your seed.

### Changed

- Door constraints no longer lock the way between G-1 and G-2: that passage has no door frame, so the coloured gate
  looked out of place.
- The filler items are now `25 E-Crystals`, `50 E-Crystals`, `100 E-Crystals` and `1-Up`, the smaller amounts more
  often; before, every filler was 50 E-Crystals and the 1-Up never came up.
- The Transerver consoles show their normal menu during Troop Reinforcement and Protect HQ instead of the reduced one.
- Logic: the Sub Tank of K-1 asks for Model LX and that door unlocked, instead of four biometals.
- Logic: the apple of A-3 asks for any model, instead of Model FX, X or ZX.

### Fixed

- Logic: the hidden path of K-4 (the door switch, the 1-Up, Disk B-12 and the E-Crystal beside it) asks for a way
  into K-4 through its door from K-3, where the lava chase starts; with `mission_objectives: locations_and_items` and
  that door locked by a door constraint it was in logic from the Transerver of Area K, which never arms the chase.
- Stop The Dig stopped counting as completed after reporting Repel The Army.
- Find The Survivors stopped counting as completed after reporting Recover The Disk, and Fight The Mavericks after reporting Attack The Excavators: the Missions goal requirement lost them from its count, and their missions could be accepted again.

- The eight usable items of the pause menu (Cake, Orange, Candy, Bread, Apple, E Tank, W Tank and Smelling Salts) are items of the pool, and the eight places that hand them out are locations.
  - A usable you have used comes back when you open any Transerver console.
  - Being handed one shows no "You got" popup; the client's notice says what you found.
  - The child gives the cake on any day, once Save The People has brought him to C-1; Scombrésoce sells the salts once Troop Reinforcement is complete; Cédre and Scombrésoce stay in the base during Protect HQ.
  - Any attack shakes the tree of A-3 and its first fruit is the apple; any hit on the hanging doll of X-2 frees the W Tank.

## [0.2.1] - 2026-10-05

### Fixed

- Universal Tracker showed checks in logic that were not reachable yet when the YAML had random options, such as a random `starting_model` with `hu_in_pool`. It now reads the options of your seed from the server, so it should always be consistent.

### Changed

- As a bonus due to the changes on this fix, Universal Tracker no longer needs your YAML for this game.

## [0.2.0] - 2026-09-26

### Added

- Added "configurable goal requirements".
  - Goal Requirement "Biometals": Collect a specific ammount of models from the pool
  - Secret Disk: A macguffin style goal that requires collecting a specific ammount of secret disks from the pool.
  - Missions: Complete a chosen number of the 14 story missions.
- The STATUS tab of the pause menu shows the progress towards the goal requirements.
  - A `/mmzx_goal` has been added to the client as well, that prints the goal requirements and your progress.
- Added `progressive_models` as an option: each of the biometals H, F, L and P comes either as two halves (as before) or as one item that gives the whole model at once.
- Added `require_full_models`: the Biometals goal requirement can ask for both halves of a progressive model or just one of them.
- Added `skip_minibosses`: a QoL change so mini bosses can be skipped.
  - `after_first_defeat`: you have to beat them once. But reloading the area will not respawn them.
  - `always`: all of them count as beaten from the start, so their fights never start.

### Changed

- The item icons of the pickups are now part of the patched ROM instead of swapped by the client, so they show correctly even while the client is disconnected or not running.

### Fixed

- The trigger for "Protect HQ" was lost when another area's mission was started, and there was no way to re-trigger it. Entering Area X now resumes Protect HQ once four area missions are completed.
- Checks collected while the client was reconnecting to the server were not sent until collecting the next check. Now they send right after reconnecting.
- Reconnecting to the server no longer removes the Card Keys, the Life Up and Sub Tank capacity and the max HP for a moment.
- A pickup that holds a multiworld item can no longer be sliced into small pieces with a weapon.

## [0.1.0] - 2026-09-17

The first release of this project: Mega Man ZX (USA).
See the [game page](docs/en_Mega%20Man%20ZX.md) for what the randomizer does and the [setup guide](docs/setup_en.md) to get playing. 

[Unreleased]: https://github.com/Nekusen/Archipelago-MegaManZX/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Nekusen/Archipelago-MegaManZX/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Nekusen/Archipelago-MegaManZX/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Nekusen/Archipelago-MegaManZX/releases/tag/v0.1.0
