    factory_pos_map, pos_val_map, pos_u_map = extract_consumption_maps(rows_cons, model_name) if rows_cons else ({}, {}, {})

    latest_comp_m_nbr = _detect_shipment_cutoff_month(latest_year, data_by_year[latest_year]["gts_val"])
    if latest_year == curr_kv_yr_str:
        curr_kv_m = KenvueCalendar.get_date_info(date.today()).kv_month_num
        latest_comp_m_nbr = min(latest_comp_m_nbr, max(0, curr_kv_m - 1))

    cons_comp_m = (
        get_kv_month_completeness_status(rows_cons, target_year=latest_year)["latest_complete_m_nbr"]
        if rows_cons else latest_comp_m_nbr
    )

    # Clear incomplete/open Shipment months
    for m_i in range(latest_comp_m_nbr, 12):
        data_by_year[latest_year]["gts_val"][m_i] = None
        data_by_year[latest_year]["gts_qty"][m_i] = None

    # Clear incomplete/open Consumption maps separately so complete OCT Factory POS ($12.9) is preserved
    for m_i in range(cons_comp_m, 12):
        factory_pos_map.pop((str(latest_year), m_i), None)
        pos_val_map.pop((str(latest_year), m_i), None)
        pos_u_map.pop((str(latest_year), m_i), None)
