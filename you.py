            year_idx = 1 if cell_year <= (cell_year if month_num <= 12 else cell_year) else 2
            out_grid = {"trigger": "cell_edit", "timestamp": time.time(), "row_id": row_id, "year_idx": year_idx}
