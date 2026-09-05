# Mega Man ZX — Multiworld Setup Guide

## Required software

- **Archipelago** 0.6.x (`ArchipelagoLauncher`).
- **BizHawk 2.9+** with the NDS (melonDS) core.
- Your own **Mega Man ZX (USA)** ROM (`ARZE`). It is never distributed.
- Optional: **Universal Tracker** (the world ships an embedded map pack:
  overall map with a counter per room (missions/biometals/quests on each
  area badge), one map per area and one per room,
  auto-tab and a player position icon).

## One-time setup

1. Copy `mmzx.apworld` into `custom_worlds/` (or double-click it).
2. First run asks for your ROM (Settings → Mega Man ZX ROM File).
3. In BizHawk: **Config → Customize → Advanced → turn AutoSaveRAM OFF**
   and make sure the NDS core is melonDS.

## Generating and playing

1. Create a YAML (Launcher → Generate Template Options → Mega Man ZX).
2. Generate. You get an `AP_*_P#_<name>.apmmzx` patch.
3. Open the `.apmmzx` with the launcher: it builds the patched `.nds` and
   opens the **BizHawk Client**. Load the `.nds` in BizHawk and connect.
4. Start a **New Game**: the tutorial is skipped. You appear in the Guardian
   Transerver hub with your starting model, on Normal difficulty.

## Options

- `starting_model` (Model X / none / ZX / HX / FX / LX / PX / OX / Hu) and
  `character` (Vent / Aile).
- `mission_auto_accept` (default on): missions are accepted automatically
  when you enter their area (or approach a boss floor door in the hub), so
  they can be done in any order. Turning it off is not supported by the
  logic.
- `boss_logic`: per-boss difficulty, your call. For each story boss you can
  state what you must be carrying before the *logic* considers you able to
  beat it, so the seed never requires you to fight something you consider
  too hard for your current gear. It only restricts logic — in game you may
  fight whatever you like with whatever you have.

  ```yaml
  boss_logic:
    Hivolt: "HX & Life Up x2"          # one half of Biometal H, 2 Life Ups
    Flammole: "Model FX (full) & Absorber Chip"   # both halves + a chip
    Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
    Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
  ```

  Bosses: Rayfly (B-2), Model Z (D-2), Hivolt (E-7), Lurerre (F-5),
  Fistleo (G-5), Purprill (H-4), Hurricaune (I-3), Leganchor (J-5),
  Flammole (K-4), Protectos (L-4), Prometheus (X-3), Pandora (M-3),
  Prometheus & Pandora (O-2), Serpent (D-5), Omega Zero (N-1). The room code
  ("E-7") works as a key too. Anything you leave out asks for nothing.

  Requirements can name models (`X ZX HX FX LX PX OX`; `HX2` or
  `Model HX (full)` means both halves of the progressive item, i.e. the
  level-2 charge), `MODEL` (any), `ALL6`, `Life Up xN`, `Sub Tank xN`,
  ITEM B chips by name, and Card Keys, combined with `&`, `|` and
  parentheses. A required Life Up / Sub Tank / chip is promoted to
  progression automatically. The eight Pseudoroids are fought twice — their
  own area and the boss rush in the D-4 tower, which the game makes you clear
  before it lets you through to D-5 — and the requirement applies to both, so
  reaching Serpent means being able to handle all eight.
- `hu_in_pool`: human form becomes an item (experimental).
- `submission_checks` (quests), `level4_victories`.
- `pickup_checks_1up` / `_energy` / `_weapon` / `_crystals` (default off):
  the 133 fixed refill pickups become checks (first pickup sends the check;
  the pickup keeps respawning and healing).
- `notify_received` / `notify_sent` (default `useful`): which item classes
  pop up on screen (the game's small non-blocking message) when you receive
  an item / when one of your checks sends an item to another player: `off`,
  `progression`, `useful` (progression + useful), `all` (also filler such as
  E-Crystals and 1-Ups). Change it mid-game with `/mmzx_notify`.
- `death_link`, `goal` (defeat Serpent).

## How it works (what to expect)

- **Transerver network**: each area has a "Transerver Access - Area X" item
  that unlocks that destination in the in-game Transport list; you can
  also reach areas on foot. With a single destination the console shows
  no Transport option (that is vanilla behaviour).
- **Biometals** come only from items, named after the form they unlock
  (`Model X`, `Model ZX`, `Model OX`, and the progressive `Progressive
  Model HX/FX/LX/PX`: the first copy gives you the form, the second copy
  is the biometal's other half and unlocks the level-2 charged attack, e.g.
  HX's hurricane, plus the full Weapon Energy bar); beating either
  Pseudoroid of a pair is the "Obtain Biometal" check. Weapon Energy is
  initialised when you receive a model. The client
  enforces ownership: a form you have not received is reverted and removed
  from the model menu, so if you ever see a model you do not own, it goes
  away on the next client tick.
- **Life Ups / Sub Tanks / Data Disks** are checks; the items give the
  capacity. Card Keys and Transerver Access are progression.
- **ITEM B chips** (Absorber, Featherweight, Extender, Quick Charger, Ice
  Boots, Wind Boots, Frog, Eraser) are useful items: when received they
  appear in the ITEM B tab of the pause menu, where you activate them.
  The NPCs and quests that give them in vanilla still do.
- **Go to Transerver (in-game option)**: open the pause menu (START), go
  to the **MISSION** tab (the area map, L/R to switch tabs) and press **Y**
  ("Y Button: Go to Transerver" is shown under the map). The menu closes
  and the game's own **Target Area** list opens, with every Transerver you
  have unlocked (by item or by having reached it); pick one and you arrive
  on that area's floor of the Guardian hub, exactly like the console's
  Transport. B cancels. The `/mmzx_teleport` command still works from the client.
- **Goal**: with all six models the Slither Inc. gate in D-2 opens (press
  Up); defeat Serpent in D-5.
- Some story gates are opened automatically (F-3, G-2, the M-1 seal, the
  D-1 bridge, and the sand fall that hides the pit from K-1 to K-2). Troop
  Reinforcement runs from D-1/D-2/D-3 without the base cutscene. Protect HQ
  starts by itself when you report a mission with at least four of the
  eight area missions (E-7 … L-4) completed.

## Client commands

- `/mmzx_teleport` (to the hub), `/mmzx_teleport K` (hub floor of area K),
  `/mmzx_teleport <subarea> <x> <y>`: anti-softlock fast travel.
- `/mmzx_accept`: force-accept the mission of the current area / hub floor.
- `/mmzx_where`: log your position and state (for bug reports).
- `/mmzx_start`: re-apply the YAML starting state.
- `/mmzx_notify all` (or `off` / `progression` / `useful`): which item
  classes are announced on screen, for received and sent items at once;
  `/mmzx_notify received all` / `/mmzx_notify sent off` set one side only.
  With no arguments it prints the current setting. The starting value comes
  from the YAML (`notify_received` / `notify_sent`) and the command does
  not persist across client sessions.
- `/mmzx_icons on|off`: draw every pickup in the world (Secret Disks, Life
  Ups, Sub Tanks and the optional respawning pickups) as the item it holds:
  Life Up, Sub Tank, chips, biometal badges and Card Keys use their own
  in-game icons; everything else shows the Archipelago logo, coloured by
  class (arrow = progression, cross = useful, grey = filler). Items are
  revealed as the client scouts them; a respawning pickup whose check was
  already sent shows its normal appearance again. Default: on.
