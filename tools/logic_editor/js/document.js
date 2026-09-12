/* document.js - the logic document: shape normalization, accessors for rooms, regions, edges, checks
 * and gates, hand placements, and the mutation entry points (edit / undo / redo / changed) that
 * every edit goes through so the UI and the autosave are notified. */
(function (LE) {
'use strict';
const { Logic, W, DOC, S, CV } = LE;

const emptyRoom = () => ({
  req: null, note: '',
  regions: { main: { name: 'Main', poly: null, color: '#8ab4f8', note: '' } },
  conns: [], members: {},
});
function normalizeDoc(doc) {
  doc = doc || {};
  if (!doc.format) doc.format = 1;
  if (!doc.tiers) doc.tiers = Logic.tiers();
  for (const k of ['rooms', 'placed', 'edges', 'checks', 'gates']) {
    if (!doc[k] || typeof doc[k] !== 'object') doc[k] = {};
  }
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
// DOC is one shared object (see state.js): loading and undo/redo swap its contents, not the reference.
function replaceDoc(doc) {
  for (const k of Object.keys(DOC)) delete DOC[k];
  Object.assign(DOC, doc);
}

const RL = (r) => DOC.rooms[r || S.room];
const regionOrder = (rl) => ['main'].concat(Object.keys(rl.regions).filter(r => r !== 'main'));
function regionName(room, rid) {
  const r = DOC.rooms[room] && DOC.rooms[room].regions[rid];
  return r ? (r.name || rid) : rid;
}
function regionColor(room, rid) {
  const r = DOC.rooms[room] && DOC.rooms[room].regions[rid];
  return (r && r.color) || '#8ab4f8';
}
const roomLabel = (code) => (W.rooms[code] && W.rooms[code].label) || code;
const roomSize = (code) => (W.rooms[code] && W.rooms[code].size) || [1024, 768];
const areaLabel = (a) => a === 'z' ? 'Hub' : a.toUpperCase();
const findConn = (rl, from, to) => rl.conns.find(c => c.from === from && c.to === to) || null;

// Per-edge / per-check / per-gate overrides exist in the document only while they carry something.
function ensureEdge(name) {
  return DOC.edges[name] || (DOC.edges[name] = { pos: null, dst_pos: null, req: null, unsure: false, note: '' });
}
function pruneEdge(name) {
  const e = DOC.edges[name];
  if (e && !e.pos && !e.dst_pos && e.req == null && !e.unsure && !e.note) delete DOC.edges[name];
}
function ensureCheck(name) { return DOC.checks[name] || (DOC.checks[name] = { req: null, unsure: false, note: '' }); }
function pruneCheck(name) {
  const c = DOC.checks[name];
  if (c && c.req == null && !c.unsure && !c.note) delete DOC.checks[name];
}
function ensureGate(flag) { return DOC.gates[flag] || (DOC.gates[flag] = { req: null, note: '' }); }
// reads WITHOUT side effects (the inspector must not create entries while rendering)
const peekCheck = (name) => DOC.checks[name] || {};
const peekEdge = (name) => DOC.edges[name] || {};
const peekGate = (flag) => DOC.gates[flag] || {};

// ---- history and change notification
function pushUndo() {
  S.undo.push(JSON.stringify(DOC));
  if (S.undo.length > 100) S.undo.shift();
  S.redo = [];
}
function edit(fn, opts) { pushUndo(); fn(); changed(opts); }
function undo() {
  if (!S.undo.length) return;
  S.redo.push(JSON.stringify(DOC));
  replaceDoc(normalizeDoc(JSON.parse(S.undo.pop())));
  afterHistory();
}
function redo() {
  if (!S.redo.length) return;
  S.undo.push(JSON.stringify(DOC));
  replaceDoc(normalizeDoc(JSON.parse(S.redo.pop())));
  afterHistory();
}
function afterHistory() {
  S.activeVertex = null;
  validateSelection();
  changed();
}
// Drops a selection that no longer exists after undo/redo (or turns it into its unplaced form).
function validateSelection() {
  const rl = RL();
  const s = S.sel;
  if (s.type === 'region' && !rl.regions[s.rid]) S.sel = { type: 'room' };
  else if (s.type === 'conn' && !findConn(rl, s.from, s.to)) S.sel = { type: 'room' };
  else if (s.type === 'node' && !LE.roomNodes(S.room).byId[s.id]) {
    const [r] = checkPosition(s.id);
    S.sel = (!r && W.locations[s.id]) ? { type: 'loc', name: s.id } : { type: 'room' };
  } else if (s.type === 'loc' && W.locations[s.name]) {
    const loc = W.locations[s.name];
    if ((loc.pos && loc.room === S.room) || placementIn(s.name, S.room)) S.sel = { type: 'node', id: s.name };
  }
}
// touch: the document changed during a drag (redraw only); changed: an edit finished (save + UI).
function touch() { S.docVersion++; CV.dirty = true; }
function changed(opts = {}) {
  S.docVersion++;
  CV.dirty = true;
  LE.scheduleSave();
  LE.renderTree();
  if (!opts.keepInspector) LE.renderInspector();
  LE.renderTabs();
  LE.updateHint();
}

// ---- hand placements: DOC.placed[name] = {room, pos} or a LIST of them (the biometals are obtained
// at either of two bosses: two rooms, OR rule)
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
function altRooms(name) {
  const lab = (W.locations[name] || {}).room || '';
  return lab.includes('/') ? lab.split('/').length : 1;
}
function checkPosition(name) {
  const v = W.locations[name];
  if (!v) return [null, null];
  if (v.pos && DOC.rooms[v.room]) return [v.room, v.pos];
  const pl = placementsOf(name);
  const cur = pl.find(q => q.room === S.room) || pl[0];   // the current room's one if any
  return cur ? [cur.room, cur.pos] : [null, null];
}

Object.assign(LE, {
  emptyRoom, normalizeDoc, replaceDoc, RL, regionOrder, regionName, regionColor, roomLabel, roomSize, areaLabel,
  findConn, ensureEdge, pruneEdge, ensureCheck, pruneCheck, ensureGate, peekCheck, peekEdge, peekGate,
  pushUndo, edit, undo, redo, validateSelection, touch, changed,
  placementsOf, setPlacements, placementIn, altRooms, checkPosition,
});
})(window.LogicEditor || (window.LogicEditor = {}));
