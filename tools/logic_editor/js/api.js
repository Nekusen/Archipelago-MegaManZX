/* api.js - talks to serve.py: loads the world and the document, autosaves 600 ms after the last change
 * (POST /api/logic answers with the validation report), validates on demand and shows the status pill. */
(function (LE) {
'use strict';
const { S, DOC, $ } = LE;

function setStatus(text, cls) {
  const el = $('#status');
  el.textContent = text; el.className = 'status ' + (cls || '');
}
const postDoc = (url) => fetch(url, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(DOC),
});

async function loadWorld() {
  const [wr, lr] = await Promise.all([fetch('/api/world'), fetch('/api/logic')]);
  if (!wr.ok) throw new Error('/api/world: HTTP ' + wr.status);
  if (!lr.ok) throw new Error('/api/logic: HTTP ' + lr.status);
  return { world: await wr.json(), doc: await lr.json() };
}

function scheduleSave() {
  clearTimeout(S.saveTimer);
  setStatus('Unsaved', 'dirty');
  S.saveTimer = setTimeout(doSave, 600);
}
async function doSave() {
  if (S.saving) { S.savePending = true; return; }   // a save is in flight: run again when it ends
  S.saving = true;
  const v = S.docVersion;
  setStatus('Saving...', 'saving');
  try {
    const r = await postDoc('/api/logic');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const rep = await r.json();
    if (rep.error) throw new Error(rep.error);
    S.report = rep;
    if (S.docVersion === v) { S.savedVersion = v; setStatus('Saved', 'ok'); }
    LE.renderReport(); LE.renderTabs();
  } catch (err) {
    setStatus('Error: ' + err.message, 'error');
  } finally {
    S.saving = false;
    if (S.savePending) { S.savePending = false; doSave(); }
  }
}
async function doValidate() {
  setStatus('Validating...', 'saving');
  try {
    const r = await postDoc('/api/validate');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    S.report = await r.json();
    LE.renderReport(); LE.renderTabs();
    const saved = S.docVersion === S.savedVersion;
    setStatus(saved ? 'Saved' : 'Unsaved', saved ? 'ok' : 'dirty');
    $('#report-body').hidden = false; $('#report-toggle').textContent = '▾';
  } catch (err) { setStatus('Error: ' + err.message, 'error'); }
}
// Report of the freshly loaded document, without saving it.
function requestInitialReport() {
  postDoc('/api/validate')
    .then(r => r.json()).then(rep => { if (!rep.error) { S.report = rep; LE.renderReport(); LE.renderTabs(); } })
    .catch(() => { /* the report will arrive with the first save */ });
}

Object.assign(LE, { setStatus, loadWorld, scheduleSave, doSave, doValidate, requestInitialReport });
})(window.LogicEditor || (window.LogicEditor = {}));
