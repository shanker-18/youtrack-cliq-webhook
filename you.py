    mutated_year = _get_mutation_year_idx(refresh_trigger)
    if mutated_year == 1:
        return y1_table, no_update, add_btn_disabled, add_btn_disabled, str(year), no_update
    if mutated_year == 2:
        return no_update, y2_table, no_update, no_update, no_update, str(year + 1)

    grid_result = (
        y1_table,
        y2_table,
        add_btn_disabled,
        add_btn_disabled,
        str(year),
        str(year + 1),
    )
    _PLANNING_SERVER_CACHE[cache_key] = grid_result
    return grid_result
