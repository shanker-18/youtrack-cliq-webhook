    latest_comp_m_nbr = _detect_shipment_cutoff_month(latest_year, data_by_year[latest_year]["gts_val"])
    if latest_year == curr_kv_yr_str:
        curr_kv_m = KenvueCalendar.get_date_info(date.today()).kv_month_num
        if rows_cons:
            cons_comp_m = get_kv_month_completeness_status(rows_cons, target_year=latest_year)["latest_complete_m_nbr"]
            latest_comp_m_nbr = min(latest_comp_m_nbr, max(cons_comp_m, curr_kv_m - 1))
        else:
            latest_comp_m_nbr = min(latest_comp_m_nbr, max(0, curr_kv_m - 1))
