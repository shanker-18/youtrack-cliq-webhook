def _undo_text_edit(undo_data, domain, model_id):
    """Handle undo for item/description text edits."""
    row_id = undo_data.get("row_id")
    col_type = undo_data.get("col_type", "item")
    old_val = undo_data.get("old_val", "")
    if not row_id:
        return no_update, no_update
    row = get_row_details(domain, row_id)
    if not row:
        return no_update, no_update
    if col_type == "item":
        item_to_save, desc_to_save, field_label = old_val, row.get("description") or "", "Item"
    else:
        item_to_save, desc_to_save, field_label = row.get("item") or "", old_val, "Description"
    update_line_item_text(domain=domain, row_id=row_id, item=item_to_save, description=desc_to_save)
    invalidate_planning_cache(model_id=model_id, domain=domain)
    refresh = {"trigger": "undo_text", "timestamp": time.time(), "row_id": row_id}
    toast = {"message": f"Undo: {field_label} reverted to \"{old_val}\"", "header": "Undo Applied"}
    return refresh, toast


def _undo_paste(paste_undo_cells, domain, snapshot_id, user_id, dept_id, model_id):
    """Handle undo for bulk paste operations."""
    if not paste_undo_cells:
        return no_update, {"message": "No paste data available to undo.", "header": "Undo Note"}
    reverted = 0
    for c in paste_undo_cells:
        try:
            old_val = round(float(str(c.get("old_val", "0")).replace(",", "")), 2)
            period_month = datetime.strptime(c["period_iso"], "%Y-%m-%d").date()
            cur_val = get_cell_current_value(domain=domain, row_id=c["row_id"], period_month=period_month)
            save_cell_edit(
                domain=domain, snapshot_id=snapshot_id,
                row_id=int(c["row_id"]) if str(c["row_id"]).isdigit() else c["row_id"],
                period_month=period_month, old_value=cur_val, new_value=old_val,
                comment="Undo: paste reverted", user_id=user_id, dept_id=dept_id,
            )
            reverted += 1
        except (psycopg2.Error, ValueError, KeyError) as e:
            logger.exception("Failed to undo paste cell", extra={"context": {"error": str(e)}})
    if reverted > 0:
        invalidate_planning_cache(model_id=model_id, domain=domain)
        return {"trigger": "undo_paste", "timestamp": time.time()}, {"message": f"Undo: {reverted} pasted cell(s) reverted.", "header": "Undo Applied"}
    return no_update, {"message": "Failed to undo paste.", "header": "Error"}


def _undo_row_add(undo_data, domain, snapshot_id, dept_id, user_id, model_id):
    """Handle undo for row addition."""
    row_id = undo_data.get("row_id")
    if not row_id:
        return no_update, no_update
    soft_delete_line_item(domain, snapshot_id, row_id, dept_id, user_id, "Undo: row addition reverted")
    invalidate_planning_cache(model_id=model_id, domain=domain)
    return {"trigger": "undo_row_add", "timestamp": time.time(), "row_id": row_id}, {"message": "Undo: added row removed.", "header": "Undo Applied"}


def _undo_row_delete(undo_data, domain, snapshot_id, dept_id, user_id, model_id):
    """Handle undo for row deletion."""
    row_id = undo_data.get("row_id")
    if not row_id:
        return no_update, no_update
    restore_line_item(domain, snapshot_id, row_id, dept_id, user_id)
    invalidate_planning_cache(model_id=model_id, domain=domain)
    return {"trigger": "undo_row_delete", "timestamp": time.time(), "row_id": row_id}, {"message": "Undo: deleted row restored.", "header": "Undo Applied"}


# ── 8. Undo Action Handler (AC3, AC4, AC5, AC6, AC7) ─────────────────────────
@callback(
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("undo-action-store", "data"),
    State("active-planning-context-store", "data"),
    State("paste-undo-cells-store", "data"),
    prevent_initial_call=True,
)
def handle_undo_action(undo_data, context_data, paste_undo_cells):
    """Handle undo actions dispatched from the client-side undo stack."""
    if not undo_data or not context_data or not context_data.get("is_editable"):
        return no_update, no_update

    undo_type = undo_data.get("type")
    domain = context_data.get("domain", "CONSUMPTION")
    snapshot_id = context_data.get("snapshot_id")
    if not snapshot_id:
        return no_update, no_update

    active_user = get_current_user() or {}
    user_id = active_user.get("user_id") or context_data.get("user_id", 1)
    dept_id = context_data.get("dept_id", 2)
    model_id = context_data.get("model_id")

    try:
        if undo_type == "text_edit":
            return _undo_text_edit(undo_data, domain, model_id)
        if undo_type == "paste":
            return _undo_paste(paste_undo_cells, domain, snapshot_id, user_id, dept_id, model_id)
        if undo_type == "row_add":
            return _undo_row_add(undo_data, domain, snapshot_id, dept_id, user_id, model_id)
        if undo_type == "row_delete":
            return _undo_row_delete(undo_data, domain, snapshot_id, dept_id, user_id, model_id)
    except (psycopg2.Error, ValueError, KeyError) as e:
        logger.exception("Failed to undo %s", undo_type, extra={"context": {"error": str(e)}})
        return no_update, {"message": f"Undo failed: {e}", "header": "Error"}

    return no_update, no_update
