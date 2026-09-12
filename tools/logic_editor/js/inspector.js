/* inspector.js - right panel: the inspector of the current selection (room, region, connection, node,
 * unplaced location, gimmick) with its requirement editors, notes, region pinning and boss arena.
 * Field helpers (noteField, unsureField, kv) are shared with the gates panel. */
(function (LE) {
'use strict';
const { Logic, W, DOC, S, $, h, KIND_LABELS, catColor, catLabel } = LE;
const { RL, regionOrder, regionName, regionColor, roomLabel, findConn, edit, pushUndo, changed } = LE;
const { ensureEdge, pruneEdge, ensureCheck, pruneCheck, peekCheck, peekEdge, placementsOf, altRooms } = LE;
const { roomNodes, landingRid, nodeTooltip, isLockedKey, keyColor, gateText, reqShort, askText, flash } = LE;
const { select, switchRoom, setMode, deleteRegion, deleteSelection, removePlacement, startPlacing, addConn } = LE;
const { ICON, reqEditor } = LE;

// ---- field helpers
// Text fields take one undo step per editing burst (first keystroke until blur).
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
  const ta = h('textarea', { class: 'note', rows: 2, value: obj[key] || '', placeholder: 'free note' });
  return h('div', { class: 'field col' }, h('label', null, 'Note'), bindNote(getObj, key, ta, opts));
}
function unsureField(getObj, opts = {}) {
  const cur = (opts.peek || getObj)();
  const onchange = () => {
    edit(() => { getObj().unsure = cb.checked; if (opts.after) opts.after(); }, { keepInspector: true });
  };
  const cb = h('input', { type: 'checkbox', checked: !!cur.unsure, onchange });
  const label = h('label', { title: 'Rule not confirmed in-game ("?" in logic.txt)' }, cb, 'Unconfirmed in-game (?)');
  return h('div', { class: 'field' }, label);
}
function regionSelectField(node) {
  const rl = RL();
  const sel = h('select', { title: 'Region of the node: automatic (geometry) or pinned by hand' },
    h('option', { value: '' }, 'Automatic: ' + regionName(S.room, node.autoRid)));
  for (const rid of regionOrder(rl)) {
    sel.append(h('option', { value: rid, selected: node.pinned && node.rid === rid },
      'Pin to ' + regionName(S.room, rid)));
  }
  sel.addEventListener('change', () => {
    edit(() => { if (sel.value === '') delete rl.members[node.id]; else rl.members[node.id] = sel.value; });
  });
  const unpin = h('button', { class: 'small', title: 'Back to geometric membership',
    onclick: () => edit(() => { delete rl.members[node.id]; }) }, 'Unpin');
  return h('div', { class: 'field' }, h('label', null, 'Region'), sel, node.pinned ? unpin : null);
}
function kv(pairs) {
  const g = h('div', { class: 'kv' });
  for (const [k, v] of pairs) {
    if (v != null && v !== '') g.append(h('span', { class: 'k' }, k), h('span', { class: 'v' }, v));
  }
  return g;
}
const swatch = (color) => h('span', { class: 'sw', style: 'background:' + color });
const actions = (...buttons) => h('div', { class: 'actions' }, ...buttons);
// Requirement editor of a check, by location name (placed or not).
function checkReqFields(el, name, nullLabel) {
  el.append(h('h3', null, 'Requirement to obtain the check'));
  el.append(reqEditor({ nullable: true, nullLabel,
    get: () => (DOC.checks[name] || {}).req || null,
    set: (r) => edit(() => { ensureCheck(name).req = r; pruneCheck(name); }, { keepInspector: true }) }));
  el.append(unsureField(() => ensureCheck(name), { peek: () => peekCheck(name), after: () => pruneCheck(name) }));
  el.append(noteField(() => ensureCheck(name), 'note', { peek: () => peekCheck(name), after: () => pruneCheck(name) }));
}

// ---- dispatch
function renderInspector() {
  const el = $('#inspector');
  el.replaceChildren();
  if (!S.room) return;
  const s = S.sel;
  const rl = RL();
  if (s.type === 'room') return inspectRoom(el, rl);
  if (s.type === 'region') return rl.regions[s.rid] ? inspectRegion(el, rl, s.rid) : inspectRoom(el, rl);
  if (s.type === 'conn') {
    const c = findConn(rl, s.from, s.to);
    return c ? inspectConn(el, rl, c) : inspectRoom(el, rl);
  }
  if (s.type === 'node') {
    const n = roomNodes(S.room).byId[s.id];
    return n ? inspectNode(el, rl, n) : inspectRoom(el, rl);
  }
  if (s.type === 'loc') return inspectUnplacedLoc(el, s.name);
  if (s.type === 'gimmick') return inspectGimmick(el, s.idx);
}

// ---- room
function inspectRoom(el, rl) {
  const info = W.rooms[S.room];
  const access = W.transerver_access[S.room] ? ' · Transerver: ' + W.transerver_access[S.room] : '';
  const kind = S.room + ' · subarea ' + info.sub + ' · ' + info.size[0] + '×' + info.size[1] + ' px' + access;
  el.append(h('h2', null, 'Room ' + roomLabel(S.room)), h('div', { class: 'kind' }, kind));
  el.append(h('h3', null, 'Entry requirement (to be in the room)'));
  el.append(reqEditor({ nullable: true, nullLabel: 'No entry requirement', get: () => rl.req,
    set: (r) => edit(() => { rl.req = r; }, { keepInspector: true }) }));
  el.append(noteField(() => rl));
  el.append(h('h3', null, 'Regions (' + regionOrder(rl).length + ')'));
  const list = h('div', { class: 'list' });
  for (const rid of regionOrder(rl)) list.append(regionRow(rl, rid));
  el.append(list);
  el.append(actions(h('button', { title: 'Draw a polygon (P)', onclick: () => setMode('poly') },
    '+ Region (draw polygon)')));
  el.append(h('h3', null, 'Connections (' + rl.conns.length + ')'));
  el.append(connList(rl, rl.conns));
  if (regionOrder(rl).length > 1) el.append(newConnForm(rl, 'main'));
}
function regionRow(rl, rid) {
  const reg = rl.regions[rid];
  const nn = roomNodes(S.room).list.filter(n => n.rid === rid).length;
  const colorIn = h('input', { type: 'color', value: reg.color || '#8ab4f8', title: 'Color',
    onclick: (e) => e.stopPropagation(),
    onchange: () => edit(() => { reg.color = colorIn.value; }, { keepInspector: true }) });
  const rename = async (e) => {
    e.stopPropagation();
    const nm = await askText('Region name', reg.name || rid);
    if (nm !== null && nm.trim()) edit(() => { reg.name = nm.trim(); });
  };
  const del = h('button', { class: 'small danger', title: 'Delete the region (its nodes go back to the geometry)',
    onclick: (e) => { e.stopPropagation(); deleteRegion(rid); } }, '×');
  return h('div', { class: 'row-item', onclick: () => select({ type: 'region', rid }, { center: true }) },
    colorIn, h('span', { class: 'grow' }, reg.name || rid, ' ', h('span', { class: 'dim' }, '(' + nn + ')')),
    h('button', { class: 'small', title: 'Rename', onclick: rename }, '✎'),
    rid !== 'main' ? del : null);
}
function connList(rl, conns) {
  const list = h('div', { class: 'list' });
  if (!conns.length) list.append(h('div', { class: 'dim' }, 'none'));
  for (const c of conns) {
    const isSel = S.sel.type === 'conn' && S.sel.from === c.from && S.sel.to === c.to;
    const pick = () => select({ type: 'conn', from: c.from, to: c.to }, { center: true });
    list.append(h('div', { class: 'row-item' + (isSel ? ' sel' : ''), onclick: pick },
      swatch(regionColor(S.room, c.from)),
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

// ---- region
// Boss arena: marks this region as the place where a boss is fought. The apworld ANDs the requirement
// the player sets in their YAML (boss_logic option) into EVERY edge that lands here, so without meeting
// it you do not get in, do not cross to the other side and do not pick up anything inside. NO
// requirement is written here: it only says where each boss is. One boss, one arena.
function bossOwner(bossId) {
  for (const [room, rl] of Object.entries(DOC.rooms || {})) {
    for (const [rid, reg] of Object.entries(rl.regions || {})) if (reg.boss === bossId) return { room, rid };
  }
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
  const shape = rid === 'main' ? 'rest of the room (no polygon)' : (reg.poly || []).length + ' vertices';
  el.append(h('h2', null, swatch(reg.color), 'Region ', reg.name || rid),
    h('div', { class: 'kind' }, 'id ' + rid + ' · ' + shape + ' · ' + nodes.length + ' nodes'));
  const nameIn = h('input', { type: 'text', value: reg.name || '' });
  nameIn.addEventListener('change', () => {
    if (nameIn.value.trim()) edit(() => { reg.name = nameIn.value.trim(); });
  });
  const colorIn = h('input', { type: 'color', value: reg.color || '#8ab4f8',
    onchange: () => edit(() => { reg.color = colorIn.value; }, { keepInspector: true }) });
  el.append(h('div', { class: 'field' }, h('label', null, 'Name'), nameIn, colorIn));
  el.append(bossField(reg, rid));
  el.append(noteField(() => reg));
  if (rid !== 'main') el.append(regionActions(rid));
  el.append(h('h3', null, 'Member nodes (' + nodes.length + ')'));
  const list = h('div', { class: 'list' });
  if (!nodes.length) list.append(h('div', { class: 'dim' }, 'none'));
  for (const n of nodes) list.append(memberRow(n));
  el.append(list);
  el.append(h('h3', null, 'Connections'));
  el.append(newConnForm(rl, rid));
  el.append(connList(rl, rl.conns.filter(c => c.from === rid || c.to === rid)));
}
function regionActions(rid) {
  const editPoly = () => {
    setMode('select'); select({ type: 'region', rid }, { center: true });
    flash('Edit the vertices on the canvas (see ? for the shortcuts)');
  };
  const editTitle = 'Vertices are dragged on the canvas; double click on a side inserts; right click deletes; ' +
    'Shift+drag moves';
  return actions(
    h('button', { onclick: editPoly, title: editTitle }, 'Edit polygon'),
    h('button', { class: 'danger', title: 'Delete the region (Del)', onclick: () => deleteRegion(rid) },
      'Delete region'));
}
function memberRow(n) {
  const edgeName = n.type !== 'check' ? h('span', { class: 'dim mono' }, n.edge.name) : null;
  const pick = () => select({ type: 'node', id: n.id }, { center: true });
  return h('div', { class: 'row-item', title: nodeTooltip(n), onclick: pick },
    ICON(n),
    h('span', { class: 'grow' }, n.type === 'check' ? n.name : n.label + '  ', edgeName),
    n.pinned ? h('span', { class: 'pin' }, '📌') : null);
}

// ---- connection
function inspectConn(el, rl, c) {
  el.append(h('h2', null, 'Connection'), h('div', { class: 'kind' },
    swatch(regionColor(S.room, c.from)), regionName(S.room, c.from), ' → ',
    swatch(regionColor(S.room, c.to)), regionName(S.room, c.to)));
  el.append(h('h3', null, 'Requirement to pass'));
  el.append(reqEditor({ nullable: false, get: () => c.req || {},
    set: (r) => edit(() => { c.req = r; }, { keepInspector: true }) }));
  el.append(unsureField(() => c));
  el.append(noteField(() => c));
  const rev = findConn(rl, c.to, c.from);
  const invert = () => {
    edit(() => { const f = c.from; c.from = c.to; c.to = f; });
    select({ type: 'conn', from: c.from, to: c.to });
  };
  const del = () => { S.sel = { type: 'conn', from: c.from, to: c.to }; deleteSelection(); };
  const reverseBtn = rev
    ? h('button', { onclick: () => select({ type: 'conn', from: c.to, to: c.from }) }, 'Go to the reverse')
    : h('button', { title: 'Create the connection in the opposite direction (free)',
      onclick: () => addConn(rl, c.to, c.from, false) }, 'Create the reverse');
  const invertTitle = rev ? 'The reverse already exists' : 'Swap source and target';
  el.append(actions(reverseBtn,
    h('button', { disabled: !!rev, title: invertTitle, onclick: invert }, 'Invert'),
    h('button', { class: 'danger', title: 'Delete (Del)', onclick: del }, 'Delete')));
}

// ---- nodes: a check, or the exit / landing of an edge
function inspectNode(el, rl, n) {
  if (n.type === 'check') inspectCheckNode(el, n); else inspectEdgeNode(el, n);
}
function inspectCheckNode(el, n) {
  const loc = W.locations[n.id];
  const kind = catLabel(n.cat) + (n.placed ? ' · placed by hand' : '') + (loc.detect ? '' : ' · no detection');
  el.append(h('h2', null, n.full), h('div', { class: 'kind' }, swatch(n.color), kind));
  const others = n.placed ? placementsOf(n.id).filter(q => q.room !== S.room).map(q => roomLabel(q.room)) : [];
  el.append(kv([
    ['Room', roomLabel(S.room)], ['Position', n.pos[0] + ', ' + n.pos[1]], ['Area tag', n.placed ? loc.room : null],
    ['Also in', others.length ? others.join(', ') + ' (any of them counts: OR)' : null],
  ]));
  el.append(regionSelectField(n));
  checkReqFields(el, n.id, 'No requirement (being in the region is enough)');
  if (n.placed) {
    el.append(actions(h('button', { class: 'danger', onclick: () => removePlacement(n),
      title: 'Remove the manual placement (goes back to "Unplaced")' }, 'Remove from the room')));
  }
}
function inspectEdgeNode(el, n) {
  const e = n.edge;
  const ov = () => DOC.edges[e.name] || {};
  el.append(h('h2', null, n.type === 'out' ? 'Edge exit' : 'Edge landing'), h('div', { class: 'kind mono' }, e.name));
  el.append(kv(edgePairs(n)));
  el.append(regionSelectField(n));
  if (n.type === 'out') {
    el.append(h('h3', null, 'Extra cost to use the edge'));
    el.append(reqEditor({ nullable: true, nullLabel: 'No extra cost (only key, gate and entry of the target room)',
      get: () => ov().req || null,
      set: (r) => edit(() => { ensureEdge(e.name).req = r; pruneEdge(e.name); }, { keepInspector: true }) }));
    el.append(unsureField(() => ensureEdge(e.name), { peek: () => peekEdge(e.name), after: () => pruneEdge(e.name) }));
    el.append(noteField(() => ensureEdge(e.name), 'note',
      { peek: () => peekEdge(e.name), after: () => pruneEdge(e.name) }));
  } else {
    const o = ov();
    if (o.req || o.note) {
      el.append(h('div', { class: 'dim' }, 'The edge rule is edited at its exit (' + roomLabel(e.src) + ').'));
    }
  }
  if (n.placed) {
    el.append(actions(h('button', { class: 'danger', title: 'Remove the hand-placed position',
      onclick: () => removePlacement(n) }, 'Remove position')));
  }
}
// Key / value rows of an edge node: type, position, the other end, key, gate, Transerver.
function edgePairs(n) {
  const e = n.edge;
  const other = n.type === 'out' ? e.dst : e.src;
  const otherId = n.type === 'out' ? e.name + '@in' : e.name;
  const goTo = () => {
    switchRoom(other);
    if (roomNodes(other).byId[otherId]) select({ type: 'node', id: otherId }, { center: true });
  };
  const goLabel = 'Go to ' + roomLabel(other);
  const goBtn = h('button', { class: 'small', title: goLabel, onclick: goTo }, goLabel);
  const pairs = [['Type', KIND_LABELS[e.kind] || e.kind],
    ['Position', n.pos[0] + ', ' + n.pos[1] + (n.placed ? ' (placed by hand)' : '')]];
  if (n.type === 'out') {
    const target = roomLabel(e.dst) + ' / ' + regionName(e.dst, landingRid(e)) + ' ';
    pairs.push(['Target', h('span', null, target, e.dst !== S.room ? goBtn : null)]);
  } else {
    const srcRid = roomNodes(e.src).members[e.name] || 'main';
    const from = roomLabel(e.src) + ' / ' + regionName(e.src, srcRid) + ' ';
    pairs.push(['From', h('span', null, from, e.src !== S.room ? goBtn : null)]);
  }
  if (e.kind === 'internal') {
    const m = roomNodes(S.room).members;
    pairs.push(['Internal', 'joins ' + regionName(S.room, m[e.name] || 'main') + ' → ' +
      regionName(S.room, m[e.name + '@in'] || 'main')]);
  }
  if (e.key) {
    const locked = isLockedKey(e)
      ? ' - NOT in the pool: the door is LOCKED in the logic (in vanilla it is only crossed on the way back)' : '';
    pairs.push(['Key', h('span', null, swatch(keyColor(e)), e.key + locked)]);
  }
  if (e.gate != null) {
    const seeGates = () => { S.gatesTarget = String(e.gate); $('#gates-panel').hidden = false; LE.renderGates(); };
    pairs.push(['Gate', h('span', null, e.gate + ': ' + gateText(e.gate) + ' ',
      h('a', { class: 'link', onclick: seeGates }, 'see gates'))]);
  }
  if (e.kind === 'warp' && e.src === W.hub) {
    pairs.push(['Transerver', W.transerver_access[e.dst] || 'no Transport destination']);
  }
  if (e.kind === 'save') pairs.push(['Note', 'pads do not create a transition (NON_TRANSITION_KINDS)']);
  return pairs;
}

// ---- unplaced location and gimmick
function inspectUnplacedLoc(el, name) {
  const loc = W.locations[name];
  if (!loc) return;
  const already = placementsOf(name);
  const where = already.length
    ? ' · placed in ' + already.map(q => roomLabel(q.room)).join(', ') +
      ' (' + already.length + '/' + altRooms(name) + ' rooms)'
    : ' · UNPLACED';
  el.append(h('h2', null, name),
    h('div', { class: 'kind' }, swatch(catColor(loc.category)), catLabel(loc.category) + where));
  el.append(kv([['Area tag', loc.room || '?'],
    ['Current rule', already.length ? 'reach any of its rooms (OR) ∧ requirement' : 'fallback by area tag']]));
  el.append(actions(h('button', { class: 'primary', title: 'Click on the canvas of the current room to place it',
    onclick: () => startPlacing({ kind: 'loc', id: name }) },
  'Place in ' + roomLabel(S.room) + ' (click on the canvas)')));
  checkReqFields(el, name, 'No requirement');
}
function inspectGimmick(el, idx) {
  const g = (W.gimmicks[S.room] || [])[idx];
  if (!g) return;
  el.append(h('h2', null, g.name), h('div', { class: 'kind' }, g.layer === 'enemies' ? 'enemy' : 'gimmick'));
  el.append(kv([
    ['Position', g.pos[0] + ', ' + g.pos[1]], ['kind / sub', g.kind + ' / ' + g.sub],
    ['role / mod', g.role + ' / ' + g.mod], ['Region', regionName(S.room, Logic.regionOfPoint(RL(), g.pos))],
  ]));
  el.append(h('div', { class: 'dim' }, 'Informational only: gimmicks are not part of the logic.'));
}

Object.assign(LE, { noteField, unsureField, kv, renderInspector });
})(window.LogicEditor || (window.LogicEditor = {}));
