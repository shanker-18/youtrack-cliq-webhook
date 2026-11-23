# pylint: disable=too-many-lines,too-many-locals,too-many-branches,broad-except
"""
NA IBP Planning Application -- Variance Dashboard Data Service
=============================================================
Handles PostgreSQL connectivity (via get_db_cursor) and snapshot discovery
for the Variance Dashboard:
1. Consumption Variance (POS Building Blocks delta)
2. Shipment Variance (Shipment Building Blocks delta)
Comparison Modes:
- IBP (Default): Current Cycle Building Block[m] - Prior Cycle (IBP-1) Building Block[m]
- BP:            Current Cycle Building Block[m] - Annual BP Baseline Building Block[m]
"""
import os
import re
import datetime
from typing import Optional, Dict, List, Any, NamedTuple
from database.connection import get_db_cursor
from services.kv_calendar import KenvueCalendar
from services.validation_service import normalize_text
from utils.logger import get_logger

logger = get_logger(__name__)

MONTH_NAME_MAP = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}

DRIVER_BASE_TREND = "Base Trend"
DRIVER_OTHER = "Other"
MATCH_KEY_BASE_TREND = "BASE TREND"
DRIVER_NET_INNOVATION = "Net Innovation"
DRIVER_NET_PRICE = "Net Price"
GROUP_IBP_OVERLAYS = "IBP Overlays"

CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS = [
    ("External",     DRIVER_BASE_TREND,     MATCH_KEY_BASE_TREND),
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
    ("Other",        DRIVER_OTHER,          "OTHER"),
]

SHIPMENT_VARIANCE_DRIVER_DEFINITIONS = [
    ("Inventory",         "Distribution",       "DISTRIBUTION"),
    ("Inventory",         "Innovation",         "INNOVATION"),
    ("Inventory",         "Trade",              "TRADE"),
    ("Inventory",         "Club",               "CLUB"),
    ("Inventory",         "Retailer Inventory", "RETAILER_INVENTORY"),
    ("Inventory",         DRIVER_OTHER,         "OTHER"),
    (GROUP_IBP_OVERLAYS,  "Supply Constraints", "SUPPLY_CONSTRAINTS"),
    (GROUP_IBP_OVERLAYS,  "Liquidations",       "LIQUIDATIONS"),
    (GROUP_IBP_OVERLAYS,  DRIVER_OTHER,         "OVERLAYS_OTHER"),
]


def get_active_years() -> tuple[int, int]:
    """Dynamically determines (base_year, plan_year) using Kenvue 4-4-5 Fiscal Calendar."""
    env_year = os.getenv("IBP_PLAN_YEAR")
    if env_year and env_year.isdigit():
        plan_year = int(env_year)
    else:
        today_info = KenvueCalendar.get_date_info(datetime.date.today())
        plan_year = today_info.kv_year
    return plan_year - 1, plan_year


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


class CycleSnapshotInfo(NamedTuple):
    curr_cs_id: Optional[int]
    prior_cs_id: Optional[int]
    curr_ss_id: Optional[int]
    prior_ss_id: Optional[int]
    bp_cs_id: Optional[int] = None
    bp_ss_id: Optional[int] = None
    active_cycle_month: Optional[int] = None


def _query_cycle_snapshot(
    cur: Any, table_name: str, year: int, snapshot_type_filter: str, prior_to_id: Optional[int] = None
) -> tuple[Optional[int], Optional[int]]:
    if prior_to_id is not None:
        sql = f"""
            SELECT s.snapshot_id, pc.cycle_month
            FROM public.{table_name} s
            JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
            WHERE s.snapshot_id < %s
              AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP'
              AND (pc.planning_year_start <= %s OR pc.planning_year_start IS NULL)
            ORDER BY pc.planning_year_start DESC NULLS LAST, pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
            LIMIT 1;
        """
        cur.execute(sql, (prior_to_id, year))
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
        cur.execute(sql, (year,))
    row = cur.fetchone()
    if not row:
        return None, None
    snap_id = row.get("snapshot_id") if isinstance(row, dict) else row["snapshot_id"]
    c_mo = row.get("cycle_month") if isinstance(row, dict) else None
    m_num = parse_month_num(c_mo) if c_mo else None
    return snap_id, m_num if (m_num and 1 <= m_num <= 12) else None


def _query_bp_snapshot(cur: Any, snap_table: str, rows_table: str, vals_table: str, year: int) -> Optional[int]:
    """Finds the BP snapshot ID that holds BP values for the requested year."""
    sql = f"""
        SELECT s.snapshot_id
        FROM public.{snap_table} s
        JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
        WHERE UPPER(COALESCE(pc.snapshot_type, '')) = 'BP'
          AND EXISTS (
              SELECT 1
              FROM public.{rows_table} r
              JOIN public.{vals_table} v ON v.row_id = r.row_id
              WHERE r.snapshot_id = s.snapshot_id
                AND r.is_deleted = FALSE
                AND EXTRACT(YEAR FROM v.period_month) = %s
          )
        ORDER BY pc.planning_year_start DESC NULLS LAST, s.snapshot_id DESC
        LIMIT 1;
    """
    cur.execute(sql, (year,))
    row = cur.fetchone()
    if not row:
        return None
    return row.get("snapshot_id") if isinstance(row, dict) else row["snapshot_id"]


def _resolve_snapshot_pair(
    cur, table_name: str, year: int, curr_filter: str, prior_filter: str
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    curr_id, c_mo = _query_cycle_snapshot(cur, table_name, year, curr_filter)
    prior_id, _ = _query_cycle_snapshot(cur, table_name, year, prior_filter)
    if (not prior_id or prior_id == curr_id) and curr_id:
        prior_id, _ = _query_cycle_snapshot(cur, table_name, year, "", prior_to_id=curr_id)
    return curr_id, prior_id, c_mo


def _resolve_active_cycle_month(c_mo: Optional[int], s_mo: Optional[int]) -> Optional[int]:
    """Resolves active cycle month from consumption/shipment or falls back to calendar."""
    active = c_mo or s_mo
    if active:
        return active
    try:
        d_info = KenvueCalendar.get_date_info(datetime.date.today())
        if d_info and d_info.kv_month_num and 1 <= d_info.kv_month_num <= 12:
            return d_info.kv_month_num
    except Exception:
        pass
    return datetime.date.today().month


def get_cycle_snapshot_ids(year: int) -> CycleSnapshotInfo:
    """Detects Current, Prior (IBP-1), and BP snapshot IDs scoped to year."""
    curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id = None, None, None, None
    bp_cs_id, bp_ss_id = None, None
    active_cycle_month = None
    curr_filter = (
        "(UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' "
        "OR (pc.is_active = TRUE AND UPPER(COALESCE(pc.snapshot_type, '')) != 'BP'))"
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
                cur, "consumption_snapshots", year, curr_filter, prior_filter
            )
            curr_ss_id, prior_ss_id, s_mo = _resolve_snapshot_pair(
                cur, "shipment_snapshots", year, curr_filter, prior_filter
            )
            bp_cs_id = _query_bp_snapshot(
                cur, "consumption_snapshots", "consumption_planning_rows", "consumption_planning_values", year
            )
            bp_ss_id = _query_bp_snapshot(
                cur, "shipment_snapshots", "shipment_planning_rows", "shipment_planning_values", year
            )
            active_cycle_month = _resolve_active_cycle_month(c_mo, s_mo)
    except Exception as e:
        logger.warning("Notice discovering cycle snapshot IDs for variance: %s", e)
    if not active_cycle_month:
        active_cycle_month = _resolve_active_cycle_month(None, None)
    return CycleSnapshotInfo(
        curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id, bp_cs_id, bp_ss_id, active_cycle_month
    )


def _resolve_consumption_snap_filter(snap_info: CycleSnapshotInfo, baseline_mode: str, year: int, snapshot_year: Optional[int]) -> Optional[str]:
    """Builds the SQL snapshot filter for consumption queries based on mode."""
    if baseline_mode == "BP":
        cycle_year = snapshot_year if snapshot_year is not None else year
        bp_cs_id = snap_info.bp_cs_id if cycle_year == year else get_cycle_snapshot_ids(year).bp_cs_id
        if bp_cs_id is None:
            return None
        return f"AND cpr.snapshot_id = {bp_cs_id}"
    if baseline_mode == "PRIOR":
        if snap_info.prior_cs_id is None:
            return None
        return f"AND cpr.snapshot_id = {snap_info.prior_cs_id}"
    if snap_info.curr_cs_id:
        return f"AND (cpr.snapshot_id = {snap_info.curr_cs_id} OR cpr.snapshot_id IS NULL)"
    return "AND cpr.snapshot_id IS NULL"


def _fetch_cycle_consumption_blocks(
    models: list[str], year: int, baseline_mode: str = "CURRENT", snapshot_year: Optional[int] = None
) -> tuple[dict[str, dict[int, float]], bool]:
    """
    Fetches consumption building blocks ($M POS) for year.
    baseline_mode: 'CURRENT', 'PRIOR', or 'BP'.
    Returns (monthly_data_dict, snapshot_found_flag).
    """
    monthly_data: dict[str, dict[int, float]] = {}
    if not models:
        return monthly_data, False
    model_list = [str(m).strip() for m in models if m]
    cycle_year = snapshot_year if snapshot_year is not None else year
    snap_info = get_cycle_snapshot_ids(cycle_year)
    cpr_snap_filter = _resolve_consumption_snap_filter(snap_info, baseline_mode, year, snapshot_year)
    if cpr_snap_filter is None:
        return monthly_data, False
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
    HAVING ABS(SUM(cpv.value_in_thousands)) > 1e-9;
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, year))
            for r in cur.fetchall():
                norm_name = normalize_text(r["building_block"])
                m_num = int(r["month_num"])
                val_m = float(r["value_in_thousands"] or 0.0) / 1000.0
                monthly_data.setdefault(norm_name, {})[m_num] = (
                    monthly_data.setdefault(norm_name, {}).get(m_num, 0.0) + val_m
                )
    except Exception as e:
        logger.warning("Notice querying consumption variance blocks (%s): %s", baseline_mode, e)
        return monthly_data, False
    return monthly_data, True


def _resolve_shipment_snap_filter(snap_info: CycleSnapshotInfo, baseline_mode: str, year: int, snapshot_year: Optional[int]) -> Optional[str]:
    """Builds the SQL snapshot filter for shipment queries based on mode."""
    if baseline_mode == "BP":
        cycle_year = snapshot_year if snapshot_year is not None else year
        bp_ss_id = snap_info.bp_ss_id if cycle_year == year else get_cycle_snapshot_ids(year).bp_ss_id
        if bp_ss_id is None:
            return None
        return f"AND spr.snapshot_id = {bp_ss_id}"
    if baseline_mode == "PRIOR":
        if snap_info.prior_ss_id is None:
            return None
        return f"AND spr.snapshot_id = {snap_info.prior_ss_id}"
    if snap_info.curr_ss_id:
        return f"AND (spr.snapshot_id = {snap_info.curr_ss_id} OR spr.snapshot_id IS NULL)"
    return "AND spr.snapshot_id IS NULL"


def _fetch_cycle_shipment_blocks(
    models: list[str], year: int, baseline_mode: str = "CURRENT", snapshot_year: Optional[int] = None
) -> tuple[dict[str, dict[int, float]], bool]:
    """
    Fetches shipment building blocks ($M GTS) for year.
    baseline_mode: 'CURRENT', 'PRIOR', or 'BP'.
    Returns (monthly_data_dict, snapshot_found_flag).
    """
    monthly_data: dict[str, dict[int, float]] = {}
    if not models:
        return monthly_data, False
    model_list = [str(m).strip() for m in models if m]
    cycle_year = snapshot_year if snapshot_year is not None else year
    snap_info = get_cycle_snapshot_ids(cycle_year)
    spr_snap_filter = _resolve_shipment_snap_filter(snap_info, baseline_mode, year, snapshot_year)
    if spr_snap_filter is None:
        return monthly_data, False
    sql = f"""
    SELECT
        sbb.section AS block_section,
        sbb.code AS block_code,
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
    GROUP BY sbb.section, sbb.code, sbb.name, month_num
    HAVING ABS(SUM(spv.value_in_thousands)) > 1e-9;
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql, (model_list, year))
            for r in cur.fetchall():
                norm_sec = normalize_text(r.get("block_section"))
                norm_code = normalize_text(r.get("block_code"))
                norm_name = normalize_text(r["building_block"])
                row_key = f"{norm_sec}::{norm_code}::{norm_name}" if (norm_sec or norm_code) else norm_name
                m_num = int(r["month_num"])
                val_m = float(r["value_in_thousands"] or 0.0) / 1000.0
                monthly_data.setdefault(row_key, {})[m_num] = (
                    monthly_data.setdefault(row_key, {}).get(m_num, 0.0) + val_m
                )
    except Exception as e:
        logger.warning("Notice querying shipment variance blocks (%s): %s", baseline_mode, e)
        return monthly_data, False
    return monthly_data, True


def _matches_consumption_driver_name(db_bb_name: str, match_key: str) -> bool:
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
    return matcher(norm) if matcher else (match_key in norm)


def _matches_shipment_section(norm_sec: str, norm_grp: str) -> bool:
    """Check if section matches the expected group."""
    return not norm_sec or norm_sec == norm_grp


def _matches_shipment_other(norm: str, code: str, sec: str, grp: str) -> bool:
    """Match logic for OTHER driver rows across Inventory and IBP Overlays."""
    if code in ("OTHER_INV", "INVENTORY_OTHER"):
        return grp != GROUP_IBP_OVERLAYS
    if code in ("OTHER_OVERLAY", "OVERLAY_OTHER", "OVERLAYS_OTHER"):
        return grp == GROUP_IBP_OVERLAYS
    if "OTHER" not in norm and "OTHER" not in code:
        return False
    if grp == GROUP_IBP_OVERLAYS:
        return ("OVERLAY" in norm) or ("OVERLAY" in code) or (sec == normalize_text(GROUP_IBP_OVERLAYS))
    return ("OVERLAY" not in norm) and ("OVERLAY" not in code)


def _matches_shipment_keyword(c_key: str, norm: str, code: str) -> bool:
    """Check known shipment keywords against name and code."""
    keywords = ["RETAILER", "RETAIL", "SUPPLY", "LIQUIDAT"]
    for kw in keywords:
        if kw in c_key and (kw in norm or kw in code):
            return True
    return False


def _matches_shipment_driver_name(db_bb_name: str, grp: str, match_key: str) -> bool:
    raw = str(db_bb_name or "")
    if "::" in raw:
        parts = raw.split("::", 2)
        sec = normalize_text(parts[0]) if len(parts) > 0 else ""
        code = normalize_text(parts[1]) if len(parts) > 1 else ""
        norm = normalize_text(parts[2]) if len(parts) > 2 else ""
    else:
        sec, code, norm = "", "", normalize_text(raw)
    norm_grp = normalize_text(grp)
    if not _matches_shipment_section(sec, norm_grp):
        return False
    c_key = normalize_text(match_key)
    if "OTHER" in c_key:
        return _matches_shipment_other(norm, code, sec, grp)
    if _matches_shipment_keyword(c_key, norm, code):
        return True
    return (c_key in norm) or (bool(code) and c_key in code)


def _compute_driver_variance_monthly(
    curr_dict: dict[int, float], base_dict: dict[int, float]
) -> list[Optional[float]]:
    """
    Computes delta: (Current Cycle - Baseline) WITHOUT Price Factor.
    - If neither cycle has planned data -> None (Blank cell)
    - If both values are explicitly 0.0 -> None (Blank cell)
    - If data exists and current == baseline -> 0.0
    """
    res: list[Optional[float]] = [None] * 12
    for m in range(1, 13):
        has_curr = m in curr_dict
        has_base = m in base_dict
        if not has_curr and not has_base:
            continue
        curr_val = curr_dict.get(m, 0.0)
        base_val = base_dict.get(m, 0.0)
        if abs(curr_val) < 1e-9 and abs(base_val) < 1e-9:
            continue
        res[m - 1] = round(curr_val - base_val, 9)
    return res


def _aggregate_consumption_driver(
    current_raw: dict, baseline_raw: dict, match_key: str
) -> list[Optional[float]]:
    """Aggregates and computes variance for a single consumption driver."""
    curr_dict: dict[int, float] = {}
    for k, v in current_raw.items():
        if _matches_consumption_driver_name(k, match_key):
            for m, val in v.items():
                curr_dict[m] = curr_dict.get(m, 0.0) + val
    base_dict: dict[int, float] = {}
    for k, v in baseline_raw.items():
        if _matches_consumption_driver_name(k, match_key):
            for m, val in v.items():
                base_dict[m] = base_dict.get(m, 0.0) + val
    return _compute_driver_variance_monthly(curr_dict, base_dict)


def _compute_compound_driver(v1: list, v2: list) -> list[Optional[float]]:
    """Sums two 12-month driver arrays preserving None semantics."""
    res = [None] * 12
    for i in range(12):
        if v1[i] is not None or v2[i] is not None:
            res[i] = round((float(v1[i]) if v1[i] is not None else 0.0) + (float(v2[i]) if v2[i] is not None else 0.0), 9)
    return res


def load_consumption_variance_drivers(
    models: str | list[str] | None, year: int, comparison_mode: str = "IBP", snapshot_year: Optional[int] = None
) -> tuple[dict[str, list[Optional[float]]], bool]:
    """
    Loads Consumption Variance drivers:
    - IBP: Current Cycle BB - Prior Cycle BB ($M POS)
    - BP:  Current Cycle BB - Annual BP Baseline BB ($M POS)
    Returns (driver_data, baseline_snapshot_exists).
    """
    empty_drivers = {disp: [None] * 12 for _, disp, _ in CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS}
    if not models:
        return empty_drivers, True
    model_list = [str(m).strip() for m in ([models] if isinstance(models, str) else models) if m]
    if not model_list:
        return empty_drivers, True
    mode = (comparison_mode or "IBP").upper()
    baseline_type = "BP" if mode == "BP" else "PRIOR"
    current_raw, _ = _fetch_cycle_consumption_blocks(
        model_list, year, baseline_mode="CURRENT", snapshot_year=snapshot_year
    )
    baseline_raw, has_baseline_snap = _fetch_cycle_consumption_blocks(
        model_list, year, baseline_mode=baseline_type, snapshot_year=snapshot_year
    )
    if mode == "BP" and not has_baseline_snap:
        return empty_drivers, False
    driver_data: dict[str, list[Optional[float]]] = {}
    for _, disp_name, match_key in CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        driver_data[disp_name] = _aggregate_consumption_driver(current_raw, baseline_raw, match_key)
    driver_data[DRIVER_NET_INNOVATION] = _compute_compound_driver(
        driver_data.get("Innovation", [None] * 12),
        driver_data.get("Cannibalization", [None] * 12),
    )
    driver_data[DRIVER_NET_PRICE] = _compute_compound_driver(
        driver_data.get("Price", [None] * 12),
        driver_data.get("Elasticity", [None] * 12),
    )
    return driver_data, has_baseline_snap


def _aggregate_shipment_driver(
    current_raw: dict, baseline_raw: dict, grp: str, match_key: str
) -> list[Optional[float]]:
    """Aggregates and computes variance for a single shipment driver."""
    curr_dict: dict[int, float] = {}
    for k, v in current_raw.items():
        if _matches_shipment_driver_name(k, grp, match_key):
            for m, val in v.items():
                curr_dict[m] = curr_dict.get(m, 0.0) + val
    base_dict: dict[int, float] = {}
    for k, v in baseline_raw.items():
        if _matches_shipment_driver_name(k, grp, match_key):
            for m, val in v.items():
                base_dict[m] = base_dict.get(m, 0.0) + val
    return _compute_driver_variance_monthly(curr_dict, base_dict)


def load_shipment_variance_drivers(
    models: str | list[str] | None, year: int, comparison_mode: str = "IBP", snapshot_year: Optional[int] = None
) -> tuple[dict[Any, list[Optional[float]]], bool]:
    """
    Loads Shipment Variance drivers:
    - IBP: Current Cycle BB - Prior Cycle BB ($M GTS)
    - BP:  Current Cycle BB - Annual BP Baseline BB ($M GTS)
    Returns (driver_data, baseline_snapshot_exists).
    """
    def _empty():
        res = {}
        for grp, disp, _ in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS:
            res[disp] = [None] * 12
            res[(grp, disp)] = [None] * 12
            res[f"{grp}_{disp}"] = [None] * 12
        return res

    if not models:
        return _empty(), True
    model_list = [str(m).strip() for m in ([models] if isinstance(models, str) else models) if m]
    if not model_list:
        return _empty(), True
    mode = (comparison_mode or "IBP").upper()
    baseline_type = "BP" if mode == "BP" else "PRIOR"
    current_raw, _ = _fetch_cycle_shipment_blocks(
        model_list, year, baseline_mode="CURRENT", snapshot_year=snapshot_year
    )
    baseline_raw, has_baseline_snap = _fetch_cycle_shipment_blocks(
        model_list, year, baseline_mode=baseline_type, snapshot_year=snapshot_year
    )
    if mode == "BP" and not has_baseline_snap:
        return _empty(), False
    driver_data: dict[Any, list[Optional[float]]] = {}
    for grp, disp_name, match_key in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS:
        m_vals = _aggregate_shipment_driver(current_raw, baseline_raw, grp, match_key)
        driver_data[disp_name] = m_vals
        driver_data[(grp, disp_name)] = m_vals
        driver_data[f"{grp}_{disp_name}"] = m_vals
    return driver_data, has_baseline_snap
