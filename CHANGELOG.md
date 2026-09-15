# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). There is no numbered release yet; the first public build
will be 0.1.0.

## [Unreleased]

### Added

- Mega Man ZX (USA) as an open world for Archipelago, played on BizHawk with the melonDS core.
- 120 locations: the 95 Secret Disks, the Life Ups and Sub Tanks of the world, the four biometals and 14 missions.
- Disk E-47, the one hanging from a balloon in H-1, is a location too, and its pickup is drawn as the item it holds like any other.
- Optional locations for the 133 refill pickups of the levels (1-Ups, energy, weapon energy, E-Crystals); the first pickup sends the check and the object keeps respawning.
- 45 items: Model X, ZX and OX, progressive Model HX, FX, LX and PX (two halves each), the five Card Keys, Transerver Access for 13 areas, four Life Ups, four Sub Tanks and the eight ITEM B chips; E-Crystals and 1-Ups as filler.
- Tutorial skip: New Game starts in the Guardian hub with the model and character of the YAML, on Normal difficulty.
- Missions accepted automatically on entering their area, so they can be done in any order.
- Hybrid Transerver network: every area can be reached on foot; a warp from the hub needs the area's Transerver Access item.
- Options: `starting_model` (Model ZX by default), `character`, `hu_in_pool`, `boss_logic`, `skip_boss_rush`, the four `pickup_checks_*` toggles, `notify_received`, `notify_sent`, `notify_style`, `death_link`.
- Per-boss logic requirements written in the YAML (`boss_logic`), with generation failing early on a requirement the pool cannot meet.
- Boss rush skip (`skip_boss_rush`): the D-4 tower marks each Pseudoroid pair as beaten as the elevator reaches it.
- Every pickup in the world is drawn as the item it holds, with the game's own icons for Life Ups, Sub Tanks, chips, biometals and Card Keys and the Archipelago logo for the rest; `/mmzx_icons` toggles it.
- Pickups that hold a multiworld item play the disk chime and have no vanilla effect.
- On-screen notifications for received and sent items in the game's popup, filtered by item class and shown in full or as one line; `/mmzx_notify` changes them in game.
- "Go to Transerver" on the MISSION tab of the pause menu (Y), opening the game's own Target Area list.
- Every story cutscene can be skipped with START on first viewing.
- The DATA SELECT screen shows the biometals owned through items.
- The Secret Disk sprite shows the Archipelago logo.
- DeathLink, sending and receiving.
- Universal Tracker map tab: the game's world map, one map per area and per room, auto-tab and player position; the images come from the external [MegaManZX-Tracker](https://github.com/Nekusen/MegaManZX-Tracker) pack (`ut_pack_path`).
- Client commands `/mmzx_teleport`, `/mmzx_where`, `/mmzx_accept`, `/mmzx_start`, `/mmzx_notify`, `/mmzx_icons` and `/mmzx_debug`.
- The client refuses a ROM patched by a different version of this apworld and says which version to use.
- The slot name is stored in the patched ROM, so the client logs in without asking for it.
- Guards for two crashes of the original game that the open world makes reachable (a sprite loop after a teleport into a boss area, a room running out of sprite palettes).

### Changed

- Source layout: the ROM patch lives in `rom/` (one module per domain), the logic document and its rules in `logic/`, the Universal Tracker callbacks in `tracker/`, and the starting save image and boss rush helpers in `client/`.
- The tracker map images left the `.apworld` for the external pack; the world drops from 11 MB to under 1 MB.
- The overall map is the game's own world map from the MISSION tab; missions and biometals sit on their boss's room.
- The in-game icon set and the Secret Disk tile are built from the player's own ROM at patch time; only the three Archipelago logos ship with the world. Sub Tank and Card Key icons are the game's actual sprites.
- ROM patching uses [apnds](https://github.com/ljtpetersen/apnds) (MIT) and an original BLZ compressor instead of ndspy, so the `.apworld` is MIT throughout; the patched ROM is unchanged.
- The patcher recognises the vanilla bytes it replaces by hash instead of storing them.
- The client's diagnostic messages are hidden by default; `/mmzx_debug on` shows them.
- `hu_in_pool` is ignored when `starting_model` is `none` instead of failing generation, so a random starting model can include `none`.

### Fixed

- The ending now starts after Serpent falls even when the game would have stayed on a white screen.
- Weapon Energy of a biometal received as an item starts full instead of empty.
- Accepting Troop Reinforcement in the open world sets the mission up completely at once, instead of the client repairing it over the next few seconds.
- DeathLink sends the player's deaths; the check only ran while the player was alive, so a death was never seen.
- A DeathLink received in human form no longer freezes the game.
- Leaving a boss fight by teleport (Go to Transerver, `/mmzx_teleport`) no longer leaves every door in the game locked until Abort Mission; the fight starts over on the next visit.
- The ladder in D-3 up to the walkway of the Area O door is always lowered, so Area O can be reached before Repel The Army is accepted.
- Teleports keep the area's temporary flags, such as the lava flow setting of Area K; the first door crossed after a teleport used to reset them.
- A dropped BizHawk connection abandons the current tick and the next one retries, instead of stopping the client.
- The Operator no longer announces and hands out the Yellow Card Key at the Transervers without Transport (Area C and the DATA floors of H-4 and J-1).
- Save The People can be finished when Area I is entered from the Transerver pad of I-3: the cell scene now plays once Hurricaune is beaten.
- Pass The Test sends its check when it is reported before Locate Giro; it used to wait for Giro, and in the meantime the mission was accepted again on every visit to Area C.
- Completing Locate Giro and Pass The Test no longer unlocks the Transport to Area X-1 outside its Transerver Access item.
- With `hu_in_pool`, walking from I-5 into I-2 no longer hands out the human form before its item arrives.
- Talking to the townspeople of C-1 and C-2 in human form, or to the Guardian test NPC of C-1, no longer hands out halves of Model HX, FX, LX or PX; the models are owned through bits the game never touches, and the DATA SELECT icons follow them.
- Troop Reinforcement stays completed after reporting Search The Plant, Find The Survivors, Fight The Mavericks or Secure The Biometal; the client no longer offers it again on entering D-2.
