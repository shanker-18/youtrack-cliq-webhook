    /* ── Navigation Helpers (AC2: Arrow Key Navigation) ───────────────────── */
    function getAllEditableRows() {
        var rows = [];
        var tables = document.querySelectorAll(".planning-table");
        tables.forEach(function (tbl) {
            var trs = tbl.querySelectorAll("tbody tr:not(.row-deleted)");
            trs.forEach(function (tr) {
                if (tr.querySelector('td.cell-num[data-editable="true"]')) {
                    rows.push(tr);
                }
            });
        });
        return rows;
    }

    function navigateArrow(direction) {
        if (!selectedCell || !selectedCell.td || editingCell) return;

        var currentTd = selectedCell.td;
        var currentTr = currentTd.closest("tr");
        if (!currentTr) return;

        var editableCellsInRow = Array.from(currentTr.querySelectorAll('td.cell-num[data-editable="true"]'));
        var colIdx = editableCellsInRow.indexOf(currentTd);

        if (direction === "ArrowRight") {
            if (colIdx !== -1 && colIdx < editableCellsInRow.length - 1) {
                var nextCell = editableCellsInRow[colIdx + 1];
                selectCell(nextCell);
                if (nextCell.scrollIntoViewIfNeeded) nextCell.scrollIntoViewIfNeeded(false);
            }
            return;
        }

        if (direction === "ArrowLeft") {
            if (colIdx > 0) {
                var prevCell = editableCellsInRow[colIdx - 1];
                selectCell(prevCell);
                if (prevCell.scrollIntoViewIfNeeded) prevCell.scrollIntoViewIfNeeded(false);
            }
            return;
        }

        var allRows = getAllEditableRows();
        var rowIdx = allRows.indexOf(currentTr);
        if (rowIdx === -1) return;

        var targetTr = null;
        if (direction === "ArrowDown" && rowIdx < allRows.length - 1) {
            targetTr = allRows[rowIdx + 1];
        } else if (direction === "ArrowUp" && rowIdx > 0) {
            targetTr = allRows[rowIdx - 1];
        }

        if (targetTr) {
            // Try to match the exact same month in target row
            var targetCell = targetTr.querySelector('td.cell-num[data-month="' + selectedCell.month + '"][data-editable="true"]');
            if (!targetCell) {
                // Fallback to first editable cell in target row if that month is locked
                var targetRowEditables = Array.from(targetTr.querySelectorAll('td.cell-num[data-editable="true"]'));
                if (targetRowEditables.length > 0) {
                    targetCell = targetRowEditables[Math.min(colIdx >= 0 ? colIdx : 0, targetRowEditables.length - 1)];
                }
            }
            if (targetCell) {
                selectCell(targetCell);
                if (targetCell.scrollIntoViewIfNeeded) targetCell.scrollIntoViewIfNeeded(false);
            }
        }
    }

    /* ── Selection ───────────────────────────────────────────────────────── */
    function clearSelection() {
