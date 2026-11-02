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


# ─── Helper: Quarter & Period Aggregations ────────────────────────────────────

def calc_totals(
    monthly_vals: List[Optional[float]], cutoff_month: int = 0
) -> Dict[str, Optional[float]]:
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
        "YTD": _sum_range(0, safe_cutoff),
        "YTG": _sum_range(safe_cutoff, 12),
    }


# ─── Calculation Helpers ─────────────────────────────────────────────────────

def _ensure_compound_drivers(drivers: dict) -> None:
    """Computes compound Net Innovation and Net Price rows if not present."""
    if DRIVER_NET_INNOVATION not in drivers:
        inno = drivers.get("Innovation", [None] * 12)
        cann = drivers.get("Cannibalization", [None] * 12)
        res = [None] * 12
        for i in range(12):
            if inno[i] is not None or cann[i] is not None:
                res[i] = (inno[i] or 0.0) + (cann[i] or 0.0)
        drivers[DRIVER_NET_INNOVATION] = res

    if DRIVER_NET_PRICE not in drivers:
        price = drivers.get("Price", [None] * 12)
        elast = drivers.get("Elasticity", [None] * 12)
        res = [None] * 12
        for i in range(12):
            if price[i] is not None or elast[i] is not None:
                res[i] = (price[i] or 0.0) + (elast[i] or 0.0)
        drivers[DRIVER_NET_PRICE] = res


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
        month_num = i + 1
        if month_num <= cutoff_month and pos_plan_actual[i] is not None:
            actual_val = pos_plan_actual[i]
            calc_val = bb_calculated_pos[i]
            if actual_val is not None and calc_val is not None:
                diff_val[i] = actual_val - calc_val
            elif actual_val is not None and pos_base[i] is not None:
                diff_val[i] = actual_val - pos_base[i]
        else:
            diff_val[i] = None
    return diff_val


def _calc_bb_calculated_pos(
    pos_base: list, total_monthly_bb: list, has_bb_for_month: list
) -> list[Optional[float]]:
    """Calculates Base POS + Building Blocks series."""
    bb_calc: list[Optional[float]] = [None] * 12
    for i in range(12):
        base_val = pos_base[i]
        bb_val = total_monthly_bb[i] if has_bb_for_month[i] else 0.0
        if base_val is not None:
            bb_calc[i] = base_val + bb_val
        elif has_bb_for_month[i]:
            bb_calc[i] = bb_val
    return bb_calc


def _calc_consumption_plan_pos(
    pos_plan_actual: list, bb_calculated_pos: list, cutoff_month: int
) -> list[Optional[float]]:
    """Determines Plan POS using Actuals up to cutoff and Base+BB beyond cutoff."""
    plan = [None] * 12
    for i in range(12):
        if (i + 1) <= cutoff_month and pos_plan_actual[i] is not None:
            plan[i] = pos_plan_actual[i]
        else:
            plan[i] = bb_calculated_pos[i]
    return plan


def _calc_yoy_pct_series(
    plan_vals: list, base_vals: list
) -> list[Optional[float]]:
    """Calculates percentage YoY change across 12 monthly periods."""
    yoy_pct: list[Optional[float]] = [None] * 12
    for i in range(12):
        v_b = base_vals[i]
        v_p = plan_vals[i]
        if v_b is not None and v_p is not None and v_b != 0:
            yoy_pct[i] = ((v_p - v_b) / abs(v_b)) * 100.0
        else:
            yoy_pct[i] = None
    return yoy_pct


def _calc_totals_yoy_dict(totals_plan: dict, totals_base: dict) -> dict[str, Optional[float]]:
    """Calculates period totals YoY percentage against base year totals."""
    totals_yoy = {}
    for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        v_b = totals_base.get(col)
        v_p = totals_plan.get(col)
        if v_b is not None and v_p is not None and v_b != 0:
            totals_yoy[col] = ((v_p - v_b) / abs(v_b)) * 100.0
        else:
            totals_yoy[col] = None
    return totals_yoy


def _calc_diff_period_totals(diff_val: list, cutoff_month: int) -> dict[str, Optional[float]]:
    """Calculates quarterly and period totals for Difference row."""
    def _sum_diff_slice(st: int, en: int) -> Optional[float]:
        valid = [d for d in diff_val[st:en] if d is not None]
        return sum(valid) if valid else None

    safe_c = cutoff_month
    return {
        "Q1": _sum_diff_slice(0, 3),
        "Q2": _sum_diff_slice(3, 6),
        "Q3": _sum_diff_slice(6, 9),
        "Q4": _sum_diff_slice(9, 12),
        "FY": _sum_diff_slice(0, 12),
        "YTD": _sum_diff_slice(0, safe_c),
        "YTG": _sum_diff_slice(safe_c, 12),
    }


def _detect_cutoff_month(gts_plan_actual: list, cons_cutoff: int = 0) -> int:
    """Detects active cutoff month from complete actuals, enforcing consecutive closed months."""
    detected = 0
    for idx, v in enumerate(gts_plan_actual):
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            detected = idx + 1
        else:
            break
    if detected > 0:
        return detected
    if cons_cutoff > 0:
        return cons_cutoff
    return 0


def _compute_factory_pos(pos_plan: list, price_indices: dict) -> list:
    """Computes Factory POS = POS Plan * Price Index multiplier."""
    factory_pos = [0.0] * 12
    for i in range(12):
        month_num = i + 1
        pos_val = float(pos_plan[i] or 0.0)
        idx_mult = price_indices.get(month_num, 1.0)
        factory_pos[i] = round(pos_val * idx_mult, 2)
    return factory_pos


def _scale_consumption_drivers_by_price_index(raw_cons_drivers: dict, price_indices: dict) -> dict:
    """Scales consumption drivers by price index to generate GTS YoY drivers."""
    drivers: Dict[str, List[Optional[float]]] = {}
    for _, disp_name, match_key in CONSUMPTION_DRIVER_ROW_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        c_vals = raw_cons_drivers.get(disp_name, [None] * 12)
        g_vals = [None] * 12
        has_any = False
        for i in range(12):
            v = c_vals[i]
            if v is not None:
                pi = price_indices.get(i + 1, 1.0)
                g_vals[i] = round(v * pi, 4)
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
        target_date = datetime.date.today() + datetime.timedelta(days=1) if datetime.date.today().weekday() == 6 else datetime.date.today()
        info = KenvueCalendar.get_date_info(target_date)
        return int(info.get("fiscal_month") or info.get("kv_month_num") or 1)
    except Exception:
        return datetime.date.today().month


# ─── 1. Consumption Summary Calculation Engine ───────────────────────────────

def compute_consumption_summary_matrix(models: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Computes complete Consumption Summary Matrix:
    1. Base Year POS $ from Snowflake
    2. Live PostgreSQL Building Blocks aggregated across selected models
    3. Plan Year POS $ (Actuals up to cutoff; Base + BB beyond)
    4. YoY % Growth
    5. Closed-Month Variance ("Difference")
    """
    base_year, plan_year = get_active_years()
    rules = load_consumption_model_rules(models)
    pos_base, pos_plan_actual = fetch_snowflake_monthly_pos(rules, base_year, plan_year)

    drivers = load_live_consumption_building_blocks(models, plan_year)

    _ensure_compound_drivers(drivers)
    total_monthly_bb, has_bb_for_month = _sum_monthly_building_blocks(drivers, INDIVIDUAL_DRIVER_NAMES)
    bb_calculated_pos = _calc_bb_calculated_pos(pos_base, total_monthly_bb, has_bb_for_month)

    cutoff_month = _detect_cutoff_month(pos_plan_actual, 0)
    pos_plan = _calc_consumption_plan_pos(pos_plan_actual, bb_calculated_pos, cutoff_month)
    yoy_pct = _calc_yoy_pct_series(pos_plan, pos_base)

    diff_val = _calc_consumption_diff(pos_plan_actual, bb_calculated_pos, pos_base, cutoff_month)
    totals_base = calc_totals(pos_base, cutoff_month)
    totals_plan = calc_totals(pos_plan, cutoff_month)

    driver_totals = {
        disp_name: calc_totals(drivers.get(disp_name, [None] * 12), cutoff_month)
        for _, disp_name, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS
    }

    totals_yoy = _calc_totals_yoy_dict(totals_plan, totals_base)
    totals_diff = _calc_diff_period_totals(diff_val, cutoff_month)

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "label_base": f"{base_year} POS $",
        "label_plan": f"{plan_year} POS $",
        "cutoff_month": cutoff_month,
        "models": models,
        "pos_base": pos_base,
        "totals_base": totals_base,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "pos_plan": pos_plan,
        "totals_plan": totals_plan,
        "yoy_pct": yoy_pct,
        "totals_yoy": totals_yoy,
        "difference": diff_val,
        "totals_diff": totals_diff,
        "pos_plan_actual": pos_plan_actual,
        "bb_calculated_pos": bb_calculated_pos,
    }


# ─── Shipment Summary Helpers ────────────────────────────────────────────────

def _resolve_consumption_context(
    models: str | list[str], cons_data: Optional[Dict[str, Any]]
) -> tuple[Dict[str, Any], list, int]:
    """Ensures consumption matrix data is available for downstream shipment calculations."""
    if not cons_data:
        try:
            cons_data = compute_consumption_summary_matrix(models)
        except Exception as e:
            logger.warning("Could not compute consumption matrix context: %s", e)
            cons_data = {}
    pos_plan = cons_data.get("pos_plan", [0.0] * 12) if cons_data else [0.0] * 12
    cons_cutoff = int(cons_data.get("cutoff_month") or 0) if cons_data else 0
    return cons_data, pos_plan, cons_cutoff


def _sum_shipment_building_blocks(drivers: dict) -> list[float]:
    """Sums monthly values across all defined shipment building blocks."""
    total_bb = [0.0] * 12
    for grp, disp_name, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        d_vals = drivers.get((grp, disp_name)) or drivers.get(disp_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                total_bb[i] += d_vals[i]
    return total_bb


def _calc_shipment_plan_gts(
    cutoff_month: int,
    gts_plan_actual: list,
    factory_pos: list,
    total_shipment_bb: list,
) -> list[float]:
    """Calculates Plan GTS for shipment grid based on cutoff month."""
    gts_plan = [0.0] * 12
    for i in range(12):
        if i < cutoff_month and gts_plan_actual[i] is not None:
            gts_plan[i] = round(gts_plan_actual[i], 2)
        else:
            fp = factory_pos[i] or 0.0
            bb = total_shipment_bb[i] or 0.0
            gts_plan[i] = round(fp + bb, 2)
    return gts_plan


def _calc_gts_growth_pct(
    gts_plan: list, gts_base: list
) -> list[float]:
    """Calculates GTS YoY growth percentages across 12 monthly periods."""
    gts_yoy_pct = [0.0] * 12
    for i in range(12):
        b_val = gts_base[i]
        p_val = gts_plan[i]
        if b_val and b_val > 0 and p_val is not None:
            gts_yoy_pct[i] = ((p_val - b_val) / b_val) * 100.0
        else:
            gts_yoy_pct[i] = 0.0
    return gts_yoy_pct


def _calc_gts_growth_totals(
    totals_gts: dict, totals_base: dict
) -> dict[str, float]:
    """Calculates GTS YoY growth percentages for quarterly and summary totals."""
    totals_yoy = {}
    for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        b_tot = totals_base.get(col) or 0.0
        p_tot = totals_gts.get(col) or 0.0
        if b_tot > 0 and p_tot is not None:
            totals_yoy[col] = ((p_tot - b_tot) / b_tot) * 100.0
        else:
            totals_yoy[col] = 0.0
    return totals_yoy


def _calc_shipment_driver_totals(drivers: dict, cutoff_month: int) -> dict:
    """Calculates period totals for shipment drivers mapped by composite and plain keys."""
    driver_totals = {}
    for grp, disp_name, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        vals = drivers.get((grp, disp_name)) or drivers.get(disp_name, [None] * 12)
        tot = calc_totals(vals, cutoff_month)
        driver_totals[disp_name] = tot
        driver_totals[(grp, disp_name)] = tot
        driver_totals[f"{grp}_{disp_name}"] = tot
    return driver_totals


def _calc_gts_yoy_plan_gts(
    cutoff_month: int,
    gts_plan_actual: list,
    gts_base: list,
    factory_pos: list,
    total_monthly_bb: list,
    has_bb_for_month: list,
) -> list[float]:
    """Calculates Plan GTS for GTS YoY grid using actuals up to cutoff and Baseline+BB beyond."""
    gts_plan = [0.0] * 12
    for i in range(12):
        if i < cutoff_month and gts_plan_actual[i] is not None:
            gts_plan[i] = round(gts_plan_actual[i], 2)
        else:
            baseline = gts_base[i] if gts_base[i] is not None else factory_pos[i]
            bb = total_monthly_bb[i] if has_bb_for_month[i] else 0.0
            gts_plan[i] = round((baseline or 0.0) + bb, 2)
    return gts_plan


# ─── 2. Shipment Summary Calculation Engine ──────────────────────────────────

def compute_shipment_summary_matrix(
    models: str | list[str], cons_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes complete Shipment Summary Matrix:
    1. Factory POS = POS Plan $ (from consumption) * Price Index (from PostgreSQL)
    2. Category 1: Inventory Drivers (Distribution, Innovation, Trade, Club, Retailer Inv, Other)
    3. Category 2: IBP Overlays (Supply Constraints, Liquidations, Other)
    4. Plan Year GTS $ (Actuals up to cutoff; Factory POS + BB beyond)
    5. GTS YoY %
    """
    base_year, plan_year = get_active_years()
    rules = load_shipment_model_rules(models)
    gts_base, gts_plan_actual = fetch_snowflake_monthly_gts(rules, base_year, plan_year)

    cons_data, pos_plan, cons_cutoff = _resolve_consumption_context(models, cons_data)

    price_indices = load_price_index_from_postgres(models)
    drivers = load_live_shipment_building_blocks(models, plan_year)

    factory_pos = _compute_factory_pos(pos_plan, price_indices)
    total_shipment_bb = _sum_shipment_building_blocks(drivers)

    cutoff_month = _detect_cutoff_month(gts_plan_actual, cons_cutoff)
    gts_plan = _calc_shipment_plan_gts(cutoff_month, gts_plan_actual, factory_pos, total_shipment_bb)
    gts_yoy_pct = _calc_gts_growth_pct(gts_plan, gts_base)

    totals_factory_pos = calc_totals(factory_pos, cutoff_month)
    totals_gts = calc_totals(gts_plan, cutoff_month)
    totals_base = calc_totals(gts_base, cutoff_month)
    totals_yoy = _calc_gts_growth_totals(totals_gts, totals_base)
    driver_totals = _calc_shipment_driver_totals(drivers, cutoff_month)

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "cutoff_month": cutoff_month,
        "label_base": f"{base_year} GTS",
        "label_factory_pos": f"{plan_year} FACTORY POS",
        "label_gts": f"{plan_year} GTS",
        "models": models,
        "factory_pos": factory_pos,
        "totals_factory_pos": totals_factory_pos,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "gts_plan": gts_plan,
        "totals_gts": totals_gts,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_yoy_pct": gts_yoy_pct,
        "totals_yoy": totals_yoy,
        "gts_plan_actual": gts_plan_actual,
    }


# ─── 3. GTS YoY Summary Calculation Engine ────────────────────────────────────

def compute_gts_summary_matrix(
    models: str | list[str], cons_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes complete GTS YoY Summary Matrix:
    1. Historical Base Year GTS $ from Snowflake
    2. All 14 Consumption Building Blocks scaled by Monthly Price Index
    3. Plan Year GTS $ (Actuals up to cutoff; Baseline + BB beyond)
    4. GTS YoY %
    """
    base_year, plan_year = get_active_years()
    rules = load_shipment_model_rules(models)
    gts_base, gts_plan_actual = fetch_snowflake_monthly_gts(rules, base_year, plan_year)

    cons_data, pos_plan, cons_cutoff = _resolve_consumption_context(models, cons_data)

    price_indices = load_price_index_from_postgres(models)
    factory_pos = _compute_factory_pos(pos_plan, price_indices)

    raw_cons_drivers = cons_data.get("drivers", {}) if cons_data else load_live_consumption_building_blocks(models, plan_year)
    drivers = _scale_consumption_drivers_by_price_index(raw_cons_drivers, price_indices)

    total_monthly_bb, has_bb_for_month = _sum_monthly_building_blocks(drivers, INDIVIDUAL_DRIVER_NAMES)
    cutoff_month = _detect_cutoff_month(gts_plan_actual, cons_cutoff)

    gts_plan = _calc_gts_yoy_plan_gts(
        cutoff_month, gts_plan_actual, gts_base, factory_pos, total_monthly_bb, has_bb_for_month
    )
    gts_yoy_pct = _calc_gts_growth_pct(gts_plan, gts_base)

    totals_base = calc_totals(gts_base, cutoff_month)
    totals_plan = calc_totals(gts_plan, cutoff_month)
    totals_factory_pos = calc_totals(factory_pos, cutoff_month)
    totals_yoy = _calc_gts_growth_totals(totals_plan, totals_base)

    driver_totals = {
        disp_name: calc_totals(drivers.get(disp_name, [None] * 12), cutoff_month)
        for _, disp_name, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS
    }

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "cutoff_month": cutoff_month,
        "label_base": f"{base_year} GTS $",
        "label_plan": f"{plan_year} GTS $",
        "models": models,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_plan": gts_plan,
        "totals_plan": totals_plan,
        "factory_pos": factory_pos,
        "totals_factory_pos": totals_factory_pos,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "gts_yoy_pct": gts_yoy_pct,
        "totals_yoy": totals_yoy,
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
    rules = load_shipment_model_rules(models)
    gts_base, _ = fetch_snowflake_monthly_gts(rules, base_year)

    snap_info = get_cycle_snapshot_ids(plan_year)
    cutoff_month = _resolve_coc_cutoff_month(snap_info.active_cycle_month)

    price_factors = load_price_index_from_postgres(models)
    drivers = load_coc_building_blocks(models, plan_year, price_factors)

    # Any active driver with data fills remaining months with 0.0
    for d_name, d_vals in list(drivers.items()):
        if any(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in d_vals):
            drivers[d_name] = [0.0 if (v is None or (isinstance(v, float) and math.isnan(v))) else v for v in d_vals]

    parent_driver_names = [
        DRIVER_BASE_TREND, "Season", "Competition", "Distribution", DRIVER_NET_INNOVATION,
        "Discontinuations", "Renovation", "Media", "Trade", DRIVER_NET_PRICE,
        "Club", DRIVER_OTHER
    ]

    total_monthly_coc, has_coc_for_month = _sum_monthly_building_blocks(drivers, parent_driver_names)

    has_any_coc = any(has_coc_for_month)
    gts_plan = [
        round(total_monthly_coc[i], 4) if (has_coc_for_month[i] or has_any_coc) else None
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
        "models": models,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_plan": gts_plan,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
    }
