# Logic editor

The visual editor in which the access logic of this world is drawn. It runs locally: `serve.py` is a
standard-library HTTP server and the interface is plain HTML, CSS and JavaScript with no build step and
no dependencies. The interface is in English.

Each room is shown on a 1:1 render. You draw polygons (regions), connect them with directed connections
that carry a requirement, give requirements to checks, edge exits and event gates, and place by hand the
locations that have no position in the data (missions, quests, biometals). The result is
`logic/logic.json`, the single source of truth of the logic.
Never edit that file by hand.

## Starting it

From the apworld root:

    python tools/logic_editor/serve.py [--port 8765] [--no-browser] [--renders DIR] [--gimmicks FILE]

On Windows, `tools/run_logic_editor.bat` starts the server on port 8765 and opens the browser; it uses the
Python interpreter and the renders folder of a parent checkout when it finds them, else the `python` on
the PATH.

## Inputs

- **Room renders**: `local/renders/<room>.png` (or `--renders DIR`). They are game graphics and are not
  in the repository; produce them from your own ROM (the root README says how). Without them the editor
  works on a blank canvas of the right size.
- **Gimmicks**: `data/gimmicks.json` (or `--gimmicks FILE`): names and positions of the enemies and
  gimmicks of every room, drawn as an informational layer. The editor works without it.
- **World data**: `data.py` and `logic_format.py` of the apworld, served as `/api/world` (rooms,
  locations, edges, atom catalog, boss roster). The atom catalog is built when the server starts, so a
  new atom needs a restart to appear.

## Saving

Everything autosaves 600 ms after the last change: the document is POSTed to `/api/logic`, the server
normalizes and validates it, writes `logic/logic.json`, regenerates `logic/logic.txt` (the readable
twin) when there are no errors, and answers with the validation report shown in the bottom drawer.
"Validate" runs the same validation without saving; "logic.txt" opens the twin in a new tab. Undo and
redo keep up to 100 steps. Closing the tab with unsaved changes asks for confirmation.

## Code map

`index.html` loads the modules of `js/` in this order. Each one adds its functions to a single namespace
object, `window.LogicEditor` (`LE` inside the files), which is also handy from the browser console
(`LogicEditor.S`, `LogicEditor.DOC`, `LogicEditor.switchRoom('a01')`).

| File | Contents |
|---|---|
| `logic_core.js` | requirement algebra mirrored from `logic_format.py`: atoms, parser, DNF, tiers, point in polygon |
| `util.js` | DOM builder `h()`, `$`, geometry helpers, slugs, rgba colors |
| `state.js` | shared state (`W` world, `DOC` document, `S` UI, `V` viewport, `CV` canvas) and visual constants |
| `document.js` | document shape, accessors, hand placements, `edit` / `undo` / `redo` / `changed` |
| `nodes.js` | nodes of a room (checks, exits, landings) with region membership, labels and tooltips |
| `view.js` | pan / zoom, fit, center, canvas resize, render image cache |
| `hints.js` | tooltip, hint bar, flash messages, modal prompt |
| `draw.js` | one frame of the canvas |
| `actions.js` | tool mode, selection, room switch, polygons, placements, deletions, connections |
| `canvas_events.js` | hit-testing and the mouse / drop handlers |
| `keyboard.js` | shortcuts and the unload guard |
| `api.js` | fetches, autosave, validate, status pill |
| `report.js` | the validation report drawer |
| `topbar.js` | area / room tabs, layers, search, panel toggles, button bindings |
| `tree.js` | left panel: outline by region and the "Unplaced" list |
| `requirements.js` | the requirement editor widget |
| `inspector.js` | right panel for every kind of selection |
| `gates.js` | the "Event gates" panel |
| `main.js` | startup, URL parameters, draw loop |

## Keyboard shortcuts

`V` select · `P` draw polygon (click adds a vertex; click on the first one, double click or `Enter`
closes; `Esc` cancels; right click removes the last one) · `A` create connections by dragging from one
region to another (bidirectional; with `Shift`, one way only; Main is ignored) · `Esc` cancel / deselect /
close panels · `Del` delete the selection or the active vertex · `Ctrl+Z` / `Ctrl+Y` undo / redo ·
`0` `+` `-` fit / zoom in / zoom out (also the mouse wheel) · `F` search · `?` help ·
`Space`+drag pan (also the middle button or dragging over an empty area).

With a region selected: drag its vertices; double click on a side inserts a vertex; right click or `Del`
on a vertex removes it (minimum 3); `Shift`+drag inside moves the whole region. Hand-placed nodes
(hexagons) can be dragged; rows of the "Unplaced" list can be dragged onto the canvas.

URL parameters: `?room=a01`, `&select=<node or location>`, `&region=<rid>`, `&conn=<from>><to>`,
`&tier=expert`, `&gates=1`, `&report=1`, `&help=1`, `&mode=poly`, `&zoom=0.5`.
