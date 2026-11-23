def _parse_batch_cell(c: dict) -> Optional[Tuple]:
    """Parse and validate a single cell for batch save. Returns (rid, period, old, new) or None on error."""
    try:
        old_val = round(float(str(c.get("old_val", "0")).replace(",", "")), 2)
        new_val = round(float(str(c.get("new_val", "0")).replace(",", "")), 2)
        period_month = datetime.strptime(c["period_iso"], "%Y-%m-%d").date()
        rid = int(c["row_id"]) if str(c["row_id"]).isdigit() else c["row_id"]
    except (ValueError, TypeError, KeyError):
        return None
    return rid, period_month, old_val, new_val
