        // Arrow Key Navigation (AC2)
        if (selectedCell && !editingCell) {
            if (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                navigateArrow(e.key);
                return;
            }
        }

        // Ctrl+C / Cmd+C on selected cell
        if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C")) {
