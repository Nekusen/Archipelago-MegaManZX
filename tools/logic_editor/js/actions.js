/* actions.js - what the user does to the document from the canvas and the panels: tool mode,
 * selection, room switching, polygon drawing, hand placements, deletions and new connections.
 * Every mutation goes through LE.edit so it is undoable and autosaved. */
(function (LE) {
'use strict';
const { Logic, W, DOC, S, CV, dist, slugify, PALETTE } = LE;
const { RL, regionName, roomLabel, findConn, edit, ensureEdge, pruneEdge } = LE;
const { placementsOf, setPlacements, placementIn, roomNodes, regionCentroid } = LE;
const { fitView, centerOn, toWorld, toScreen, connGeom, updateHint, flash, askText } = LE;

function setMode(m) {
  S.mode = m;
  if (m !== 'poly') S.drawing = null;
  else { S.drawing = []; S.placing = null; S.activeVertex = null; }
  if (m !== 'edge') { S.edgeFrom = null; S.edgeHover = null; }
  else { S.placing = null; S.activeVertex = null; }
  for (const b of document.querySelectorAll('#tools button')) b.classList.toggle('active', b.dataset.mode === m);
  CV.el.classList.toggle('mode-poly', m === 'poly');
  CV.el.classList.toggle('mode-edge', m === 'edge');
  updateHint(); CV.dirty = true;
}
function select(sel, opts = {}) {
  S.sel = sel;
  if (sel.type !== 'region') S.activeVertex = null;
  LE.renderInspector();
  LE.renderTree();
  updateHint();
  CV.dirty = true;
  if (opts.center) centerOnSelection(sel);
}
function centerOnSelection(sel) {
  if (sel.type === 'node') { const n = roomNodes(S.room).byId[sel.id]; if (n) centerOn(n.pos); }
  else if (sel.type === 'region') centerOn(regionCentroid(S.room, sel.rid), 0.3);
  else if (sel.type === 'conn') {
    const rl = RL(); const c = findConn(rl, sel.from, sel.to);
    if (c) { const g = connGeom(rl, c); centerOn(toWorld(g.mid[0], g.mid[1]), 0.3); }
  }
}
function switchRoom(code, opts = {}) {
  if (!W.rooms[code]) return;
  const same = S.room === code;
  S.room = code;
  if (!same || opts.reset) {
    S.sel = { type: 'room' }; S.activeVertex = null; S.placing = null;
    if (S.mode === 'poly') setMode('select');
    S.edgeFrom = null; S.edgeHover = null;
    fitView();
  }
  LE.renderTabs(); LE.renderTree(); LE.renderInspector(); LE.renderReport(); updateHint();
  CV.dirty = true;
  try {   // keep the URL shareable: ?room=<code>, dropping the stale selection parameters
    const u = new URL(location.href);
    u.searchParams.set('room', code);
    for (const k of ['select', 'region', 'conn']) u.searchParams.delete(k);
    history.replaceState(null, '', u);
  } catch (e) { /* nothing */ }
}
// Where a hand-placed node stores its position: the placement, the edge exit or the edge landing.
function nodePosSetter(n) {
  if (n.type === 'check') return (p) => { const q = placementIn(n.id, S.room); if (q) q.pos = p; };
  if (n.type === 'out') return (p) => { ensureEdge(n.edge.name).pos = p; };
  return (p) => { ensureEdge(n.edge.name).dst_pos = p; };
}

// ---- "Edge" mode: create connections by drawing on the canvas. Only between regions with a POLYGON:
// outside them is Main, and the user does not want edges to Main by accident (the idea is to keep
// pulling everything out of that bag). A connection with Main is still possible from the region panel.
function edgeGestureEnd(to, oneWay) {
  const from = S.edgeFrom;
  S.edgeFrom = null;
  if (!from || !to || from === to) { CV.dirty = true; return; }
  const rl = RL();
  const had = !!findConn(rl, from, to), hadRev = !!findConn(rl, to, from);
  addConn(rl, from, to, !oneWay);            // it warns by itself if nothing was created
  if (had && (oneWay || hadRev)) return;
  flash((oneWay ? 'Connection ' : 'Bidirectional connection ') + regionName(S.room, from) + ' → ' +
    regionName(S.room, to) + ' (free: set its requirement)');
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

// ---- polygon drawing
function polyClick(sx, sy) {
  if (!S.drawing) S.drawing = [];
  if (S.drawing.length >= 3 && dist(toScreen(S.drawing[0]), [sx, sy]) <= 10) { closePolygon(); return; }
  S.drawing.push(toWorld(sx, sy).map(Math.round));
  CV.dirty = true; updateHint();
}
async function closePolygon() {
  const pts = (S.drawing || []).slice();
  while (pts.length > 1 && dist(toScreen(pts[pts.length - 1]), toScreen(pts[pts.length - 2])) < 4) pts.pop();
  if (pts.length < 3) { updateHint(); return; }
  const rl = RL();
  const n = Object.keys(rl.regions).length;
  const name = await askText('Name of the new region', 'Region ' + n);
  if (name === null) { S.drawing = []; CV.dirty = true; updateHint(); return; }
  const rid = newRegionId(rl, name);
  const used = new Set(Object.values(rl.regions).map(r => r.color));
  const color = PALETTE.find(c => !used.has(c)) || PALETTE[(n - 1) % PALETTE.length];
  edit(() => { rl.regions[rid] = { name: name.trim() || rid, poly: pts, color, note: '' }; });
  S.drawing = null;
  setMode('select');
  select({ type: 'region', rid });
}
// Slug of the name, never 'main' nor starting with a digit, unique within the room.
function newRegionId(rl, name) {
  let rid = slugify(name) || 'region';
  if (rid === 'main' || /^\d/.test(rid)) rid = 'r-' + rid;
  const base = rid; let k = 2;
  while (rl.regions[rid]) rid = base + '-' + (k++);
  return rid;
}

// ---- deletions
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
  if (s.type === 'conn') {
    edit(() => { rl.conns = rl.conns.filter(c => !(c.from === s.from && c.to === s.to)); });
    select({ type: 'room' });
    return;
  }
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
    if (n.type === 'check') {
      setPlacements(n.id, placementsOf(n.id).filter(q => q.room !== S.room));
    } else {
      const e = ensureEdge(n.edge.name);
      if (n.type === 'out') e.pos = null; else e.dst_pos = null;
      pruneEdge(n.edge.name);
    }
    delete rl.members[n.id];
  });
  if (n.type === 'check') select({ type: 'loc', name: n.id }); else select({ type: 'room' });
}

// ---- hand placement of locations, exits and landings (S.placing = {kind: 'loc'|'out'|'in', id})
function startPlacing(data) {
  S.placing = data; S.hover = null;
  if (S.mode === 'poly') setMode('select');
  CV.el.classList.add('placing');
  updateHint(); CV.dirty = true;
}
function stopPlacing() { S.placing = null; CV.el.classList.remove('placing'); updateHint(); CV.dirty = true; }
function placeAt(wp) {
  const d = S.placing;
  if (!d) return;
  const p = wp.map(Math.round);
  const room = S.room;
  let sel = null;
  if (d.kind === 'loc') {
    if (!W.locations[d.id]) return;
    edit(() => {
      const arr = placementsOf(d.id).filter(q => q.room !== room);
      arr.push({ room, pos: p });
      setPlacements(d.id, arr);
    });
    sel = { type: 'node', id: d.id };
  } else if (d.kind === 'out') {
    const e = W.edges.find(x => x.name === d.id);
    if (!e || e.src !== room) { flash('That exit belongs to ' + (e ? roomLabel(e.src) : '?')); stopPlacing(); return; }
    edit(() => { ensureEdge(d.id).pos = p; });
    sel = { type: 'node', id: d.id };
  } else if (d.kind === 'in') {
    const e = W.edges.find(x => x.name === d.id);
    if (!e || e.dst !== room) {
      flash('That landing belongs to ' + (e ? roomLabel(e.dst) : '?')); stopPlacing(); return;
    }
    edit(() => { ensureEdge(d.id).dst_pos = p; });
    sel = { type: 'node', id: d.id + '@in' };
  }
  stopPlacing();
  if (sel) select(sel);
}
function autoPlaceHubWarps() {
  const hub = W.hub;
  const unplaced = (e) => !e.pos && !(DOC.edges[e.name] && DOC.edges[e.name].pos);
  const todo = W.edges.filter(e => e.kind === 'warp' && e.src === hub && unplaced(e));
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

Object.assign(LE, {
  setMode, select, switchRoom, nodePosSetter, edgeGestureEnd, addConn, polyClick, closePolygon,
  deleteVertex, deleteSelection, deleteRegion, removePlacement, startPlacing, stopPlacing, placeAt, autoPlaceHubWarps,
});
})(window.LogicEditor || (window.LogicEditor = {}));
