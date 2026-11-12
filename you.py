def _is_nonzero_val(v: Any) -> bool:
    return (
        v is not None
        and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
        and abs(float(v)) >= 1e-9
    )


def _build_driver_row_data_cells(
    d_vals: list,
    d_totals: dict,
    max_pos: float,
    max_neg_mag: float,
    is_coc: bool,
    driver_name: str = "",
    drivers_dict: Optional[dict] = None,
    driver_totals_dict: Optional[dict] = None,
) -> list[html.Td]:
    """Builds monthly and total data cells for a driver row based on CoC mode."""
    if is_coc:
        return build_coc_data_cells(d_vals, d_totals, max_pos, max_neg_mag, is_driver=True, decimals=2)

    clean_vals = list(d_vals)
    clean_totals = dict(d_totals or {})
    compound_components = {
        "Net Innovation": ("Innovation", "Cannibalization"),
        "COMPOUND_NET_INNOVATION": ("Innovation", "Cannibalization"),
        "Net Price": ("Price", "Elasticity"),
        "COMPOUND_NET_PRICE": ("Price", "Elasticity"),
    }
    comp_pair = compound_components.get(driver_name)

    if comp_pair is not None:
        if drivers_dict:
            c1 = drivers_dict.get(comp_pair[0], [None] * 12)
            c2 = drivers_dict.get(comp_pair[1], [None] * 12)
            clean_vals = [
                clean_vals[i] if (i < len(c1) and _is_nonzero_val(c1[i])) or (i < len(c2) and _is_nonzero_val(c2[i])) else None
                for i in range(len(clean_vals))
            ]
        else:
            clean_vals = [v if _is_nonzero_val(v) else None for v in clean_vals]

        period_slices = {"Q1": (0, 3), "Q2": (3, 6), "Q3": (6, 9), "Q4": (9, 12), "FY": (0, 12)}
        for col, (st, en) in period_slices.items():
            if all(v is None for v in clean_vals[st:en]):
                clean_totals[col] = None
        for col in ("YTD", "YTG"):
            if not _is_nonzero_val(clean_totals.get(col)):
                if driver_totals_dict:
                    t1 = (driver_totals_dict.get(comp_pair[0]) or {}).get(col)
                    t2 = (driver_totals_dict.get(comp_pair[1]) or {}).get(col)
                    if not _is_nonzero_val(t1) and not _is_nonzero_val(t2):
                        clean_totals[col] = None
                elif all(v is None for v in clean_vals):
                    clean_totals[col] = None
    else:
        clean_vals = [v if _is_nonzero_val(v) else None for v in clean_vals]
        clean_totals = {col: (val if _is_nonzero_val(val) else None) for col, val in clean_totals.items()}

    return build_data_cells(clean_vals, clean_totals, max_pos, max_neg_mag, is_driver=True, decimals=2)


def _render_grouped_driver_rows(
    definitions: list,
    drivers_dict: dict,
    driver_totals_dict: dict,
    max_pos: float,
    max_neg_mag: float,
    is_coc: bool = False,
    is_shipment: bool = False,
) -> List[html.Tr]:
    group_counts: Dict[str, int] = {}
    for grp, _, _ in definitions:
        group_counts[grp] = group_counts.get(grp, 0) + 1
    seen_groups = set()
    group_rows_counter: Dict[str, int] = {}
    rows = []
    for grp, driver_name, _ in definitions:
        cells = []
        if grp not in seen_groups:
            seen_groups.add(grp)
            group_rows_counter[grp] = 0
            cells.append(html.Td(grp, rowSpan=group_counts[grp], className="sum-category-label"))
        group_rows_counter[grp] += 1
        is_last_in_group = (group_rows_counter[grp] == group_counts[grp])
        is_sub = driver_name in SUB_DRIVERS and not is_shipment
        driver_cls = CLASS_DRIVER_SUB if is_sub else "sum-driver-label"
        cells.append(html.Td(driver_name, className=driver_cls))
        d_vals, d_totals = _resolve_driver_vals_and_totals(
            grp, driver_name, drivers_dict, driver_totals_dict, is_shipment
        )
        cells.extend(
            _build_driver_row_data_cells(
                d_vals, d_totals, max_pos, max_neg_mag, is_coc,
                driver_name=driver_name, drivers_dict=drivers_dict, driver_totals_dict=driver_totals_dict,
            )
        )
        row_cls = "sum-row-group-bottom" if is_last_in_group else None
        rows.append(html.Tr(cells, className=row_cls))
    return rows
