    function onEditKeydown(e) {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            commitEdit();
            // Enter moves down to next row (Excel standard)
            navigateArrow("ArrowDown");
        } else if (e.key === "Tab") {
            e.preventDefault();
            e.stopPropagation();
            var isShift = e.shiftKey;
            commitEdit();
            // Tab advances to next cell
            navigateTab(isShift);
        } else if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            cancelEdit();
        }
    }
