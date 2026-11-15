    // Keydown
    document.addEventListener("keydown", function (e) {
        // Never intercept keyboard events when user is inside any modal dialog
        if (isInsideModal(e.target) || isInsideModal(document.activeElement)) {
            return;
        }

        // Ensure action delete buttons never receive keyboard focus
        var activeEl = document.activeElement;
        var targetEl = e.target;

        // If focus is in Item or Description input: handle Tab, Shift+Tab, and Up/Down cleanly
        var isInlineText = activeEl && activeEl.classList && activeEl.classList.contains("cell-inline-input");
        if (isInlineText) {
            if (e.key === "Tab") {
                e.preventDefault();
                navigateTab(e.shiftKey);
                return;
            }
            if (e.key === "ArrowDown") {
                e.preventDefault();
                navigateArrow("ArrowDown");
                return;
            }
            if (e.key === "ArrowUp") {
                e.preventDefault();
                navigateArrow("ArrowUp");
                return;
            }
            // Let normal typing and left/right cursor moving happen inside text input
            return;
        }

        // Never intercept keyboard events when focus is in any general form element outside table
        var isFormEl = function (el) {
            if (!el || !el.tagName) return false;
            var tag = el.tagName.toUpperCase();
            return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
        };

        if (isFormEl(activeEl) || isFormEl(targetEl)) {
            if (!editingCell || (editingCell.input !== activeEl && editingCell.input !== targetEl)) {
                return;
            }
        }
