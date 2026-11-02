# pylint: disable=too-many-return-statements,too-many-nested-blocks,global-statement,too-many-lines
"""
NA IBP Planning Application - Validation Calculations Engine
============================================================
Authoritative calculation engine for both Consumption and Shipment validation:
- Uses services.kv_calendar.KenvueCalendar for pure 4-4-5 fiscal math (zero Excel dump dependency)
- Price Index lookups using openpyxl & fallback maps
- PostgreSQL Live Building Block additions (11 official POS adjustment blocks)
- Statistical 2-sigma outlier detection on Build metrics
- Pure Python implementation (zero pandas dependency)
"""

import os
import re
import math
import statistics
from datetime import date, datetime
from typing import Optional, Dict, List, Tuple, Any, Set
import psycopg2

from config import config
from database.connection import get_db_cursor
from services.kv_calendar import KenvueCalendar, MONTH_NAMES, MONTH_ABBR
from utils.constants import DRIVER_NET_INNOVATION, DRIVER_NET_PRICE
from utils.logger import get_logger

logger = get_logger(__name__)

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

MONTH_NUMBER_TO_3LETTER = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
}

MONTH_NAME_MAP = {
    "JAN": "JAN", "JANUARY": "JAN",
    "FEB": "FEB", "FEBRUARY": "FEB",
    "MAR": "MAR", "MARCH": "MAR",
    "APR": "APR", "APRIL": "APR",
    "MAY": "MAY",
    "JUN": "JUN", "JUNE": "JUN",
    "JUL": "JUL", "JULY": "JUL",
    "AUG": "AUG", "AUGUST": "AUG",
    "SEP": "SEP", "SEPTEMBER": "SEP",
    "OCT": "OCT", "OCTOBER": "OCT",
    "NOV": "NOV", "NOVEMBER": "NOV",
    "DEC": "DEC", "DECEMBER": "DEC",
}

# Official POS Adjustment Building Blocks
ALLOWED_BUILDING_BLOCKS = [
    "Base Trend",
    "Season",
    "Competition",
    "Distribution",
    DRIVER_NET_INNOVATION,
    "Discontinuations",
    "Renovation",
    "Media",
    "Trade",
    DRIVER_NET_PRICE,
    "Club",
    "Other",
]

RAW_BB_MAP = {
    "BASE TREND": "Base Trend",
    "SEASON": "Season",
    "COMPETITION": "Competition",
    "DISTRIBUTION": "Distribution",
    "INNOVATION": DRIVER_NET_INNOVATION,
    "CANNIBALIZATION": DRIVER_NET_INNOVATION,
    "NET INNOVATION": DRIVER_NET_INNOVATION,
    "DISCONTINUATIONS": "Discontinuations",
    "RENOVATION": "Renovation",
    "MEDIA": "Media",
    "TRADE": "Trade",
    "PRICE": DRIVER_NET_PRICE,
    "ELASTICITY": DRIVER_NET_PRICE,
    "NET PRICE": DRIVER_NET_PRICE,
    "CLUB": "Club",
    "OTHER": "Other",
}

_CACHED_PRICE_INDEX_MAP = None


def normalize_text(val: Any) -> str:
    """Normalize string consistently across Excel, PostgreSQL, and Snowflake."""
    if val is None:
        return ""
    s = str(val).replace("\xa0", " ").strip().upper()
    if s in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
        return ""
    return re.sub(r"\s+", " ", s)


def _normalize_numeric_month(val: Any) -> str:
    try:
        m_int = int(float(val))
        return MONTH_NUMBER_TO_3LETTER.get(m_int, "")
    except (ValueError, TypeError):
        return ""


def _parse_month_token(token: str) -> str:
    if token.isdigit():
        return MONTH_NUMBER_TO_3LETTER.get(int(token), "")
    for k, v in MONTH_NAME_MAP.items():
        if k in token:
            return v
    return ""


def _normalize_string_month(s: str) -> str:
    s_norm = normalize_text(s)
    if not s_norm:
        return ""
    if s_norm in MONTH_NAME_MAP:
        return MONTH_NAME_MAP[s_norm]
    parts = re.split(r"[\s\-_/]+", s_norm)
    for p in parts:
        res = _parse_month_token(p)
        if res:
            return res
    return ""


def normalize_month_3letter(val: Any) -> str:
    """Converts month representation (e.g. 1, '01', 'Jan', 'January', '2026-01-01') into 'JAN'..'DEC'."""
    if isinstance(val, (int, float)):
        return _normalize_numeric_month(val)
    return _normalize_string_month(str(val))


# --- 1. Kenvue Calendar 4-4-5 Fiscal Ranges via services.kv_calendar ---------

def get_kv_month_ranges(start_year: int = 2021, end_year: int = 2027) -> List[dict]:
    """Generates Kenvue Fiscal Month date ranges dynamically using KenvueCalendar."""
    ranges = []
    for yr in range(start_year, end_year + 1):
        for m_num in range(1, 13):
            info = KenvueCalendar.get_month_info(yr, m_num)
            ranges.append({
                "KV_YEAR": yr,
                "MONTH_NUMBER": m_num,
                "MONTH": MONTH_NAMES[m_num - 1].upper(),
                "START_DATE": info.start_date,
                "END_DATE": info.end_date,
                "NUM_WEEKS": info.num_weeks,
                "QUARTER": info.quarter,
            })
    return ranges


def map_date_to_kv_calendar(dt: date | datetime | str) -> Optional[Tuple[int, int, str]]:
    """Maps a date to (kv_year, kv_month_number, month_abbr)."""
    if dt is None:
        return None
    try:
        if isinstance(dt, str):
            dt_clean = dt.strip().split(" ")[0].split("T")[0]
            if "-" in dt_clean:
                d_obj = datetime.strptime(dt_clean, "%Y-%m-%d").date()
            elif "/" in dt_clean:
                d_obj = datetime.strptime(dt_clean, "%m/%d/%Y").date()
            else:
                return None
        elif isinstance(dt, datetime):
            d_obj = dt.date()
        elif isinstance(dt, date):
            d_obj = dt
        else:
            return None
        info = KenvueCalendar.get_date_info(d_obj)
        return info.kv_year, info.kv_month_num, info.kv_month_abbr.upper()
    except Exception as err:
        logger.debug("Error mapping date %s to KV Calendar: %s", dt, err)
        return None


def _update_latest_year(yr: int, latest_year: Optional[int]) -> int:
    return max(yr, latest_year) if latest_year is not None else yr


def _record_row_calendar_week(r: dict, weeks_by_m: dict, target_y: int, distinct_dates: set) -> None:
    dt_val = r.get("WEEK_DATE") or r.get("WEEK_START_DATE") or r.get("DATE") or r.get("PERIOD_DATE")
    if not dt_val:
        return
    res = map_date_to_kv_calendar(dt_val)
    if not res:
        return
    yr, m_num, _ = res
    if yr == target_y:
        distinct_dates.add(str(dt_val)[:10])
        weeks_by_m[m_num].add(str(dt_val)[:10])


def _record_row_completed_month(r: dict, weeks_by_m: dict, target_y: int) -> None:
    m_raw = r.get("MONTHNUMBER") or r.get("MONTH_NUMBER") or r.get("MONTH")
    if not m_raw:
        return
    m_3 = normalize_month_3letter(m_raw)
    if not (m_3 and m_3 in MONTHS):
        return
    m_num = MONTHS.index(m_3) + 1
    info = KenvueCalendar.get_month_info(target_y, m_num)
    for w in range(info.num_weeks):
        weeks_by_m[m_num].add(f"synth_wk_{w}")


def _collect_weeks_by_month(rows: List[dict], target_y: int) -> Tuple[Dict[int, Set[str]], Set[str]]:
    weeks_by_m = {m: set() for m in range(1, 13)}
    distinct_dates = set()
    for r in rows:
        y_raw = r.get("YEAR") or r.get("FISCAL_YEAR")
        try:
            r_yr = int(y_raw) if y_raw is not None else None
        except (ValueError, TypeError):
            r_yr = None

        if r_yr == target_y:
            _record_row_calendar_week(r, weeks_by_m, target_y, distinct_dates)
            if not distinct_dates:
                _record_row_completed_month(r, weeks_by_m, target_y)
    return weeks_by_m, distinct_dates


def _evaluate_month_completeness_details(
    target_y: int, weeks_by_m: Dict[int, Set[str]], has_explicit_dates: bool
) -> Tuple[Dict[int, dict], int]:
    month_details = {}
    latest_comp = 0
    for m in range(1, 13):
        info = KenvueCalendar.get_month_info(target_y, m)
        exp_w = info.num_weeks
        act_w = len(weeks_by_m[m])
        is_comp = (act_w >= exp_w) if has_explicit_dates else (act_w > 0)
        if is_comp:
            latest_comp = m
        month_details[m] = {
            "expected_weeks": exp_w,
            "actual_weeks_found": act_w,
            "is_complete": is_comp,
            "distinct_week_dates": sorted(list(weeks_by_m[m])),
        }
    return month_details, latest_comp


def get_kv_month_completeness_status(
    rows_consumption: List[dict],
    target_year: Optional[str | int] = None
) -> dict:
    """Dynamically determines the latest complete Kenvue month based on 4-4-5 calendar week counts."""
    latest_y = None
    for r in rows_consumption:
        y_val = r.get("YEAR") or r.get("FISCAL_YEAR")
        try:
            if y_val:
                latest_y = _update_latest_year(int(y_val), latest_y)
        except (ValueError, TypeError):
            pass

    target_y = int(target_year) if target_year else (latest_y or 2026)
    weeks_by_m, distinct_dates = _collect_weeks_by_month(rows_consumption, target_y)
    month_details, latest_comp = _evaluate_month_completeness_details(target_y, weeks_by_m, bool(distinct_dates))

    ytd_s = slice(0, latest_comp)
    ytg_s = slice(latest_comp, 12)

    return {
        "target_year": target_y,
        "latest_complete_m_nbr": latest_comp,
        "latest_complete_m_name": MONTH_NUMBER_TO_3LETTER.get(latest_comp),
        "ytd_slice": ytd_s,
        "ytg_slice": ytg_s,
        "month_details": month_details,
    }


# --- 2. Price Index Reference & Factory POS Calculations ---------------------

def _find_price_index_headers(rows: list) -> Tuple[Optional[int], Optional[int], Optional[int], int]:
    hdr_idx = 0
    for idx, r in enumerate(rows[:5]):
        row_str = [normalize_text(c) for c in r if c is not None]
        if any("MODEL" in s for s in row_str) and any("INDEX" in s or "PRICE" in s or "FACTOR" in s for s in row_str):
            hdr_idx = idx
            break
    hdr_row = [normalize_text(c) for c in rows[hdr_idx]]
    m_col, mo_col, idx_col = None, None, None
    for c_i, name in enumerate(hdr_row):
        if "MODEL" in name:
            m_col = c_i
        elif "MONTH" in name or "PERIOD" in name:
            mo_col = c_i
        elif "INDEX" in name or "PRICE" in name or "FACTOR" in name:
            idx_col = c_i
    return m_col, mo_col, idx_col, hdr_idx


def _parse_price_index_sheet_rows(rows: list, m_col: int, mo_col: int, idx_col: int, start_idx: int) -> dict:
    price_map = {}
    for r in rows[start_idx + 1:]:
        if len(r) <= max(m_col, mo_col, idx_col):
            continue
        m_val = normalize_text(r[m_col])
        mo_val = normalize_month_3letter(r[mo_col])
        val = r[idx_col]
        if m_val and mo_val:
            try:
                price_map[(mo_val, m_val)] = float(val) if val is not None else 1.0
            except (ValueError, TypeError):
                continue
    return price_map


def _load_price_index_from_excel(path: str) -> dict:
    import openpyxl  # pylint: disable=import-outside-toplevel
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return {}
    m_col, mo_col, idx_col, h_idx = _find_price_index_headers(rows)
    if m_col is None or mo_col is None or idx_col is None:
        return {}
    return _parse_price_index_sheet_rows(rows, m_col, mo_col, idx_col, h_idx)


def load_price_index_map(force_reload: bool = False) -> Dict[Tuple[str, str], float]:
    """Loads Price Index reference map keyed by (Month_3Letter, Model_Normalized) -> float multiplier."""
    global _CACHED_PRICE_INDEX_MAP
    if _CACHED_PRICE_INDEX_MAP is not None and not force_reload:
        return _CACHED_PRICE_INDEX_MAP

    paths_to_try = [
        getattr(config, "PRICE_INDEX_FILE_PATH", None),
        "Price Index.xlsx",
        os.path.join(os.path.dirname(__file__), "..", "Price Index.xlsx"),
        os.path.join(os.getcwd(), "Price Index.xlsx"),
    ]
    resolved_path = None
    for p in paths_to_try:
        if p and os.path.exists(p):
            resolved_path = p
            break

    if not resolved_path:
        logger.warning("Price Index.xlsx not found at candidate paths; defaulting to multiplier 1.0.")
        _CACHED_PRICE_INDEX_MAP = {}
        return _CACHED_PRICE_INDEX_MAP

    try:
        _CACHED_PRICE_INDEX_MAP = _load_price_index_from_excel(resolved_path)
    except Exception as err:
        logger.warning("Failed to parse Price Index file at %s: %s; using fallback.", resolved_path, err)
        _CACHED_PRICE_INDEX_MAP = {}

    return _CACHED_PRICE_INDEX_MAP


def get_factory_pos_val(month_num: int, model_name: str | list[str], pos_val: float | None) -> Tuple[float | None, float]:
    """Calculates Factory POS $ = POS $ * Price Index multiplier."""
    if pos_val is None:
        return None, 1.0
    norm_m = normalize_month_3letter(month_num)
    idx_map = load_price_index_map()
    if isinstance(model_name, (list, tuple, set)):
        clean_models = [normalize_text(m) for m in model_name if m]
        indices = [idx_map.get((norm_m, m), 1.0) for m in clean_models if (norm_m, m) in idx_map]
        index_val = (sum(indices) / len(indices)) if indices else 1.0
    else:
        norm_model = normalize_text(model_name)
        index_val = idx_map.get((norm_m, norm_model), 1.0)
    return float(pos_val) * index_val, index_val


# --- 3. Live PostgreSQL Building Block Planning Values -----------------------

def load_live_building_blocks(domain: str = "CONSUMPTION") -> List[Dict[str, Any]]:
    """
    Queries live PostgreSQL planning rows and values for active building blocks.
    Returns list of dicts: [{'model': ..., 'period_month': ..., 'building_block': ..., 'value_in_thousands': ...}].
    """
    table_prefix = "shipment" if domain.upper() == "SHIPMENT" else "consumption"
    sql = f"""
    SELECT
        hm.model_name AS model,
        DATE_TRUNC('month', pv.period_month)::date AS period_month,
        bb.name AS building_block,
        SUM(pv.value_in_thousands) AS value_in_thousands
    FROM public.{table_prefix}_planning_rows pr
    INNER JOIN public.{table_prefix}_building_blocks bb
        ON pr.building_block_id = bb.block_id
    INNER JOIN public.{table_prefix}_planning_values pv
        ON pr.row_id = pv.row_id
    INNER JOIN public.master_models hm
        ON pr.model_id = hm.model_id
    WHERE
        pr.is_deleted = FALSE
        AND bb.is_active = TRUE
        AND hm.is_active = TRUE
        AND (
            pr.snapshot_id IS NULL 
            OR pr.snapshot_id = (
                SELECT s.snapshot_id
                FROM public.{table_prefix}_snapshots s
                JOIN public.planning_cycles pc ON s.cycle_id = pc.cycle_id
                WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%%CURRENT%%' OR pc.is_active = TRUE)
                ORDER BY pc.cycle_month DESC NULLS LAST, s.snapshot_id DESC
                LIMIT 1
            )
        )
    GROUP BY
        hm.model_name,
        DATE_TRUNC('month', pv.period_month),
        bb.name
    ORDER BY
        hm.model_name,
        period_month,
        bb.name;
    """
    try:
        with get_db_cursor(commit=False) as cur:
            cur.execute(sql)
            raw_rows = cur.fetchall()
    except (psycopg2.Error, OSError, RuntimeError) as err:
        logger.warning("Could not query live building blocks: %s", err)
        return []

    result = []
    for r in raw_rows:
        result.append({
            "model": str(r["model"]).strip(),
            "period_month": r["period_month"],
            "building_block": str(r["building_block"]).strip(),
            "value_in_thousands": float(r["value_in_thousands"] or 0.0),
        })
    return result


def _matches_period(p_val: Any, year: int, month_nbr: int) -> bool:
    if not p_val:
        return False
    dt = map_date_to_kv_calendar(p_val)
    if dt:
        return dt[0] == year and dt[1] == month_nbr
    p_str = str(p_val).strip()
    return p_str.startswith(f"{year}-{month_nbr:02d}")


def _matches_consumption_bb_row(r: dict, norm_targets: Set[str], year: int, month_nbr: int) -> bool:
    if normalize_text(r.get("model", "")) not in norm_targets:
        return False
    b_raw = str(r.get("building_block", "")).strip()
    canon_b = RAW_BB_MAP.get(normalize_text(b_raw))
    if not canon_b or canon_b not in ALLOWED_BUILDING_BLOCKS:
        return False
    return _matches_period(r.get("period_month"), year, month_nbr)


def get_building_block_total_for_period(
    model_name: str | list[str],
    year: int,
    month_nbr: int,
    bb_rows: List[Dict[str, Any]]
) -> float:
    """Returns total active POS Building Block additions in thousands ($K) for period."""
    if not model_name or not bb_rows:
        return 0.0
    targets = [model_name] if isinstance(model_name, str) else model_name
    norm_targets = {normalize_text(m) for m in targets if m}
    return sum(
        float(r.get("value_in_thousands") or 0.0)
        for r in bb_rows
        if _matches_consumption_bb_row(r, norm_targets, year, month_nbr)
    )


SHIPMENT_ALLOWED_BUILDING_BLOCKS = [
    "Distribution",
    "Innovation",
    "Trade",
    "Club",
    "Retailer Inventory",
    "Supply Constraints",
    "Liquidations",
    "Other",
]


def map_shipment_bb_name(raw_name: str) -> Optional[str]:
    """Maps Shipment Building Block PostgreSQL names to standard logical names."""
    if not raw_name:
        return None
    norm = normalize_text(raw_name)
    if "DISTRIBUT" in norm:
        return "Distribution"
    if "INNOVAT" in norm:
        return "Innovation"
    if "TRADE" in norm:
        return "Trade"
    if "CLUB" in norm:
        return "Club"
    if "INVENT" in norm or "RETAIL" in norm:
        return "Retailer Inventory"
    if "SUPPLY" in norm:
        return "Supply Constraints"
    if "LIQUIDAT" in norm:
        return "Liquidations"
    if "OTHER" in norm or "OVERLAY" in norm or "IBP" in norm:
        return "Other"
    return str(raw_name).strip() if norm else None


def _matches_shipment_bb_row(r: Dict[str, Any], norm_targets: Set[str], year: int, month_nbr: int) -> bool:
    if normalize_text(r.get("model", "")) not in norm_targets:
        return False
    b_raw = str(r.get("building_block", "")).strip()
    canon_b = map_shipment_bb_name(b_raw)
    if not canon_b or canon_b not in SHIPMENT_ALLOWED_BUILDING_BLOCKS:
        return False
    return _matches_period(r.get("period_month"), year, month_nbr)


def get_shipment_building_block_total_for_period(
    model_name: str | list[str],
    year: int,
    month_nbr: int,
    bb_rows: List[Dict[str, Any]]
) -> float:
    """Returns total active Shipment Building Block additions in thousands ($K) for period."""
    if not model_name or not bb_rows:
        return 0.0
    targets = [model_name] if isinstance(model_name, str) else model_name
    norm_targets = {normalize_text(m) for m in targets if m}
    return sum(
        float(r.get("value_in_thousands") or 0.0)
        for r in bb_rows
        if _matches_shipment_bb_row(r, norm_targets, year, month_nbr)
    )


def _extract_row_year_and_month_idx(r: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
    yr = str(r.get("YEAR") or 0)
    m_raw = r.get("MONTHNUMBER") or r.get("MONTH_NUMBER") or r.get("MONTH")
    m_3 = normalize_month_3letter(m_raw)
    if not (yr.isdigit() and int(yr) >= 2022 and m_3 in MONTHS):
        return None, None
    return yr, MONTHS.index(m_3)


def _accumulate_pos_maps(
    r: Dict[str, Any],
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float]
) -> None:
    yr, m_idx = _extract_row_year_and_month_idx(r)
    if not yr or m_idx is None:
        return
    pv = r.get("POS_AMT") or r.get("POS_DOLLARS")
    pu = r.get("POS_QTY") or r.get("POS_UNITS")
    key = (yr, m_idx)
    if pv is not None:
        pos_val_map[key] = (pos_val_map.get(key) or 0.0) + float(pv)
    if pu is not None:
        pos_u_map[key] = (pos_u_map.get(key) or 0.0) + float(pu)


def _build_factory_pos_map(
    pos_val_map: Dict[Tuple[str, int], float],
    model_name: str | list[str]
) -> Dict[Tuple[str, int], float]:
    factory_pos_map = {}
    for (y_str, m_idx), pv_val in pos_val_map.items():
        f_pos, _ = get_factory_pos_val(m_idx + 1, model_name, pv_val)
        factory_pos_map[(str(y_str), m_idx)] = f_pos if f_pos is not None else pv_val
    return factory_pos_map


def extract_consumption_maps(
    rows_cons: List[Dict[str, Any]],
    model_name: str | list[str]
) -> Tuple[Dict[Tuple[str, int], float], Dict[Tuple[str, int], float], Dict[Tuple[str, int], float]]:
    """Extracts factory_pos_map, pos_val_map, pos_u_map from Snowflake consumption rows."""
    if not rows_cons:
        return {}, {}, {}
    pos_val_map: Dict[Tuple[str, int], float] = {}
    pos_u_map: Dict[Tuple[str, int], float] = {}
    for r in rows_cons:
        _accumulate_pos_maps(r, pos_val_map, pos_u_map)
    factory_pos_map = _build_factory_pos_map(pos_val_map, model_name)
    return factory_pos_map, pos_val_map, pos_u_map


# --- 4. Full Metrics Matrix Calculators ---------------------------------------

def calc_asp(pos_val: Optional[float], pos_units: Optional[float]) -> Optional[float]:
    if pos_val is None or pos_units is None or pos_units == 0:
        return None
    return round(float(pos_val) / float(pos_units), 2)


def calc_pct_var(current: Optional[float], base: Optional[float]) -> Optional[float]:
    if current is None or base is None or base == 0:
        return None
    return round(((float(current) - float(base)) / abs(float(base))) * 100.0, 1)


def calc_share(sub_val: Optional[float], total_val: Optional[float]) -> Optional[float]:
    if sub_val is None or total_val is None or total_val == 0:
        return None
    return round((float(sub_val) / float(total_val)) * 100.0, 1)


def _accumulate_year_consumption_metrics(
    r: Dict[str, Any], data_by_year: Dict[str, Dict[str, List[Optional[float]]]]
) -> None:
    yr, m_idx = _extract_row_year_and_month_idx(r)
    if not yr or m_idx is None:
        return
    if yr not in data_by_year:
        data_by_year[yr] = {"pos_val": [None] * 12, "factory_pos": [None] * 12, "pos_u": [None] * 12}
    amt = r.get("POS_AMT") or r.get("POS_DOLLARS")
    qty = r.get("POS_QTY") or r.get("POS_UNITS")
    if amt is not None:
        data_by_year[yr]["pos_val"][m_idx] = (data_by_year[yr]["pos_val"][m_idx] or 0.0) + float(amt)
    if qty is not None:
        data_by_year[yr]["pos_u"][m_idx] = (data_by_year[yr]["pos_u"][m_idx] or 0.0) + float(qty)


def _aggregate_consumption_sf_rows(rows_sf: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Optional[float]]]]:
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]] = {}
    for r in rows_sf:
        _accumulate_year_consumption_metrics(r, data_by_year)
    return data_by_year


def _extract_ytd_slice(comp_status: dict) -> slice:
    ytd_slice = comp_status.get("ytd_slice")
    if not isinstance(ytd_slice, slice):
        comp_m = comp_status.get("latest_complete_m_nbr") or 8
        ytd_slice = slice(0, comp_m)
    return ytd_slice


def _compute_projected_asp(
    data_by_year: dict, latest_year: str, prev_year: str, m_i: int, prev_yr_pos: float, ytd_slice: slice
) -> Optional[float]:
    asp_m = None
    prev_yr_u = data_by_year.get(prev_year, {}).get("pos_u", [None] * 12)[m_i]
    if prev_yr_u and prev_yr_u > 0:
        prev_asp = prev_yr_pos / prev_yr_u
        ytd_val_lat = sum(v for v in data_by_year[latest_year]["pos_val"][ytd_slice] if v is not None)
        ytd_u_lat = sum(v for v in data_by_year[latest_year]["pos_u"][ytd_slice] if v is not None)
        ytd_val_prv = sum(v for v in data_by_year.get(prev_year, {}).get("pos_val", [])[ytd_slice] if v is not None)
        ytd_u_prv = sum(v for v in data_by_year.get(prev_year, {}).get("pos_u", [])[ytd_slice] if v is not None)
        lat_asp_ytd = (ytd_val_lat / ytd_u_lat) if ytd_u_lat > 0 else 0.0
        prv_asp_ytd = (ytd_val_prv / ytd_u_prv) if ytd_u_prv > 0 else 0.0
        asp_trend = (lat_asp_ytd / prv_asp_ytd) if (lat_asp_ytd and prv_asp_ytd and prv_asp_ytd > 0) else 1.0
        asp_m = prev_asp * asp_trend
    return asp_m


def _project_consumption_future_months(
    data_by_year: dict,
    latest_year: str,
    prev_year: str,
    latest_year_int: int,
    latest_comp_m_nbr: int,
    model_name: str | list[str],
    comp_status: dict,
):
    if latest_comp_m_nbr >= 12:
        return
    try:
        bb_rows = load_live_building_blocks(domain="CONSUMPTION")
    except (psycopg2.Error, OSError, ValueError, KeyError):
        bb_rows = []

    ytd_slice = _extract_ytd_slice(comp_status)

    for m_n in range(latest_comp_m_nbr + 1, 13):
        m_i = m_n - 1
        prev_yr_pos = data_by_year.get(prev_year, {}).get("pos_val", [None] * 12)[m_i]
        tot_bb_k = get_building_block_total_for_period(model_name, latest_year_int, m_n, bb_rows)
        if prev_yr_pos is None and tot_bb_k == 0.0:
            continue
        base_val = prev_yr_pos if prev_yr_pos is not None else 0.0
        calc_pos_usd = base_val + (tot_bb_k * 1000.0)
        data_by_year[latest_year]["pos_val"][m_i] = calc_pos_usd

        f_pos, _ = get_factory_pos_val(m_n, model_name, calc_pos_usd)
        data_by_year[latest_year]["factory_pos"][m_i] = f_pos

        proj_asp = _compute_projected_asp(data_by_year, latest_year, prev_year, m_i, prev_yr_pos or 0.0, ytd_slice)
        if proj_asp and proj_asp > 0:
            data_by_year[latest_year]["pos_u"][m_i] = calc_pos_usd / proj_asp


def _calculate_single_year_consumption_metrics(
    d: dict, prev_yr_dec_pos: Optional[float], prev_yr_dec_asp: Optional[float]
) -> dict:
    asp = [None] * 12
    for i in range(12):
        c_asp = calc_asp(d["pos_val"][i], d["pos_u"][i])
        if c_asp is not None:
            asp[i] = c_asp
        elif i > 0:
            asp[i] = asp[i - 1]
        else:
            asp[i] = prev_yr_dec_asp

    build = [None] * 12
    for i in range(12):
        cur_p = d["pos_val"][i]
        prev_p = d["pos_val"][i - 1] if i > 0 else prev_yr_dec_pos
        if cur_p is not None and prev_p is not None and prev_p != 0:
            build[i] = round(cur_p / prev_p, 2)

    tot_p = sum(v for v in d["pos_val"] if v is not None and not (isinstance(v, float) and math.isnan(v)))
    share = [calc_share(d["pos_val"][i], tot_p) for i in range(12)]

    return {
        "pos_val": d["pos_val"],
        "factory_pos": d["factory_pos"],
        "pos_u": d["pos_u"],
        "asp": asp,
        "build": build,
        "share": share,
    }


def _calculate_consumption_year_metrics(
    data_by_year: dict, all_years: List[str]
) -> Dict[str, Dict[str, Any]]:
    year_metrics = {}
    prev_yr_dec_pos = None
    prev_yr_dec_asp = None
    for yr in all_years:
        d = data_by_year[yr]
        metrics = _calculate_single_year_consumption_metrics(d, prev_yr_dec_pos, prev_yr_dec_asp)
        year_metrics[yr] = metrics
        prev_yr_dec_pos = d["pos_val"][11]
        prev_yr_dec_asp = metrics["asp"][11]
    return year_metrics


def _detect_consumption_build_outliers(
    year_metrics: dict, latest_year: str, hist_years: List[str]
) -> Dict[int, Dict[str, Any]]:
    red_outliers = {}
    if not hist_years:
        return red_outliers
    for m_i in range(12):
        hist_vals = [
            year_metrics[h_yr]["build"][m_i]
            for h_yr in hist_years
            if h_yr in year_metrics and year_metrics[h_yr]["build"][m_i] is not None
        ]
        if len(hist_vals) >= 2:
            mean = statistics.mean(hist_vals)
            stdev = statistics.stdev(hist_vals)
            curr = year_metrics[latest_year]["build"][m_i]
            if curr is not None and (curr < (mean - 2 * stdev) or curr > (mean + 2 * stdev)):
                red_outliers[m_i] = {"mean": round(mean, 2), "stdev": round(stdev, 2), "value": curr}
    return red_outliers


def build_consumption_matrix(rows_sf: List[Dict[str, Any]], model_name: str | list[str]) -> Dict[str, Any]:
    """Computes complete Consumption Validation matrix from Snowflake weekly data and live DB building blocks."""
    if not rows_sf:
        return {}

    data_by_year = _aggregate_consumption_sf_rows(rows_sf)
    all_years = sorted([yr for yr in data_by_year if yr.isdigit() and int(yr) >= 2022])
    if not all_years:
        return {}

    latest_year = all_years[-1]
    prev_year = str(int(latest_year) - 1)
    latest_year_int = int(latest_year)
    hist_years = [str(latest_year_int - 5 + i) for i in range(5) if str(latest_year_int - 5 + i) in data_by_year]

    for yr_k in all_years:
        for m_i in range(12):
            pv_val = data_by_year[yr_k]["pos_val"][m_i]
            if pv_val is not None:
                f_pos, _ = get_factory_pos_val(m_i + 1, model_name, pv_val)
                data_by_year[yr_k]["factory_pos"][m_i] = f_pos

    comp_status = get_kv_month_completeness_status(rows_sf, target_year=latest_year)
    for yr_k in all_years:
        yr_comp = get_kv_month_completeness_status(rows_sf, target_year=yr_k)
        yr_m_details = yr_comp.get("month_details", {})
        for m_n in range(1, 13):
            if not yr_m_details.get(m_n, {}).get("is_complete", False):
                m_i = m_n - 1
                data_by_year[yr_k]["pos_val"][m_i] = None
                data_by_year[yr_k]["pos_u"][m_i] = None
                data_by_year[yr_k]["factory_pos"][m_i] = None

    _project_consumption_future_months(
        data_by_year, latest_year, prev_year, latest_year_int, comp_status["latest_complete_m_nbr"], model_name, comp_status
    )
    year_metrics = _calculate_consumption_year_metrics(data_by_year, all_years)
    red_outliers = _detect_consumption_build_outliers(year_metrics, latest_year, hist_years)

    return {
        "all_years": all_years,
        "latest_year": latest_year,
        "prev_year": prev_year,
        "year_metrics": year_metrics,
        "comp_status": comp_status,
        "red_outliers": red_outliers,
        "data_by_year": data_by_year,
    }


def _is_valid_numeric_val(val: Any) -> bool:
    return val is not None and not (isinstance(val, float) and (math.isnan(val) or math.isinf(val)))


def _accumulate_shipment_row(
    r: Dict[str, Any], data_by_year: Dict[str, Dict[str, List[Optional[float]]]]
) -> None:
    yr = str(r.get("YEAR") or 0)
    m_nbr = int(r.get("MONTHNUMBER") or 0)
    if not yr.isdigit() or int(yr) < 2022 or m_nbr < 1 or m_nbr > 12:
        return
    m_idx = m_nbr - 1
    if yr not in data_by_year:
        data_by_year[yr] = {"gts_val": [None] * 12, "gts_qty": [None] * 12}
    amt_raw = r.get("GTS_AMT")
    qty_raw = r.get("GTS_QTY")
    if _is_valid_numeric_val(amt_raw):
        data_by_year[yr]["gts_val"][m_idx] = (data_by_year[yr]["gts_val"][m_idx] or 0.0) + float(amt_raw)
    if _is_valid_numeric_val(qty_raw):
        q_num = float(qty_raw)
        data_by_year[yr]["gts_qty"][m_idx] = (data_by_year[yr]["gts_qty"][m_idx] or 0.0) + (abs(q_num) if q_num != 0 else 0.0)


def _aggregate_shipment_sf_rows(rows_ship: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Optional[float]]]]:
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]] = {}
    for r in rows_ship:
        _accumulate_shipment_row(r, data_by_year)
    return data_by_year


def _compute_prev_year_fy_price_factor(
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]],
    prev_year: str,
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
) -> float:
    if prev_year not in data_by_year:
        return 1.0
    prev_usd_arr = [v for v in data_by_year[prev_year]["gts_val"] if v is not None and not (isinstance(v, float) and math.isnan(v))]
    prev_qty_arr = [v for v in data_by_year[prev_year]["gts_qty"] if v is not None and not (isinstance(v, float) and math.isnan(v))]
    prev_pos_val_arr = [pos_val_map.get((str(prev_year), i)) for i in range(12) if pos_val_map.get((str(prev_year), i)) is not None]
    prev_pos_u_arr = [pos_u_map.get((str(prev_year), i)) for i in range(12) if pos_u_map.get((str(prev_year), i)) is not None]

    tot_prev_usd = sum(prev_usd_arr) if prev_usd_arr else 0.0
    tot_prev_qty = sum(prev_qty_arr) if prev_qty_arr else 0.0
    tot_prev_pos_val = sum(prev_pos_val_arr) if prev_pos_val_arr else 0.0
    tot_prev_pos_u = sum(prev_pos_u_arr) if prev_pos_u_arr else 0.0

    asp_prev_fy = (tot_prev_pos_val / tot_prev_pos_u) if (tot_prev_pos_val > 0 and tot_prev_pos_u > 0) else None
    b3_prev_fy = (tot_prev_usd / tot_prev_qty) if (tot_prev_usd > 0 and tot_prev_qty > 0) else None
    if asp_prev_fy and b3_prev_fy and b3_prev_fy != 0:
        return asp_prev_fy / b3_prev_fy
    return 1.0


def _resolve_month_factory_pos(
    latest_year: str,
    prev_year: str,
    m_i: int,
    m_nbr: int,
    model_name: str | list[str],
    factory_pos_map: Dict[Tuple[str, int], float],
    pos_val_map: Dict[Tuple[str, int], float],
    cons_bb_rows: Optional[List[Dict[str, Any]]] = None,
) -> float:
    factory_pos = factory_pos_map.get((str(latest_year), m_i))
    if factory_pos is not None:
        return factory_pos

    prev_pos_val = pos_val_map.get((str(prev_year), m_i))

    if cons_bb_rows is None:
        try:
            cons_bb_rows = load_live_building_blocks(domain="CONSUMPTION")
        except (psycopg2.Error, OSError, ValueError, KeyError):
            cons_bb_rows = []

    latest_year_int = int(latest_year) if str(latest_year).isdigit() else 2026
    tot_cons_bb_k = get_building_block_total_for_period(model_name, latest_year_int, m_nbr, cons_bb_rows)
    tot_cons_bb_usd = (tot_cons_bb_k * 1000.0) if tot_cons_bb_k else 0.0

    if prev_pos_val is not None:
        projected_plan_pos = prev_pos_val + tot_cons_bb_usd
        f_pos_calc, _ = get_factory_pos_val(m_nbr, model_name, projected_plan_pos)
        factory_pos = f_pos_calc if f_pos_calc is not None else projected_plan_pos
    elif tot_cons_bb_usd > 0:
        f_pos_calc, _ = get_factory_pos_val(m_nbr, model_name, tot_cons_bb_usd)
        factory_pos = f_pos_calc if f_pos_calc is not None else tot_cons_bb_usd
    else:
        factory_pos = 0.0

    factory_pos_map[(str(latest_year), m_i)] = factory_pos
    return factory_pos


def _resolve_month_asp(
    latest_year: str,
    prev_year: str,
    m_i: int,
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
) -> Optional[float]:
    p_val_m = pos_val_map.get((str(latest_year), m_i))
    p_u_m = pos_u_map.get((str(latest_year), m_i))
    if p_val_m and p_u_m and p_u_m != 0:
        return p_val_m / p_u_m

    if prev_year:
        p_val_prev = pos_val_map.get((str(prev_year), m_i))
        p_u_prev = pos_u_map.get((str(prev_year), m_i))
        if p_val_prev and p_u_prev and p_u_prev != 0:
            return p_val_prev / p_u_prev

    return None


def _project_shipment_future_months(
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]],
    latest_year: str,
    prev_year: str,
    latest_comp_m_nbr: int,
    factory_pos_map: Dict[Tuple[str, int], float],
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
    fy_price_factor_prev: float,
    model_name: str | list[str],
    bb_rows: Optional[List[Dict[str, Any]]],
    cons_bb_rows: Optional[List[Dict[str, Any]]] = None,
):
    if latest_comp_m_nbr >= 12:
        return
    if bb_rows is None:
        try:
            bb_rows = load_live_building_blocks(domain="SHIPMENT")
        except (psycopg2.Error, OSError, ValueError, KeyError):
            bb_rows = []
    if cons_bb_rows is None:
        try:
            cons_bb_rows = load_live_building_blocks(domain="CONSUMPTION")
        except (psycopg2.Error, OSError, ValueError, KeyError):
            cons_bb_rows = []

    for m_i in range(latest_comp_m_nbr, 12):
        m_nbr = m_i + 1
        factory_pos = _resolve_month_factory_pos(
            latest_year, prev_year, m_i, m_nbr, model_name, factory_pos_map, pos_val_map, cons_bb_rows
        )
        bb_total_k = get_shipment_building_block_total_for_period(model_name, int(latest_year), m_nbr, bb_rows)
        calc_grs_usd = factory_pos + ((bb_total_k * 1000.0) if bb_total_k else 0.0)
        data_by_year[latest_year]["gts_val"][m_i] = calc_grs_usd

        asp_m = _resolve_month_asp(latest_year, prev_year, m_i, pos_val_map, pos_u_map)
        b3_proj = (asp_m / fy_price_factor_prev) if (asp_m and fy_price_factor_prev != 0) else None
        if calc_grs_usd is not None and b3_proj and b3_proj != 0:
            data_by_year[latest_year]["gts_qty"][m_i] = calc_grs_usd / b3_proj


def _calc_single_yr_b3(
    gts_val: List[Optional[float]],
    gts_qty: List[Optional[float]],
    yr: str,
    prev_year: str,
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
    fy_price_factor_prev: float,
) -> List[Optional[float]]:
    b3_arr = [None] * 12
    for m_i in range(12):
        gs = gts_val[m_i]
        gu = gts_qty[m_i]
        if gs is not None and gu is not None and gu != 0:
            b3_arr[m_i] = gs / gu
        else:
            asp_m = _resolve_month_asp(yr, prev_year, m_i, pos_val_map, pos_u_map)
            b3_arr[m_i] = (asp_m / fy_price_factor_prev) if (asp_m is not None and fy_price_factor_prev != 0) else None
    return b3_arr


def _calc_single_yr_build_bleed(
    gts_val: List[Optional[float]],
    yr: str,
    factory_pos_map: Dict[Tuple[str, int], float],
) -> List[Optional[float]]:
    build_bleed_arr = [None] * 12
    for m_i in range(12):
        gs = gts_val[m_i]
        fp = factory_pos_map.get((str(yr), m_i))
        if gs is not None and not (isinstance(gs, float) and math.isnan(gs)):
            build_bleed_arr[m_i] = (gs - fp) if (fp is not None and not (isinstance(fp, float) and math.isnan(fp))) else gs
        elif fp is not None and not (isinstance(fp, float) and math.isnan(fp)):
            build_bleed_arr[m_i] = 0.0 - fp
        else:
            build_bleed_arr[m_i] = 0.0
    return build_bleed_arr


def _calc_single_yr_unit_ratio(
    gts_val: List[Optional[float]],
    gts_qty: List[Optional[float]],
    yr: str,
    prev_year: str,
    pos_u_map: Dict[Tuple[str, int], float],
) -> List[Optional[float]]:
    unit_ratio_arr = [None] * 12
    for m_i in range(12):
        gs = gts_val[m_i]
        if gs is None or gs == 0 or (isinstance(gs, float) and math.isnan(gs)):
            unit_ratio_arr[m_i] = None
            continue
        g_u = gts_qty[m_i]
        p_u = pos_u_map.get((str(yr), m_i))
        if p_u is None and prev_year:
            p_u = pos_u_map.get((str(prev_year), m_i))
        if g_u is not None and p_u and p_u != 0:
            unit_ratio_arr[m_i] = round(g_u / p_u, 2)
        else:
            unit_ratio_arr[m_i] = None
    return unit_ratio_arr


def _calc_single_yr_price_factor(
    b3_arr: List[Optional[float]],
    yr: str,
    prev_year: str,
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
) -> List[Optional[float]]:
    price_factor_arr = [None] * 12
    for m_i in range(12):
        b3_val = b3_arr[m_i]
        asp_m = _resolve_month_asp(yr, prev_year, m_i, pos_val_map, pos_u_map)
        if asp_m and b3_val and b3_val != 0:
            price_factor_arr[m_i] = round(asp_m / b3_val, 2)
        else:
            price_factor_arr[m_i] = None
    return price_factor_arr


def _calculate_shipment_single_year_metrics(
    yr: str,
    d: Dict[str, List[Optional[float]]],
    prev_year: str,
    factory_pos_map: Dict[Tuple[str, int], float],
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
    fy_price_factor_prev: float,
) -> Dict[str, Any]:
    b3_arr = _calc_single_yr_b3(d["gts_val"], d["gts_qty"], yr, prev_year, pos_val_map, pos_u_map, fy_price_factor_prev)
    build_bleed_arr = _calc_single_yr_build_bleed(d["gts_val"], yr, factory_pos_map)
    unit_ratio_arr = _calc_single_yr_unit_ratio(d["gts_val"], d["gts_qty"], yr, prev_year, pos_u_map)
    price_factor_arr = _calc_single_yr_price_factor(b3_arr, yr, prev_year, pos_val_map, pos_u_map)

    return {
        "gts_val": d["gts_val"],
        "gts_qty": d["gts_qty"],
        "b3": b3_arr,
        "build_bleed": build_bleed_arr,
        "unit_ratio": unit_ratio_arr,
        "price_factor": price_factor_arr,
    }


def _evaluate_month_unit_ratio_outlier(
    m_i: int,
    ref_vals: List[float],
    year_metrics: Dict[str, Dict[str, Any]],
    latest_year: str,
    unit_ratio_outliers: Dict[int, Dict[str, Any]]
) -> None:
    if len(ref_vals) < 2:
        return
    m_mean = statistics.mean(ref_vals)
    m_sd = statistics.stdev(ref_vals)
    curr_ur = year_metrics[latest_year]["unit_ratio"][m_i]
    if curr_ur is not None and (curr_ur < (m_mean - 2 * m_sd) or curr_ur > (m_mean + 2 * m_sd)):
        unit_ratio_outliers[m_i] = {"mean": round(m_mean, 2), "stdev": round(m_sd, 2), "value": curr_ur}


def _detect_unit_ratio_outliers(
    year_metrics: Dict[str, Dict[str, Any]],
    latest_year: str,
    ref_years: List[str],
) -> Dict[int, Dict[str, Any]]:
    unit_ratio_outliers: Dict[int, Dict[str, Any]] = {}
    if not ref_years or latest_year not in year_metrics:
        return unit_ratio_outliers

    for m_i in range(12):
        ref_vals = [
            year_metrics[y]["unit_ratio"][m_i]
            for y in ref_years
            if y in year_metrics and year_metrics[y]["unit_ratio"][m_i] is not None
        ]
        _evaluate_month_unit_ratio_outlier(m_i, ref_vals, year_metrics, latest_year, unit_ratio_outliers)

    return unit_ratio_outliers


def _detect_shipment_cutoff_month(latest_year: str, gts_vals: List[Optional[float]]) -> int:
    cutoff = 8 if latest_year == "2026" else 12
    for i in range(11, -1, -1):
        if gts_vals[i] is not None and not (isinstance(gts_vals[i], float) and math.isnan(gts_vals[i])):
            cutoff = i + 1
            break
    return cutoff


def _blend_factory_pos_override(
    factory_pos_map: Dict[Tuple[str, int], float],
    factory_pos_by_year: Optional[Dict[str, List[Optional[float]]]],
) -> None:
    if not factory_pos_by_year:
        return
    for yr_k, fp_list in factory_pos_by_year.items():
        for m_i, val in enumerate(fp_list):
            if val is not None:
                factory_pos_map[(str(yr_k), m_i)] = val


def build_shipment_matrix(
    rows_ship: List[Dict[str, Any]],
    model_name: str | list[str],
    factory_pos_by_year: Optional[Dict[str, List[Optional[float]]]] = None,
    rows_cons: Optional[List[Dict[str, Any]]] = None,
    bb_rows: Optional[List[Dict[str, Any]]] = None,
    cons_bb_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Computes complete Shipment Validation matrix matching validation/ship.py specifications."""
    if not rows_ship:
        return {}

    data_by_year = _aggregate_shipment_sf_rows(rows_ship)
    all_years = sorted([yr for yr in data_by_year if yr.isdigit() and int(yr) >= 2022])
    if not all_years:
        return {}

    latest_year = all_years[-1]
    prev_year = str(int(latest_year) - 1)
    ref_years = [y for y in all_years if y < latest_year][-4:]

    factory_pos_map, pos_val_map, pos_u_map = extract_consumption_maps(rows_cons, model_name) if rows_cons else ({}, {}, {})
    _blend_factory_pos_override(factory_pos_map, factory_pos_by_year)

    fy_price_factor_prev = _compute_prev_year_fy_price_factor(data_by_year, prev_year, pos_val_map, pos_u_map)
    latest_comp_m_nbr = _detect_shipment_cutoff_month(latest_year, data_by_year[latest_year]["gts_val"])

    _project_shipment_future_months(
        data_by_year,
        latest_year,
        prev_year,
        latest_comp_m_nbr,
        factory_pos_map,
        pos_val_map,
        pos_u_map,
        fy_price_factor_prev,
        model_name,
        bb_rows,
        cons_bb_rows,
    )

    year_metrics = {
        yr: _calculate_shipment_single_year_metrics(yr, data_by_year[yr], prev_year, factory_pos_map, pos_val_map, pos_u_map, fy_price_factor_prev)
        for yr in all_years
    }
    unit_ratio_outliers = _detect_unit_ratio_outliers(year_metrics, latest_year, ref_years)

    comp_status = {
        "latest_complete_m_nbr": latest_comp_m_nbr,
        "ytd_slice": [0, latest_comp_m_nbr],
        "ytg_slice": [latest_comp_m_nbr, 12],
    }

    return {
        "all_years": all_years,
        "latest_year": latest_year,
        "prev_year": prev_year,
        "year_metrics": year_metrics,
        "comp_status": comp_status,
        "unit_ratio_outliers": unit_ratio_outliers,
        "red_outliers": {},
        "data_by_year": data_by_year,
        "pos_val_map": pos_val_map,
        "pos_u_map": pos_u_map,
        "factory_pos_map": factory_pos_map,
        "fy_price_factor_prev": fy_price_factor_prev,
    }
