        // AC5: Push before-state to undo stack for paste
        pushUndo({
            type: "paste",
            row_id:    selectedCell.rowId,
            month:     selectedCell.month || "JAN",
            year_idx:  selectedCell.yearIdx || 1,
            col_type:  selectedCell.colType || "month",
            ts:        now,
        });
