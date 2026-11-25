def _build_variance_result_dict(mode, has_plan_baseline, base_year, plan_year, cutoff_month,
                                 models, base_variance, plan_variance, drivers, driver_totals,
                                 max_pos, max_neg_mag):
    """Builds the standard variance matrix result dictionary."""
    return {
        "comparison_mode": mode,
        "bp_missing": (mode == "BP" and not has_plan_baseline),
        "base_year": base_year,
        "plan_year": plan_year,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "cutoff_month": cutoff_month,
        "models": models,
        "base_row_vals": base_variance,
        "totals_base": calc_variance_totals(base_variance, cutoff_month),
        "plan_row_vals": plan_variance,
        "totals_plan": calc_variance_totals(plan_variance, cutoff_month),
        "drivers": drivers,
        "driver_totals": driver_totals,
        "max_pos": max_pos,
        "max_neg_mag": max_neg_mag,
    }
