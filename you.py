        var formattedVal = newNum.toFixed(2);
        cleanupEdit(formattedVal);

        // AC2: Push before-state to undo stack
        pushUndo({
            type: "cell_value",
            row_id: ctx.rowId,
            month: ctx.month,
            year_idx: ctx.yearIdx,
            old_val: oldNum,
            new_val: newNum,
            ts: Date.now(),
        });

        dispatch(EVT_SAVE, {
