/* requirements.js - the requirement editor widget: one block per tier with alternative rows of atom
 * chips, an atom picker and a free-text expression field parsed by LE.Logic. Used by the inspector
 * and the gates panel through reqEditor({get, set, nullable, nullLabel}). */
(function (LE) {
'use strict';
const { Logic, W, h, reqUiText } = LE;

function atomLabel(atom) { const a = W.atoms.find(x => x.id === atom); return a ? a.label : atom; }
function atomSelect(onPick) {
  const sel = h('select', { class: 'add-atom', title: 'Add an atom (AND)' }, h('option', { value: '' }, '+ atom'));
  const groups = {};
  for (const a of W.atoms) (groups[a.group] = groups[a.group] || []).push(a);
  for (const g of Object.keys(groups)) {
    const og = h('optgroup', { label: g });
    for (const a of groups[g]) og.append(h('option', { value: a.id }, a.id + ' - ' + a.label));
    sel.append(og);
  }
  sel.addEventListener('change', () => { if (sel.value) { onPick(sel.value); sel.value = ''; } });
  return sel;
}

// opts: get() -> requirement or null, set(req), nullable (offers "no requirement" = null), nullLabel.
function reqEditor(opts) {
  const root = h('div', { class: 'req' });
  const tiers = Logic.tiers();
  function current() { return opts.get(); }
  function setReq(req) { opts.set(req); build(); }
  // The first tier is always present in the document; a higher tier without alternatives is dropped.
  function setTier(tier, dnf) {
    const req = Object.assign({}, current() || {});
    if (dnf === null || (tier !== tiers[0] && dnf.length === 0)) delete req[tier]; else req[tier] = dnf;
    if (req[tiers[0]] === undefined) req[tiers[0]] = [];
    setReq(req);
  }
  function build() {
    root.replaceChildren();
    const req = current();
    if (opts.nullable) {
      const cb = h('input', { type: 'checkbox', checked: req == null,
        onchange: () => setReq(cb.checked ? null : { [tiers[0]]: [[]] }) });
      root.append(h('label', { class: 'req-null', title: 'null in the document' }, cb,
        opts.nullLabel || 'No requirement (free)'));
      if (req == null) return;
    }
    const r = req || {};
    for (const tier of tiers) root.append(tierBlock(tiers, tier, r[tier] === undefined ? null : r[tier], setTier));
    const sum = h('div', { class: 'summary' });
    for (const tier of tiers) {
      const inherits = tier !== tiers[0] ? '  (+ ' + tiers.slice(0, tiers.indexOf(tier)).join(', ') + ')' : '';
      sum.append(h('div', null, tier + ': ' + reqUiText(r, tier) + inherits));
    }
    sum.append(h('div', { class: 'hint' }, 'expert extends normal: in expert the alternatives of normal also count.'));
    root.append(sum);
  }
  build();
  return root;
}
// One tier: header buttons, one row per alternative, the expression field. dnf null = tier absent.
function tierBlock(tiers, tier, dnf, setTier) {
  const alts = dnf || [];
  const blk = h('div', { class: 'tier' });
  blk.append(h('div', { class: 'tier-head' },
    h('span', { class: 'tname' }, tier),
    h('span', { class: 'thint' }, tier === tiers[0] ? '' : '(extends ' + tiers[0] + ')'),
    h('span', { class: 'spacer' }),
    h('button', { title: 'Free: one empty alternative [[]]', onclick: () => setTier(tier, [[]]) }, 'Free'),
    h('button', { title: 'Impossible: no alternatives []', onclick: () => setTier(tier, []) }, 'Impossible'),
    h('button', { title: 'Add an alternative (OR)', onclick: () => setTier(tier, alts.concat([[]])) },
      '+ alternative')));
  if (!alts.length) {
    const none = tier === tiers[0]
      ? 'no alternatives: impossible in ' + tier
      : 'no alternatives of its own (only those of ' + tiers[0] + ')';
    blk.append(h('div', { class: 'none' }, none));
  }
  alts.forEach((alt, ai) => blk.append(altRow(tier, alts, ai, setTier)));
  blk.append(...exprField(tier, dnf, setTier));
  return blk;
}
// One alternative: chips joined by "&", an atom picker and a remove button.
function altRow(tier, alts, ai, setTier) {
  const alt = alts[ai];
  const copy = () => alts.map(a => a.slice());
  const row = h('div', { class: 'alt' }, h('span', { class: 'or' }, ai ? 'or' : ''));
  if (!alt.length) row.append(h('span', { class: 'chip free', title: 'Empty alternative = free' }, 'free'));
  alt.forEach((atom, xi) => {
    const remove = () => { const na = copy(); na[ai].splice(xi, 1); setTier(tier, na); };
    row.append(h('span', { class: 'chip g-' + Logic.groupOf(atom), title: atomLabel(atom) }, atom,
      h('span', { class: 'x', title: 'Remove', onclick: remove }, '×')));
    if (xi < alt.length - 1) row.append(h('span', { class: 'dim' }, '&'));
  });
  const addAtom = (atom) => { const na = copy(); if (!na[ai].includes(atom)) na[ai].push(atom); setTier(tier, na); };
  const removeAlt = () => { const na = copy(); na.splice(ai, 1); setTier(tier, na); };
  row.append(atomSelect(addAtom));
  row.append(h('span', { class: 'rm', title: 'Remove this alternative', onclick: removeAlt }, '×'));
  return row;
}
// Free-text expression for the tier; Enter (or the button) parses and replaces the tier.
function exprField(tier, dnf, setTier) {
  const inp = h('input', { type: 'text', value: dnf === null ? '' : Logic.dnfToText(dnf),
    placeholder: 'expression: HX & (LX | FX) · free · never',
    title: 'Enter applies. Grammar of logic_format.parse_expr' });
  const err = h('div', { class: 'expr-err' });
  inp.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const txt = inp.value.trim();
    if (!txt) { err.textContent = 'Empty: type free or never (impossible).'; return; }
    try { const parsed = Logic.parseExpr(txt); err.textContent = ''; setTier(tier, parsed); }
    catch (ex) { err.textContent = ex.message; }
  });
  const apply = () => inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
  const applyBtn = h('button', { class: 'small', title: 'Apply the expression (Enter)', onclick: apply }, '↵');
  return [h('div', { class: 'expr' }, inp, applyBtn), err];
}

Object.assign(LE, { atomLabel, atomSelect, reqEditor });
})(window.LogicEditor || (window.LogicEditor = {}));
