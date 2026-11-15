    /* ── Navigation Helpers (AC2: Full Row Arrow Navigation) ───────────────── */
    function getNavigableCellsInRow(tr) {
        if (!tr || tr.classList.contains("row-deleted")) return [];
        var cells = [];
        // 1. Item cell
        var itemTd = tr.querySelector("td.cell-subbrand");
        if (itemTd) cells.push(itemTd);
        // 2. Description cell
        var descTd = tr.querySelector("td.cell-desc");
        if (descTd) cells.push(descTd);
        // 3. Month cells (JAN - DEC)
        var monthTds = tr.querySelectorAll("td.cell-num");
        monthTds.forEach(function (td) {
            cells.push(td);
        });
        return cells;
    }

    function getAllEditableRows() {
        var rows = [];
        var tables = document.querySelectorAll(".planning-table");
        tables.forEach(function (tbl) {
            var trs = tbl.querySelectorAll("tbody tr:not(.row-deleted)");
            trs.forEach(function (tr) {
                rows.push(tr);
            });
        });
        return rows;
    }

    function navigateArrow(direction) {
        if (!selectedCell || !selectedCell.td || editingCell) return;

        var currentTd = selectedCell.td;
        var currentTr = currentTd.closest("tr");
        if (!currentTr) return;

        var cellsInRow = getNavigableCellsInRow(currentTr);
        var colIdx = cellsInRow.indexOf(currentTd);

        // Move Left / Right
        if (direction === "ArrowRight") {
            if (colIdx !== -1 && colIdx < cellsInRow.length - 1) {
                var nextCell = cellsInRow[colIdx + 1];
                selectCell(nextCell);
                if (nextCell.scrollIntoViewIfNeeded) nextCell.scrollIntoViewIfNeeded(false);
            }
            return;
        }

        if (direction === "ArrowLeft") {
            if (colIdx > 0) {
                var prevCell = cellsInRow[colIdx - 1];
                selectCell(prevCell);
                if (prevCell.scrollIntoViewIfNeeded) prevCell.scrollIntoViewIfNeeded(false);
            }
            return;
        }

        // Move Up / Down
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
            var targetCells = getNavigableCellsInRow(targetTr);
            if (colIdx >= 0 && colIdx < targetCells.length) {
                var targetCell = targetCells[colIdx];
                selectCell(targetCell);
                if (targetCell.scrollIntoViewIfNeeded) targetCell.scrollIntoViewIfNeeded(false);
            }
        }
    }
