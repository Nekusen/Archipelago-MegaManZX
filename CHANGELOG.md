# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added "configurable goal requirements".
  - Goal Requirement "Biometals": Collect a specific ammount of models from the pool
  - Secret Disk: A macguffin style goal that requires collecting a specific ammount of secret disks from the pool.
- The STATUS tab of the pause menu shows the progress towards the goal requirements.
  - A `/mmzx_goal` has been added that prints the goal requirements and your progress in the client as well.

### Changed

- The disks found in the world no longer count as Secret Disks in Fleuve's database. Fleuve's database now uses the Secret Disks obtained from the multiworld.

## [0.1.0] - 2026-09-17

The first release of this project: Mega Man ZX (USA).
See the [game page](docs/en_Mega%20Man%20ZX.md) for what the randomizer does and the [setup guide](docs/setup_en.md) to get playing. 

[Unreleased]: https://github.com/Nekusen/Archipelago-MegaManZX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Nekusen/Archipelago-MegaManZX/releases/tag/v0.1.0
