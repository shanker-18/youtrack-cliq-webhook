# pylint: disable=too-many-lines,too-many-locals,too-many-branches,broad-except
"""
NA IBP Planning Application — Summary Dashboard Data Service
============================================================
Handles PostgreSQL connectivity (via ThreadedConnectionPool / get_db_cursor)
and Snowflake connectivity (via RSA Private Key authentication) for all
Summary Dashboards: Consumption Summary, Shipment Summary, GTS YoY, and GTS CoC.

Features:
- Pure Python implementation (zero pandas dependency)
- 100% Dynamic years and months using services.kv_calendar.KenvueCalendar
- Parameterized queries supporting single or multi-model selections
- Dynamic completeness validation for Snowflake actuals
- Snapshots and cycle discovery for GTS Change of Cycle (CoC)
"""

import os
import re
import datetime
from typing import Optional, Dict, List, Tuple, Any, NamedTuple
import psycopg2

from config import config
from database.connection import get_db_cursor
from services.kv_calendar import KenvueCalendar
from services.validation_service import (
    get_snowflake_connection,
    normalize_text,
    is_token_expired_error,
)
from utils.logger import get_logger

logger = get_logger(__name__)

MONTH_NAME_MAP = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12
}


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

# ─── Constant Definitions ─────────────────────────────────────────────────────

MATCH_KEY_BASE_TREND = "BASE TREND"
DRIVER_NET_INNOVATION = "Net Innovation"
DRIVER_NET_PRICE = "Net Price"
GROUP_IBP_OVERLAYS = "IBP Overlays"

# ─── Driver Definitions ───────────────────────────────────────────────────────

# Consumption & GTS YoY Driver Definitions: (Category Group, Display Name, DB Match Key)
CONSUMPTION_DRIVER_ROW_DEFINITIONS = [
    ("External",     "Base Trend",          MATCH_KEY_BASE_TREND),
    ("External",     "Season",              "SEASON"),
    ("External",     "Competition",         "COMPETITION"),
    ("Distribution", "Distribution",        "DISTRIBUTION"),
    ("Innovation",   DRIVER_NET_INNOVATION, "COMPOUND_NET_INNOVATION"),  # Innovation + Cannibalization
    ("Innovation",   "Innovation",          "INNOVATION"),
    ("Innovation",   "Cannibalization",     "CANNIBALIZATION"),
    ("Innovation",   "Discontinuations",    "DISCONTINUATIONS"),
    ("Innovation",   "Renovation",          "RENOVATION"),
    ("Investment",   "Media",               "MEDIA"),
    ("Investment",   "Trade",               "TRADE"),
    ("Price",        DRIVER_NET_PRICE,      "COMPOUND_NET_PRICE"),       # Price + Elasticity
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Other",        "Club",                "CLUB"),
    ("Other",        "Other",               "OTHER"),
]

# Shipment Driver Definitions: (Category Group, Display Name, DB Match Key)
SHIPMENT_DRIVER_ROW_DEFINITIONS = [
    ("Inventory",         "Distribution",       "DISTRIBUTION"),
    ("Inventory",         "Innovation",         "INNOVATION"),
    ("Inventory",         "Trade",              "TRADE"),
    ("Inventory",         "Club",               "CLUB"),
    ("Inventory",         "Retailer Inventory", "RETAILER_INVENTORY"),
    ("Inventory",         "Other",              "OTHER"),
    (GROUP_IBP_OVERLAYS,  "Supply Constraints", "SUPPLY_CONSTRAINTS"),
    (GROUP_IBP_OVERLAYS,  "Liquidations",       "LIQUIDATIONS"),
    (GROUP_IBP_OVERLAYS,  "Other",              "OVERLAYS_OTHER"),
]

# GTS CoC Driver Definitions: (Category Group, Display Name, DB Match Key)
GTS_COC_DRIVER_DEFINITIONS = [
    ("External",     "Base Trend",          MATCH_KEY_BASE_TREND),
    ("External",     "Season",              "SEASON"),
    ("External",     "Competition",         "COMPETITION"),
    ("Distribution", "Distribution",        "DISTRIBUTION"),
    ("Innovation",   DRIVER_NET_INNOVATION, "COMPOUND_NET_INNOVATION"),
    ("Innovation",   "Innovation",          "INNOVATION"),
    ("Innovation",   "Cannibalization",     "CANNIBALIZATION"),
    ("Innovation",   "Discontinuations",    "DISCONTINUATIONS"),
    ("Innovation",   "Renovation",          "RENOVATION"),
    ("Investment",   "Media",               "MEDIA"),
    ("Investment",   "Trade",               "TRADE"),
    ("Price",        DRIVER_NET_PRICE,      "COMPOUND_NET_PRICE"),
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Other",        "Club",                "CLUB"),
    ("Other",        "Other",               "OTHER"),
]


# ─── 1. Dynamic Fiscal Year & Month Parsing ───────────────────────────────────

def get_active_years() -> tuple[int, int]:
    """
    Dynamically determines (base_year, plan_year) using Kenvue 4-4-5 Fiscal Calendar.
    - If IBP_PLAN_YEAR is set in environment, uses that override.
    - Otherwise, derives active plan_year safely from KenvueCalendar.get_date_info.
    base_year is always plan_year - 1.
    """
    env_year = os.getenv("IBP_PLAN_YEAR")
    if env_year and env_year.isdigit():
        plan_year = int(env_year)
    else:
        target_date = datetime.date.today() + datetime.timedelta(days=1)
        plan_year = target_date.year
        try:
            today_info = KenvueCalendar.get_date_info(target_date)
            if isinstance(today_info, dict):
                plan_year = int(today_info.get("fiscal_year") or today_info.get("kv_year") or target_date.year)
            elif hasattr(today_info, "fiscal_year"):
                plan_year = int(today_info.fiscal_year)
            elif hasattr(today_info, "kv_year"):
                plan_year = int(today_info.kv_year)
        except Exception:
            try:
                today_info = KenvueCalendar.get_date_info(target_date.strftime("%Y-%m-%d"))
                if isinstance(today_info, dict):
                    plan_year = int(today_info.get("fiscal_year") or today_info.get("kv_year") or target_date.year)
            except Exception:
                plan_year = target_date.year
    base_year = plan_year - 1
    return base_year, plan_year


def parse_month_num(val: Any) -> Optional[int]:
    """Converts month representation (e.g. 1, '1', 'JAN', 'JANUARY') to an int 1..12."""
    if val is None:
        return None
    if isinstance(val, int):
        return val if 1 <= val <= 12 else None
    s = str(val).strip()
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 12 else None
    up = s.upper()
    return MONTH_NAME_MAP.get(up)


# ─── 2. Hierarchy Discovery & Model Rule Lookups ──────────────────────────────

def get_available_squads_and_models() -> dict[str, list[str]]:
    """
    Retrieves all active Squads and their associated Models from consumption_hierarchy_mapping.
    Returns: mapping of squad_name -> list of model_names.
    """
    sql = """
    SELECT DISTINCT
        COALESCE(chm.need_state, 'UNKNOWN') AS squad,
        mm.model_name
    FROM public.consumption_hierarchy_mapping chm
    INNER JOIN public.master_models mm ON chm.model_id = mm.model_id
    WHERE chm.is_active = TRUE AND mm.is_active = TRUE
    ORDER BY squad, mm.model_name;
    """
    squad_map: dict[str, list[str]] = {}
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            for r in rows:
                squad = str(r.get("squad") or "").strip().upper()
                m_name = str(r.get("model_name") or "").strip()
                if squad and squad not in ["ALL", "NONE", "UNKNOWN"] and m_name:
                    squad_map.setdefault(squad, [])
                    if m_name not in squad_map[squad]:
                        squad_map[squad].append(m_name)
    except Exception as e:
        logger.error("Failed to load squads and models: %s", e)

    for models_list in squad_map.values():
        models_list.sort()
    return squad_map


def load_consumption_model_rules(models: str | list[str]) -> list[dict[str, str]]:
    """Loads Circana POS product hierarchy rules (C1..C5, B1..B2) for selected model(s)."""
    model_list = _normalize_models(models)
    if not model_list:
        return []

    sql = """
    SELECT
        chm.brand_name,
        chm.sub_brand_name,
        chm.category,
        chm.subcategory
    FROM public.consumption_hierarchy_mapping chm
    INNER JOIN public.master_models mm ON chm.model_id = mm.model_id
    WHERE mm.model_name = ANY(%s) AND chm.is_active = TRUE;
    """
    rules = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list,))
            for r in cur.fetchall():
                rules.append({
                    "brand": normalize_text(r.get("brand_name")),
                    "sub_brand": normalize_text(r.get("sub_brand_name")),
                    "category": normalize_text(r.get("category")),
                    "subcategory": normalize_text(r.get("subcategory")),
                })
    except Exception as e:
        logger.error("Failed to load consumption model rules: %s", e)
    return rules


def load_shipment_model_rules(models: str | list[str]) -> list[dict[str, str]]:
    """Loads SAP F360 shipment 7-dimension hierarchy rules for selected model(s)."""
    model_list = _normalize_models(models)
    if not model_list:
        return []

    sql = """
    SELECT
        shm.business_segment,
        shm.business_subsegment,
        shm.need_state,
        shm.category,
        shm.subcategory,
        shm.brand,
        shm.sub_brand
    FROM public.shipment_hierarchy_mapping shm
    INNER JOIN public.master_models mm ON shm.model_id = mm.model_id
    WHERE mm.model_name = ANY(%s) AND shm.is_active = TRUE;
    """
    rules = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list,))
            for r in cur.fetchall():
                rules.append({
                    "c1": normalize_text(r.get("business_segment")),
                    "c2": normalize_text(r.get("business_subsegment")),
                    "c3": normalize_text(r.get("need_state")),
                    "c4": normalize_text(r.get("category")),
                    "c5": normalize_text(r.get("subcategory")),
                    "b1": normalize_text(r.get("brand")),
                    "b2": normalize_text(r.get("sub_brand")),
                })
    except Exception as e:
        logger.error("Failed to load shipment model rules: %s", e)
    return rules


# ─── 3. PostgreSQL Price Index & Multipliers ─────────────────────────────────

def _parse_price_index_rows(rows: list[dict[str, Any]]) -> dict[int, float]:
    """Aggregates and averages monthly price index multipliers from query rows."""
    monthly_indices: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for r in rows:
        m_num = int(r["month_num"])
        raw_idx = r["price_index"]
        if 1 <= m_num <= 12 and raw_idx is not None:
            try:
                val = float(raw_idx)
                if val > 0:
                    monthly_indices[m_num].append(val)
            except (ValueError, TypeError):
                pass

    final_indices = {}
    for m in range(1, 13):
        arr = monthly_indices[m]
        final_indices[m] = (sum(arr) / len(arr)) if arr else 1.0
    return final_indices


def load_price_index_from_postgres(
    models: str | list[str]
) -> dict[int, float]:
    """
    Queries public.model_price_index in PostgreSQL for selected model(s).
    Returns mapping: month_num (1..12) -> multiplier (float).
    """
    model_list = _normalize_models(models)
    if not model_list:
        return dict.fromkeys(range(1, 13), 1.0)

    sql = """
    SELECT
        mpi.month_num,
        mpi.price_index
    FROM public.model_price_index mpi
    INNER JOIN public.master_models mm ON mpi.model_id = mm.model_id
    WHERE mm.model_name = ANY(%s) AND mpi.is_active = TRUE;
    """
    rows = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list,))
            rows = cur.fetchall()
    except Exception as e:
        logger.warning("Notice querying model_price_index: %s", e)

    return _parse_price_index_rows(rows)


# ─── 4. PostgreSQL Live Building Blocks ──────────────────────────────────────

def _accumulate_consumption_bb_rows(rows: list[dict[str, Any]]) -> dict[str, list[Optional[float]]]:
    """Accumulates monthly planning values in millions for consumption building blocks."""
    raw_bb: dict[str, list[Optional[float]]] = {}
    for r in rows:
        norm_name = normalize_text(r["building_block"])
        m_num = int(r["month_num"])
        val_m = float(r["value_in_thousands"] or 0.0) / 1000.0  # $K to $M
        if norm_name not in raw_bb:
            raw_bb[norm_name] = [None] * 12
        cur_v = raw_bb[norm_name][m_num - 1]
        raw_bb[norm_name][m_num - 1] = (cur_v or 0.0) + val_m
    return raw_bb


def _extract_consumption_driver_val(
    raw_bb: dict[str, list[Optional[float]]], pattern: str
) -> list[Optional[float]]:
    """Sums monthly building block values matching the given driver pattern."""
    res: list[Optional[float]] = [None] * 12
    for db_name, m_arr in raw_bb.items():
        if pattern in db_name:
            for i in range(12):
                if m_arr[i] is not None:
                    res[i] = (res[i] or 0.0) + m_arr[i]
    return res


def _combine_monthly_drivers(
    a: list[Optional[float]], b: list[Optional[float]]
) -> list[Optional[float]]:
    """Adds two 12-month driver series together preserving None semantics."""
    res: list[Optional[float]] = [None] * 12
    for i in range(12):
        if a[i] is not None or b[i] is not None:
            res[i] = (a[i] or 0.0) + (b[i] or 0.0)
    return res


def load_live_consumption_building_blocks(
    models: str | list[str], plan_year: int
) -> dict[str, list[Optional[float]]]:
    """
    Loads Consumption Building Blocks aggregated across one or multiple models for plan_year.
    Returns: Display Name -> [12 monthly values in Millions ($M)]
    """
    model_list = _normalize_models(models)

    if not model_list:
        return {disp: [None] * 12 for _, disp, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS}

    sql = """
    SELECT
        cbb.name AS building_block,
        EXTRACT(MONTH FROM cpv.period_month)::int AS month_num,
        SUM(cpv.value_in_thousands) AS value_in_thousands
    FROM public.consumption_planning_rows cpr
    INNER JOIN public.consumption_building_blocks cbb
        ON cpr.building_block_id = cbb.block_id
    INNER JOIN public.consumption_planning_values cpv
        ON cpr.row_id = cpv.row_id
    INNER JOIN public.master_models mm
        ON cpr.model_id = mm.model_id
    WHERE
        mm.model_name = ANY(%s)
        AND cpr.is_deleted = FALSE
        AND cbb.is_active = TRUE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM cpv.period_month) = %s
    GROUP BY cbb.name, month_num
    ORDER BY cbb.name, month_num;
    """
    rows = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, plan_year))
            rows = cur.fetchall()
    except Exception as e:
        logger.error("Failed to load consumption building blocks: %s", e)

    raw_bb = _accumulate_consumption_bb_rows(rows)

    driver_data: dict[str, list[Optional[float]]] = {}
    for _, disp_name, match_key in CONSUMPTION_DRIVER_ROW_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        driver_data[disp_name] = _extract_consumption_driver_val(raw_bb, match_key)

    driver_data[DRIVER_NET_INNOVATION] = _combine_monthly_drivers(
        driver_data.get("Innovation", [None] * 12),
        driver_data.get("Cannibalization", [None] * 12),
    )
    driver_data[DRIVER_NET_PRICE] = _combine_monthly_drivers(
        driver_data.get("Price", [None] * 12),
        driver_data.get("Elasticity", [None] * 12),
    )

    return driver_data


def _build_shipment_bb_sql(model_list: list[str], plan_year: int) -> tuple[str, tuple]:
    """Builds parameterized SQL query for loading shipment building blocks."""
    sql = """
    SELECT
        sbb.name AS driver_building_block,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 1  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS jan_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 2  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS feb_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 3  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS mar_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 4  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS apr_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 5  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS may_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 6  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS jun_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 7  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS jul_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 8  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS aug_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 9  THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS sep_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 10 THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS oct_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 11 THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS nov_m,
        ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 12 THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS dec_m
    FROM public.shipment_planning_rows spr
    INNER JOIN public.shipment_building_blocks sbb
        ON spr.building_block_id = sbb.block_id
    INNER JOIN public.shipment_planning_values spv
        ON spr.row_id = spv.row_id
    INNER JOIN public.master_models mm
        ON spr.model_id = mm.model_id
    WHERE
        mm.model_name = ANY(%s)
        AND spr.is_deleted = FALSE
        AND sbb.is_active = TRUE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM spv.period_month) = %s
    GROUP BY sbb.name
    ORDER BY sbb.name;
    """
    return sql, (model_list, plan_year)


def _accumulate_shipment_driver(
    rows: list[dict[str, Any]], month_cols: list[str], grp: str, disp_name: str, match_key: str
) -> list[Optional[float]]:
    """Sums monthly shipment values for building blocks matching the driver match key."""
    monthly_vals = [0.0] * 12
    has_data = False
    for r in rows:
        db_name = normalize_text(r.get("driver_building_block"))
        is_match = False
        if grp == GROUP_IBP_OVERLAYS and match_key == "OVERLAYS_OTHER":
            is_match = ("OVERLAYS" in db_name and "OTHER" in db_name) or ("IBP" in db_name and "OTHER" in db_name)
        elif grp == "Inventory" and match_key == "OTHER":
            is_match = "OTHER" in db_name and "IBP" not in db_name and "OVERLAY" not in db_name
        else:
            is_match = match_key in db_name

        if is_match:
            has_data = True
            for m_idx, col in enumerate(month_cols):
                val = float(r.get(col) or 0.0)
                monthly_vals[m_idx] += val

    return [round(v, 4) for v in monthly_vals] if has_data else [None] * 12


def load_live_shipment_building_blocks(
    models: str | list[str], plan_year: int
) -> dict[Any, list[Optional[float]]]:
    """Loads Shipment Building Blocks (Inventory & Overlays) in Millions ($M)."""
    model_list = _normalize_models(models)

    empty_res: dict[Any, list[Optional[float]]] = {}
    if not model_list:
        for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
            empty_res[disp] = [None] * 12
            empty_res[(grp, disp)] = [None] * 12
            empty_res[f"{grp}_{disp}"] = [None] * 12
        return empty_res

    sql, params = _build_shipment_bb_sql(model_list, plan_year)
    rows = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except Exception as e:
        logger.error("Failed to load live shipment building blocks: %s", e)

    month_cols = ["jan_m", "feb_m", "mar_m", "apr_m", "may_m", "jun_m", "jul_m", "aug_m", "sep_m", "oct_m", "nov_m", "dec_m"]
    driver_data: dict[Any, list[Optional[float]]] = {}
    for grp, disp_name, match_key in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        final_vals = _accumulate_shipment_driver(rows, month_cols, grp, disp_name, match_key) if rows else [None] * 12
        driver_data[disp_name] = final_vals
        driver_data[(grp, disp_name)] = final_vals
        driver_data[f"{grp}_{disp_name}"] = final_vals

    return driver_data


# ─── 5. Planning Cycles & Snapshots for GTS Change of Cycle (CoC) ─────────────

class CycleSnapshotInfo(NamedTuple):
    curr_cs_id: Optional[int]
    prior_cs_id: Optional[int]
    curr_ss_id: Optional[int]
    prior_ss_id: Optional[int]
    active_cycle_month: Optional[int] = None


def _query_cycle_snapshot(
    cur: Any, table_name: str, plan_year: int, snapshot_type_filter: str, prior_to_id: Optional[int] = None
) -> tuple[Optional[int], Optional[int]]:
    """Queries single cycle snapshot id and cycle month number."""
    if prior_to_id is not None:
        sql = f"""
            SELECT s.snapshot_id, pc.cycle_month
            FROM public.{table_name} s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE s.snapshot_id < %s
              AND (pc.planning_year_start = %s OR pc.planning_year_start IS NULL)
            ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1;
        """
        cur.execute(sql, (prior_to_id, plan_year))
    else:
        sql = f"""
            SELECT s.snapshot_id, pc.cycle_month
            FROM public.{table_name} s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE ({snapshot_type_filter})
              AND (pc.planning_year_start = %s OR pc.planning_year_start IS NULL)
            ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1;
        """
        cur.execute(sql, (plan_year,))

    row = cur.fetchone()
    if row:
        s_id = row.get("snapshot_id") if isinstance(row, dict) else row[0]
        c_month = row.get("cycle_month") if isinstance(row, dict) else row[1]
        c_mo_num = None
        if c_month:
            try:
                c_mo_num = int(str(c_month).split("-")[1]) if "-" in str(c_month) else int(c_month)
            except Exception:
                c_mo_num = None
        return s_id, c_mo_num
    return None, None


def _resolve_snapshot_pair(
    cur: Any, table_name: str, plan_year: int, curr_filter: str, prior_filter: str
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolves (curr_id, prior_id, active_cycle_month) for a snapshot table."""
    curr_id, c_mo = _query_cycle_snapshot(cur, table_name, plan_year, curr_filter)
    prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, prior_filter)
    if curr_id and not prior_id:
        prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, "", prior_to_id=curr_id)
    return curr_id, prior_id, c_mo


def _query_fallback_cycle_month(cur: Any, plan_year: int) -> Optional[int]:
    """Queries active cycle month from planning_cycles table as fallback."""
    sql = """
        SELECT cycle_month
        FROM public.planning_cycles
        WHERE is_active = TRUE AND (planning_year_start = %s OR planning_year_start IS NULL)
        ORDER BY cycle_month DESC NULLS LAST
        LIMIT 1;
    """
    cur.execute(sql, (plan_year,))
    row = cur.fetchone()
    if row:
        c_val = row.get("cycle_month") if isinstance(row, dict) else row[0]
        if c_val:
            try:
                return int(str(c_val).split("-")[1]) if "-" in str(c_val) else int(c_val)
            except Exception:
                pass
    return None


def get_cycle_snapshot_ids(plan_year: int) -> CycleSnapshotInfo:
    """
    Detects Current and Prior snapshot IDs for Consumption and Shipment scoped to plan_year.
    Also discovers active_cycle_month (1..12) from planning_cycles.
    """
    curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id = None, None, None, None
    active_cycle_month = None

    curr_filter = "UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' OR pc.is_active = TRUE"
    prior_filter = (
        "UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PRIOR%%' "
        "OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PREV%%' "
        "OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%IBP-1%%'"
    )

    try:
        with get_db_cursor(commit=False) as cur:
            curr_cs_id, prior_cs_id, c_mo = _resolve_snapshot_pair(
                cur, "consumption_snapshots", plan_year, curr_filter, prior_filter
            )
            curr_ss_id, prior_ss_id, s_mo = _resolve_snapshot_pair(
                cur, "shipment_snapshots", plan_year, curr_filter, prior_filter
            )
            active_cycle_month = c_mo or s_mo or _query_fallback_cycle_month(cur, plan_year)
            if not active_cycle_month:
                try:
                    target_date = datetime.date.today() + datetime.timedelta(days=1)
                    dt_info = KenvueCalendar.get_date_info(target_date.strftime("%Y-%m-%d"))
                    if dt_info and "fiscal_month" in dt_info:
                        active_cycle_month = int(dt_info["fiscal_month"])
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Notice discovering cycle snapshot IDs: %s", e)

    return CycleSnapshotInfo(curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id, active_cycle_month)


def _build_cycle_filter_clauses(
    is_prior: bool,
    curr_cs_id: Optional[int],
    prior_cs_id: Optional[int],
    curr_ss_id: Optional[int],
    prior_ss_id: Optional[int],
) -> tuple[str, str]:
    """Builds SQL snapshot filter fragments for consumption and shipment planning rows."""
    if not is_prior:
        cpr_filter = f"""AND (
            cpr.snapshot_id IS NULL
            OR cpr.snapshot_id = {curr_cs_id}
        )""" if curr_cs_id else """AND (
            cpr.snapshot_id IS NULL 
            OR cpr.snapshot_id = (
                SELECT s.snapshot_id
                FROM public.consumption_snapshots s
                JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
                WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%CURRENT%' OR pc.is_active = TRUE)
                ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )"""
        spr_filter = f"""AND (
            spr.snapshot_id IS NULL
            OR spr.snapshot_id = {curr_ss_id}
        )""" if curr_ss_id else """AND (
            spr.snapshot_id IS NULL 
            OR spr.snapshot_id = (
                SELECT s.snapshot_id
                FROM public.shipment_snapshots s
                JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
                WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%CURRENT%' OR pc.is_active = TRUE)
                ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )"""
    else:
        cpr_filter = f"AND cpr.snapshot_id = {prior_cs_id}" if prior_cs_id else """AND cpr.snapshot_id = (
            SELECT s.snapshot_id
            FROM public.consumption_snapshots s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PRIOR%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PREV%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%IBP-1%')
            ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1
        )"""
        spr_filter = f"AND spr.snapshot_id = {prior_ss_id}" if prior_ss_id else """AND spr.snapshot_id = (
            SELECT s.snapshot_id
            FROM public.shipment_snapshots s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PRIOR%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PREV%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%IBP-1%')
            ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1
        )"""
    return cpr_filter, spr_filter


def _fetch_cycle_building_blocks(
    models: list[str], plan_year: int, is_prior: bool = False
) -> dict[str, dict[int, float]]:
    """Safely fetches raw monthly building block values (in Thousands) from PostgreSQL."""
    monthly_data: dict[str, dict[int, float]] = {}
    if not models:
        return monthly_data

    model_list = [str(m).strip() for m in models if m]
    snap_info = get_cycle_snapshot_ids(plan_year)

    if is_prior and snap_info.prior_cs_id is None and snap_info.prior_ss_id is None:
        return monthly_data

    cpr_snap_filter, spr_snap_filter = _build_cycle_filter_clauses(
        is_prior, snap_info.curr_cs_id, snap_info.prior_cs_id, snap_info.curr_ss_id, snap_info.prior_ss_id
    )

    sql = f"""
    -- Consumption Building Blocks
    SELECT
        cbb.name AS building_block,
        EXTRACT(MONTH FROM cpv.period_month)::int AS month_num,
        SUM(cpv.value_in_thousands) AS value_in_thousands
    FROM public.consumption_planning_rows cpr
    INNER JOIN public.consumption_building_blocks cbb
        ON cpr.building_block_id = cbb.block_id
    INNER JOIN public.consumption_planning_values cpv
        ON cpr.row_id = cpv.row_id
    INNER JOIN public.master_models mm
        ON cpr.model_id = mm.model_id
    WHERE
        mm.model_name = ANY(%s)
        AND cpr.is_deleted = FALSE
        AND cbb.is_active = TRUE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM cpv.period_month) = %s
        {cpr_snap_filter}
    GROUP BY cbb.name, month_num

    UNION ALL

    -- Shipment Building Blocks
    SELECT
        sbb.name AS building_block,
        EXTRACT(MONTH FROM spv.period_month)::int AS month_num,
        SUM(spv.value_in_thousands) AS value_in_thousands
    FROM public.shipment_planning_rows spr
    INNER JOIN public.shipment_building_blocks sbb
        ON spr.building_block_id = sbb.block_id
    INNER JOIN public.shipment_planning_values spv
        ON spr.row_id = spv.row_id
    INNER JOIN public.master_models mm
        ON spr.model_id = mm.model_id
    WHERE
        mm.model_name = ANY(%s)
        AND spr.is_deleted = FALSE
        AND sbb.is_active = TRUE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM spv.period_month) = %s
        {spr_snap_filter}
    GROUP BY sbb.name, month_num;
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, plan_year, model_list, plan_year))
            for r in cur.fetchall():
                norm_name = normalize_text(r["building_block"])
                m_num = int(r["month_num"])
                val_m = float(r["value_in_thousands"] or 0.0) / 1000.0  # $K to $M
                monthly_data.setdefault(norm_name, {})[m_num] = (
                    monthly_data.setdefault(norm_name, {}).get(m_num, 0.0) + val_m
                )
    except Exception as e:
        cycle_lbl = "Prior" if is_prior else "Current"
        logger.warning("Notice querying cycle building blocks (%s): %s", cycle_lbl, e)

    return monthly_data


def _matches_driver_name(db_bb_name: str, match_key: str) -> bool:
    """Exact driver matching logic for CoC."""
    return match_key in db_bb_name


def _aggregate_driver_raw_monthly(raw_data: dict[str, dict[int, float]], match_key: str) -> dict[int, float]:
    """Aggregates monthly sums for building blocks matching the specified driver match key."""
    result: dict[int, float] = {}
    for k, v in raw_data.items():
        if _matches_driver_name(k, match_key):
            for m, val in v.items():
                result[m] = result.get(m, 0.0) + val
    return result


def _compute_single_driver_coc(
    match_key: str,
    current_raw: dict[str, dict[int, float]],
    prior_raw: dict[str, dict[int, float]],
    price_factors: dict[int, float],
) -> list[Optional[float]]:
    """Calculates monthly CoC deltas for a single driver scaled by price factor."""
    curr_dict = _aggregate_driver_raw_monthly(current_raw, match_key)
    prior_dict = _aggregate_driver_raw_monthly(prior_raw, match_key)

    res: list[Optional[float]] = [None] * 12
    has_any = False
    for m in range(1, 13):
        if m in curr_dict or m in prior_dict:
            curr_val = curr_dict.get(m, 0.0)
            prior_val = prior_dict.get(m, 0.0)
            pf = price_factors.get(m, 1.0)
            res[m - 1] = round((curr_val - prior_val) * pf, 4)
            has_any = True

    if has_any:
        return [0.0 if v is None else v for v in res]
    return [None] * 12


def _sum_monthly_pair(arr1: list, arr2: list, round_digits: int = 4) -> list[Optional[float]]:
    """Sums two 12-month lists element-wise with rounding and None coalescing."""
    has_any = any(v is not None for v in arr1) or any(v is not None for v in arr2)
    if not has_any:
        return [None] * 12
    res: list[Optional[float]] = [None] * 12
    for i in range(12):
        v1 = arr1[i]
        v2 = arr2[i]
        if v1 is not None or v2 is not None:
            res[i] = round((v1 or 0.0) + (v2 or 0.0), round_digits)
        else:
            res[i] = 0.0
    return res


def load_coc_building_blocks(
    models: str | list[str], plan_year: int, price_factors: dict[int, float]
) -> dict[str, list[Optional[float]]]:
    """
    Computes CoC Building Blocks:
        CoC Value[m] = (Current Cycle POS[m] - Previous Cycle POS[m]) * Price Factor[m]
    """
    model_list = _normalize_models(models)

    if not model_list:
        return {disp: [None] * 12 for _, disp, _ in GTS_COC_DRIVER_DEFINITIONS}

    current_raw = _fetch_cycle_building_blocks(model_list, plan_year, is_prior=False)
    prior_raw = _fetch_cycle_building_blocks(model_list, plan_year, is_prior=True)

    driver_data: dict[str, list[Optional[float]]] = {}
    for _, disp_name, match_key in GTS_COC_DRIVER_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        driver_data[disp_name] = _compute_single_driver_coc(match_key, current_raw, prior_raw, price_factors)

    # Net Innovation = Innovation CoC + Cannibalization CoC
    driver_data[DRIVER_NET_INNOVATION] = _sum_monthly_pair(
        driver_data.get("Innovation", [None] * 12),
        driver_data.get("Cannibalization", [None] * 12),
    )

    # Net Price = Price CoC + Elasticity CoC
    driver_data[DRIVER_NET_PRICE] = _sum_monthly_pair(
        driver_data.get("Price", [None] * 12),
        driver_data.get("Elasticity", [None] * 12),
    )

    return driver_data


# ─── 6. Snowflake Ingestion (POS & GTS) ───────────────────────────────────────

def _build_snowflake_pos_filter(rules: list[dict[str, str]]) -> str:
    """Constructs dynamic SQL filter for Circana POS syndication data."""
    if not rules:
        return ""
    clauses = []
    for r in rules:
        b = r.get("brand", "").replace("'", "''")
        sb = r.get("sub_brand", "").replace("'", "''")
        c = r.get("category", "").replace("'", "''")
        sc = r.get("subcategory", "").replace("'", "''")

        sub_conditions = []
        if b:
            sub_conditions.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_B1_BRAND_DESC)) = '{b}'")
        if sb:
            sub_conditions.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_B2_SUB_BRAND_DESC)) = '{sb}'")
        if c:
            sub_conditions.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C4_CATEGORY_DESC)) = '{c}'")
        if sc:
            sub_conditions.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C5_SUBCATEGORY_DESC)) = '{sc}'")

        if sub_conditions:
            clauses.append("(" + " AND ".join(sub_conditions) + ")")

    if clauses:
        return "AND (" + " OR ".join(clauses) + ")"
    return ""


def _validate_month_completeness(weeks_by_month: dict[int, int], plan_year: int) -> dict[int, bool]:
    """Validates 4-4-5 completeness for each month."""
    is_complete = {}
    for m in range(1, 13):
        expected = KenvueCalendar.get_month_week_count(plan_year, m)
        actual = weeks_by_month.get(m, 0)
        is_complete[m] = (actual >= expected) and (actual > 0)
    return is_complete


def fetch_snowflake_monthly_pos(
    rules: list[dict[str, str]], base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Fetches weekly retail POS actuals from Snowflake GLBL_SYNDCTD_FACT_DATA."""
    pos_base: list[Optional[float]] = [None] * 12
    pos_plan_actual: list[Optional[float]] = [None] * 12

    if not rules:
        return pos_base, pos_plan_actual

    try:
        from database.connection import get_snowflake_connection as get_sf_conn
    except ImportError:
        get_sf_conn = get_snowflake_connection

    filter_sql = _build_snowflake_pos_filter(rules)
    start_date_str = f"{base_year}-01-01"
    end_date_str = f"{plan_year}-12-31"

    c_db = getattr(config, "SNOWFLAKE_CONSUMPTION_DATABASE", os.getenv("SNOWFLAKE_CONSUMPTION_DATABASE", "EDW_POS_DEMAND_PLANNING"))
    c_sch = getattr(config, "SNOWFLAKE_CONSUMPTION_SCHEMA", os.getenv("SNOWFLAKE_CONSUMPTION_SCHEMA", "CIRCANA_US"))

    query = f"""
    SELECT
        dim_time.GLOBAL_DATE_SHORT_DESC AS WEEK_DATE,
        SUM(fact.GLOBAL_VALUE_LC) AS POS_VALUE,
        SUM(fact.GLOBAL_UNITS) AS POS_UNITS
    FROM {c_db}.{c_sch}.GLBL_SYNDCTD_FACT_DATA fact
    INNER JOIN {c_db}.{c_sch}.GLBL_SYNDCTD_DIM_MARKET dim_market
        ON fact.market_id = dim_market.market_id
        AND dim_market.DELIVERY_KEY = fact.DELIVERY_KEY
    INNER JOIN {c_db}.{c_sch}.GLBL_SYNDCTD_DIM_TIME dim_time
        ON fact.date_id = dim_time.date_id
        AND fact.DELIVERY_KEY = dim_time.DELIVERY_KEY
    INNER JOIN {c_db}.{c_sch}.GLBL_SYNDCTD_DIM_PRODUCT dim_product
        ON fact.GLOBAL_PRODUCT_UTAG = dim_product.GLOBAL_PRODUCT_UTAG
    WHERE
        dim_market.GLOBAL_MARKET = 'UNITED STATES'
        AND dim_market.GLOBAL_SUPPLIER = 'CIRCANA'
        AND dim_time.GLOBAL_DATE_GRAIN_DESC = 'WEEKLY'
        AND dim_product.LOCAL_MANUFACTURER IN ('KENVUE INC', 'KENVUE')
        AND dim_market.SOURCE_RETAILER_SHORT_DESC = 'TOTAL US - MULTI OUTLET+'
        AND TRY_TO_DATE(dim_time.GLOBAL_DATE_SHORT_DESC) BETWEEN '{start_date_str}' AND '{end_date_str}'
        {filter_sql}
    GROUP BY dim_time.GLOBAL_DATE_SHORT_DESC
    ORDER BY TRY_TO_DATE(dim_time.GLOBAL_DATE_SHORT_DESC) ASC;
    """

    try:
        conn = get_sf_conn()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()

        base_sums: dict[int, float] = {m: 0.0 for m in range(1, 13)}
        plan_sums: dict[int, float] = {m: 0.0 for m in range(1, 13)}
        plan_weeks: dict[int, int] = {m: 0 for m in range(1, 13)}
        has_base_data: set[int] = set()

        for r in rows:
            dt_str, val, _ = r[0], float(r[1] or 0.0), float(r[2] or 0.0)
            d_obj = datetime.date.fromisoformat(str(dt_str)[:10])
            eval_date = d_obj + datetime.timedelta(days=1) if d_obj.weekday() == 6 else d_obj
            dt_info = KenvueCalendar.get_date_info(eval_date)
            yr = dt_info.fiscal_year if hasattr(dt_info, "fiscal_year") else dt_info.get("fiscal_year")
            mo = dt_info.fiscal_month if hasattr(dt_info, "fiscal_month") else dt_info.get("fiscal_month")

            if yr == base_year and 1 <= mo <= 12:
                base_sums[mo] += val
                has_base_data.add(mo)
            elif yr == plan_year and 1 <= mo <= 12:
                plan_sums[mo] += val
                plan_weeks[mo] += 1

        is_complete = _validate_month_completeness(plan_weeks, plan_year)

        for m in range(1, 13):
            if m in has_base_data:
                pos_base[m - 1] = round(base_sums[m] / 1000000.0, 4)  # To Millions
            if is_complete[m]:
                pos_plan_actual[m - 1] = round(plan_sums[m] / 1000000.0, 4)

    except Exception as e:
        logger.error("Snowflake consumption POS query error: %s", e)

    return pos_base, pos_plan_actual


def _build_snowflake_gts_where_clause(rules: list[dict[str, str]]) -> str:
    """Builds WHERE clause for SAP F360 shipments query."""
    if not rules:
        return "1=1"
    sub_clauses = []
    for r in rules:
        c1 = r.get("c1", "").replace("'", "''")
        c2 = r.get("c2", "").replace("'", "''")
        c3 = r.get("c3", "").replace("'", "''")
        c4 = r.get("c4", "").replace("'", "''")
        c5 = r.get("c5", "").replace("'", "''")
        b1 = r.get("b1", "").replace("'", "''")
        b2 = r.get("b2", "").replace("'", "''")

        sub_conds = []
        if c1:
            sub_conds.append(f"UPPER(TRIM(C1_BUSINESS_SEGMENT)) = '{c1}'")
        if c2:
            sub_conds.append(f"UPPER(TRIM(C2_BUSINESS_SUBSEGMENT)) = '{c2}'")
        if c3:
            sub_conds.append(f"UPPER(TRIM(C3_NEED_STATE)) = '{c3}'")
        if c4:
            sub_conds.append(f"UPPER(TRIM(C4_CATEGORY)) = '{c4}'")
        if c5:
            sub_conds.append(f"UPPER(TRIM(C5_SUBCATEGORY)) = '{c5}'")
        if b1:
            sub_conds.append(f"UPPER(TRIM(B1_BRAND)) = '{b1}'")
        if b2:
            sub_conds.append(f"UPPER(TRIM(B2_SUBBRAND)) = '{b2}'")

        if sub_conds:
            sub_clauses.append("(" + " AND ".join(sub_conds) + ")")

    if sub_clauses:
        return " OR ".join(sub_clauses)
    return "1=1"


def _aggregate_snowflake_gts_months(
    rows: list[Any], base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Aggregates Snowflake GTS query rows into monthly arrays in Millions ($M)."""
    gts_base: list[Optional[float]] = [None] * 12
    gts_plan_actual: list[Optional[float]] = [None] * 12

    base_map: dict[int, float] = {}
    plan_map: dict[int, float] = {}

    for r in rows:
        yr = int(r[0])
        mo = int(r[1])
        amt = float(r[2] or 0.0)

        if 1 <= mo <= 12:
            if yr == base_year:
                base_map[mo] = base_map.get(mo, 0.0) + amt
            elif yr == plan_year:
                plan_map[mo] = plan_map.get(mo, 0.0) + amt

    for m in range(1, 13):
        if m in base_map:
            gts_base[m - 1] = round(base_map[m] / 1000000.0, 4)
        if m in plan_map:
            gts_plan_actual[m - 1] = round(plan_map[m] / 1000000.0, 4)

    return gts_base, gts_plan_actual


def fetch_snowflake_monthly_gts(
    rules: list[dict[str, str]], base_year: int, plan_year: Optional[int] = None
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Fetches SAP F360 shipments monthly actuals from Snowflake."""
    py = plan_year or (base_year + 1)
    gts_base: list[Optional[float]] = [None] * 12
    gts_plan_actual: list[Optional[float]] = [None] * 12

    if not rules:
        return gts_base, gts_plan_actual

    s_db = getattr(config, "SNOWFLAKE_SHIPMENT_DATABASE", os.getenv("SNOWFLAKE_SHIPMENT_DATABASE", "EDW_STANDARDIZED"))
    s_sch = getattr(config, "SNOWFLAKE_SHIPMENT_SCHEMA", os.getenv("SNOWFLAKE_SHIPMENT_SCHEMA", "NORTH_AMERICA"))
    s_view = getattr(config, "SNOWFLAKE_SHIPMENT_VIEW", os.getenv("SNOWFLAKE_SHIPMENT_VIEW", "VW_FACT_F360_SHIPMENTS"))

    where_clause = _build_snowflake_gts_where_clause(rules)
    year_filter = f"YEAR IN ({base_year}, {py})"

    query = f"""
    SELECT
        YEAR,
        MONTHNUMBER,
        SUM(GTS_AMT) AS GTS_AMT,
        SUM(GTS_QTY) AS GTS_QTY
    FROM {s_db}.{s_sch}.{s_view}
    WHERE
        ({where_clause})
        AND {year_filter}
    GROUP BY
        YEAR,
        MONTHNUMBER
    ORDER BY
        YEAR,
        MONTHNUMBER;
    """

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        gts_base, gts_plan_actual = _aggregate_snowflake_gts_months(rows, base_year, py)
    except Exception as e:
        logger.error("Snowflake shipment GTS query error: %s", e)

    return gts_base, gts_plan_actual
