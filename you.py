# ── 4. Close Audit Modal ─────────────────────────────────────────────────────
@callback(
    Output("modal-audit-history", "is_open", allow_duplicate=True),
    Output("modal-audit-nocomment-confirm", "is_open", allow_duplicate=True),
    Input("btn-close-audit-modal", "n_clicks"),
    prevent_initial_call=True,
)
def handle_close_audit_modal(n_close):
    """Close the cell audit history modal dialog."""
    return False, False


# ── 5. Cell Comment Pop-up (Uses existing save_cell_edit logic) ──────────────
@callback(
    Output("modal-cell-comment", "is_open"),
    Output("comment-model-label", "children"),
    Output("comment-row-label", "children"),
    Output("comment-period-label", "children"),
    Output("comment-curval-label", "children"),
    Output("comment-status-line", "children"),
    Output("comment-modal-textarea", "value"),
    Output("comment-modal-textarea", "disabled"),
    Output("comment-history-table-container", "children"),
    Output("btn-save-comment-modal", "style"),
    Output("comment-target-row-id", "data"),
    Output("comment-target-period", "data"),
    Output("comment-target-cur-val", "data"),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("btn-open-comment-modal", "n_clicks"),
    State("selected-cell-store", "data"),
    State("active-planning-context-store", "data"),
    prevent_initial_call=True,
)
def handle_open_comment_modal(n_clicks, selected_cell, context_data):
    """Open the Cell Comment modal for the currently selected grid cell."""
    if not n_clicks or not context_data:
        return (no_update,) * 14
    row_id = (selected_cell or {}).get("row_id")
    month_col = (selected_cell or {}).get("month")
    if not row_id or not month_col:
        toast = {"message": "Click any month cell in the grid first, then click Comment.", "header": "Select a Cell"}
        return (no_update,) * 13 + (toast,)
    year_index, month_col, cell_year, period_date = _extract_audit_cell_coordinates(selected_cell, context_data)
    domain = context_data.get("domain", "CONSUMPTION")
    row_details, events, cur_val = _load_audit_row_and_events(domain, row_id, period_date)
    is_row_deleted, row_label = _resolve_audit_row_label(row_details, row_id)
    is_snapshot, is_demand, is_bp, is_period_locked = _resolve_audit_context_flags(context_data)
    st = _determine_audit_modal_state(is_row_deleted, is_snapshot, is_demand, is_bp, is_period_locked, events)
    model_name = _resolve_audit_model_name(context_data, row_details)
    period_label = f"{month_col} {cell_year} ({'Year 1' if year_index == 1 else 'Year 2'})"
    return (
        True,
        model_name,
        row_label,
        period_label,
        cur_val,
        st["status_line"],
        "",
        st["cmt_disabled"],
        build_audit_history_table(events),
        st["save_btn_style"],
        row_id,
        period_date.isoformat(),
        cur_val,
        no_update,
    )


@callback(
    Output("modal-cell-comment", "is_open", allow_duplicate=True),
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("btn-save-comment-modal", "n_clicks"),
    State("comment-modal-textarea", "value"),
    State("comment-target-row-id", "data"),
    State("comment-target-period", "data"),
    State("comment-target-cur-val", "data"),
    State("active-planning-context-store", "data"),
    prevent_initial_call=True,
)
def handle_save_comment_modal(n_save, comment_text, row_id, period_iso, cur_val_str, context_data):
    """Save cell comment (or close as no-change if empty) via existing save_cell_edit()."""
    if not n_save or not row_id or not period_iso or not context_data:
        return no_update, no_update, no_update
    snapshot_id = context_data.get("snapshot_id")
    if not snapshot_id:
        return False, no_update, {"message": "Cannot save comment for uninitialized snapshot.", "header": "Error"}
    try:
        cur_val = round(float(str(cur_val_str).replace(",", "").strip()), 2)
    except (ValueError, TypeError):
        cur_val = 0.0
    domain = context_data.get("domain", "CONSUMPTION")
    dept_id = context_data.get("dept_id", 2)
    active_user = get_current_user() or {}
    user_id = active_user.get("user_id") or context_data.get("user_id", 1)
    period_month = datetime.strptime(period_iso, "%Y-%m-%d").date()
    try:
        res = save_cell_edit(
            domain=domain,
            snapshot_id=snapshot_id,
            row_id=row_id,
            period_month=period_month,
            old_value=cur_val,
            new_value=cur_val,
            comment=(comment_text or "").strip(),
            user_id=user_id,
            dept_id=dept_id,
        )
        if res.get("status") == "NO_CHANGE":
            return False, no_update, {"message": "No comment entered. Saved without changes.", "header": "Audit Log Unchanged"}
        refresh_token = {"trigger": "comment_added", "timestamp": time.time(), "row_id": row_id}
        return False, refresh_token, {"message": "Comment saved to PostgreSQL.", "header": "Comment Saved"}
    except (psycopg2.Error, ValueError, KeyError) as e:
        logger.error("Failed to save cell comment", extra={"context": {"error": str(e)}})
        return no_update, no_update, {"message": f"Failed to save comment: {e}", "header": "Error"}


@callback(
    Output("modal-cell-comment", "is_open", allow_duplicate=True),
    Input("btn-close-comment-modal", "n_clicks"),
    prevent_initial_call=True,
)
def handle_close_comment_modal(n_close):
    """Close the cell comment modal."""
    return False
