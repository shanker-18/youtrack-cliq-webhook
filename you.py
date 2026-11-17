app.clientside_callback(
    """
    function(n) {
        var evts = window.__IBP_LAST_EVENTS__;
        if (!evts || !evts.undo) return window.dash_clientside.no_update;
        var d = evts.undo;
        evts.undo = null;
        return d;
    }
    """,
    dash.Output("undo-action-store", "data"),
    dash.Input("cell-interaction-interval", "n_intervals"),
)
