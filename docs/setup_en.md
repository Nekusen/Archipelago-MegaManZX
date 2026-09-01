# Mega Man ZX — Multiworld Setup Guide

## Required software

- **Archipelago** 0.6.x (`ArchipelagoLauncher`).
- **BizHawk 2.9+** with the NDS (melonDS) core.
- Your own **Mega Man ZX (USA)** ROM (`ARZE`, MD5
  `88b684b1b3eea885a07625da89f1e5b3`). It is never distributed.

## One-time setup

1. Put the world in Archipelago: copy `mmzx.apworld` into
   `custom_worlds/` (or double-click it).
2. First run asks for your ROM (Settings → Mega Man ZX ROM File).
3. In BizHawk: **Config → Customize → Advanced → turn AutoSaveRAM OFF**
   (so NDS saves work), and make sure the NDS core is melonDS.

## Generating and playing

1. Create a YAML (`ArchipelagoLauncher` → Generate Template Options →
   Mega Man ZX) and set your options (character, goal, DeathLink…).
2. Generate the multiworld. You get an `AP_*_P#_<name>.apmmzx` patch.
3. Open the `.apmmzx` with the Archipelago launcher → it produces a
   patched `.nds` and launches the **BizHawk Client**.
4. Open the patched `.nds` in BizHawk. The client auto-connects to the
   emulator; enter the server address and connect.

## Notes for v0.1

- **No logic**: every check is reachable in whatever order — use the
  client's fast-travel if you get stuck.
- The client detects checks and grants items by reading/writing RAM
  directly (no in-ROM item placement). Received items (biometals, card
  keys, life ups…) are re-applied each session automatically.
- Goal: defeat Serpent.
