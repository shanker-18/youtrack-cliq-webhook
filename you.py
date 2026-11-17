app.clientside_callback(
    """
    function(gridData) {
        if (!gridData || !gridData.trigger || !gridData.row_id) return window.dash_clientside.no_update;
        var stack = window.__IBP_UNDO_STACK__;
        if (!stack) return window.dash_clientside.no_update;
        if (gridData.trigger === "add_row") {
            stack.push({type: "row_add", row_id: gridData.row_id, ts: Date.now()});
            if (stack.length > 10) stack.shift();
        } else if (gridData.trigger === "delete_row") {
            stack.push({type: "row_delete", row_id: gridData.row_id, ts: Date.now()});
            if (stack.length > 10) stack.shift();
        }
        var btn = document.getElementById("btn-undo-action");
        if (btn) btn.disabled = (stack.length === 0);
        return "Undo last action (Ctrl+Z)";
    }
    """,
    dash.Output("btn-undo-action", "title"),
    dash.Input("active-grid-rows-store", "data"),
)
