# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Nekusen/Archipelago-MegaManZX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Nekusen/Archipelago-MegaManZX/releases/tag/v0.1.0
