function pushUndo(entry) {
    window.__IBP_UNDO_STACK__.push(entry);
    if (window.__IBP_UNDO_STACK__.length > MAX_UNDO) {
        window.__IBP_UNDO_STACK__.shift();
    }
    _syncUndoButton();
}
