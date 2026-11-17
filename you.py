    // Focus into text cell input
    document.addEventListener("focusin", function (e) {
        if (isInsideModal(e.target)) return;
        var textTd = e.target.closest ? e.target.closest("td.cell-subbrand, td.cell-desc") : null;
        if (textTd) {
            if (editingCell) commitEdit();
            selectCell(textTd);
        }
    }, true);

    // AC3 + AC4: Capture text field before-state for undo
