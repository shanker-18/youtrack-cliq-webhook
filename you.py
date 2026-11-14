    function selectCell(td) {
        if (editingCell) return; // Don't change selection while editing
        clearSelection();
        if (!td) return;

        // Ensure cell has tabindex so browser focus() works on all table cells
        if (!td.hasAttribute("tabindex") || td.getAttribute("tabindex") === "-1") {
            td.setAttribute("tabindex", "0");
        }

        td.classList.add("cell-selected");
        if (document.activeElement !== td && (!td.contains(document.activeElement))) {
            try { 
                td.focus({ preventScroll: true }); 
            } catch (err) {
                try { td.focus(); } catch (e) {}
            }
        }

        var info = getCellInfo(td);
        selectedCell = {
            td: td,
            rowId: info.row_id,
            month: info.month,
            yearIdx: info.year_idx,
            colType: info.col_type || "month",
        };
        dispatch(EVT_SELECTED, {
            row_id:   info.row_id,
            month:    info.month,
            year_idx: info.year_idx,
            col_type: info.col_type || "month",
            ts:       Date.now(),
        });
    }
