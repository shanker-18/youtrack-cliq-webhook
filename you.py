def handle_save_cell_edit(
    n_save,
    new_val_str,
    comment,
    row_id,
    period_iso,
    old_val_str,
    context_data,
    n_save_nocomment=None,
):
    """
    Plain (non-callback) save helper. Validates input and persists the cell edit.
    Returns (modal_open, refresh_token, toast).
    """
    if not row_id or not period_iso or not context_data:
        return no_update, no_update, no_update

    try:
        new_val = round(float(str(new_val_str).replace(",", "").strip()), 2)
    except (ValueError, TypeError):
        toast = {"message": "Invalid numeric value entered.", "header": "Validation Error"}
        return no_update, no_update, toast

    try:
        old_val = round(float(str(old_val_str).replace(",", "").strip()), 2)
    except (ValueError, TypeError):
        old_val = 0.0

    clean_comment = str(comment or "").strip()
    return _execute_save_cell_edit(
        new_val, old_val, clean_comment, row_id, period_iso, context_data
    )


@callback(
    Output("modal-audit-history", "is_open", allow_duplicate=True),
    Output("modal-audit-nocomment-confirm", "is_open", allow_duplicate=True),
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("btn-modal-save-action", "n_clicks"),
    State("audit-cell-value-input", "value"),
    State("audit-comment-input", "value"),
    State("audit-target-row-id", "data"),
    State("audit-target-period", "data"),
    State("audit-target-old-val", "data"),
    State("active-planning-context-store", "data"),
    Input("btn-audit-nocomment-save", "n_clicks"),
    prevent_initial_call=True,
)
def handle_save_cell_edit_callback(
    n_save,
    new_val_str,
    comment,
    row_id,
    period_iso,
    old_val_str,
    context_data,
    n_save_nocomment=None,
):
    """
    Dash callback wrapper: resolves the trigger, shows the no-comment confirmation
    if needed, then delegates to handle_save_cell_edit.
    """
    trig_id = callback_context.triggered_id
    if trig_id == "btn-audit-nocomment-save":
        if not n_save_nocomment:
            return no_update, no_update, no_update, no_update
    elif not n_save:
        return no_update, no_update, no_update, no_update

    if not row_id or not period_iso or not context_data:
        return no_update, False, no_update, no_update

    clean_comment = str(comment or "").strip()
    if trig_id == "btn-modal-save-action" and not clean_comment:
        return no_update, True, no_update, no_update

    modal_open, refresh_token, toast = handle_save_cell_edit(
        n_save, new_val_str, comment, row_id, period_iso, old_val_str, context_data
    )
    return modal_open, False, refresh_token, toast
