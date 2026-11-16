        // Tab & Shift+Tab Navigation (AC3, AC4, AC5, AC9)
        if (e.key === "Tab" && selectedCell && !editingCell) {
            e.preventDefault();
            navigateTab(e.shiftKey);
            return;
        }

        // Enter on selected cell → Open edit mode (AC6)
        if (e.key === "Enter" && selectedCell && !editingCell) {
            if (isCellEditable(selectedCell.td)) {
                e.preventDefault();
                startEdit(selectedCell.td, undefined);
                return;
            } else if (selectedCell.td.classList.contains("cell-subbrand") || selectedCell.td.classList.contains("cell-desc")) {
                var textInp = selectedCell.td.querySelector("input");
                if (textInp) {
                    e.preventDefault();
                    textInp.focus();
                    textInp.select();
                    return;
                }
            }
        }

        // Ctrl+C / Cmd+C on selected cell
        if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C")) {
