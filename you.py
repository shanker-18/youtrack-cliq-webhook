    factory_pos_map, pos_val_map, pos_u_map = extract_consumption_maps(rows_cons, model_name) if rows_cons else ({}, {}, {})

    latest_comp_m_nbr = _detect_shipment_cutoff_month(latest_year, data_by_year[latest_year]["gts_val"])
    if latest_year == curr_kv_yr_str:
        curr_kv_m = KenvueCalendar.get_date_info(date.today()).kv_month_num
        latest_comp_m_nbr = min(latest_comp_m_nbr, max(0, curr_kv_m - 1))

    # Clear partial-month actuals for incomplete/open months so they project from Plan + Building Blocks
    for m_i in range(latest_comp_m_nbr, 12):
        data_by_year[latest_year]["gts_val"][m_i] = None
        data_by_year[latest_year]["gts_qty"][m_i] = None
        factory_pos_map.pop((str(latest_year), m_i), None)
        pos_val_map.pop((str(latest_year), m_i), None)
        pos_u_map.pop((str(latest_year), m_i), None)

    _blend_factory_pos_override(factory_pos_map, factory_pos_by_year)
    fy_price_factor_prev = _compute_prev_year_fy_price_factor(data_by_year, prev_year, pos_val_map, pos_u_map)

    _project_shipment_future_months(
