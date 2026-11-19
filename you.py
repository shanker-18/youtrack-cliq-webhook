def _parse_batch_cell(c: dict) -> Optional[Tuple]:
    """Parse and validate a single cell for batch save. Returns (rid, period, old, new) or None on error."""
    try:
        old_val = round(float(str(c.get("old_val", "0")).replace(",", "")), 2)
        new_val = round(float(str(c.get("new_val", "0")).replace(",", "")), 2)
        period_month = datetime.strptime(c["period_iso"], "%Y-%m-%d").date()
        rid = int(c["row_id"]) if str(c["row_id"]).isdigit() else c["row_id"]
    except (ValueError, TypeError, KeyError):
        return None
    if old_val == new_val:
        return ()
    return rid, period_month, old_val, new_val


def _upsert_and_audit_cell(is_consumption, cursor, rid, period_month, old_val, new_val, snapshot_id, user_id, dept_id, comment):
    """Upsert one cell value and insert its audit record using a shared cursor."""
    upsert_fn = upsert_consumption_value if is_consumption else upsert_shipment_value
    audit_fn = insert_consumption_audit_record if is_consumption else insert_shipment_audit_record
    val_record = upsert_fn(row_id=rid, period_month=period_month, value=new_val, user_id=user_id, cursor=cursor)
    val_id = val_record["value_id"] if val_record else None
    audit_fn(
        snapshot_id=snapshot_id, row_id=rid, value_id=val_id,
        event_type="BULK_PASTE_SAVED", old_value=old_val, new_value=new_val,
        comment=comment, performed_by=user_id, dept_id=dept_id, cursor=cursor,
    )


def batch_save_cell_edits(cells: list, ctx: dict) -> dict:
    """Save multiple cell edits in a single database transaction instead of one per cell."""
    domain = ctx.get("domain", "CONSUMPTION")
    is_consumption = domain.upper() == "CONSUMPTION"
    snapshot_id = ctx["snapshot_id"]
    comment = ctx.get("comment") or "Bulk paste saved by planner"

    changed_cells = [
        c for c in cells
        if not c.get("skipped") and c.get("changed") and not c.get("is_text")
    ]
    if not changed_cells:
        return {"saved": 0, "errors": 0}

    saved = 0
    errors = 0
    with get_db_cursor(commit=True) as cursor:
        valid_user_id = _resolve_valid_user_id(cursor, ctx.get("user_id", 1))
        for c in changed_cells:
            parsed = _parse_batch_cell(c)
            if parsed is None:
                errors += 1
                continue
            if not parsed:
                continue
            rid, period_month, old_val, new_val = parsed
            _upsert_and_audit_cell(
                is_consumption, cursor, rid, period_month, old_val, new_val,
                snapshot_id, valid_user_id, ctx.get("dept_id", 2), comment,
            )
            saved += 1

    return {"saved": saved, "errors": errors}
