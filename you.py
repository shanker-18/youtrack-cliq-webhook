
    // AC3 + AC4: Capture text field before-state for undo
    document.addEventListener("focusin", function (e) {
        if (isInsideModal(e.target)) return;
        var inp = e.target;
        if (!inp || !inp.tagName || inp.tagName.toUpperCase() !== "INPUT") return;
        var td = inp.closest ? inp.closest("td.cell-subbrand, td.cell-desc") : null;
        if (!td) return;
        var info = getCellInfo(td);
        if (!info || !info.row_id) return;
        inp.__ibp_undo_before = {
            type: "text_edit",
            row_id: info.row_id,
            col_type: td.classList.contains("cell-subbrand") ? "item" : "desc",
            old_val: inp.value || "",
            ts: Date.now(),
        };
    }, true);

    document.addEventListener("change", function (e) {
        if (isInsideModal(e.target)) return;
        var inp = e.target;
        if (!inp || !inp.__ibp_undo_before) return;
        var before = inp.__ibp_undo_before;
        var newVal = (inp.value || "").trim();
        var oldVal = (before.old_val || "").trim();
        if (newVal !== oldVal) {
            before.new_val = newVal;
            pushUndo(before);
        }
        inp.__ibp_undo_before = null;
    }, true);
