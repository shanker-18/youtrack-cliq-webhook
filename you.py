def save_paste_changes(n_save, cells_preview, comment, context_data):
    """
    Plain (non-callback) save helper.
    Returns (modal_open, refresh_token, toast).
    """
    if not n_save or not cells_preview or not context_data:
        return no_update, no_update, no_update
    user_comment = (comment or "").strip()
    return _execute_save_paste_changes(cells_preview, user_comment, context_data)


@callback(
    Output("modal-paste-preview", "is_open", allow_duplicate=True),
    Output("modal-paste-nocomment-confirm", "is_open", allow_duplicate=True),
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("btn-paste-save", "n_clicks"),
    State("paste-preview-cells-store", "data"),
    State("paste-comment-input", "value"),
    State("active-planning-context-store", "data"),
    Input("btn-paste-nocomment-save", "n_clicks"),
    prevent_initial_call=True,
)
def save_paste_changes_callback(
    n_save,
    cells_preview,
    comment,
    context_data,
    n_save_nocomment=None,
):
    """
    Dash callback wrapper: if Save is clicked with an empty rationale,
    opens the confirmation pop-up first; otherwise saves.
    """
    trig_id = callback_context.triggered_id
    if trig_id == "btn-paste-nocomment-save":
        if not n_save_nocomment:
            return no_update, no_update, no_update, no_update
    elif not n_save:
        return no_update, no_update, no_update, no_update

    if not cells_preview or not context_data:
        return no_update, False, no_update, no_update

    user_comment = (comment or "").strip()
    if trig_id == "btn-paste-save" and not user_comment:
        return no_update, True, no_update, no_update

    modal_open, refresh_token, toast = _execute_save_paste_changes(
        cells_preview, user_comment, context_data
    )
    return modal_open, False, refresh_token, toast
