def _extract_in_memory_current_value(
    row_by_id: dict, rid: str, period: date, base_year: int
) -> Tuple[Optional[float], str]:
    """Read cell value from already-fetched in-memory row store instead of DB query."""
    row = row_by_id.get(str(rid))
    if not row:
        return None, "0.00"
    year_idx = "y1" if period.year == base_year else "y2"
    vals = row.get(f"{year_idx}Vals", [])
    month_idx = period.month - 1
    if month_idx >= len(vals):
        return None, "0.00"
    try:
        val = float(str(vals[month_idx]).replace(",", "") or 0.0)
        return val, f"{val:.2f}"
    except (ValueError, TypeError, IndexError):
        return None, "0.00"
