/* keyboard.js - global shortcuts (tool modes, undo / redo, zoom, search, help, space-to-pan, Escape
 * cascade) and the unload guard that warns about unsaved changes. */
(function (LE) {
'use strict';
const { S, CV, $ } = LE;
const { undo, redo, setMode, select, fitView, zoomAt, deleteSelection, closePolygon, stopPlacing } = LE;

const TEXT_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);
const isTyping = (t) => !!t && (TEXT_TAGS.has(t.tagName) || t.isContentEditable);

// Escape backs out one level at a time: field, panels, placement, edge source, tool, vertex, selection.
function onEscape(t, typing) {
  if (!$('#modal').hidden) return;
  if (typing) { t.blur(); LE.hideSearch(); return; }
  if (!$('#help-panel').hidden) { $('#help-panel').hidden = true; return; }
  if (!$('#gates-panel').hidden) { $('#gates-panel').hidden = true; return; }
  if (S.placing) { stopPlacing(); return; }
  if (S.mode === 'edge') { if (S.edgeFrom) { S.edgeFrom = null; CV.dirty = true; } else setMode('select'); return; }
  if (S.mode === 'poly') { setMode('select'); return; }
  if (S.activeVertex != null) { S.activeVertex = null; CV.dirty = true; return; }
  select({ type: 'room' });
}
function onKeyDown(e) {
  const t = e.target;
  const typing = isTyping(t);
  if (e.key === 'Escape') { onEscape(t, typing); return; }
  if (typing) return;
  if (!$('#modal').hidden) return;
  const k = e.key;
  const ctrl = e.ctrlKey || e.metaKey;
  if (ctrl && k.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return; }
  if (ctrl && k.toLowerCase() === 'y') { e.preventDefault(); redo(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  switch (k) {
    case 'v': case 'V': setMode('select'); break;
    case 'p': case 'P': setMode('poly'); break;
    case 'a': case 'A': setMode('edge'); break;
    case 'Delete': deleteSelection(); break;
    case 'Enter': if (S.mode === 'poly') closePolygon(); break;
    case '0': fitView(); break;
    case '+': case '=': zoomAt(CV.w / 2, CV.h / 2, 1.25); break;
    case '-': case '_': zoomAt(CV.w / 2, CV.h / 2, 1 / 1.25); break;
    case 'f': case 'F': e.preventDefault(); $('#search').focus(); $('#search').select(); break;
    case '?': LE.togglePanel('help-panel'); break;
    case ' ': if (!S.space) { S.space = true; CV.el.classList.add('grab'); } e.preventDefault(); break;
    default: return;
  }
}
function onKeyUp(e) { if (e.key === ' ') { S.space = false; CV.el.classList.remove('grab'); } }
function onBeforeUnload(e) {
  if (S.docVersion !== S.savedVersion || S.saving) { e.preventDefault(); e.returnValue = ''; }
}
function bindKeys() {
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('beforeunload', onBeforeUnload);
}

Object.assign(LE, { bindKeys });
})(window.LogicEditor || (window.LogicEditor = {}));
