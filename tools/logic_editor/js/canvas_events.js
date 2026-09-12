/* canvas_events.js - mouse and drop handling on the canvas: hit-testing of vertices, sides, nodes,
 * gimmicks, connections and regions, then one named handler per event. A drag in progress lives in
 * S.drag with a `kind` (pan, vertex, region, node, edge). */
(function (LE) {
'use strict';
const { Logic, W, S, V, CV, $, dist, segDist } = LE;
const { RL, pushUndo, edit, touch, changed, roomNodes, toScreen, toWorld, zoomAt, resizeCanvas, nodeVisible } = LE;
const { showTooltipFor, hideTooltip, updateHint } = LE;
const { select, placeAt, polyClick, closePolygon, deleteVertex, edgeGestureEnd, nodePosSetter } = LE;

function evPos(e) { const r = CV.el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
const startPan = (sx, sy, click) => ({ kind: 'pan', sx, sy, tx: V.tx, ty: V.ty, moved: false, click });

// ---- hit-testing (screen coordinates); priority: vertex/side of the selected region, node, gimmick,
// connection, region
function hitTest(sx, sy) {
  const rl = RL();
  const nodes = roomNodes(S.room);
  const p = [sx, sy];
  if (S.mode === 'select' && S.sel.type === 'region' && S.sel.rid !== 'main' && S.layers.regions) {
    const reg = rl.regions[S.sel.rid];
    if (reg && reg.poly) {
      for (let i = 0; i < reg.poly.length; i++) if (dist(toScreen(reg.poly[i]), p) <= 8) return { type: 'vertex', i };
    }
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
  const gi = gimmickHit(p);
  if (gi) return gi;
  if (S.layers.conns) for (const s of CV.connShapes) {
    const r = s.rect;
    if (r && sx >= r[0] && sx <= r[0] + r[2] && sy >= r[1] && sy <= r[1] + r[3]) return { type: 'conn', conn: s.conn };
    for (let i = 1; i < s.pts.length; i++) {
      if (segDist(p, s.pts[i - 1], s.pts[i]) <= 6) return { type: 'conn', conn: s.conn };
    }
  }
  if (S.layers.regions) {
    const rid = Logic.regionOfPoint(rl, toWorld(sx, sy));
    if (rid !== 'main') return { type: 'region', rid };
  }
  return null;
}
function gimmickHit(p) {
  if (!(S.layers.gimmicks || S.layers.enemies)) return null;
  const gs = W.gimmicks[S.room] || [];
  let bi = -1, bd = 7;
  for (let i = 0; i < gs.length; i++) {
    const g = gs[i];
    if (!(g.layer === 'enemies' ? S.layers.enemies : S.layers.gimmicks)) continue;
    const d = dist(toScreen(g.pos), p);
    if (d < bd) { bd = d; bi = i; }
  }
  return bi >= 0 ? { type: 'gimmick', idx: bi, g: gs[bi] } : null;
}
// Index of the side of the selected polygon under the cursor (not near a vertex), or -1.
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
// Polygon region under the cursor, or null for Main (edge mode ignores Main).
function polyRegionAt(sx, sy) {
  const rid = Logic.regionOfPoint(RL(), toWorld(sx, sy));
  return rid === 'main' ? null : rid;
}

// ---- mouse down
function onMouseDown(e) {
  const active = document.activeElement;
  if (active && active !== document.body && active !== CV.el) active.blur();
  LE.hideSearch();
  const [sx, sy] = evPos(e);
  if (e.button === 1 || (e.button === 0 && S.space)) {
    S.drag = startPan(sx, sy, false);
    e.preventDefault(); CV.el.classList.add('grabbing'); return;
  }
  if (e.button !== 0) return;
  if (S.placing) { placeAt(toWorld(sx, sy)); return; }
  if (S.mode === 'poly') { polyClick(sx, sy); return; }
  if (S.mode === 'edge') { mouseDownEdgeMode(e, sx, sy); return; }
  mouseDownSelect(e, sx, sy, hitTest(sx, sy));
}
function mouseDownEdgeMode(e, sx, sy) {
  const rid = polyRegionAt(sx, sy);
  if (!rid) {   // Main / outside every polygon: cancel and let the canvas be dragged
    S.edgeFrom = null; CV.dirty = true;
    S.drag = startPan(sx, sy, false);
    return;
  }
  if (S.edgeFrom && S.edgeFrom !== rid) { edgeGestureEnd(rid, e.shiftKey); return; }
  S.edgeFrom = rid;
  select({ type: 'region', rid });
  S.drag = { kind: 'edge', from: rid, moved: false };
  CV.dirty = true;
}
function mouseDownSelect(e, sx, sy, hit) {
  if (!hit) { S.drag = startPan(sx, sy, true); return; }
  if (hit.type === 'vertex') {
    S.activeVertex = hit.i; pushUndo();
    S.drag = { kind: 'vertex', i: hit.i, moved: false };
    CV.dirty = true; return;
  }
  if (hit.type === 'side') {
    if (e.shiftKey) { pushUndo(); S.drag = { kind: 'region', rid: hit.rid, last: toWorld(sx, sy), moved: false }; }
    return;   // the region stays selected; the double click inserts a vertex here
  }
  if (hit.type === 'node') {
    select({ type: 'node', id: hit.node.id });
    if (hit.node.placed) {
      S.drag = { kind: 'node', node: hit.node, set: nodePosSetter(hit.node), moved: false, snap: false };
    }
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
}

// ---- mouse move (on window, so drags survive leaving the canvas)
function onMouseMove(e) {
  if (!CV.el) return;
  const [sx, sy] = evPos(e);
  CV.mouse = [sx, sy];
  if (S.drag) { moveDrag(S.drag, sx, sy); return; }
  if (e.target !== CV.el) { clearHover(); return; }
  if (S.mode === 'poly') { CV.dirty = true; return; }
  if (S.mode === 'edge') {
    clearHover();
    const rid = polyRegionAt(sx, sy);
    if (rid !== S.edgeHover) { S.edgeHover = rid; CV.dirty = true; }
    CV.el.classList.toggle('pointer', false);
    if (S.edgeFrom) CV.dirty = true;
    return;
  }
  if (S.placing) { CV.dirty = true; return; }
  updateHover(hitTest(sx, sy), sx, sy);
}
function moveDrag(d, sx, sy) {
  if (d.kind === 'pan') {
    V.tx = d.tx + (sx - d.sx); V.ty = d.ty + (sy - d.sy);
    if (Math.abs(sx - d.sx) + Math.abs(sy - d.sy) > 3) d.moved = true;
    CV.dirty = true; return;
  }
  const wp = toWorld(sx, sy).map(Math.round);
  if (d.kind === 'vertex') {
    const poly = RL().regions[S.sel.rid].poly;
    poly[d.i] = wp; d.moved = true; touch();
  } else if (d.kind === 'node') {
    if (!d.snap) { pushUndo(); d.snap = true; }   // one undo step per drag, taken on the first move
    d.set(wp); d.moved = true; touch();
  } else if (d.kind === 'edge') {
    S.edgeHover = polyRegionAt(sx, sy);
    CV.dirty = true;
  } else if (d.kind === 'region') {
    const cur = toWorld(sx, sy);
    const dx = cur[0] - d.last[0], dy = cur[1] - d.last[1];
    const poly = RL().regions[d.rid].poly;
    for (const p of poly) { p[0] = Math.round(p[0] + dx); p[1] = Math.round(p[1] + dy); }
    d.last = cur; d.moved = true; touch();
  }
}
function clearHover() { if (S.hover) { S.hover = null; hideTooltip(); CV.dirty = true; } }
// Identity of a hit for "did the hover change" comparisons.
const hoverKey = (x) => JSON.stringify(x && [
  x.type, x.i, x.idx, x.rid, x.node && x.node.id, x.conn && x.conn.from + x.conn.to,
]);
function updateHover(hit, sx, sy) {
  const prev = S.hover;
  S.hover = hit;
  if (hoverKey(prev) !== hoverKey(hit)) CV.dirty = true;
  showTooltipFor(hit, sx, sy);
  CV.el.classList.toggle('pointer', !!hit && hit.type !== 'vertex' && hit.type !== 'side');
  CV.el.classList.toggle('move', !!hit && hit.type === 'vertex');
  CV.el.classList.toggle('side', !!hit && hit.type === 'side');
}

// ---- mouse up and the rest
function onMouseUp(e) {
  const d = S.drag;
  if (!d) return;
  S.drag = null;
  CV.el.classList.remove('grabbing');
  if (d.kind === 'pan') {
    if (!d.moved && d.click && S.mode === 'select') { S.activeVertex = null; select({ type: 'room' }); }
    return;
  }
  if (d.kind === 'edge') {
    // drag: released over the target. Click without dragging: the source stays pinned and the next
    // click picks the target.
    const to = polyRegionAt(CV.mouse[0], CV.mouse[1]);
    if (to && to !== d.from) edgeGestureEnd(to, e && e.shiftKey);
    CV.dirty = true; return;
  }
  if (d.moved) changed();
  else if (d.kind !== 'node') S.undo.pop();   // nothing moved: drop the undo step taken on mouse down
}
function onDblClick(e) {
  const [sx, sy] = evPos(e);
  if (S.mode === 'poly') { closePolygon(); return; }
  if (S.placing) return;
  const i = sideHit(sx, sy);
  if (i >= 0) {
    const wp = toWorld(sx, sy).map(Math.round);
    edit(() => { RL().regions[S.sel.rid].poly.splice(i + 1, 0, wp); }, { keepInspector: true });
    S.activeVertex = i + 1;
  }
}
function onContextMenu(e) {
  e.preventDefault();
  const [sx, sy] = evPos(e);
  if (S.mode === 'poly') { if (S.drawing && S.drawing.length) S.drawing.pop(); CV.dirty = true; updateHint(); return; }
  const hit = hitTest(sx, sy);
  if (hit && hit.type === 'vertex') deleteVertex(hit.i);
}
function onWheel(e) {
  e.preventDefault();
  const [sx, sy] = evPos(e);
  zoomAt(sx, sy, e.deltaY < 0 ? 1.15 : 1 / 1.15);
}
function onDragOver(e) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; }
// Drop of a row dragged from the "Unplaced" list of the tree (payload: {kind, id}).
function onDrop(e) {
  e.preventDefault();
  let data = null;
  try { data = JSON.parse(e.dataTransfer.getData('text/plain')); } catch (err) { return; }
  if (!data || !data.kind) return;
  const [sx, sy] = evPos(e);
  S.placing = data;
  placeAt(toWorld(sx, sy));
}

function bindCanvas() {
  const canvas = CV.el;
  canvas.addEventListener('mousedown', onMouseDown);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
  canvas.addEventListener('mouseleave', clearHover);
  canvas.addEventListener('dblclick', onDblClick);
  canvas.addEventListener('contextmenu', onContextMenu);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('dragover', onDragOver);
  canvas.addEventListener('drop', onDrop);
  const ro = new ResizeObserver(() => resizeCanvas());
  ro.observe($('#canvas-wrap'));
}

Object.assign(LE, { hitTest, sideHit, polyRegionAt, bindCanvas });
})(window.LogicEditor || (window.LogicEditor = {}));
