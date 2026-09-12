/* draw.js - renders one frame of the canvas: the room image, region polygons, connection arrows,
 * gimmicks, nodes, the vertices of the selected region, the polygon draft, the edge-mode gesture and
 * the placement marker. Records the connection geometry in CV.connShapes for hit-testing. */
(function (LE) {
'use strict';
const { Logic, W, S, V, CV, hexA, clamp, polyCentroid } = LE;
const { RL, regionOrder, regionColor, roomSize, findConn, roomNodes, regionCentroid, reqShort } = LE;
const { toScreen, getImage } = LE;

let ctx = null;   // 2D context of the frame being drawn (set by draw)
const FONT = 'px system-ui, "Segoe UI", sans-serif';

function layerOf(n) { return n.type === 'check' ? 'checks' : n.type === 'out' ? 'doors' : 'landings'; }
const nodeVisible = (n) => !!S.layers[layerOf(n)];

// ---- primitives
function haloText(text, x, y, opts = {}) {
  ctx.font = (opts.bold ? 'bold ' : '') + (opts.size || 11) + FONT;
  ctx.textAlign = opts.align || 'center';
  ctx.textBaseline = opts.baseline || 'top';
  ctx.lineWidth = 3; ctx.lineJoin = 'round';
  ctx.strokeStyle = 'rgba(0,0,0,.85)';
  ctx.strokeText(text, x, y);
  ctx.fillStyle = opts.color || '#eee';
  ctx.fillText(text, x, y);
}
function pill(text, x, y, opts = {}) {
  ctx.font = (opts.bold ? 'bold ' : '') + (opts.size || 11) + FONT;
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
function shapeTri(x, y, r) {
  ctx.beginPath();
  ctx.moveTo(x - r * 0.8, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x - r * 0.8, y + r);
  ctx.closePath();
}
function shapeCircle(x, y, r) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); }
function shapeHex(x, y, r) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const a = Math.PI / 3 * i - Math.PI / 6;
    const px = x + r * Math.cos(a), py = y + r * Math.sin(a);
    if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
  }
  ctx.closePath();
}
function drawPin(x, y) {
  ctx.beginPath(); ctx.moveTo(x, y + 7); ctx.lineTo(x, y); ctx.strokeStyle = '#111'; ctx.lineWidth = 2; ctx.stroke();
  shapeCircle(x, y - 1, 3.5); ctx.fillStyle = '#fff'; ctx.fill();
  ctx.strokeStyle = '#111'; ctx.lineWidth = 1; ctx.stroke();
}
// Begins a path through screen points, optionally closed.
function tracePath(pts, close) {
  ctx.beginPath();
  pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
  if (close) ctx.closePath();
}
function arrowHead(tip, ang, size) {
  ctx.beginPath();
  ctx.moveTo(tip[0], tip[1]);
  ctx.lineTo(tip[0] - size * Math.cos(ang - 0.4), tip[1] - size * Math.sin(ang - 0.4));
  ctx.lineTo(tip[0] - size * Math.cos(ang + 0.4), tip[1] - size * Math.sin(ang + 0.4));
  ctx.closePath();
}

// ---- the frame
function draw() {
  ctx = CV.ctx;
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = '#101012';
  ctx.fillRect(0, 0, CV.w, CV.h);
  CV.connShapes = [];
  if (!S.room) return;
  drawRoomImage(dpr);
  const rl = RL();
  const nodes = roomNodes(S.room);
  if (S.layers.regions) drawRegions(rl);
  if (S.layers.conns) for (const c of rl.conns) drawConn(rl, c);
  if (S.layers.gimmicks || S.layers.enemies) drawGimmicks();
  drawNodes(nodes);
  if (S.mode === 'select' && S.sel.type === 'region' && S.sel.rid !== 'main' && S.layers.regions) drawVertices(rl);
  if (S.mode === 'poly' && S.drawing) drawPolygonDraft();
  if (S.mode === 'edge') drawEdgeGesture(rl);
  if (S.placing && S.hover === null) drawPlacingMarker();
}
function drawRoomImage(dpr) {
  const sz = roomSize(S.room);
  const im = getImage(S.room);
  const [ox, oy] = toScreen([0, 0]);
  if (im.ready) {
    ctx.save();
    ctx.setTransform(dpr * V.scale, 0, 0, dpr * V.scale, dpr * V.tx, dpr * V.ty);
    ctx.imageSmoothingEnabled = V.scale < 1;   // crisp pixels when zoomed in
    ctx.drawImage(im.img, 0, 0);
    ctx.restore();
  } else {
    ctx.fillStyle = '#1b1b20';
    ctx.fillRect(ox, oy, sz[0] * V.scale, sz[1] * V.scale);
    const msg = im.error ? 'Render not available: ' + S.room + '.png' : 'Loading render...';
    haloText(msg, CV.w / 2, CV.h / 2 - 6, { size: 14, color: '#aaa' });
  }
  ctx.strokeStyle = 'rgba(255,255,255,.25)'; ctx.lineWidth = 1;
  ctx.strokeRect(ox + 0.5, oy + 0.5, sz[0] * V.scale, sz[1] * V.scale);
}
function drawRegions(rl) {
  const sel = S.sel;
  for (const rid of regionOrder(rl)) {
    const reg = rl.regions[rid];
    if (rid === 'main' || !reg.poly || reg.poly.length < 3) continue;
    const isSel = sel.type === 'region' && sel.rid === rid;
    const isHov = S.hover && S.hover.type === 'region' && S.hover.rid === rid;
    tracePath(reg.poly.map(toScreen), true);
    ctx.fillStyle = hexA(reg.color, isSel ? 0.3 : isHov ? 0.24 : 0.16);
    ctx.fill();
    ctx.strokeStyle = hexA(reg.color, 0.95);
    ctx.lineWidth = isSel ? 2.5 : isHov ? 2 : 1.5;
    if (isSel) ctx.setLineDash([]);
    ctx.stroke();
    const c = toScreen(polyCentroid(reg.poly));
    haloText(reg.name || rid, c[0], c[1] - 7, { bold: true, size: 12, color: reg.color });
  }
  // Main has no polygon: label it at its centroid only when the room has other regions or connections
  if (regionOrder(rl).length > 1 || rl.conns.length) {
    const c = toScreen(regionCentroid(S.room, 'main'));
    const isSel = sel.type === 'region' && sel.rid === 'main';
    const main = rl.regions.main;
    pill(main.name || 'Main', c[0], c[1], {
      bold: true, color: main.color || '#8ab4f8', border: isSel ? '#fff' : hexA(main.color, 0.8),
    });
  }
}
function drawGimmicks() {
  const sel = S.sel;
  const gs = W.gimmicks[S.room] || [];
  for (let i = 0; i < gs.length; i++) {
    const g = gs[i];
    if (!(g.layer === 'enemies' ? S.layers.enemies : S.layers.gimmicks)) continue;
    const [x, y] = toScreen(g.pos);
    if (x < -20 || y < -20 || x > CV.w + 20 || y > CV.h + 20) continue;
    const isSel = sel.type === 'gimmick' && sel.idx === i;
    const isHov = S.hover && S.hover.type === 'gimmick' && S.hover.idx === i;
    shapeCircle(x, y, isSel || isHov ? 4.5 : 3);
    ctx.fillStyle = g.layer === 'enemies' ? '#ef9a9a' : '#b0bec5';
    ctx.fill(); ctx.strokeStyle = '#111'; ctx.lineWidth = 1; ctx.stroke();
    if (isSel) { shapeCircle(x, y, 9); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke(); }
    if (S.layers.labels && (isHov || isSel || V.scale >= 0.6)) {
      haloText(g.name, x, y + 5, { size: 9, color: '#c8d0d4' });
    }
  }
}
const NODE_ORDER = { in: 0, out: 1, check: 2 };   // landings first so checks and exits paint on top
const LABEL_COLOR = { check: '#f2f2f2', out: '#ffe9a8', in: '#bfe0ff' };
function drawNodes(nodes) {
  const sel = S.sel;
  const vis = nodes.list.filter(nodeVisible).sort((a, b) => NODE_ORDER[a.type] - NODE_ORDER[b.type]);
  for (const n of vis) {
    const [x, y] = toScreen(n.pos);
    if (x < -40 || y < -40 || x > CV.w + 40 || y > CV.h + 40) continue;
    const isSel = sel.type === 'node' && sel.id === n.id;
    const isHov = S.hover && S.hover.type === 'node' && S.hover.node.id === n.id;
    if (isSel || isHov) {
      shapeCircle(x, y, isSel ? 15 : 13);
      ctx.strokeStyle = isSel ? '#fff' : 'rgba(255,255,255,.55)'; ctx.lineWidth = 2; ctx.stroke();
    }
    drawNodeShape(n, x, y);
    if (n.pinned) drawPin(x + 9, y - 10);
    // labels: checks and exits below, landings above (they usually coincide with an exit)
    if (S.layers.labels) {
      haloText(n.label, x, n.type === 'in' ? y - 11 : y + 11,
        { size: 10, baseline: n.type === 'in' ? 'bottom' : 'top', color: LABEL_COLOR[n.type] });
    }
  }
}
// Hand-placed nodes are hexagons; checks squares, exits triangles, landings hollow circles.
function drawNodeShape(n, x, y) {
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
}
function drawVertices(rl) {
  const reg = rl.regions[S.sel.rid];
  if (!reg || !reg.poly) return;
  reg.poly.forEach((p, i) => {
    const [x, y] = toScreen(p);
    const act = S.activeVertex === i;
    const hov = S.hover && S.hover.type === 'vertex' && S.hover.i === i;
    shapeSquare(x, y, act ? 6 : hov ? 5.5 : 4.5);
    ctx.fillStyle = act ? '#fff' : reg.color; ctx.fill();
    ctx.strokeStyle = '#000'; ctx.lineWidth = 1.5; ctx.stroke();
  });
}
function drawPolygonDraft() {
  const pts = S.drawing.map(toScreen);
  const mouse = CV.mouse;
  tracePath(pts, false);
  if (pts.length) ctx.lineTo(mouse[0], mouse[1]);
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.setLineDash([6, 4]); ctx.stroke(); ctx.setLineDash([]);
  if (pts.length >= 3) {
    tracePath(pts, true);
    ctx.fillStyle = 'rgba(255,255,255,.12)'; ctx.fill();
  }
  pts.forEach((p, i) => {
    const closer = i === 0 && pts.length >= 3;   // the first vertex grows: clicking it closes the polygon
    shapeCircle(p[0], p[1], closer ? 7 : 4);
    ctx.fillStyle = closer ? '#8ab4f8' : '#fff'; ctx.fill();
    ctx.strokeStyle = '#000'; ctx.lineWidth = 1; ctx.stroke();
  });
}
function drawEdgeGesture(rl) {
  const outline = (rid, color, width) => {
    const reg = rl.regions[rid];
    if (!reg || !reg.poly) return;
    tracePath(reg.poly.map(toScreen), true);
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
    ctx.fillStyle = color.replace('rgb', 'rgba').replace(')', ',.14)');
    ctx.fill();
  };
  if (S.edgeHover && S.edgeHover !== S.edgeFrom) outline(S.edgeHover, 'rgb(129,201,149)', 2);
  if (!S.edgeFrom) return;
  outline(S.edgeFrom, 'rgb(255,233,168)', 2.5);
  const A = toScreen(regionCentroid(S.room, S.edgeFrom));
  const B = S.edgeHover && S.edgeHover !== S.edgeFrom ? toScreen(regionCentroid(S.room, S.edgeHover)) : CV.mouse;
  ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]);
  ctx.strokeStyle = '#ffe9a8'; ctx.lineWidth = 2; ctx.setLineDash([7, 5]); ctx.stroke(); ctx.setLineDash([]);
  arrowHead(B, Math.atan2(B[1] - A[1], B[0] - A[0]), 11);
  ctx.fillStyle = '#ffe9a8'; ctx.fill();
}
function drawPlacingMarker() {
  const [x, y] = CV.mouse;
  shapeHex(x, y, 10);
  ctx.strokeStyle = '#fff'; ctx.setLineDash([3, 3]); ctx.lineWidth = 1.5; ctx.stroke(); ctx.setLineDash([]);
}

// ---- connections: a quadratic curve between region centroids, bowed when the reverse exists too
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
  const path = () => {
    ctx.beginPath(); ctx.moveTo(g.a[0], g.a[1]); ctx.quadraticCurveTo(g.m[0], g.m[1], g.b[0], g.b[1]);
  };
  path(); ctx.strokeStyle = 'rgba(0,0,0,.6)'; ctx.lineWidth = isSel ? 6 : 5; ctx.setLineDash([]); ctx.stroke();
  path(); ctx.strokeStyle = color; ctx.lineWidth = isSel ? 3 : 2;
  if (c.unsure) ctx.setLineDash([7, 5]); else if (never) ctx.setLineDash([2, 4]);
  ctx.stroke(); ctx.setLineDash([]);
  // arrow head along the tangent at the end of the curve
  const tl = Math.hypot(g.tan[0], g.tan[1]) || 1, tx = g.tan[0] / tl, ty = g.tan[1] / tl;
  ctx.beginPath();
  ctx.moveTo(g.b[0], g.b[1]);
  ctx.lineTo(g.b[0] - tx * 11 - ty * 5, g.b[1] - ty * 11 + tx * 5);
  ctx.lineTo(g.b[0] - tx * 11 + ty * 5, g.b[1] - ty * 11 - tx * 5);
  ctx.closePath(); ctx.fillStyle = color; ctx.fill();
  ctx.strokeStyle = 'rgba(0,0,0,.6)'; ctx.lineWidth = 1; ctx.stroke();
  let rect = null;
  if (S.layers.labels) {
    const txt = (c.unsure ? '? ' : '') + reqShort(c.req, S.tier);
    rect = pill(txt, g.mid[0], g.mid[1],
      { color: never ? '#ff9e9e' : '#fff', border: isSel ? '#fff' : null, size: 10 });
  }
  CV.connShapes.push({ conn: c, pts: g.pts, rect });
}

Object.assign(LE, { nodeVisible, draw, connGeom });
})(window.LogicEditor || (window.LogicEditor = {}));
