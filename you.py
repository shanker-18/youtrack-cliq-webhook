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
from typing import Optional, Dict, List, Tuple, Any, NamedTuple, Union
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
        target_date = datetime.date.today()
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
                pass

    base_year = plan_year - 1
    return base_year, plan_year


def parse_month_num(val: Any) -> Optional[int]:
    """Extracts month number (1..12) from dates, numbers, or month names."""
    if val is None:
        return None
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.month
    s = str(val).strip().upper()
    if s.isdigit():
        n = int(s)
        if 1 <= n <= 12:
            return n
    for k, v in MONTH_NAME_MAP.items():
        if k in s:
            return v
    m_iso = re.search(r"[-/](\d{1,2})", s)
    if m_iso:
        n = int(m_iso.group(1))
        if 1 <= n <= 12:
            return n
    return None


# ─── 2. PostgreSQL Hierarchy Mapping ──────────────────────────────────────────

def load_squads_and_models() -> dict[str, list[str]]:
    """Loads distinct squad (Need State) to model list mapping from PostgreSQL."""
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
    """Loads Shipment GTS hierarchy rules (C1..C5, B1..B2) for selected model(s)."""
    model_list = _normalize_models(models)
    if not model_list:
        return []

    sql = """
    SELECT
        g.code AS c1_business_segment,
        shm.business_subsegment AS c2_business_subsegment,
        shm.need_state AS c3_need_state,
        shm.category AS c4_category,
        shm.subcategory AS c5_subcategory,
        shm.brand_name AS b1_brand,
        shm.sub_brand_name AS b2_subbrand
    FROM public.shipment_hierarchy_mapping shm
    INNER JOIN public.master_models mm ON shm.model_id = mm.model_id
    INNER JOIN public.gbus g ON shm.gbu_id = g.gbu_id
    WHERE mm.model_name = ANY(%s) AND shm.is_active = TRUE;
    """
    rules = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list,))
            for r in cur.fetchall():
                rule = {
                    "C1_BUSINESS_SEGMENT": normalize_text(r.get("c1_business_segment")),
                    "C2_BUSINESS_SUBSEGMENT": normalize_text(r.get("c2_business_subsegment")),
                    "C3_NEED_STATE": normalize_text(r.get("c3_need_state")),
                    "C4_CATEGORY": normalize_text(r.get("c4_category")),
                    "C5_SUBCATEGORY": normalize_text(r.get("c5_subcategory")),
                    "B1_BRAND": normalize_text(r.get("b1_brand")),
                    "B2_SUBBRAND": normalize_text(r.get("b2_subbrand")),
                }
                if any(rule.values()):
                    rules.append(rule)
    except Exception as e:
        logger.error("Failed to load shipment model rules: %s", e)
    return rules


# ─── 3. PostgreSQL Model Price Index Multipliers ──────────────────────────────

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


# ─── 4. PostgreSQL Live Building Blocks ───────────────────────────────────────

def _accumulate_consumption_bb_rows(rows: list[dict[str, Any]]) -> dict[str, list[Optional[float]]]:
    """Accumulates monthly planning values in millions for consumption building blocks."""
    raw_bb: dict[str, list[Optional[float]]] = {}
    for r in rows:
        m_num = int(r["month_num"])
        if 1 <= m_num <= 12:
            m_idx = m_num - 1
            norm_bb = normalize_text(r["building_block"])
            val_m = float(r["value_in_thousands"] or 0.0) / 1000.0  # $K to $M
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
        AND (
            cpr.snapshot_id IS NULL
            OR cpr.snapshot_id = (
                SELECT s.snapshot_id
                FROM public.consumption_snapshots s
                JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
                WHERE (
                    UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%'
                    OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP')
                )
                ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )
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


def _matches_other_shipment_driver(
    c_db: str, c_code: str, c_sec: str, c_key: str, grp: str
) -> bool:
    """Matches 'OTHER' driver rows across Inventory and IBP Overlays sections."""
    result = False
    if c_code in ("OTHERINV", "INVENTORYOTHER"):
        result = grp == "Inventory"
    elif c_code in ("OTHEROVERLAY", "OVERLAYOTHER", "OVERLAYSOTHER"):
        result = grp == GROUP_IBP_OVERLAYS
    elif "OTHER" in c_db or "OTHER" in c_code:
        if "OVERLAY" in c_db or "IBP" in c_db or "OVERLAY" in c_code or c_sec == "IBPOVERLAYS":
            result = grp == GROUP_IBP_OVERLAYS
        elif "INVENT" in c_db or "INV" in c_code or c_sec == "INVENTORY":
            result = grp == "Inventory"
        else:
            result = (grp == "Inventory") if "OVERLAY" not in c_key else (grp == GROUP_IBP_OVERLAYS)
    return result


def _matches_shipment_driver(
    db_name: str,
    grp: str,
    disp_name: str,
    match_key: str,
    db_section: str = "",
    db_code: str = "",
) -> bool:
    """Matches a PostgreSQL building block (by section, code, and name) to a defined dashboard driver."""
    c_db = _clean_token(db_name)
    c_disp = _clean_token(disp_name)
    c_key = _clean_token(match_key)
    c_sec = _clean_token(db_section)
    c_code = _clean_token(db_code)
    c_grp = _clean_token(grp)
    if not c_db and not c_code:
        return False
    if c_sec and c_sec != c_grp:
        return False
    if c_disp == "OTHER":
        return _matches_other_shipment_driver(c_db, c_code, c_sec, c_key, grp)
    keywords = ["LIQUIDAT", "SUPPLY", "RETAIL", "DISTRIB", "INNOVAT", "TRADE", "CLUB"]
    if any(kw in c_key and (kw in c_db or kw in c_code) for kw in keywords):
        return True
    return bool(
        (c_key in c_db)
        or (c_disp in c_db)
        or (c_db and (c_db in c_key or c_db in c_disp))
        or (c_code and (c_key in c_code or c_code in c_key))
    )


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
    models: Union[str, List[str], None], plan_year: int
) -> dict[Any, list[Optional[float]]]:
    """
    Queries live shipment building blocks from PostgreSQL for current cycle.
    - If a model has building blocks: Returns entered and unentered months.
    - If a model has NO building blocks: All driver rows remain completely blank (None).
    """
    model_list = _normalize_models(models)

    if not model_list:
        empty_res = {}
        for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
            empty_res[disp] = [None] * 12
            empty_res[(grp, disp)] = [None] * 12
            empty_res[f"{grp}_{disp}"] = [None] * 12
        return empty_res

    sql = """
    SELECT
        sbb.section AS block_section,
        sbb.code AS block_code,
        sbb.name AS building_block,
        EXTRACT(MONTH FROM spv.period_month)::int AS month_num,
        ROUND(SUM(spv.value_in_thousands) / 1000.0, 4) AS value_in_millions
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
        AND (
            spr.snapshot_id IS NULL
            OR spr.snapshot_id = (
                SELECT s.snapshot_id
                FROM public.shipment_snapshots s
                JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
                WHERE (
                    UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%'
                    OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP')
                )
                ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )
    GROUP BY mm.model_name, sbb.section, sbb.code, sbb.name, month_num
    ORDER BY mm.model_name, sbb.section, sbb.name, month_num;
    """
    rows = []
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, plan_year))
            rows = cur.fetchall()
    except Exception as e:
        logger.error("Failed to load live shipment building blocks: %s", e)

    driver_data: dict[Any, list[Optional[float]]] = {}
    for grp, disp_name, match_key in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        matched = False
        monthly_accum = [0.0] * 12
        for r in rows:
            db_bb_name = str(r.get("building_block") or r.get("driver_building_block") or "")
            db_sec = str(r.get("block_section") or "")
            db_code = str(r.get("block_code") or "")
            if _matches_shipment_driver(db_bb_name, grp, disp_name, match_key, db_section=db_sec, db_code=db_code):
                matched = True
                m_num = int(r.get("month_num") or 0)
                if 1 <= m_num <= 12:
                    val = float(r.get("value_in_millions") if r.get("value_in_millions") is not None else (float(r.get("value_in_thousands") or 0.0) / 1000.0))
                    monthly_accum[m_num - 1] += val

        final_vals = [round(v, 4) for v in monthly_accum] if matched else [None] * 12
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
              AND (pc.planning_year_start <= %s OR pc.planning_year_start IS NULL)
              AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP'
            ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1;
        """
        cur.execute(sql, (prior_to_id, plan_year))
    else:
        sql = f"""
            SELECT s.snapshot_id, pc.cycle_month
            FROM public.{table_name} s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE ({snapshot_type_filter})
              AND (pc.planning_year_start <= %s OR pc.planning_year_start IS NULL)
            ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1;
        """
        cur.execute(sql, (plan_year,))
    row = cur.fetchone()
    if not row:
        return None, None
    snap_id = row.get("snapshot_id") if isinstance(row, dict) else row["snapshot_id"]
    c_mo = row.get("cycle_month") if isinstance(row, dict) else None
    m_num = parse_month_num(c_mo) if c_mo else None
    return snap_id, m_num if (m_num and 1 <= m_num <= 12) else None


def _resolve_snapshot_pair(
    cur, table_name: str, plan_year: int, curr_filter: str, prior_filter: str
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolves Current and Prior snapshot ID pair along with detected cycle month."""
    curr_id, c_mo = _query_cycle_snapshot(cur, table_name, plan_year, curr_filter)
    prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, prior_filter)
    if (not prior_id or prior_id == curr_id) and curr_id:
        prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, "", prior_to_id=curr_id)
    return curr_id, prior_id, c_mo


def _query_fallback_cycle_month(cur, plan_year: int) -> Optional[int]:
    """Queries latest active cycle month from planning_cycles table."""
    cur.execute("""
        SELECT pc.cycle_month
        FROM public.planning_cycles pc
        WHERE (
            UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%'
            OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP')
        )
          AND (pc.planning_year_start <= %s OR pc.planning_year_start IS NULL)
        ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST
        LIMIT 1;
    """, (plan_year,))
    row = cur.fetchone()
    if row and isinstance(row, dict) and row.get("cycle_month"):
        m_num = parse_month_num(row["cycle_month"])
        if m_num and 1 <= m_num <= 12:
            return m_num
    return None


def get_cycle_snapshot_ids(plan_year: int) -> CycleSnapshotInfo:
    """
    Detects Current and Prior snapshot IDs for Consumption and Shipment scoped to plan_year.
    Also discovers active_cycle_month (1..12) from planning_cycles.
    """
    curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id = None, None, None, None
    active_cycle_month = None

    curr_filter = (
        "UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' "
        "OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP')"
    )
    prior_filter = (
        "("
        "UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PRIOR%%' "
        "OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PREV%%' "
        "OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%IBP-1%%'"
        ") AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP'"
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
                    dt_info = KenvueCalendar.get_date_info(datetime.date.today())
                    if isinstance(dt_info, dict):
                        val = dt_info.get("fiscal_month") or dt_info.get("kv_month_num")
                        if val:
                            active_cycle_month = int(val)
                    elif hasattr(dt_info, "kv_month_num") and dt_info.kv_month_num:
                        active_cycle_month = int(dt_info.kv_month_num)
                    elif getattr(dt_info, "fiscal_month", None):
                        active_cycle_month = int(getattr(dt_info, "fiscal_month"))
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
                WHERE (
                    UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%'
                    OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP')
                )
                ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
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
                WHERE (
                    UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%'
                    OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP')
                )
                ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )"""
    else:
        cpr_filter = f"AND cpr.snapshot_id = {prior_cs_id}" if prior_cs_id else """AND cpr.snapshot_id = (
            SELECT s.snapshot_id
            FROM public.consumption_snapshots s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PRIOR%%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PREV%%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%IBP-1%%')
              AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP'
            ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1
        )"""
        spr_filter = f"AND spr.snapshot_id = {prior_ss_id}" if prior_ss_id else """AND spr.snapshot_id = (
            SELECT s.snapshot_id
            FROM public.shipment_snapshots s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PRIOR%%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%PREV%%'
                   OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%IBP-1%%')
              AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP'
            ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1
        )"""
    return cpr_filter, spr_filter


def _fetch_cycle_building_blocks(
    models: list[str], plan_year: int, is_prior: bool = False
) -> dict[str, dict[int, float]]:
    """
    Safely fetches raw monthly consumption building block values (in Thousands) from PostgreSQL.
    Excludes zero-only rows at extraction time via HAVING ABS(SUM(...)) > 1e-9.
    """
    monthly_data: dict[str, dict[int, float]] = {}
    if not models:
        return monthly_data

    model_list = [str(m).strip() for m in models if m]
    snap_info = get_cycle_snapshot_ids(plan_year)

    if is_prior and snap_info.prior_cs_id is None:
        return monthly_data

    cpr_snap_filter, _ = _build_cycle_filter_clauses(
        is_prior, snap_info.curr_cs_id, snap_info.prior_cs_id, snap_info.curr_ss_id, snap_info.prior_ss_id
    )

    sql = f"""
    -- Consumption Building Blocks only (exclude 0-only rows at extraction)
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
    HAVING ABS(SUM(cpv.value_in_thousands)) > 1e-9;
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, plan_year))
            for r in cur.fetchall():
                norm_name = normalize_text(r["building_block"])
                m_num = int(r["month_num"])
                val_m = float(r["value_in_thousands"] or 0.0) / 1000.0  # $K to $M
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
    for m in range(1, 13):
        has_curr = m in curr_dict
        has_prior = m in prior_dict

        if not has_curr and not has_prior:
            res[m - 1] = None
        else:
            curr_val = curr_dict.get(m, 0.0)
            prior_val = prior_dict.get(m, 0.0)

            # Both current and prior cycle values are 0 -> leave box empty
            if abs(curr_val) < 1e-9 and abs(prior_val) < 1e-9:
                res[m - 1] = None
            else:
                pf = price_factors.get(m, 1.0)
                res[m - 1] = round((curr_val - prior_val) * pf, 4)

    return res


def _sum_monthly_pair(arr1: list, arr2: list, round_digits: int = 4) -> list[Optional[float]]:
    """Sums two 12-month lists element-wise with rounding and None preservation."""
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
            res[i] = None
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
        if conds:
            rule_clauses.append("(" + " AND ".join(conds) + ")")
    return ("AND (" + " OR\n        ".join(rule_clauses) + ")") if rule_clauses else ""


def _aggregate_snowflake_pos_weeks(
    rows: list[Any], base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Aggregates weekly POS rows into 12-month base and plan actual arrays."""
    val_base_agg = [0.0] * 12
    val_plan_agg = [0.0] * 12
    has_base = [False] * 12
    plan_weeks: dict[int, set] = {m: set() for m in range(1, 13)}

    for r in rows:
        d_str = str(r[0]).strip()
        val = float(r[1] or 0.0)
        try:
            dt = datetime.datetime.strptime(d_str[:10], "%Y-%m-%d").date()
        except Exception:
            continue

        d_info = KenvueCalendar.get_date_info(dt)
        yr, m_nbr = d_info.kv_year, d_info.kv_month_num
        if yr == base_year and 1 <= m_nbr <= 12:
            val_base_agg[m_nbr - 1] += val
            has_base[m_nbr - 1] = True
        elif yr == plan_year and 1 <= m_nbr <= 12:
            val_plan_agg[m_nbr - 1] += val
            plan_weeks[m_nbr].add(dt)

    pos_base: list[Optional[float]] = [None] * 12
    pos_plan_actual: list[Optional[float]] = [None] * 12
    for i in range(12):
        month_num = i + 1
        if has_base[i]:
            pos_base[i] = val_base_agg[i] / 1_000_000.0

        expected_weeks = KenvueCalendar.get_month_week_count(plan_year, month_num)
        actual_weeks = len(plan_weeks[month_num])
        if actual_weeks >= expected_weeks and actual_weeks > 0:
            pos_plan_actual[i] = val_plan_agg[i] / 1_000_000.0

    return pos_base, pos_plan_actual


def fetch_snowflake_monthly_pos(
    rules: list[dict[str, str]], base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """
    Fetches POS $ for dynamic base_year and plan_year from Snowflake GLBL_SYNDCTD_FACT_DATA.
    Checks completeness against KenvueCalendar.get_month_week_count(plan_year, month_num).
    """
    pos_base: list[Optional[float]] = [None] * 12
    pos_plan_actual: list[Optional[float]] = [None] * 12
    if not rules:
        return pos_base, pos_plan_actual

    filter_sql = _build_snowflake_pos_filter(rules)
    if not filter_sql:
        return pos_base, pos_plan_actual

    st_base, _ = KenvueCalendar.get_cycle_bounds(base_year, 1)
    _, en_plan = KenvueCalendar.get_cycle_bounds(plan_year, 12)
    start_date_str = str(st_base)
    end_date_str = str(en_plan)

    c_db = config.SNOWFLAKE_VD_CONSUMPTION_DATABASE
    c_sch = config.SNOWFLAKE_VD_CONSUMPTION_SCHEMA

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
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        pos_base, pos_plan_actual = _aggregate_snowflake_pos_weeks(rows, base_year, plan_year)
    except Exception as e:
        logger.error("Snowflake monthly POS query error: %s", e)

    return pos_base, pos_plan_actual


def _build_snowflake_gts_where(rules: list[dict[str, str]]) -> str:
    """Constructs SQL WHERE clause across 7 hierarchy dimensions for shipment GTS query."""
    row_conditions = []
    ship_fields = [
        "C1_BUSINESS_SEGMENT", "C2_BUSINESS_SUBSEGMENT", "C3_NEED_STATE",
        "C4_CATEGORY", "C5_SUBCATEGORY", "B1_BRAND", "B2_SUBBRAND"
    ]
    for r in rules:
        field_conds = []
        for f in ship_fields:
            val = r.get(f, "").strip()
            if val and val not in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
                val_esc = val.replace("'", "''")
                field_conds.append(f"UPPER(TRIM(COALESCE({f}, ''))) = '{val_esc}'")
        if field_conds:
            row_conditions.append("(" + " AND ".join(field_conds) + ")")
    return " OR\n        ".join(row_conditions)


def _aggregate_snowflake_gts_months(
    rows: list[Any], base_year: int, plan_year: Optional[int]
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """Aggregates monthly GTS rows into base and plan actual arrays in millions."""
    gts_base: list[Optional[float]] = [None] * 12
    gts_plan_actual: list[Optional[float]] = [None] * 12
    for yr_val, mo_val, amt_val, _ in rows:
        yr = int(yr_val or 0)
        mo = int(mo_val or 0)
        if 1 <= mo <= 12:
            m_idx = mo - 1
            val_m = float(amt_val or 0.0) / 1_000_000.0  # Dollars to Millions ($M)
            if yr == base_year:
                gts_base[m_idx] = (gts_base[m_idx] or 0.0) + val_m
            elif plan_year is not None and yr == plan_year:
                gts_plan_actual[m_idx] = (gts_plan_actual[m_idx] or 0.0) + val_m
    return gts_base, gts_plan_actual


def fetch_snowflake_monthly_gts(
    rules: list[dict[str, str]], base_year: int, plan_year: Optional[int] = None
) -> tuple[list[Optional[float]], list[Optional[float]]]:
    """
    Queries VW_FACT_F360_SHIPMENTS in Snowflake.
    Returns:
      gts_base: 12 months of base_year GTS $ in Millions ($M)
      gts_plan_actual: 12 months of plan_year GTS $ in Millions ($M)
    """
    gts_base: list[Optional[float]] = [None] * 12
    gts_plan_actual: list[Optional[float]] = [None] * 12
    if not rules:
        return gts_base, gts_plan_actual

    where_clause = _build_snowflake_gts_where(rules)
    if not where_clause:
        return gts_base, gts_plan_actual

    year_filter = (
        f"YEAR IN ({base_year}, {plan_year})"
        if plan_year is not None else
        f"YEAR = {base_year}"
    )

    s_db = config.SNOWFLAKE_VD_SHIPMENT_DATABASE
    s_sch = config.SNOWFLAKE_VD_SHIPMENT_SCHEMA
    s_view = config.SNOWFLAKE_VD_SHIPMENT_VIEW

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
        gts_base, gts_plan_actual = _aggregate_snowflake_gts_months(rows, base_year, plan_year)
    except Exception as e:
        logger.error("Snowflake shipment GTS query error: %s", e)

    return gts_base, gts_plan_actual
