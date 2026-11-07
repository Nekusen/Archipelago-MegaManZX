# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-11-08

### Added

- Added the goal `defeat_omega_zero`: beat Omega Zero in N-1. The door of his arena opens with your `goal_requirements`
  (the rest of Area N is open as always).
- Added `zero3_bosses` and `zero4_bosses`: the eight Mega Man Zero 3/4 bosses of N-1 are in the game and each one beaten
  is a check. They can be named in `boss_logic`
  - IMPORTANT: each option needs your own Mega Man Zero 3 or Zero 4 (GBA) ROM. The game keeps the
    sprites of those bosses in the cartridge, so the launcher asks for the ROM when you open the `.apmmzx` and converts
    them from it. With the option off no ROM is ever asked for.
- Added the goal requirement `Mutos Reploid Hunting`: beat `required_mutos_reploids` of those bosses (1 to 8; 5 or more
  need both games on).
- Added the location `Obtain Biometal Z`, sent when you beat Giro in D-2.
- Added `area_m_access`: what opens the seal at the entrance of Area M.
  - `open`: the seal is open from the start, as before.
  - `biometals`: get the five `Obtain Biometal` checks of your game (Z, H, F, L and P).
  - `passwords`: collect `required_passwords` Passwords out of the `total_passwords` in the pool.
  - With `biometals` or `passwords` the Transerver Access of Area M is not in the pool.
- Missions can be played again through the new "Replay Missions" option in the Transerver consoles.
  - While a mission picked there is under way, entering an area does not accept that area's mission. Report or abort the one you picked to go back to normal.
  - "Abort Mission" is now offered only for a mission picked from the "Replay Missions" list. 
  - Troop Reinforcement replays like any other mission. There's no briefing, head to Area D and play it through.
- Added `mission_objectives`: the objects and events of the story missions can be checks, and items too.
  - `locations_only`: Multiple events and items from the story become checks, like the four Computer Chips in area B, the guardians of Pass The Test or the people trapped in Area G. The game itself plays as before, nothing is changed in progression or how the open world behaves.
  - `locations_and_items`: the same location, but the objects are also items of the pool. A mission is reported only with its object, Rayfly shows up only with a Computer Chip, the F-3 and G-2 doors open with their own items, and so on.
- Added "door constraints": each seed can lock some of the doors between rooms behind a Card Key, so the map opens in smaller steps instead of most of it at once. A locked door shows the colour of its key.
  - `door_constraints_min` and `door_constraints_max`: how many doors a seed locks (0 to 15, both 0 by default).
- Added `include_warps_in_logic`: the teleports to the Guardian Base at the end of Troop Reinforcement and Repel The Army count as a way into Area X, so a check there may expect you to clear one of those missions instead of holding its Transerver Access. Off by default.
- The eight "Item A" usables in the game are now items of the pool, and the eight places that hand them out are locations.
  - Usable items get added to your inventory when you get them as items from the multiworld. Picking them in the game only sends a location.
  - A usable you have used comes back when you open any Transerver console, so you can use them as much as you want.
  - The child gives the cake location on any day, even if its not your birthday, once Save The People is completed.
- Added `sub_tank_refill_operator`: a Guardian next to your starting Transerver who, for 200 E-Crystals,
  refills every Sub Tank you hold.
- Added `infinite_lives`: when this option is on you lose no lifes and you can't Game Over. With it on, the 1-Up item is not in
  the filler pool.

### Changed

- The entire logic has been reworked to use AP's Rule Builder. This is mostly internal, but as an upside this means you can now use /get_logical_path or /explain in Universal Tracker.
- The filler item pool has been reworked: now there's `25 E-Crystals`, `50 E-Crystals`, `100 E-Crystals`, `Energy Refill`, `Weapon Energy Refill`
  and `1-Up`. The goal is to lower the total ammount of useless E-Crystals, as well as making filler feel at least slightly relevant.
- Some client messages have been modified so they only show in debug , as they are not relevant for the player usually.

### Fixed

- Small logic fixes and adjustments
- The following missions had their "cleared mission" flag removed by other events sometimes. This should be fixed now.
  - Stop The Dig stopped counting as completed after reporting Repel The Army.
  - Find The Survivors stopped counting as completed after reporting Recover The Disk
  - Fight The Mavericks after reporting Attack The Excavators

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
