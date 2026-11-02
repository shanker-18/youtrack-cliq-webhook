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
- 9-Decimal high precision for all building blocks
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

# ─── Constant Definitions ─────────────────────────────────────────────────────

MATCH_KEY_BASE_TREND = "BASE TREND"
DRIVER_NET_INNOVATION = "Net Innovation"
DRIVER_NET_PRICE = "Net Price"
GROUP_IBP_OVERLAYS = "IBP Overlays"

# ─── Driver Definitions ───────────────────────────────────────────────────────

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
    ("Investment",   "Media",               "MEDIA"),
    ("Investment",   "Trade",               "TRADE"),
    ("Price",        DRIVER_NET_PRICE,      "COMPOUND_NET_PRICE"),
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Other",        "Club",                "CLUB"),
    ("Other",        "Other",               "OTHER"),
]

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
    env_year = os.getenv("IBP_PLAN_YEAR")
    if env_year and env_year.isdigit():
        plan_year = int(env_year)
    else:
        today_info = KenvueCalendar.get_date_info(datetime.date.today())
        plan_year = today_info.kv_year
    base_year = plan_year - 1
    return base_year, plan_year


def parse_month_num(val: Any) -> Optional[int]:
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
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]
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
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]
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
        final_indices[m] = round((sum(arr) / len(arr)), 9) if arr else 1.0
    return final_indices


def load_price_index_from_postgres(
    models: str | list[str]
) -> dict[int, float]:
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]
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


# ─── 4. PostgreSQL Live Building Blocks (9-Decimal Precision) ─────────────────

def _accumulate_consumption_bb_rows(rows: list[dict[str, Any]]) -> dict[str, list[Optional[float]]]:
    raw_bb: dict[str, list[Optional[float]]] = {}
    for r in rows:
        m_num = int(r["month_num"])
        if 1 <= m_num <= 12:
            m_idx = m_num - 1
            norm_bb = normalize_text(r["building_block"])
            val_m = round(float(r["value_in_thousands"] or 0.0) / 1000.0, 9)   # 9 Decimals
            raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] = round(
                (raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] or 0.0) + val_m, 9
            )
    return raw_bb


def _extract_consumption_driver_val(
    raw_bb: dict[str, list[Optional[float]]], pattern: str
) -> list[Optional[float]]:
    res: list[Optional[float]] = [None] * 12
    for db_name, m_arr in raw_bb.items():
        if pattern in db_name:
            for i in range(12):
                if m_arr[i] is not None:
                    res[i] = round((res[i] or 0.0) + m_arr[i], 9)
    return res


def _combine_monthly_drivers(
    a: list[Optional[float]], b: list[Optional[float]]
) -> list[Optional[float]]:
    res: list[Optional[float]] = [None] * 12
    for i in range(12):
        if a[i] is not None or b[i] is not None:
            res[i] = round((a[i] or 0.0) + (b[i] or 0.0), 9)
    return res


def load_live_consumption_building_blocks(
    models: Union[str, List[str], None], plan_year: int
) -> dict[str, list[Optional[float]]]:
    """Loads Consumption Building Blocks with full 9-decimal precision."""
    if not models:
        return {disp: [None] * 12 for _, disp, _ in CONSUMPTION_DRIVER_ROW_DEFINITIONS}

    if isinstance(models, str):
        model_list = [models.strip()] if models.strip() else []
    elif isinstance(models, list):
        model_list = [str(m).strip() for m in models if m]
    else:
        model_list = []

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
                WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' OR pc.is_active = TRUE)
                ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
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

    driver_data: dict[str, list[Optional[float]]] = {}
    for _, disp_name, match_key in CONSUMPTION_DRIVER_ROW_DEFINITIONS:
        if match_key == "COMPOUND_NET_INNOVATION":
            driver_data[disp_name] = _combine_monthly_drivers(innov, cann)
        elif match_key == "COMPOUND_NET_PRICE":
            driver_data[disp_name] = _combine_monthly_drivers(price, elast)
        else:
            driver_data[disp_name] = _extract_consumption_driver_val(raw_bb, match_key)

    return driver_data


def _clean_token(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _matches_shipment_driver(db_name: str, grp: str, disp_name: str, match_key: str) -> bool:
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
    matched = False
    monthly_accum = [0.0] * 12
    for r in rows:
        db_bb_name = str(r["driver_building_block"] or "")
        if _matches_shipment_driver(db_bb_name, grp, disp_name, match_key):
            matched = True
            for m_idx, col_name in enumerate(month_cols):
                monthly_accum[m_idx] += float(r[col_name] or 0.0)

    return [round(v, 9) for v in monthly_accum] if matched else [None] * 12


def load_live_shipment_building_blocks(
    models: Union[str, List[str], None], plan_year: int
) -> dict[Any, list[Optional[float]]]:
    """Queries live shipment building blocks from PostgreSQL (9-Decimal Precision)."""
    if not models:
        empty_res = {}
        for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
            empty_res[disp] = [None] * 12
            empty_res[(grp, disp)] = [None] * 12
            empty_res[f"{grp}_{disp}"] = [None] * 12
        return empty_res

    if isinstance(models, str):
        model_list = [models.strip()] if models.strip() else []
    elif isinstance(models, list):
        model_list = [str(m).strip() for m in models if m]
    else:
        model_list = []

    if not model_list:
        empty_res = {}
        for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
            empty_res[disp] = [None] * 12
            empty_res[(grp, disp)] = [None] * 12
            empty_res[f"{grp}_{disp}"] = [None] * 12
        return empty_res

    sql = """
    SELECT
        sbb.name AS building_block,
        EXTRACT(MONTH FROM spv.period_month)::int AS month_num,
        ROUND(SUM(spv.value_in_thousands) / 1000.0, 9) AS value_in_millions
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
                WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' OR pc.is_active = TRUE)
                ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )
    GROUP BY mm.model_name, sbb.name, month_num
    ORDER BY mm.model_name, sbb.name, month_num;
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
            if _matches_shipment_driver(db_bb_name, grp, disp_name, match_key):
                matched = True
                m_num = int(r.get("month_num") or 0)
                if 1 <= m_num <= 12:
                    val = float(r.get("value_in_millions") if r.get("value_in_millions") is not None else (float(r.get("value_in_thousands") or 0.0) / 1000.0))
                    monthly_accum[m_num - 1] += val

        final_vals = [round(v, 9) for v in monthly_accum] if matched else [None] * 12
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
    snap_id = row.get("snapshot_id") if isinstance(row, dict) else row["snapshot_id"]
    c_mo = row.get("cycle_month") if isinstance(row, dict) else None
    m_num = parse_month_num(c_mo) if c_mo else None
    return snap_id, m_num if (m_num and 1 <= m_num <= 12) else None


def _resolve_snapshot_pair(
    cur, table_name: str, plan_year: int, curr_filter: str, prior_filter: str
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    curr_id, c_mo = _query_cycle_snapshot(cur, table_name, plan_year, curr_filter)
    prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, prior_filter)
    if not prior_id and curr_id:
        prior_id, _ = _query_cycle_snapshot(cur, table_name, plan_year, "", prior_to_id=curr_id)
    return curr_id, prior_id, c_mo


def _query_fallback_cycle_month(cur, plan_year: int) -> Optional[int]:
    cur.execute("""
        SELECT pc.cycle_month
        FROM public.planning_cycles pc
        WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' OR pc.is_active = TRUE)
          AND (pc.planning_year_start = %s OR pc.planning_year_start IS NULL)
        ORDER BY pc.cycle_month DESC NULLS LAST
        LIMIT 1;
    """, (plan_year,))
    row = cur.fetchone()
    if row and isinstance(row, dict) and row.get("cycle_month"):
        m_num = parse_month_num(row["cycle_month"])
        if m_num and 1 <= m_num <= 12:
            return m_num
    return None


def get_cycle_snapshot_ids(plan_year: int) -> CycleSnapshotInfo:
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
    except Exception as e:
        logger.warning("Notice discovering cycle snapshot IDs: %s", e)

    if not active_cycle_month:
        try:
            today = datetime.date.today()
            d = today + datetime.timedelta(days=1) if today.weekday() == 6 else today
            d_info = KenvueCalendar.get_date_info(d)
            if d_info and d_info.kv_month_num and 1 <= d_info.kv_month_num <= 12:
                active_cycle_month = d_info.kv_month_num
        except Exception:
            pass
        if not active_cycle_month:
            active_cycle_month = datetime.date.today().month

    return CycleSnapshotInfo(curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id, active_cycle_month)


def _build_cycle_filter_clauses(
    is_prior: bool,
    curr_cs_id: Optional[int],
    prior_cs_id: Optional[int],
    curr_ss_id: Optional[int],
    prior_ss_id: Optional[int],
) -> tuple[str, str]:
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
                val_m = round(float(r["value_in_thousands"] or 0.0) / 1000.0, 9)
                monthly_data.setdefault(norm_name, {})[m_num] = round(
                    monthly_data.setdefault(norm_name, {}).get(m_num, 0.0) + val_m, 9
                )
    except Exception as e:
        logger.warning("Notice querying cycle building blocks (%s): %s", "Prior" if is_prior else "Current", e)

    return monthly_data


def _matches_coc_driver_name(db_bb_name: str, match_key: str) -> bool:
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
    result: dict[int, float] = {}
    for k, v in raw_data.items():
        if _matches_coc_driver_name(k, match_key):
            for m, val in v.items():
                result[m] = round(result.get(m, 0.0) + val, 9)
    return result


def _compute_single_driver_coc(
    match_key: str,
    current_raw: dict[str, dict[int, float]],
    prior_raw: dict[str, dict[int, float]],
    price_factors: dict[int, float],
) -> list[Optional[float]]:
    """Calculates monthly CoC deltas for a single driver scaled by price factor (9 Decimals)."""
    curr_dict = _aggregate_driver_raw_monthly(current_raw, match_key)
    prior_dict = _aggregate_driver_raw_monthly(prior_raw, match_key)
    res: list[Optional[float]] = [None] * 12
    has_any = False
    for m in range(1, 13):
        if m in curr_dict or m in prior_dict:
            curr_val = curr_dict.get(m, 0.0)
            prior_val = prior_dict.get(m, 0.0)
            pf = price_factors.get(m, 1.0)
            res[m - 1] = round((curr_val - prior_val) * pf, 9)
            has_any = True

    if has_any:
        return [0.0 if v is None else v for v in res]
    return [None] * 12


def _sum_monthly_pair(arr1: list, arr2: list, round_digits: int = 9) -> list[Optional[float]]:
    res: list[Optional[float]] = [None] * 12
    for i in range(12):
        if arr1[i] is not None or arr2[i] is not None:
            res[i] = round((arr1[i] or 0.0) + (arr2[i] or 0.0), round_digits)
    return res


def load_coc_building_blocks(
    models: str | list[str], plan_year: int, price_factors: dict[int, float]
) -> dict[str, list[Optional[float]]]:
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
        round_digits=9,
    )

    driver_data[DRIVER_NET_PRICE] = _sum_monthly_pair(
        driver_data.get("Price", [None] * 12),
        driver_data.get("Elasticity", [None] * 12),
        round_digits=9,
    )

    return driver_data


# ─── 6. Snowflake Ingestion (POS & GTS) ───────────────────────────────────────

def _build_snowflake_pos_filter(rules: list[dict[str, str]]) -> str:
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
            pos_base[i] = round(val_base_agg[i] / 1_000_000.0, 9)

        expected_weeks = KenvueCalendar.get_month_week_count(plan_year, month_num)
        actual_weeks = len(plan_weeks[month_num])
        if actual_weeks >= expected_weeks and actual_weeks > 0:
            pos_plan_actual[i] = round(val_plan_agg[i] / 1_000_000.0, 9)

    return pos_base, pos_plan_actual


def fetch_snowflake_monthly_pos(
    rules: list[dict[str, str]], base_year: int, plan_year: int
) -> tuple[list[Optional[float]], list[Optional[float]]]:
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
    gts_base: list[Optional[float]] = [None] * 12
    gts_plan_actual: list[Optional[float]] = [None] * 12
    for yr_val, mo_val, amt_val, _ in rows:
        yr = int(yr_val or 0)
        mo = int(mo_val or 0)
        if 1 <= mo <= 12:
            m_idx = mo - 1
            val_m = round(float(amt_val or 0.0) / 1_000_000.0, 9)
            if yr == base_year:
                gts_base[m_idx] = round((gts_base[m_idx] or 0.0) + val_m, 9)
            elif plan_year is not None and yr == plan_year:
                gts_plan_actual[m_idx] = round((gts_plan_actual[m_idx] or 0.0) + val_m, 9)
    return gts_base, gts_plan_actual


def fetch_snowflake_monthly_gts(
    rules: list[dict[str, str]], base_year: int, plan_year: Optional[int] = None
) -> tuple[list[Optional[float]], list[Optional[float]]]:
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
