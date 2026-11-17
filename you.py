@callback(
    Output("modal-audit-history", "is_open", allow_duplicate=True),
    Output("modal-audit-nocomment-confirm", "is_open", allow_duplicate=True),
    Input("btn-close-audit-modal", "n_clicks"),
    prevent_initial_call=True,
)
def handle_close_audit_modal(n_close):
    """Close the cell audit history modal dialog."""
    return False, False
