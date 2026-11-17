# ── 8. Undo Action Handler (AC3, AC4, AC5, AC6, AC7) ─────────────────────────
@callback(
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("undo-action-store", "data"),
    State("active-planning-context-store", "data"),
    prevent_initial_call=True,
)
def handle_undo_action(undo_data, context_data):
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

    if undo_type == "text_edit":
        row_id = undo_data.get("row_id")
        col_type = undo_data.get("col_type", "item")
        old_val = undo_data.get("old_val", "")
        if not row_id:
            return no_update, no_update
        try:
            row = get_row_details(domain, row_id)
            if not row:
                return no_update, no_update
            if col_type == "item":
                item_to_save = old_val
                desc_to_save = row.get("description") or ""
                field_label = "Item"
            else:
                item_to_save = row.get("item") or ""
                desc_to_save = old_val
                field_label = "Description"
            update_line_item_text(domain=domain, row_id=row_id, item=item_to_save, description=desc_to_save)
            invalidate_planning_cache(model_id=model_id, domain=domain)
            refresh = {"trigger": "undo_text", "timestamp": time.time(), "row_id": row_id}
            toast = {"message": f"Undo: {field_label} reverted to \"{old_val}\"", "header": "Undo Applied"}
            return refresh, toast
        except (psycopg2.Error, ValueError, KeyError) as e:
            logger.exception("Failed to undo text edit", extra={"context": {"error": str(e)}})
            return no_update, {"message": f"Undo failed: {e}", "header": "Error"}

    if undo_type == "paste":
        toast = {"message": "Paste undo: please use Ctrl+Z immediately after paste for best results.", "header": "Undo Note"}
        return no_update, toast

    if undo_type == "row_add":
        row_id = undo_data.get("row_id")
        if not row_id:
            return no_update, no_update
        try:
            soft_delete_line_item(domain, snapshot_id, row_id, dept_id, user_id, "Undo: row addition reverted")
            invalidate_planning_cache(model_id=model_id, domain=domain)
            refresh = {"trigger": "undo_row_add", "timestamp": time.time(), "row_id": row_id}
            toast = {"message": "Undo: added row removed.", "header": "Undo Applied"}
            return refresh, toast
        except (psycopg2.Error, ValueError, KeyError) as e:
            logger.exception("Failed to undo row add", extra={"context": {"error": str(e)}})
            return no_update, {"message": f"Undo failed: {e}", "header": "Error"}

    if undo_type == "row_delete":
        row_id = undo_data.get("row_id")
        if not row_id:
            return no_update, no_update
        try:
            restore_line_item(domain, snapshot_id, row_id, dept_id, user_id)
            invalidate_planning_cache(model_id=model_id, domain=domain)
            refresh = {"trigger": "undo_row_delete", "timestamp": time.time(), "row_id": row_id}
            toast = {"message": "Undo: deleted row restored.", "header": "Undo Applied"}
            return refresh, toast
        except (psycopg2.Error, ValueError, KeyError) as e:
            logger.exception("Failed to undo row delete", extra={"context": {"error": str(e)}})
            return no_update, {"message": f"Undo failed: {e}", "header": "Error"}

    return no_update, no_update
