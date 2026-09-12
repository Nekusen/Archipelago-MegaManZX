/* state.js - shared mutable state and visual constants: world data W, the document DOC, the UI state S,
 * the viewport V and the canvas metrics CV. Every other module reads and writes these through LE. */
(function (LE) {
'use strict';

const CAT = {
  disk: { color: '#4dd0e1', label: 'Data Disk' },
  life_up: { color: '#ef5350', label: 'Life Up' },
  sub_tank: { color: '#ffee58', label: 'Sub Tank' },
  biometal: { color: '#ba68c8', label: 'Biometal' },
  mission: { color: '#66bb6a', label: 'Mission' },
  quest: { color: '#ffa726', label: 'Quest' },
  pickup_crystal: { color: '#a8a8a8', label: 'E-Crystal (pickup)' },
  pickup_1up: { color: '#c4c4c4', label: '1-Up (pickup)' },
  pickup_energy: { color: '#8f8f8f', label: 'Energy (pickup)' },
  pickup_weapon: { color: '#777777', label: 'Weapon Energy (pickup)' },
};
const catColor = (c) => (CAT[c] || { color: '#9e9e9e' }).color;
const catLabel = (c) => (CAT[c] || { label: c || '?' }).label;
const KEY_COLOR = {
  'Yellow Card Key': '#ffd600', 'Green Card Key': '#43a047', 'Red Card Key': '#e53935',
  'Blue Card Key': '#1e88e5', 'White Card Key': '#f5f5f5', 'Purple Card Key': '#ab47bc',
};
const NOKEY = '#cfd8dc';
const IN_COLOR = '#90caf9';
const PALETTE = ['#f28b82', '#fbbc04', '#81c995', '#a7ffeb', '#d7aefb', '#ff8bcb', '#78d9ec', '#fde293'];
const KIND_LABELS = {   // edge kinds of data.py as shown in tooltips and the inspector
  door: 'door', internal: 'internal door', warp: 'warp', save: 'pad (save)', curated: 'curated edge',
};
const LAYER_DEFS = [   // [key, label, visible by default]
  ['checks', 'Checks', true], ['doors', 'Doors', true], ['landings', 'Landings', true],
  ['gimmicks', 'Gimmicks', true], ['enemies', 'Enemies', false], ['regions', 'Regions', true],
  ['conns', 'Connections', true], ['labels', 'Labels', true],
];

// World data (/api/world) and the logic document. Both are single objects whose CONTENTS main.js and
// the undo history replace in place, so every module can keep a direct reference to them.
const W = {};
const DOC = {};

const S = {
  room: null, tier: 'normal', mode: 'select',
  sel: { type: 'room' }, hover: null, activeVertex: null,
  drawing: null, placing: null, drag: null, space: false,
  edgeFrom: null, edgeHover: null,   // 'edge' mode: pinned source and region under the cursor
  layers: {}, collapsed: new Set(),
  docVersion: 0, undo: [], redo: [],
  saveTimer: null, saving: false, savePending: false, savedVersion: 0,
  report: { errors: [], warnings: [], unsure: 0, unplaced: 0 },
  gatesTarget: null,
};
for (const [k, , d] of LAYER_DEFS) S.layers[k] = d;
try {
  const saved = JSON.parse(localStorage.getItem('mmzx-logic-layers') || 'null');
  if (saved && typeof saved === 'object') {
    for (const [k] of LAYER_DEFS) if (typeof saved[k] === 'boolean') S.layers[k] = saved[k];
  }
} catch (e) { /* no storage */ }

// Viewport: screen = world * scale + (tx, ty).
const V = { scale: 1, tx: 0, ty: 0 };
// Canvas element, its 2D context, its CSS size, the redraw flag, the last mouse position (screen
// coordinates) and the connection geometry of the last frame (for hit-testing).
const CV = { el: null, ctx: null, w: 1, h: 1, dirty: true, mouse: [0, 0], connShapes: [] };

Object.assign(LE, {
  CAT, catColor, catLabel, KEY_COLOR, NOKEY, IN_COLOR, PALETTE, KIND_LABELS, LAYER_DEFS, W, DOC, S, V, CV,
});
})(window.LogicEditor || (window.LogicEditor = {}));
