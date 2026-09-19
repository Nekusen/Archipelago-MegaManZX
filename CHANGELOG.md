# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Configurable goal requirements. `goal_requirements` lists what opens the gate to Slither Inc.: `Biometals`
  (the models of `required_models`, all of them or any `required_models_count`) and/or `Secret Disks`, a hunt for
  `required_secret_disks` of the `total_secret_disks` shuffled into the multiworld. The default is the six main
  models, as before; the list cannot be empty.
- Secret Disk goal items. Each one received lights up an entry of Fleuve's database, in an order picked by the seed;
  the popup announces them with their count, and a notice tells you when the gate opens.
- The STATUS tab of the pause menu shows the progress towards the goal requirements.
- `/mmzx_goal` prints the goal requirements and your progress in the client.
- The `Goal` group on the options page.

### Changed

- The disks found in the world no longer count as Secret Disks in Fleuve's database: they are checks like any other.
  A disk collected by the server (`!collect`) now disappears from the world.
- The ROM must be created again from the `.apmmzx` with this version.

## [0.1.0] - 2026-09-17

The first release of this project: Mega Man ZX (USA).
See the [game page](docs/en_Mega%20Man%20ZX.md) for what the randomizer does and the [setup guide](docs/setup_en.md) to get playing. 

[Unreleased]: https://github.com/Nekusen/Archipelago-MegaManZX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Nekusen/Archipelago-MegaManZX/releases/tag/v0.1.0
