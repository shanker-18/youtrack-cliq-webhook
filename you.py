# pylint: disable=too-many-return-statements,too-many-nested-blocks,global-statement,too-many-lines
"""
NA IBP Planning Application — Validation Calculations Engine
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
        n = int(val)
        if 1 <= n <= 12:
            return MONTH_NUMBER_TO_3LETTER[n]
    except (ValueError, TypeError, OverflowError):
        pass
    return ""


def _parse_month_token(s: str) -> str:
    for t in re.findall(r"[A-Z0-9]+", s):
        if t in MONTH_NAME_MAP:
            return MONTH_NAME_MAP[t]
    m_iso = re.search(r"(\d{4})[-/](\d{1,2})", s)
    if m_iso:
        mo = int(m_iso.group(2))
        if 1 <= mo <= 12:
            return MONTH_NUMBER_TO_3LETTER[mo]
    return ""


def _normalize_string_month(s: str) -> str:
    s_clean = s.strip().upper()
    if not s_clean or s_clean in ("NAN", "NONE", "NULL", "N/A"):
        return ""
    if s_clean.isdigit():
        return _normalize_numeric_month(s_clean)
    return _parse_month_token(s_clean)


def normalize_month_3letter(val: Any) -> str:
    """Normalizes any month representation into standard 3-letter uppercase ('JAN'..'DEC')."""
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        res = _normalize_numeric_month(val)
        if res:
            return res
    if isinstance(val, (datetime, date)):
        return MONTH_NUMBER_TO_3LETTER.get(val.month, "")
    return _normalize_string_month(str(val))


# ─── 1. Pure 4-4-5 Fiscal Calendar Calculations ──────────────────────────────

def get_fiscal_year_weeks(year: int) -> int:
    """Returns total fiscal weeks in year (53 in 2021, 52 for other standard years)."""
    return KenvueCalendar.get_fiscal_year_weeks(year)


def get_kv_cycle_bounds(year: int, month_nbr: int) -> Tuple[date, date]:
    """Pure calendar mathematical calculation of cycle start and end dates."""
    return KenvueCalendar.get_cycle_bounds(year, month_nbr)


def map_date_to_kv_calendar(date_str: str) -> Optional[dict]:
    """Maps date to KV fiscal month metadata dynamically."""
    if not date_str:
        return None
    try:
        clean_d = date.fromisoformat(str(date_str).strip()[:10])
    except (ValueError, TypeError):
        return None

    c_info = KenvueCalendar.find_cycle_for_date(clean_d)
    if not c_info:
        return None

    yr, mo, c_start, c_end = c_info
    return {
        "year": yr,
        "y_str": str(yr),
        "month_nbr": mo,
        "m_idx": mo - 1,
        "month_abbr": MONTHS[mo - 1],
        "cycle_start": c_start.isoformat(),
        "cycle_end": c_end.isoformat(),
        "is_complete": clean_d >= c_end,
    }


def get_kv_month_ranges(start_year: int = 2021, end_year: int = 2027) -> List[dict]:
    """Generates Kenvue Fiscal Month date ranges dynamically using KenvueCalendar."""
    ranges = []
    for yr in range(start_year, end_year + 1):
        for m in range(1, 13):
            c_start, c_end = KenvueCalendar.get_cycle_bounds(yr, m)
            ranges.append({
                "year": yr,
                "y_str": str(yr),
                "m_nbr": m,
                "kv_month": f"{yr}-{m:02d}",
                "start": c_start.isoformat(),
                "end": c_end.isoformat(),
            })
    return ranges


def get_kv_month_completeness_status(as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """Dynamically calculates month completeness and YTD/YTG slices."""
    cur_date = as_of_date or date.today()
    c_info = KenvueCalendar.find_cycle_for_date(cur_date)
    if not c_info:
        c_info = (cur_date.year, cur_date.month, cur_date, cur_date)
    c_yr, c_mo, _, c_end = c_info

    latest_complete_m_nbr = c_mo if cur_date >= c_end else c_mo - 1
    if latest_complete_m_nbr < 0:
        latest_complete_m_nbr = 0
    if latest_complete_m_nbr > 12:
        latest_complete_m_nbr = 12

    return {
        "cycle_year": c_yr,
        "cycle_month_nbr": c_mo,
        "latest_complete_m_nbr": latest_complete_m_nbr,
        "ytd_slice": [0, latest_complete_m_nbr],
        "ytg_slice": [latest_complete_m_nbr, 12],
    }


# ─── 2. Price Index Engine ───────────────────────────────────────────────────

def _get_hardcoded_fallback_price_index() -> Dict[Tuple[str, str], float]:
    """Hardcoded fallback dictionary for Price Index."""
    tylenol_vals = [0.77, 0.76, 0.76, 0.76, 0.76, 0.77, 0.76, 0.80, 0.80, 0.75, 0.77, 0.76]
    res: Dict[Tuple[str, str], float] = {}
    for i, m in enumerate(MONTHS):
        res[(m, "CHILDREN'S TYLENOL")] = tylenol_vals[i]
        res[(m, "AVEENO BABY")] = 1.0
        res[(m, "ADULT SUDAFED")] = 1.0
        res[(m, "LISTERINE")] = 1.0
        res[(m, "NEOSPORIN")] = 1.0
        res[(m, "MOTRIN")] = 1.0
        res[(m, "BENADRYL")] = 1.0
        res[(m, "TYLENOL")] = 1.0
        res[(m, "AVEENO")] = 1.0
        res[(m, "NEUTROGENA")] = 1.0
        res[(m, "JOHNSON'S")] = 1.0
        res[(m, "PEPCID")] = 1.0
        res[(m, "IMODIUM")] = 1.0
        res[(m, "BAND-AID")] = 1.0
        res[(m, "OGX")] = 1.0
        res[(m, "MAUI MOISTURE")] = 1.0
        res[(m, "CLEAN & CLEAR")] = 1.0
        res[(m, "LUBRIDERM")] = 1.0
        res[(m, "DESITIN")] = 1.0
        res[(m, "ROGAINE")] = 1.0
        res[(m, "NICORETTE")] = 1.0
        res[(m, "NIZORAL")] = 1.0
    return res


def _read_excel_rows(ws: Any) -> Tuple[List[str], List[List[Any]]]:
    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        return [], []
    headers = [str(cell).strip() if cell is not None else "" for cell in all_rows[0]]
    data_rows = [list(r) for r in all_rows[1:] if any(c is not None for c in r)]
    return headers, data_rows


def _find_col_index(headers: List[str], candidates: List[str]) -> Optional[int]:
    norm_headers = [normalize_text(h) for h in headers]
    for c in candidates:
        norm_c = normalize_text(c)
        for idx, nh in enumerate(norm_headers):
            if norm_c == nh or norm_c in nh:
                return idx
    return None


def _detect_format_a_columns(headers: List[str]) -> Optional[Tuple[int, int, int]]:
    m_idx = _find_col_index(headers, ["MODEL", "MODEL_NAME", "BRAND", "PRODUCT"])
    mo_idx = _find_col_index(headers, ["MONTH", "PERIOD", "KV_MONTH", "FISCAL_MONTH"])
    pi_idx = _find_col_index(headers, ["PRICE_INDEX", "PRICE INDEX", "INDEX", "FACTOR"])
    if m_idx is not None and mo_idx is not None and pi_idx is not None:
        return m_idx, mo_idx, pi_idx
    return None


def _parse_format_a(
    data_rows: List[List[Any]],
    m_idx: int,
    mo_idx: int,
    pi_idx: int
) -> Dict[Tuple[str, str], float]:
    result = {}
    for row in data_rows:
        if len(row) <= max(m_idx, mo_idx, pi_idx):
            continue
        model = normalize_text(row[m_idx])
        month_3l = normalize_month_3letter(row[mo_idx])
        raw_pi = row[pi_idx]
        if not model or not month_3l:
            continue
        try:
            val = float(raw_pi)
            if not (math.isnan(val) or math.isinf(val)):
                result[(month_3l, model)] = val
        except (ValueError, TypeError):
            continue
    return result


def _detect_format_b_columns(headers: List[str]) -> Optional[Tuple[int, Dict[str, int]]]:
    m_idx = _find_col_index(headers, ["MODEL", "MODEL_NAME", "BRAND", "PRODUCT"])
    if m_idx is None:
        return None

    month_cols: Dict[str, int] = {}
    for idx, h in enumerate(headers):
        m_3l = normalize_month_3letter(h)
        if m_3l and m_3l in MONTHS and m_3l not in month_cols:
            month_cols[m_3l] = idx

    if len(month_cols) >= 6:
        return m_idx, month_cols
    return None


def _parse_format_b(
    data_rows: List[List[Any]],
    m_idx: int,
    month_cols: Dict[str, int]
) -> Dict[Tuple[str, str], float]:
    result = {}
    for row in data_rows:
        if len(row) <= m_idx:
            continue
        model = normalize_text(row[m_idx])
        if not model:
            continue
        for m_3l, c_idx in month_cols.items():
            if len(row) <= c_idx:
                continue
            raw_val = row[c_idx]
            try:
                val = float(raw_val)
                if not (math.isnan(val) or math.isinf(val)):
                    result[(m_3l, model)] = val
            except (ValueError, TypeError):
                continue
    return result


def _parse_price_index_sheet(ws: Any) -> Dict[Tuple[str, str], float]:
    headers, data_rows = _read_excel_rows(ws)
    if not headers or not data_rows:
        return {}

    fmt_a = _detect_format_a_columns(headers)
    if fmt_a:
        res = _parse_format_a(data_rows, fmt_a[0], fmt_a[1], fmt_a[2])
        if res:
            return res

    fmt_b = _detect_format_b_columns(headers)
    if fmt_b:
        res = _parse_format_b(data_rows, fmt_b[0], fmt_b[1])
        if res:
            return res

    return {}


def _resolve_price_index_file_path() -> Optional[str]:
    cfg_path = getattr(config, "PRICE_INDEX_EXCEL_PATH", None)
    if cfg_path and os.path.exists(cfg_path):
        return cfg_path

    env_path = os.getenv("PRICE_INDEX_EXCEL_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    common_locations = [
        "Price Index.xlsx",
        "Price_Index.xlsx",
        "price_index.xlsx",
        os.path.join("data", "Price Index.xlsx"),
        os.path.join("assets", "Price Index.xlsx"),
        os.path.join(os.path.dirname(__file__), "Price Index.xlsx"),
        os.path.join(os.path.dirname(__file__), "..", "Price Index.xlsx"),
        os.path.join(os.path.dirname(__file__), "..", "data", "Price Index.xlsx"),
    ]
    for loc in common_locations:
        if os.path.exists(loc):
            return os.path.abspath(loc)
    return None


def _load_excel_price_index(fpath: str) -> Dict[Tuple[str, str], float]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(fpath, data_only=True, read_only=True)
    except Exception as err:
        logger.warning("Could not open Price Index Excel '%s': %s", fpath, err)
        return {}

    result = {}
    try:
        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            parsed = _parse_price_index_sheet(ws)
            if parsed:
                result.update(parsed)
    finally:
        wb.close()
    return result


def load_price_index_map(force_reload: bool = False) -> Dict[Tuple[str, str], float]:
    """Loads Price Index lookup map: (month_3letter, normalized_model) -> multiplier."""
    global _CACHED_PRICE_INDEX_MAP
    if _CACHED_PRICE_INDEX_MAP is not None and not force_reload:
        return _CACHED_PRICE_INDEX_MAP

    fpath = _resolve_price_index_file_path()
    result = {}
    if fpath:
        result = _load_excel_price_index(fpath)

    fallback = _get_hardcoded_fallback_price_index()
    for k, v in fallback.items():
        if k not in result:
            result[k] = v

    _CACHED_PRICE_INDEX_MAP = result
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


# ─── 3. Live PostgreSQL Building Block Planning Values ───────────────────────

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
    if isinstance(p_val, (date, datetime)):
        return p_val.year == year and p_val.month == month_nbr
    s = str(p_val).strip()
    try:
        dt = date.fromisoformat(s[:10])
        return dt.year == year and dt.month == month_nbr
    except (ValueError, TypeError):
        pass
    for fmt in ("%m/%d/%Y", "%Y/%m/%d", "%d-%b-%Y", "%d-%b-%y", "%Y-%m"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.year == year and dt.month == month_nbr
        except (ValueError, TypeError):
            continue
    return False


def _matches_consumption_bb_row(r: Dict[str, Any], norm_targets: Set[str], year: int, month_nbr: int) -> bool:
    if normalize_text(r.get("model", "")) not in norm_targets:
        return False
    if normalize_text(r.get("building_block", "")) not in RAW_BB_MAP:
        return False
    return _matches_period(r.get("period_month"), year, month_nbr)


def get_building_block_total_for_period(
    model_name: str | list[str], year: int, month_nbr: int, bb_rows: List[Dict[str, Any]]
) -> float:
    """Returns total building block planning value in thousands ($K) for model(s) in period year-month."""
    if not bb_rows or not model_name:
        return 0.0

    if isinstance(model_name, (list, tuple, set)):
        norm_targets = {normalize_text(m) for m in model_name if m}
    else:
        norm_targets = {normalize_text(model_name)}

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
    if "OTHER" in norm or "OVERLAY" in norm or "IBP" in norm:
        return "Other"
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
    for b in SHIPMENT_ALLOWED_BUILDING_BLOCKS:
        if normalize_text(b) == norm:
            return b
    return None


def _matches_shipment_bb_row(r: Dict[str, Any], norm_targets: Set[str], year: int, month_nbr: int) -> bool:
    if normalize_text(r.get("model", "")) not in norm_targets:
        return False
    if not map_shipment_bb_name(r.get("building_block", "")):
        return False
    return _matches_period(r.get("period_month"), year, month_nbr)


def get_shipment_building_block_total_for_period(
    model_name: str | list[str], year: int, month_nbr: int, bb_rows: List[Dict[str, Any]]
) -> float:
    """Returns total shipment building block planning value in thousands ($K) for model(s) in period year-month."""
    if not bb_rows or not model_name:
        return 0.0

    if isinstance(model_name, (list, tuple, set)):
        norm_targets = {normalize_text(m) for m in model_name if m}
    else:
        norm_targets = {normalize_text(model_name)}

    return sum(
        float(r.get("value_in_thousands") or 0.0)
        for r in bb_rows
        if _matches_shipment_bb_row(r, norm_targets, year, month_nbr)
    )


def _extract_row_year_and_month_idx(r: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
    kv_m_str = str(r.get("KV_MONTH") or "").strip()
    if kv_m_str and "-" in kv_m_str:
        parts = kv_m_str.split("-")
        return parts[0], int(parts[1]) - 1

    d_str = str(r.get("GLOBAL_DATE_SHORT_DESC") or "").strip()
    kv_info = map_date_to_kv_calendar(d_str)
    if kv_info:
        return kv_info["y_str"], kv_info["m_idx"]

    return None, None


def _accumulate_pos_maps(
    r: Dict[str, Any],
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
) -> None:
    y_str, m_idx = _extract_row_year_and_month_idx(r)
    if not y_str or m_idx is None or (y_str.isdigit() and int(y_str) < 2021):
        return

    pv = r.get("POS_VALUE") if r.get("POS_VALUE") is not None else r.get("POS_DOLLARS")
    pu = r.get("POS_UNITS")
    key = (str(y_str), m_idx)
    if pv is not None:
        pos_val_map[key] = pos_val_map.get(key, 0.0) + float(pv)
    if pu is not None:
        pos_u_map[key] = pos_u_map.get(key, 0.0) + float(pu)


def _build_factory_pos_map(
    pos_val_map: Dict[Tuple[str, int], float], model_name: str | list[str]
) -> Dict[Tuple[str, int], float]:
    factory_pos_map: Dict[Tuple[str, int], float] = {}
    for (y_str, m_idx), pv_val in pos_val_map.items():
        f_pos, _ = get_factory_pos_val(m_idx + 1, model_name, pv_val)
        factory_pos_map[(str(y_str), m_idx)] = f_pos if f_pos is not None else pv_val
    return factory_pos_map


def extract_consumption_maps(
    rows_cons: List[Dict[str, Any]], model_name: str | list[str]
) -> Tuple[Dict[Tuple[str, int], float], Dict[Tuple[str, int], float], Dict[Tuple[str, int], float]]:
    """
    Extracts factory_pos_map, pos_val_map, pos_u_map from Snowflake consumption rows.
    Returns: (factory_pos_map, pos_val_map, pos_u_map) keyed by (year_str, month_idx 0..11).
    """
    if not rows_cons:
        return {}, {}, {}

    pos_val_map: Dict[Tuple[str, int], float] = {}
    pos_u_map: Dict[Tuple[str, int], float] = {}

    for r in rows_cons:
        _accumulate_pos_maps(r, pos_val_map, pos_u_map)

    factory_pos_map = _build_factory_pos_map(pos_val_map, model_name)
    return factory_pos_map, pos_val_map, pos_u_map


# ─── 4. Full Metrics Matrix Calculators ──────────────────────────────────────

def calc_asp(pos_val: Optional[float], pos_units: Optional[float]) -> Optional[float]:
    if pos_val is None or pos_units is None or pos_units == 0:
        return None
    return pos_val / pos_units


def calc_pct_var(actual: Optional[float], comparison: Optional[float]) -> Optional[float]:
    if actual is None or comparison is None or comparison == 0:
        return None
    return ((actual - comparison) / abs(comparison)) * 100.0


def calc_share(month_val: Optional[float], total_val: Optional[float]) -> Optional[float]:
    if month_val is None or total_val is None or total_val == 0:
        return None
    return (month_val / total_val) * 100.0


def _accumulate_year_consumption_metrics(
    r: Dict[str, Any], data_by_year: Dict[str, Dict[str, List[Optional[float]]]]
) -> None:
    y_str, m_idx = _extract_row_year_and_month_idx(r)
    if not y_str or m_idx is None or (y_str.isdigit() and int(y_str) < 2021):
        return

    if y_str not in data_by_year:
        data_by_year[y_str] = {
            "pos_val": [None] * 12,
            "factory_pos": [None] * 12,
            "pos_u": [None] * 12,
        }
    d_dict = data_by_year[y_str]
    pv = r.get("POS_VALUE") or r.get("POS_DOLLARS")
    pu = r.get("POS_UNITS")

    if pv is not None:
        d_dict["pos_val"][m_idx] = (d_dict["pos_val"][m_idx] or 0.0) + float(pv)
    if pu is not None:
        d_dict["pos_u"][m_idx] = (d_dict["pos_u"][m_idx] or 0.0) + float(pu)


def _aggregate_consumption_sf_rows(
    rows_cons: List[Dict[str, Any]], model_name: str | list[str]
) -> Dict[str, Dict[str, List[Optional[float]]]]:
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]] = {}
    for r in rows_cons:
        _accumulate_year_consumption_metrics(r, data_by_year)

    for _, d_dict in data_by_year.items():
        for m_i in range(12):
            pv_m = d_dict["pos_val"][m_i]
            if pv_m is not None:
                f_pos, _ = get_factory_pos_val(m_i + 1, model_name, pv_m)
                d_dict["factory_pos"][m_i] = f_pos
    return data_by_year


def _extract_ytd_slice(comp_status: Dict[str, Any]) -> List[int]:
    return comp_status.get("ytd_slice", [0, 8])


def _compute_projected_asp(
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]],
    latest_year: str,
    prev_year: str,
    m_i: int,
    prev_yr_pos: float,
    ytd_slice: List[int],
) -> Optional[float]:
    curr_ytd_val = sum(x for x in data_by_year[latest_year]["pos_val"][ytd_slice[0]:ytd_slice[1]] if x is not None)
    curr_ytd_u = sum(x for x in data_by_year[latest_year]["pos_u"][ytd_slice[0]:ytd_slice[1]] if x is not None)
    curr_asp_ytd = (curr_ytd_val / curr_ytd_u) if curr_ytd_u and curr_ytd_u > 0 else 0.0

    prev_ytd_val = sum(x for x in data_by_year.get(prev_year, {}).get("pos_val", [])[ytd_slice[0]:ytd_slice[1]] if x is not None)
    prev_ytd_u = sum(x for x in data_by_year.get(prev_year, {}).get("pos_u", [])[ytd_slice[0]:ytd_slice[1]] if x is not None)
    prev_asp_ytd = (prev_ytd_val / prev_ytd_u) if prev_ytd_u and prev_ytd_u > 0 else 0.0

    prev_same_u = data_by_year.get(prev_year, {}).get("pos_u", [None] * 12)[m_i]
    prev_same_asp = (prev_yr_pos / prev_same_u) if prev_same_u and prev_same_u > 0 else curr_asp_ytd
    yoy_asp_pct = ((curr_asp_ytd - prev_asp_ytd) / prev_asp_ytd) if prev_asp_ytd > 0 else 0.0

    return prev_same_asp * (1.0 + yoy_asp_pct)


def _project_consumption_future_months(
    data_by_year: Dict[str, Dict[str, List[Optional[float]]]],
    latest_year: str,
    prev_year: str,
    latest_year_int: int,
    latest_comp_m_nbr: int,
    model_name: str | list[str],
    comp_status: Dict[str, Any],
):
    if latest_comp_m_nbr >= 12:
        return
    bb_rows = load_live_building_blocks(domain="CONSUMPTION")
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
    d: Dict[str, List[Optional[float]]],
    prev_yr_dec_pos: Optional[float],
) -> Dict[str, Any]:
    pos_val = d["pos_val"]
    factory_pos = d["factory_pos"]
    pos_u = d["pos_u"]

    asp_arr = [calc_asp(pos_val[i], pos_u[i]) for i in range(12)]

    build_arr = [None] * 12
    for i in range(12):
        curr_m = pos_val[i]
        prior_m = pos_val[i - 1] if i > 0 else prev_yr_dec_pos
        if curr_m is not None and prior_m is not None and prior_m > 0:
            build_arr[i] = (curr_m / prior_m) - 1.0

    valid_vals = [v for v in pos_val if v is not None]
    fy_tot = sum(valid_vals) if valid_vals else 0.0
    share_arr = [calc_share(pos_val[i], fy_tot) for i in range(12)]

    return {
        "pos_val": pos_val,
        "factory_pos": factory_pos,
        "pos_u": pos_u,
        "asp": asp_arr,
        "build": build_arr,
        "share": share_arr,
    }


def _calc_yoy_growth(
    curr_arr: List[Optional[float]],
    prev_arr: Optional[List[Optional[float]]]
) -> List[Optional[float]]:
    if not prev_arr:
        return [None] * 12
    return [calc_pct_var(curr_arr[i], prev_arr[i]) for i in range(12)]


def _detect_2sigma_outliers(
    year_metrics: Dict[str, Dict[str, Any]],
    latest_year: str,
    ref_years: List[str]
) -> Dict[int, str]:
    outliers: Dict[int, str] = {}
    for m_i in range(12):
        vals = []
        for yr in ref_years:
            b_val = year_metrics.get(yr, {}).get("build", [None] * 12)[m_i]
            if b_val is not None and not (isinstance(b_val, float) and math.isnan(b_val)):
                vals.append(b_val)
        if len(vals) < 3:
            continue
        mean_val = statistics.mean(vals)
        stdev_val = statistics.stdev(vals)
        latest_val = year_metrics.get(latest_year, {}).get("build", [None] * 12)[m_i]
        if latest_val is not None and stdev_val > 0.0001:
            z_score = abs(latest_val - mean_val) / stdev_val
            if z_score > 2.0:
                outliers[m_i] = "red"
    return outliers


def build_consumption_matrix(
    rows_cons: List[Dict[str, Any]],
    model_name: str | list[str],
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Computes complete Consumption Validation matrix matching official validation specifications."""
    if not rows_cons:
        return {}

    data_by_year = _aggregate_consumption_sf_rows(rows_cons, model_name)
    all_years = sorted([yr for yr in data_by_year if yr.isdigit() and int(yr) >= 2021])
    if not all_years:
        return {}

    latest_year = all_years[-1]
    prev_year = str(int(latest_year) - 1)
    ref_years = [y for y in all_years if y < latest_year][-4:]

    comp_status = get_kv_month_completeness_status(as_of_date)
    latest_comp_m_nbr = comp_status["latest_complete_m_nbr"]
    latest_year_int = int(latest_year)

    _project_consumption_future_months(
        data_by_year, latest_year, prev_year, latest_year_int, latest_comp_m_nbr, model_name, comp_status
    )

    year_metrics: Dict[str, Dict[str, Any]] = {}
    for yr in all_years:
        prev_dec = data_by_year.get(str(int(yr) - 1), {}).get("pos_val", [None] * 12)[11]
        year_metrics[yr] = _calculate_single_year_consumption_metrics(data_by_year[yr], prev_dec)

    yoy_metrics: Dict[str, Dict[str, List[Optional[float]]]] = {}
    for yr in all_years:
        prev_yr_str = str(int(yr) - 1)
        if prev_yr_str in year_metrics:
            yoy_metrics[yr] = {
                "pos_val": _calc_yoy_growth(year_metrics[yr]["pos_val"], year_metrics[prev_yr_str]["pos_val"]),
                "pos_u": _calc_yoy_growth(year_metrics[yr]["pos_u"], year_metrics[prev_yr_str]["pos_u"]),
                "asp": _calc_yoy_growth(year_metrics[yr]["asp"], year_metrics[prev_yr_str]["asp"]),
            }
        else:
            yoy_metrics[yr] = {
                "pos_val": [None] * 12,
                "pos_u": [None] * 12,
                "asp": [None] * 12,
            }

    red_outliers = _detect_2sigma_outliers(year_metrics, latest_year, ref_years)

    return {
        "all_years": all_years,
        "latest_year": latest_year,
        "prev_year": prev_year,
        "ref_years": ref_years,
        "year_metrics": year_metrics,
        "yoy_metrics": yoy_metrics,
        "red_outliers": red_outliers,
        "comp_status": comp_status,
        "data_by_year": data_by_year,
    }


# ─── 5. Shipment Authoritative Math Engine ───────────────────────────────────

def _accumulate_shipment_row(r: Dict[str, Any], data_by_year: Dict[str, Dict[str, List[Optional[float]]]]) -> None:
    y_str, m_idx = _extract_row_year_and_month_idx(r)
    if not y_str or m_idx is None or (y_str.isdigit() and int(y_str) < 2021):
        return

    if y_str not in data_by_year:
        data_by_year[y_str] = {
            "gts_val": [None] * 12,
            "gts_qty": [None] * 12,
        }

    gv = r.get("GTS_VAL") or r.get("GTS_DOLLARS") or r.get("GROSS_SALES")
    gu = r.get("GTS_QTY") or r.get("GTS_UNITS") or r.get("GROSS_UNITS")

    if gv is not None:
        data_by_year[y_str]["gts_val"][m_idx] = (data_by_year[y_str]["gts_val"][m_idx] or 0.0) + float(gv)
    if gu is not None:
        data_by_year[y_str]["gts_qty"][m_idx] = (data_by_year[y_str]["gts_qty"][m_idx] or 0.0) + float(gu)


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

    sum_gs_prev = sum(x for x in data_by_year[prev_year]["gts_val"] if x is not None)
    sum_gu_prev = sum(x for x in data_by_year[prev_year]["gts_qty"] if x is not None)
    fy_b3_prev = (sum_gs_prev / sum_gu_prev) if sum_gu_prev and sum_gu_prev > 0 else 1.0

    sum_pv_prev = sum(pos_val_map.get((prev_year, m), 0.0) for m in range(12))
    sum_pu_prev = sum(pos_u_map.get((prev_year, m), 0.0) for m in range(12))
    fy_asp_prev = (sum_pv_prev / sum_pu_prev) if sum_pu_prev and sum_pu_prev > 0 else 1.0

    return (fy_asp_prev / fy_b3_prev) if fy_b3_prev and fy_b3_prev > 0 else 1.0


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

    if cons_bb_rows is None:
        try:
            cons_bb_rows = load_live_building_blocks(domain="CONSUMPTION")
        except (psycopg2.Error, OSError, ValueError, KeyError):
            cons_bb_rows = []

    prev_pos_val = pos_val_map.get((str(prev_year), m_i))
    tot_cons_bb_k = get_building_block_total_for_period(model_name, int(latest_year), m_nbr, cons_bb_rows)

    if prev_pos_val is not None or tot_cons_bb_k:
        base_pos = prev_pos_val if prev_pos_val is not None else 0.0
        plan_pos = base_pos + (tot_cons_bb_k * 1000.0)
        f_pos_calc, _ = get_factory_pos_val(m_nbr, model_name, plan_pos)
        factory_pos = f_pos_calc if f_pos_calc is not None else plan_pos
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
):
    if latest_comp_m_nbr >= 12:
        return
    if bb_rows is None:
        try:
            bb_rows = load_live_building_blocks(domain="SHIPMENT")
        except (psycopg2.Error, OSError, ValueError, KeyError):
            bb_rows = []

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
        else:
            gu = gts_qty[m_i]
            pu = pos_u_map.get((str(yr), m_i))
            if (pu is None or pu == 0) and prev_year:
                pu = pos_u_map.get((str(prev_year), m_i))
            unit_ratio_arr[m_i] = ((gu / pu) * 100.0) if (gu is not None and pu is not None and pu != 0) else None
    return unit_ratio_arr


def _calc_single_yr_price_factor(
    gts_val: List[Optional[float]],
    gts_qty: List[Optional[float]],
    yr: str,
    prev_year: str,
    b3_arr: List[Optional[float]],
    pos_val_map: Dict[Tuple[str, int], float],
    pos_u_map: Dict[Tuple[str, int], float],
    fy_price_factor_prev: float,
) -> List[Optional[float]]:
    price_factor_arr = [None] * 12
    for m_i in range(12):
        gs = gts_val[m_i]
        if gs is None or gs == 0 or (isinstance(gs, float) and math.isnan(gs)):
            price_factor_arr[m_i] = None
        else:
            b3 = b3_arr[m_i]
            asp = _resolve_month_asp(yr, prev_year, m_i, pos_val_map, pos_u_map)
            price_factor_arr[m_i] = (asp / b3) if (asp is not None and b3 is not None and b3 != 0) else fy_price_factor_prev
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
    gts_val = d["gts_val"]
    gts_qty = d["gts_qty"]

    b3_arr = _calc_single_yr_b3(gts_val, gts_qty, yr, prev_year, pos_val_map, pos_u_map, fy_price_factor_prev)
    build_bleed_arr = _calc_single_yr_build_bleed(gts_val, yr, factory_pos_map)
    unit_ratio_arr = _calc_single_yr_unit_ratio(gts_val, gts_qty, yr, prev_year, pos_u_map)
    price_factor_arr = _calc_single_yr_price_factor(gts_val, gts_qty, yr, prev_year, b3_arr, pos_val_map, pos_u_map, fy_price_factor_prev)

    return {
        "gts_val": gts_val,
        "gts_qty": gts_qty,
        "b3": b3_arr,
        "build_bleed": build_bleed_arr,
        "unit_ratio": unit_ratio_arr,
        "price_factor": price_factor_arr,
        "gross_ship": gts_val,
        "gross_case": gts_qty,
        "net_ship": b3_arr,
        "share": unit_ratio_arr,
    }


def _evaluate_month_unit_ratio_outlier(
    m_i: int,
    year_metrics: Dict[str, Dict[str, Any]],
    latest_year: str,
    ref_years: List[str],
) -> Optional[str]:
    v_curr = year_metrics[latest_year]["unit_ratio"][m_i]
    if v_curr is None or (isinstance(v_curr, float) and math.isnan(v_curr)):
        return None

    ref_4_vals = [
        year_metrics[y]["unit_ratio"][m_i]
        for y in ref_years
        if y in year_metrics
        and year_metrics[y]["unit_ratio"][m_i] is not None
        and not (isinstance(year_metrics[y]["unit_ratio"][m_i], float) and math.isnan(year_metrics[y]["unit_ratio"][m_i]))
    ]
    if len(ref_4_vals) < 4:
        return None

    sum_ref = sum(ref_4_vals)
    baseline = (sum_ref - min(ref_4_vals) - max(ref_4_vals)) / 2.0
    if baseline <= 0:
        return None

    rel_diff_pct = abs((v_curr - baseline) / baseline) * 100.0
    if rel_diff_pct > 10.0:
        return "red"
    if rel_diff_pct > 5.0:
        return "yellow"
    return None


def _detect_unit_ratio_outliers(
    year_metrics: Dict[str, Dict[str, Any]],
    latest_year: str,
    ref_years: List[str],
) -> Dict[int, str]:
    unit_ratio_outliers: Dict[int, str] = {}
    if latest_year not in year_metrics:
        return unit_ratio_outliers

    for m_i in range(12):
        color = _evaluate_month_unit_ratio_outlier(m_i, year_metrics, latest_year, ref_years)
        if color:
            unit_ratio_outliers[m_i] = color

    return unit_ratio_outliers


def _detect_shipment_cutoff_month(latest_year: str, latest_gts_vals: List[Optional[float]]) -> int:
    cutoff = 8 if latest_year == "2026" else 12
    for m_i in range(11, -1, -1):
        v = latest_gts_vals[m_i]
        if v is not None and not (isinstance(v, float) and math.isnan(v)) and v > 0:
            return m_i + 1
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
) -> Dict[str, Any]:
    """
    Computes complete Shipment Validation matrix matching validation/ship.py specifications.
    """
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
        data_by_year, latest_year, prev_year, latest_comp_m_nbr, factory_pos_map, pos_val_map, pos_u_map, fy_price_factor_prev, model_name, bb_rows
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
