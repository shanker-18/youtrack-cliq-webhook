    // Focus into any cell (month cell or text cell)
    document.addEventListener("focusin", function (e) {
        if (isInsideModal(e.target)) return;
        var td = isMonthCell(e.target);
        if (td) {
            if (editingCell && (editingCell.td === td || editingCell.input === e.target)) return;
            if (editingCell) commitEdit();
            selectCell(td);
            return;
        }
        var textTd = e.target.closest ? e.target.closest("td.cell-subbrand, td.cell-desc") : null;
        if (textTd) {
            if (editingCell) commitEdit();
            selectCell(textTd);
        }
    }, true);
