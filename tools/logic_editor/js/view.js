/* view.js - viewport (pan / zoom) conversions, fit and center helpers, the canvas resize, and the
 * small LRU cache of room renders loaded from /renders/<room>.png. */
(function (LE) {
'use strict';
const { S, V, CV, $, clamp, roomSize } = LE;

const toScreen = (p) => [p[0] * V.scale + V.tx, p[1] * V.scale + V.ty];
const toWorld = (sx, sy) => [(sx - V.tx) / V.scale, (sy - V.ty) / V.scale];
function fitView() {
  const sz = roomSize(S.room);
  const s = Math.min((CV.w - 40) / sz[0], (CV.h - 40) / sz[1]);
  V.scale = clamp(s, 0.02, 8);
  V.tx = (CV.w - sz[0] * V.scale) / 2;
  V.ty = (CV.h - sz[1] * V.scale) / 2;
  CV.dirty = true; updateZoomLabel();
}
function zoomAt(sx, sy, factor) {
  const ns = clamp(V.scale * factor, 0.02, 16);
  const [wx, wy] = toWorld(sx, sy);
  V.scale = ns; V.tx = sx - wx * ns; V.ty = sy - wy * ns;
  CV.dirty = true; updateZoomLabel();
}
function centerOn(pos, minScale = 0.6) {
  if (V.scale < minScale) V.scale = 1;
  V.tx = CV.w / 2 - pos[0] * V.scale; V.ty = CV.h / 2 - pos[1] * V.scale;
  CV.dirty = true; updateZoomLabel();
}
function updateZoomLabel() { $('#zoom-label').textContent = Math.round(V.scale * 100) + '%'; }
function resizeCanvas() {
  const wrap = $('#canvas-wrap');
  const dpr = window.devicePixelRatio || 1;
  CV.w = Math.max(1, wrap.clientWidth); CV.h = Math.max(1, wrap.clientHeight);
  CV.el.width = Math.round(CV.w * dpr); CV.el.height = Math.round(CV.h * dpr);
  CV.dirty = true;
}

// Renders are big: keep the 6 most recent, the current room always included.
const imgCache = new Map();
function getImage(room) {
  if (imgCache.has(room)) { const e = imgCache.get(room); imgCache.delete(room); imgCache.set(room, e); return e; }
  const img = new Image();
  const e = { img, ready: false, error: false };
  img.onload = () => { e.ready = true; CV.dirty = true; };
  img.onerror = () => { e.error = true; CV.dirty = true; };
  img.src = '/renders/' + room + '.png';
  imgCache.set(room, e);
  while (imgCache.size > 6) {
    const first = imgCache.keys().next().value;
    if (first === room) break;
    imgCache.delete(first);
  }
  return e;
}

Object.assign(LE, { toScreen, toWorld, fitView, zoomAt, centerOn, updateZoomLabel, resizeCanvas, getImage });
})(window.LogicEditor || (window.LogicEditor = {}));
