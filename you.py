/* ── Undo Stack (AC1, AC8, AC9, AC10) ────────────────────────────────── */
var MAX_UNDO = 10;
window.__IBP_UNDO_STACK__ = [];
var EVT_UNDO = "ibp:undo";

function pushUndo(entry) {
    window.__IBP_UNDO_STACK__.push(entry);
    if (window.__IBP_UNDO_STACK__.length > MAX_UNDO) {
        window.__IBP_UNDO_STACK__.shift();
    }
    _syncUndoButton();
}

function popUndo() {
    if (window.__IBP_UNDO_STACK__.length === 0) return null;
    var entry = window.__IBP_UNDO_STACK__.pop();
    _syncUndoButton();
    return entry;
}

function _syncUndoButton() {
    var btn = document.getElementById("btn-undo-action");
    if (btn) {
        btn.disabled = (window.__IBP_UNDO_STACK__.length === 0);
    }
}
