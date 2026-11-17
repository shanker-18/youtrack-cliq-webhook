    return modal_open, False, refresh_token, toast


@callback(
    Output("modal-audit-nocomment-confirm", "is_open", allow_duplicate=True),
    Input("btn-audit-nocomment-add", "n_clicks"),
    prevent_initial_call=True,
)
def handle_nocomment_focus_comment(n_add):
    """Close no-comment confirmation pop-up so user can enter a comment."""
    if not n_add:
        return no_update
    return False
