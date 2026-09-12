/* hints.js - transient feedback: the canvas tooltip, the hint bar (instructions of the current mode
 * and short flash messages) and the modal text prompt used to name regions. */
(function (LE) {
'use strict';
const { Logic, S, CV, $, RL, regionName, nodeTooltip } = LE;

function showTooltipFor(hit, sx, sy) {
  const tt = $('#tooltip');
  if (!hit || hit.type === 'vertex' || hit.type === 'side') { hideTooltip(); return; }
  let text = '';
  if (hit.type === 'node') text = nodeTooltip(hit.node);
  else if (hit.type === 'gimmick') {
    text = hit.g.name + ' (' + (hit.g.layer === 'enemies' ? 'enemy' : 'gimmick') + ') @ ' + hit.g.pos.join(',');
  } else if (hit.type === 'conn') {
    const c = hit.conn;
    text = 'Connection ' + regionName(S.room, c.from) + ' → ' + regionName(S.room, c.to) + '\n' +
      Logic.reqToLines(c.req).join('\n') + (c.unsure ? '\n(unconfirmed)' : '') + (c.note ? '\n# ' + c.note : '');
  } else if (hit.type === 'region') {
    const r = RL().regions[hit.rid];
    text = 'Region ' + (r.name || hit.rid) + (r.note ? '\n# ' + r.note : '');
  }
  tt.textContent = text;
  tt.hidden = false;
  const x = Math.min(sx + 14, CV.w - tt.offsetWidth - 8), y = Math.min(sy + 16, CV.h - tt.offsetHeight - 8);
  tt.style.left = Math.max(0, x) + 'px'; tt.style.top = Math.max(0, y) + 'px';
}
function hideTooltip() { $('#tooltip').hidden = true; }

function hintText() {
  if (S.placing) return 'Placing "' + S.placing.id + '": click on the canvas · Esc cancels';
  if (S.mode === 'poly') {
    return 'Polygon: click adds a vertex (' + ((S.drawing || []).length) + ') · click on the first one, ' +
      'double click or Enter closes · right click removes the last one · Esc cancels';
  }
  if (S.mode === 'edge') {
    return S.edgeFrom
      ? 'Edge from "' + regionName(S.room, S.edgeFrom) + '": release or click on the target region · ' +
        'Shift = one way only · Esc cancels'
      : 'Edge: drag from one region to another (or click source, click target). Bidirectional; Shift = one way only. ' +
        'Main does not count: outside the polygons nothing happens';
  }
  if (S.sel.type === 'region' && S.sel.rid !== 'main') {
    return 'Region "' + regionName(S.room, S.sel.rid) + '": drag vertices · double click on a side inserts · ' +
      'right click / Del deletes a vertex · Shift+drag moves the region · Del (no active vertex) deletes the region';
  }
  return '';
}
function updateHint() {
  const el = $('#hint');
  const text = hintText();
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

// Resolves with the typed text, or null on Cancel / Escape.
function askText(title, def) {
  return new Promise((resolve) => {
    const m = $('#modal'), inp = $('#modal-input');
    $('#modal-title').textContent = title;
    inp.value = def || '';
    m.hidden = false;
    inp.focus(); inp.select();
    const done = (v) => { m.hidden = true; cleanup(); resolve(v); };
    const onKey = (e) => {
      if (e.key === 'Enter') { e.preventDefault(); done(inp.value); }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); done(null); }
    };
    const onOk = () => done(inp.value), onCancel = () => done(null);
    function cleanup() {
      inp.removeEventListener('keydown', onKey);
      $('#modal-ok').removeEventListener('click', onOk);
      $('#modal-cancel').removeEventListener('click', onCancel);
    }
    inp.addEventListener('keydown', onKey);
    $('#modal-ok').addEventListener('click', onOk);
    $('#modal-cancel').addEventListener('click', onCancel);
  });
}

Object.assign(LE, { showTooltipFor, hideTooltip, updateHint, flash, askText });
})(window.LogicEditor || (window.LogicEditor = {}));
