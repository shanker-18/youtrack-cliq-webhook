# pylint: disable=too-many-lines,too-many-locals,too-many-branches,broad-except
"""
NA IBP Planning Application — Variance Calculations Engine
==========================================================
Authoritative calculation engine for:
1. Consumption Variance Matrix (IBP: Current - Prior | BP: Current - Annual BP)
2. Shipment Variance Matrix (IBP: Current - Prior | BP: Current - Annual BP)

Rules:
- Top Row {base_year}: Current cycle in base year - Baseline in base year
- Bottom Row {plan_year}: Sum of active driver variances; labelled strictly with the year (e.g. '2026')
- Monospace 2-decimal formatting with parentheses for negatives e.g. (0.10) and blanks for no data
"""

import math
import os
import datetime
from typing import Optional, Dict, List, Any, Union

from services.variance_service import (
    get_active_years,
    get_cycle_snapshot_ids,
    load_consumption_variance_drivers,
    load_shipment_variance_drivers,
    CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS,
    SHIPMENT_VARIANCE_DRIVER_DEFINITIONS,
    DRIVER_BASE_TREND,
    DRIVER_NET_INNOVATION,
    DRIVER_NET_PRICE,
)
from utils.logger import get_logger

logger = get_logger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CONSUMPTION_PARENT_DRIVER_NAMES = [
    DRIVER_BASE_TREND, "Season", "Competition", "Distribution", DRIVER_NET_INNOVATION,
    "Discontinuations", "Renovation", "Media", "Trade", DRIVER_NET_PRICE,
    "Club", "Other"
]


def calc_variance_totals(
    monthly_vals: List[Optional[float]], cutoff_month: int = 0
) -> Dict[str, Optional[float]]:
    """Calculates Q1..Q4, FY, YTD, and YTG totals preserving None and 0.0."""
    has_data = any(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in monthly_vals)
    if not has_data:
        return dict.fromkeys(["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"], None)

    def _sum_range(st: int, en: int) -> Optional[float]:
        if st >= en:
            return None
        arr = [v for v in monthly_vals[st:en] if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return round(sum(arr), 9) if arr else None

    safe_cutoff = max(0, min(12, int(cutoff_month or 0)))
    return {
        "Q1": _sum_range(0, 3),
        "Q2": _sum_range(3, 6),
        "Q3": _sum_range(6, 9),
        "Q4": _sum_range(9, 12),
        "FY": _sum_range(0, 12),
        "YTD": _sum_range(0, safe_cutoff),
        "YTG": _sum_range(safe_cutoff, 12),
    }


def _resolve_cutoff_month(active_cycle_month: Optional[int]) -> int:
    env_cutoff = os.getenv("IBP_CUTOFF_MONTH")
    if env_cutoff and env_cutoff.isdigit():
        return int(env_cutoff)
    if active_cycle_month and 1 <= active_cycle_month <= 12:
        return active_cycle_month
    try:
        from services.kv_calendar import KenvueCalendar
        info = KenvueCalendar.get_date_info(datetime.date.today())
        if isinstance(info, dict):
            return int(info.get("fiscal_month") or info.get("kv_month_num") or 1)
        return int(getattr(info, "kv_month_num", None) or getattr(info, "fiscal_month", None) or datetime.date.today().month)
    except Exception:
        return datetime.date.today().month


def calculate_driver_heatmap_ranges(drivers: dict, driver_totals: Optional[dict] = None) -> tuple[float, float]:
    all_vals: List[float] = []
    for d_vals in drivers.values():
        if isinstance(d_vals, list):
            for v in d_vals:
                if v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                    all_vals.append(float(v))
    if driver_totals:
        for t_dict in driver_totals.values():
            if isinstance(t_dict, dict):
                for v in t_dict.values():
                    if v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                        all_vals.append(float(v))
    pos_vals = [v for v in all_vals if v > 0]
    neg_vals = [abs(v) for v in all_vals if v < 0]
    max_pos = max(pos_vals) if pos_vals else 1.0
    max_neg_mag = max(neg_vals) if neg_vals else 1.0
    return max_pos, max_neg_mag


# ─── 1. Consumption Variance Calculation Engine ──────────────────────────────

def compute_consumption_variance_matrix(
    models: Union[str, List[str]], comparison_mode: str = "IBP"
) -> Dict[str, Any]:
    """
    Computes Consumption Variance Matrix for IBP (Current - Prior) or BP (Current - Annual BP).
    """
    mode = (comparison_mode or "IBP").upper()
    base_year, plan_year = get_active_years()
    snap_info = get_cycle_snapshot_ids(plan_year)
    cutoff_month = _resolve_cutoff_month(snap_info.active_cycle_month)

    # 1. Base Year Variance (Current base_year - Baseline base_year)
    base_year_drivers, _ = load_consumption_variance_drivers(models, base_year, comparison_mode=mode)
    for d_name, d_vals in list(base_year_drivers.items()):
        base_year_drivers[d_name] = [
            round(v, 9) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else None
            for v in d_vals
        ]

    base_monthly_tot = [0.0] * 12
    base_has_month = [False] * 12
    for d_name in CONSUMPTION_PARENT_DRIVER_NAMES:
        d_vals = base_year_drivers.get(d_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                base_monthly_tot[i] += d_vals[i]
                base_has_month[i] = True

    pos_base_variance = [
        round(base_monthly_tot[i], 9) if base_has_month[i] else None
        for i in range(12)
    ]

    # 2. Plan Year Driver Variances (Current plan_year - Baseline plan_year)
    drivers, has_plan_baseline = load_consumption_variance_drivers(models, plan_year, comparison_mode=mode)
    for d_name, d_vals in list(drivers.items()):
        drivers[d_name] = [
            round(v, 9) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else None
            for v in d_vals
        ]

    # 3. Plan Year Bottom Row (Sum of all active parent building blocks)
    plan_monthly_tot = [0.0] * 12
    plan_has_month = [False] * 12
    for d_name in CONSUMPTION_PARENT_DRIVER_NAMES:
        d_vals = drivers.get(d_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                plan_monthly_tot[i] += d_vals[i]
                plan_has_month[i] = True

    pos_plan_variance = [
        round(plan_monthly_tot[i], 9) if plan_has_month[i] else None
        for i in range(12)
    ]

    totals_base = calc_variance_totals(pos_base_variance, cutoff_month)
    totals_plan = calc_variance_totals(pos_plan_variance, cutoff_month)

    driver_totals = {
        disp_name: calc_variance_totals(drivers.get(disp_name, [None] * 12), cutoff_month)
        for _, disp_name, _ in CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS
    }

    max_pos, max_neg_mag = calculate_driver_heatmap_ranges(drivers, driver_totals)

    return {
        "comparison_mode": mode,
        "bp_missing": (mode == "BP" and not has_plan_baseline),
        "base_year": base_year,
        "plan_year": plan_year,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "cutoff_month": cutoff_month,
        "models": models,
        "base_row_vals": pos_base_variance,
        "totals_base": totals_base,
        "plan_row_vals": pos_plan_variance,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "max_pos": max_pos,
        "max_neg_mag": max_neg_mag,
    }


# ─── 2. Shipment Variance Calculation Engine ─────────────────────────────────

def compute_shipment_variance_matrix(
    models: Union[str, List[str]], comparison_mode: str = "IBP"
) -> Dict[str, Any]:
    """
    Computes Shipment Variance Matrix for IBP (Current - Prior) or BP (Current - Annual BP).
    """
    mode = (comparison_mode or "IBP").upper()
    base_year, plan_year = get_active_years()
    snap_info = get_cycle_snapshot_ids(plan_year)
    cutoff_month = _resolve_cutoff_month(snap_info.active_cycle_month)

    # 1. Base Year Shipment Variance
    base_year_drivers, _ = load_shipment_variance_drivers(models, base_year, comparison_mode=mode)
    base_monthly_tot = [0.0] * 12
    base_has_month = [False] * 12
    for grp, disp_name, _ in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS:
        d_vals = base_year_drivers.get((grp, disp_name)) or base_year_drivers.get(disp_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                base_monthly_tot[i] += d_vals[i]
                base_has_month[i] = True

    ship_base_variance = [
        round(base_monthly_tot[i], 9) if base_has_month[i] else None
        for i in range(12)
    ]

    # 2. Plan Year Shipment Driver Variances
    drivers, has_plan_baseline = load_shipment_variance_drivers(models, plan_year, comparison_mode=mode)
    plan_monthly_tot = [0.0] * 12
    plan_has_month = [False] * 12
    driver_totals = {}
    for grp, disp_name, _ in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS:
        d_vals = drivers.get((grp, disp_name)) or drivers.get(disp_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                plan_monthly_tot[i] += d_vals[i]
                plan_has_month[i] = True

        tot = calc_variance_totals(d_vals, cutoff_month)
        driver_totals[disp_name] = tot
        driver_totals[(grp, disp_name)] = tot
        driver_totals[f"{grp}_{disp_name}"] = tot

    # 3. Plan Year Bottom Row
    ship_plan_variance = [
        round(plan_monthly_tot[i], 9) if plan_has_month[i] else None
        for i in range(12)
    ]

    totals_base = calc_variance_totals(ship_base_variance, cutoff_month)
    totals_plan = calc_variance_totals(ship_plan_variance, cutoff_month)

    plain_drivers = {disp: drivers.get(disp, [None] * 12) for _, disp, _ in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS}
    max_pos, max_neg_mag = calculate_driver_heatmap_ranges(plain_drivers, driver_totals)

    return {
        "comparison_mode": mode,
        "bp_missing": (mode == "BP" and not has_plan_baseline),
        "base_year": base_year,
        "plan_year": plan_year,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "cutoff_month": cutoff_month,
        "models": models,
        "base_row_vals": ship_base_variance,
        "totals_base": totals_base,
        "plan_row_vals": ship_plan_variance,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "max_pos": max_pos,
        "max_neg_mag": max_neg_mag,
    }
