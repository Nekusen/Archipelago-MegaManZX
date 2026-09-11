/* app.js - Mega Man ZX visual logic editor (front-end).
 * Plain JavaScript (ES2020), no dependencies, no build. Served by tools/logic_editor/serve.py.
 * The logic core (expression parser, DNF, geometric membership) mirrors
 * worlds/mmzx/logic_format.py and is exposed as globalThis.MMZXLogic for tests.
 * URL parameters: ?room=a01&select=<node id>&region=<rid>&conn=<from>><to>&tier=expert&gates=1
 */
'use strict';
(function (root) {

// =====================================================================
// Logic core (mirror of logic_format.py)
// =====================================================================
const DEFAULT_ATOMS = (() => {
  const out = [];
  const models = { HU: 'Hu (human form)', X: 'Model X', ZX: 'Model ZX', HX: 'Model HX', FX: 'Model FX', LX: 'Model LX', PX: 'Model PX', OX: 'Model OX' };
  for (const [id, label] of Object.entries(models)) out.push({ id, group: 'model', label });
  for (const m of ['HX', 'FX', 'LX', 'PX']) out.push({ id: m + '2', group: 'model', label: 'Model ' + m + ' complete (2 halves: level 2 charge)' });
  out.push({ id: 'MODEL', group: 'model', label: 'MODEL (any non-Hu model)' });
  out.push({ id: 'ALL6', group: 'model', label: 'ALL6 (all six biometals)' });
  for (const k of ['YELLOW', 'GREEN', 'RED', 'BLUE', 'WHITE', 'PURPLE']) out.push({ id: k, group: 'key', label: k[0] + k.slice(1).toLowerCase() + ' Card Key' });
  for (let n = 1; n <= 4; n++) out.push({ id: 'LIFEUP>=' + n, group: 'life', label: 'Life Up x' + n });
  for (let n = 1; n <= 4; n++) out.push({ id: 'SUBTANK>=' + n, group: 'life', label: 'Sub Tank x' + n });
  for (const m of ['LOCATE_GIRO', 'PASS_THE_TEST', 'TROOP_REINFORCEMENT', 'SEARCH_THE_PLANT', 'FIND_THE_SURVIVORS', 'FIGHT_THE_MAVERICKS', 'SECURE_THE_BIOMETAL', 'SAVE_THE_PEOPLE', 'RECOVER_THE_DISK', 'ATTACK_THE_EXCAVATORS', 'PROTECT_THE_LAB', 'PROTECT_HQ', 'STOP_THE_DIG', 'REPEL_THE_ARMY', 'DESTROY_MODEL_W']) out.push({ id: m, group: 'mission', label: m });
  for (let n = 1; n <= 8; n++) out.push({ id: 'MISSIONS>=' + n, group: 'mission', label: 'Area missions completed x' + n + ' (of the 8: E-7...L-4)' });
  for (const a of 'ABCDEFGIKLMOX') out.push({ id: 'ACCESS_' + a, group: 'transerver', label: 'Transerver Access - Area ' + a });
  return out;
})();

const Logic = (() => {
  let TIERS = ['normal', 'expert'];
  let plain = new Set();      // atoms without a count
  let counts = new Set();     // NAME prefixes of NAME>=n
  let groups = {};            // id -> group
  let catalog = [];
  const CONST_TRUE = ['TRUE', 'ANY', 'FREE'];
  const CONST_FALSE = ['FALSE', 'NEVER', 'IMPOSSIBLE'];
  const COUNT_RE = /^([A-Z_]+)>=(\d+)$/;

  function configure(atoms, tiers) {
    catalog = atoms || DEFAULT_ATOMS;
    if (tiers && tiers.length) TIERS = tiers.slice();
    plain = new Set(); counts = new Set(); groups = {};
    for (const a of catalog) {
      groups[a.id] = a.group;
      const m = COUNT_RE.exec(a.id);
      if (m) counts.add(m[1]); else plain.add(a.id);
    }
  }
  configure(DEFAULT_ATOMS);

  function canonicalAtom(tok) {
    if (typeof tok !== 'string') return null;
    const t = tok.trim().toUpperCase().replace(/ /g, '');
    if (plain.has(t)) return t;
    const m = COUNT_RE.exec(t);
    if (m && counts.has(m[1])) {
      const n = parseInt(m[2], 10);
      if (n < 1) return null;
      return m[1] + '>=' + n;
    }
    return null;
  }
  const isValidAtom = (tok) => canonicalAtom(tok) !== null;
  function groupOf(atom) {
    if (groups[atom]) return groups[atom];
    const m = COUNT_RE.exec(atom || '');
    if (m) for (const a of catalog) if (a.id.startsWith(m[1] + '>=')) return a.group;
    return '';
  }

  function dnfNormalize(dnf) {
    const alts = dnf.map(alt => { const s = []; for (const a of alt) if (!s.includes(a)) s.push(a); return s; });
    const keep = [];
    for (let i = 0; i < alts.length; i++) {
      const sa = new Set(alts[i]);
      let absorbed = false;
      for (let j = 0; j < alts.length; j++) {
        if (i === j) continue;
        const sb = new Set(alts[j]);
        let subset = true;
        for (const x of sb) if (!sa.has(x)) { subset = false; break; }
        if (!subset) continue;
        if (sb.size < sa.size || (sb.size === sa.size && j < i)) { absorbed = true; break; }
      }
      if (!absorbed) keep.push(alts[i]);
    }
    return keep;
  }
  const dnfAnd = (a, b) => { const out = []; for (const x of a) for (const y of b) out.push(x.concat(y)); return dnfNormalize(out); };
  const dnfOr = (a, b) => dnfNormalize(a.concat(b));
  const DNF_TRUE = () => [[]];
  const DNF_FALSE = () => [];

  const TOK = /\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*>=\s*\d+)?|&&|\|\||[&|()+,])/y;
  function tokens(expr) {
    const out = [];
    expr = expr.trim();
    let pos = 0;
    while (pos < expr.length) {
      TOK.lastIndex = pos;
      const m = TOK.exec(expr);
      if (!m) throw new Error('invalid expression at position ' + pos + ': "' + expr.slice(pos, pos + 12) + '"');
      out.push(m[1].replace(/ /g, ''));
      pos = TOK.lastIndex;
    }
    return out;
  }
  const isAnd = (t) => t === '&' || t === '&&' || t === '+' || t === ',' || t.toUpperCase() === 'AND';
  const isOr = (t) => t === '|' || t === '||' || t.toUpperCase() === 'OR';
  function parseExpr(expr) {
    if (expr == null) return DNF_TRUE();
    const toks = tokens(expr);
    if (!toks.length) return DNF_TRUE();
    const [dnf, i] = parseOr(toks, 0);
    if (i !== toks.length) throw new Error('leftover tokens starting at "' + toks[i] + '"');
    return dnf;
  }
  function parseOr(toks, i) {
    let [node, j] = parseAnd(toks, i);
    while (j < toks.length && isOr(toks[j])) {
      const [rhs, k] = parseAnd(toks, j + 1);
      node = dnfOr(node, rhs); j = k;
    }
    return [node, j];
  }
  function parseAnd(toks, i) {
    let [node, j] = parseAtom(toks, i);
    while (j < toks.length && isAnd(toks[j])) {
      const [rhs, k] = parseAtom(toks, j + 1);
      node = dnfAnd(node, rhs); j = k;
    }
    return [node, j];
  }
  function parseAtom(toks, i) {
    if (i >= toks.length) throw new Error('incomplete expression');
    const t = toks[i];
    if (t === '(') {
      const [node, j] = parseOr(toks, i + 1);
      if (j >= toks.length || toks[j] !== ')') throw new Error("missing ')'");
      return [node, j + 1];
    }
    const up = t.toUpperCase();
    if (CONST_TRUE.includes(up)) return [DNF_TRUE(), i + 1];
    if (CONST_FALSE.includes(up)) return [DNF_FALSE(), i + 1];
    const a = canonicalAtom(t);
    if (a === null) throw new Error('unknown atom "' + t + '"');
    return [[[a]], i + 1];
  }
  function dnfToText(dnf) {
    if (!dnf || !dnf.length) return 'never';
    if (dnf.some(alt => alt.length === 0)) return 'free';
    return dnf.map(alt => alt.join(' & ')).join(' | ');
  }
  function reqAlternatives(req, tier) {
    if (req == null) return DNF_TRUE();
    const idx = TIERS.indexOf(tier == null ? TIERS[TIERS.length - 1] : tier);
    let alts = [];
    for (const t of TIERS.slice(0, idx + 1)) alts = alts.concat(req[t] || []);
    return dnfNormalize(alts);
  }
  const reqIsFree = (req, tier = TIERS[0]) => reqAlternatives(req, tier).some(a => a.length === 0);
  const reqIsNever = (req, tier) => reqAlternatives(req, tier).length === 0;
  function reqToLines(req) {
    if (req == null) return ['free'];
    const lines = [];
    let total = 0;
    for (const t of TIERS) for (const alt of (req[t] || [])) { total++; lines.push(t + ': ' + (alt.length ? alt.join(' & ') : 'free')); }
    if (!total) lines.push('never');
    return lines;
  }

  function pointInPoly(pt, poly) {
    if (!poly || poly.length < 3) return false;
    const x = pt[0], y = pt[1];
    let inside = false;
    const n = poly.length;
    let j = n - 1;
    for (let i = 0; i < n; i++) {
      const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
      if ((yi > y) !== (yj > y)) {
        const xc = (xj - xi) * (y - yi) / (yj - yi) + xi;
        if (x < xc) inside = !inside;
      }
      j = i;
    }
    return inside;
  }
  function polyArea(poly) {
    if (!poly || poly.length < 3) return 0;
    let s = 0;
    const n = poly.length;
    for (let i = 0; i < n; i++) {
      const a = poly[i], b = poly[(i + 1) % n];
      s += a[0] * b[1] - b[0] * a[1];
    }
    return Math.abs(s) / 2;
  }
  function regionOfPoint(roomLogic, pt) {
    let best = 'main', bestArea = null;
    const regs = (roomLogic && roomLogic.regions) || {};
    for (const rid of Object.keys(regs)) {
      const poly = regs[rid].poly;
      if (rid === 'main' || !poly) continue;
      if (pointInPoly(pt, poly)) {
        const a = polyArea(poly);
        if (bestArea === null || a < bestArea) { best = rid; bestArea = a; }
      }
    }
    return best;
  }
  return { configure, canonicalAtom, isValidAtom, groupOf, dnfNormalize, dnfAnd, dnfOr, parseExpr, dnfToText,
    reqAlternatives, reqIsFree, reqIsNever, reqToLines, pointInPoly, polyArea, regionOfPoint,
    tiers: () => TIERS.slice(), catalog: () => catalog };
})();
root.MMZXLogic = Logic;

if (typeof document === 'undefined') return;   // in node: core only

// =====================================================================
// Utilities
// =====================================================================
const $ = (sel, el = document) => el.querySelector(sel);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const PROPS = new Set(['value', 'checked', 'disabled', 'selected', 'hidden', 'draggable', 'open', 'readOnly', 'indeterminate']);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const k of Object.keys(attrs)) {
    const v = attrs[k];
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style') el.style.cssText = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (PROPS.has(k)) el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  const add = (kid) => {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(add); return; }
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  };
  kids.forEach(add);
  return el;
}
function slugify(name) {
  return String(name).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
function hexA(hex, a) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || '');
  if (!m) return 'rgba(138,180,248,' + a + ')';
  return 'rgba(' + parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' + parseInt(m[3], 16) + ',' + a + ')';
}
function segDist(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const l2 = dx * dx + dy * dy;
  let t = l2 ? ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2 : 0;
  t = clamp(t, 0, 1);
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}
function polyCentroid(poly) {
  const n = poly.length;
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < n; i++) {
    const p = poly[i], q = poly[(i + 1) % n];
    const f = p[0] * q[1] - q[0] * p[1];
    a += f; cx += (p[0] + q[0]) * f; cy += (p[1] + q[1]) * f;
  }
  if (Math.abs(a) < 1e-9) {
    let sx = 0, sy = 0; for (const p of poly) { sx += p[0]; sy += p[1]; }
    return [sx / n, sy / n];
  }
  return [cx / (3 * a), cy / (3 * a)];
}
function polyBounds(poly) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of poly) { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); }
  return [x0, y0, x1, y1];
}

// =====================================================================
// Visual constants
// =====================================================================
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
const KEY_COLOR = { 'Yellow Card Key': '#ffd600', 'Green Card Key': '#43a047', 'Red Card Key': '#e53935', 'Blue Card Key': '#1e88e5', 'White Card Key': '#f5f5f5', 'Purple Card Key': '#ab47bc' };
const NOKEY = '#cfd8dc';
const IN_COLOR = '#90caf9';
const PALETTE = ['#f28b82', '#fbbc04', '#81c995', '#a7ffeb', '#d7aefb', '#ff8bcb', '#78d9ec', '#fde293'];
const KIND_ES = { door: 'door', internal: 'internal door', warp: 'warp', save: 'pad (save)', curated: 'curated edge' };
const LAYER_DEFS = [
  ['checks', 'Checks', true], ['doors', 'Doors', true], ['landings', 'Landings', true],
  ['gimmicks', 'Gimmicks', true], ['enemies', 'Enemies', false], ['regions', 'Regions', true],
  ['conns', 'Connections', true], ['labels', 'Labels', true],
];

// =====================================================================
// State
// =====================================================================
let W = null, DOC = null;
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
  if (saved && typeof saved === 'object') for (const [k] of LAYER_DEFS) if (typeof saved[k] === 'boolean') S.layers[k] = saved[k];
} catch (e) { /* no storage */ }

const V = { scale: 1, tx: 0, ty: 0 };
let canvas, ctx, cw = 1, ch = 1, dirty = true, mouse = [0, 0];
let connShapes = [];   // connection geometry of the last frame (hit-test)

// =====================================================================
// Document: access and mutation
// =====================================================================
function normalizeDoc(doc) {
  doc = doc || {};
  if (!doc.format) doc.format = 1;
  if (!doc.tiers) doc.tiers = Logic.tiers();
  for (const k of ['rooms', 'placed', 'edges', 'checks', 'gates']) if (!doc[k] || typeof doc[k] !== 'object') doc[k] = {};
  for (const r of W.room_order) if (!doc.rooms[r]) doc.rooms[r] = emptyRoom();
  for (const rl of Object.values(doc.rooms)) {
    if (!rl.regions) rl.regions = {};
    if (!rl.regions.main) rl.regions.main = emptyRoom().regions.main;
    if (!rl.conns) rl.conns = [];
    if (!rl.members) rl.members = {};
    if (rl.req === undefined) rl.req = null;
    if (rl.note == null) rl.note = '';
  }
  return doc;
}
const emptyRoom = () => ({ req: null, note: '', regions: { main: { name: 'Main', poly: null, color: '#8ab4f8', note: '' } }, conns: [], members: {} });
const RL = (r) => DOC.rooms[r || S.room];
const regionOrder = (rl) => ['main'].concat(Object.keys(rl.regions).filter(r => r !== 'main'));
const regionName = (room, rid) => { const r = DOC.rooms[room] && DOC.rooms[room].regions[rid]; return r ? (r.name || rid) : rid; };
const regionColor = (room, rid) => { const r = DOC.rooms[room] && DOC.rooms[room].regions[rid]; return (r && r.color) || '#8ab4f8'; };
const roomLabel = (code) => (W.rooms[code] && W.rooms[code].label) || code;
const roomSize = (code) => (W.rooms[code] && W.rooms[code].size) || [1024, 768];
const areaLabel = (a) => a === 'z' ? 'Hub' : a.toUpperCase();
const findConn = (rl, from, to) => rl.conns.find(c => c.from === from && c.to === to) || null;

function ensureEdge(name) { return DOC.edges[name] || (DOC.edges[name] = { pos: null, dst_pos: null, req: null, unsure: false, note: '' }); }
function pruneEdge(name) { const e = DOC.edges[name]; if (e && !e.pos && !e.dst_pos && e.req == null && !e.unsure && !e.note) delete DOC.edges[name]; }
function ensureCheck(name) { return DOC.checks[name] || (DOC.checks[name] = { req: null, unsure: false, note: '' }); }
function pruneCheck(name) { const c = DOC.checks[name]; if (c && c.req == null && !c.unsure && !c.note) delete DOC.checks[name]; }
function ensureGate(flag) { return DOC.gates[flag] || (DOC.gates[flag] = { req: null, note: '' }); }
// reads WITHOUT side effects (the inspector must not create entries while rendering)
const peekCheck = (name) => DOC.checks[name] || {};
const peekEdge = (name) => DOC.edges[name] || {};
const peekGate = (flag) => DOC.gates[flag] || {};

function pushUndo() {
  S.undo.push(JSON.stringify(DOC));
  if (S.undo.length > 100) S.undo.shift();
  S.redo = [];
}
function edit(fn, opts) { pushUndo(); fn(); changed(opts); }
function undo() {
  if (!S.undo.length) return;
  S.redo.push(JSON.stringify(DOC));
  DOC = normalizeDoc(JSON.parse(S.undo.pop()));
  afterHistory();
}
function redo() {
  if (!S.redo.length) return;
  S.undo.push(JSON.stringify(DOC));
  DOC = normalizeDoc(JSON.parse(S.redo.pop()));
  afterHistory();
}
function afterHistory() {
  S.activeVertex = null;
  validateSelection();
  changed();
}
function validateSelection() {
  const rl = RL();
  const s = S.sel;
  if (s.type === 'region' && !rl.regions[s.rid]) S.sel = { type: 'room' };
  else if (s.type === 'conn' && !findConn(rl, s.from, s.to)) S.sel = { type: 'room' };
  else if (s.type === 'node' && !roomNodes(S.room).byId[s.id]) {
    const [r] = checkPosition(s.id);
    S.sel = (!r && W.locations[s.id]) ? { type: 'loc', name: s.id } : { type: 'room' };
  } else if (s.type === 'loc' && W.locations[s.name] && ((W.locations[s.name].pos && W.locations[s.name].room === S.room) || placementIn(s.name, S.room))) S.sel = { type: 'node', id: s.name };
}
function touch() { S.docVersion++; dirty = true; }
function changed(opts = {}) {
  S.docVersion++;
  dirty = true;
  scheduleSave();
  renderTree();
  if (!opts.keepInspector) renderInspector();
  renderTabs();
  updateHint();
}

// =====================================================================
// Nodes of a room (checks, exits and landings) with membership
// =====================================================================
let cache = { v: -1, nodes: {}, cent: {}, unplacedLocs: null };
function ensureCache() { if (cache.v !== S.docVersion) cache = { v: S.docVersion, nodes: {}, cent: {}, unplacedLocs: null }; }
// Hand placements: DOC.placed[name] = {room,pos} or a LIST of them (the
// biometals are obtained at either of two bosses: two rooms, OR rule).
function placementsOf(name) {
  const p = DOC.placed[name];
  const arr = Array.isArray(p) ? p : (p ? [p] : []);
  return arr.filter(q => q && DOC.rooms[q.room] && q.pos);
}
function setPlacements(name, arr) {
  if (!arr.length) delete DOC.placed[name];
  else if (arr.length === 1) DOC.placed[name] = arr[0];
  else DOC.placed[name] = arr;
}
function placementIn(name, room) { return placementsOf(name).find(q => q.room === room) || null; }
// number of alternative rooms according to the area tag ('E-7/I-3' = 2)
function altRooms(name) { const lab = (W.locations[name] || {}).room || ''; return lab.includes('/') ? lab.split('/').length : 1; }
function checkPosition(name) {
  const v = W.locations[name];
  if (!v) return [null, null];
  if (v.pos && DOC.rooms[v.room]) return [v.room, v.pos];
  const pl = placementsOf(name);
  const cur = pl.find(q => q.room === S.room) || pl[0];   // the current room's one if any
  return cur ? [cur.room, cur.pos] : [null, null];
}
function edgeEndpoints(e) {
  const ov = DOC.edges[e.name] || {};
  const pos = ov.pos || e.pos || null;
  let dpos = ov.dst_pos || e.dst_pos || null;
  if (dpos && dpos[0] == null) dpos = null;
  return [pos, dpos];
}
function shortName(name, room) {
  const p = roomLabel(room) + ': ';
  return name.startsWith(p) ? name.slice(p.length) : name;
}
function roomNodes(room) {
  ensureCache();
  if (cache.nodes[room]) return cache.nodes[room];
  const rl = DOC.rooms[room];
  const list = [], byId = {}, members = {};
  const un = { outs: [], ins: [] };
  const add = (n) => { list.push(n); byId[n.id] = n; };
  for (const name of Object.keys(W.locations)) {
    const loc = W.locations[name];
    let pos = null;
    if (loc.pos && loc.room === room) pos = loc.pos;
    else if (!loc.pos) { const q = placementIn(name, room); if (q) pos = q.pos; }
    if (!pos) continue;
    add({ id: name, type: 'check', full: name, name: shortName(name, room), pos, placed: !(loc.pos && loc.room === room), cat: loc.category, color: catColor(loc.category), detect: loc.detect });
  }
  for (const e of W.edges) {
    const [pos, dpos] = edgeEndpoints(e);
    if (e.src === room) {
      if (pos) add({ id: e.name, type: 'out', full: e.name, edge: e, pos, placed: !e.pos, color: keyColor(e), locked: isLockedKey(e) });
      else un.outs.push(e);
    }
    if (e.dst === room) {
      if (dpos) add({ id: e.name + '@in', type: 'in', full: e.name + '@in', edge: e, pos: dpos, placed: !e.dst_pos, color: IN_COLOR });
      else un.ins.push(e);
    }
  }
  for (const n of list) {
    const ov = rl.members[n.id];
    if (ov && rl.regions[ov]) { n.rid = ov; n.pinned = true; }
    else { n.rid = Logic.regionOfPoint(rl, n.pos); n.pinned = false; }
    n.autoRid = Logic.regionOfPoint(rl, n.pos);
    members[n.id] = n.rid;
  }
  // nodes without a position: override or main (like resolve_members)
  for (const e of un.outs) members[e.name] = (rl.members[e.name] && rl.regions[rl.members[e.name]]) ? rl.members[e.name] : 'main';
  for (const e of un.ins) members[e.name + '@in'] = (rl.members[e.name + '@in'] && rl.regions[rl.members[e.name + '@in']]) ? rl.members[e.name + '@in'] : 'main';
  const out = { list, byId, members, un };
  cache.nodes[room] = out;   // before the labels: nodeLabel queries the membership of OTHER rooms (cycles A-1 <-> A-4)
  for (const n of list) n.label = nodeLabel(n);
  return out;
}
function landingRid(e) { return roomNodes(e.dst).members[e.name + '@in'] || 'main'; }
function nodeLabel(n) {
  if (n.type === 'check') return n.name;
  const e = n.edge;
  if (n.type === 'out') {
    if (e.kind === 'internal') return '↔ internal';
    if (e.kind === 'save') return 'pad';
    const rid = landingRid(e);
    const dst = roomLabel(e.dst) + (rid !== 'main' ? '/' + regionName(e.dst, rid) : '');
    if (e.kind === 'warp') return '⇄ ' + dst;
    if (e.kind === 'curated') return '⇢ ' + dst;
    return '→ ' + dst;
  }
  if (e.kind === 'internal') return '← internal';
  if (e.kind === 'save') return '← ' + roomLabel(e.src) + ' (pad)';
  if (e.kind === 'warp') return '⇄ ' + roomLabel(e.src);
  return '← ' + roomLabel(e.src);
}
function nodeTooltip(n) {
  const rl = RL();
  const reg = regionName(S.room, n.rid) + (n.pinned ? ' (pinned)' : '');
  if (n.type === 'check') {
    const ch = DOC.checks[n.id] || {};
    return n.full + '\n' + catLabel(n.cat) + (n.placed ? ' · placed by hand' : '') + ' · region ' + reg + '\nrequirement: ' + reqUiText(ch.req) + (ch.unsure ? ' (?)' : '');
  }
  const e = n.edge, ov = DOC.edges[e.name] || {};
  let s = e.name + '\n' + (n.type === 'out' ? 'exit' : 'landing') + ' · ' + (KIND_ES[e.kind] || e.kind);
  s += n.type === 'out' ? ' → ' + roomLabel(e.dst) + '/' + regionName(e.dst, landingRid(e)) : ' from ' + roomLabel(e.src);
  if (e.key) s += '\nkey: ' + e.key + (isLockedKey(e) ? ' (NOT in the pool: locked door)' : '');
  if (e.gate != null) s += '\ngate ' + e.gate + ': ' + gateText(e.gate);
  if (e.kind === 'warp' && e.src === W.hub && W.transerver_access[e.dst]) s += '\nneeds ' + W.transerver_access[e.dst];
  s += '\nregion ' + reg;
  if (ov.req) s += '\nextra cost: ' + reqUiText(ov.req);
  void rl;
  return s;
}
// key whose item is NOT in the pool (e.g. White Card Key): the door stays
// locked in the logic (the server says so via W.unavailable_items)
function isLockedKey(e) { return !!(e && e.key && (W.unavailable_items || []).includes(e.key)); }
function keyColor(e) { return isLockedKey(e) ? '#555' : (e.key ? (KEY_COLOR[e.key] || NOKEY) : NOKEY); }
function unplacedLocations() {
  ensureCache();
  if (!cache.unplacedLocs) cache.unplacedLocs = Object.keys(W.locations).filter(n => !W.locations[n].pos && placementsOf(n).length === 0);
  return cache.unplacedLocs;
}
// placed in some room but with more possible rooms (biometals: 2 bosses)
function multiCandidates() {
  return Object.keys(W.locations).filter(n => !W.locations[n].pos && placementsOf(n).length > 0 && placementsOf(n).length < altRooms(n));
}
function regionCentroid(room, rid) {
  ensureCache();
  const k = room + '/' + rid;
  if (cache.cent[k]) return cache.cent[k];
  const rl = DOC.rooms[room];
  let c;
  const reg = rl.regions[rid];
  if (rid !== 'main' && reg && reg.poly && reg.poly.length >= 3) c = polyCentroid(reg.poly);
  else {
    const nodes = roomNodes(room).list.filter(n => n.rid === rid);
    if (nodes.length) { let sx = 0, sy = 0; for (const n of nodes) { sx += n.pos[0]; sy += n.pos[1]; } c = [sx / nodes.length, sy / nodes.length]; }
    else { const sz = roomSize(room); c = [sz[0] / 2, sz[1] / 2]; }
  }
  cache.cent[k] = c;
  return c;
}
function gateText(flag) {
  const g = DOC.gates[String(flag)];
  if (!g || g.req == null) return 'free (the client opens it)';
  return reqUiText(g.req);
}
function reqUiText(req, tier) {
  const t = Logic.dnfToText(Logic.reqAlternatives(req, tier || S.tier));
  return t === 'free' ? 'free' : t === 'never' ? 'impossible' : t;
}
function reqShort(req, tier, max = 34) {
  let t = reqUiText(req, tier);
  if (t.length > max) t = t.slice(0, max - 1) + '…';
  return t;
}

// =====================================================================
// View (pan/zoom) and images
// =====================================================================
const toScreen = (p) => [p[0] * V.scale + V.tx, p[1] * V.scale + V.ty];
const toWorld = (sx, sy) => [(sx - V.tx) / V.scale, (sy - V.ty) / V.scale];
function fitView() {
  const sz = roomSize(S.room);
  const s = Math.min((cw - 40) / sz[0], (ch - 40) / sz[1]);
  V.scale = clamp(s, 0.02, 8);
  V.tx = (cw - sz[0] * V.scale) / 2;
  V.ty = (ch - sz[1] * V.scale) / 2;
  dirty = true; updateZoomLabel();
}
function zoomAt(sx, sy, factor) {
  const ns = clamp(V.scale * factor, 0.02, 16);
  const [wx, wy] = toWorld(sx, sy);
  V.scale = ns; V.tx = sx - wx * ns; V.ty = sy - wy * ns;
  dirty = true; updateZoomLabel();
}
function centerOn(pos, minScale = 0.6) {
  if (V.scale < minScale) V.scale = 1;
  V.tx = cw / 2 - pos[0] * V.scale; V.ty = ch / 2 - pos[1] * V.scale;
  dirty = true; updateZoomLabel();
}
function updateZoomLabel() { $('#zoom-label').textContent = Math.round(V.scale * 100) + '%'; }

const imgCache = new Map();
function getImage(room) {
  if (imgCache.has(room)) { const e = imgCache.get(room); imgCache.delete(room); imgCache.set(room, e); return e; }
  const img = new Image();
  const e = { img, ready: false, error: false };
  img.onload = () => { e.ready = true; dirty = true; };
  img.onerror = () => { e.error = true; dirty = true; };
  img.src = '/renders/' + room + '.png';
  imgCache.set(room, e);
  while (imgCache.size > 6) {
    const first = imgCache.keys().next().value;
    if (first === room) break;
    imgCache.delete(first);
  }
  return e;
}

// =====================================================================
// Drawing
// =====================================================================
function layerOf(n) { return n.type === 'check' ? 'checks' : n.type === 'out' ? 'doors' : 'landings'; }
const nodeVisible = (n) => !!S.layers[layerOf(n)];
function haloText(text, x, y, opts = {}) {
  ctx.font = (opts.bold ? 'bold ' : '') + (opts.size || 11) + 'px system-ui, "Segoe UI", sans-serif';
  ctx.textAlign = opts.align || 'center';
  ctx.textBaseline = opts.baseline || 'top';
  ctx.lineWidth = 3; ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(0,0,0,.85)';
  ctx.strokeText(text, x, y);
  ctx.fillStyle = opts.color || '#eee';
  ctx.fillText(text, x, y);
}
function pill(text, x, y, opts = {}) {
  ctx.font = (opts.bold ? 'bold ' : '') + (opts.size || 11) + 'px system-ui, "Segoe UI", sans-serif';
  const w = ctx.measureText(text).width + 10, hh = (opts.size || 11) + 6;
  ctx.fillStyle = opts.bg || 'rgba(0,0,0,.72)';
  ctx.beginPath();
  ctx.roundRect ? ctx.roundRect(x - w / 2, y - hh / 2, w, hh, 4) : ctx.rect(x - w / 2, y - hh / 2, w, hh);
  ctx.fill();
  if (opts.border) { ctx.strokeStyle = opts.border; ctx.lineWidth = 1; ctx.stroke(); }
  ctx.fillStyle = opts.color || '#eee';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y);
  return [x - w / 2, y - hh / 2, w, hh];
}
function shapeSquare(x, y, r) { ctx.beginPath(); ctx.rect(x - r, y - r, 2 * r, 2 * r); }
function shapeTri(x, y, r) { ctx.beginPath(); ctx.moveTo(x - r * 0.8, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x - r * 0.8, y + r); ctx.closePath(); }
function shapeCircle(x, y, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); }
function shapeHex(x, y, r) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) { const a = Math.PI / 3 * i - Math.PI / 6; const px = x + r * Math.cos(a), py = y + r * Math.sin(a); if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py); }
  ctx.closePath();
}
function drawPin(x, y) {
  ctx.beginPath(); ctx.moveTo(x, y + 7); ctx.lineTo(x, y); ctx.strokeStyle = '#111'; ctx.lineWidth = 2; ctx.stroke();
  shapeCircle(x, y - 1, 3.5); ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle = '#111'; ctx.lineWidth = 1; ctx.stroke();
}
function draw() {
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = '#101012';
  ctx.fillRect(0, 0, cw, ch);
  connShapes = [];
  if (!S.room || !W) return;
  const sz = roomSize(S.room);
  const im = getImage(S.room);
  const [ox, oy] = toScreen([0, 0]);
  if (im.ready) {
    ctx.save();
    ctx.setTransform(dpr * V.scale, 0, 0, dpr * V.scale, dpr * V.tx, dpr * V.ty);
    ctx.imageSmoothingEnabled = V.scale < 1;
    ctx.drawImage(im.img, 0, 0);
    ctx.restore();
  } else {
    ctx.fillStyle = '#1b1b20';
    ctx.fillRect(ox, oy, sz[0] * V.scale, sz[1] * V.scale);
    haloText(im.error ? 'Render not available: ' + S.room + '.png' : 'Loading render...', cw / 2, ch / 2 - 6, { size: 14, color: '#aaa' });
  }
  ctx.strokeStyle = 'rgba(255,255,255,.25)'; ctx.lineWidth = 1;
  ctx.strokeRect(ox + 0.5, oy + 0.5, sz[0] * V.scale, sz[1] * V.scale);

  const rl = RL();
  const nodes = roomNodes(S.room);
  const sel = S.sel;
  // --- regions
  if (S.layers.regions) {
    for (const rid of regionOrder(rl)) {
      const reg = rl.regions[rid];
      if (rid === 'main' || !reg.poly || reg.poly.length < 3) continue;
      const pts = reg.poly.map(toScreen);
      const isSel = sel.type === 'region' && sel.rid === rid;
      const isHov = S.hover && S.hover.type === 'region' && S.hover.rid === rid;
      ctx.beginPath();
      pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.fillStyle = hexA(reg.color, isSel ? 0.3 : isHov ? 0.24 : 0.16);
      ctx.fill();
      ctx.strokeStyle = hexA(reg.color, 0.95);
      ctx.lineWidth = isSel ? 2.5 : isHov ? 2 : 1.5;
      if (isSel) ctx.setLineDash([]);
      ctx.stroke();
      const c = toScreen(polyCentroid(reg.poly));
      haloText(reg.name || rid, c[0], c[1] - 7, { bold: true, size: 12, color: reg.color });
    }
    if (regionOrder(rl).length > 1 || rl.conns.length) {
      const c = toScreen(regionCentroid(S.room, 'main'));
      const isSel = sel.type === 'region' && sel.rid === 'main';
      pill(rl.regions.main.name || 'Main', c[0], c[1], { bold: true, color: rl.regions.main.color || '#8ab4f8', border: isSel ? '#fff' : hexA(rl.regions.main.color, 0.8) });
    }
  }
  // --- connections
  if (S.layers.conns) for (const c of rl.conns) drawConn(rl, c);
  // --- gimmicks / enemies
  if (S.layers.gimmicks || S.layers.enemies) {
    const gs = W.gimmicks[S.room] || [];
    for (let i = 0; i < gs.length; i++) {
      const g = gs[i];
      if (!(g.layer === 'enemies' ? S.layers.enemies : S.layers.gimmicks)) continue;
      const [x, y] = toScreen(g.pos);
      if (x < -20 || y < -20 || x > cw + 20 || y > ch + 20) continue;
      const isSel = sel.type === 'gimmick' && sel.idx === i;
      const isHov = S.hover && S.hover.type === 'gimmick' && S.hover.idx === i;
      shapeCircle(x, y, isSel || isHov ? 4.5 : 3);
      ctx.fillStyle = g.layer === 'enemies' ? '#ef9a9a' : '#b0bec5';
      ctx.fill(); ctx.strokeStyle = '#111'; ctx.lineWidth = 1; ctx.stroke();
      if (isSel) { shapeCircle(x, y, 9); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke(); }
      if (S.layers.labels && (isHov || isSel || V.scale >= 0.6)) haloText(g.name, x, y + 5, { size: 9, color: '#c8d0d4' });
    }
  }
  // --- nodes (landings, exits, checks)
  const order = { in: 0, out: 1, check: 2 };
  const vis = nodes.list.filter(nodeVisible).sort((a, b) => order[a.type] - order[b.type]);
  for (const n of vis) {
    const [x, y] = toScreen(n.pos);
    if (x < -40 || y < -40 || x > cw + 40 || y > ch + 40) continue;
    const isSel = sel.type === 'node' && sel.id === n.id;
    const isHov = S.hover && S.hover.type === 'node' && S.hover.node.id === n.id;
    if (isSel || isHov) {
      shapeCircle(x, y, isSel ? 15 : 13);
      ctx.strokeStyle = isSel ? '#fff' : 'rgba(255,255,255,.55)'; ctx.lineWidth = 2; ctx.stroke();
    }
    ctx.lineWidth = 1.5; ctx.strokeStyle = '#111';
    if (n.placed) {
      shapeHex(x, y, 10);
      if (n.type === 'in') { ctx.strokeStyle = n.color; ctx.lineWidth = 2.5; ctx.stroke(); }
      else { ctx.fillStyle = n.color; ctx.fill(); ctx.stroke(); }
      if (n.type === 'out') { shapeTri(x + 1, y, 4); ctx.fillStyle = '#111'; ctx.fill(); }
    } else if (n.type === 'check') {
      shapeSquare(x, y, 8); ctx.fillStyle = n.color; ctx.fill(); ctx.stroke();
    } else if (n.type === 'out') {
      shapeTri(x, y, 9); ctx.fillStyle = n.color; ctx.fill(); ctx.stroke();
    } else {
      shapeCircle(x, y, 8); ctx.strokeStyle = n.color; ctx.lineWidth = 2.5; ctx.stroke();
    }
    if (n.pinned) drawPin(x + 9, y - 10);
    // labels: checks and exits below, landings above (they usually coincide with an exit)
    if (S.layers.labels) haloText(n.label, x, n.type === 'in' ? y - 11 : y + 11, { size: 10, baseline: n.type === 'in' ? 'bottom' : 'top', color: n.type === 'check' ? '#f2f2f2' : n.type === 'out' ? '#ffe9a8' : '#bfe0ff' });
  }
  // --- vertices of the selected region
  if (S.mode === 'select' && sel.type === 'region' && sel.rid !== 'main' && S.layers.regions) {
    const reg = rl.regions[sel.rid];
    if (reg && reg.poly) reg.poly.forEach((p, i) => {
      const [x, y] = toScreen(p);
      const act = S.activeVertex === i;
      const hov = S.hover && S.hover.type === 'vertex' && S.hover.i === i;
      shapeSquare(x, y, act ? 6 : hov ? 5.5 : 4.5);
      ctx.fillStyle = act ? '#fff' : reg.color; ctx.fill();
      ctx.strokeStyle = '#000'; ctx.lineWidth = 1.5; ctx.stroke();
    });
  }
  // --- polygon under construction
  if (S.mode === 'poly' && S.drawing) {
    const pts = S.drawing.map(toScreen);
    ctx.beginPath();
    pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
    if (pts.length) ctx.lineTo(mouse[0], mouse[1]);
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]); ctx.stroke(); ctx.setLineDash([]);
    if (pts.length >= 3) {
      ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath();
      ctx.fillStyle = 'rgba(255,255,255,.12)'; ctx.fill();
    }
    pts.forEach((p, i) => {
      shapeCircle(p[0], p[1], i === 0 && pts.length >= 3 ? 7 : 4);
      ctx.fillStyle = i === 0 && pts.length >= 3 ? '#8ab4f8' : '#fff'; ctx.fill();
      ctx.strokeStyle = '#000'; ctx.lineWidth = 1; ctx.stroke();
    });
  }
  // --- edge mode: source/target highlight and rubber band
  if (S.mode === 'edge') {
    const outline = (rid, color, width) => {
      const reg = rl.regions[rid];
      if (!reg || !reg.poly) return;
      const pts = reg.poly.map(toScreen);
      ctx.beginPath();
      pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
      ctx.closePath();
      ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
      ctx.fillStyle = color.replace('rgb', 'rgba').replace(')', ',.14)');
      ctx.fill();
    };
    if (S.edgeHover && S.edgeHover !== S.edgeFrom) outline(S.edgeHover, 'rgb(129,201,149)', 2);
    if (S.edgeFrom) {
      outline(S.edgeFrom, 'rgb(255,233,168)', 2.5);
      const A = toScreen(regionCentroid(S.room, S.edgeFrom));
      const B = S.edgeHover && S.edgeHover !== S.edgeFrom
        ? toScreen(regionCentroid(S.room, S.edgeHover)) : mouse;
      ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]);
      ctx.strokeStyle = '#ffe9a8'; ctx.lineWidth = 2; ctx.setLineDash([7, 5]); ctx.stroke(); ctx.setLineDash([]);
      const ang = Math.atan2(B[1] - A[1], B[0] - A[0]);
      ctx.beginPath();
      ctx.moveTo(B[0], B[1]);
      ctx.lineTo(B[0] - 11 * Math.cos(ang - 0.4), B[1] - 11 * Math.sin(ang - 0.4));
      ctx.lineTo(B[0] - 11 * Math.cos(ang + 0.4), B[1] - 11 * Math.sin(ang + 0.4));
      ctx.closePath(); ctx.fillStyle = '#ffe9a8'; ctx.fill();
    }
  }
  // --- placement marker
  if (S.placing && S.hover === null) {
    shapeHex(mouse[0], mouse[1], 10); ctx.strokeStyle = '#fff'; ctx.setLineDash([3, 3]); ctx.lineWidth = 1.5; ctx.stroke(); ctx.setLineDash([]);
  }
}
function connGeom(rl, c) {
  const A = toScreen(regionCentroid(S.room, c.from));
  const B = toScreen(regionCentroid(S.room, c.to));
  const rev = !!findConn(rl, c.to, c.from);
  const dx = B[0] - A[0], dy = B[1] - A[1];
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len, nx = -uy, ny = ux;
  const off = rev ? clamp(len * 0.15, 18, 70) : 0;
  const pad = Math.min(24, len / 3);
  const a = [A[0] + ux * pad, A[1] + uy * pad], b = [B[0] - ux * pad, B[1] - uy * pad];
  const m = [(a[0] + b[0]) / 2 + nx * off * 2, (a[1] + b[1]) / 2 + ny * off * 2];
  const pts = [];
  for (let i = 0; i <= 16; i++) {
    const t = i / 16, s = 1 - t;
    pts.push([s * s * a[0] + 2 * s * t * m[0] + t * t * b[0], s * s * a[1] + 2 * s * t * m[1] + t * t * b[1]]);
  }
  return { a, b, m, pts, mid: pts[8], tan: [b[0] - m[0], b[1] - m[1]] };
}
function drawConn(rl, c) {
  const g = connGeom(rl, c);
  const isSel = S.sel.type === 'conn' && S.sel.from === c.from && S.sel.to === c.to;
  const isHov = S.hover && S.hover.type === 'conn' && S.hover.conn === c;
  const color = isSel ? '#ffffff' : isHov ? '#ffe9a8' : hexA(regionColor(S.room, c.from), 1);
  const never = Logic.reqIsNever(c.req, S.tier);
  const path = () => { ctx.beginPath(); ctx.moveTo(g.a[0], g.a[1]); ctx.quadraticCurveTo(g.m[0], g.m[1], g.b[0], g.b[1]); };
  path(); ctx.strokeStyle = 'rgba(0,0,0,.6)'; ctx.lineWidth = isSel ? 6 : 5; ctx.setLineDash([]); ctx.stroke();
  path(); ctx.strokeStyle = color; ctx.lineWidth = isSel ? 3 : 2;
  if (c.unsure) ctx.setLineDash([7, 5]); else if (never) ctx.setLineDash([2, 4]);
  ctx.stroke(); ctx.setLineDash([]);
  const tl = Math.hypot(g.tan[0], g.tan[1]) || 1, tx = g.tan[0] / tl, ty = g.tan[1] / tl;
  ctx.beginPath();
  ctx.moveTo(g.b[0], g.b[1]);
  ctx.lineTo(g.b[0] - tx * 11 - ty * 5, g.b[1] - ty * 11 + tx * 5);
  ctx.lineTo(g.b[0] - tx * 11 + ty * 5, g.b[1] - ty * 11 - tx * 5);
  ctx.closePath(); ctx.fillStyle = color; ctx.fill(); ctx.strokeStyle = 'rgba(0,0,0,.6)'; ctx.lineWidth = 1; ctx.stroke();
  let rect = null;
  if (S.layers.labels) {
    const txt = (c.unsure ? '? ' : '') + reqShort(c.req, S.tier);
    rect = pill(txt, g.mid[0], g.mid[1], { color: never ? '#ff9e9e' : '#fff', border: isSel ? '#fff' : null, size: 10 });
  }
  connShapes.push({ conn: c, pts: g.pts, rect });
}

// =====================================================================
// Hit-test
// =====================================================================
function hitTest(sx, sy) {
  const rl = RL();
  const nodes = roomNodes(S.room);
  const p = [sx, sy];
  if (S.mode === 'select' && S.sel.type === 'region' && S.sel.rid !== 'main' && S.layers.regions) {
    const reg = rl.regions[S.sel.rid];
    if (reg && reg.poly) for (let i = 0; i < reg.poly.length; i++) if (dist(toScreen(reg.poly[i]), p) <= 8) return { type: 'vertex', i };
    // near a side of the selected region: do not deselect (allows the double click to insert a vertex)
    const si = sideHit(sx, sy);
    if (si >= 0) return { type: 'side', i: si, rid: S.sel.rid };
  }
  let best = null, bd = 13;
  for (const n of nodes.list) {
    if (!nodeVisible(n)) continue;
    const d = dist(toScreen(n.pos), p);
    if (d < bd) { bd = d; best = n; }
  }
  if (best) return { type: 'node', node: best };
  if (S.layers.gimmicks || S.layers.enemies) {
    const gs = W.gimmicks[S.room] || [];
    let bi = -1; bd = 7;
    for (let i = 0; i < gs.length; i++) {
      const g = gs[i];
      if (!(g.layer === 'enemies' ? S.layers.enemies : S.layers.gimmicks)) continue;
      const d = dist(toScreen(g.pos), p);
      if (d < bd) { bd = d; bi = i; }
    }
    if (bi >= 0) return { type: 'gimmick', idx: bi, g: gs[bi] };
  }
  if (S.layers.conns) for (const s of connShapes) {
    if (s.rect && sx >= s.rect[0] && sx <= s.rect[0] + s.rect[2] && sy >= s.rect[1] && sy <= s.rect[1] + s.rect[3]) return { type: 'conn', conn: s.conn };
    for (let i = 1; i < s.pts.length; i++) if (segDist(p, s.pts[i - 1], s.pts[i]) <= 6) return { type: 'conn', conn: s.conn };
  }
  if (S.layers.regions) {
    const rid = Logic.regionOfPoint(rl, toWorld(sx, sy));
    if (rid !== 'main') return { type: 'region', rid };
  }
  return null;
}
function sideHit(sx, sy) {
  const rl = RL();
  if (S.sel.type !== 'region' || S.sel.rid === 'main') return -1;
  const poly = rl.regions[S.sel.rid].poly || [];
  const p = [sx, sy];
  for (let i = 0; i < poly.length; i++) {
    const a = toScreen(poly[i]), b = toScreen(poly[(i + 1) % poly.length]);
    if (dist(a, p) <= 8 || dist(b, p) <= 8) continue;
    if (segDist(p, a, b) <= 6) return i;
  }
  return -1;
}

// =====================================================================
// Canvas interaction
// =====================================================================
function evPos(e) { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
function setMode(m) {
  S.mode = m;
  if (m !== 'poly') S.drawing = null;
  else { S.drawing = []; S.placing = null; S.activeVertex = null; }
  if (m !== 'edge') { S.edgeFrom = null; S.edgeHover = null; }
  else { S.placing = null; S.activeVertex = null; }
  for (const b of document.querySelectorAll('#tools button')) b.classList.toggle('active', b.dataset.mode === m);
  canvas.classList.toggle('mode-poly', m === 'poly');
  canvas.classList.toggle('mode-edge', m === 'edge');
  updateHint(); dirty = true;
}

// --- "Edge" mode: create connections by drawing on the canvas ---------
// Only between regions with a POLYGON: outside them is Main, and the user
// does not want edges to Main by accident (the idea is to keep pulling
// everything out of that bag). If a connection with Main is needed, the
// dropdown in the region panel is still there.
function polyRegionAt(sx, sy) {
  const rid = Logic.regionOfPoint(RL(), toWorld(sx, sy));
  return rid === 'main' ? null : rid;
}
function edgeGestureEnd(to, oneWay) {
  const from = S.edgeFrom;
  S.edgeFrom = null;
  if (!from || !to || from === to) { dirty = true; return; }
  const rl = RL();
  const had = !!findConn(rl, from, to), hadRev = !!findConn(rl, to, from);
  addConn(rl, from, to, !oneWay);            // it warns by itself if nothing was created
  if (had && (oneWay || hadRev)) return;
  flash((oneWay ? 'Connection ' : 'Bidirectional connection ') + regionName(S.room, from) + ' → ' + regionName(S.room, to) + ' (free: set its requirement)');
}
function select(sel, opts = {}) {
  S.sel = sel;
  if (sel.type !== 'region') S.activeVertex = null;
  renderInspector();
  renderTree();
  updateHint();
  dirty = true;
  if (opts.center) {
    if (sel.type === 'node') { const n = roomNodes(S.room).byId[sel.id]; if (n) centerOn(n.pos); }
    else if (sel.type === 'region') centerOn(regionCentroid(S.room, sel.rid), 0.3);
    else if (sel.type === 'conn') { const rl = RL(); const c = findConn(rl, sel.from, sel.to); if (c) { const g = connGeom(rl, c); centerOn(toWorld(g.mid[0], g.mid[1]), 0.3); } }
  }
}
function switchRoom(code, opts = {}) {
  if (!W.rooms[code]) return;
  const same = S.room === code;
  S.room = code;
  if (!same || opts.reset) { S.sel = { type: 'room' }; S.activeVertex = null; S.placing = null; if (S.mode === 'poly') setMode('select'); S.edgeFrom = null; S.edgeHover = null; fitView(); }
  renderTabs(); renderTree(); renderInspector(); renderReport(); updateHint();
  dirty = true;
  try { const u = new URL(location.href); u.searchParams.set('room', code); for (const k of ['select', 'region', 'conn']) u.searchParams.delete(k); history.replaceState(null, '', u); } catch (e) { /* nothing */ }
}
function nodePosSetter(n) {
  if (n.type === 'check') return (p) => { const q = placementIn(n.id, S.room); if (q) q.pos = p; };
  if (n.type === 'out') return (p) => { ensureEdge(n.edge.name).pos = p; };
  return (p) => { ensureEdge(n.edge.name).dst_pos = p; };
}
function bindCanvas() {
  canvas.addEventListener('mousedown', (e) => {
    if (document.activeElement && document.activeElement !== document.body && document.activeElement !== canvas) document.activeElement.blur();
    hideSearch();
    const [sx, sy] = evPos(e);
    if (e.button === 1 || (e.button === 0 && S.space)) {
      S.drag = { kind: 'pan', sx, sy, tx: V.tx, ty: V.ty, moved: false };
      e.preventDefault(); canvas.classList.add('grabbing'); return;
    }
    if (e.button !== 0) return;
    if (S.placing) { placeAt(toWorld(sx, sy)); return; }
    if (S.mode === 'poly') { polyClick(sx, sy); return; }
    if (S.mode === 'edge') {
      const rid = polyRegionAt(sx, sy);
      if (!rid) {   // Main / outside every polygon: cancel and let the canvas be dragged
        S.edgeFrom = null; dirty = true;
        S.drag = { kind: 'pan', sx, sy, tx: V.tx, ty: V.ty, moved: false };
        return;
      }
      if (S.edgeFrom && S.edgeFrom !== rid) { edgeGestureEnd(rid, e.shiftKey); return; }
      S.edgeFrom = rid;
      select({ type: 'region', rid });
      S.drag = { kind: 'edge', from: rid, moved: false };
      dirty = true; return;
    }
    const hit = hitTest(sx, sy);
    if (!hit) { S.drag = { kind: 'pan', sx, sy, tx: V.tx, ty: V.ty, moved: false, click: true }; return; }
    if (hit.type === 'vertex') {
      S.activeVertex = hit.i; pushUndo();
      S.drag = { kind: 'vertex', i: hit.i, moved: false };
      dirty = true; return;
    }
    if (hit.type === 'side') {
      if (e.shiftKey) { pushUndo(); S.drag = { kind: 'region', rid: hit.rid, last: toWorld(sx, sy), moved: false }; }
      return;   // the region stays selected; the double click inserts a vertex here
    }
    if (hit.type === 'node') {
      select({ type: 'node', id: hit.node.id });
      if (hit.node.placed) S.drag = { kind: 'node', node: hit.node, set: nodePosSetter(hit.node), moved: false, snap: false };
      return;
    }
    if (hit.type === 'gimmick') { select({ type: 'gimmick', idx: hit.idx }); return; }
    if (hit.type === 'conn') { select({ type: 'conn', from: hit.conn.from, to: hit.conn.to }); return; }
    if (hit.type === 'region') {
      if (e.shiftKey && S.sel.type === 'region' && S.sel.rid === hit.rid) {
        pushUndo();
        S.drag = { kind: 'region', rid: hit.rid, last: toWorld(sx, sy), moved: false };
      } else { select({ type: 'region', rid: hit.rid }); }
    }
  });
  window.addEventListener('mousemove', (e) => {
    if (!canvas) return;
    const [sx, sy] = evPos(e);
    mouse = [sx, sy];
    const d = S.drag;
    if (d) {
      if (d.kind === 'pan') {
        V.tx = d.tx + (sx - d.sx); V.ty = d.ty + (sy - d.sy);
        if (Math.abs(sx - d.sx) + Math.abs(sy - d.sy) > 3) d.moved = true;
        dirty = true; return;
      }
      const wp = toWorld(sx, sy).map(Math.round);
      if (d.kind === 'vertex') {
        const poly = RL().regions[S.sel.rid].poly;
        poly[d.i] = wp; d.moved = true; touch();
      } else if (d.kind === 'node') {
        if (!d.snap) { pushUndo(); d.snap = true; }
        d.set(wp); d.moved = true; touch();
      } else if (d.kind === 'edge') {
        S.edgeHover = polyRegionAt(sx, sy);
        dirty = true;
      } else if (d.kind === 'region') {
        const cur = toWorld(sx, sy);
        const dx = cur[0] - d.last[0], dy = cur[1] - d.last[1];
        const poly = RL().regions[d.rid].poly;
        for (const p of poly) { p[0] = Math.round(p[0] + dx); p[1] = Math.round(p[1] + dy); }
        d.last = cur; d.moved = true; touch();
      }
      return;
    }
    if (e.target !== canvas) { if (S.hover) { S.hover = null; hideTooltip(); dirty = true; } return; }
    if (S.mode === 'poly') { dirty = true; return; }
    if (S.mode === 'edge') {
      if (S.hover) { S.hover = null; hideTooltip(); dirty = true; }
      const rid = polyRegionAt(sx, sy);
      if (rid !== S.edgeHover) { S.edgeHover = rid; dirty = true; }
      canvas.classList.toggle('pointer', false);
      if (S.edgeFrom) dirty = true;
      return;
    }
    if (S.placing) { dirty = true; return; }
    const hit = hitTest(sx, sy);
    const prev = S.hover;
    S.hover = hit;
    if (JSON.stringify(prev && [prev.type, prev.i, prev.idx, prev.rid, prev.node && prev.node.id, prev.conn && prev.conn.from + prev.conn.to]) !==
        JSON.stringify(hit && [hit.type, hit.i, hit.idx, hit.rid, hit.node && hit.node.id, hit.conn && hit.conn.from + hit.conn.to])) dirty = true;
    showTooltipFor(hit, sx, sy);
    canvas.classList.toggle('pointer', !!hit && hit.type !== 'vertex' && hit.type !== 'side');
    canvas.classList.toggle('move', !!hit && hit.type === 'vertex');
    canvas.classList.toggle('side', !!hit && hit.type === 'side');
  });
  window.addEventListener('mouseup', (e) => {
    const d = S.drag;
    if (!d) return;
    S.drag = null;
    canvas.classList.remove('grabbing');
    if (d.kind === 'pan') {
      if (!d.moved && d.click && S.mode === 'select') { S.activeVertex = null; select({ type: 'room' }); }
      return;
    }
    if (d.kind === 'edge') {
      // drag: released over the target. Click without dragging: the source
      // stays pinned and the next click picks the target.
      const to = polyRegionAt(mouse[0], mouse[1]);
      if (to && to !== d.from) edgeGestureEnd(to, e && e.shiftKey);
      dirty = true; return;
    }
    if (d.moved) changed();
    else if (d.kind !== 'node') S.undo.pop();
  });
  canvas.addEventListener('mouseleave', () => { if (S.hover) { S.hover = null; hideTooltip(); dirty = true; } });
  canvas.addEventListener('dblclick', (e) => {
    const [sx, sy] = evPos(e);
    if (S.mode === 'poly') { closePolygon(); return; }
    if (S.placing) return;
    const i = sideHit(sx, sy);
    if (i >= 0) {
      const wp = toWorld(sx, sy).map(Math.round);
      edit(() => { RL().regions[S.sel.rid].poly.splice(i + 1, 0, wp); }, { keepInspector: true });
      S.activeVertex = i + 1;
    }
  });
  canvas.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const [sx, sy] = evPos(e);
    if (S.mode === 'poly') { if (S.drawing && S.drawing.length) S.drawing.pop(); dirty = true; updateHint(); return; }
    const hit = hitTest(sx, sy);
    if (hit && hit.type === 'vertex') deleteVertex(hit.i);
  });
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const [sx, sy] = evPos(e);
    zoomAt(sx, sy, e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });
  canvas.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  canvas.addEventListener('drop', (e) => {
    e.preventDefault();
    let data = null;
    try { data = JSON.parse(e.dataTransfer.getData('text/plain')); } catch (err) { return; }
    if (!data || !data.kind) return;
    const [sx, sy] = evPos(e);
    S.placing = data;
    placeAt(toWorld(sx, sy));
  });
  const ro = new ResizeObserver(() => resizeCanvas());
  ro.observe($('#canvas-wrap'));
}
function resizeCanvas() {
  const wrap = $('#canvas-wrap');
  const dpr = window.devicePixelRatio || 1;
  cw = Math.max(1, wrap.clientWidth); ch = Math.max(1, wrap.clientHeight);
  canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
  dirty = true;
}
function polyClick(sx, sy) {
  if (!S.drawing) S.drawing = [];
  if (S.drawing.length >= 3 && dist(toScreen(S.drawing[0]), [sx, sy]) <= 10) { closePolygon(); return; }
  S.drawing.push(toWorld(sx, sy).map(Math.round));
  dirty = true; updateHint();
}
async function closePolygon() {
  const pts = (S.drawing || []).slice();
  while (pts.length > 1 && dist(toScreen(pts[pts.length - 1]), toScreen(pts[pts.length - 2])) < 4) pts.pop();
  if (pts.length < 3) { updateHint(); return; }
  const rl = RL();
  const n = Object.keys(rl.regions).length;
  const name = await askText('Name of the new region', 'Region ' + n);
  if (name === null) { S.drawing = []; dirty = true; updateHint(); return; }
  let rid = slugify(name) || 'region';
  if (rid === 'main' || /^\d/.test(rid)) rid = 'r-' + rid;
  const base = rid; let k = 2;
  while (rl.regions[rid]) rid = base + '-' + (k++);
  const used = new Set(Object.values(rl.regions).map(r => r.color));
  const color = PALETTE.find(c => !used.has(c)) || PALETTE[(n - 1) % PALETTE.length];
  edit(() => { rl.regions[rid] = { name: name.trim() || rid, poly: pts, color, note: '' }; });
  S.drawing = null;
  setMode('select');
  select({ type: 'region', rid });
}
function deleteVertex(i) {
  const rl = RL();
  if (S.sel.type !== 'region' || S.sel.rid === 'main') return;
  const poly = rl.regions[S.sel.rid].poly;
  if (!poly || poly.length <= 3) { flash('A polygon needs at least 3 vertices'); return; }
  edit(() => { poly.splice(i, 1); }, { keepInspector: true });
  S.activeVertex = null;
}
function deleteSelection() {
  const rl = RL();
  const s = S.sel;
  if (s.type === 'region' && s.rid !== 'main' && S.activeVertex != null) { deleteVertex(S.activeVertex); return; }
  if (s.type === 'conn') { edit(() => { rl.conns = rl.conns.filter(c => !(c.from === s.from && c.to === s.to)); }); select({ type: 'room' }); return; }
  if (s.type === 'region') { if (s.rid !== 'main') deleteRegion(s.rid); return; }
  if (s.type === 'node') {
    const n = roomNodes(S.room).byId[s.id];
    if (n && n.placed) removePlacement(n);
  }
}
function deleteRegion(rid) {
  const rl = RL();
  edit(() => {
    delete rl.regions[rid];
    rl.conns = rl.conns.filter(c => c.from !== rid && c.to !== rid);
    for (const k of Object.keys(rl.members)) if (rl.members[k] === rid) delete rl.members[k];
  });
  select({ type: 'room' });
}
function removePlacement(n) {
  const rl = RL();
  edit(() => {
    if (n.type === 'check') { setPlacements(n.id, placementsOf(n.id).filter(q => q.room !== S.room)); delete rl.members[n.id]; }
    else if (n.type === 'out') { const e = ensureEdge(n.edge.name); e.pos = null; pruneEdge(n.edge.name); delete rl.members[n.id]; }
    else { const e = ensureEdge(n.edge.name); e.dst_pos = null; pruneEdge(n.edge.name); delete rl.members[n.id]; }
  });
  if (n.type === 'check') select({ type: 'loc', name: n.id }); else select({ type: 'room' });
}
function startPlacing(data) {
  S.placing = data; S.hover = null;
  if (S.mode === 'poly') setMode('select');
  canvas.classList.add('placing');
  updateHint(); dirty = true;
}
function stopPlacing() { S.placing = null; canvas.classList.remove('placing'); updateHint(); dirty = true; }
function placeAt(wp) {
  const d = S.placing;
  if (!d) return;
  const p = wp.map(Math.round);
  const room = S.room;
  let sel = null;
  if (d.kind === 'loc') {
    if (!W.locations[d.id]) return;
    edit(() => { const arr = placementsOf(d.id).filter(q => q.room !== room); arr.push({ room, pos: p }); setPlacements(d.id, arr); });
    sel = { type: 'node', id: d.id };
  } else if (d.kind === 'out') {
    const e = W.edges.find(x => x.name === d.id);
    if (!e || e.src !== room) { flash('That exit belongs to ' + (e ? roomLabel(e.src) : '?')); stopPlacing(); return; }
    edit(() => { ensureEdge(d.id).pos = p; });
    sel = { type: 'node', id: d.id };
  } else if (d.kind === 'in') {
    const e = W.edges.find(x => x.name === d.id);
    if (!e || e.dst !== room) { flash('That landing belongs to ' + (e ? roomLabel(e.dst) : '?')); stopPlacing(); return; }
    edit(() => { ensureEdge(d.id).dst_pos = p; });
    sel = { type: 'node', id: d.id + '@in' };
  }
  stopPlacing();
  if (sel) select(sel);
}
function autoPlaceHubWarps() {
  const hub = W.hub;
  const todo = W.edges.filter(e => e.kind === 'warp' && e.src === hub && !e.pos && !(DOC.edges[e.name] && DOC.edges[e.name].pos));
  if (!todo.length) { flash('No unplaced hub warps left'); return; }
  edit(() => {
    for (const e of todo) {
      const letter = e.dst[0].toUpperCase();
      const y = W.hub_floor_y[letter];
      if (y == null) continue;
      ensureEdge(e.name).pos = [letter === 'N' ? 560 : 368, y];
    }
  });
  flash(todo.length + ' warps placed');
}

// =====================================================================
// Keyboard
// =====================================================================
function bindKeys() {
  window.addEventListener('keydown', (e) => {
    const t = e.target;
    const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
    if (e.key === 'Escape') {
      if (!$('#modal').hidden) return;
      if (typing) { t.blur(); hideSearch(); return; }
      if (!$('#help-panel').hidden) { $('#help-panel').hidden = true; return; }
      if (!$('#gates-panel').hidden) { $('#gates-panel').hidden = true; return; }
      if (S.placing) { stopPlacing(); return; }
      if (S.mode === 'edge') { if (S.edgeFrom) { S.edgeFrom = null; dirty = true; } else setMode('select'); return; }
      if (S.mode === 'poly') { setMode('select'); return; }
      if (S.activeVertex != null) { S.activeVertex = null; dirty = true; return; }
      select({ type: 'room' });
      return;
    }
    if (typing) return;
    if (!$('#modal').hidden) return;
    const k = e.key;
    if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
    if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'y') { e.preventDefault(); redo(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    switch (k) {
      case 'v': case 'V': setMode('select'); break;
      case 'p': case 'P': setMode('poly'); break;
      case 'a': case 'A': setMode('edge'); break;
      case 'Delete': deleteSelection(); break;
      case 'Enter': if (S.mode === 'poly') closePolygon(); break;
      case '0': fitView(); break;
      case '+': case '=': zoomAt(cw / 2, ch / 2, 1.25); break;
      case '-': case '_': zoomAt(cw / 2, ch / 2, 1 / 1.25); break;
      case 'f': case 'F': e.preventDefault(); $('#search').focus(); $('#search').select(); break;
      case '?': togglePanel('help-panel'); break;
      case ' ': if (!S.space) { S.space = true; canvas.classList.add('grab'); } e.preventDefault(); break;
      default: return;
    }
  });
  window.addEventListener('keyup', (e) => { if (e.key === ' ') { S.space = false; canvas.classList.remove('grab'); } });
  window.addEventListener('beforeunload', (e) => {
    if (S.docVersion !== S.savedVersion || S.saving) { e.preventDefault(); e.returnValue = ''; }
  });
}

// =====================================================================
// Saving and report
// =====================================================================
function setStatus(text, cls) { const el = $('#status'); el.textContent = text; el.className = 'status ' + (cls || ''); }
function scheduleSave() {
  clearTimeout(S.saveTimer);
  setStatus('Unsaved', 'dirty');
  S.saveTimer = setTimeout(doSave, 600);
}
async function doSave() {
  if (S.saving) { S.savePending = true; return; }
  S.saving = true;
  const v = S.docVersion;
  setStatus('Saving...', 'saving');
  try {
    const r = await fetch('/api/logic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(DOC) });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const rep = await r.json();
    if (rep.error) throw new Error(rep.error);
    S.report = rep;
    if (S.docVersion === v) { S.savedVersion = v; setStatus('Saved', 'ok'); }
    renderReport(); renderTabs();
  } catch (err) {
    setStatus('Error: ' + err.message, 'error');
  } finally {
    S.saving = false;
    if (S.savePending) { S.savePending = false; doSave(); }
  }
}
async function doValidate() {
  setStatus('Validating...', 'saving');
  try {
    const r = await fetch('/api/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(DOC) });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    S.report = await r.json();
    renderReport(); renderTabs();
    setStatus(S.docVersion === S.savedVersion ? 'Saved' : 'Unsaved', S.docVersion === S.savedVersion ? 'ok' : 'dirty');
    $('#report-body').hidden = false; $('#report-toggle').textContent = '▾';
  } catch (err) { setStatus('Error: ' + err.message, 'error'); }
}
const ROOM_RE = /^([a-z]\d\d)\b/;
function reportRoomOf(text) { const m = ROOM_RE.exec(text); return m ? m[1] : null; }
function renderReport() {
  const rep = S.report || { errors: [], warnings: [] };
  const errs = rep.errors || [], warns = rep.warnings || [];
  const counter = $('#counter');
  counter.textContent = errs.length + ' error' + (errs.length === 1 ? '' : 's') + ' · ' + warns.length + ' warning' + (warns.length === 1 ? '' : 's');
  counter.className = 'counter ' + (errs.length ? 'has-err' : warns.length ? 'has-warn' : '');
  const sum = $('#report-summary');
  const parts = ['Report: ', h('span', { class: 'e' }, errs.length + ' errors'), ' · ', h('span', { class: 'w' }, warns.length + ' warnings'),
    ' · ' + (rep.unsure || 0) + ' unconfirmed · ' + (rep.unplaced || 0) + ' unplaced'];
  if (rep.txt === false) parts.push(h('span', { class: 'e' }, ' · logic.txt NOT regenerated (there are errors)'));
  sum.replaceChildren(...parts);
  const body = $('#report-body');
  body.replaceChildren();
  const items = errs.map(t => ({ t, cls: 'err' })).concat(warns.map(t => ({ t, cls: 'warn' })));
  if (!items.length) { body.append(h('div', { class: 'ok' }, 'No errors or warnings.')); return; }
  const here = [], other = [];
  for (const it of items) { it.room = reportRoomOf(it.t); (it.room === S.room ? here : other).push(it); }
  if (here.length) body.append(h('div', { class: 'dim' }, 'Current room (' + roomLabel(S.room) + '):'));
  for (const it of here.concat(other)) {
    body.append(h('div', { class: 'it ' + it.cls + (it.room === S.room ? ' here' : '') + (it.room ? ' jump' : ''), title: it.room ? 'Go to ' + roomLabel(it.room) : null,
      onclick: it.room ? () => switchRoom(it.room) : null }, it.t));
  }
}

// =====================================================================
// Top bar: tabs, layers, search
// =====================================================================
function renderTabs() {
  const areas = [];
  for (const r of W.room_order) { const a = W.rooms[r].area; if (!areas.includes(a)) areas.push(a); }
  const curArea = W.rooms[S.room].area;
  const at = $('#area-tabs');
  at.replaceChildren(...areas.map(a => h('button', { class: a === curArea ? 'active' : '', title: 'Area ' + areaLabel(a), onclick: () => switchRoom(W.room_order.find(r => W.rooms[r].area === a)) }, areaLabel(a))));
  const rt = $('#room-tabs');
  const rep = S.report || {};
  const counts = {};
  for (const t of (rep.errors || [])) { const r = reportRoomOf(t); if (r) counts[r] = counts[r] || { e: 0, w: 0 }, counts[r].e++; }
  for (const t of (rep.warnings || [])) { const r = reportRoomOf(t); if (r) counts[r] = counts[r] || { e: 0, w: 0 }, counts[r].w++; }
  rt.replaceChildren(...W.room_order.filter(r => W.rooms[r].area === curArea).map(r => {
    const c = counts[r];
    return h('button', { class: r === S.room ? 'active' : '', title: r + (c ? ' · ' + c.e + ' errors, ' + c.w + ' warnings' : ''), onclick: () => switchRoom(r) },
      roomLabel(r), c ? h('span', { class: 'badge' + (c.e ? ' err' : '') }, c.e || c.w) : null);
  }));
}
function renderLayers() {
  const el = $('#layers');
  el.replaceChildren(...LAYER_DEFS.map(([k, label]) => {
    const cb = h('input', { type: 'checkbox', checked: !!S.layers[k], onchange: () => { S.layers[k] = cb.checked; lab.classList.toggle('on', cb.checked); dirty = true; try { localStorage.setItem('mmzx-logic-layers', JSON.stringify(S.layers)); } catch (e) { /* nothing */ } } });
    const lab = h('label', { class: S.layers[k] ? 'on' : '', title: 'Layer: ' + label }, cb, label);
    return lab;
  }));
}
let searchItems = null, searchActive = -1;
function buildSearchIndex() {
  const items = [];
  for (const name of Object.keys(W.locations)) items.push({ kind: 'loc', name, text: name.toLowerCase(), k: 'location' });
  for (const r of W.room_order) for (const rid of Object.keys(DOC.rooms[r].regions)) items.push({ kind: 'region', room: r, rid, name: roomLabel(r) + ' / ' + regionName(r, rid), text: (roomLabel(r) + ' ' + regionName(r, rid) + ' ' + rid).toLowerCase(), k: 'region' });
  for (const e of W.edges) items.push({ kind: 'edge', name: e.name, text: e.name.toLowerCase(), k: 'edge', edge: e });
  return items;
}
function hideSearch() { $('#search-results').hidden = true; searchActive = -1; }
function runSearch() {
  const q = $('#search').value.trim().toLowerCase();
  const box = $('#search-results');
  if (!q) { hideSearch(); return; }
  const items = buildSearchIndex().filter(i => i.text.includes(q));
  items.sort((a, b) => a.text.indexOf(q) - b.text.indexOf(q) || a.name.length - b.name.length);
  searchItems = items.slice(0, 40);
  searchActive = searchItems.length ? 0 : -1;
  box.replaceChildren();
  if (!searchItems.length) box.append(h('div', { class: 'empty' }, 'No results'));
  searchItems.forEach((it, i) => {
    let where = '';
    if (it.kind === 'loc') { const [r] = checkPosition(it.name); where = r ? roomLabel(r) : 'unplaced [' + (W.locations[it.name].room || '?') + ']'; }
    else if (it.kind === 'edge') where = roomLabel(it.edge.src) + ' → ' + roomLabel(it.edge.dst);
    box.append(h('div', { class: 'item' + (i === searchActive ? ' active' : ''), onmousedown: (e) => { e.preventDefault(); goToSearch(it); } },
      h('span', { class: 'k' }, it.k), h('span', null, it.name), h('span', { class: 'r' }, where)));
  });
  box.hidden = false;
}
function goToSearch(it) {
  hideSearch(); $('#search').blur();
  if (it.kind === 'loc') {
    const [r] = checkPosition(it.name);
    if (r) { switchRoom(r); select({ type: 'node', id: it.name }, { center: true }); }
    else select({ type: 'loc', name: it.name });
  } else if (it.kind === 'region') { switchRoom(it.room); select({ type: 'region', rid: it.rid }, { center: true }); }
  else if (it.kind === 'edge') {
    switchRoom(it.edge.src);
    if (roomNodes(S.room).byId[it.name]) select({ type: 'node', id: it.name }, { center: true });
    else { switchRoom(it.edge.dst); if (roomNodes(S.room).byId[it.name + '@in']) select({ type: 'node', id: it.name + '@in' }, { center: true }); }
  }
}
function bindTop() {
  $('#tier').value = S.tier;
  $('#tier').addEventListener('change', (e) => { S.tier = e.target.value; dirty = true; renderInspector(); renderTree(); });
  $('#btn-validate').addEventListener('click', doValidate);
  $('#btn-txt').addEventListener('click', () => window.open('/api/txt', '_blank'));
  $('#btn-gates').addEventListener('click', () => { S.gatesTarget = null; togglePanel('gates-panel'); });
  $('#btn-help').addEventListener('click', () => togglePanel('help-panel'));
  $('#counter').addEventListener('click', toggleReport);
  $('#report-head').addEventListener('click', toggleReport);
  for (const b of document.querySelectorAll('#tools button')) b.addEventListener('click', () => setMode(b.dataset.mode));
  $('#zoom-in').addEventListener('click', () => zoomAt(cw / 2, ch / 2, 1.25));
  $('#zoom-out').addEventListener('click', () => zoomAt(cw / 2, ch / 2, 1 / 1.25));
  $('#zoom-fit').addEventListener('click', fitView);
  for (const b of document.querySelectorAll('.panel-close')) b.addEventListener('click', () => { $('#' + b.dataset.close).hidden = true; });
  const si = $('#search');
  si.addEventListener('input', runSearch);
  si.addEventListener('focus', runSearch);
  si.addEventListener('blur', () => setTimeout(hideSearch, 150));
  si.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); if (searchItems && searchItems[searchActive]) goToSearch(searchItems[searchActive]); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!searchItems || !searchItems.length) return;
      searchActive = (searchActive + (e.key === 'ArrowDown' ? 1 : -1) + searchItems.length) % searchItems.length;
      const kids = $('#search-results').children;
      for (let i = 0; i < kids.length; i++) kids[i].classList.toggle('active', i === searchActive);
      if (kids[searchActive]) kids[searchActive].scrollIntoView({ block: 'nearest' });
    }
  });
}
function toggleReport() {
  const b = $('#report-body');
  b.hidden = !b.hidden;
  $('#report-toggle').textContent = b.hidden ? '▴' : '▾';
}
function togglePanel(id) {
  const p = $('#' + id);
  p.hidden = !p.hidden;
  if (!p.hidden && id === 'gates-panel') renderGates();
}

// =====================================================================
// Left panel: room outline
// =====================================================================
const ICON = (n) => {
  const cls = 'ico ' + (n.placed ? 'hex' : n.type === 'check' ? 'sq' : n.type === 'out' ? 'tri' : 'cir');
  return h('span', { class: cls, style: 'background:' + n.color + ';color:' + n.color });
};
function renderTree() {
  const el = $('#tree');
  el.replaceChildren();
  if (!S.room) return;
  const rl = RL();
  const nodes = roomNodes(S.room);
  const order = { check: 0, out: 1, in: 2 };
  for (const rid of regionOrder(rl)) {
    const reg = rl.regions[rid];
    const members = nodes.list.filter(n => n.rid === rid).sort((a, b) => order[a.type] - order[b.type] || a.label.localeCompare(b.label));
    const key = S.room + '/' + rid;
    const collapsed = S.collapsed.has(key);
    const wrap = h('div', { class: 'tree-region' + (collapsed ? ' collapsed' : '') });
    const head = h('div', { class: 'tree-head' + (S.sel.type === 'region' && S.sel.rid === rid ? ' sel' : ''), title: 'Region ' + (reg.name || rid) + ' (' + rid + ')', onclick: () => select({ type: 'region', rid }, { center: true }) },
      h('span', { class: 'caret', onclick: (e) => { e.stopPropagation(); if (collapsed) S.collapsed.delete(key); else S.collapsed.add(key); renderTree(); } }, collapsed ? '▸' : '▾'),
      h('span', { class: 'sw', style: 'background:' + reg.color }),
      h('span', { class: 'name' }, reg.name || rid),
      h('span', { class: 'n' }, members.length));
    wrap.append(head);
    const list = h('div', { class: 'tree-nodes' });
    for (const n of members) list.append(treeNode(n));
    if (!members.length) list.append(h('div', { class: 'empty dim' }, 'empty'));
    wrap.append(list);
    el.append(wrap);
  }
  // unplaced
  const sec = h('div', { class: 'tree-section' }, h('h4', null, 'Unplaced'));
  const un = nodes.un;
  const hubTodo = S.room === W.hub ? un.outs.filter(e => e.kind === 'warp' && !e.pos) : [];
  if (hubTodo.length) sec.append(h('div', { class: 'actions' }, h('button', { class: 'small', title: 'Places each "z01 transerver to X" warp at (368, floor of the target area); N at x=560', onclick: autoPlaceHubWarps }, 'Auto-place hub warps (' + hubTodo.length + ')')));
  if (un.outs.length) {
    sec.append(h('div', { class: 'sub' }, 'Exits of ' + roomLabel(S.room) + ' without a position (' + un.outs.length + ')'));
    for (const e of un.outs) sec.append(unplacedRow({ kind: 'out', id: e.name }, { type: 'out', placed: true, color: e.key ? (KEY_COLOR[e.key] || NOKEY) : NOKEY }, e.name, '→ ' + roomLabel(e.dst)));
  }
  if (un.ins.length) {
    sec.append(h('div', { class: 'sub' }, 'Landings in ' + roomLabel(S.room) + ' without a position (' + un.ins.length + ')'));
    for (const e of un.ins) sec.append(unplacedRow({ kind: 'in', id: e.name }, { type: 'in', placed: true, color: IN_COLOR }, e.name, '← ' + roomLabel(e.src)));
  }
  const multi = multiCandidates().filter(n => !placementIn(n, S.room));
  if (multi.length) {
    sec.append(h('div', { class: 'sub', title: 'Obtained in any of several rooms (area tag with "/"): place them in each one; in the logic any of them counts (OR)' }, 'With several possible rooms: also place in (' + multi.length + ')'));
    for (const name of multi) {
      const loc = W.locations[name];
      const done = placementsOf(name).map(q => roomLabel(q.room)).join(', ');
      sec.append(unplacedRow({ kind: 'loc', id: name }, { type: 'check', placed: true, color: catColor(loc.category) }, name, placementsOf(name).length + '/' + altRooms(name) + ' · already in ' + done, S.sel.type === 'loc' && S.sel.name === name, () => select({ type: 'loc', name })));
    }
  }
  const locs = unplacedLocations();
  sec.append(h('div', { class: 'sub' }, 'Game locations without a room (' + locs.length + ')'));
  if (!locs.length) sec.append(h('div', { class: 'empty' }, 'none'));
  for (const name of locs) {
    const loc = W.locations[name];
    sec.append(unplacedRow({ kind: 'loc', id: name }, { type: 'check', placed: true, color: catColor(loc.category) }, name, '[' + (loc.room || '?') + ']', S.sel.type === 'loc' && S.sel.name === name, () => select({ type: 'loc', name })));
  }
  el.append(sec);
}
function treeNode(n) {
  const row = h('div', { class: 'tree-node' + (S.sel.type === 'node' && S.sel.id === n.id ? ' sel' : ''), title: nodeTooltip(n),
    onclick: () => select({ type: 'node', id: n.id }, { center: true }) },
    ICON(n), h('span', { class: 'lbl' }, n.type === 'check' ? n.name : n.label),
    n.pinned ? h('span', { class: 'pin', title: 'Region pinned by hand' }, '📌') : null,
    n.type !== 'check' ? h('span', { class: 'tag' }, n.edge.key ? (isLockedKey(n.edge) ? '🔒 locked' : n.edge.key.replace(' Card Key', '')) : (n.edge.gate != null ? 'gate ' + n.edge.gate : '')) : null);
  return row;
}
function unplacedRow(data, fake, name, tag, isSel, onclick) {
  const row = h('div', { class: 'tree-node drag' + (isSel ? ' sel' : ''), draggable: true, title: name + '\nDrag onto the canvas or press "Place" and click on the canvas',
    ondragstart: (e) => { e.dataTransfer.setData('text/plain', JSON.stringify(data)); e.dataTransfer.effectAllowed = 'copy'; },
    onclick: onclick || null },
    ICON(fake), h('span', { class: 'lbl' }, name), h('span', { class: 'tag' }, tag),
    h('button', { class: 'place', title: 'Place in this room: click on the canvas', onclick: (e) => { e.stopPropagation(); startPlacing(data); } }, 'Place'));
  return row;
}

// =====================================================================
// Requirement editor (reusable component)
// =====================================================================
function reqEditor(opts) {
  const root = h('div', { class: 'req' });
  const tiers = Logic.tiers();
  function current() { return opts.get(); }
  function setReq(req) { opts.set(req); build(); }
  function setTier(tier, dnf) {
    const req = Object.assign({}, current() || {});
    if (dnf === null || (tier !== tiers[0] && dnf.length === 0)) delete req[tier]; else req[tier] = dnf;
    if (req[tiers[0]] === undefined) req[tiers[0]] = [];
    setReq(req);
  }
  function build() {
    root.replaceChildren();
    const req = current();
    if (opts.nullable) {
      const cb = h('input', { type: 'checkbox', checked: req == null, onchange: () => setReq(cb.checked ? null : { [tiers[0]]: [[]] }) });
      root.append(h('label', { class: 'req-null', title: 'null in the document' }, cb, opts.nullLabel || 'No requirement (free)'));
      if (req == null) return;
    }
    const r = req || {};
    for (const tier of tiers) root.append(tierBlock(tier, r[tier] === undefined ? null : r[tier]));
    const sum = h('div', { class: 'summary' });
    for (const tier of tiers) sum.append(h('div', null, tier + ': ' + reqUiText(r, tier) + (tier !== tiers[0] ? '  (+ ' + tiers.slice(0, tiers.indexOf(tier)).join(', ') + ')' : '')));
    sum.append(h('div', { class: 'hint' }, 'expert extends normal: in expert the alternatives of normal also count.'));
    root.append(sum);
  }
  function tierBlock(tier, dnf) {
    const alts = dnf || [];
    const blk = h('div', { class: 'tier' });
    blk.append(h('div', { class: 'tier-head' },
      h('span', { class: 'tname' }, tier),
      h('span', { class: 'thint' }, tier === tiers[0] ? '' : '(extends ' + tiers[0] + ')'),
      h('span', { class: 'spacer' }),
      h('button', { title: 'Free: one empty alternative [[]]', onclick: () => setTier(tier, [[]]) }, 'Free'),
      h('button', { title: 'Impossible: no alternatives []', onclick: () => setTier(tier, []) }, 'Impossible'),
      h('button', { title: 'Add an alternative (OR)', onclick: () => setTier(tier, alts.concat([[]])) }, '+ alternative')));
    if (!alts.length) blk.append(h('div', { class: 'none' }, tier === tiers[0] ? 'no alternatives: impossible in ' + tier + (dnf === null ? '' : '') : 'no alternatives of its own (only those of ' + tiers[0] + ')'));
    alts.forEach((alt, ai) => {
      const row = h('div', { class: 'alt' }, h('span', { class: 'or' }, ai ? 'or' : ''));
      if (!alt.length) row.append(h('span', { class: 'chip free', title: 'Empty alternative = free' }, 'free'));
      alt.forEach((atom, xi) => {
        row.append(h('span', { class: 'chip g-' + Logic.groupOf(atom), title: atomLabel(atom) }, atom,
          h('span', { class: 'x', title: 'Remove', onclick: () => { const na = alts.map(a => a.slice()); na[ai].splice(xi, 1); setTier(tier, na); } }, '×')));
        if (xi < alt.length - 1) row.append(h('span', { class: 'dim' }, '&'));
      });
      row.append(atomSelect((atom) => { const na = alts.map(a => a.slice()); if (!na[ai].includes(atom)) na[ai].push(atom); setTier(tier, na); }));
      row.append(h('span', { class: 'rm', title: 'Remove this alternative', onclick: () => { const na = alts.map(a => a.slice()); na.splice(ai, 1); setTier(tier, na); } }, '×'));
      blk.append(row);
    });
    const inp = h('input', { type: 'text', value: dnf === null ? '' : Logic.dnfToText(dnf), placeholder: 'expression: HX & (LX | FX) · free · never', title: 'Enter applies. Grammar of logic_format.parse_expr' });
    const err = h('div', { class: 'expr-err' });
    inp.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      const txt = inp.value.trim();
      if (!txt) { err.textContent = 'Empty: type free or never (impossible).'; return; }
      try { const parsed = Logic.parseExpr(txt); err.textContent = ''; setTier(tier, parsed); }
      catch (ex) { err.textContent = ex.message; }
    });
    blk.append(h('div', { class: 'expr' }, inp, h('button', { class: 'small', title: 'Apply the expression (Enter)', onclick: () => inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' })) }, '↵')), err);
    return blk;
  }
  build();
  return root;
}
function atomLabel(atom) { const a = W.atoms.find(x => x.id === atom); return a ? a.label : atom; }
function atomSelect(onPick) {
  const sel = h('select', { class: 'add-atom', title: 'Add an atom (AND)' }, h('option', { value: '' }, '+ atom'));
  const groups = {};
  for (const a of W.atoms) (groups[a.group] = groups[a.group] || []).push(a);
  for (const g of Object.keys(groups)) {
    const og = h('optgroup', { label: g });
    for (const a of groups[g]) og.append(h('option', { value: a.id }, a.id + ' - ' + a.label));
    sel.append(og);
  }
  sel.addEventListener('change', () => { if (sel.value) { onPick(sel.value); sel.value = ''; } });
  return sel;
}

// =====================================================================
// Inspector
// =====================================================================
function bindNote(getObj, key, el, opts = {}) {
  let snap = false;
  el.addEventListener('input', () => {
    if (!snap) { pushUndo(); snap = true; }
    getObj()[key] = el.value;
    if (opts.after) opts.after();
    changed({ keepInspector: true });
  });
  el.addEventListener('blur', () => { snap = false; if (opts.after) opts.after(); });
  return el;
}
function noteField(getObj, key = 'note', opts = {}) {
  const obj = (opts.peek || getObj)();   // peek: read without creating the entry
  return h('div', { class: 'field col' }, h('label', null, 'Note'), bindNote(getObj, key, h('textarea', { class: 'note', rows: 2, value: obj[key] || '', placeholder: 'free note' }), opts));
}
function unsureField(getObj, opts = {}) {
  const cur = (opts.peek || getObj)();
  const cb = h('input', { type: 'checkbox', checked: !!cur.unsure, onchange: () => { edit(() => { getObj().unsure = cb.checked; if (opts.after) opts.after(); }, { keepInspector: true }); } });
  return h('div', { class: 'field' }, h('label', { title: 'Rule not confirmed in-game ("?" in logic.txt)' }, cb, 'Unconfirmed in-game (?)'));
}
function regionSelectField(node) {
  const rl = RL();
  const sel = h('select', { title: 'Region of the node: automatic (geometry) or pinned by hand' },
    h('option', { value: '' }, 'Automatic: ' + regionName(S.room, node.autoRid)));
  for (const rid of regionOrder(rl)) sel.append(h('option', { value: rid, selected: node.pinned && node.rid === rid }, 'Pin to ' + regionName(S.room, rid)));
  sel.addEventListener('change', () => { edit(() => { if (sel.value === '') delete rl.members[node.id]; else rl.members[node.id] = sel.value; }); });
  return h('div', { class: 'field' }, h('label', null, 'Region'), sel,
    node.pinned ? h('button', { class: 'small', title: 'Back to geometric membership', onclick: () => edit(() => { delete rl.members[node.id]; }) }, 'Unpin') : null);
}
function kv(pairs) {
  const g = h('div', { class: 'kv' });
  for (const [k, v] of pairs) if (v != null && v !== '') g.append(h('span', { class: 'k' }, k), h('span', { class: 'v' }, v));
  return g;
}
function renderInspector() {
  const el = $('#inspector');
  el.replaceChildren();
  if (!S.room) return;
  const s = S.sel;
  const rl = RL();
  if (s.type === 'room') return inspectRoom(el, rl);
  if (s.type === 'region') return rl.regions[s.rid] ? inspectRegion(el, rl, s.rid) : inspectRoom(el, rl);
  if (s.type === 'conn') { const c = findConn(rl, s.from, s.to); return c ? inspectConn(el, rl, c) : inspectRoom(el, rl); }
  if (s.type === 'node') { const n = roomNodes(S.room).byId[s.id]; return n ? inspectNode(el, rl, n) : inspectRoom(el, rl); }
  if (s.type === 'loc') return inspectUnplacedLoc(el, s.name);
  if (s.type === 'gimmick') return inspectGimmick(el, s.idx);
}
function inspectRoom(el, rl) {
  const info = W.rooms[S.room];
  el.append(h('h2', null, 'Room ' + roomLabel(S.room)), h('div', { class: 'kind' }, S.room + ' · subarea ' + info.sub + ' · ' + info.size[0] + '×' + info.size[1] + ' px' + (W.transerver_access[S.room] ? ' · Transerver: ' + W.transerver_access[S.room] : '')));
  el.append(h('h3', null, 'Entry requirement (to be in the room)'));
  el.append(reqEditor({ nullable: true, nullLabel: 'No entry requirement', get: () => rl.req, set: (r) => edit(() => { rl.req = r; }, { keepInspector: true }) }));
  el.append(noteField(() => rl));
  el.append(h('h3', null, 'Regions (' + regionOrder(rl).length + ')'));
  const list = h('div', { class: 'list' });
  for (const rid of regionOrder(rl)) {
    const reg = rl.regions[rid];
    const nn = roomNodes(S.room).list.filter(n => n.rid === rid).length;
    const colorIn = h('input', { type: 'color', value: reg.color || '#8ab4f8', title: 'Color', onclick: (e) => e.stopPropagation(), onchange: () => edit(() => { reg.color = colorIn.value; }, { keepInspector: true }) });
    list.append(h('div', { class: 'row-item', onclick: () => select({ type: 'region', rid }, { center: true }) },
      colorIn, h('span', { class: 'grow' }, reg.name || rid, ' ', h('span', { class: 'dim' }, '(' + nn + ')')),
      h('button', { class: 'small', title: 'Rename', onclick: async (e) => { e.stopPropagation(); const nm = await askText('Region name', reg.name || rid); if (nm !== null && nm.trim()) edit(() => { reg.name = nm.trim(); }); } }, '✎'),
      rid !== 'main' ? h('button', { class: 'small danger', title: 'Delete the region (its nodes go back to the geometry)', onclick: (e) => { e.stopPropagation(); deleteRegion(rid); } }, '×') : null));
  }
  el.append(list);
  el.append(h('div', { class: 'actions' }, h('button', { title: 'Draw a polygon (P)', onclick: () => setMode('poly') }, '+ Region (draw polygon)')));
  el.append(h('h3', null, 'Connections (' + rl.conns.length + ')'));
  el.append(connList(rl, rl.conns));
  if (regionOrder(rl).length > 1) el.append(newConnForm(rl, 'main'));
}
function connList(rl, conns) {
  const list = h('div', { class: 'list' });
  if (!conns.length) list.append(h('div', { class: 'dim' }, 'none'));
  for (const c of conns) {
    const isSel = S.sel.type === 'conn' && S.sel.from === c.from && S.sel.to === c.to;
    list.append(h('div', { class: 'row-item' + (isSel ? ' sel' : ''), onclick: () => select({ type: 'conn', from: c.from, to: c.to }, { center: true }) },
      h('span', { class: 'sw', style: 'background:' + regionColor(S.room, c.from) }),
      h('span', { class: 'grow' }, regionName(S.room, c.from) + ' → ' + regionName(S.room, c.to)),
      c.unsure ? h('span', { class: 'unsure', title: 'unconfirmed' }, '?') : null,
      h('span', { class: 'req' }, reqShort(c.req, S.tier, 22))));
  }
  return list;
}
function newConnForm(rl, from) {
  const others = regionOrder(rl).filter(r => r !== from);
  if (!others.length) return h('div', { class: 'dim' }, 'Draw another region to be able to connect.');
  const sel = h('select', null, ...others.map(r => h('option', { value: r }, regionName(S.room, r))));
  const bi = h('input', { type: 'checkbox', checked: true });
  return h('div', { class: 'field', title: 'Create a directed connection from ' + regionName(S.room, from) },
    h('span', { class: 'lbl' }, 'New connection ' + regionName(S.room, from) + ' →'), sel,
    h('label', null, bi, 'bidirectional'),
    h('button', { class: 'primary small', onclick: () => addConn(rl, from, sel.value, bi.checked) }, 'Create'));
}
function addConn(rl, from, to, bidir) {
  if (from === to) return;
  const mk = (a, b) => ({ from: a, to: b, req: { [Logic.tiers()[0]]: [[]] }, unsure: false, note: '' });
  let created = 0;
  edit(() => {
    if (!findConn(rl, from, to)) { rl.conns.push(mk(from, to)); created++; }
    if (bidir && !findConn(rl, to, from)) { rl.conns.push(mk(to, from)); created++; }
  });
  if (!created) flash('That connection already exists');
  select({ type: 'conn', from, to });
}
// Boss arena: marks this region as the place where a boss is fought.
// The apworld ANDs the requirement the player sets in their YAML (boss_logic
// option) into EVERY edge that lands here, so without meeting it you do not
// get in, do not cross to the other side and do not pick up anything inside.
// NO requirement is written here: it only says where each boss is.
function bossOwner(bossId) {
  for (const [room, rl] of Object.entries(DOC.rooms || {}))
    for (const [rid, reg] of Object.entries(rl.regions || {}))
      if (reg.boss === bossId) return { room, rid };
  return null;
}
function bossField(reg, rid) {
  const roster = W.bosses || [];
  if (!roster.length) return h('div');
  const sel = h('select', { title: 'Marks this region as the arena of a boss (boss_logic option of the YAML)' },
    h('option', { value: '' }, '(none)'));
  for (const b of roster) {
    const own = bossOwner(b.id);
    const taken = own && !(own.room === S.room && own.rid === rid);
    sel.append(h('option', {
      value: b.id, disabled: taken ? 'disabled' : null,
      title: taken ? 'already tagged in ' + own.room + '/' + own.rid : b.room_label,
    }, b.name + ' (' + b.room_label + ')' + (taken ? ' - already in ' + own.room + '/' + own.rid : '')));
  }
  sel.value = reg.boss || '';
  sel.addEventListener('change', () => edit(() => {
    if (sel.value) reg.boss = sel.value; else delete reg.boss;
  }, { keepInspector: true }));
  const b = roster.find(x => x.id === reg.boss);
  const hint = b && b.room !== S.room
    ? h('div', { class: 'dim' }, '⚠️ ' + b.name + ' was expected in ' + b.room_label)
    : null;
  return h('div', { class: 'field col' }, h('label', null, 'Boss arena'), sel, hint);
}
function inspectRegion(el, rl, rid) {
  const reg = rl.regions[rid];
  const nodes = roomNodes(S.room).list.filter(n => n.rid === rid);
  el.append(h('h2', null, h('span', { class: 'sw', style: 'background:' + reg.color }), 'Region ', reg.name || rid), h('div', { class: 'kind' }, 'id ' + rid + ' · ' + (rid === 'main' ? 'rest of the room (no polygon)' : (reg.poly || []).length + ' vertices') + ' · ' + nodes.length + ' nodes'));
  const nameIn = h('input', { type: 'text', value: reg.name || '' });
  nameIn.addEventListener('change', () => { if (nameIn.value.trim()) edit(() => { reg.name = nameIn.value.trim(); }); });
  const colorIn = h('input', { type: 'color', value: reg.color || '#8ab4f8', onchange: () => edit(() => { reg.color = colorIn.value; }, { keepInspector: true }) });
  el.append(h('div', { class: 'field' }, h('label', null, 'Name'), nameIn, colorIn));
  el.append(bossField(reg, rid));
  el.append(noteField(() => reg));
  if (rid !== 'main') el.append(h('div', { class: 'actions' },
    h('button', { title: 'Vertices are dragged on the canvas; double click on a side inserts; right click deletes; Shift+drag moves', onclick: () => { setMode('select'); select({ type: 'region', rid }, { center: true }); flash('Edit the vertices on the canvas (see ? for the shortcuts)'); } }, 'Edit polygon'),
    h('button', { class: 'danger', title: 'Delete the region (Del)', onclick: () => deleteRegion(rid) }, 'Delete region')));
  el.append(h('h3', null, 'Member nodes (' + nodes.length + ')'));
  const list = h('div', { class: 'list' });
  if (!nodes.length) list.append(h('div', { class: 'dim' }, 'none'));
  for (const n of nodes) list.append(h('div', { class: 'row-item', title: nodeTooltip(n), onclick: () => select({ type: 'node', id: n.id }, { center: true }) }, ICON(n), h('span', { class: 'grow' }, n.type === 'check' ? n.name : n.label + '  ', n.type !== 'check' ? h('span', { class: 'dim mono' }, n.edge.name) : null), n.pinned ? h('span', { class: 'pin' }, '📌') : null));
  el.append(list);
  el.append(h('h3', null, 'Connections'));
  el.append(newConnForm(rl, rid));
  el.append(connList(rl, rl.conns.filter(c => c.from === rid || c.to === rid)));
}
function inspectConn(el, rl, c) {
  el.append(h('h2', null, 'Connection'), h('div', { class: 'kind' },
    h('span', { class: 'sw', style: 'background:' + regionColor(S.room, c.from) }), regionName(S.room, c.from), ' → ',
    h('span', { class: 'sw', style: 'background:' + regionColor(S.room, c.to) }), regionName(S.room, c.to)));
  el.append(h('h3', null, 'Requirement to pass'));
  el.append(reqEditor({ nullable: false, get: () => c.req || {}, set: (r) => edit(() => { c.req = r; }, { keepInspector: true }) }));
  el.append(unsureField(() => c));
  el.append(noteField(() => c));
  const rev = findConn(rl, c.to, c.from);
  el.append(h('div', { class: 'actions' },
    rev ? h('button', { onclick: () => select({ type: 'conn', from: c.to, to: c.from }) }, 'Go to the reverse') : h('button', { title: 'Create the connection in the opposite direction (free)', onclick: () => addConn(rl, c.to, c.from, false) }, 'Create the reverse'),
    h('button', { disabled: !!rev, title: rev ? 'The reverse already exists' : 'Swap source and target', onclick: () => { edit(() => { const f = c.from; c.from = c.to; c.to = f; }); select({ type: 'conn', from: c.from, to: c.to }); } }, 'Invert'),
    h('button', { class: 'danger', title: 'Delete (Del)', onclick: () => { S.sel = { type: 'conn', from: c.from, to: c.to }; deleteSelection(); } }, 'Delete')));
}
function inspectNode(el, rl, n) {
  if (n.type === 'check') {
    const loc = W.locations[n.id];
    el.append(h('h2', null, n.full), h('div', { class: 'kind' }, h('span', { class: 'sw', style: 'background:' + n.color }), catLabel(n.cat) + (n.placed ? ' · placed by hand' : '') + (loc.detect ? '' : ' · no detection')));
    const others = n.placed ? placementsOf(n.id).filter(q => q.room !== S.room).map(q => roomLabel(q.room)) : [];
    el.append(kv([['Room', roomLabel(S.room)], ['Position', n.pos[0] + ', ' + n.pos[1]], ['Area tag', n.placed ? loc.room : null],
      ['Also in', others.length ? others.join(', ') + ' (any of them counts: OR)' : null]]));
    el.append(regionSelectField(n));
    el.append(h('h3', null, 'Requirement to obtain the check'));
    el.append(reqEditor({ nullable: true, nullLabel: 'No requirement (being in the region is enough)', get: () => (DOC.checks[n.id] || {}).req || null, set: (r) => edit(() => { ensureCheck(n.id).req = r; pruneCheck(n.id); }, { keepInspector: true }) }));
    el.append(unsureField(() => ensureCheck(n.id), { peek: () => peekCheck(n.id), after: () => pruneCheck(n.id) }));
    el.append(noteField(() => ensureCheck(n.id), 'note', { peek: () => peekCheck(n.id), after: () => pruneCheck(n.id) }));
    if (n.placed) el.append(h('div', { class: 'actions' }, h('button', { class: 'danger', title: 'Remove the manual placement (goes back to "Unplaced")', onclick: () => removePlacement(n) }, 'Remove from the room')));
    return;
  }
  const e = n.edge;
  const ov = () => DOC.edges[e.name] || {};
  const other = n.type === 'out' ? e.dst : e.src;
  const otherId = n.type === 'out' ? e.name + '@in' : e.name;
  el.append(h('h2', null, n.type === 'out' ? 'Edge exit' : 'Edge landing'), h('div', { class: 'kind mono' }, e.name));
  const goBtn = h('button', { class: 'small', title: 'Go to ' + roomLabel(other), onclick: () => { switchRoom(other); if (roomNodes(other).byId[otherId]) select({ type: 'node', id: otherId }, { center: true }); } }, 'Go to ' + roomLabel(other));
  const pairs = [['Type', KIND_ES[e.kind] || e.kind], ['Position', n.pos[0] + ', ' + n.pos[1] + (n.placed ? ' (placed by hand)' : '')]];
  if (n.type === 'out') pairs.push(['Target', h('span', null, roomLabel(e.dst) + ' / ' + regionName(e.dst, landingRid(e)) + ' ', e.dst !== S.room ? goBtn : null)]);
  else pairs.push(['From', h('span', null, roomLabel(e.src) + ' / ' + regionName(e.src, roomNodes(e.src).members[e.name] || 'main') + ' ', e.src !== S.room ? goBtn : null)]);
  if (e.kind === 'internal') pairs.push(['Internal', 'joins ' + regionName(S.room, roomNodes(S.room).members[e.name] || 'main') + ' → ' + regionName(S.room, roomNodes(S.room).members[e.name + '@in'] || 'main')]);
  if (e.key) pairs.push(['Key', h('span', null, h('span', { class: 'sw', style: 'background:' + keyColor(e) }), e.key + (isLockedKey(e) ? ' - NOT in the pool: the door is LOCKED in the logic (in vanilla it is only crossed on the way back)' : ''))]);
  if (e.gate != null) pairs.push(['Gate', h('span', null, e.gate + ': ' + gateText(e.gate) + ' ', h('a', { class: 'link', onclick: () => { S.gatesTarget = String(e.gate); $('#gates-panel').hidden = false; renderGates(); } }, 'see gates'))]);
  if (e.kind === 'warp' && e.src === W.hub) pairs.push(['Transerver', W.transerver_access[e.dst] || 'no Transport destination']);
  if (e.kind === 'save') pairs.push(['Note', 'pads do not create a transition (NON_TRANSITION_KINDS)']);
  el.append(kv(pairs));
  el.append(regionSelectField(n));
  if (n.type === 'out') {
    el.append(h('h3', null, 'Extra cost to use the edge'));
    el.append(reqEditor({ nullable: true, nullLabel: 'No extra cost (only key, gate and entry of the target room)', get: () => ov().req || null, set: (r) => edit(() => { ensureEdge(e.name).req = r; pruneEdge(e.name); }, { keepInspector: true }) }));
    el.append(unsureField(() => ensureEdge(e.name), { peek: () => peekEdge(e.name), after: () => pruneEdge(e.name) }));
    el.append(noteField(() => ensureEdge(e.name), 'note', { peek: () => peekEdge(e.name), after: () => pruneEdge(e.name) }));
  } else {
    const o = ov();
    if (o.req || o.note) el.append(h('div', { class: 'dim' }, 'The edge rule is edited at its exit (' + roomLabel(e.src) + ').'));
  }
  if (n.placed) el.append(h('div', { class: 'actions' }, h('button', { class: 'danger', title: 'Remove the hand-placed position', onclick: () => removePlacement(n) }, 'Remove position')));
}
function inspectUnplacedLoc(el, name) {
  const loc = W.locations[name];
  if (!loc) return;
  const already = placementsOf(name);
  el.append(h('h2', null, name), h('div', { class: 'kind' }, h('span', { class: 'sw', style: 'background:' + catColor(loc.category) }), catLabel(loc.category) + (already.length ? ' · placed in ' + already.map(q => roomLabel(q.room)).join(', ') + ' (' + already.length + '/' + altRooms(name) + ' rooms)' : ' · UNPLACED')));
  el.append(kv([['Area tag', loc.room || '?'], ['Current rule', already.length ? 'reach any of its rooms (OR) ∧ requirement' : 'fallback by area tag (v0.2)']]));
  el.append(h('div', { class: 'actions' }, h('button', { class: 'primary', title: 'Click on the canvas of the current room to place it', onclick: () => startPlacing({ kind: 'loc', id: name }) }, 'Place in ' + roomLabel(S.room) + ' (click on the canvas)')));
  el.append(h('h3', null, 'Requirement to obtain the check'));
  el.append(reqEditor({ nullable: true, nullLabel: 'No requirement', get: () => (DOC.checks[name] || {}).req || null, set: (r) => edit(() => { ensureCheck(name).req = r; pruneCheck(name); }, { keepInspector: true }) }));
  el.append(unsureField(() => ensureCheck(name), { peek: () => peekCheck(name), after: () => pruneCheck(name) }));
  el.append(noteField(() => ensureCheck(name), 'note', { peek: () => peekCheck(name), after: () => pruneCheck(name) }));
}
function inspectGimmick(el, idx) {
  const g = (W.gimmicks[S.room] || [])[idx];
  if (!g) return;
  el.append(h('h2', null, g.name), h('div', { class: 'kind' }, g.layer === 'enemies' ? 'enemy' : 'gimmick'));
  el.append(kv([['Position', g.pos[0] + ', ' + g.pos[1]], ['kind / sub', g.kind + ' / ' + g.sub], ['role / mod', g.role + ' / ' + g.mod], ['Region', regionName(S.room, Logic.regionOfPoint(RL(), g.pos))]]));
  el.append(h('div', { class: 'dim' }, 'Informational only: gimmicks are not part of the logic.'));
}

// =====================================================================
// Gates panel
// =====================================================================
function renderGates() {
  const body = $('#gates-body');
  body.replaceChildren();
  const flags = Array.from(new Set(Object.keys(W.gate_edges).concat(Object.keys(DOC.gates)))).sort((a, b) => Number(a) - Number(b));
  if (!flags.length) { body.append(h('div', { class: 'dim' }, 'There are no event gates on the edges.')); return; }
  body.append(h('div', { class: 'dim', style: 'margin-bottom:8px' }, 'Full rule of an edge = key ∧ gate ∧ entry of the target room ∧ extra cost. "Free" gate = null: the client opens it.'));
  for (const flag of flags) {
    const g = DOC.gates[flag] || { req: null, note: '' };
    const edges = (W.gate_edges[flag] || []).map(n => W.edges.find(e => e.name === n)).filter(Boolean);
    const card = h('div', { class: 'gate' + (S.gatesTarget === flag ? ' target' : '') }, h('h4', null, 'Gate ' + flag, W.event_gates_open.includes(Number(flag)) ? h('span', { class: 'open' }, '  · the client opens it (EVENT_GATES_OPEN)') : null));
    const ed = h('div', { class: 'edges' });
    if (!edges.length) ed.append('no edges in data');
    for (const e of edges) ed.append(h('a', { class: 'link', onclick: () => { $('#gates-panel').hidden = true; switchRoom(e.src); if (roomNodes(e.src).byId[e.name]) select({ type: 'node', id: e.name }, { center: true }); } }, roomLabel(e.src) + ' → ' + roomLabel(e.dst) + '  (' + e.name + ')' + (e.key ? ' · ' + e.key : '')));
    card.append(ed);
    card.append(reqEditor({ nullable: true, nullLabel: 'Free: the client opens it (null)', get: () => (DOC.gates[flag] || {}).req || null, set: (r) => edit(() => { ensureGate(flag).req = r; }, { keepInspector: true }) }));
    card.append(noteField(() => ensureGate(flag), 'note', { peek: () => peekGate(flag) }));
    body.append(card);
    void g;
  }
  if (S.gatesTarget) { const t = body.querySelector('.gate.target'); if (t) t.scrollIntoView({ block: 'start' }); }
}

// =====================================================================
// Tooltip, hints, modal, notices
// =====================================================================
function showTooltipFor(hit, sx, sy) {
  const tt = $('#tooltip');
  if (!hit || hit.type === 'vertex' || hit.type === 'side') { hideTooltip(); return; }
  let text = '';
  if (hit.type === 'node') text = nodeTooltip(hit.node);
  else if (hit.type === 'gimmick') text = hit.g.name + ' (' + (hit.g.layer === 'enemies' ? 'enemy' : 'gimmick') + ') @ ' + hit.g.pos.join(',');
  else if (hit.type === 'conn') text = 'Connection ' + regionName(S.room, hit.conn.from) + ' → ' + regionName(S.room, hit.conn.to) + '\n' + Logic.reqToLines(hit.conn.req).join('\n') + (hit.conn.unsure ? '\n(unconfirmed)' : '') + (hit.conn.note ? '\n# ' + hit.conn.note : '');
  else if (hit.type === 'region') { const r = RL().regions[hit.rid]; text = 'Region ' + (r.name || hit.rid) + (r.note ? '\n# ' + r.note : ''); }
  tt.textContent = text;
  tt.hidden = false;
  const x = Math.min(sx + 14, cw - tt.offsetWidth - 8), y = Math.min(sy + 16, ch - tt.offsetHeight - 8);
  tt.style.left = Math.max(0, x) + 'px'; tt.style.top = Math.max(0, y) + 'px';
}
function hideTooltip() { $('#tooltip').hidden = true; }
function updateHint() {
  const el = $('#hint');
  let text = '';
  if (S.placing) text = 'Placing "' + S.placing.id + '": click on the canvas · Esc cancels';
  else if (S.mode === 'poly') text = 'Polygon: click adds a vertex (' + ((S.drawing || []).length) + ') · click on the first one, double click or Enter closes · right click removes the last one · Esc cancels';
  else if (S.mode === 'edge') text = S.edgeFrom
    ? 'Edge from "' + regionName(S.room, S.edgeFrom) + '": release or click on the target region · Shift = one way only · Esc cancels'
    : 'Edge: drag from one region to another (or click source, click target). Bidirectional; Shift = one way only. Main does not count: outside the polygons nothing happens';
  else if (S.sel.type === 'region' && S.sel.rid !== 'main') text = 'Region "' + regionName(S.room, S.sel.rid) + '": drag vertices · double click on a side inserts · right click / Del deletes a vertex · Shift+drag moves the region · Del (no active vertex) deletes the region';
  el.textContent = text;
  el.hidden = !text;
}
let flashTimer = null;
function flash(msg) {
  const el = $('#hint');
  el.textContent = msg; el.hidden = false;
  clearTimeout(flashTimer);
  flashTimer = setTimeout(updateHint, 2500);
}
function askText(title, def) {
  return new Promise((resolve) => {
    const m = $('#modal'), inp = $('#modal-input');
    $('#modal-title').textContent = title;
    inp.value = def || '';
    m.hidden = false;
    inp.focus(); inp.select();
    const done = (v) => { m.hidden = true; cleanup(); resolve(v); };
    const onKey = (e) => { if (e.key === 'Enter') { e.preventDefault(); done(inp.value); } else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(null); } };
    const onOk = () => done(inp.value), onCancel = () => done(null);
    function cleanup() { inp.removeEventListener('keydown', onKey); $('#modal-ok').removeEventListener('click', onOk); $('#modal-cancel').removeEventListener('click', onCancel); }
    inp.addEventListener('keydown', onKey);
    $('#modal-ok').addEventListener('click', onOk);
    $('#modal-cancel').addEventListener('click', onCancel);
  });
}

// =====================================================================
// Startup
// =====================================================================
function applyUrl() {
  const q = new URLSearchParams(location.search);
  const tier = q.get('tier');
  if (tier && Logic.tiers().includes(tier)) { S.tier = tier; $('#tier').value = tier; }
  const mode = q.get('mode');
  let room = q.get('room');
  if (!room || !W.rooms[room]) room = W.start_room && W.rooms[W.start_room] ? W.start_room : W.room_order[0];
  const sel = q.get('select');
  if (sel && W.locations[sel]) { const [r] = checkPosition(sel); if (r) room = r; }   // a location overrides ?room=
  switchRoom(room);
  if (sel) {
    const nodes = roomNodes(S.room);
    if (nodes.byId[sel]) select({ type: 'node', id: sel }, { center: true });
    else if (W.locations[sel]) select({ type: 'loc', name: sel });
  }
  const region = q.get('region');
  if (region && RL().regions[region]) select({ type: 'region', rid: region }, { center: true });
  const conn = q.get('conn');
  if (conn && conn.includes('>')) { const [f, t] = conn.split('>'); if (findConn(RL(), f, t)) select({ type: 'conn', from: f, to: t }, { center: true }); }
  if (q.get('gates')) { S.gatesTarget = q.get('gates') === '1' ? null : q.get('gates'); $('#gates-panel').hidden = false; renderGates(); }
  if (q.get('help')) $('#help-panel').hidden = false;
  if (q.get('report')) { $('#report-body').hidden = false; $('#report-toggle').textContent = '▾'; }
  if (mode === 'poly') setMode('poly');
  const zoom = parseFloat(q.get('zoom'));
  if (zoom > 0) { const c = toWorld(cw / 2, ch / 2); V.scale = zoom; V.tx = cw / 2 - c[0] * zoom; V.ty = ch / 2 - c[1] * zoom; updateZoomLabel(); dirty = true; }
}
function loop() { if (dirty) { dirty = false; draw(); } requestAnimationFrame(loop); }
async function init() {
  canvas = $('#canvas');
  ctx = canvas.getContext('2d');
  try {
    const [wr, lr] = await Promise.all([fetch('/api/world'), fetch('/api/logic')]);
    if (!wr.ok) throw new Error('/api/world: HTTP ' + wr.status);
    if (!lr.ok) throw new Error('/api/logic: HTTP ' + lr.status);
    W = await wr.json();
    const doc = await lr.json();
    Logic.configure(W.atoms, W.tiers);
    DOC = normalizeDoc(doc);
  } catch (err) {
    const b = $('#boot'); b.className = 'boot error';
    b.textContent = 'Could not load the world: ' + err.message + '\n\nStart the server: .venv/Scripts/python.exe tools/logic_editor/serve.py --no-browser --port 8765';
    return;
  }
  $('#boot').remove();
  renderLayers();
  bindTop(); bindCanvas(); bindKeys();
  resizeCanvas();
  setMode('select');
  applyUrl();
  setStatus('Saved', 'ok');
  loop();
  fetch('/api/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(DOC) })
    .then(r => r.json()).then(rep => { if (!rep.error) { S.report = rep; renderReport(); renderTabs(); } })
    .catch(() => { /* the report will arrive with the first save */ });
  root.MMZXEditor = { get W() { return W; }, get DOC() { return DOC; }, S, V, switchRoom, select, edit, undo, redo, roomNodes, doSave, fitView, startPlacing, setMode, toScreen, toWorld, centerOn, regionCentroid };
}
document.addEventListener('DOMContentLoaded', init);
})(globalThis);
