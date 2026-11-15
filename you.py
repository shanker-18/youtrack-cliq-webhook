        if (targetTr) {
            var targetCells = getNavigableCellsInRow(targetTr);
            if (colIdx >= 0 && colIdx < targetCells.length) {
                var targetCell = targetCells[colIdx];
                selectCell(targetCell);
                if (targetCell.scrollIntoViewIfNeeded) targetCell.scrollIntoViewIfNeeded(false);
            }
        }
    }

    /* ── Tab & Shift+Tab Navigation (AC3, AC4, AC5, AC9) ─────────────────── */
    function navigateTab(isShift) {
        if (!selectedCell || !selectedCell.td) return;
        var currentTd = selectedCell.td;

        // Build continuous flat list of all navigable cells across all rows & tables
        var allRows = getAllEditableRows();
        var allCells = [];
        allRows.forEach(function (tr) {
            var rowCells = getNavigableCellsInRow(tr);
            rowCells.forEach(function (td) {
                // Include text cells (item/desc) and editable month cells
                if (isCellEditable(td) || td.classList.contains("cell-subbrand") || td.classList.contains("cell-desc")) {
                    allCells.push(td);
                }
            });
        });

        if (allCells.length === 0) return;

        var currentIndex = allCells.indexOf(currentTd);
        var targetIndex = -1;

        if (!isShift) {
            // Forward Tab: Next cell -> End of row wraps to next row (AC3, AC5, AC9)
            if (currentIndex === -1) {
                targetIndex = 0;
            } else if (currentIndex < allCells.length - 1) {
                targetIndex = currentIndex + 1;
            } else {
                targetIndex = 0; // Wrap around to top
            }
        } else {
            // Reverse Shift + Tab: Previous cell -> Start of row wraps to previous row (AC4)
            if (currentIndex === -1) {
                targetIndex = allCells.length - 1;
            } else if (currentIndex > 0) {
                targetIndex = currentIndex - 1;
            } else {
                targetIndex = allCells.length - 1; // Wrap around to bottom
            }
        }

        if (targetIndex >= 0 && targetIndex < allCells.length) {
            var targetCell = allCells[targetIndex];
            selectCell(targetCell);
            if (targetCell.scrollIntoViewIfNeeded) targetCell.scrollIntoViewIfNeeded(false);
        }
    }

    /* ── Selection ───────────────────────────────────────────────────────── */
