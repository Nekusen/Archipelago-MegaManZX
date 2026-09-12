/* main.js - startup: fetches the world and the document, wires the widgets, applies the URL parameters
 * (?room, select, region, conn, tier, gates, help, report, mode, zoom) and runs the draw loop. */
(function (LE) {
'use strict';
const { Logic, W, S, V, CV, $ } = LE;
const { RL, findConn, replaceDoc, normalizeDoc, checkPosition, roomNodes, toWorld, updateZoomLabel, resizeCanvas } = LE;
const { select, switchRoom, setMode, renderLayers, bindTop, bindCanvas, bindKeys, renderGates } = LE;
const { setStatus, loadWorld, requestInitialReport, draw } = LE;

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
  if (conn && conn.includes('>')) {
    const [f, t] = conn.split('>');
    if (findConn(RL(), f, t)) select({ type: 'conn', from: f, to: t }, { center: true });
  }
  if (q.get('gates')) {   // gates=1 opens the panel; gates=<flag> scrolls to that flag
    S.gatesTarget = q.get('gates') === '1' ? null : q.get('gates');
    $('#gates-panel').hidden = false; renderGates();
  }
  if (q.get('help')) $('#help-panel').hidden = false;
  if (q.get('report')) { $('#report-body').hidden = false; $('#report-toggle').textContent = '▾'; }
  if (mode === 'poly') setMode('poly');
  const zoom = parseFloat(q.get('zoom'));
  if (zoom > 0) {
    const c = toWorld(CV.w / 2, CV.h / 2);
    V.scale = zoom; V.tx = CV.w / 2 - c[0] * zoom; V.ty = CV.h / 2 - c[1] * zoom;
    updateZoomLabel(); CV.dirty = true;
  }
}
function loop() { if (CV.dirty) { CV.dirty = false; draw(); } requestAnimationFrame(loop); }
async function init() {
  CV.el = $('#canvas');
  CV.ctx = CV.el.getContext('2d');
  try {
    const { world, doc } = await loadWorld();
    Object.assign(W, world);
    Logic.configure(W.atoms, W.tiers);
    replaceDoc(normalizeDoc(doc));
  } catch (err) {
    const b = $('#boot'); b.className = 'boot error';
    b.textContent = 'Could not load the world: ' + err.message +
      '\n\nStart the server: .venv/Scripts/python.exe tools/logic_editor/serve.py --no-browser --port 8765';
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
  requestInitialReport();
}
document.addEventListener('DOMContentLoaded', init);

Object.assign(LE, { init });
})(window.LogicEditor || (window.LogicEditor = {}));
