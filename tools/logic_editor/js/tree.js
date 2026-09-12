/* tree.js - left panel: the outline of the current room grouped by region (collapsible), plus the
 * "Unplaced" section with exits, landings and locations that can be dragged onto the canvas. */
(function (LE) {
'use strict';
const { W, S, $, h, KEY_COLOR, NOKEY, IN_COLOR, catColor } = LE;
const { RL, regionOrder, roomLabel, roomNodes, nodeTooltip, isLockedKey, unplacedLocations, multiCandidates } = LE;
const { placementsOf, placementIn, altRooms, select, startPlacing, autoPlaceHubWarps } = LE;

const ICON = (n) => {
  const cls = 'ico ' + (n.placed ? 'hex' : n.type === 'check' ? 'sq' : n.type === 'out' ? 'tri' : 'cir');
  return h('span', { class: cls, style: 'background:' + n.color + ';color:' + n.color });
};
const TREE_ORDER = { check: 0, out: 1, in: 2 };

function renderTree() {
  const el = $('#tree');
  el.replaceChildren();
  if (!S.room) return;
  const rl = RL();
  const nodes = roomNodes(S.room);
  for (const rid of regionOrder(rl)) el.append(regionBlock(rl, rid, nodes));
  el.append(unplacedSection(nodes));
}
function regionBlock(rl, rid, nodes) {
  const reg = rl.regions[rid];
  const members = nodes.list.filter(n => n.rid === rid)
    .sort((a, b) => TREE_ORDER[a.type] - TREE_ORDER[b.type] || a.label.localeCompare(b.label));
  const key = S.room + '/' + rid;
  const collapsed = S.collapsed.has(key);
  const toggle = (e) => {
    e.stopPropagation();
    if (collapsed) S.collapsed.delete(key); else S.collapsed.add(key);
    renderTree();
  };
  const head = h('div', {
    class: 'tree-head' + (S.sel.type === 'region' && S.sel.rid === rid ? ' sel' : ''),
    title: 'Region ' + (reg.name || rid) + ' (' + rid + ')',
    onclick: () => select({ type: 'region', rid }, { center: true }),
  },
  h('span', { class: 'caret', onclick: toggle }, collapsed ? '▸' : '▾'),
  h('span', { class: 'sw', style: 'background:' + reg.color }),
  h('span', { class: 'name' }, reg.name || rid),
  h('span', { class: 'n' }, members.length));
  const list = h('div', { class: 'tree-nodes' });
  for (const n of members) list.append(treeNode(n));
  if (!members.length) list.append(h('div', { class: 'empty dim' }, 'empty'));
  return h('div', { class: 'tree-region' + (collapsed ? ' collapsed' : '') }, head, list);
}
function unplacedSection(nodes) {
  const sec = h('div', { class: 'tree-section' }, h('h4', null, 'Unplaced'));
  const un = nodes.un;
  const hubTodo = S.room === W.hub ? un.outs.filter(e => e.kind === 'warp' && !e.pos) : [];
  if (hubTodo.length) {
    sec.append(h('div', { class: 'actions' }, h('button', {
      class: 'small', title: 'Places each "z01 transerver to X" warp at (368, floor of the target area); N at x=560',
      onclick: autoPlaceHubWarps,
    }, 'Auto-place hub warps (' + hubTodo.length + ')')));
  }
  if (un.outs.length) {
    sec.append(h('div', { class: 'sub' },
      'Exits of ' + roomLabel(S.room) + ' without a position (' + un.outs.length + ')'));
    for (const e of un.outs) {
      const fake = { type: 'out', placed: true, color: e.key ? (KEY_COLOR[e.key] || NOKEY) : NOKEY };
      sec.append(unplacedRow({ kind: 'out', id: e.name }, fake, e.name, '→ ' + roomLabel(e.dst)));
    }
  }
  if (un.ins.length) {
    sec.append(h('div', { class: 'sub' },
      'Landings in ' + roomLabel(S.room) + ' without a position (' + un.ins.length + ')'));
    for (const e of un.ins) {
      const fake = { type: 'in', placed: true, color: IN_COLOR };
      sec.append(unplacedRow({ kind: 'in', id: e.name }, fake, e.name, '← ' + roomLabel(e.src)));
    }
  }
  sec.append(...multiRoomRows());
  const locs = unplacedLocations();
  sec.append(h('div', { class: 'sub' }, 'Game locations without a room (' + locs.length + ')'));
  if (!locs.length) sec.append(h('div', { class: 'empty' }, 'none'));
  for (const name of locs) sec.append(locationRow(name, '[' + (W.locations[name].room || '?') + ']'));
  return sec;
}
// Locations placed in some room that can also be obtained in others (biometals: two bosses).
function multiRoomRows() {
  const multi = multiCandidates().filter(n => !placementIn(n, S.room));
  if (!multi.length) return [];
  const rows = [h('div', {
    class: 'sub',
    title: 'Obtained in any of several rooms (area tag with "/"): place them in each one; ' +
      'in the logic any of them counts (OR)',
  }, 'With several possible rooms: also place in (' + multi.length + ')')];
  for (const name of multi) {
    const done = placementsOf(name).map(q => roomLabel(q.room)).join(', ');
    rows.push(locationRow(name, placementsOf(name).length + '/' + altRooms(name) + ' · already in ' + done));
  }
  return rows;
}
function locationRow(name, tag) {
  const fake = { type: 'check', placed: true, color: catColor(W.locations[name].category) };
  const isSel = S.sel.type === 'loc' && S.sel.name === name;
  return unplacedRow({ kind: 'loc', id: name }, fake, name, tag, isSel, () => select({ type: 'loc', name }));
}
function treeNode(n) {
  let tag = null;
  if (n.type !== 'check') {
    const e = n.edge;
    if (e.key) tag = isLockedKey(e) ? '🔒 locked' : e.key.replace(' Card Key', '');
    else tag = e.gate != null ? 'gate ' + e.gate : '';
  }
  return h('div', {
    class: 'tree-node' + (S.sel.type === 'node' && S.sel.id === n.id ? ' sel' : ''), title: nodeTooltip(n),
    onclick: () => select({ type: 'node', id: n.id }, { center: true }),
  },
  ICON(n), h('span', { class: 'lbl' }, n.type === 'check' ? n.name : n.label),
  n.pinned ? h('span', { class: 'pin', title: 'Region pinned by hand' }, '📌') : null,
  tag !== null ? h('span', { class: 'tag' }, tag) : null);
}
// A draggable row of the "Unplaced" section; `fake` only carries what ICON needs.
function unplacedRow(data, fake, name, tag, isSel, onclick) {
  const dragStart = (e) => {
    e.dataTransfer.setData('text/plain', JSON.stringify(data));
    e.dataTransfer.effectAllowed = 'copy';
  };
  const place = (e) => { e.stopPropagation(); startPlacing(data); };
  return h('div', {
    class: 'tree-node drag' + (isSel ? ' sel' : ''), draggable: true,
    title: name + '\nDrag onto the canvas or press "Place" and click on the canvas',
    ondragstart: dragStart, onclick: onclick || null,
  },
  ICON(fake), h('span', { class: 'lbl' }, name), h('span', { class: 'tag' }, tag),
  h('button', { class: 'place', title: 'Place in this room: click on the canvas', onclick: place }, 'Place'));
}

Object.assign(LE, { ICON, renderTree });
})(window.LogicEditor || (window.LogicEditor = {}));
