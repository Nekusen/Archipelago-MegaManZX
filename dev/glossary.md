# Glossary

Terms this world uses in its code, data and documents, for a reader who has not played Mega Man
ZX. Game mechanics are described only as far as the randomizer relies on them.

- AP graphics set: the sprite set the patcher builds from the player's ROM plus the three
  Archipelago logos; the icon table picks one of its animations per pickup.
- arena: a region of the logic document tagged with a boss id. The boss's `boss_logic`
  requirement is added to every edge landing in it, so nothing inside is reachable without it.
- atom: the smallest unit of a requirement: an item (`HX`, `YELLOW`), a full biometal (`HX2`), a
  count (`LIFEUP>=2`, `MISSIONS>=4`), a mission event, `BOSS_<ID>`, or a macro (`ALL6`, `MODEL`).
- badge: an area's icon on the game's Transport map. Each badge is one "Transerver Access -
  Area X" item and the hub floor it unlocks.
- biometal, model: a transformable form. Model X, ZX, OX and the human form Hu are single items;
  HX, FX, LX and PX are progressive items whose two copies are the biometal's two halves.
- boss rush: the eight teleporters in the D-4 tower (the Slither Inc. tower) where the
  Pseudoroids are fought again before D-5. In the logic their doors lead to the generic room z02.
- Card Key: the game's coloured keys (Yellow, Green, Red, Blue, Purple), progression items whose
  bits the client owns. White exists in the game, is never obtainable and stays out of the pool.
- cave (code cave): a small Thumb routine the patcher places in an unused stretch of the ARM9
  and reaches through a redirected branch. See `rom_patches.md`.
- checkpoint commit: copying the live progress block to the canonical copy and the story block
  to its checkpoint copy, as the game does on a save pad.
- coords index: the position of an entity in its room's coordinate table; it identifies a
  pickup in the mailbox and in the icon table.
- curated door: a room connection the game has but the door table lacks, added by hand to
  `data.DOORS` (the hub floor corridors, the K-1 fall).
- Data Disk (Secret Disk): the game's collectable disks, series B, E, M and O; each one placed
  in the world is a check.
- detect recipe: the `detect` field of a location in `data.py`: how the client recognises the
  check in RAM (`bit`, `all`, `any`, `mailbox`).
- DNF: disjunctive normal form, the shape of a compiled requirement: a list of alternatives,
  each a list of atoms that must all hold. `[[]]` is free, `[]` impossible.
- event gate: a door or wall the game opens through a story flag. The client sets some of those
  flags for everyone and the Slither gate's when all six models are held.
- Field: the placeholder region for locations not yet placed in a room (unplaced missions and
  quests); their rule is reaching the rooms of their area label.
- force-accept: the client accepting a mission by writing what the console would: snapshot,
  start flag, state, story handler, extra bits and checkpoint commit.
- golden image: the save image of a fresh post-tutorial game, built per slot at generation
  (`rom/golden.py`) and baked into the ARM9 as an autoload section; the skip cave copies it into
  the LOAD buffer on New Game, which loads it and skips the tutorial.
- grant recipe: the `grant` field of an item in `data.py`: how the client gives it (`live_bit`,
  `progressive`, `transerver`, `lifeup`, `subtank`, `ecrystals`, `oneup`).
- half: one of the two copies of a progressive model item. One half makes the form usable; both
  complete the biometal (level-2 charge, larger Weapon Energy cap).
- hstate, story handler: the game's per-mission state machine, selected by the active mission
  id, that plays cutscenes and sets flags by rectangles; `hstate` is its initial state.
- hub, hub floor: the Guardian base Transerver room (z01). It stacks one floor per area, each
  with its console; teleports land on the floor's console pad. Standing on a floor sets that
  floor's Transport destination bit, as in vanilla.
- start point, starting Transerver: where a new game begins, one record of
  `data.STARTING_TRANSERVERS` chosen by `starting_transerver`: the spawn the golden image
  writes, the room the logic starts in and the one Transerver Access item granted at the
  start (`area_a` = floor A, `guardian_base` = floor X). Everything else about the start is
  derived from the record.
- hybrid network: the Transerver model of this world: moving on foot is always allowed, and only
  a warp leaving the hub requires the destination's access item.
- hybrid tracker: the Universal Tracker map mode where the layout ships in the world and the
  images come from the external tracker pack.
- landing: the point where an edge arrives in its destination room; with the exit in the source
  room it decides which two regions the edge joins.
- live vs canonical: the game keeps the progress block twice: the live copy it reads during play
  and the canonical copy the checkpoint restores on death and the save stores. Grants touch both.
- LOAD buffer: the RAM image the game's Continue path restores from; the golden image is written
  there. During gameplay it is the live scene buffer.
- mailbox (pickup mailbox): the counter and ring in free RAM where the patched game records each
  collected fixed refill, polled by the client.
- megamerge: the game's transformation event. Troop Reinforcement's megamerge flag gates the
  Giro scene in D-2.
- NOTIFY: the RAM mailbox and popup routine the client uses to show "Got" and "Sent" notices in
  the game's small popup.
- PALSHARE: the patch that makes the AP graphics set share the item set's palette instead of
  taking one of the fifteen object palettes.
- PICKUP_AP: the ROM-side check of the `present` bitmap of the icon table (which pickups of the
  room are unsent multiworld locations) that suppresses the vanilla effect of those pickups.
- Pseudoroid: one of the eight biometal bosses (Hivolt, Lurerre, Fistleo, Purprill, Hurricaune,
  Leganchor, Flammole, Protectos). Pairs share a biometal.
- requirement (REQ): what an edge or check demands, one DNF per tier:
  `{"normal": DNF, "expert": DNF}`.
- RETRY: the patch that re-applies a pickup's icon override every frame until the client's table
  is valid.
- return door (ret): a door synthesized in the opposite direction of a table entry, because the
  game's door table records one direction per pair.
- room code: `a01`, `e07`: area letter plus room number. Uppercase with a dash is the game's own
  label ("E-7").
- skip_boss_rush: option that marks each Pseudoroid pair as beaten in the boss rush as the player
  reaches its elevator stop, so D-4 is crossed without refights.
- subarea: the game's numeric room id; the client reads the stable copy of the current one. z01
  is 70 and z02 is 71.
- tier: a logic level, `normal` or `expert`. Cumulative: expert allows everything normal does
  plus its own alternatives.
- Transerver: the game's teleport and mission console. The network is the set of rooms with one;
  the hub is the one in the Guardian base.
- unstick: a client stage that repairs a state the open world can leave broken: the Troop
  unstick (Giro scene) and the ending unstick (credits after Serpent).
- WE (Weapon Energy): a model's special-attack energy. Its cap depends on the pair's victory
  levels, which the client sets for models granted by item.
- witness: in the tests, an item no rule uses, put into a `boss_logic` requirement to prove that
  the requirement reaches exactly the boss's arena.
- z01, z02: the two generic rooms: z01 is the hub, z02 the shared destination of the boss rush
  teleporters (no checks).
