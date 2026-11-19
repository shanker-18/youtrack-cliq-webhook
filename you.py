    try:
        save_year_idx = int((save_data or {}).get("year_idx", 1))
    except (TypeError, ValueError):
        save_year_idx = 1
    grid_token, toast_token = _commit_inline_cell_numeric_edit(
        domain, snapshot_id, parsed_row_id, period_dt, old_num, new_num,
        user_id, context_data.get("dept_id", 2),
        context_data.get("model_id"), month, cell_year
    )
    if isinstance(grid_token, dict) and grid_token.get("trigger") == "cell_edit":
        grid_token["year_idx"] = save_year_idx
    return grid_token, toast_token
