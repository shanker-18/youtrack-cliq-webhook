    try:
        save_year_idx = int((save_data or {}).get("year_idx", 1))
    except (TypeError, ValueError):
        save_year_idx = 1
