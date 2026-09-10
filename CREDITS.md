# Credits and third-party notices

This world is original code (MIT, see `LICENSE`) built on the work below.
Nothing from the game itself is distributed: the patcher reads everything it
needs from the player's own ROM.

## Components shipped inside the `.apworld`

| Component | Author | License | Use |
|---|---|---|---|
| [apnds](https://github.com/ljtpetersen/apnds) 0.2.5 (`apnds/`, unmodified) | James Petersen | MIT | Splitting the ARM9 into its autoload sections and writing its start parameters back at patch time; its decoder is the reference for our BLZ encoder. See `apnds/LICENSE`. |
| Archipelago logo sprites (`gfx/`, 3 icons) | The [Metroid: Zero Mission apworld](https://github.com/lilDavid/Archipelago-Metroid-Zero-Mission) (lil David and contributors) | MIT | In-game icon for items of other games (progression / useful / filler variants). |

Everything else in the package (patches, the BLZ code compressor, client,
logic, data, tracker code) was written for this project.

## Archipelago

[Archipelago](https://github.com/ArchipelagoMW/Archipelago) (MIT) — the
multiworld framework, the `BizHawkClient` base and `worlds/_bizhawk`, the
`APProcedurePatch` machinery and the BizHawk Lua connector.

## Knowledge and tools used during development (not distributed)

| Resource | Author | License / terms | What it gave us |
|---|---|---|---|
| [Mega Man ZX Editor](https://github.com/AlaryVanEeckhout/Mega_Man_ZX_Editor) and its wiki | AlaryVanEeckhout | GPL-3.0 | Level layout and entity format (inherited from the rmz3 decomp), RAM/ROM map of the USA version, entity nomenclature, headless room renders for the logic editor. Used as an external tool; not vendored. |
| [MMZX_Adjustments_Lua](https://github.com/GameDJ/MMZX_Adjustments_Lua) | GameDJ / Meta_X | — | Many RAM addresses of the USA version (via the editor's wiki). |
| Action Replay codes on [gamehacking.org](https://gamehacking.org/game/24982) and Neoseeker | Dybbles, nolberto82, Helder, VisitntX and others | — | Starting addresses and the location of several ARM9 routines (pickups, damage, NPC checks). |
| [The Cutting Room Floor](https://tcrf.net/Mega_Man_ZX) | TCRF contributors | CC BY 3.0 | Debug room, unused White Card Key, Model O notes. |
| [Prof9 / MMZX-Slot2-Patch](https://github.com/Prof9/MMZX-Slot2-Patch) | Prof9 | Unlicense | Reference for hooking this game's ARM9. |
| [Pokémon Platinum apworld](https://github.com/ljtpetersen/platinum_archipelago) | James Petersen | MIT | The template for a DS BizHawk client and for shipping an NDS library inside an apworld. |
| [py-desmume](https://github.com/SkyTemple/py-desmume) / DeSmuME, [Ghidra](https://github.com/NationalSecurityAgency/ghidra), [BizHawk](https://github.com/TASEmulators/BizHawk), [melonDS](https://melonds.kuribo64.net) | their authors | GPL / Apache-2.0 / MIT / GPL | Reverse-engineering bench and emulators. |
| [GBATek](https://problemkaputt.de/gbatek.htm) | Martin Korth | — | DS hardware and ROM format reference (linked, not reproduced). |
| RetroAchievements (game 9818), GameFAQs guides by Yeblos and snkupo, MMKB | their authors | — | Consulted for cross-checking; nothing reproduced. |

## Trademarks

Mega Man ZX is a trademark of Capcom Co., Ltd. This project is not affiliated
with, sponsored by or endorsed by Capcom or Inti Creates.
