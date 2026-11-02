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
    ("Innovation",   DRIVER_NET_INNOVATION, "COMPOUND_NET_INNOVATION"),
    ("Innovation",   "Innovation",          "INNOVATION"),
    ("Innovation",   "Cannibalization",     "CANNIBALIZATION"),
    ("Innovation",   "Discontinuations",    "DISCONTINUATIONS"),
    ("Innovation",   "Renovation",          "RENOVATION"),
    ("Commercial",   "Media",               "MEDIA"),
    ("Commercial",   "Trade",               "TRADE"),
    ("Price",        DRIVER_NET_PRICE,      "COMPOUND_NET_PRICE"),
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Customer",     "Club",                "CLUB"),
    ("Other",        "Other",               "OTHER"),
]

# Shipment Driver Definitions: (Category Group, Display Name, DB Match Key)
SHIPMENT_DRIVER_ROW_DEFINITIONS = [
    ("Consumption",       "Factory POS",                       "POS"),
    ("Inventory",         "Trade Inventory Change",            "INVENTORY CHANGE"),
    ("Inventory",         "Retailer Inventory Adjustment",     "INVENTORY ADJUSTMENT"),
    ("Inventory",         "Other",                             "INVENTORY OTHER"),
    ("IBP Overlays",      "Supply & Operation Execution Risk", "SUPPLY"),
    ("IBP Overlays",      "Liquidation / Discontinuation",     "LIQUIDATION"),
    ("IBP Overlays",      "Innovation Pipeline",               "INNOVATION PIPELINE"),
    ("IBP Overlays",      "Club Pipeline",                     "CLUB PIPELINE"),
    ("IBP Overlays",      "Trade Pipefill / Pipeline",         "TRADE PIPELINE"),
    ("IBP Overlays",      "Retail Distribution Gains/Losses",  "DISTRIBUTION GAINS"),
    ("IBP Overlays",      "Other",                             "OVERLAY OTHER"),
]

# GTS Change of Cycle (CoC) Driver Definitions
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
    ("Commercial",   "Media",               "MEDIA"),
    ("Commercial",   "Trade",               "TRADE"),
    ("Price",        DRIVER_NET_PRICE,      "COMPOUND_NET_PRICE"),
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Customer",     "Club",                "CLUB"),
    ("Other",        "Other",               "OTHER"),
]


# ─── 1. Fiscal Planning Calendar & Cycle Service ──────────────────────────────

def get_active_years() -> tuple[int, int]:
    """Discovers base_year (Prior Year) and plan_year (Current Planning Year)."""
    env_base = os.getenv("IBP_BASE_YEAR")
    env_plan = os.getenv("IBP_PLAN_YEAR")
    if env_base and env_plan:
        try:
            return int(env_base), int(env_plan)
        except ValueError:
            pass

    target_date = datetime.date.today() + datetime.timedelta(days=1)
    date_str = target_date.strftime("%Y-%m-%d")
    date_info = KenvueCalendar.get_date_info(date_str)
    plan_year = int(date_info.get("fiscal_year", target_date.year))
    base_year = plan_year - 1
    return base_year, plan_year


def parse_month_num(val: Any) -> Optional[int]:
    """Normalizes month representations (int, date, string name) to 1..12."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        v_int = int(val)
        return v_int if 1 <= v_int <= 12 else None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.month

    s = str(val).strip().upper()
    if s.isdigit():
        v_int = int(s)
        return v_int if 1 <= v_int <= 12 else None
    if s in MONTH_NAME_MAP:
        return MONTH_NAME_MAP[s]
    clean = re.sub(r"[^A-Z]", "", s)
    return MONTH_NAME_MAP.get(clean[:3], None)


# ─── 2. Model & Squad PostgreSQL Discovery ───────────────────────────────────

def load_squads_and_models() -> dict[str, list[str]]:
    """Fetches hierarchy of active Squads mapped to their active Models."""
    squad_map: dict[str, list[str]] = {}
    sql = """
        SELECT
            COALESCE(ms.squad_name, 'Unassigned') AS squad_name,
            mm.model_name
        FROM public.master_models mm
        LEFT JOIN public.master_squads ms ON mm.squad_id = ms.squad_id
        WHERE mm.is_active = TRUE
          AND (ms.is_active = TRUE OR ms.squad_id IS NULL)
        ORDER BY squad_name, mm.model_name;
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            for r in rows:
                sq = str(r["squad_name"]).strip()
                m = str(r["model_name"]).strip()
                if sq and m:
                    squad_map.setdefault(sq, []).append(m)
    except Exception as e:
        logger.error("Failed to load squads and models: %s", e)

    return squad_map


def load_consumption_model_rules(models: str | list[str]) -> list[dict[str, str]]:
    """Loads Snowflake Consumption mapping rules for specified model(s)."""
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        return []

    sql = """
        SELECT
            mm.model_name,
            mcr.brand,
            mcr.sub_brand,
            mcr.category,
            mcr.subcategory,
            mcr.form,
            mcr.segment
        FROM public.model_consumption_rules mcr
        JOIN public.master_models mm ON mcr.model_id = mm.model_id
        WHERE mm.model_name = ANY(%s)
          AND mcr.is_active = TRUE
          AND mm.is_active = TRUE;
    """
    rules: list[dict[str, str]] = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list,))
            rules = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("Failed to load consumption rules: %s", e)
    return rules


def load_shipment_model_rules(models: str | list[str]) -> list[dict[str, str]]:
    """Loads Snowflake Shipment mapping rules for specified model(s)."""
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        return []

    sql = """
        SELECT
            mm.model_name,
            msr.brand,
            msr.sub_brand,
            msr.category,
            msr.subcategory,
            msr.form,
            msr.segment
        FROM public.model_shipment_rules msr
        JOIN public.master_models mm ON msr.model_id = mm.model_id
        WHERE mm.model_name = ANY(%s)
          AND msr.is_active = TRUE
          AND mm.is_active = TRUE;
    """
    rules: list[dict[str, str]] = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list,))
            rules = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error("Failed to load shipment rules: %s", e)
    return rules


# ─── 3. Price Index & Factors ────────────────────────────────────────────────

def _build_price_index_query(has_model_filter: bool) -> str:
    """Builds SQL query for Price Index calculation."""
    model_clause = "AND mm.model_name = ANY(%s)" if has_model_filter else ""
    return f"""
    WITH weight_universe AS (
        SELECT
            EXTRACT(MONTH FROM spv.period_month)::int AS month_num,
            SUM(spv.value_in_thousands) AS total_weight_k
        FROM public.shipment_planning_rows spr
        INNER JOIN public.shipment_planning_values spv
            ON spr.row_id = spv.row_id
        INNER JOIN public.master_models mm
            ON spr.model_id = mm.model_id
        WHERE
            spr.is_deleted = FALSE
            AND mm.is_active = TRUE
            AND EXTRACT(YEAR FROM spv.period_month) = %s
            {model_clause}
        GROUP BY month_num
    )
    SELECT
        EXTRACT(MONTH FROM spv.period_month)::int AS month_num,
        SUM(
            (spv.value_in_thousands / NULLIF(wu.total_weight_k, 0))
            * NULLIF(spv.price_index, 0)
        ) AS weighted_price_index
    FROM public.shipment_planning_rows spr
    INNER JOIN public.shipment_planning_values spv
        ON spr.row_id = spv.row_id
    INNER JOIN public.master_models mm
        ON spr.model_id = mm.model_id
    INNER JOIN weight_universe wu
        ON EXTRACT(MONTH FROM spv.period_month)::int = wu.month_num
    WHERE
        spr.is_deleted = FALSE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM spv.period_month) = %s
        {model_clause}
    GROUP BY
        EXTRACT(MONTH FROM spv.period_month)::int
    ORDER BY
        month_num ASC;
    """


def load_price_index_from_postgres(
    models: str | list[str], plan_year: Optional[int] = None
) -> dict[int, float]:
    """Loads weighted Price Index (defaults to 100.0) from shipment planning values."""
    if plan_year is None:
        _, plan_year = get_active_years()

    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    has_filter = len(model_list) > 0
    sql = _build_price_index_query(has_filter)
    params = (plan_year, model_list, plan_year, model_list) if has_filter else (plan_year, plan_year)

    indices = {m: 100.0 for m in range(1, 13)}
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, params)
            for r in cur.fetchall():
                m_num = int(r["month_num"])
                if 1 <= m_num <= 12 and r["weighted_price_index"] is not None:
                    indices[m_num] = float(r["weighted_price_index"])
    except Exception as e:
        logger.error("Failed to load price index from postgres: %s", e)

    return indices


# ─── 4. Live Building Blocks (Consumption & Shipment) ────────────────────────

def _accumulate_consumption_bb_rows(rows: list[dict[str, Any]]) -> dict[str, list[Optional[float]]]:
    """Accumulates monthly planning values in millions for consumption building blocks."""
    raw_bb: dict[str, list[Optional[float]]] = {}
    for r in rows:
        m_num = int(r["month_num"])
        if 1 <= m_num <= 12:
            m_idx = m_num - 1
            norm_bb = normalize_text(r["building_block"])
            val_m = float(r["value_in_thousands"] or 0.0) / 1000.0
            raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] = (
                (raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] or 0.0) + val_m
            )
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
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

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
    innov = _extract_consumption_driver_val(raw_bb, "INNOVATION")
    cann = _extract_consumption_driver_val(raw_bb, "CANNIBALIZATION")
    price = _extract_consumption_driver_val(raw_bb, "PRICE")
    elast = _extract_consumption_driver_val(raw_bb, "ELASTICITY")

    compound_map = {
        "COMPOUND_NET_INNOVATION": _combine_monthly_drivers(innov, cann),
        "COMPOUND_NET_PRICE": _combine_monthly_drivers(price, elast),
        "INNOVATION": innov,
        "CANNIBALIZATION": cann,
        "PRICE": price,
        "ELASTICITY": elast,
    }

    driver_data: dict[str, list[Optional[float]]] = {}
    for _, disp_name, match_key in CONSUMPTION_DRIVER_ROW_DEFINITIONS:
        if match_key in compound_map:
            driver_data[disp_name] = compound_map[match_key]
        else:
            driver_data[disp_name] = _extract_consumption_driver_val(raw_bb, match_key)

    return driver_data


def _clean_token(s: Any) -> str:
    """Normalizes string into uppercase alphanumeric token for fuzzy driver matching."""
    if s is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _matches_shipment_driver(db_name: str, grp: str, disp_name: str, match_key: str) -> bool:
    """Matches a PostgreSQL building block name to a defined dashboard driver."""
    c_db = _clean_token(db_name)
    c_disp = _clean_token(disp_name)
    c_key = _clean_token(match_key)
    if not c_db:
        return False
    if c_disp == "OTHER":
        if "OVERLAY" in c_db or "IBP" in c_db:
            return grp == GROUP_IBP_OVERLAYS
        if "INVENT" in c_db:
            return grp == "Inventory"
        return grp == "Inventory" if "OVERLAY" not in c_key else grp == GROUP_IBP_OVERLAYS
    for kw in ["LIQUIDAT", "SUPPLY", "RETAIL", "DISTRIB", "INNOVAT", "TRADE", "CLUB"]:
        if kw in c_key and kw in c_db:
            return True
    return (c_key in c_db) or (c_disp in c_db) or (c_db in c_key) or (c_db in c_disp)


def _accumulate_shipment_driver(
    rows: list[dict[str, Any]],
    month_cols: list[str],
    grp: str,
    disp_name: str,
    match_key: str,
) -> list[Optional[float]]:
    """Accumulates monthly values across matching shipment rows for a single driver."""
    matched = False
    monthly_accum = [0.0] * 12
    for r in rows:
        db_bb_name = str(r["driver_building_block"] or "")
        if _matches_shipment_driver(db_bb_name, grp, disp_name, match_key):
            matched = True
            for m_idx, col_name in enumerate(month_cols):
                monthly_accum[m_idx] += float(r[col_name] or 0.0)

    return [round(v, 4) for v in monthly_accum] if matched else [None] * 12


def load_live_shipment_building_blocks(
    models: str | list[str], plan_year: int
) -> dict[Any, list[Optional[float]]]:
    """Queries live shipment building blocks from PostgreSQL using pivoted monthly query."""
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        empty_res = {}
        for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
            empty_res[disp] = [None] * 12
            empty_res[(grp, disp)] = [None] * 12
            empty_res[f"{grp}_{disp}"] = [None] * 12
        return empty_res

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
    GROUP BY
        sbb.name
    ORDER BY
        sbb.name ASC;
    """
    rows = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, plan_year))
            rows = cur.fetchall()
    except Exception as e:
        logger.error("Failed to load live shipment building blocks: %s", e)

    month_cols = ["jan_m", "feb_m", "mar_m", "apr_m", "may_m", "jun_m",
                  "jul_m", "aug_m", "sep_m", "oct_m", "nov_m", "dec_m"]

    driver_data = {}
    for grp, disp_name, match_key in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        arr = _accumulate_shipment_driver(rows, month_cols, grp, disp_name, match_key)
        driver_data[(grp, disp_name)] = arr
        driver_data[disp_name] = arr
        driver_data[f"{grp}_{disp_name}"] = arr

    return driver_data


# ─── 5. GTS Change of Cycle (CoC) Snapshots ───────────────────────────────────

class CycleSnapshotInfo(NamedTuple):
    curr_cs_id: Optional[int] = None
    prior_cs_id: Optional[int] = None
    curr_ss_id: Optional[int] = None
    prior_ss_id: Optional[int] = None
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
    if not row:
        return None, None
    snap_id = None
    c_mo = None
    if isinstance(row, dict):
        snap_id = row.get("snapshot_id")
        c_mo = row.get("cycle_month")
    else:
        try:
            snap_id = row["snapshot_id"]
            c_mo = row["cycle_month"]
        except (TypeError, KeyError, IndexError):
            snap_id = row[0] if len(row) > 0 else None
            c_mo = row[1] if len(row) > 1 else None
    m_num = parse_month_num(c_mo) if c_mo else None
    return snap_id, m_num if (m_num and 1 <= m_num <= 12) else None


def _resolve_snapshot_pair(
    cur, table_name: str, plan_year: int, curr_filter: str, prior_filter: str
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolves Current and Prior snapshot ID pair along with detected cycle month."""
    curr_id, c_mo = _query_cycle_snapshot(cur, table_name, plan_year, curr_filter)
    prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, prior_filter)
    if not prior_id and curr_id:
        prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, "", prior_to_id=curr_id)
    return curr_id, prior_id, c_mo


def _query_fallback_cycle_month(cur, plan_year: int) -> Optional[int]:
    """Queries latest active cycle month from planning_cycles table."""
    cur.execute("""
        SELECT pc.cycle_month
        FROM public.planning_cycles pc
        WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' OR pc.is_active = TRUE)
          AND (pc.planning_year_start = %s OR pc.planning_year_start IS NULL)
        ORDER BY pc.cycle_month DESC NULLS LAST
        LIMIT 1;
    """, (plan_year,))
    row = cur.fetchone()
    if row:
        val = row.get("cycle_month") if isinstance(row, dict) else row[0]
        m_num = parse_month_num(val)
        if m_num and 1 <= m_num <= 12:
            return m_num
    return None


def get_cycle_snapshot_ids(plan_year: int) -> CycleSnapshotInfo:
    """
    Detects Current and Prior snapshot IDs for Consumption and Shipment scoped to plan_year.
    Also discovers active_cycle_month (1..12) from planning_cycles with KenvueCalendar fallback.
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
        cpr_filter = f"AND (cpr.snapshot_id = {curr_cs_id} OR cpr.snapshot_id IS NULL)" if curr_cs_id else ""
        spr_filter = f"AND (spr.snapshot_id = {curr_ss_id} OR spr.snapshot_id IS NULL)" if curr_ss_id else ""
    else:
        cpr_filter = f"AND cpr.snapshot_id = {prior_cs_id}" if prior_cs_id else "AND 1=0"
        spr_filter = f"AND spr.snapshot_id = {prior_ss_id}" if prior_ss_id else "AND 1=0"
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
                val_m = float(r["value_in_thousands"] or 0.0) / 1000.0
                monthly_data.setdefault(norm_name, {})[m_num] = (
                    monthly_data.setdefault(norm_name, {}).get(m_num, 0.0) + val_m
                )
    except Exception as e:
        logger.warning("Notice querying cycle building blocks (%s): %s", "Prior" if is_prior else "Current", e)

    return monthly_data


def _matches_coc_driver_name(db_bb_name: str, match_key: str) -> bool:
    """Robust pattern matching between PostgreSQL block name and logical driver for GTS CoC."""
    norm = normalize_text(db_bb_name)
    rules = {
        "INNOVATION": lambda n: "INNOVATION" in n and "NET" not in n and "CANNIBAL" not in n,
        "CANNIBALIZATION": lambda n: "CANNIBAL" in n,
        "PRICE": lambda n: "PRICE" in n and "NET" not in n and "ELAST" not in n,
        "ELASTICITY": lambda n: "ELAST" in n,
        "OTHER": lambda n: "OTHER" in n and "OVERLAY" not in n,
        "RENOVATION": lambda n: "RENOVAT" in n,
        "DISCONTINUATIONS": lambda n: "DISCONTINU" in n,
        MATCH_KEY_BASE_TREND: lambda n: "BASE" in n and "TREND" in n,
        "SEASON": lambda n: "SEASON" in n,
        "COMPETITION": lambda n: "COMPET" in n,
        "DISTRIBUTION": lambda n: "DISTRIBUT" in n,
        "MEDIA": lambda n: "MEDIA" in n,
        "TRADE": lambda n: "TRADE" in n,
        "CLUB": lambda n: "CLUB" in n,
    }
    matcher = rules.get(match_key)
    if matcher:
        return matcher(norm)
    return match_key in norm


def _aggregate_driver_raw_monthly(
    raw_data: dict[str, dict[int, float]], match_key: str
) -> dict[int, float]:
    """Aggregates raw monthly building block values matching a logical driver key."""
    result: dict[int, float] = {}
    for k, v in raw_data.items():
        if _matches_coc_driver_name(k, match_key):
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

    return res if has_any else [None] * 12


def _sum_monthly_pair(arr1: list, arr2: list, round_digits: int = 4) -> list[Optional[float]]:
    """Sums two 12-month lists element-wise with rounding and None coalescing."""
    res: list[Optional[float]] = [None] * 12
    for i in range(12):
        if arr1[i] is not None or arr2[i] is not None:
            res[i] = round((arr1[i] or 0.0) + (arr2[i] or 0.0), round_digits)
    return res


def load_coc_building_blocks(
    models: str | list[str], plan_year: int, price_factors: dict[int, float]
) -> dict[str, list[Optional[float]]]:
    """
    Computes CoC Building Blocks:
        CoC Value[m] = (Current Cycle POS[m] - Previous Cycle POS[m]) * Price Factor[m]
    """
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        return {disp: [None] * 12 for _, disp, _ in GTS_COC_DRIVER_DEFINITIONS}

    current_raw = _fetch_cycle_building_blocks(model_list, plan_year, is_prior=False)
    prior_raw = _fetch_cycle_building_blocks(model_list, plan_year, is_prior=True)

    driver_data: dict[str, list[Optional[float]]] = {}
    for _, disp_name, match_key in GTS_COC_DRIVER_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        driver_data[disp_name] = _compute_single_driver_coc(match_key, current_raw, prior_raw, price_factors)

    driver_data[DRIVER_NET_INNOVATION] = _sum_monthly_pair(
        driver_data.get("Innovation", [None] * 12),
        driver_data.get("Cannibalization", [None] * 12),
    )

    driver_data[DRIVER_NET_PRICE] = _sum_monthly_pair(
        driver_data.get("Price", [None] * 12),
        driver_data.get("Elasticity", [None] * 12),
    )

    return driver_data


# ─── 6. Snowflake Ingestion (POS & GTS) ───────────────────────────────────────

def _build_snowflake_pos_filter(rules: list[dict[str, str]]) -> str:
    """Builds SQL WHERE filter for Snowflake POS product hierarchy rules."""
    rule_clauses = []
    for r in rules:
        conds = []
        if r.get("brand"):
            b_esc = r["brand"].replace("'", "''")
            conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_B1_BRAND_DESC)) = '{b_esc}'")
        if r.get("sub_brand"):
            sb_esc = r["sub_brand"].replace("'", "''")
            conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_B2_SUB_BRAND_DESC)) = '{sb_esc}'")
        if r.get("category"):
            c_esc = r["category"].replace("'", "''")
            conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C4_CATEGORY_DESC)) = '{c_esc}'")
        if r.get("subcategory"):
            sc_esc = r["subcategory"].replace("'", "''")
            conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C5_SUB_CATEGORY_DESC)) = '{sc_esc}'")
        if r.get("form"):
            f_esc = r["form"].replace("'", "''")
            conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C6_FORM_DESC)) = '{f_esc}'")
        if r.get("segment"):
            sg_esc = r["segment"].replace("'", "''")
            conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C7_SEGMENT_DESC)) = '{sg_esc}'")

        if conds:
            rule_clauses.append("(" + " AND ".join(conds) + ")")

    return f"AND ({' OR '.join(rule_clauses)})" if rule_clauses else "AND 1=0"


def _build_snowflake_gts_filter(rules: list[dict[str, str]]) -> str:
    """Builds SQL WHERE filter for Snowflake GTS product hierarchy rules."""
    rule_clauses = []
    for r in rules:
        conds = []
        if r.get("brand"):
            b_esc = r["brand"].replace("'", "''")
            conds.append(f"UPPER(TRIM(p.BRAND)) = '{b_esc}'")
        if r.get("sub_brand"):
            sb_esc = r["sub_brand"].replace("'", "''")
            conds.append(f"UPPER(TRIM(p.SUB_BRAND)) = '{sb_esc}'")
        if r.get("category"):
            c_esc = r["category"].replace("'", "''")
            conds.append(f"UPPER(TRIM(p.CATEGORY)) = '{c_esc}'")
        if r.get("subcategory"):
            sc_esc = r["subcategory"].replace("'", "''")
            conds.append(f"UPPER(TRIM(p.SUB_CATEGORY)) = '{sc_esc}'")
        if r.get("form"):
            f_esc = r["form"].replace("'", "''")
            conds.append(f"UPPER(TRIM(p.FORM)) = '{f_esc}'")
        if r.get("segment"):
            sg_esc = r["segment"].replace("'", "''")
            conds.append(f"UPPER(TRIM(p.SEGMENT)) = '{sg_esc}'")

        if conds:
            rule_clauses.append("(" + " AND ".join(conds) + ")")

    return f"AND ({' OR '.join(rule_clauses)})" if rule_clauses else "AND 1=0"


def _aggregate_snowflake_pos_months(
    rows: list, base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Aggregates raw Snowflake POS weekly rows into 12 monthly totals ($M)."""
    base_m = [0.0] * 12
    plan_m = [0.0] * 12
    has_base = [False] * 12
    has_plan = [False] * 12

    for r in rows:
        yr = int(r[0])
        mo = int(r[1])
        val = float(r[2] or 0.0)
        if 1 <= mo <= 12:
            m_idx = mo - 1
            if yr == base_year:
                base_m[m_idx] += val
                has_base[m_idx] = True
            elif yr == plan_year:
                plan_m[m_idx] += val
                has_plan[m_idx] = True

    pos_base = [round(base_m[i] / 1e6, 4) if has_base[i] else None for i in range(12)]
    pos_plan_actual = [round(plan_m[i] / 1e6, 4) if has_plan[i] else None for i in range(12)]

    return pos_base, pos_plan_actual


def _detect_pos_cutoff_month(plan_year: int, pos_plan_actual: list[Optional[float]]) -> int:
    """Determines closed cutoff month for POS based on calendar and non-empty actuals."""
    env_cutoff = os.getenv("IBP_CUTOFF_MONTH")
    if env_cutoff and env_cutoff.isdigit():
        return int(env_cutoff)

    target_date = datetime.date.today() + datetime.timedelta(days=1)
    date_str = target_date.strftime("%Y-%m-%d")
    date_info = KenvueCalendar.get_date_info(date_str)
    cur_year = int(date_info.get("fiscal_year", target_date.year))
    cur_month = int(date_info.get("fiscal_month", target_date.month))

    cutoff = 0
    if plan_year == cur_year:
        max_possible = max(0, cur_month - 1)
        for i in range(max_possible):
            if pos_plan_actual[i] is not None:
                cutoff = i + 1
            else:
                break
    elif plan_year < cur_year:
        cutoff = 12
    return cutoff


def fetch_snowflake_monthly_pos(
    rules: list[dict[str, str]], base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]], int]:
    """Fetches base and plan actual POS from Snowflake and evaluates completeness."""
    if not rules:
        return [None] * 12, [None] * 12, 0

    rule_filter = _build_snowflake_pos_filter(rules)
    query = f"""
        SELECT
            cal.FISCAL_YEAR,
            cal.FISCAL_MONTH,
            SUM(f.DOLLAR_SALES) AS TOTAL_POS
        FROM PROD_DATALAKE.CONSUMPTION.FACT_POS_WEEKLY f
        JOIN PROD_DATALAKE.CONSUMPTION.DIM_RETAIL_CALENDAR cal
            ON f.WEEK_END_DATE = cal.WEEK_END_DATE
        JOIN PROD_DATALAKE.CONSUMPTION.DIM_PRODUCT dim_product
            ON f.PRODUCT_KEY = dim_product.PRODUCT_KEY
        WHERE cal.FISCAL_YEAR IN ({base_year}, {plan_year})
          {rule_filter}
        GROUP BY cal.FISCAL_YEAR, cal.FISCAL_MONTH
        ORDER BY cal.FISCAL_YEAR, cal.FISCAL_MONTH;
    """
    rows = []
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
    except Exception as e:
        logger.error("Snowflake consumption POS query error: %s", e)

    pos_base, pos_plan_actual = _aggregate_snowflake_pos_months(rows, base_year, plan_year)
    cutoff_month = _detect_pos_cutoff_month(plan_year, pos_plan_actual)

    for i in range(cutoff_month, 12):
        pos_plan_actual[i] = None

    return pos_base, pos_plan_actual, cutoff_month


def _aggregate_snowflake_gts_months(
    rows: list, base_year: int, plan_year: Optional[int]
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Aggregates raw Snowflake shipment rows into base and plan monthly GTS ($M)."""
    base_m = [0.0] * 12
    plan_m = [0.0] * 12
    has_base = [False] * 12
    has_plan = [False] * 12

    for r in rows:
        yr = int(r[0])
        mo = int(r[1])
        val = float(r[2] or 0.0)
        if 1 <= mo <= 12:
            m_idx = mo - 1
            if yr == base_year:
                base_m[m_idx] += val
                has_base[m_idx] = True
            elif plan_year and yr == plan_year:
                plan_m[m_idx] += val
                has_plan[m_idx] = True

    gts_base = [round(base_m[i] / 1e6, 4) if has_base[i] else None for i in range(12)]
    gts_plan_actual = [round(plan_m[i] / 1e6, 4) if has_plan[i] else None for i in range(12)]

    return gts_base, gts_plan_actual


def fetch_snowflake_monthly_gts(
    rules: list[dict[str, str]], base_year: int, plan_year: Optional[int] = None
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Queries Snowflake for Gross Trade Sales (GTS) aggregated across selected models."""
    if not rules:
        return [None] * 12, [None] * 12

    years = f"{base_year}, {plan_year}" if plan_year else str(base_year)
    rule_filter = _build_snowflake_gts_filter(rules)

    query = f"""
        SELECT
            cal.FISCAL_YEAR,
            cal.FISCAL_MONTH,
            SUM(f.GROSS_SALES_AMT) AS TOTAL_GTS
        FROM PROD_DATALAKE.SHIPMENT.FACT_SALES_MONTHLY f
        JOIN PROD_DATALAKE.SHIPMENT.DIM_FISCAL_CALENDAR cal
            ON f.CALENDAR_MONTH_KEY = cal.CALENDAR_MONTH_KEY
        JOIN PROD_DATALAKE.SHIPMENT.DIM_PRODUCT p
            ON f.PRODUCT_KEY = p.PRODUCT_KEY
        WHERE cal.FISCAL_YEAR IN ({years})
          {rule_filter}
        GROUP BY cal.FISCAL_YEAR, cal.FISCAL_MONTH
        ORDER BY cal.FISCAL_YEAR, cal.FISCAL_MONTH;
    """
    gts_base, gts_plan_actual = [None] * 12, [None] * 12
    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        gts_base, gts_plan_actual = _aggregate_snowflake_gts_months(rows, base_year, plan_year)
    except Exception as e:
        logger.error("Snowflake shipment GTS query error: %s", e)

    return gts_base, gts_plan_actual
