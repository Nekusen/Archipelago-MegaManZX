# Logic format

The access logic of this world is not written in Python. The logic author draws it in the visual editor under
`tools/logic_editor/`, room by room, on a render of each room. The editor writes `logic/logic.json`, the single source
of truth, and exports `logic/logic.txt`, a readable twin meant for review and diffs. Neither file is edited by hand.

Four modules consume the document. `logic_format.py` is the shared core: atoms, requirement parsing, region membership
of every node, validation and the text export. It imports nothing from Archipelago, so the editor and the command-line
tools load it on their own. `logic.py` holds what is not drawn: the door table, the key rule, the Transerver rule, the
area-label rule and the starting room. `regions.py` turns the document into Archipelago regions, entrances, locations
and events, and `bosses.py` adds the per-boss requirements from the player's YAML. Behind all of this is `data.py`, a
generated table of locations, doors and room ids.

## Model

The model follows Randovania's structure of rooms, nodes and regions, with requirements written as text in the
style of the Ori randomizer; nothing is shared with either beyond the idea.

A room is identified by a three-character code: the area letter and a two-digit number, as in `a01` or `k04`. The
Guardian base is area `x`. Two codes are synthetic: `z01` is the Hub, the single room that stands for the whole
Transerver network with its floors stacked vertically, and `z02` is Hub-2, the generic arena reached from the D-4 boss
rush teleporters. The room set is derived from the door table, and every room maps to a game subarea. Labels shown to
humans are `A-1`, `Hub` and `Hub-2`.

Each room has a set of regions. The region `main` always exists and has no polygon: it is everything not covered by a
drawn polygon. Every other region is a polygon drawn on the room render, in pixel coordinates, with a display name, a
color and a note. Region ids are slugs unique within the room. The Archipelago region name is the room code for `main`
and `room/rid` otherwise, for example `e07/boss-room`.

Regions hold nodes. A node is a check, the exit point of an edge, or the landing point of an edge, named `<edge>@in`.
A node belongs to the smallest polygon that contains its point, or to `main` if none does; the logic author can pin a
node to another region through `rooms[room].members`. Connections are the drawn part of the graph: directed
region-to-region edges inside a room, each direction with its own requirement.

Edges between rooms come from the door table and are not editable. Each entry carries a stable name, source and
destination room, a kind, an optional key item, an optional event-gate flag and both endpoint positions. The kinds are
`door` for a physical door between rooms, `internal` for a door inside the same room, `warp` for a Transerver pad that
leads into the Hub, `save` for a save-only pad that creates no transition, and `curated` for a seam that the game's
door table does not record. Curated edges are the two falls of area K and the floor corridors that join the pad rooms
of one Hub floor.

The game's door table records one direction per door, so every door has a synthesized return door, marked `ret`, at
the landing point of the forward door; a polygon that contains a landing therefore contains its return door too. An
internal door only creates a transition when its exit and landing fall in different regions.

The document can add two things to an edge: hand-placed endpoint positions, for edges whose table entry has none, and
an extra cost, the requirement to use the edge from its exit region. Its key, its event gate and the entry requirement
of the destination room are applied by the world on their own.

Checks are placed by position. Locations with a position in the data are placed automatically; missions, quests and
biometals have none and are placed by hand in `placed`, as a room and a point. A biometal is obtained from either of
two bosses, so its entry is a list of two placements and any of them counts. A check can carry a requirement of its
own, the condition to obtain it once inside its region.

A location that is neither positioned nor placed falls back to the area label of its data entry. `B-1B-2` means
reaching both rooms, `E-7/I-3` means reaching either, and a bare letter such as `F` means every room of that area. The
rule tests the `main` region of each room, so an unplaced location does not see drawn regions.

Event gates are doors that the game opens through a story flag. The document lists them by flag number under `gates`,
each with a requirement or none. A gate with no requirement is open in the logic; the client opens it in the game.
Rooms, regions, connections, edges, checks and gates all accept a free-text note, carried into `logic.txt` as a
trailing comment.

Region names follow a convention that keeps `logic.txt` readable; `tools/logic_editor/normalize_names.py` rewrites
names and ids to it without touching the logic. Names are Title Case and write room codes with a dash (`A-2`).

| name | region |
|---|---|
| `<Room> Entrance` | a region whose doors to other rooms all lead to that room |
| `Hub Entrance` | the region with the Transerver pad, the warp into the Hub |
| `Save Pad` | the region with a save-only pad |
| `Boss Room`, `Mini-Boss Room`, `Before Boss Room`, `After Boss Room` | around a fight |
| `Middle Area` | the passage between entrances |
| `Upper Area`, `Lower Area`, `Left Area`, `Right Area`, and combinations such as `Upper Right Area` | zones by position |
| `Nth Floor`, `Nth Floor Room`, `Nth Floor Room (Outside)`, `Basement Room` | levels of a vertical room |

When two regions of a room would get the same name, each keeps its original name in parentheses, as in
`E-4 Entrance (Bottom Area)`; `A-2 Entrance` and `A-2 Entrance (Top Part)` count as the same name for this purpose,
and a trailing `Entrance` is dropped from the part in parentheses. A room that must be crossed with a given model gets
one entrance region per door plus a middle region, with the requirement on the connections into the middle; `main` is
then empty and unconnected on purpose, and the rule survives if doors are ever shuffled.

```json
{
  "format": 1,
  "tiers": ["normal", "expert"],
  "rooms": {
    "e07": {
      "req": null,
      "note": "",
      "regions": {
        "main": {"name": "Main", "poly": null, "color": "#8ab4f8", "note": ""},
        "boss-room": {"name": "Boss Room", "poly": [[880, 560], [1520, 560], [1520, 900], [880, 900]],
                      "color": "#81c995", "note": "", "boss": "hivolt"}
      },
      "conns": [{"from": "main", "to": "boss-room", "req": {"normal": [["MODEL"]]}, "unsure": false, "note": ""}],
      "members": {}
    }
  },
  "placed": {"Mission - Search The Plant": {"room": "e07", "pos": [1180, 705]},
             "Obtain Biometal H": [{"room": "e07", "pos": [976, 705]}, {"room": "i03", "pos": [1428, 832]}]},
  "edges": {"e07 door (1760,720)": {"pos": null, "dst_pos": null, "req": {"normal": [["SEARCH_THE_PLANT"]]},
                                    "unsure": false, "note": ""}},
  "checks": {"A-1: Disk O-9": {"req": {"normal": [["HU"]]}, "unsure": false, "note": ""}},
  "gates": {"225": {"req": {"normal": [["ALL6"]]}, "note": ""}, "381": {"req": null, "note": ""}}
}
```

Keys of `edges` are door names from the data, keys of `checks` and `placed` are location names, and keys of `gates`
are flag numbers as decimal strings. The file is saved with sorted keys and one-space indentation. Loading fills in
the missing keys of a partial document, ensures every room has a `main` region, and migrates retired edge names and
boss ids. The retired edge names belong to curated edges that had no position of their own and were replaced by the
synthesized return door of the door they mirrored; a document saved with the old names is mapped to the new ones on
load.

## Requirements

A requirement is an object with one entry per tier. Each entry is a list of alternatives, and each alternative is a
list of atoms. Alternatives are combined with OR, the atoms of an alternative with AND. An empty alternative means
free, and an empty list of alternatives means impossible. Where the document allows it, `null` also means free: room
entry, edge cost, check and gate. A connection must always carry a requirement.

```json
{"normal": [["HX", "LX"]], "expert": [["FX"]]}
```

Tiers are cumulative. At `normal` the example needs `HX` and `LX`. At `expert` the alternatives of both tiers apply,
so `FX` alone is enough as well. A tier that is absent contributes nothing. The player picks the tier with the
`logic_difficulty` option.

The editor and the boss YAML also accept requirements as text. The parser takes atoms joined by `&`, `and`, `+` or `,`
for AND and by `|` or `or` for OR, with parentheses for grouping. `TRUE`, `ANY` and `FREE` stand for free; `FALSE`,
`NEVER` and `IMPOSSIBLE` for impossible. Atoms are case-insensitive and ignore spaces. The result is normalized:
duplicate atoms and alternatives are dropped, and an alternative that contains another one is redundant and removed.

Connections, checks and edge costs carry an `unsure` flag for rules not yet confirmed in the game. It has no effect on
generation; the text twin marks it with `?` and the validator counts it.

| Atom | Satisfied by |
|---|---|
| `HU` | Human form. Always true, unless `hu_in_pool` is on; then the item Model Hu. |
| `X`, `ZX`, `OX` | The items Model X, Model ZX, Model OX. |
| `HX`, `FX`, `LX`, `PX` | One copy of the progressive item, that is one half of the biometal. |
| `HX2`, `FX2`, `LX2`, `PX2` | Two copies: the full biometal, which unlocks the level 2 charged attack, for example HX's hurricane that raises the Life Up platform of I-5. |
| `MODEL` | Any of the seven models other than Hu. |
| `ALL6` | `X`, `ZX`, `HX`, `FX`, `LX` and `PX` together. |
| `YELLOW`, `GREEN`, `RED`, `BLUE`, `PURPLE` | The matching Card Key. |
| `WHITE` | White Card Key. It is not in the pool, so the atom is never met and the validator warns. |
| `LIFEUP>=n`, `SUBTANK>=n` | At least n copies of Life Up or Sub Tank, n from 1 to 4. |
| `LOCATE_GIRO` ... `DESTROY_MODEL_W` | The event `Cleared: <Mission>` of one of the 15 missions. |
| `MISSIONS>=n` | At least n of the 8 area missions cleared, n from 1 to 8. The game counts reported missions, not merely completed ones, and launches Protect HQ on the Report that brings the count to 4. |
| `ACCESS_<A>` | The item `Transerver Access - Area <A>`, for areas A B C D E F G I K L M O X. |
| `CHIP_<NAME>` | One of the 8 ITEM B chips, for example `CHIP_ABSORBER` for Absorber Chip. |
| `BOSS_<ID>` | The player's requirement for that boss from `boss_logic`. Free when the YAML sets none. |

The area missions counted by `MISSIONS>=n` are Search The Plant, Find The Survivors, Fight The Mavericks, Secure The
Biometal, Save The People, Recover The Disk, Attack The Excavators and Protect The Lab.

Life Up, Sub Tank and the chips are useful items in the data. When any requirement uses them, in the document or in a
boss YAML, the world creates them as progression instead, because Archipelago only tracks progression items in its
state. When a requirement is compiled, an atom that resolves to nothing is dropped from its alternative: `HU` without
`hu_in_pool`, or a `BOSS_*` atom with no YAML requirement. An alternative left empty by that makes the whole
requirement free.

## How the logic is evaluated

`regions.py` creates one Archipelago region per document region, plus `Menu` and `Field`. `Menu` connects to the
`main` region of the starting room, chosen by the `starting_transerver` option, with that room's entry requirement.
`Menu` also connects freely to `Field`, which holds the locations that are not tied to a region.

Every drawn connection becomes an entrance with its requirement. Every door table entry except the `save` kind becomes
an entrance from the region of its exit to the region of its landing; an internal door whose ends share a region is
skipped. Its rule is the AND of the key item, the entry requirement of the destination room when the door changes
room, the extra cost from `edges`, the Transerver rule, the requirement of its event gate and the arena rule of the
landing region. Entrances are named after the door, a stable identifier of the physical door rather than of its
destination, so entrance randomization could later be built on the same document.

The Transerver rule applies only to `warp` edges that leave the Hub. Warping to a room requires the
`Transerver Access` item of that room's Hub floor, as listed in the data; a floor with no Transport destination
cannot be warped to at all. Stepping on a pad to enter the Hub is free, and walking between rooms through doors and
floor corridors never touches this rule.

Active locations are placed in the region of their point, with the check requirement as access rule. A location with
two placements goes to `Field` with the rule "reach either region", and one with no placement goes to `Field` with the
area-label rule. Every mission also produces an event `Cleared: <Mission>` in the same region and with the same
rule as the mission's location, whether or not that location is an active check; the mission atoms test these events.

The goal is the event `Victory` on the location `Defeat Serpent`, held in `Field`. Its rule is reaching the
placement of `Mission - Destroy Model W`, that mission's own check requirement, and `ALL6`. The
game itself does not need the six biometals to reach Serpent; `ALL6` is a design requirement standing in for the
vanilla seal.

### Boss difficulty

The requirement to beat a boss does not live in the document. The player writes it in the `boss_logic` option, and the
world injects it when compiling; the document only anchors where each boss is fought. It is a logic-only restriction:
in the game the player fights with whatever they have, but the seed never forces them through a boss they are not
equipped for by their own standard.

The preferred anchor is the `boss` tag on a region, its arena. The world ANDs the boss requirement into every entrance
that lands in that region: connections, doors, warps and internal doors. Nothing inside the arena can be entered,
crossed or collected without meeting it. One boss has exactly one arena. The other anchor is a `BOSS_<ID>` atom
written into a requirement, used where the fight is not a region of its own.

The roster has fifteen bosses: Rayfly B-2, Model Z D-2, the eight Pseudoroids Hivolt E-7, Lurerre F-5, Fistleo G-5,
Purprill H-4, Hurricaune I-3, Leganchor J-5, Flammole K-4 and Protectos L-4, then Prometheus X-3, Pandora M-3,
Prometheus & Pandora O-2, Serpent D-5 and Omega Zero N-1. Giga Aspis, the tutorial boss, is not listed because the
randomizer skips the tutorial.

A YAML key names a boss by display name, id, room code or room label, compared without case, spaces or punctuation:
`Hivolt`, `hivolt`, `e07` and `E-7` are the same key. A value is a text requirement in the syntax above, or a list
whose items are ANDed. Plain-language aliases are rewritten before parsing: `all biometals`, `any model`,
`Model HX`, `Model HX (full)`, `Life Up x2`, `Sub Tank x1`, `Absorber Chip`,
`Red Card Key`, and a few Spanish equivalents. An empty value or `free` asks for nothing. A boss requirement
may not name another boss, which would recurse, nor a mission event, which depends on regions the requirement itself
may be closing; it is stored in the `normal` tier, so it applies at every difficulty.

```yaml
Mega Man ZX:
  boss_logic:
    Hivolt: "HX & LIFEUP>=2"
    Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
    Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
    Flammole: "Model FX (full) & Absorber Chip"
```

Generation fails early if the YAML sets a requirement for a boss that the document does not anchor, since it would
apply to nothing. After the pool is built, the world checks that the goal is reachable with every item in hand; if it
is not, the error names the bosses whose requirement is still unmet. That catches requests the pool cannot satisfy,
such as a biometal demanded for the two bosses that are its only sources, or more Life Ups than exist. The slot data
carries a text rendering of the boss requirements.

### The D-4 boss rush

The tower of D-4 makes the player fight the eight Pseudoroids again before the exit to D-5. The eight teleporters are
edges from `d04` into the generic room `z02`, and each carries the `BOSS_*` atom of its Pseudoroid as an edge cost.
The `index` of a Pseudoroid in the roster (Hivolt 0 to Protectos 7) is the argument the game gives its teleporter
entity and the position of its victory level. The exit door to D-5 carries all eight atoms, because the game does not open it before the rush is complete. A boss
anchored only on those edges does not count as anchored: its story fight would be left without the requirement.

With the `skip_boss_rush` option the eight teleporter edges are left out of the graph, so `z02` becomes unreachable,
and the exit to D-5 loses its extra cost. Arena tags are untouched, so the story fights keep their requirement. In the
game the client marks each pair of Pseudoroids as defeated while the player climbs the tower; that client-side logic
lives in `bossrush.py` and plays no part in generation.

## Validation

The validator in `logic_format.py` returns errors, warnings, the number of `unsure` rules and the number of unplaced
locations. Errors mean the document is inconsistent with the data and block the text export; warnings point at likely
mistakes and never block anything. An empty `main` with no connections is not reported, being the normal outcome of
the entrance-region pattern.

Errors:

- a room of the world is missing from the document, or the document names a room the world does not have;
- a room has no `main` region;
- a region other than `main` has no polygon or fewer than three vertices;
- a region is tagged with an unknown boss id, or the same boss is tagged in two regions;
- a connection refers to an unknown region, joins a region to itself, or repeats an existing from-to pair;
- a connection has no requirement;
- a requirement is malformed: not an object, an unknown tier, a tier that is not a list of lists, or an unknown atom;
- a member override points to an unknown region;
- `placed` names an unknown location or an unknown room;
- `edges` names a door that is not in the door table, or `checks` names an unknown location.

Warnings:

- a requirement uses an atom whose item is not in the pool, so it is never met;
- a boss is tagged in a room other than the one where it is fought;
- some bosses of the roster are not anchored anywhere, so `boss_logic` cannot apply to them;
- a door needs a key that is not in the pool, so it stays closed in the logic;
- some locations are unplaced and fall back to the area-label rule;
- a region has nodes or connections but no possible entry, judging by topology alone at the `expert` tier;
- a region other than `main` is empty: no checks, doors or connections;
- a region has entries but no door or connection leading back out; in the game one can always turn back, so this
  is a drawing mistake;
- a region is isolated from the rest of its room: only doors to other rooms, no connections or internal doors;
- `main` holds nodes but has no connection to the other regions of a room that has some, listing the endpoints that lack a position.

`tools/check_logic.py` runs the validator from the command line against `data.py`, with the Hub as starting room. It
prints the errors, then the warnings unless `--quiet`, then one summary line with the counts of rooms, regions,
connections, checks with a rule, edges with a cost, errors, warnings, unsure rules and unplaced locations. When there
are no errors it rewrites `logic/logic.txt`, unless `--no-txt`. The exit code is 1 on errors.

## The text twin

`logic.txt` is generated from the document and the data. It starts with a comment header that recalls the atom list
and the meaning of `free`, `never` and `?`, then a `gates:` block, then one block per room in data order, then an
`unplaced:` block when some locations have no room.

```
room E-7 [e07]
  region Main
  region Boss Room  (4 vertices)   [ARENA: Hivolt]
    check Obtain Biometal H   (also in I-3: any of them counts)
      normal: MODEL
    conn -> E-5 Entrance
      normal: MODEL
  region E-8 Entrance  (4 vertices)
    warp -> Hub @(1632,720)
    door -> E-8 @(1760,720)
      normal: SEARCH_THE_PLANT
    path -> I-1/Hub Entrance @(1632,720)
    <- E-8 @(1760,720)
    conn -> Boss Room
      normal: MODEL
```

The room line gives the label and the code, then `entry:` with the entry requirement if any, then the note. Regions
come `Main` first and the rest in id order, with the polygon's vertex count, the `[ARENA: ]` tag and the note.
Inside a region come the edges that leave it: `door`, `internal` for a door to another region of the same room,
`warp`, `pad(save)` or `path` for a curated seam, then the destination label with `/Region` when the landing is not
its `main`, the exit position, `key`, `gate` and, for warps out of the Hub, `needs` with the access item; an extra
cost follows on indented lines. Landings from other rooms appear as `<- Room @(x,y)`. Checks show their
requirement only when it is not simply free, and name the other room where a two-placement location also counts.
Connections always show theirs.

A requirement prints one line per alternative, prefixed with the tier: `normal: HX & LX`, then
`expert: FX`. A free alternative prints as `free` and no alternative at all as `never`. A `?` before the tier
marks an `unsure` rule, and a trailing `# ...` carries the note.

## The visual editor

The editor is a small local web application: `serve.py` is a standard-library HTTP server and the interface is plain
HTML, JavaScript and CSS in the same folder. From the apworld root, run `python tools/logic_editor/serve.py`,
with `--port`, `--no-browser`, `--renders DIR` and `--gimmicks FILE` as options. On Windows,
`tools/run_logic_editor.bat` starts the server and opens the browser, using the interpreter and renders folder of a
parent checkout when there is one and the `python` on the PATH otherwise.

Rooms are drawn on 1:1 renders read from `tools/logic_editor/local/renders/`, one PNG per room code. The renders are
game graphics and are not in the repository; without them the editor works on a blank canvas. The gimmicks layer,
enemies and switches with their names and positions, comes from `tools/logic_editor/data/gimmicks.json`, a file
derived outside this repository from the room entity tables of the ROM, with the kinds named after the Mega Man ZX
Editor's nomenclature; it is informational only and the editor runs without it.

The server exposes `GET /api/world` for the static data, atom catalog and boss roster, `GET /api/logic` for
the document or an empty skeleton, `POST /api/logic` to save, `POST /api/validate` to validate without
saving, `GET /api/txt` for the text twin and `POST /api/reload` to reread the data. Saving normalizes and
validates the document, writes `logic.json`, rewrites `logic.txt` when there are no errors, and returns the report.
The atom catalog is built at startup, so a new atom needs a restart to appear. A full guide to the editor is a
separate document.

## Related tools

- `tools/check_logic.py`: validates the document against the data and regenerates `logic.txt`.
- `tools/logic_probe.py`: builds a one-player multiworld from an Archipelago source checkout, given options and an inventory, and prints the reachable regions, the locations in logic and the frontier of blocked edges with the rule that blocks each; `--loc` explains one location.
- `tools/logic_snapshot.py`: evaluates a matrix of option sets and inventories into a JSON baseline and compares two baselines, to prove that a change alters nothing it should not.
- `tools/tag_bosses.py`: one-off migration that tagged the arenas and anchored the boss rush; it will be removed.
- `test/test_boss_logic.py` and `test/test_skip_boss_rush.py`: check that a boss requirement closes exactly what lies behind that boss, and that `skip_boss_rush` changes only the tower.
