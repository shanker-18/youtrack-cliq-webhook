

# ── Ctrl+Z Global Shortcut Listener ──────────────────────────────────────────
dash.clientside_callback(
    """
    function(id) {
        if (!window.__IBP_UNDO_KEY_ATTACHED__) {
            window.__IBP_UNDO_KEY_ATTACHED__ = true;
            document.addEventListener("keydown", function(e) {
                if ((e.ctrlKey || e.metaKey) && (e.key === 'z' || e.key === 'Z') && !e.shiftKey) {
                    var btn = document.getElementById("btn-planning-undo");
                    if (btn && !btn.disabled) {
                        e.preventDefault();
                        btn.click();
                    }
                }
            });
        }
        return window.dash_clientside.no_update;
    }
    """,
    dash.Output("btn-planning-undo", "id"),
    dash.Input("btn-planning-undo", "id"),
)
