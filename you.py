    result = _commit_inline_cell_numeric_edit(
        domain, snapshot_id, parsed_row_id, period_dt, old_num, new_num,
        user_id, context_data.get("dept_id", 2),
        context_data.get("model_id"), month, cell_year
    )
    if isinstance(result[0], dict) and result[0].get("trigger") == "cell_edit":
        result[0]["year_idx"] = save_year_idx
    return result
