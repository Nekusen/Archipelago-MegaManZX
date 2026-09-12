/* nodes.js - the nodes of a room (checks, edge exits and landings) derived from W and DOC with their
 * region membership, labels and tooltips, cached per document version; region centroids; and the
 * short requirement texts shown in the UI. */
(function (LE) {
'use strict';
const { Logic, W, DOC, S, KIND_LABELS, KEY_COLOR, NOKEY, IN_COLOR, catColor, catLabel, polyCentroid } = LE;
const { regionName, roomLabel, roomSize, placementIn, placementsOf, altRooms } = LE;

let cache = { v: -1, nodes: {}, cent: {}, unplacedLocs: null };
function ensureCache() {
  if (cache.v !== S.docVersion) cache = { v: S.docVersion, nodes: {}, cent: {}, unplacedLocs: null };
}

function edgeEndpoints(e) {
  const ov = DOC.edges[e.name] || {};
  const pos = ov.pos || e.pos || null;
  let dpos = ov.dst_pos || e.dst_pos || null;
  if (dpos && dpos[0] == null) dpos = null;
  return [pos, dpos];
}
function shortName(name, room) {
  const p = roomLabel(room) + ': ';
  return name.startsWith(p) ? name.slice(p.length) : name;
}
// {list, byId, members: {nodeId: rid}, un: {outs, ins}} where `un` lists the edges without a position.
function roomNodes(room) {
  ensureCache();
  if (cache.nodes[room]) return cache.nodes[room];
  const rl = DOC.rooms[room];
  const list = [], byId = {}, members = {};
  const un = { outs: [], ins: [] };
  const add = (n) => { list.push(n); byId[n.id] = n; };
  for (const name of Object.keys(W.locations)) {
    const loc = W.locations[name];
    let pos = null;
    if (loc.pos && loc.room === room) pos = loc.pos;
    else if (!loc.pos) { const q = placementIn(name, room); if (q) pos = q.pos; }
    if (!pos) continue;
    add({ id: name, type: 'check', full: name, name: shortName(name, room), pos,
      placed: !(loc.pos && loc.room === room), cat: loc.category, color: catColor(loc.category), detect: loc.detect });
  }
  for (const e of W.edges) {
    const [pos, dpos] = edgeEndpoints(e);
    if (e.src === room) {
      if (pos) {
        add({ id: e.name, type: 'out', full: e.name, edge: e, pos, placed: !e.pos,
          color: keyColor(e), locked: isLockedKey(e) });
      } else un.outs.push(e);
    }
    if (e.dst === room) {
      if (dpos) {
        add({ id: e.name + '@in', type: 'in', full: e.name + '@in', edge: e, pos: dpos, placed: !e.dst_pos,
          color: IN_COLOR });
      } else un.ins.push(e);
    }
  }
  for (const n of list) {
    const ov = rl.members[n.id];
    if (ov && rl.regions[ov]) { n.rid = ov; n.pinned = true; }
    else { n.rid = Logic.regionOfPoint(rl, n.pos); n.pinned = false; }
    n.autoRid = Logic.regionOfPoint(rl, n.pos);
    members[n.id] = n.rid;
  }
  // nodes without a position: override or main (like resolve_members)
  const pinnedOrMain = (id) => (rl.members[id] && rl.regions[rl.members[id]]) ? rl.members[id] : 'main';
  for (const e of un.outs) members[e.name] = pinnedOrMain(e.name);
  for (const e of un.ins) members[e.name + '@in'] = pinnedOrMain(e.name + '@in');
  const out = { list, byId, members, un };
  cache.nodes[room] = out;   // before the labels: nodeLabel queries the membership of OTHER rooms (cycles A-1 <-> A-4)
  for (const n of list) n.label = nodeLabel(n);
  return out;
}
function landingRid(e) { return roomNodes(e.dst).members[e.name + '@in'] || 'main'; }
function nodeLabel(n) {
  if (n.type === 'check') return n.name;
  const e = n.edge;
  if (n.type === 'out') {
    if (e.kind === 'internal') return '↔ internal';
    if (e.kind === 'save') return 'pad';
    const rid = landingRid(e);
    const dst = roomLabel(e.dst) + (rid !== 'main' ? '/' + regionName(e.dst, rid) : '');
    if (e.kind === 'warp') return '⇄ ' + dst;
    if (e.kind === 'curated') return '⇢ ' + dst;
    return '→ ' + dst;
  }
  if (e.kind === 'internal') return '← internal';
  if (e.kind === 'save') return '← ' + roomLabel(e.src) + ' (pad)';
  if (e.kind === 'warp') return '⇄ ' + roomLabel(e.src);
  return '← ' + roomLabel(e.src);
}
function nodeTooltip(n) {
  const reg = regionName(S.room, n.rid) + (n.pinned ? ' (pinned)' : '');
  if (n.type === 'check') {
    const ch = DOC.checks[n.id] || {};
    return n.full + '\n' + catLabel(n.cat) + (n.placed ? ' · placed by hand' : '') + ' · region ' + reg +
      '\nrequirement: ' + reqUiText(ch.req) + (ch.unsure ? ' (?)' : '');
  }
  const e = n.edge, ov = DOC.edges[e.name] || {};
  let s = e.name + '\n' + (n.type === 'out' ? 'exit' : 'landing') + ' · ' + (KIND_LABELS[e.kind] || e.kind);
  s += n.type === 'out'
    ? ' → ' + roomLabel(e.dst) + '/' + regionName(e.dst, landingRid(e))
    : ' from ' + roomLabel(e.src);
  if (e.key) s += '\nkey: ' + e.key + (isLockedKey(e) ? ' (NOT in the pool: locked door)' : '');
  if (e.gate != null) s += '\ngate ' + e.gate + ': ' + gateText(e.gate);
  if (e.kind === 'warp' && e.src === W.hub && W.transerver_access[e.dst]) s += '\nneeds ' + W.transerver_access[e.dst];
  s += '\nregion ' + reg;
  if (ov.req) s += '\nextra cost: ' + reqUiText(ov.req);
  return s;
}
// key whose item is NOT in the pool (e.g. White Card Key): the door stays locked in the logic (the
// server says so via W.unavailable_items)
function isLockedKey(e) { return !!(e && e.key && (W.unavailable_items || []).includes(e.key)); }
function keyColor(e) { return isLockedKey(e) ? '#555' : (e.key ? (KEY_COLOR[e.key] || NOKEY) : NOKEY); }
function unplacedLocations() {
  ensureCache();
  if (!cache.unplacedLocs) {
    cache.unplacedLocs = Object.keys(W.locations).filter(n => !W.locations[n].pos && placementsOf(n).length === 0);
  }
  return cache.unplacedLocs;
}
// placed in some room but with more possible rooms (biometals: 2 bosses)
function multiCandidates() {
  return Object.keys(W.locations).filter(n => !W.locations[n].pos && placementsOf(n).length > 0 &&
    placementsOf(n).length < altRooms(n));
}
// Centroid of a polygon region; for main (or a polygon-less region) the mean of its nodes, else the
// room center. Used to anchor connection arrows and labels.
function regionCentroid(room, rid) {
  ensureCache();
  const k = room + '/' + rid;
  if (cache.cent[k]) return cache.cent[k];
  const rl = DOC.rooms[room];
  let c;
  const reg = rl.regions[rid];
  if (rid !== 'main' && reg && reg.poly && reg.poly.length >= 3) c = polyCentroid(reg.poly);
  else {
    const nodes = roomNodes(room).list.filter(n => n.rid === rid);
    if (nodes.length) {
      let sx = 0, sy = 0;
      for (const n of nodes) { sx += n.pos[0]; sy += n.pos[1]; }
      c = [sx / nodes.length, sy / nodes.length];
    } else { const sz = roomSize(room); c = [sz[0] / 2, sz[1] / 2]; }
  }
  cache.cent[k] = c;
  return c;
}
function gateText(flag) {
  const g = DOC.gates[String(flag)];
  if (!g || g.req == null) return 'free (the client opens it)';
  return reqUiText(g.req);
}
function reqUiText(req, tier) {
  const t = Logic.dnfToText(Logic.reqAlternatives(req, tier || S.tier));
  return t === 'free' ? 'free' : t === 'never' ? 'impossible' : t;
}
function reqShort(req, tier, max = 34) {
  let t = reqUiText(req, tier);
  if (t.length > max) t = t.slice(0, max - 1) + '…';
  return t;
}

Object.assign(LE, {
  roomNodes, landingRid, nodeLabel, nodeTooltip, isLockedKey, keyColor, unplacedLocations, multiCandidates,
  regionCentroid, gateText, reqUiText, reqShort,
});
})(window.LogicEditor || (window.LogicEditor = {}));
