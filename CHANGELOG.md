# Changelog

## Unreleased

- ROM patching no longer uses ndspy (GPL-3). The ARM9 is split and repacked
  with [apnds](https://github.com/ljtpetersen/apnds) 0.2.5 (MIT) and
  compressed by an original BLZ encoder with optimal parsing; the patched
  ROM is byte-identical to the previous one. The `.apworld` is MIT
  throughout.
- The patcher no longer embeds any bytes of the game as guards: the two
  remaining ones (the Secret Disk tile and the pause-menu help text) are
  now SHA-256 digests.
- Everything the player sees is now in English: option descriptions (the
  YAML template), client log messages and command help, generation errors
  (`boss_logic`), patching errors and the DeathLink message.
- The client's diagnostic messages (auto-accepted missions, restored flags,
  model reverts, teleport bookkeeping) are hidden by default; `/mmzx_debug on`
  shows them.
- Repository split: the world now lives in its own repository, mounted as a
  submodule of the private development toolkit. Game-derived assets
  (tracker map images, in-game icon set) are no longer tracked; they are
  generated locally and will be replaced by clean-room equivalents.
- Added README, LICENSE (MIT), CREDITS, `archipelago.json`, `.apignore`.
- `tools/` now holds the logic editor, the logic validator and probe and the
  apworld packager; `test/` the logic tests.

## 0.2 (2026-09, private)

- Playable end to end on BizHawk: 274 locations, 45 items, hybrid Transerver
  network, event gates, progressive biometals, respawning pickups as
  optional checks, in-game item icons and notifications, pause-menu
  "Go to Transerver", `boss_logic`, `skip_boss_rush`, DeathLink, Universal
  Tracker map pack.
- Logic v0.3: drawn in the visual editor (`logic/logic.json`), levels
  normal / expert.
