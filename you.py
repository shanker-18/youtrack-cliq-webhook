# pylint: disable=too-many-lines,too-many-locals,too-many-branches,broad-except
"""
NA IBP Planning Application — Summary Calculations Engine
=========================================================
Authoritative calculation engine for:
1. Consumption Summary Dashboard
2. Shipment Summary Dashboard
3. GTS YoY Summary Dashboard
4. GTS Change of Cycle (CoC) Summary Dashboard

Features:
- Pure Python implementation (zero pandas dependency)
- 100% Dynamic years and months using services.kv_calendar.KenvueCalendar
- Multi-model aggregation (sum before calculation across models)
- Dynamic cutoff month and completeness detection
- Dynamic totals across quarters (Q1-Q4), FY, YTD, and YTG
"""

import math
import os
import datetime
from typing import Optional, Dict, List, Any, Union

from services.summary_service import (
    get_active_years,
    load_consumption_model_rules,
    load_shipment_model_rules,
    load_price_index_from_postgres,
    load_live_consumption_building_blocks,
    load_live_shipment_building_blocks,
    load_coc_building_blocks,
    fetch_snowflake_monthly_pos,
    fetch_snowflake_monthly_gts,
    get_cycle_snapshot_ids,
    CONSUMPTION_DRIVER_ROW_DEFINITIONS,
    SHIPMENT_DRIVER_ROW_DEFINITIONS,
    GTS_COC_DRIVER_DEFINITIONS,
)
from utils.logger import get_logger

logger = get_logger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DRIVER_BASE_TREND = "Base Trend"
DRIVER_OTHER = "Other"
DRIVER_NET_INNOVATION = "Net Innovation"
DRIVER_NET_PRICE = "Net Price"

INDIVIDUAL_DRIVER_NAMES = [
    DRIVER_BASE_TREND, "Season", "Competition", "Distribution", "Innovation",
    "Cannibalization", "Discontinuations", "Renovation", "Media", "Trade",
    "Price", "Elasticity", "Club", DRIVER_OTHER
]


def _normalize_models(models: Any) -> list[str]:
    """Safely normalizes input model(s) to a clean list of non-empty strings."""
    if not models:
        return []
    if isinstance(models, str):
        s = models.strip()
        return [s] if s else []
    try:
        return [str(m).strip() for m in models if m and str(m).strip()]
    except (TypeError, ValueError):
        return []


# ─── Helper: Quarter & Period Aggregations ────────────────────────────────────

def calc_totals(
    monthly_vals: List[Optional[float]], cutoff_month: int = 0
) -> Dict[str, Optional[float]]:
    """
    Calculates Q1..Q4, FY, YTD, and YTG totals dynamically.
    If all 12 months are None, returns None for all totals to keep blank driver rows blank.
    """
    has_data = any(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in monthly_vals)
    if not has_data:
        return dict.fromkeys(["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"], None)

    def _sum_range(st: int, en: int) -> Optional[float]:
        if st >= en:
            return None
        arr = [v for v in monthly_vals[st:en] if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return round(sum(arr), 4) if arr else None

    safe_cutoff = max(0, min(12, int(cutoff_month or 0)))

    return {
        "Q1": _sum_range(0, 3),
        "Q2": _sum_range(3, 6),
        "Q3": _sum_range(6, 9),
        "Q4": _sum_range(9, 12),
        "FY": _sum_range(0, 12),
        "YTD": _sum_range(0, safe_cutoff) if safe_cutoff > 0 else None,
        "YTG": _sum_range(safe_cutoff, 12) if safe_cutoff < 12 else None,
    }


def _sum_two_monthly_series(series_a: list, series_b: list) -> list[Optional[float]]:
    """Element-wise sum of two 12-month lists preserving None semantics."""
    result: list[Optional[float]] = [None] * 12
    for i in range(12):
        if series_a[i] is not None or series_b[i] is not None:
            result[i] = round((series_a[i] or 0.0) + (series_b[i] or 0.0), 4)
    return result


def _ensure_compound_drivers(drivers: dict):
    """Computes Net Innovation and Net Price if individual sub-drivers are present."""
    inno = drivers.get("Innovation", [None] * 12)
    cann = drivers.get("Cannibalization", [None] * 12)
    if DRIVER_NET_INNOVATION not in drivers or not any(v is not None for v in drivers[DRIVER_NET_INNOVATION]):
        drivers[DRIVER_NET_INNOVATION] = _sum_two_monthly_series(inno, cann)

    price = drivers.get("Price", [None] * 12)
    elast = drivers.get("Elasticity", [None] * 12)
    if DRIVER_NET_PRICE not in drivers or not any(v is not None for v in drivers[DRIVER_NET_PRICE]):
        drivers[DRIVER_NET_PRICE] = _sum_two_monthly_series(price, elast)


def _sum_monthly_building_blocks(drivers: dict, driver_names: list) -> tuple[list, list]:
    """Sums monthly building blocks across driver names, tracking active months."""
    total_monthly_bb = [0.0] * 12
    has_bb_for_month = [False] * 12
    for d_name in driver_names:
        d_vals = drivers.get(d_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                total_monthly_bb[i] += d_vals[i]
                has_bb_for_month[i] = True
    return total_monthly_bb, has_bb_for_month


def _calc_consumption_diff(
    pos_plan_actual: list, bb_calculated_pos: list, pos_base: list, cutoff_month: int
) -> list:
    """Calculates Difference row (Actuals - (Base + BB)) for closed months only."""
    diff_val = [None] * 12
    for i in range(12):
        m_num = i + 1
        if m_num <= cutoff_month:
            act = pos_plan_actual[i]
            bb_calc = bb_calculated_pos[i]
            base_v = pos_base[i]
            if act is not None and bb_calc is not None:
                diff_val[i] = round(act - bb_calc, 4)
            elif act is not None and base_v is not None:
                diff_val[i] = round(act - base_v, 4)
    return diff_val


def _calc_bb_calculated_pos(
    pos_base: list, total_monthly_bb: list, has_bb_for_month: list
) -> list:
    """Calculates BB Calculated POS: Base + BB sum if building blocks exist."""
    res = [None] * 12
    for i in range(12):
        base_v = pos_base[i]
        if base_v is not None and has_bb_for_month[i]:
            res[i] = round(base_v + total_monthly_bb[i], 4)
        else:
            res[i] = base_v
    return res


def _calc_consumption_plan_pos(
    pos_plan_actual: list, bb_calculated_pos: list, cutoff_month: int
) -> list:
    """Merges Actual POS (closed months) and BB Calculated POS (open months)."""
    res = [None] * 12
    for i in range(12):
        m_num = i + 1
        if m_num <= cutoff_month and pos_plan_actual[i] is not None:
            res[i] = pos_plan_actual[i]
        else:
            res[i] = bb_calculated_pos[i]
    return res


def _calc_yoy_pct_series(plan_series: list, base_series: list) -> list[Optional[float]]:
    """Calculates YoY %: ((Plan - Base) / Base) * 100."""
    res = [None] * 12
    for i in range(12):
        p, b = plan_series[i], base_series[i]
        if p is not None and b is not None and b != 0:
            res[i] = round(((p - b) / b) * 100.0, 1)
        else:
            res[i] = None
    return res


def _calc_totals_yoy_dict(totals_plan: dict, totals_base: dict) -> dict[str, Optional[float]]:
    """Calculates YoY growth % for period totals."""
    yoy_dict = {}
    for period in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        p, b = totals_plan.get(period), totals_base.get(period)
        if p is not None and b is not None and b != 0:
            yoy_dict[period] = round(((p - b) / b) * 100.0, 1)
        else:
            yoy_dict[period] = None
    return yoy_dict


def _calc_diff_period_totals(diff_val: list, cutoff_month: int) -> dict[str, Optional[float]]:
    """Computes quarterly and period sums for the Difference row."""
    def _sum_diff_slice(st: int, en: int) -> Optional[float]:
        if st >= en:
            return None
        valid = [v for v in diff_val[st:en] if v is not None]
        return round(sum(valid), 4) if valid else None

    return {
        "Q1": _sum_diff_slice(0, min(3, cutoff_month)),
        "Q2": _sum_diff_slice(3, min(6, cutoff_month)),
        "Q3": _sum_diff_slice(6, min(9, cutoff_month)),
        "Q4": _sum_diff_slice(9, min(12, cutoff_month)),
        "FY": _sum_diff_slice(0, cutoff_month),
        "YTD": _sum_diff_slice(0, cutoff_month),
        "YTG": None,
    }


def _detect_cutoff_month(gts_plan_actual: list, cons_cutoff: int) -> int:
    """Detects shipment cutoff month, aligning with consumption cutoff."""
    ship_cutoff = 0
    for i in range(12):
        if gts_plan_actual[i] is not None:
            ship_cutoff = i + 1
        else:
            break
    if cons_cutoff > 0:
        return min(cons_cutoff, ship_cutoff) if ship_cutoff > 0 else cons_cutoff
    return ship_cutoff


def _compute_factory_pos(pos_plan: list, price_indices: dict) -> list:
    """Scales POS plan by price indices: Factory POS = POS * (Price Index / 100)."""
    factory_pos = [None] * 12
    for i in range(12):
        m_num = i + 1
        if pos_plan[i] is not None:
            factor = price_indices.get(m_num, 100.0) / 100.0
            factory_pos[i] = round(pos_plan[i] * factor, 4)
    return factory_pos


def _scale_consumption_drivers_by_price_index(raw_cons_drivers: dict, price_indices: dict) -> dict:
    """Scales individual consumption drivers by price index to produce GTS YoY drivers."""
    drivers = {}
    for _, disp_name, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS:
        raw_vals = raw_cons_drivers.get(disp_name, [None] * 12)
        g_vals = [None] * 12
        has_any = False
        for i in range(12):
            m_num = i + 1
            if raw_vals[i] is not None:
                factor = price_indices.get(m_num, 100.0) / 100.0
                g_vals[i] = round(raw_vals[i] * factor, 4)
                has_any = True
        drivers[disp_name] = g_vals if has_any else [None] * 12

    _ensure_compound_drivers(drivers)
    return drivers


def _resolve_coc_cutoff_month(active_cycle_month: Optional[int]) -> int:
    """Determines active cutoff month for Change of Cycle calculation."""
    env_cutoff = os.getenv("IBP_CUTOFF_MONTH")
    if env_cutoff and env_cutoff.isdigit():
        return int(env_cutoff)
    if active_cycle_month and 1 <= active_cycle_month <= 12:
        return active_cycle_month
    try:
        from services.kv_calendar import KenvueCalendar
        target_date = datetime.date.today() + datetime.timedelta(days=1)
        dt_info = KenvueCalendar.get_date_info(target_date.strftime("%Y-%m-%d"))
        if isinstance(dt_info, dict) and "fiscal_month" in dt_info:
            return int(dt_info["fiscal_month"])
        elif hasattr(dt_info, "fiscal_month"):
            return int(dt_info.fiscal_month)
    except Exception:
        pass
    return 0


# ─── 1. Consumption Summary Calculation Engine ───────────────────────────────

def compute_consumption_summary_matrix(models: str | list[str]) -> Dict[str, Any]:
    """Calculates complete Consumption Summary Dashboard matrix."""
    base_year, plan_year = get_active_years()
    model_list = _normalize_models(models)
    rules = load_consumption_model_rules(model_list)

    pos_base, pos_plan_actual, cutoff_month = fetch_snowflake_monthly_pos(rules, base_year, plan_year)
    drivers = load_live_consumption_building_blocks(model_list, plan_year)
    _ensure_compound_drivers(drivers)

    parent_driver_names = [
        DRIVER_BASE_TREND, "Season", "Competition", "Distribution", DRIVER_NET_INNOVATION,
        "Discontinuations", "Renovation", "Media", "Trade", DRIVER_NET_PRICE,
        "Club", DRIVER_OTHER
    ]

    total_monthly_bb, has_bb_for_month = _sum_monthly_building_blocks(drivers, parent_driver_names)
    diff_val = _calc_consumption_diff(pos_plan_actual, total_monthly_bb, pos_base, cutoff_month)
    bb_calc_pos = _calc_bb_calculated_pos(pos_base, total_monthly_bb, has_bb_for_month)
    pos_plan = _calc_consumption_plan_pos(pos_plan_actual, bb_calc_pos, cutoff_month)

    yoy_pct = _calc_yoy_pct_series(pos_plan, pos_base)

    totals_base = calc_totals(pos_base, cutoff_month)
    totals_plan = calc_totals(pos_plan, cutoff_month)
    totals_yoy = _calc_totals_yoy_dict(totals_plan, totals_base)
    totals_diff = _calc_diff_period_totals(diff_val, cutoff_month)

    driver_totals = {
        disp_name: calc_totals(drivers.get(disp_name, [None] * 12), cutoff_month)
        for _, disp_name, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS
    }

    return _resolve_consumption_payload(
        base_year, plan_year, cutoff_month, model_list, pos_base, totals_base,
        pos_plan_actual, drivers, driver_totals, diff_val, totals_diff,
        pos_plan, totals_plan, yoy_pct, totals_yoy
    )


def _resolve_consumption_payload(
    base_year, plan_year, cutoff_month, models, pos_base, totals_base,
    pos_plan_actual, drivers, driver_totals, diff_val, totals_diff,
    pos_plan, totals_plan, yoy_pct, totals_yoy
) -> Dict[str, Any]:
    """Assembles final dictionary payload for consumption dashboard."""
    return {
        "base_year": base_year, "plan_year": plan_year,
        "label_base": str(base_year), "label_plan": str(plan_year),
        "cutoff_month": cutoff_month, "models": models,
        "pos_base": pos_base, "totals_base": totals_base,
        "pos_plan_actual": pos_plan_actual,
        "drivers": drivers, "driver_totals": driver_totals,
        "diff_val": diff_val, "totals_diff": totals_diff,
        "pos_plan": pos_plan, "totals_plan": totals_plan,
        "yoy_pct": yoy_pct, "totals_yoy": totals_yoy,
    }


# ─── 2. Shipment Summary Calculation Engine ──────────────────────────────────

def _sum_shipment_building_blocks(drivers: dict) -> list[float]:
    """Sums active building block values across all defined shipment drivers."""
    total_bb = [0.0] * 12
    for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        key = (grp, disp) if (grp, disp) in drivers else disp
        d_vals = drivers.get(key, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                total_bb[i] += d_vals[i]
    return total_bb


def _calc_shipment_plan_gts(
    gts_base: list, gts_plan_actual: list, total_bb: list, cutoff_month: int
) -> list[Optional[float]]:
    """Calculates Plan GTS: Actuals for closed months, (Base + BB) for open months."""
    gts_plan = [None] * 12
    for i in range(12):
        m_num = i + 1
        if m_num <= cutoff_month and gts_plan_actual[i] is not None:
            gts_plan[i] = gts_plan_actual[i]
        else:
            base_v = gts_base[i]
            if base_v is not None:
                gts_plan[i] = round(base_v + total_bb[i], 4)
            elif total_bb[i] != 0.0:
                gts_plan[i] = round(total_bb[i], 4)
    return gts_plan


def _calc_gts_growth_pct(plan_series: list, base_series: list) -> list[Optional[float]]:
    """Computes percentage growth between plan and base series."""
    growth_pct = [None] * 12
    for i in range(12):
        p, b = plan_series[i], base_series[i]
        if p is not None and b is not None and b != 0:
            growth_pct[i] = round(((p - b) / b) * 100.0, 1)
        else:
            growth_pct[i] = None
    return growth_pct


def _calc_gts_growth_totals(totals_plan: dict, totals_base: dict) -> dict[str, Optional[float]]:
    """Computes percentage growth between period totals."""
    growth_totals = {}
    for period in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        p, b = totals_plan.get(period), totals_base.get(period)
        if p is not None and b is not None and b != 0:
            growth_totals[period] = round(((p - b) / b) * 100.0, 1)
        else:
            growth_totals[period] = None
    return growth_totals


def _calc_shipment_driver_totals(drivers: dict, cutoff_month: int) -> dict:
    """Computes quarter and period totals for each shipment building block."""
    driver_totals = {}
    for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        key = (grp, disp) if (grp, disp) in drivers else disp
        vals = drivers.get(key, [None] * 12)
        totals = calc_totals(vals, cutoff_month)
        driver_totals[(grp, disp)] = totals
        driver_totals[disp] = totals
        driver_totals[f"{grp}_{disp}"] = totals
    return driver_totals


def _calc_gts_yoy_plan_gts(
    gts_base: list, gts_plan_actual: list, factory_pos: list, total_monthly_bb: list, cutoff_month: int
) -> list[Optional[float]]:
    """Calculates Plan GTS for GTS YoY: Actuals for closed months, (Factory POS + BB) for open months."""
    gts_plan = [None] * 12
    for i in range(12):
        m_num = i + 1
        if m_num <= cutoff_month and gts_plan_actual[i] is not None:
            gts_plan[i] = gts_plan_actual[i]
        else:
            f_val = factory_pos[i]
            if f_val is not None:
                gts_plan[i] = round(f_val + total_monthly_bb[i], 4)
            elif gts_base[i] is not None:
                gts_plan[i] = round(gts_base[i] + total_monthly_bb[i], 4)
    return gts_plan


def compute_shipment_summary_matrix(
    models: str | list[str], cons_cutoff_month: int = 0
) -> Dict[str, Any]:
    """Calculates complete Shipment Summary Dashboard matrix."""
    base_year, plan_year = get_active_years()
    model_list = _normalize_models(models)
    rules = load_shipment_model_rules(model_list)

    gts_base, gts_plan_actual = fetch_snowflake_monthly_gts(rules, base_year, plan_year)
    cutoff_month = _detect_cutoff_month(gts_plan_actual, cons_cutoff_month)

    drivers = load_live_shipment_building_blocks(model_list, plan_year)
    total_bb = _sum_shipment_building_blocks(drivers)
    gts_plan = _calc_shipment_plan_gts(gts_base, gts_plan_actual, total_bb, cutoff_month)

    growth_pct = _calc_gts_growth_pct(gts_plan, gts_base)

    totals_base = calc_totals(gts_base, cutoff_month)
    totals_plan = calc_totals(gts_plan, cutoff_month)
    totals_growth = _calc_gts_growth_totals(totals_plan, totals_base)
    driver_totals = _calc_shipment_driver_totals(drivers, cutoff_month)

    return {
        "base_year": base_year, "plan_year": plan_year,
        "label_base": str(base_year), "label_plan": str(plan_year),
        "cutoff_month": cutoff_month, "models": model_list,
        "gts_base": gts_base, "totals_base": totals_base,
        "gts_plan_actual": gts_plan_actual,
        "drivers": drivers, "driver_totals": driver_totals,
        "gts_plan": gts_plan, "totals_plan": totals_plan,
        "growth_pct": growth_pct, "totals_growth": totals_growth,
    }


# ─── 3. GTS YoY Summary Calculation Engine ───────────────────────────────────

def compute_gts_summary_matrix(models: str | list[str]) -> Dict[str, Any]:
    """Calculates complete GTS YoY Summary Dashboard matrix."""
    base_year, plan_year = get_active_years()
    model_list = _normalize_models(models)
    cons_data = compute_consumption_summary_matrix(model_list)
    pos_plan = cons_data["pos_plan"]
    cutoff_month = cons_data["cutoff_month"]

    price_indices = load_price_index_from_postgres(model_list)
    factory_pos = _compute_factory_pos(pos_plan, price_indices)

    raw_cons_drivers = load_live_consumption_building_blocks(model_list, plan_year)
    drivers = _scale_consumption_drivers_by_price_index(raw_cons_drivers, price_indices)

    ship_rules = load_shipment_model_rules(model_list)
    gts_base, gts_plan_actual = fetch_snowflake_monthly_gts(ship_rules, base_year, plan_year)

    parent_driver_names = [
        DRIVER_BASE_TREND, "Season", "Competition", "Distribution", DRIVER_NET_INNOVATION,
        "Discontinuations", "Renovation", "Media", "Trade", DRIVER_NET_PRICE,
        "Club", DRIVER_OTHER
    ]

    total_monthly_bb, _ = _sum_monthly_building_blocks(drivers, parent_driver_names)
    gts_plan = _calc_gts_yoy_plan_gts(gts_base, gts_plan_actual, factory_pos, total_monthly_bb, cutoff_month)

    growth_pct = _calc_gts_growth_pct(gts_plan, gts_base)

    totals_base = calc_totals(gts_base, cutoff_month)
    totals_plan = calc_totals(gts_plan, cutoff_month)
    totals_growth = _calc_gts_growth_totals(totals_plan, totals_base)

    driver_totals = {
        disp_name: calc_totals(drivers.get(disp_name, [None] * 12), cutoff_month)
        for _, disp_name, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS
    }

    return {
        "base_year": base_year, "plan_year": plan_year,
        "label_base": str(base_year), "label_plan": str(plan_year),
        "cutoff_month": cutoff_month, "models": model_list,
        "gts_base": gts_base, "totals_base": totals_base,
        "gts_plan_actual": gts_plan_actual,
        "factory_pos": factory_pos,
        "drivers": drivers, "driver_totals": driver_totals,
        "gts_plan": gts_plan, "totals_plan": totals_plan,
        "growth_pct": growth_pct, "totals_growth": totals_growth,
    }


# ─── 4. GTS Change of Cycle (CoC) Calculation Engine ─────────────────────────

def compute_gtscoc_summary_matrix(models: str | list[str]) -> Dict[str, Any]:
    """
    Computes complete GTS Change of Cycle (CoC) Matrix:
    1. Top Row: Base Year (dashes -)
    2. Driver Rows: (Current Cycle POS - Prior Cycle POS) * Price Factor
    3. Bottom Row: Plan Year (Sum of all active Building Blocks)
    """
    base_year, plan_year = get_active_years()
    model_list = _normalize_models(models)
    rules = load_shipment_model_rules(model_list)
    gts_base, _ = fetch_snowflake_monthly_gts(rules, base_year)

    snap_info = get_cycle_snapshot_ids(plan_year)
    cutoff_month = _resolve_coc_cutoff_month(snap_info.active_cycle_month)

    price_factors = load_price_index_from_postgres(model_list)
    drivers = load_coc_building_blocks(model_list, plan_year, price_factors)

    parent_driver_names = [
        DRIVER_BASE_TREND, "Season", "Competition", "Distribution", DRIVER_NET_INNOVATION,
        "Discontinuations", "Renovation", "Media", "Trade", DRIVER_NET_PRICE,
        "Club", DRIVER_OTHER
    ]

    total_monthly_coc, has_coc_for_month = _sum_monthly_building_blocks(drivers, parent_driver_names)

    gts_plan = [
        round(total_monthly_coc[i], 4) if has_coc_for_month[i] else None
        for i in range(12)
    ]

    totals_base = calc_totals(gts_base, cutoff_month)
    totals_plan = calc_totals(gts_plan, cutoff_month)

    driver_totals = {
        disp_name: calc_totals(drivers.get(disp_name, [None] * 12), cutoff_month)
        for _, disp_name, _ in GTS_COC_DRIVER_DEFINITIONS
    }

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "cutoff_month": cutoff_month,
        "models": model_list,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_plan": gts_plan,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
    }
