        // Arrow Key Navigation (AC2)
        if (selectedCell && !editingCell) {
            if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                navigateArrow(e.key);
                return;
            }
        }

        // Tab & Shift+Tab Navigation (AC3, AC4, AC5, AC9)
        if (e.key === "Tab" && selectedCell && !editingCell) {
            e.preventDefault();
            navigateTab(e.shiftKey);
            return;
        }
