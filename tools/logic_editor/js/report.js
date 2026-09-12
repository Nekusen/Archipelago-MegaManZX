/* report.js - the validation report drawer at the bottom: the counters in the header, the list of
 * errors and warnings (those of the current room first, each one a link to its room) and the toggle. */
(function (LE) {
'use strict';
const { S, $, h, roomLabel, switchRoom } = LE;

const ROOM_RE = /^([a-z]\d\d)\b/;   // validation messages start with the room code
function reportRoomOf(text) { const m = ROOM_RE.exec(text); return m ? m[1] : null; }

function renderReport() {
  const rep = S.report || { errors: [], warnings: [] };
  const errs = rep.errors || [], warns = rep.warnings || [];
  const counter = $('#counter');
  counter.textContent = errs.length + ' error' + (errs.length === 1 ? '' : 's') + ' · ' +
    warns.length + ' warning' + (warns.length === 1 ? '' : 's');
  counter.className = 'counter ' + (errs.length ? 'has-err' : warns.length ? 'has-warn' : '');
  const parts = ['Report: ', h('span', { class: 'e' }, errs.length + ' errors'), ' · ',
    h('span', { class: 'w' }, warns.length + ' warnings'),
    ' · ' + (rep.unsure || 0) + ' unconfirmed · ' + (rep.unplaced || 0) + ' unplaced'];
  if (rep.txt === false) parts.push(h('span', { class: 'e' }, ' · logic.txt NOT regenerated (there are errors)'));
  $('#report-summary').replaceChildren(...parts);
  const body = $('#report-body');
  body.replaceChildren();
  const items = errs.map(t => ({ t, cls: 'err' })).concat(warns.map(t => ({ t, cls: 'warn' })));
  if (!items.length) { body.append(h('div', { class: 'ok' }, 'No errors or warnings.')); return; }
  const here = [], other = [];
  for (const it of items) { it.room = reportRoomOf(it.t); (it.room === S.room ? here : other).push(it); }
  if (here.length) body.append(h('div', { class: 'dim' }, 'Current room (' + roomLabel(S.room) + '):'));
  for (const it of here.concat(other)) {
    body.append(h('div', {
      class: 'it ' + it.cls + (it.room === S.room ? ' here' : '') + (it.room ? ' jump' : ''),
      title: it.room ? 'Go to ' + roomLabel(it.room) : null,
      onclick: it.room ? () => switchRoom(it.room) : null,
    }, it.t));
  }
}
function toggleReport() {
  const b = $('#report-body');
  b.hidden = !b.hidden;
  $('#report-toggle').textContent = b.hidden ? '▴' : '▾';
}

Object.assign(LE, { reportRoomOf, renderReport, toggleReport });
})(window.LogicEditor || (window.LogicEditor = {}));
