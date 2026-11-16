    function navigateTab(isShift) {
        if (!selectedCell || !selectedCell.td) return;
        var currentTd = selectedCell.td;

        // Build continuous flat list of all navigable cells across all rows & tables
        var allRows = getAllEditableRows();
        var allCells = [];
        allRows.forEach(function (tr) {
            var rowCells = getNavigableCellsInRow(tr);
            rowCells.forEach(function (td) {
                allCells.push(td);
            });
        });
