    document.addEventListener(EVT_UNDO, function (e) {
        window.__IBP_LAST_EVENTS__.undo = e.detail;
    });

    // AC1: Undo Button Click
    document.addEventListener("click", function (e) {
        var btn = e.target.closest("#btn-undo-action");
        if (!btn) return;
        var undoEntry = popUndo();
        if (undoEntry) {
            if (undoEntry.type === "cell_value") {
                dispatch(EVT_SAVE, {
                    row_id:   undoEntry.row_id,
                    month:    undoEntry.month,
                    year_idx: undoEntry.year_idx,
                    new_val:  undoEntry.old_val,
                    ts:       Date.now(),
                });
            } else {
                dispatch(EVT_UNDO, undoEntry);
            }
        }
    }, false);
