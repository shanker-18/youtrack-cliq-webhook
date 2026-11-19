    cur_num, old_val_str = None, "0.00"
    if row_by_id:
        cur_num, old_val_str = _extract_in_memory_current_value(row_by_id, rid, period, base_year)
    if cur_num is None:
        cur_num, old_val_str = _resolve_current_cell_value(domain, rid, period)
