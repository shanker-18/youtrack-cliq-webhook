"""
consumption_summary.py
======================
Dynamic Calculation Engine and UI Presentation for Consumption Summary Dashboard:
1. Dynamic Years: Automatically detects plan_year and base_year using Kenvue 4-4-5 Fiscal Calendar.
2. Dynamic Kenvue 4-4-5 Fiscal Calendar mapping (from kv_calender.py).
3. Circana Snowflake EDW POS $ Queries for dynamic base_year and plan_year.
4. PostgreSQL Live Building Blocks (Aggregated across multi-models for dynamic plan_year).
   - Net Innovation = Innovation + Cannibalization
   - Net Price = Price + Elasticity
5. Sum Before Calculation:
   - Sum Base POS $ across all selected models
   - Sum Plan Actual POS $ across all selected models
   - Sum each Building Block across all selected models
   - Combined Plan Forecast = Combined Base + Combined Building Blocks
   - Combined YoY % = ((Combined Plan - Combined Base) / Combined Base) * 100%
   - Combined Difference = Combined Plan Actual - (Combined Base + Combined Building Blocks)
6. UI Presentation & Heatmaps:
   - render_consumption_table(data: dict) -> html.Div
   - 11-Tier Dynamic Heatmap Gradient & Number Formatters
"""

import os
import re
import math
import datetime
from typing import Optional, Dict, List, Tuple, Any, Union
from dotenv import load_dotenv
from dash import html

load_dotenv()

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ─── 1. DYNAMIC KENVUE 4-4-5 FISCAL CALENDAR (FROM kv_calender.py) ───────────

import sys
import types

# Dynamic fallback for 'config' module if not present in the environment:
# kv_calender.py contains `from config import Config`. If config.py is not in the project,
# this injects a lightweight Config object into sys.modules without modifying kv_calender.py.
if "config" not in sys.modules:
    try:
        import config  # type: ignore
    except ImportError:
        _cfg_mod = types.ModuleType("config")
        _cfg_mod.Config = type("Config", (), {
            "STANDARD_LOCK_POLICY": os.getenv("STANDARD_LOCK_POLICY", "THIRD_FRIDAY")
        })
        sys.modules["config"] = _cfg_mod

from kv_calender import KenvueCalendar


def get_postgres_connection():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("IBP_DB_HOST", "localhost"),
        port=int(os.getenv("IBP_DB_PORT", "5432")),
        dbname=os.getenv("IBP_DB_NAME", "na_ibp_db"),
        user=os.getenv("IBP_DB_USER", "postgres"),
        password=os.getenv("IBP_DB_PASSWORD", "postgres"),
        sslmode=os.getenv("IBP_DB_SSLMODE", "prefer"),
        connect_timeout=5,
    )


def get_active_years() -> Tuple[int, int]:
    """
    Dynamically determines (base_year, plan_year) based on Kenvue 4-4-5 Fiscal Calendar.
    - If IBP_PLAN_YEAR is set in .env, uses that explicit override.
    - Otherwise, derives active plan_year from KenvueCalendar.get_date_info(datetime.date.today()).kv_year.
    base_year is always plan_year - 1.
    Completely dynamic with zero hardcoding.
    """
    env_year = os.getenv("IBP_PLAN_YEAR")
    if env_year and env_year.isdigit():
        plan_year = int(env_year)
    else:
        today_info = KenvueCalendar.get_date_info(datetime.date.today())
        plan_year = today_info.kv_year
    base_year = plan_year - 1
    return base_year, plan_year


# ─── 2. POSTGRESQL CONNECTION & HIERARCHY ────────────────────────────────────

def normalize_text(val) -> str:
    if val is None:
        return ""
    s = str(val).replace("\xa0", " ").strip().upper()
    if s in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
        return ""
    return re.sub(r"\s+", " ", s)


def load_squads_and_models() -> Dict[str, List[str]]:
    conn = get_postgres_connection()
    conn.autocommit = True
    cur = conn.cursor()
    queries = [
        """
        SELECT DISTINCT
            COALESCE(chm.need_state, 'UNKNOWN') AS squad,
            mm.model_name
        FROM public.consumption_hierarchy_mapping chm
        INNER JOIN public.master_models mm ON chm.model_id = mm.model_id
        WHERE chm.is_active = TRUE AND mm.is_active = TRUE
        ORDER BY squad, mm.model_name;
        """,
        """
        SELECT DISTINCT
            COALESCE(hmap.squad_name, 'UNKNOWN') AS squad,
            hm.model_name
        FROM public.hierarchy_mapping hmap
        INNER JOIN public.hierarchy_models hm ON hmap.model_id = hm.model_id
        WHERE hmap.is_active = TRUE AND hm.is_active = TRUE
        ORDER BY squad, hm.model_name;
        """
    ]
    rows = []
    for q in queries:
        try:
            cur.execute(q)
            rows = cur.fetchall()
            if rows:
                break
        except Exception:
            conn.rollback()
    cur.close()
    conn.close()
    squad_map: Dict[str, List[str]] = {}
    for squad, m_name in rows:
        sq = str(squad).strip().upper()
        m = str(m_name).strip()
        if sq and sq not in ["ALL", "NONE", "UNKNOWN"]:
            squad_map.setdefault(sq, [])
            if m not in squad_map[sq]:
                squad_map[sq].append(m)
    for sq in squad_map:
        squad_map[sq].sort()
    return squad_map


def load_model_rules(models: Union[str, List[str]]) -> List[Dict[str, str]]:
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]
    if not model_list:
        return []
    conn = get_postgres_connection()
    conn.autocommit = True
    cur = conn.cursor()
    queries = [
        """
        SELECT
            chm.brand_name,
            chm.sub_brand_name,
            chm.category,
            chm.subcategory
        FROM public.consumption_hierarchy_mapping chm
        INNER JOIN public.master_models mm ON chm.model_id = mm.model_id
        WHERE mm.model_name = ANY(%s) AND chm.is_active = TRUE;
        """,
        """
        SELECT
            hmap.brand_name,
            hmap.sub_brand_name,
            hmap.category,
            hmap.subcategory
        FROM public.hierarchy_mapping hmap
        INNER JOIN public.hierarchy_models hm ON hmap.model_id = hm.model_id
        WHERE hm.model_name = ANY(%s) AND hmap.is_active = TRUE;
        """
    ]
    rows = []
    for q in queries:
        try:
            cur.execute(q, (model_list,))
            rows = cur.fetchall()
            if rows:
                break
        except Exception:
            conn.rollback()
    cur.close()
    conn.close()
    rules = []
    for r in rows:
        rules.append({
            "brand": normalize_text(r[0]),
            "sub_brand": normalize_text(r[1]),
            "category": normalize_text(r[2]),
            "subcategory": normalize_text(r[3]),
        })
    return rules


# ─── 3. DYNAMIC SNOWFLAKE POS QUERY ──────────────────────────────────────────

def get_snowflake_connection():
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    config = {
        "user": os.getenv("SNOWFLAKE_USER", "SA-JX2-SNFK-CVD-RPT@KENVUE.COM"),
        "account": os.getenv("SNOWFLAKE_ACCOUNT", "BK40750.east-us-2.azure"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "PROD_ENVIRONMENT_USAGE_XSMALL1_WH"),
        "database": os.getenv("SNOWFLAKE_DATABASE", "PROD_CUSTOMER360_GLBLSYNDCTD"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "CORE_ACCESS"),
        "role": os.getenv("SNOWFLAKE_ROLE", "PROD_SA_JX2_SNFK_CVD_RPT_ER"),
    }
    private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    private_key_pem = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    if private_key_path or private_key_pem:
        try:
            if private_key_path and os.path.exists(private_key_path):
                with open(private_key_path, "rb") as kf:
                    pem_bytes = kf.read()
            else:
                pem_str = private_key_pem.replace("\\n", "\n").strip()
                pem_bytes = pem_str.encode("utf-8")
            p_key = serialization.load_pem_private_key(
                pem_bytes,
                password=passphrase.encode("utf-8") if passphrase else None,
                backend=default_backend()
            )
            pkb = p_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            config["private_key"] = pkb
        except Exception as e:
            print(f"[Snowflake Notice]: Private key parsing: {e}")
    else:
        config["password"] = os.getenv("SNOWFLAKE_PASSWORD")

    conn = snowflake.connector.connect(**config)
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE PROD_ENVIRONMENT_USAGE_XSMALL1_WH;")
    cur.execute("USE DATABASE PROD_CUSTOMER360_GLBLSYNDCTD;")
    cur.execute("USE SCHEMA CORE_ACCESS;")
    cur.close()
    return conn


def fetch_snowflake_monthly_pos(
    rules: List[Dict[str, str]], base_year: int, plan_year: int
) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """Fetches POS $ for dynamic base_year and plan_year from Snowflake."""
    pos_base = [None] * 12
    pos_plan_actual = [None] * 12
    if not rules:
        return pos_base, pos_plan_actual
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
    if not rule_clauses:
        return pos_base, pos_plan_actual

    filter_sql = "AND (" + " OR\n        ".join(rule_clauses) + ")"
    st_base, _ = KenvueCalendar.get_cycle_bounds(base_year, 1)
    _, en_plan = KenvueCalendar.get_cycle_bounds(plan_year, 12)
    start_date_str = str(st_base)
    end_date_str = str(en_plan)

    official_query = f"""
    SELECT
        dim_time.GLOBAL_DATE_SHORT_DESC AS WEEK_DATE,
        SUM(fact.GLOBAL_VALUE_LC) AS POS_VALUE,
        SUM(fact.GLOBAL_UNITS) AS POS_UNITS
    FROM PROD_CUSTOMER360_GLBLSYNDCTD.CORE_ACCESS.GLBL_SYNDCTD_FACT_DATA fact
    INNER JOIN PROD_CUSTOMER360_GLBLSYNDCTD.CORE_ACCESS.GLBL_SYNDCTD_DIM_MARKET dim_market
        ON fact.market_id = dim_market.market_id
        AND dim_market.DELIVERY_KEY = fact.DELIVERY_KEY
    INNER JOIN PROD_CUSTOMER360_GLBLSYNDCTD.CORE_ACCESS.GLBL_SYNDCTD_DIM_TIME dim_time
        ON fact.date_id = dim_time.date_id
        AND fact.DELIVERY_KEY = dim_time.DELIVERY_KEY
    INNER JOIN PROD_CUSTOMER360_GLBLSYNDCTD.CORE_ACCESS.GLBL_SYNDCTD_DIM_PRODUCT dim_product
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
        cur.execute(official_query)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        val_base_agg = [0.0] * 12
        val_plan_agg = [0.0] * 12
        has_base = [False] * 12
        plan_weeks = {m: set() for m in range(1, 13)}

        for r in rows:
            d_str = str(r[0]).strip()
            val = float(r[1] or 0.0)
            try:
                dt = datetime.datetime.strptime(d_str[:10], "%Y-%m-%d").date()
            except Exception:
                continue

            d_info = KenvueCalendar.get_date_info(dt)
            yr, m_nbr = d_info.kv_year, d_info.kv_month_num
            if yr == base_year and m_nbr and 1 <= m_nbr <= 12:
                val_base_agg[m_nbr - 1] += val
                has_base[m_nbr - 1] = True
            elif yr == plan_year and m_nbr and 1 <= m_nbr <= 12:
                val_plan_agg[m_nbr - 1] += val
                plan_weeks[m_nbr].add(dt)

        for i in range(12):
            month_num = i + 1
            if has_base[i]:
                pos_base[i] = val_base_agg[i] / 1_000_000.0

            # Dynamic Completeness Check (100% Dynamic, Zero Hardcoding):
            # Derives expected weeks dynamically from KenvueCalendar.get_month_week_count (from kv_calender.py).
            # A month is ONLY treated as Actual if ALL expected weeks (4 or 5 weeks) are present in Snowflake.
            # Incomplete/partial months remain None until all weeks arrive.
            expected_weeks = KenvueCalendar.get_month_week_count(plan_year, month_num)
            actual_weeks = len(plan_weeks[month_num])
            if actual_weeks >= expected_weeks and actual_weeks > 0:
                pos_plan_actual[i] = val_plan_agg[i] / 1_000_000.0
            else:
                pos_plan_actual[i] = None
    except Exception as e:
        print(f"[Snowflake Query Error]: {e}")

    return pos_base, pos_plan_actual


# ─── 4. POSTGRESQL BUILDING BLOCKS & COMPOUND DRIVERS ────────────────────────

DRIVER_ROW_DEFINITIONS = [
    # (Category Group, Display Name, DB Match Key)
    ("External",     "Base Trend",          "BASE TREND"),
    ("External",     "Season",              "SEASON"),
    ("External",     "Competition",         "COMPETITION"),
    ("Distribution", "Distribution",        "DISTRIBUTION"),
    ("Innovation",   "Net Innovation",      "COMPOUND_NET_INNOVATION"),  # Innovation + Cannibalization
    ("Innovation",   "Innovation",          "INNOVATION"),
    ("Innovation",   "Cannibalization",     "CANNIBALIZATION"),
    ("Innovation",   "Discontinuations",    "DISCONTINUATIONS"),
    ("Innovation",   "Renovations",         "RENOVATION"),
    ("Investment",   "Media",               "MEDIA"),
    ("Investment",   "Trade",               "TRADE"),
    ("Price",        "Net Price",           "COMPOUND_NET_PRICE"),       # Price + Elasticity
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Other",        "Club",                "CLUB"),
    ("Other",        "Other (Not Defined)", "OTHER"),
]


def load_live_building_blocks(
    models: Union[str, List[str]], plan_year: int
) -> Dict[str, List[Optional[float]]]:
    """Loads Building Blocks aggregated across one or multiple models for the dynamic plan_year."""
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        return {disp: [None] * 12 for _, disp, _ in DRIVER_ROW_DEFINITIONS}

    conn = get_postgres_connection()
    conn.autocommit = True
    cur = conn.cursor()

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
    raw_bb = {}
    try:
        cur.execute(sql, (model_list, plan_year))
        for bb_name, m_num, val_k in cur.fetchall():
            if m_num and 1 <= int(m_num) <= 12:
                m_idx = int(m_num) - 1
                norm_bb = normalize_text(bb_name)
                val_m = float(val_k or 0.0) / 1000.0
                raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] = (raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] or 0.0) + val_m
    except Exception:
        conn.rollback()
        try:
            cur.execute(sql.replace("master_models", "hierarchy_models"), (model_list, plan_year))
            for bb_name, m_num, val_k in cur.fetchall():
                if m_num and 1 <= int(m_num) <= 12:
                    m_idx = int(m_num) - 1
                    norm_bb = normalize_text(bb_name)
                    val_m = float(val_k or 0.0) / 1000.0
                    raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] = (raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] or 0.0) + val_m
        except Exception:
            conn.rollback()
    finally:
        cur.close()
        conn.close()

    driver_data: Dict[str, List[Optional[float]]] = {}

    def _get_raw_val(pattern: str) -> List[Optional[float]]:
        res = [None] * 12
        for db_name, m_arr in raw_bb.items():
            if pattern in db_name:
                for i in range(12):
                    if m_arr[i] is not None:
                        res[i] = (res[i] or 0.0) + m_arr[i]
        return res

    innov = _get_raw_val("INNOVATION")
    cann = _get_raw_val("CANNIBALIZATION")
    price = _get_raw_val("PRICE")
    elast = _get_raw_val("ELASTICITY")

    for grp, disp_name, match_key in DRIVER_ROW_DEFINITIONS:
        if match_key == "COMPOUND_NET_INNOVATION":
            net_inv = [None] * 12
            for i in range(12):
                if innov[i] is not None or cann[i] is not None:
                    net_inv[i] = (innov[i] or 0.0) + (cann[i] or 0.0)
            driver_data[disp_name] = net_inv
        elif match_key == "COMPOUND_NET_PRICE":
            net_pr = [None] * 12
            for i in range(12):
                if price[i] is not None or elast[i] is not None:
                    net_pr[i] = (price[i] or 0.0) + (elast[i] or 0.0)
            driver_data[disp_name] = net_pr
        elif match_key == "INNOVATION":
            driver_data[disp_name] = innov
        elif match_key == "CANNIBALIZATION":
            driver_data[disp_name] = cann
        elif match_key == "PRICE":
            driver_data[disp_name] = price
        elif match_key == "ELASTICITY":
            driver_data[disp_name] = elast
        else:
            driver_data[disp_name] = _get_raw_val(match_key)

    return driver_data


# ─── 5. FULL MATRIX COMPUTATION (DYNAMIC YEARS) ──────────────────────────────

def calc_totals(monthly_vals: List[Optional[float]], cutoff_month: int = 0) -> Dict[str, Optional[float]]:
    def _sum_range(st, en):
        arr = [v for v in monthly_vals[st:en] if v is not None]
        return sum(arr) if arr else None

    return {
        "Q1": _sum_range(0, 3),
        "Q2": _sum_range(3, 6),
        "Q3": _sum_range(6, 9),
        "Q4": _sum_range(9, 12),
        "FY": _sum_range(0, 12),
        "YTD": _sum_range(0, cutoff_month),
        "YTG": _sum_range(cutoff_month, 12),
    }


def compute_consumption_summary_matrix(models: Union[str, List[str]]) -> Dict[str, Any]:
    base_year, plan_year = get_active_years()
    rules = load_model_rules(models)
    pos_base, pos_plan_actual = fetch_snowflake_monthly_pos(rules, base_year, plan_year)
    drivers = load_live_building_blocks(models, plan_year)

    individual_driver_names = [
        "Base Trend", "Season", "Competition", "Distribution", "Innovation",
        "Cannibalization", "Discontinuations", "Renovations", "Media", "Trade",
        "Price", "Elasticity", "Club", "Other (Not Defined)"
    ]

    total_monthly_bb = [0.0] * 12
    has_bb_for_month = [False] * 12
    for d_name in individual_driver_names:
        d_vals = drivers.get(d_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                total_monthly_bb[i] += d_vals[i]
                has_bb_for_month[i] = True

    bb_calculated_pos = [None] * 12
    for i in range(12):
        base_val = pos_base[i]
        bb_val = total_monthly_bb[i] if has_bb_for_month[i] else 0.0
        if base_val is not None:
            bb_calculated_pos[i] = base_val + bb_val
        elif has_bb_for_month[i]:
            bb_calculated_pos[i] = bb_val

    # Dynamically detect cutoff month from Snowflake actuals:
    # A month is treated as complete if pos_plan_actual is not None (handles positive, zero, and negative actuals).
    # If Snowflake has no complete actuals for any month, cutoff_month safely defaults to 0 (all forecast).
    detected_cutoff = 0
    for idx, v in enumerate(pos_plan_actual):
        if v is not None:
            detected_cutoff = idx + 1
    cutoff_month = detected_cutoff

    # Plan POS Row: Actuals for closed months with complete Snowflake data, Building Block calculated for forecast
    pos_plan = [None] * 12
    for i in range(12):
        month_num = i + 1
        if month_num <= cutoff_month and pos_plan_actual[i] is not None:
            pos_plan[i] = pos_plan_actual[i]
        else:
            pos_plan[i] = bb_calculated_pos[i]

    yoy_pct = [None] * 12
    for i in range(12):
        v_base = pos_base[i]
        v_plan = pos_plan[i]
        if v_base is not None and v_plan is not None and v_base != 0:
            yoy_pct[i] = ((v_plan - v_base) / abs(v_base)) * 100.0

    # Difference Row: Actuals from Snowflake - (Base Year POS + Building Blocks)
    # Automatically displays ONLY for closed months where complete Snowflake actuals exist
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

    totals_base = calc_totals(pos_base, cutoff_month)
    totals_plan = calc_totals(pos_plan, cutoff_month)

    driver_totals = {}
    for _, disp_name, _ in DRIVER_ROW_DEFINITIONS:
        driver_totals[disp_name] = calc_totals(drivers[disp_name], cutoff_month)

    totals_yoy = {}
    for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        v_b = totals_base.get(col)
        v_p = totals_plan.get(col)
        if v_b is not None and v_p is not None and v_b != 0:
            totals_yoy[col] = ((v_p - v_b) / abs(v_b)) * 100.0
        else:
            totals_yoy[col] = None

    totals_diff = {}
    def _sum_diff_slice(st, en):
        valid = [d for d in diff_val[st:en] if d is not None]
        return sum(valid) if valid else None

    totals_diff["Q1"] = _sum_diff_slice(0, 3)
    totals_diff["Q2"] = _sum_diff_slice(3, 6)
    totals_diff["Q3"] = _sum_diff_slice(6, 9)
    totals_diff["Q4"] = _sum_diff_slice(9, 12)
    totals_diff["FY"] = _sum_diff_slice(0, 12)
    totals_diff["YTD"] = _sum_diff_slice(0, cutoff_month)
    totals_diff["YTG"] = _sum_diff_slice(cutoff_month, 12)

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "cutoff_month": cutoff_month,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "models": models,
        "pos_base": pos_base,
        "totals_base": totals_base,
        "pos_plan": pos_plan,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "yoy_pct": yoy_pct,
        "totals_yoy": totals_yoy,
        "difference": diff_val,
        "totals_diff": totals_diff,
    }


# ─── 6. DYNAMIC COLOR CODING HEATMAP & FORMATTERS ────────────────────────────

def get_driver_heatmap_style(val: float, max_pos: float, max_neg_mag: float):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "#ffffff", "#111827", "500"
    v = float(val)
    if abs(v) <= 0.004:
        return "#ffffff", "#374151", "500"  # Neutral White

    if v > 0:
        ratio = (v / max_pos) if max_pos > 0 else 0
        if ratio >= 0.75:
            return "#00897b", "#ffffff", "700"   # Tier 5: Dark Rich Green
        elif ratio >= 0.50:
            return "#26a69a", "#ffffff", "600"   # Tier 4: Medium-Dark Green
        elif ratio >= 0.25:
            return "#4db6ac", "#004d40", "600"   # Tier 3: Medium Green
        elif ratio >= 0.10:
            return "#80cbc4", "#004d40", "600"   # Tier 2: Light Green
        else:
            return "#c8ece6", "#004d40", "500"   # Tier 1: Soft Pale Mint
    else:
        ratio = (abs(v) / max_neg_mag) if max_neg_mag > 0 else 0
        if ratio >= 0.75:
            return "#FF6B6B", "#ffffff", "700"   # Tier 5: High Red
        elif ratio >= 0.50:
            return "#ef6c6a", "#ffffff", "700"   # Tier 4: Strong Salmon/Red
        elif ratio >= 0.25:
            return "#f8a5a3", "#7f0000", "600"   # Tier 3: Medium Salmon
        elif ratio >= 0.10:
            return "#ffb4b2", "#7f0000", "600"   # Tier 2: Light Salmon
        else:
            return "#ffdcdb", "#b71c1c", "500"   # Tier 1: Soft Pale Pink


def fmt_currency(val, is_driver: bool = False, is_diff: bool = False) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    if is_driver or is_diff:
        if val < -0.0001:
            return f"(${abs(val):.2f})" if is_driver else f"(${abs(val):.1f})"
        return f"${val:.2f}" if is_driver else f"${val:.1f}"
    if val < 0:
        return f"-${abs(val):.1f}"
    return f"${val:.1f}"


def fmt_pct(val) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}%"


def build_data_cells(m_vals, totals, max_pos, max_neg_mag, is_driver=False, is_pct=False, bg_override=None):
    cells = []
    for val in m_vals:
        txt = fmt_pct(val) if is_pct else fmt_currency(val, is_driver=is_driver)
        cell_bg = bg_override or "#ffffff"
        text_color = "#111827"
        font_wt = "700" if (bg_override or is_pct) else "500"

        if is_driver:
            cell_bg, text_color, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        elif is_pct and val is not None:
            text_color = "#15803d" if val >= 0 else "#b91c1c"

        cells.append(html.Td(txt, style={
            "padding": "6px 8px", "textAlign": "right", "fontSize": "12px",
            "fontWeight": font_wt, "color": text_color, "backgroundColor": cell_bg,
            "border": "1px solid #e5e7eb"
        }))

    for idx, col_name in enumerate(["Q1", "Q2", "Q3", "Q4", "FY"]):
        val = totals.get(col_name)
        txt = fmt_pct(val) if is_pct else fmt_currency(val, is_driver=is_driver)
        b_left = "3px solid #9ca3af" if idx == 0 else "1px solid #e5e7eb"
        cell_bg = bg_override or "#f9fafb"
        text_color = "#111827"
        font_wt = "700"

        if is_driver:
            cell_bg, text_color, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        elif is_pct and val is not None:
            text_color = "#15803d" if val >= 0 else "#b91c1c"

        cells.append(html.Td(txt, style={
            "padding": "6px 8px", "textAlign": "right", "fontSize": "12px",
            "fontWeight": font_wt, "color": text_color, "backgroundColor": cell_bg,
            "border": "1px solid #e5e7eb", "borderLeft": b_left
        }))

    for idx, col_name in enumerate(["YTD", "YTG"]):
        val = totals.get(col_name)
        txt = fmt_pct(val) if is_pct else fmt_currency(val, is_driver=is_driver)
        b_left = "3px solid #9ca3af" if idx == 0 else "1px solid #e5e7eb"
        cell_bg = bg_override or "#f9fafb"
        text_color = "#111827"
        font_wt = "700"

        if is_driver:
            cell_bg, text_color, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        elif is_pct and val is not None:
            text_color = "#15803d" if val >= 0 else "#b91c1c"

        cells.append(html.Td(txt, style={
            "padding": "6px 8px", "textAlign": "right", "fontSize": "12px",
            "fontWeight": font_wt, "color": text_color, "backgroundColor": cell_bg,
            "border": "1px solid #e5e7eb", "borderLeft": b_left
        }))

    return cells


# ─── 7. UI PRESENTATION: CONSUMPTION MATRIX TABLE ────────────────────────────

def render_consumption_table(data: dict) -> html.Div:
    """Renders Consumption Matrix."""
    max_pos, max_neg_mag = 0.001, 0.001
    for d_name, m_vals in data["drivers"].items():
        for v in m_vals:
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                if v > max_pos: max_pos = v
                elif v < 0 and abs(v) > max_neg_mag: max_neg_mag = abs(v)

    th_style = {
        "backgroundColor": "#d7ece8", "color": "#1f2937", "fontWeight": "800",
        "fontSize": "13px", "padding": "8px 10px", "border": "1px solid #d1d5db",
        "textAlign": "center", "whiteSpace": "nowrap"
    }

    header_cells = [
        html.Th("", style={**th_style, "minWidth": "110px", "borderRight": "none"}),
        html.Th("Driver", style={**th_style, "minWidth": "160px", "textAlign": "left"}),
    ]

    for m in MONTHS:
        header_cells.append(html.Th(m, style=th_style))

    divider_style = {**th_style, "borderLeft": "3px solid #9ca3af"}
    header_cells.append(html.Th("Q1", style=divider_style))
    header_cells.append(html.Th("Q2", style=th_style))
    header_cells.append(html.Th("Q3", style=th_style))
    header_cells.append(html.Th("Q4", style=th_style))
    header_cells.append(html.Th("FY", style={**th_style, "fontWeight": "900"}))
    header_cells.append(html.Th("YTD", style=divider_style))
    header_cells.append(html.Th("YTG", style=th_style))

    thead = html.Thead(html.Tr(header_cells))
    tbody_rows = []

    # 1. Base Year Row (Dynamic Year Label)
    base_lbl = str(data.get("label_base") or data.get("base_year") or "")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td(base_lbl, style={"fontWeight": "800", "fontSize": "13px", "padding": "6px 10px", "border": "1px solid #e5e7eb"}),
        *build_data_cells(data["pos_base"], data["totals_base"], max_pos, max_neg_mag)
    ]))

    # 2. Driver Rows
    group_counts = {}
    for grp, _, _ in DRIVER_ROW_DEFINITIONS:
        group_counts[grp] = group_counts.get(grp, 0) + 1

    seen_groups = set()
    SUB_DRIVERS = {"Innovation", "Cannibalization", "Price", "Elasticity"}

    for grp, driver_name, _ in DRIVER_ROW_DEFINITIONS:
        cells = []
        if grp not in seen_groups:
            seen_groups.add(grp)
            cells.append(html.Td(
                grp, rowSpan=group_counts[grp],
                style={
                    "textAlign": "center", "verticalAlign": "middle",
                    "backgroundColor": "#dff0ea", "color": "#065f46",
                    "fontWeight": "800", "fontSize": "13px", "border": "1px solid #c4e4dc",
                    "padding": "8px 6px"
                }
            ))

        is_sub = driver_name in SUB_DRIVERS
        cells.append(html.Td(driver_name, style={
            "fontWeight": "500", "fontSize": "12px", "color": "#1f2937", "padding": "6px 14px",
            "border": "1px solid #e5e7eb", "textAlign": "right" if is_sub else "left",
            "fontStyle": "italic" if is_sub else "normal"
        }))

        d_vals = data["drivers"].get(driver_name, [None] * 12)
        d_totals = data["driver_totals"].get(driver_name, {})
        cells.extend(build_data_cells(d_vals, d_totals, max_pos, max_neg_mag, is_driver=True))
        tbody_rows.append(html.Tr(cells))

    # 3. Plan Year Row (Dynamic Year Label)
    plan_lbl = str(data.get("label_plan") or data.get("plan_year") or "")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td(plan_lbl, style={
            "fontWeight": "800", "fontSize": "13px", "padding": "6px 10px",
            "border": "1px solid #e5e7eb", "backgroundColor": "#f1ebfb", "color": "#111827"
        }),
        *build_data_cells(data["pos_plan"], data["totals_plan"], max_pos, max_neg_mag, bg_override="#faf6ff")
    ]))

    # 4. YoY % Row
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td("YoY %", style={"fontWeight": "800", "fontSize": "13px", "padding": "6px 10px", "border": "1px solid #e5e7eb", "color": "#004d40"}),
        *build_data_cells(data["yoy_pct"], data["totals_yoy"], max_pos, max_neg_mag, is_pct=True)
    ]))

    # 5. Difference Row
    diff_cells = []
    for val in data["difference"]:
        txt = fmt_currency(val, is_diff=True)
        col = "#00796b" if (val is not None and val >= 0) else "#dc2626"
        diff_cells.append(html.Td(txt, style={"padding": "6px 8px", "textAlign": "right", "fontSize": "12px", "fontWeight": "700", "color": col, "backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}))

    for col_name in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        val = data["totals_diff"].get(col_name)
        txt = fmt_currency(val, is_diff=True)
        col = "#00796b" if (val is not None and val >= 0) else "#dc2626"
        b_left = "3px solid #9ca3af" if col_name in ["Q1", "YTD"] else "1px solid #e5e7eb"
        diff_cells.append(html.Td(txt, style={"padding": "6px 8px", "textAlign": "right", "fontSize": "12px", "fontWeight": "700", "color": col, "backgroundColor": "#f9fafb", "border": "1px solid #e5e7eb", "borderLeft": b_left}))

    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td("Difference", style={"fontWeight": "800", "fontSize": "13px", "padding": "6px 10px", "border": "1px solid #e5e7eb", "color": "#1f2937"}),
        *diff_cells
    ]))

    return html.Div([
        html.Table([thead, html.Tbody(tbody_rows)], style={
            "width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff",
            "borderRadius": "8px", "boxShadow": "0 2px 8px rgba(0,0,0,0.04)"
        })
    ], style={"border": "1px solid #d1d5db", "borderRadius": "8px", "overflowX": "auto"})
