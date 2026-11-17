# ── 2. Save Cell Edit with Delta Auditing ─────────────────────────────────────
@callback(
    Output("modal-audit-history", "is_open", allow_duplicate=True),
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("btn-modal-save-action", "n_clicks"),
    State("audit-cell-value-input", "value"),
    State("audit-comment-input", "value"),
    State("audit-target-row-id", "data"),
    State("audit-target-period", "data"),
    State("audit-target-old-val", "data"),
    State("active-planning-context-store", "data"),
    prevent_initial_call=True,
)
def handle_save_cell_edit(n_save, new_val_str, comment, row_id, period_iso, old_val_str, context_data):
    """Persist numeric value update and rationale into PostgreSQL with delta auditing."""
    if not n_save or not row_id or not period_iso or not context_data:
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

    domain = context_data.get("domain", "CONSUMPTION")
    snapshot_id = context_data.get("snapshot_id")
    if not snapshot_id:
        return False, no_update, {"message": "Cannot save audit comment for uninitialized snapshot.", "header": "Error"}
    dept_id = context_data.get("dept_id", 2)
    active_user = get_current_user() or {}
    user_id = active_user.get("user_id") or context_data.get("user_id", 1)
    period_month = datetime.strptime(period_iso, "%Y-%m-%d").date()

    modal_open = False
    refresh_token = no_update
    toast = no_update
    try:
        res = save_cell_edit(
            domain=domain,
            snapshot_id=snapshot_id,
            row_id=row_id,
            period_month=period_month,
            old_value=old_val,
            new_value=new_val,
            comment=comment or "",
            user_id=user_id,
            dept_id=dept_id,
        )
        if res.get("status") == "NO_CHANGE":
            toast = {"message": "No change detected in value or comment. Audit log unchanged.", "header": "Audit Log Unchanged"}
        else:
            delta_text = res.get("delta", f"{new_val:.2f}")
            refresh_token = {"trigger": "cell_edit", "timestamp": time.time(), "row_id": row_id}
            toast = {"message": f"Saved cell edit to PostgreSQL: {delta_text}", "header": "Cell Saved"}
    except (psycopg2.Error, ValueError, KeyError) as e:
        logger.error("Failed to save cell edit", extra={"context": {"error": str(e)}})
        modal_open = no_update
        toast = {"message": f"Failed to save cell: {e}", "header": "Error"}

    return modal_open, refresh_token, toast
