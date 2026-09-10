# Credits and third-party notices

This world is original code (MIT, see `LICENSE`) built on the work below.
Nothing from the game itself is distributed: the patcher reads everything it
needs from the player's own ROM.

## Components shipped inside the `.apworld`

| Component | Author | License | Use |
|---|---|---|---|
| [ndspy](https://github.com/RoadrunnerWMC/ndspy) 4.2.0 (`ndspy/`, subset) | RoadrunnerWMC | GPL-3.0-or-later | Reading the ROM and (de)compressing the ARM9 at patch time. **Being replaced by apnds (MIT).** While it is present, the packaged `.apworld` as a whole is distributed under the terms of the GPL-3.0; see `ndspy/LICENSE`. |
| Archipelago logo sprites (`gfx/`, 3 icons) | The [Metroid: Zero Mission apworld](https://github.com/lilDavid/Archipelago-Metroid-Zero-Mission) (lil David and contributors) | MIT | In-game icon for items of other games (progression / useful / filler variants). |

Everything else in the package (patches, client, logic, data, tracker code)
was written for this project.

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
| [apnds](https://github.com/ljtpetersen/apnds) and the [Pokémon Platinum apworld](https://github.com/ljtpetersen/platinum_archipelago) | James Petersen | MIT | NDS ROM handling written for Archipelago; the template for a DS BizHawk client. |
| [py-desmume](https://github.com/SkyTemple/py-desmume) / DeSmuME, [Ghidra](https://github.com/NationalSecurityAgency/ghidra), [BizHawk](https://github.com/TASEmulators/BizHawk), [melonDS](https://melonds.kuribo64.net) | their authors | GPL / Apache-2.0 / MIT / GPL | Reverse-engineering bench and emulators. |
| [GBATek](https://problemkaputt.de/gbatek.htm) | Martin Korth | — | DS hardware and ROM format reference (linked, not reproduced). |
| RetroAchievements (game 9818), GameFAQs guides by Yeblos and snkupo, MMKB | their authors | — | Consulted for cross-checking; nothing reproduced. |

## Trademarks

Mega Man ZX is a trademark of Capcom Co., Ltd. This project is not affiliated
with, sponsored by or endorsed by Capcom or Inti Creates.
