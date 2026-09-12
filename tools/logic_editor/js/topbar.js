/* topbar.js - header widgets: area and room tabs (with error badges), the layer toggles persisted in
 * localStorage, the search box with keyboard navigation, panel toggling and the button bindings. */
(function (LE) {
'use strict';
const { W, DOC, S, CV, $, h, LAYER_DEFS, areaLabel, roomLabel, regionName, checkPosition, roomNodes } = LE;
const { select, switchRoom, setMode, fitView, zoomAt, doValidate, reportRoomOf, toggleReport } = LE;

// ---- tabs
function renderTabs() {
  const areas = [];
  for (const r of W.room_order) { const a = W.rooms[r].area; if (!areas.includes(a)) areas.push(a); }
  const curArea = W.rooms[S.room].area;
  $('#area-tabs').replaceChildren(...areas.map(a => h('button', {
    class: a === curArea ? 'active' : '', title: 'Area ' + areaLabel(a),
    onclick: () => switchRoom(W.room_order.find(r => W.rooms[r].area === a)),
  }, areaLabel(a))));
  const counts = reportCountsByRoom();
  $('#room-tabs').replaceChildren(...W.room_order.filter(r => W.rooms[r].area === curArea).map(r => {
    const c = counts[r];
    return h('button', {
      class: r === S.room ? 'active' : '', title: r + (c ? ' · ' + c.e + ' errors, ' + c.w + ' warnings' : ''),
      onclick: () => switchRoom(r),
    }, roomLabel(r), c ? h('span', { class: 'badge' + (c.e ? ' err' : '') }, c.e || c.w) : null);
  }));
}
function reportCountsByRoom() {
  const rep = S.report || {};
  const counts = {};
  const bump = (text, key) => {
    const r = reportRoomOf(text);
    if (r) { counts[r] = counts[r] || { e: 0, w: 0 }; counts[r][key]++; }
  };
  for (const t of (rep.errors || [])) bump(t, 'e');
  for (const t of (rep.warnings || [])) bump(t, 'w');
  return counts;
}
function renderLayers() {
  $('#layers').replaceChildren(...LAYER_DEFS.map(([k, label]) => {
    const cb = h('input', { type: 'checkbox', checked: !!S.layers[k], onchange: () => {
      S.layers[k] = cb.checked; lab.classList.toggle('on', cb.checked); CV.dirty = true;
      try { localStorage.setItem('mmzx-logic-layers', JSON.stringify(S.layers)); } catch (e) { /* nothing */ }
    } });
    const lab = h('label', { class: S.layers[k] ? 'on' : '', title: 'Layer: ' + label }, cb, label);
    return lab;
  }));
}

// ---- search over locations, regions and edges
let searchItems = null, searchActive = -1;
function buildSearchIndex() {
  const items = [];
  for (const name of Object.keys(W.locations)) {
    items.push({ kind: 'loc', name, text: name.toLowerCase(), k: 'location' });
  }
  for (const r of W.room_order) {
    for (const rid of Object.keys(DOC.rooms[r].regions)) {
      items.push({ kind: 'region', room: r, rid, name: roomLabel(r) + ' / ' + regionName(r, rid),
        text: (roomLabel(r) + ' ' + regionName(r, rid) + ' ' + rid).toLowerCase(), k: 'region' });
    }
  }
  for (const e of W.edges) items.push({ kind: 'edge', name: e.name, text: e.name.toLowerCase(), k: 'edge', edge: e });
  return items;
}
function hideSearch() { $('#search-results').hidden = true; searchActive = -1; }
function searchWhere(it) {
  if (it.kind === 'loc') {
    const [r] = checkPosition(it.name);
    return r ? roomLabel(r) : 'unplaced [' + (W.locations[it.name].room || '?') + ']';
  }
  if (it.kind === 'edge') return roomLabel(it.edge.src) + ' → ' + roomLabel(it.edge.dst);
  return '';
}
function runSearch() {
  const q = $('#search').value.trim().toLowerCase();
  const box = $('#search-results');
  if (!q) { hideSearch(); return; }
  const items = buildSearchIndex().filter(i => i.text.includes(q));
  items.sort((a, b) => a.text.indexOf(q) - b.text.indexOf(q) || a.name.length - b.name.length);
  searchItems = items.slice(0, 40);
  searchActive = searchItems.length ? 0 : -1;
  box.replaceChildren();
  if (!searchItems.length) box.append(h('div', { class: 'empty' }, 'No results'));
  searchItems.forEach((it, i) => {
    const pick = (e) => { e.preventDefault(); goToSearch(it); };
    box.append(h('div', { class: 'item' + (i === searchActive ? ' active' : ''), onmousedown: pick },
      h('span', { class: 'k' }, it.k), h('span', null, it.name), h('span', { class: 'r' }, searchWhere(it))));
  });
  box.hidden = false;
}
function goToSearch(it) {
  hideSearch(); $('#search').blur();
  if (it.kind === 'loc') {
    const [r] = checkPosition(it.name);
    if (r) { switchRoom(r); select({ type: 'node', id: it.name }, { center: true }); }
    else select({ type: 'loc', name: it.name });
  } else if (it.kind === 'region') { switchRoom(it.room); select({ type: 'region', rid: it.rid }, { center: true }); }
  else if (it.kind === 'edge') {
    // the exit if it has a position, else the landing in the target room
    switchRoom(it.edge.src);
    if (roomNodes(S.room).byId[it.name]) { select({ type: 'node', id: it.name }, { center: true }); return; }
    switchRoom(it.edge.dst);
    if (roomNodes(S.room).byId[it.name + '@in']) select({ type: 'node', id: it.name + '@in' }, { center: true });
  }
}
function onSearchKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    if (searchItems && searchItems[searchActive]) goToSearch(searchItems[searchActive]);
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (!searchItems || !searchItems.length) return;
    searchActive = (searchActive + (e.key === 'ArrowDown' ? 1 : -1) + searchItems.length) % searchItems.length;
    const kids = $('#search-results').children;
    for (let i = 0; i < kids.length; i++) kids[i].classList.toggle('active', i === searchActive);
    if (kids[searchActive]) kids[searchActive].scrollIntoView({ block: 'nearest' });
  }
}

// ---- panels and buttons
function togglePanel(id) {
  const p = $('#' + id);
  p.hidden = !p.hidden;
  if (!p.hidden && id === 'gates-panel') LE.renderGates();
}
function bindTop() {
  $('#tier').value = S.tier;
  $('#tier').addEventListener('change', (e) => {
    S.tier = e.target.value; CV.dirty = true; LE.renderInspector(); LE.renderTree();
  });
  $('#btn-validate').addEventListener('click', doValidate);
  $('#btn-txt').addEventListener('click', () => window.open('/api/txt', '_blank'));
  $('#btn-gates').addEventListener('click', () => { S.gatesTarget = null; togglePanel('gates-panel'); });
  $('#btn-help').addEventListener('click', () => togglePanel('help-panel'));
  $('#counter').addEventListener('click', toggleReport);
  $('#report-head').addEventListener('click', toggleReport);
  for (const b of document.querySelectorAll('#tools button')) {
    b.addEventListener('click', () => setMode(b.dataset.mode));
  }
  $('#zoom-in').addEventListener('click', () => zoomAt(CV.w / 2, CV.h / 2, 1.25));
  $('#zoom-out').addEventListener('click', () => zoomAt(CV.w / 2, CV.h / 2, 1 / 1.25));
  $('#zoom-fit').addEventListener('click', fitView);
  for (const b of document.querySelectorAll('.panel-close')) {
    b.addEventListener('click', () => { $('#' + b.dataset.close).hidden = true; });
  }
  const si = $('#search');
  si.addEventListener('input', runSearch);
  si.addEventListener('focus', runSearch);
  si.addEventListener('blur', () => setTimeout(hideSearch, 150));   // let a click on a result land first
  si.addEventListener('keydown', onSearchKeydown);
}

Object.assign(LE, { renderTabs, renderLayers, hideSearch, togglePanel, bindTop });
})(window.LogicEditor || (window.LogicEditor = {}));
