def batch_save_cell_edits(cells: list, ctx: dict) -> dict:
    """Save multiple cell edits in a single database transaction instead of one per cell."""
    domain = ctx.get("domain", "CONSUMPTION")
    is_consumption = domain.upper() == "CONSUMPTION"
    snapshot_id = ctx["snapshot_id"]
    user_id = ctx.get("user_id", 1)
    dept_id = ctx.get("dept_id", 2)
    comment = ctx.get("comment") or "Bulk paste saved by planner"

    saved = 0
    errors = 0

    changed_cells = [
        c for c in cells
        if not c.get("skipped") and c.get("changed") and not c.get("is_text")
    ]
    if not changed_cells:
        return {"saved": 0, "errors": 0}

    with get_db_cursor(commit=True) as cursor:
        valid_user_id = _resolve_valid_user_id(cursor, user_id)
        for c in changed_cells:
            try:
                old_val = round(float(str(c.get("old_val", "0")).replace(",", "")), 2)
                new_val = round(float(str(c.get("new_val", "0")).replace(",", "")), 2)
                period_month = datetime.strptime(c["period_iso"], "%Y-%m-%d").date()
                rid = int(c["row_id"]) if str(c["row_id"]).isdigit() else c["row_id"]
            except (ValueError, TypeError, KeyError):
                errors += 1
                continue

            if round(new_val, 2) == round(old_val, 2):
                continue

            if is_consumption:
                val_record = upsert_consumption_value(
                    row_id=rid, period_month=period_month,
                    value=new_val, user_id=valid_user_id, cursor=cursor,
                )
                val_id = val_record["value_id"] if val_record else None
                insert_consumption_audit_record(
                    snapshot_id=snapshot_id, row_id=rid, value_id=val_id,
                    event_type="BULK_PASTE_SAVED", old_value=old_val, new_value=new_val,
                    comment=comment, performed_by=valid_user_id, dept_id=dept_id, cursor=cursor,
                )
            else:
                val_record = upsert_shipment_value(
                    row_id=rid, period_month=period_month,
                    value=new_val, user_id=valid_user_id, cursor=cursor,
                )
                val_id = val_record["value_id"] if val_record else None
                insert_shipment_audit_record(
                    snapshot_id=snapshot_id, row_id=rid, value_id=val_id,
                    event_type="BULK_PASTE_SAVED", old_value=old_val, new_value=new_val,
                    comment=comment, performed_by=valid_user_id, dept_id=dept_id, cursor=cursor,
                )
            saved += 1

    return {"saved": saved, "errors": errors}
