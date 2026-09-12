/* logic_core.js - requirement algebra shared with logic_format.py: the default atom catalog, the
 * expression parser, DNF normalization, tier accumulation and point-in-polygon membership.
 * No DOM access. Exposed as LE.Logic; every other module goes through it. */
(function (LE) {
'use strict';

// Fallback catalog used until /api/world delivers the real one (logic_format.atom_catalog).
const DEFAULT_ATOMS = (() => {
  const out = [];
  const models = {
    HU: 'Hu (human form)', X: 'Model X', ZX: 'Model ZX', HX: 'Model HX',
    FX: 'Model FX', LX: 'Model LX', PX: 'Model PX', OX: 'Model OX',
  };
  for (const [id, label] of Object.entries(models)) out.push({ id, group: 'model', label });
  for (const m of ['HX', 'FX', 'LX', 'PX']) {
    out.push({ id: m + '2', group: 'model', label: 'Model ' + m + ' complete (2 halves: level 2 charge)' });
  }
  out.push({ id: 'MODEL', group: 'model', label: 'MODEL (any non-Hu model)' });
  out.push({ id: 'ALL6', group: 'model', label: 'ALL6 (all six biometals)' });
  for (const k of ['YELLOW', 'GREEN', 'RED', 'BLUE', 'WHITE', 'PURPLE']) {
    out.push({ id: k, group: 'key', label: k[0] + k.slice(1).toLowerCase() + ' Card Key' });
  }
  for (let n = 1; n <= 4; n++) out.push({ id: 'LIFEUP>=' + n, group: 'life', label: 'Life Up x' + n });
  for (let n = 1; n <= 4; n++) out.push({ id: 'SUBTANK>=' + n, group: 'life', label: 'Sub Tank x' + n });
  const missions = [
    'LOCATE_GIRO', 'PASS_THE_TEST', 'TROOP_REINFORCEMENT', 'SEARCH_THE_PLANT', 'FIND_THE_SURVIVORS',
    'FIGHT_THE_MAVERICKS', 'SECURE_THE_BIOMETAL', 'SAVE_THE_PEOPLE', 'RECOVER_THE_DISK',
    'ATTACK_THE_EXCAVATORS', 'PROTECT_THE_LAB', 'PROTECT_HQ', 'STOP_THE_DIG', 'REPEL_THE_ARMY',
    'DESTROY_MODEL_W',
  ];
  for (const m of missions) out.push({ id: m, group: 'mission', label: m });
  for (let n = 1; n <= 8; n++) {
    const label = 'Area missions completed x' + n + ' (of the 8: E-7...L-4)';
    out.push({ id: 'MISSIONS>=' + n, group: 'mission', label });
  }
  for (const a of 'ABCDEFGIKLMOX') {
    out.push({ id: 'ACCESS_' + a, group: 'transerver', label: 'Transerver Access - Area ' + a });
  }
  return out;
})();

let TIERS = ['normal', 'expert'];
let plain = new Set();      // atoms without a count
let counts = new Set();     // NAME prefixes of NAME>=n
let groups = {};            // id -> group
let catalog = [];
const CONST_TRUE = ['TRUE', 'ANY', 'FREE'];
const CONST_FALSE = ['FALSE', 'NEVER', 'IMPOSSIBLE'];
const COUNT_RE = /^([A-Z_]+)>=(\d+)$/;

function configure(atoms, tiers) {
  catalog = atoms || DEFAULT_ATOMS;
  if (tiers && tiers.length) TIERS = tiers.slice();
  plain = new Set(); counts = new Set(); groups = {};
  for (const a of catalog) {
    groups[a.id] = a.group;
    const m = COUNT_RE.exec(a.id);
    if (m) counts.add(m[1]); else plain.add(a.id);
  }
}
configure(DEFAULT_ATOMS);

function canonicalAtom(tok) {
  if (typeof tok !== 'string') return null;
  const t = tok.trim().toUpperCase().replace(/ /g, '');
  if (plain.has(t)) return t;
  const m = COUNT_RE.exec(t);
  if (m && counts.has(m[1])) {
    const n = parseInt(m[2], 10);
    if (n < 1) return null;
    return m[1] + '>=' + n;
  }
  return null;
}
const isValidAtom = (tok) => canonicalAtom(tok) !== null;
function groupOf(atom) {
  if (groups[atom]) return groups[atom];
  const m = COUNT_RE.exec(atom || '');
  if (m) for (const a of catalog) if (a.id.startsWith(m[1] + '>=')) return a.group;
  return '';
}

// ---- DNF: a requirement is a list of alternatives (OR), each a list of atoms (AND)
function dnfNormalize(dnf) {
  const alts = dnf.map(alt => { const s = []; for (const a of alt) if (!s.includes(a)) s.push(a); return s; });
  const keep = [];
  for (let i = 0; i < alts.length; i++) {
    const sa = new Set(alts[i]);
    let absorbed = false;
    for (let j = 0; j < alts.length; j++) {
      if (i === j) continue;
      const sb = new Set(alts[j]);
      let subset = true;
      for (const x of sb) if (!sa.has(x)) { subset = false; break; }
      if (!subset) continue;
      // a smaller alternative absorbs this one; equal ones keep the first occurrence
      if (sb.size < sa.size || (sb.size === sa.size && j < i)) { absorbed = true; break; }
    }
    if (!absorbed) keep.push(alts[i]);
  }
  return keep;
}
function dnfAnd(a, b) {
  const out = [];
  for (const x of a) for (const y of b) out.push(x.concat(y));
  return dnfNormalize(out);
}
const dnfOr = (a, b) => dnfNormalize(a.concat(b));
const DNF_TRUE = () => [[]];
const DNF_FALSE = () => [];

// ---- expression parser: HX & (LX | FX), and/or, + and , as AND, free/never constants
const TOK = /\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*>=\s*\d+)?|&&|\|\||[&|()+,])/y;
function tokens(expr) {
  const out = [];
  expr = expr.trim();
  let pos = 0;
  while (pos < expr.length) {
    TOK.lastIndex = pos;
    const m = TOK.exec(expr);
    if (!m) throw new Error('invalid expression at position ' + pos + ': "' + expr.slice(pos, pos + 12) + '"');
    out.push(m[1].replace(/ /g, ''));
    pos = TOK.lastIndex;
  }
  return out;
}
const isAnd = (t) => t === '&' || t === '&&' || t === '+' || t === ',' || t.toUpperCase() === 'AND';
const isOr = (t) => t === '|' || t === '||' || t.toUpperCase() === 'OR';
function parseExpr(expr) {
  if (expr == null) return DNF_TRUE();
  const toks = tokens(expr);
  if (!toks.length) return DNF_TRUE();
  const [dnf, i] = parseOr(toks, 0);
  if (i !== toks.length) throw new Error('leftover tokens starting at "' + toks[i] + '"');
  return dnf;
}
function parseOr(toks, i) {
  let [node, j] = parseAnd(toks, i);
  while (j < toks.length && isOr(toks[j])) {
    const [rhs, k] = parseAnd(toks, j + 1);
    node = dnfOr(node, rhs); j = k;
  }
  return [node, j];
}
function parseAnd(toks, i) {
  let [node, j] = parseAtom(toks, i);
  while (j < toks.length && isAnd(toks[j])) {
    const [rhs, k] = parseAtom(toks, j + 1);
    node = dnfAnd(node, rhs); j = k;
  }
  return [node, j];
}
function parseAtom(toks, i) {
  if (i >= toks.length) throw new Error('incomplete expression');
  const t = toks[i];
  if (t === '(') {
    const [node, j] = parseOr(toks, i + 1);
    if (j >= toks.length || toks[j] !== ')') throw new Error("missing ')'");
    return [node, j + 1];
  }
  const up = t.toUpperCase();
  if (CONST_TRUE.includes(up)) return [DNF_TRUE(), i + 1];
  if (CONST_FALSE.includes(up)) return [DNF_FALSE(), i + 1];
  const a = canonicalAtom(t);
  if (a === null) throw new Error('unknown atom "' + t + '"');
  return [[[a]], i + 1];
}
function dnfToText(dnf) {
  if (!dnf || !dnf.length) return 'never';
  if (dnf.some(alt => alt.length === 0)) return 'free';
  return dnf.map(alt => alt.join(' & ')).join(' | ');
}

// ---- tiers: a requirement is {tier: dnf}; a higher tier EXTENDS the lower ones
function reqAlternatives(req, tier) {
  if (req == null) return DNF_TRUE();
  const idx = TIERS.indexOf(tier == null ? TIERS[TIERS.length - 1] : tier);
  let alts = [];
  for (const t of TIERS.slice(0, idx + 1)) alts = alts.concat(req[t] || []);
  return dnfNormalize(alts);
}
const reqIsFree = (req, tier = TIERS[0]) => reqAlternatives(req, tier).some(a => a.length === 0);
const reqIsNever = (req, tier) => reqAlternatives(req, tier).length === 0;
function reqToLines(req) {
  if (req == null) return ['free'];
  const lines = [];
  let total = 0;
  for (const t of TIERS) {
    for (const alt of (req[t] || [])) { total++; lines.push(t + ': ' + (alt.length ? alt.join(' & ') : 'free')); }
  }
  if (!total) lines.push('never');
  return lines;
}

// ---- geometry: which region of a room contains a point (smallest polygon wins, else main)
function pointInPoly(pt, poly) {
  if (!poly || poly.length < 3) return false;
  const x = pt[0], y = pt[1];
  let inside = false;
  const n = poly.length;
  let j = n - 1;
  for (let i = 0; i < n; i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    if ((yi > y) !== (yj > y)) {
      const xc = (xj - xi) * (y - yi) / (yj - yi) + xi;
      if (x < xc) inside = !inside;
    }
    j = i;
  }
  return inside;
}
function polyArea(poly) {
  if (!poly || poly.length < 3) return 0;
  let s = 0;
  const n = poly.length;
  for (let i = 0; i < n; i++) {
    const a = poly[i], b = poly[(i + 1) % n];
    s += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(s) / 2;
}
function regionOfPoint(roomLogic, pt) {
  let best = 'main', bestArea = null;
  const regs = (roomLogic && roomLogic.regions) || {};
  for (const rid of Object.keys(regs)) {
    const poly = regs[rid].poly;
    if (rid === 'main' || !poly) continue;
    if (pointInPoly(pt, poly)) {
      const a = polyArea(poly);
      if (bestArea === null || a < bestArea) { best = rid; bestArea = a; }
    }
  }
  return best;
}

LE.DEFAULT_ATOMS = DEFAULT_ATOMS;
LE.Logic = {
  configure, canonicalAtom, isValidAtom, groupOf, dnfNormalize, dnfAnd, dnfOr, parseExpr, dnfToText,
  reqAlternatives, reqIsFree, reqIsNever, reqToLines, pointInPoly, polyArea, regionOfPoint,
  tiers: () => TIERS.slice(), catalog: () => catalog,
};
})(window.LogicEditor || (window.LogicEditor = {}));
