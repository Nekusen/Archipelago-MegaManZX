/* gates.js - the "Event gates" panel: one card per event flag with the edges it closes and the
 * requirement to open it (null = the client opens it). */
(function (LE) {
'use strict';
const { W, DOC, S, $, h, roomLabel, ensureGate, peekGate, edit, roomNodes } = LE;
const { select, switchRoom, reqEditor, noteField } = LE;

function renderGates() {
  const body = $('#gates-body');
  body.replaceChildren();
  const flags = Array.from(new Set(Object.keys(W.gate_edges).concat(Object.keys(DOC.gates))))
    .sort((a, b) => Number(a) - Number(b));
  if (!flags.length) { body.append(h('div', { class: 'dim' }, 'There are no event gates on the edges.')); return; }
  body.append(h('div', { class: 'dim', style: 'margin-bottom:8px' },
    'Full rule of an edge = key ∧ gate ∧ entry of the target room ∧ extra cost. ' +
    '"Free" gate = null: the client opens it.'));
  for (const flag of flags) body.append(gateCard(flag));
  if (S.gatesTarget) { const t = body.querySelector('.gate.target'); if (t) t.scrollIntoView({ block: 'start' }); }
}
function gateCard(flag) {
  const edges = (W.gate_edges[flag] || []).map(n => W.edges.find(e => e.name === n)).filter(Boolean);
  const openByClient = W.event_gates_open.includes(Number(flag));
  const card = h('div', { class: 'gate' + (S.gatesTarget === flag ? ' target' : '') },
    h('h4', null, 'Gate ' + flag,
      openByClient ? h('span', { class: 'open' }, '  · the client opens it (EVENT_GATES_OPEN)') : null));
  const ed = h('div', { class: 'edges' });
  if (!edges.length) ed.append('no edges in data');
  for (const e of edges) {
    const go = () => {
      $('#gates-panel').hidden = true; switchRoom(e.src);
      if (roomNodes(e.src).byId[e.name]) select({ type: 'node', id: e.name }, { center: true });
    };
    ed.append(h('a', { class: 'link', onclick: go },
      roomLabel(e.src) + ' → ' + roomLabel(e.dst) + '  (' + e.name + ')' + (e.key ? ' · ' + e.key : '')));
  }
  card.append(ed);
  card.append(reqEditor({
    nullable: true, nullLabel: 'Free: the client opens it (null)',
    get: () => (DOC.gates[flag] || {}).req || null,
    set: (r) => edit(() => { ensureGate(flag).req = r; }, { keepInspector: true }),
  }));
  card.append(noteField(() => ensureGate(flag), 'note', { peek: () => peekGate(flag) }));
  return card;
}

Object.assign(LE, { renderGates });
})(window.LogicEditor || (window.LogicEditor = {}));
