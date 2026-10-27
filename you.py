"""
gts.py
======
Authoritative Calculation Engine and UI Presentation for GTS YoY Dashboard:
1. Dynamic Years: Automatically detects plan_year and base_year (e.g. 2026 & 2025, or 2027 & 2026).
2. Historical Year Row: {base_year} GTS $ pulled directly from Snowflake VW_FACT_F360_SHIPMENTS (in $M).
3. 11 Building Block Drivers:
     GTS Driver[m] = Consumption Building Block[m] * Price Index[m]
     - Net Innovation = (Innovation GTS + Cannibalization GTS)
     - Net Price = (Price GTS + Elasticity GTS)
4. Current Year Row: {plan_year} GTS $ for each month is calculated as:
     - Completed months (<= cutoff): Snowflake Actual GTS $
     - Forecast months (> cutoff): Factory POS + Sum of Building Blocks
5. GTS YoY % Row:
     ((Plan GTS - Base GTS) / Base GTS) * 100
6. NO Difference Row (as specified).
7. Formatting: 1 decimal place (.1f) for all GTS $ currency values ($123.4M, -$5.6M), preventing -$0.0.
8. 11-Tier Dynamic Heatmap Gradient with High Red (#FF6B6B).
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

MONTH_NAME_MAP = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12
}


# ─── 0. DYNAMIC KENVUE 4-4-5 FISCAL CALENDAR (FROM kv_calender.py) ───────────

import sys
import types

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


def get_active_years() -> Tuple[int, int]:
    """Dynamically determines base_year and plan_year using Kenvue 4-4-5 Fiscal Calendar."""
    env_year = os.getenv("IBP_PLAN_YEAR")
    if env_year and env_year.isdigit():
        plan_year = int(env_year)
    else:
        today_info = KenvueCalendar.get_date_info(datetime.date.today())
        plan_year = today_info.kv_year
    base_year = plan_year - 1
    return base_year, plan_year


def normalize_text(val: Any) -> str:
    """Normalizes text values consistently."""
    if val is None:
        return ""
    s = str(val).replace("\xa0", " ").strip().upper()
    if s in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
        return ""
    return re.sub(r"\s+", " ", s)


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


def get_postgres_connection():
    """Connects to PostgreSQL na_ibp_db."""
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


def get_snowflake_connection():
    """Connects to Snowflake using RSA Private Key or password credentials."""
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    config = {
        "user": os.getenv("SNOWFLAKE_USER", "SA-JX2-SNFK-CVD-RPT@KENVUE.COM"),
        "account": os.getenv("SNOWFLAKE_ACCOUNT", "BK40750.east-us-2.azure"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "PROD_ENVIRONMENT_USAGE_XSMALL1_WH"),
        "database": os.getenv("SNOWFLAKE_DATABASE", "PROD_CVD_DISC"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "NAIBP_ACCESS"),
        "role": os.getenv("SNOWFLAKE_ROLE", "PROD_SA_JX2_SNFK_CVD_RPT_ER"),
    }
    private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    private_key_pem = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

    if private_key_path or private_key_pem:
        try:
            if private_key_path and os.path.exists(private_key_path):
                with open(private_key_path, "rb") as k_file:
                    p_key = serialization.load_pem_private_key(
                        k_file.read(),
                        password=passphrase.encode() if passphrase else None,
                        backend=default_backend()
                    )
            elif private_key_pem:
                pem_clean = private_key_pem.strip('"\'').replace("\\n", "\n")
                p_key = serialization.load_pem_private_key(
                    pem_clean.encode(),
                    password=passphrase.encode() if passphrase else None,
                    backend=default_backend()
                )
            else:
                p_key = None

            if p_key:
                pkb = p_key.private_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                config["private_key"] = pkb
        except Exception as e:
            print(f"[Snowflake Key Notice]: {e}")
            if os.getenv("SNOWFLAKE_PASSWORD"):
                config["password"] = os.getenv("SNOWFLAKE_PASSWORD")
    elif os.getenv("SNOWFLAKE_PASSWORD"):
        config["password"] = os.getenv("SNOWFLAKE_PASSWORD")

    return snowflake.connector.connect(**config)


# ─── DRIVER ROW DEFINITIONS (MATCHING CONSUMPTION & GTS DASHBOARD) ───────────

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


# ─── 1. POSTGRESQL HIERARCHY RULES ──────────────────────────────────────────

def load_model_rules(models: Union[str, List[str]]) -> List[Dict[str, str]]:
    """Loads product hierarchy rules (C1..C5, B1..B2) for selected model(s)."""
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
        SELECT shm.*
        FROM public.shipment_hierarchy_mapping shm
        INNER JOIN public.master_models mm ON shm.model_id = mm.model_id
        WHERE mm.model_name = ANY(%s) AND (shm.is_active IS NULL OR shm.is_active = TRUE);
        """,
        """
        SELECT chm.*
        FROM public.consumption_hierarchy_mapping chm
        INNER JOIN public.master_models mm ON chm.model_id = mm.model_id
        WHERE mm.model_name = ANY(%s) AND (chm.is_active IS NULL OR chm.is_active = TRUE);
        """
    ]

    rows = []
    col_names = []
    for q in queries:
        try:
            cur.execute(q, (model_list,))
            res = cur.fetchall()
            if res:
                rows = res
                col_names = [desc[0].lower() for desc in cur.description]
                break
        except Exception:
            conn.rollback()

    cur.close()
    conn.close()

    rules = []
    for r in rows:
        row_dict = dict(zip(col_names, r))
        c1 = (row_dict.get("c1_business_segment") or row_dict.get("business_segment") or
              row_dict.get("gbu_code") or row_dict.get("global_gmc_c1_business_segment_desc") or "")
        c2 = (row_dict.get("c2_business_subsegment") or row_dict.get("business_subsegment") or
              row_dict.get("global_gmc_c2_business_sub_segment_desc") or "")
        c3 = (row_dict.get("c3_need_state") or row_dict.get("need_state") or
              row_dict.get("squad_name") or row_dict.get("global_gmc_c3_need_state_desc") or "")
        c4 = (row_dict.get("c4_category") or row_dict.get("category") or
              row_dict.get("global_gmc_c4_category_desc") or "")
        c5 = (row_dict.get("c5_subcategory") or row_dict.get("subcategory") or
              row_dict.get("sub_category") or row_dict.get("global_gmc_c5_sub_category_desc") or "")
        b1 = (row_dict.get("b1_brand") or row_dict.get("brand_name") or
              row_dict.get("brand") or row_dict.get("global_gmc_b1_brand_desc") or "")
        b2 = (row_dict.get("b2_subbrand") or row_dict.get("sub_brand_name") or
              row_dict.get("sub_brand") or row_dict.get("subbrand") or
              row_dict.get("global_gmc_b2_sub_brand_desc") or "")

        rule = {
            "C1_BUSINESS_SEGMENT": normalize_text(c1),
            "C2_BUSINESS_SUBSEGMENT": normalize_text(c2),
            "C3_NEED_STATE": normalize_text(c3),
            "C4_CATEGORY": normalize_text(c4),
            "C5_SUBCATEGORY": normalize_text(c5),
            "B1_BRAND": normalize_text(b1),
            "B2_SUBBRAND": normalize_text(b2),
        }
        if any(rule.values()):
            rules.append(rule)

    return rules


# ─── 2. POSTGRESQL MODEL PRICE INDEX MULTIPLIERS ─────────────────────────────

def load_price_index_from_postgres(
    models: Union[str, List[str]], plan_year: int
) -> Dict[int, float]:
    """
    Queries public.model_price_index in PostgreSQL for selected model(s).
    Returns mapping: month_num (1..12) -> multiplier (float).
    """
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        return {m: 1.0 for m in range(1, 13)}

    monthly_indices: Dict[int, List[float]] = {m: [] for m in range(1, 13)}

    try:
        conn = get_postgres_connection()
        conn.autocommit = True
        cur = conn.cursor()

        queries = [
            """
            SELECT mpi.*
            FROM public.model_price_index mpi
            INNER JOIN public.master_models mm ON mpi.model_id = mm.model_id
            WHERE mm.model_name = ANY(%s);
            """,
            """
            SELECT mpi.*
            FROM public.model_price_index mpi
            WHERE (mpi.model_name = ANY(%s) OR mpi.model = ANY(%s));
            """
        ]

        rows = []
        col_names = []
        for q in queries:
            try:
                params = (model_list,) if q.count("%s") == 1 else (model_list, model_list)
                cur.execute(q, params)
                res = cur.fetchall()
                if res:
                    rows = res
                    col_names = [desc[0].lower() for desc in cur.description]
                    break
            except Exception:
                conn.rollback()

        cur.close()
        conn.close()

        for r in rows:
            row_dict = dict(zip(col_names, r))
            row_yr = row_dict.get("year") or row_dict.get("plan_year") or row_dict.get("period_year")
            if row_yr is not None:
                try:
                    if int(row_yr) != plan_year:
                        continue
                except (ValueError, TypeError):
                    pass
            raw_month = (
                row_dict.get("month_num") or row_dict.get("month") or
                row_dict.get("period_month") or row_dict.get("mnth")
            )
            m_num = parse_month_num(raw_month)
            raw_idx = (
                row_dict.get("price_index") or row_dict.get("index") or
                row_dict.get("index_value") or row_dict.get("index_val") or
                row_dict.get("multiplier")
            )
            if m_num and 1 <= m_num <= 12 and raw_idx is not None:
                try:
                    val = float(raw_idx)
                    if val > 0:
                        monthly_indices[m_num].append(val)
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"[Price Index DB Notice]: {e}")

    final_indices = {}
    for m in range(1, 13):
        arr = monthly_indices[m]
        final_indices[m] = (sum(arr) / len(arr)) if arr else 1.0

    return final_indices


# ─── 3. SNOWFLAKE HISTORICAL GTS $ INGESTION ─────────────────────────────────

def fetch_snowflake_monthly_gts(
    rules: List[Dict[str, str]], base_year: int, plan_year: Optional[int] = None
) -> Union[List[Optional[float]], Tuple[List[Optional[float]], List[Optional[float]]]]:
    """
    Queries PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS in Snowflake.
    If plan_year is provided, returns (gts_base, gts_plan_actual).
    Otherwise returns gts_base for backward compatibility.
    """
    gts_base = [None] * 12
    gts_plan_actual = [None] * 12
    if not rules:
        return (gts_base, gts_plan_actual) if plan_year is not None else gts_base

    row_conditions = []
    for r in rules:
        field_conds = []
        for f in ["C1_BUSINESS_SEGMENT", "C2_BUSINESS_SUBSEGMENT", "C3_NEED_STATE", "C4_CATEGORY", "C5_SUBCATEGORY", "B1_BRAND", "B2_SUBBRAND"]:
            val = r.get(f, "").strip()
            if val and val not in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
                val_esc = val.replace("'", "''")
                field_conds.append(f"UPPER(TRIM(COALESCE({f}, ''))) = '{val_esc}'")
        if field_conds:
            row_conditions.append("(" + " AND ".join(field_conds) + ")")

    if not row_conditions:
        return (gts_base, gts_plan_actual) if plan_year is not None else gts_base

    where_clause = " OR\n        ".join(row_conditions)
    year_filter = f"YEAR IN ({base_year}, {plan_year})" if plan_year is not None else f"YEAR = {base_year}"
    query = f"""
    SELECT
        YEAR,
        MONTHNUMBER,
        SUM(GTS_AMT) AS GTS_AMT
    FROM PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS
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
        conn.close()

        for yr_val, mo_val, amt_val in rows:
            yr = int(yr_val or 0)
            mo = int(mo_val or 0)
            if 1 <= mo <= 12:
                m_idx = mo - 1
                val_m = float(amt_val or 0.0) / 1_000_000.0  # Dollars to Millions ($M)
                if yr == base_year:
                    gts_base[m_idx] = (gts_base[m_idx] or 0.0) + val_m
                elif plan_year is not None and yr == plan_year:
                    gts_plan_actual[m_idx] = (gts_plan_actual[m_idx] or 0.0) + val_m
    except Exception as e:
        print(f"[Snowflake GTS Query Notice]: {e}")

    return (gts_base, gts_plan_actual) if plan_year is not None else gts_base


# ─── 4. POSTGRESQL LIVE BUILDING BLOCKS * PRICE INDEX (GTS YoY) ─────────────

def load_live_gts_building_blocks(
    models: Union[str, List[str]], plan_year: int, price_indices: Dict[int, float]
) -> Dict[str, List[Optional[float]]]:
    """
    Authoritative Building Blocks calculation for GTS YoY Dashboard:
    Formula: GTS Building Block[m] = Consumption Building Block[m] * Price Index[m]
    Matches the official business rule: gts.py = consumption_summary.py * price factor.
    """
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]

    if not model_list:
        return {disp: [None] * 12 for _, disp, _ in DRIVER_ROW_DEFINITIONS}

    upper_models = [m.upper() for m in model_list]

    # First attempt: import and reuse consumption_summary directly if available
    raw_bb: Dict[str, List[Optional[float]]] = {}
    try:
        import consumption_summary as cs
        cons_drivers = cs.load_live_building_blocks(model_list, plan_year)
        if any(any(v is not None and v != 0 for v in vals) for vals in cons_drivers.values()):
            # Multiply consumption building blocks by price index
            driver_data: Dict[str, List[Optional[float]]] = {}
            for _, disp_name, _ in DRIVER_ROW_DEFINITIONS:
                c_vals = cons_drivers.get(disp_name, [None] * 12)
                g_vals = [None] * 12
                has_any = False
                for i in range(12):
                    v = c_vals[i]
                    if v is not None:
                        pi = price_indices.get(i + 1, 1.0)
                        g_vals[i] = round(v * pi, 4)
                        has_any = True
                driver_data[disp_name] = g_vals if has_any else [None] * 12

            # Recalculate compound drivers
            net_inno = [None] * 12
            for i in range(12):
                iv = driver_data.get("Innovation", [None] * 12)[i]
                cv = driver_data.get("Cannibalization", [None] * 12)[i]
                if iv is not None or cv is not None:
                    net_inno[i] = round((iv or 0.0) + (cv or 0.0), 4)
            driver_data["Net Innovation"] = net_inno

            net_price = [None] * 12
            for i in range(12):
                pv = driver_data.get("Price", [None] * 12)[i]
                ev = driver_data.get("Elasticity", [None] * 12)[i]
                if pv is not None or ev is not None:
                    net_price[i] = round((pv or 0.0) + (ev or 0.0), 4)
            driver_data["Net Price"] = net_price

            return driver_data
    except Exception as e:
        print(f"[GTS Live BB Import Notice]: {e}")

    # Fallback: direct query to PostgreSQL na_ibp_db
    try:
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
            (mm.model_name = ANY(%s) OR UPPER(TRIM(mm.model_name)) = ANY(%s))
            AND cpr.is_deleted = FALSE
            AND cbb.is_active = TRUE
            AND mm.is_active = TRUE
            AND EXTRACT(YEAR FROM cpv.period_month) = %s
        GROUP BY cbb.name, month_num
        ORDER BY cbb.name, month_num;
        """
        try:
            cur.execute(sql, (model_list, upper_models, plan_year))
            rows = cur.fetchall()
        except Exception:
            conn.rollback()
            cur.execute(sql.replace("master_models", "hierarchy_models"), (model_list, upper_models, plan_year))
            rows = cur.fetchall()

        for bb_name, m_num, val_k in rows:
            if m_num and 1 <= int(m_num) <= 12:
                m_idx = int(m_num) - 1
                norm_bb = normalize_text(bb_name)
                val_m = float(val_k or 0.0) / 1000.0  # Thousands to Millions ($M)
                raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] = (raw_bb.setdefault(norm_bb, [None] * 12)[m_idx] or 0.0) + val_m

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[GTS Live BB DB Notice]: {e}")

    def _get_raw_val(pattern: str) -> List[Optional[float]]:
        res = [None] * 12
        matched = False
        for db_name, m_arr in raw_bb.items():
            if pattern in db_name:
                for i in range(12):
                    if m_arr[i] is not None:
                        res[i] = (res[i] or 0.0) + m_arr[i]
                        matched = True
        return res if matched else [None] * 12

    driver_data: Dict[str, List[Optional[float]]] = {}
    for grp, disp_name, match_key in DRIVER_ROW_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        c_vals = _get_raw_val(match_key)
        g_vals = [None] * 12
        has_any = False
        for i in range(12):
            v = c_vals[i]
            if v is not None:
                pi = price_indices.get(i + 1, 1.0)
                g_vals[i] = round(v * pi, 4)
                has_any = True
        driver_data[disp_name] = g_vals if has_any else [None] * 12

    # Compound Net Innovation
    innov = driver_data.get("Innovation", [None] * 12)
    cann = driver_data.get("Cannibalization", [None] * 12)
    net_inno = [None] * 12
    for i in range(12):
        if innov[i] is not None or cann[i] is not None:
            net_inno[i] = round((iv := innov[i] or 0.0) + (cv := cann[i] or 0.0), 4)
    driver_data["Net Innovation"] = net_inno

    # Compound Net Price
    price = driver_data.get("Price", [None] * 12)
    elast = driver_data.get("Elasticity", [None] * 12)
    net_price = [None] * 12
    for i in range(12):
        if price[i] is not None or elast[i] is not None:
            net_price[i] = round((pv := price[i] or 0.0) + (ev := elast[i] or 0.0), 4)
    driver_data["Net Price"] = net_price

    return driver_data


# Alias for backward compatibility with existing tests
load_coc_building_blocks = load_live_gts_building_blocks


# ─── 5. AGGREGATIONS & GTS YoY MATRIX ENGINE ─────────────────────────────────

def calc_totals(monthly_vals: List[Optional[float]], cutoff_month: int = 0) -> Dict[str, Optional[float]]:
    """Calculates Q1..Q4, FY, YTD, and YTG totals dynamically."""
    has_data = any(v is not None for v in monthly_vals)
    if not has_data:
        return {col: None for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]}

    def _sum_range(st, en):
        arr = [v for v in monthly_vals[st:en] if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return round(sum(arr), 4) if arr else 0.0

    return {
        "Q1": _sum_range(0, 3),
        "Q2": _sum_range(3, 6),
        "Q3": _sum_range(6, 9),
        "Q4": _sum_range(9, 12),
        "FY": _sum_range(0, 12),
        "YTD": _sum_range(0, cutoff_month),
        "YTG": _sum_range(cutoff_month, 12),
    }


def compute_gts_summary_matrix(models: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Computes complete GTS YoY Summary Matrix:
    1. Historical Row: {base_year} GTS $ from Snowflake VW_FACT_F360_SHIPMENTS
    2. Factory POS $ integration from consumption_summary.py * price_index
    3. Building Blocks: Sourced dynamically for plan_year
    4. Current Row: {plan_year} GTS $:
         - Actual GTS shipments for completed months
         - Forecast (Baseline + Building Blocks) for remaining months
    5. GTS YoY % Row: ((Plan GTS - Base GTS) / Base GTS) * 100
    6. NO Difference row
    """
    base_year, plan_year = get_active_years()
    rules = load_model_rules(models)

    # 1. Base Year and Plan Year GTS actuals from Snowflake
    gts_base, gts_plan_actual = fetch_snowflake_monthly_gts(rules, base_year, plan_year)

    # 2. Price Index multipliers from PostgreSQL
    price_indices = load_price_index_from_postgres(models, plan_year)

    # 3. Consumption Summary & Factory POS Integration
    pos_plan = [0.0] * 12
    cons_cutoff = 0
    cons_data = {}
    try:
        import consumption_summary as cs
        cons_data = cs.compute_consumption_summary_matrix(models)
        pos_plan_raw = cons_data.get("pos_plan", [0.0] * 12)
        pos_plan = [float(v or 0.0) for v in pos_plan_raw]
        cons_cutoff = int(cons_data.get("cutoff_month") or 0)
    except Exception as e:
        print(f"[Consumption Summary / Factory POS Integration Notice]: {e}")

    factory_pos = [0.0] * 12
    for i in range(12):
        month_num = i + 1
        pos_val = pos_plan[i]
        idx_mult = price_indices.get(month_num, 1.0)
        factory_pos[i] = round(pos_val * idx_mult, 2)

    # 4. Building Blocks: Consumption Building Blocks * Price Index
    drivers = load_coc_building_blocks(models, plan_year, price_indices)

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

    # 5. Dynamically detect cutoff month from Snowflake plan_year GTS actuals
    detected_gts_cutoff = 0
    for idx, v in enumerate(gts_plan_actual):
        if v is not None:
            detected_gts_cutoff = idx + 1

    # Safe dynamic fallback:
    if detected_gts_cutoff > 0:
        cutoff_month = detected_gts_cutoff
    elif cons_cutoff > 0:
        cutoff_month = cons_cutoff
    else:
        cutoff_month = 0

    # 6. Current Year GTS Row Population:
    gts_plan = [0.0] * 12
    for i in range(12):
        if i < cutoff_month and gts_plan_actual[i] is not None:
            gts_plan[i] = round(gts_plan_actual[i], 2)
        else:
            baseline = gts_base[i] if gts_base[i] is not None else factory_pos[i]
            bb = total_monthly_bb[i] if has_bb_for_month[i] else 0.0
            gts_plan[i] = round((baseline or 0.0) + bb, 2)

    # 7. GTS YoY % Calculation against Base GTS
    gts_yoy_pct = [0.0] * 12
    for i in range(12):
        v_base = gts_base[i]
        v_plan = gts_plan[i]
        if v_base and v_base > 0 and v_plan is not None:
            gts_yoy_pct[i] = ((v_plan - v_base) / v_base) * 100.0
        else:
            gts_yoy_pct[i] = 0.0

    # 8. Totals calculation
    totals_base = calc_totals(gts_base, cutoff_month)
    totals_plan = calc_totals(gts_plan, cutoff_month)
    totals_factory_pos = calc_totals(factory_pos, cutoff_month)

    totals_yoy = {}
    for col_name in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        b_val = totals_base.get(col_name)
        p_val = totals_plan.get(col_name)
        if b_val and b_val > 0 and p_val is not None:
            totals_yoy[col_name] = ((p_val - b_val) / b_val) * 100.0
        else:
            totals_yoy[col_name] = 0.0

    driver_totals = {}
    for _, disp_name, _ in DRIVER_ROW_DEFINITIONS:
        m_vals = drivers.get(disp_name, [None] * 12)
        driver_totals[disp_name] = calc_totals(m_vals, cutoff_month)

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "cutoff_month": cutoff_month,
        "label_base": f"{base_year} GTS $",
        "label_plan": f"{plan_year} GTS $",
        "label_gts": f"{plan_year} GTS $",
        "label_pct": "GTS YoY %",
        "models": models,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_plan_actual": gts_plan_actual,
        "gts_plan": gts_plan,
        "totals_plan": totals_plan,
        "totals_gts": totals_plan,
        "factory_pos": factory_pos,
        "totals_factory_pos": totals_factory_pos,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "gts_yoy_pct": gts_yoy_pct,
        "totals_yoy": totals_yoy,
    }


# ─── 6. DYNAMIC HEATMAP & FORMATTING HELPERS (1 DECIMAL PLACE) ───────────────

def get_driver_heatmap_style(val: float, max_pos: float, max_neg_mag: float):
    """11-Tier Dynamic Heatmap Gradient with High Red (#FF6B6B)."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "#ffffff", "#111827", "500"
    v = float(val)
    if abs(v) <= 0.004:
        return "#ffffff", "#374151", "500"

    if v > 0:
        ratio = (v / max_pos) if max_pos > 0 else 0
        if ratio >= 0.75:
            return "#00897b", "#ffffff", "700"
        elif ratio >= 0.50:
            return "#26a69a", "#ffffff", "600"
        elif ratio >= 0.25:
            return "#4db6ac", "#004d40", "600"
        elif ratio >= 0.10:
            return "#80cbc4", "#004d40", "600"
        else:
            return "#c8ece6", "#004d40", "500"
    else:
        ratio = (abs(v) / max_neg_mag) if max_neg_mag > 0 else 0
        if ratio >= 0.75:
            return "#FF6B6B", "#ffffff", "700"   # Tier 5: High Red (#FF6B6B)
        elif ratio >= 0.50:
            return "#ef6c6a", "#ffffff", "700"
        elif ratio >= 0.25:
            return "#f8a5a3", "#7f0000", "600"
        elif ratio >= 0.10:
            return "#ffcdd2", "#7f0000", "600"
        else:
            return "#ffebee", "#7f0000", "500"


def fmt_currency(val, is_driver: bool = False, decimals: int = 1) -> str:
    """Formats GTS currency values to 1 decimal place (.1f). Prevents -$0.0."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    v = float(val)
    if round(abs(v), decimals) == 0:
        return "$0.0" if decimals == 1 else "$0.00"
    if is_driver:
        if v < 0:
            return f"-${abs(v):,.{decimals}f}"
        return f"${v:,.{decimals}f}"
    return f"${v:,.{decimals}f}"


def fmt_pct(val, decimals: int = 1) -> str:
    """Formats percentage values to 1 decimal place. Prevents -0.0%."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    v = float(val)
    if round(abs(v), decimals) == 0:
        return f"{0.0:.{decimals}f}%"
    return f"{v:.{decimals}f}%"


def build_data_cells(m_vals, totals, max_pos, max_neg_mag, is_driver=False, is_pct=False, bg_override=None, decimals=1):
    """Builds monthly, quarterly, and full-year table cells with 1 decimal formatting."""
    cells = []
    for val in m_vals:
        txt = fmt_pct(val, decimals=decimals) if is_pct else fmt_currency(val, is_driver=is_driver, decimals=decimals)
        if bg_override:
            bg_col = bg_override
            txt_col = "#111827"
            font_wt = "700"
        elif is_driver:
            bg_col, txt_col, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        elif is_pct:
            bg_col = "#ffffff"
            txt_col = "#004d40" if (val is not None and val >= 0) else "#7f0000"
            font_wt = "700"
        else:
            bg_col = "#ffffff"
            txt_col = "#111827"
            font_wt = "700"

        cells.append(html.Td(txt, style={
            "padding": "6px 8px", "textAlign": "right", "fontSize": "12px",
            "backgroundColor": bg_col, "color": txt_col, "fontWeight": font_wt,
            "border": "1px solid #e5e7eb"
        }))

    for col_name in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        val = totals.get(col_name)
        txt = fmt_pct(val, decimals=decimals) if is_pct else fmt_currency(val, is_driver=is_driver, decimals=decimals)

        if bg_override:
            bg_col = bg_override
            txt_col = "#111827"
            font_wt = "700"
        elif is_driver:
            bg_col, txt_col, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        elif is_pct:
            bg_col = "#f9fafb"
            txt_col = "#004d40" if (val is not None and val >= 0) else "#7f0000"
            font_wt = "700"
        else:
            bg_col = "#f9fafb"
            txt_col = "#111827"
            font_wt = "800"

        b_left = "3px solid #9ca3af" if col_name in ["Q1", "YTD"] else "1px solid #e5e7eb"

        cells.append(html.Td(txt, style={
            "padding": "6px 8px", "textAlign": "right", "fontSize": "12px",
            "backgroundColor": bg_col, "color": txt_col, "fontWeight": font_wt,
            "border": "1px solid #e5e7eb", "borderLeft": b_left
        }))

    return cells


# ─── 7. GTS YoY TABLE RENDERER (NO DIFFERENCE ROW, 1 DECIMAL PLACE) ─────────

def render_gts_table(data: dict) -> html.Div:
    """
    Renders GTS YoY Summary Matrix:
    1. {base_year} GTS $ (from Snowflake)
    2. 11 Building Block Drivers: Consumption BB * Price Index
    3. {plan_year} GTS $ (Actuals for completed months, Forecast for remaining months)
    4. GTS YoY %
    (NO Difference row, all currency in .1f decimal precision)
    """
    max_pos, max_neg_mag = 0.001, 0.001
    for d_name, m_vals in data["drivers"].items():
        for v in m_vals:
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                if v > max_pos:
                    max_pos = v
                elif v < 0 and abs(v) > max_neg_mag:
                    max_neg_mag = abs(v)

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

    # 1. Base Year Row: {base_year} GTS $
    base_yr = data.get("base_year")
    base_label = data.get("label_base") or (f"{base_yr} GTS $" if base_yr else "Base GTS $")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td(base_label, style={
            "fontWeight": "800", "fontSize": "13px", "padding": "6px 10px", "border": "1px solid #e5e7eb"
        }),
        *build_data_cells(data["gts_base"], data["totals_base"], max_pos, max_neg_mag, decimals=1)
    ]))

    # 2. Driver Rows (11 Drivers: Consumption BB * Price Index)
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
        cells.extend(build_data_cells(d_vals, d_totals, max_pos, max_neg_mag, is_driver=True, decimals=1))
        tbody_rows.append(html.Tr(cells))

    # 3. Plan Year Row: {plan_year} GTS $
    plan_yr = data.get("plan_year")
    plan_label = data.get("label_plan") or data.get("label_gts") or (f"{plan_yr} GTS $" if plan_yr else "Plan GTS $")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td(plan_label, style={
            "fontWeight": "800", "fontSize": "13px", "padding": "6px 10px",
            "border": "1px solid #e5e7eb", "backgroundColor": "#f1ebfb", "color": "#111827"
        }),
        *build_data_cells(data["gts_plan"], data.get("totals_plan") or data.get("totals_gts", {}), max_pos, max_neg_mag, bg_override="#faf6ff", decimals=1)
    ]))

    # 4. GTS YoY % Row
    pct_label = data.get("label_pct", "GTS YoY %")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#ffffff", "border": "1px solid #e5e7eb"}),
        html.Td(pct_label, style={
            "fontWeight": "800", "fontSize": "13px", "padding": "6px 10px",
            "border": "1px solid #e5e7eb", "color": "#004d40"
        }),
        *build_data_cells(data["gts_yoy_pct"], data["totals_yoy"], max_pos, max_neg_mag, is_pct=True, decimals=1)
    ]))

    return html.Div([
        html.Table([thead, html.Tbody(tbody_rows)], style={
            "width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff",
            "borderRadius": "8px", "boxShadow": "0 2px 8px rgba(0,0,0,0.04)"
        })
    ], style={"border": "1px solid #d1d5db", "borderRadius": "8px", "overflow": "hidden"})
