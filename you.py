        // Ctrl+Z / Cmd+Z — Undo (AC1)
        if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z") && !e.shiftKey) {
            if (selectedCell || !editingCell) {
                e.preventDefault();
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
            }
            return;
        }
