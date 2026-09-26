
"""
BB.py - Building Blocks Calculation & Diagnostics Module for Consumption Validation Dashboard.

Dynamically calculates current Kenvue month POS value using:
  Previous-Year Same Kenvue Month POS $ (normalized to $M)
+ Current-Year 11 Official Building Block Values (PostgreSQL)
-------------------------------------------------
= Current-Year Calculated POS $ ($M)

Then calculates:
  Factory POS $ = Calculated POS $ * Existing Index Value

Reuses existing implementations from database.py.
Filters specifically for the 11 official POS adjustment building blocks:
  Base Trend, Season, Competition, Distribution, Innovation, Discontinuations,
  Renovation, Media, Trade, Price, Club.
"""

import os
import sys
import math
from typing import Optional, Dict, List, Tuple
import pandas as pd

import database

# Authoritative Reference Query for Building Blocks
BB_QUERY = """
SELECT
    hm.model_name AS model,
    DATE_TRUNC('month', cpv.period_month)::date AS period_month,
    cbb.name AS building_block,
    SUM(cpv.value_in_thousands) AS value_in_thousands
FROM public.consumption_planning_rows cpr
INNER JOIN public.consumption_building_blocks cbb
    ON cpr.building_block_id = cbb.block_id
INNER JOIN public.consumption_planning_values cpv
    ON cpr.row_id = cpv.row_id
INNER JOIN public.hierarchy_models hm
    ON cpr.model_id = hm.model_id
WHERE
    cpr.is_deleted = FALSE
    AND cbb.is_active = TRUE
    AND hm.is_active = TRUE
GROUP BY
    hm.model_name,
    DATE_TRUNC('month', cpv.period_month),
    cbb.name
ORDER BY
    hm.model_name,
    period_month,
    cbb.name;
"""

# The 11 Official POS Adjustment Building Blocks
ALLOWED_BUILDING_BLOCKS = [
    "Base Trend",
    "Season",
    "Competition",
    "Distribution",
    "Net Innovation",
    "Discontinuations",
    "Renovation",
    "Media",
    "Trade",
    "Net Price",
    "Club",
]

RAW_BB_MAP = {
    "BASE TREND": "Base Trend",
    "SEASON": "Season",
    "COMPETITION": "Competition",
    "DISTRIBUTION": "Distribution",
    "INNOVATION": "Net Innovation",
    "CANNIBALIZATION": "Net Innovation",
    "NET INNOVATION": "Net Innovation",
    "DISCONTINUATIONS": "Discontinuations",
    "RENOVATION": "Renovation",
    "MEDIA": "Media",
    "TRADE": "Trade",
    "PRICE": "Net Price",
    "ELASTICITY": "Net Price",
    "NET PRICE": "Net Price",
    "CLUB": "Club",
}

ALLOWED_BB_NORM = set(RAW_BB_MAP.keys())

# Building Blocks are calculated dynamically for all models present in PostgreSQL
BUILDING_BLOCK_DISPLAY_MODELS = []
BUILDING_BLOCK_DISPLAY_MODELS_NORM = set()


_cached_bb_df = None


def load_building_block_data(force_reload: bool = False) -> pd.DataFrame:
    """
    Executes authoritative reference BB_QUERY against PostgreSQL to load active Building Block planning records.
    Returns DataFrame with columns: ['model', 'period_month', 'building_block', 'value_in_thousands'].
    Caches result in _cached_bb_df for fast subsequent lookups.
    """
    global _cached_bb_df
    if _cached_bb_df is not None and not force_reload:
        return _cached_bb_df

    df = pd.DataFrame(columns=['model', 'period_month', 'building_block', 'value_in_thousands'])
    try:
        conn = database.get_postgres_connection()
        cur = conn.cursor()
        cur.execute(BB_QUERY)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            df = pd.DataFrame(rows, columns=['model', 'period_month', 'building_block', 'value_in_thousands'])
            df['value_in_thousands'] = pd.to_numeric(df['value_in_thousands'], errors='coerce').fillna(0.0)
            df['building_block'] = df['building_block'].astype(str).str.strip()
            df['model'] = df['model'].astype(str).str.strip()
    except Exception as e:
        print(f"[POSTGRES BUILDING BLOCK LOAD NOTICE]: {e}")

    _cached_bb_df = df
    return df


def get_current_kv_period(df: pd.DataFrame = None, target_year: Optional[str] = None) -> dict:
    """
    Determines current Kenvue year, current/target Kenvue month, and completeness
    using existing Kenvue Calendar logic in database.py.
    """
    comp = database.get_kv_month_completeness_status(df, target_year=target_year)
    t_year = comp.get("latest_year", "")

    latest_comp_nbr = comp.get("latest_complete_m_nbr", 0)
    month_details = comp.get("month_details", {})

    target_m_nbr = min(latest_comp_nbr + 1, 12) if (latest_comp_nbr > 0 and latest_comp_nbr < 12) else (12 if latest_comp_nbr == 12 else 1)
    m_info = month_details.get(target_m_nbr, {})
    is_comp = m_info.get("is_complete", False)
    m_name = database.MONTHS[target_m_nbr - 1] if 1 <= target_m_nbr <= 12 else "N/A"

    return {
        "target_year": t_year,
        "target_month_nbr": target_m_nbr,
        "target_month_name": m_name,
        "is_complete": is_comp,
        "month_details": month_details,
        "completeness_status": comp
    }


def get_previous_year_pos(
    df: pd.DataFrame,
    current_year: str,
    current_month_nbr: int,
    model_name: Optional[str] = None
) -> Tuple[Optional[float], Optional[float], List[Tuple]]:
    """
    Gets POS $ for the SAME Kenvue month in the PREVIOUS KENVUE YEAR.
    Example: Current = Sep 2026 -> Previous Year = Sep 2025.
    Normalizes raw Snowflake POS dollars into dashboard $M units (divides by 1,000,000).
    Returns tuple: (raw_pos_dollars, normalized_pos_in_millions, weekly_rows).
    """
    if df is None or df.empty or not current_year or not str(current_year).isdigit():
        return None, None, []

    prev_year = str(int(current_year) - 1)
    target_kv_m = f"{prev_year}-{current_month_nbr:02d}"

    raw_pos = 0.0
    found = False
    weekly_rows = []

    for _, r in df.iterrows():
        d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', '')).strip()
        kv_info = database.map_date_to_kv_calendar(d_str) if d_str else None
        
        kv_m_str = ""
        wk_id = r.get('KV_WK_ID')
        
        if kv_info:
            kv_m_str = f"{kv_info['y_str']}-{kv_info['m_nbr']:02d}"
            if not wk_id:
                wk_id = kv_info.get('wk_id')
        else:
            kv_m_str = str(r.get('KV_MONTH', '')).strip()

        if kv_m_str == target_kv_m:
            pv = r.get('POS_VALUE') if pd.notnull(r.get('POS_VALUE')) else r.get('POS_DOLLARS')
            if pd.notnull(pv):
                val = float(pv)
                raw_pos += val
                found = True
                weekly_rows.append((str(wk_id or 'N/A'), d_str, val))

    if not found:
        return None, None, []

    pos_in_m = raw_pos / 1_000_000.0
    return raw_pos, pos_in_m, weekly_rows


def get_building_block_values(
    model_name: str,
    year: str,
    month_nbr: int,
    bb_df: Optional[pd.DataFrame] = None
) -> Tuple[Dict[str, Optional[float]], Optional[float], List[Tuple], bool]:
    """
    Filters Building Block planning values for model and period matching the 11 official POS adjustment blocks:
      Base Trend, Season, Competition, Distribution, Innovation, Discontinuations,
      Renovation, Media, Trade, Price, Club.
    Returns tuple: (blocks_dict, total_bb_value, raw_rows_list, has_bb_data).
    If model is not in BUILDING_BLOCK_DISPLAY_MODELS or no matching records exist, returns total_bb_value = None and has_bb_data = False.
    """
    if not model_name or database.normalize_text(model_name) in database.IGNORED_PLACEHOLDERS:
        return {b: None for b in ALLOWED_BUILDING_BLOCKS}, None, [], False

    norm_target_model = database.normalize_text(model_name)

    if bb_df is None or bb_df.empty:
        bb_df = load_building_block_data()

    if bb_df.empty:
        return {b: None for b in ALLOWED_BUILDING_BLOCKS}, None, [], False

    yr_int = int(year) if year and str(year).isdigit() else 2026

    blocks = {}
    total = 0.0
    raw_list = []

    for _, r in bb_df.iterrows():
        row_model = str(r['model'])
        if database.normalize_text(row_model) != norm_target_model:
            continue

        b_name_raw = str(r['building_block']).strip()
        b_norm = database.normalize_text(b_name_raw)

        # Filter strictly for the 11 official POS adjustment Building Blocks
        if b_norm not in ALLOWED_BB_NORM:
            continue

        p_val = r['period_month']
        match_period = False

        if pd.notnull(p_val):
            dt = pd.to_datetime(p_val, errors='coerce')
            if pd.notnull(dt):
                if dt.year == yr_int and dt.month == month_nbr:
                    match_period = True
            else:
                p_str = str(p_val).strip()
                if p_str.startswith(f"{yr_int}-{month_nbr:02d}"):
                    match_period = True

        if match_period:
            canonical_name = RAW_BB_MAP.get(b_norm, b_name_raw)
            val = float(r['value_in_thousands']) if pd.notnull(r['value_in_thousands']) else 0.0
            blocks[canonical_name] = blocks.get(canonical_name, 0.0) + val
            total += val
            raw_list.append((canonical_name, val, yr_int, month_nbr))

    has_bb_data = len(raw_list) > 0
    if not has_bb_data:
        return {b: None for b in ALLOWED_BUILDING_BLOCKS}, None, [], False

    final_blocks = {}
    for b in ALLOWED_BUILDING_BLOCKS:
        final_blocks[b] = blocks.get(b, 0.0)

    return final_blocks, total, raw_list, True



def calculate_current_month_asp(
    df: pd.DataFrame,
    current_year: str,
    target_month_nbr: int
) -> Optional[float]:
    """
    Calculates ASP for Current Month (Building Block target month):
      ASP(Current Month) = ASP(Previous Year Same Month) * (1 + YoY% of ASP OF YTD)
    """
    if df is None or df.empty or not current_year or not str(current_year).isdigit():
        return None

    prev_year = str(int(current_year) - 1)
    target_m_idx = target_month_nbr - 1

    pos_val_curr = [0.0] * 12
    pos_u_curr = [0.0] * 12
    pos_val_prev = [0.0] * 12
    pos_u_prev = [0.0] * 12

    has_val_prev = [False] * 12
    has_u_prev = [False] * 12

    for _, r in df.iterrows():
        kv_m_str = str(r.get('KV_MONTH', '')).strip()
        if kv_m_str and '-' in kv_m_str:
            parts = kv_m_str.split('-')
            y_str = parts[0]
            try:
                m_nbr = int(parts[1])
                m_idx = m_nbr - 1
            except Exception:
                continue
        else:
            d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', '')).strip()
            kv_info = database.map_date_to_kv_calendar(d_str) if d_str else None
            if not kv_info:
                continue
            y_str = kv_info['y_str']
            m_idx = kv_info['m_idx']

        pv = r.get('POS_VALUE') if pd.notnull(r.get('POS_VALUE')) else r.get('POS_DOLLARS')
        pu = r.get('POS_UNITS')

        if y_str == current_year and 0 <= m_idx < 12:
            if pd.notnull(pv):
                pos_val_curr[m_idx] += float(pv)
            if pd.notnull(pu):
                pos_u_curr[m_idx] += float(pu)
        elif y_str == prev_year and 0 <= m_idx < 12:
            if pd.notnull(pv):
                pos_val_prev[m_idx] += float(pv)
                has_val_prev[m_idx] = True
            if pd.notnull(pu):
                pos_u_prev[m_idx] += float(pu)
                has_u_prev[m_idx] = True

    if not (has_val_prev[target_m_idx] and has_u_prev[target_m_idx] and pos_u_prev[target_m_idx] > 0):
        return None

    prev_same_month_asp = pos_val_prev[target_m_idx] / pos_u_prev[target_m_idx]

    ytd_end = target_m_idx if target_m_idx > 0 else 12

    curr_ytd_val = sum(pos_val_curr[:ytd_end])
    curr_ytd_u = sum(pos_u_curr[:ytd_end])

    prev_ytd_val = sum(pos_val_prev[:ytd_end])
    prev_ytd_u = sum(pos_u_prev[:ytd_end])

    ytd_asp_curr = (curr_ytd_val / curr_ytd_u) if curr_ytd_u > 0 else None
    ytd_asp_prev = (prev_ytd_val / prev_ytd_u) if prev_ytd_u > 0 else None

    yoy_asp_ytd_pct = 0.0
    if ytd_asp_curr is not None and ytd_asp_prev is not None and ytd_asp_prev > 0:
        yoy_asp_ytd_pct = (ytd_asp_curr - ytd_asp_prev) / abs(ytd_asp_prev)

    calc_asp = prev_same_month_asp * (1.0 + yoy_asp_ytd_pct)
    return calc_asp


def calculate_current_month_pos(
    df: pd.DataFrame,
    model_name: str,
    target_year: Optional[str] = None,
    target_month_nbr: Optional[int] = None
) -> dict:
    """
    Main calculation entry point for Building Blocks & Current Month POS:
      Current-Month Calculated POS ($M) = Previous-Year Same Month POS ($M) + Building Block Total ($K)
      Calculated Factory POS ($M) = Calculated Current POS ($M) * Existing Index Value
    Gated strictly by Kenvue Month completeness (complete == TRUE) and BUILDING_BLOCK_DISPLAY_MODELS.
    """
    period_info = get_current_kv_period(df, target_year=target_year)
    yr = target_year or period_info["target_year"]
    m_nbr = target_month_nbr or period_info["target_month_nbr"]
    m_name = database.MONTHS[m_nbr - 1] if 1 <= m_nbr <= 12 else "N/A"
    prev_yr_str = str(int(yr) - 1) if yr and str(yr).isdigit() else "N/A"

    m_complete = period_info.get("is_complete", False)
    m_details = period_info.get("month_details", {}).get(m_nbr, {})
    req_weeks = m_details.get("req_weeks_count", 0)
    avail_weeks = m_details.get("avail_weeks_count", 0)
    pos_raw_avail = avail_weeks > 0

    norm_model = database.normalize_text(model_name)
    is_bb_eligible = bool(norm_model and norm_model not in database.IGNORED_PLACEHOLDERS)

    # Print required Model Eligibility diagnostic block
    print("\n" + "=" * 60)
    print(f"Selected Model: {model_name}")
    print(f"Building Block Eligible: {'YES' if is_bb_eligible else 'NO'}")

    # Get Previous-Year Same Month POS
    raw_prev_pos, prev_pos_m, prev_weekly_rows = get_previous_year_pos(df, yr, m_nbr, model_name=model_name)

    # Load & filter Building Block data (11 official blocks)
    bb_df = load_building_block_data()
    bb_blocks, bb_total, bb_raw_list, has_bb_data = get_building_block_values(model_name, yr, m_nbr, bb_df=bb_df)

    if is_bb_eligible:
        print(f"Building Block records available: {len(bb_raw_list)}")
    else:
        print("Building Block display skipped for selected model.")

    pos_display_allowed = is_bb_eligible and has_bb_data and (prev_pos_m is not None)
    bb_display_allowed = is_bb_eligible and has_bb_data

    # Calculation: Current-Month Calculated POS ($M) = Previous-Year POS ($M) + Building Block Total ($M)
    calc_pos_m = None
    if is_bb_eligible and has_bb_data and (prev_pos_m is not None):
        bb_total_m = (bb_total / 1000.0) if bb_total is not None else 0.0
        calc_pos_m = prev_pos_m + bb_total_m

    # Calculation: Factory POS ($M) = Calculated POS ($M) * Price Index
    factory_pos_m = None
    index_val = None
    if calc_pos_m is not None:
        norm_m = database.normalize_month_3letter(m_nbr)
        idx_map = database.get_price_index_lookup_map()
        key = (norm_m, norm_model)
        if key in idx_map:
            index_val = idx_map[key]
            factory_pos_m = calc_pos_m * index_val
        else:
            factory_pos_m = calc_pos_m

    # Print exact required CURRENT MONTH DISPLAY GATE diagnostic block
    print("\nCURRENT MONTH DISPLAY GATE")
    print("=" * 60)
    print(f"Current Kenvue Month : {yr}-{m_nbr:02d}")
    print(f"Required Weeks       : {req_weeks}")
    print(f"Available Weeks      : {avail_weeks}")
    print(f"Month Complete       : {'TRUE' if m_complete else 'FALSE'}")
    print("")
    print(f"POS Raw Available    : {'YES' if pos_raw_avail else 'NO'}")
    print(f"POS Display Allowed  : {'YES' if pos_display_allowed else 'NO'}")
    print("")
    print(f"Building Block Data  : {'YES' if has_bb_data else 'NO'}")
    print(f"BB Display Allowed   : {'YES' if bb_display_allowed else 'NO'}")
    print("")
    print(f"Final POS $          : {f'${calc_pos_m:.1f} M' if calc_pos_m is not None else 'BLANK'}")
    print(f"Final Factory POS $  : {f'${factory_pos_m:.1f} M' if factory_pos_m is not None else 'BLANK'}")
    calc_asp_val = None
    if is_bb_eligible and has_bb_data:
        calc_asp_val = calculate_current_month_asp(df, yr, m_nbr)

    print(f"Final POS U          : BLANK")
    print(f"Final ASP            : {f'${calc_asp_val:.2f}' if calc_asp_val is not None else 'BLANK'}")
    print(f"Final BBI            : {f'{bb_total:.2f}' if (bb_display_allowed and bb_total is not None) else 'BLANK'}")
    print(f"Final % of Year      : BLANK")
    print("=" * 60)

    if is_bb_eligible:
        print("\n" + "=" * 70)
        print(f"BUILDING BLOCK SUMMARY | MODEL: '{model_name}' | PERIOD: {yr}-{m_nbr:02d} ({m_name})")
        print("=" * 70)
        if has_bb_data and bb_blocks:
            for b_name in ALLOWED_BUILDING_BLOCKS:
                val_k = bb_blocks.get(b_name, 0.0)
                print(f"  - {b_name:<20} : ${val_k:>10,.2f} K")
            print("-" * 70)
            tot_val_k = bb_total if bb_total is not None else 0.0
            print(f"  TOTAL BUILDING BLOCKS  : ${tot_val_k:>10,.2f} K (${tot_val_k/1000.0:>6,.2f} M)")
        else:
            print("  No building block planning values found for this period.")
        print("-" * 70)
        if prev_pos_m is not None:
            print(f"  PREV YEAR SAME MONTH POS $ : ${prev_pos_m:>10,.2f} M")
        if calc_pos_m is not None:
            print(f"  CALCULATED MONTH POS $     : ${calc_pos_m:>10,.2f} M")
        if factory_pos_m is not None:
            print(f"  CALCULATED FACTORY POS $   : ${factory_pos_m:>10,.2f} M")
        print("=" * 70 + "\n")

    return {
        "target_year": yr,
        "target_month_nbr": m_nbr,
        "target_month_name": m_name,
        "prev_year_str": prev_yr_str,
        "prev_year_pos_raw": raw_prev_pos,
        "prev_year_pos_m": prev_pos_m,
        "building_blocks": bb_blocks,
        "bb_total": bb_total,
        "has_bb_data": has_bb_data,
        "is_complete": m_complete,
        "calculated_pos_m": calc_pos_m,
        "index_val": index_val,
        "factory_pos_m": factory_pos_m,
        "calculated_asp": calc_asp_val
    }


def calculate_factory_pos(calculated_pos_val: float, target_year: str, target_month_nbr: int, model_name: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculates Factory POS $ = Calculated POS $ * Existing Index Value.
    Uses existing Index Value logic in database.py.
    Returns tuple: (factory_pos_val, index_val).
    """
    if calculated_pos_val is None or pd.isna(calculated_pos_val):
        return None, None

    norm_m = database.normalize_month_3letter(target_month_nbr)
    norm_model = database.normalize_text(model_name)
    idx_map = database.get_price_index_lookup_map()
    key = (norm_m, norm_model)

    if key in idx_map:
        index_val = idx_map[key]
        return (float(calculated_pos_val) * index_val), index_val

    return None, None
