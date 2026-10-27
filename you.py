"""
shipment_summary.py
===================
Authoritative Calculation Engine for Shipment Summary Dashboard (Matching Images 1 & 2):
1. Drivers & Categories:
   - Top Row: {plan_year} FACTORY POS (Computed via POS $ * model_price_index from PostgreSQL)
   - Category 1: Inventory (Distribution, Innovation, Trade, Club, Retailer Inventory, Other)
   - Category 2: IBP Overlays (Supply Constraints, Liquidations, Other)
   - Bottom Rows: {plan_year} GTS and GTS YoY %
2. Smart Blank vs $0.00 Handling (Using Direct Pivoted PostgreSQL Query):
   - Active drivers with partial records: unentered months returned as 0.0000 -> displayed as $0.00 (Image 1)
   - Drivers/models with no building blocks: query returns 0 rows -> kept completely blank (None) (Image 2)
3. Dynamic Years: Automatically rolls with active plan_year and base_year using Kenvue 4-4-5 Fiscal Calendar.
4. PostgreSQL Hierarchy Mapping:
   - Queries public.shipment_hierarchy_mapping joined with public.master_models
5. PostgreSQL Price Index:
   - Queries public.model_price_index joined with public.master_models
6. Snowflake GTS $ Integration:
   - Queries PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS
7. PostgreSQL Live Shipment Building Blocks:
   - Queries public.shipment_planning_rows, shipment_building_blocks, shipment_planning_values
"""

import os
import re
import math
import datetime
from typing import Optional, Dict, List, Tuple, Any, Union
from dotenv import load_dotenv

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
    """Normalizes strings consistently."""
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


# ─── SHIPMENT DRIVER ROW DEFINITIONS (MATCHING IMAGE 3) ──────────────────────

SHIPMENT_DRIVER_ROW_DEFINITIONS = [
    # (Category Group, Display Name, DB Match Key)
    ("Inventory",    "Distribution",       "DISTRIBUTION"),
    ("Inventory",    "Innovation",         "INNOVATION"),
    ("Inventory",    "Trade",              "TRADE"),
    ("Inventory",    "Club",               "CLUB"),
    ("Inventory",    "Retailer Inventory", "RETAILER_INVENTORY"),
    ("Inventory",    "Other",              "OTHER"),
    ("IBP Overlays", "Supply Constraints", "SUPPLY_CONSTRAINTS"),
    ("IBP Overlays", "Liquidations",       "LIQUIDATIONS"),
    ("IBP Overlays", "Other",              "OVERLAYS_OTHER"),
]


# ─── 1. POSTGRESQL MODEL PRICE INDEX MULTIPLIERS ─────────────────────────────

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


# ─── 2. POSTGRESQL SHIPMENT HIERARCHY MAPPING ───────────────────────────────

def load_shipment_model_rules(models: Union[str, List[str]]) -> List[Dict[str, str]]:
    """
    Queries public.shipment_hierarchy_mapping joined with public.master_models
    to extract product hierarchy rules (C1..C5, B1..B2) for the selected model(s).
    """
    if isinstance(models, str):
        model_list = [models.strip()]
    else:
        model_list = [str(m).strip() for m in models if m]
    if not model_list:
        return []
    rows = []
    col_names = []
    try:
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
            SELECT shm.*
            FROM public.shipment_hierarchy_mapping shm
            WHERE (shm.model_name = ANY(%s) OR shm.model = ANY(%s))
              AND (shm.is_active IS NULL OR shm.is_active = TRUE);
            """
        ]
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
    except Exception as e:
        print(f"[Shipment Hierarchy Mapping Notice]: {e}")
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


# ─── 3. SNOWFLAKE ACTUAL GTS $ DATA INGESTION ────────────────────────────────

def fetch_snowflake_monthly_gts(
    rules: List[Dict[str, str]], base_year: int, plan_year: int
) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """
    Queries PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS in Snowflake.
    Returns:
      gts_base: 12 months of base_year GTS $ in Millions ($M)
      gts_plan_actual: 12 months of plan_year GTS $ in Millions ($M)
    """
    gts_base = [None] * 12
    gts_plan_actual = [None] * 12
    if not rules:
        return gts_base, gts_plan_actual
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
        return gts_base, gts_plan_actual
    where_clause = " OR\n        ".join(row_conditions)
    query = f"""
    SELECT
        YEAR,
        MONTHNUMBER,
        SUM(GTS_AMT) AS GTS_AMT,
        SUM(GTS_QTY) AS GTS_QTY
    FROM PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS
    WHERE
        ({where_clause})
        AND YEAR IN ({base_year}, {plan_year})
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
        for yr_val, mo_val, amt_val, _ in rows:
            yr = int(yr_val or 0)
            mo = int(mo_val or 0)
            if 1 <= mo <= 12:
                m_idx = mo - 1
                val_m = float(amt_val or 0.0) / 1_000_000.0  # Dollars to Millions ($M)
                if yr == base_year:
                    gts_base[m_idx] = (gts_base[m_idx] or 0.0) + val_m
                elif yr == plan_year:
                    gts_plan_actual[m_idx] = (gts_plan_actual[m_idx] or 0.0) + val_m
    except Exception as e:
        print(f"[Snowflake Shipment Query Notice]: {e}")
    return gts_base, gts_plan_actual


# ─── 4. POSTGRESQL LIVE SHIPMENT BUILDING BLOCKS (PIVOTED MONTHLY QUERY) ────

def _clean_token(s: Any) -> str:
    """Normalizes string into uppercase alphanumeric token for fuzzy driver matching."""
    if s is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _matches_driver(db_name: str, grp: str, disp_name: str, match_key: str) -> bool:
    """Matches a PostgreSQL building block name to a defined dashboard driver."""
    c_db = _clean_token(db_name)
    c_disp = _clean_token(disp_name)
    c_key = _clean_token(match_key)
    if not c_db:
        return False
    # Special handling for "Other" in Inventory vs IBP Overlays
    if c_disp == "OTHER":
        if "OVERLAY" in c_db or "IBP" in c_db:
            return grp == "IBP Overlays"
        if "INVENT" in c_db:
            return grp == "Inventory"
        return grp == "Inventory" if "OVERLAY" not in c_key else grp == "IBP Overlays"
    # Specific driver root matching
    if "LIQUIDAT" in c_key and "LIQUIDAT" in c_db:
        return True
    if "SUPPLY" in c_key and "SUPPLY" in c_db:
        return True
    if "RETAIL" in c_key and "RETAIL" in c_db:
        return True
    if "DISTRIB" in c_key and "DISTRIB" in c_db:
        return True
    if "INNOVAT" in c_key and "INNOVAT" in c_db:
        return True
    if "TRADE" in c_key and "TRADE" in c_db:
        return True
    if "CLUB" in c_key and "CLUB" in c_db:
        return True
    return (c_key in c_db) or (c_disp in c_db) or (c_db in c_key) or (c_db in c_disp)


def load_live_shipment_building_blocks(
    models: Union[str, List[str]], plan_year: int
) -> Dict[Any, List[Optional[float]]]:
    """
    Queries live shipment building blocks from PostgreSQL using the exact pivoted monthly query:
    - If a model has building blocks: Returns entered and unentered months.
    - If a model has NO building blocks: All driver rows remain completely blank (None).
    """
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
    rows = []
    try:
        conn = get_postgres_connection()
        conn.autocommit = True
        cur = conn.cursor()
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
            ROUND(SUM(CASE WHEN EXTRACT(MONTH FROM spv.period_month) = 12 THEN spv.value_in_thousands / 1000.0 ELSE 0 END)::numeric, 4) AS dec_m,
            ROUND(SUM(spv.value_in_thousands / 1000.0)::numeric, 4) AS full_year_total_m
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
        cur.execute(sql, (model_list, plan_year))
        rows = cur.fetchall()
        if not rows and model_list:
            sql_fallback = sql.replace("mm.model_name = ANY(%s)", "UPPER(TRIM(mm.model_name)) = ANY(%s)")
            upper_models = [m.strip().upper() for m in model_list]
            cur.execute(sql_fallback, (upper_models, plan_year))
            rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Shipment Building Block Notice]: {e}")
    if not rows:
        empty_res = {}
        for grp, disp, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
            empty_res[disp] = [None] * 12
            empty_res[(grp, disp)] = [None] * 12
            empty_res[f"{grp}_{disp}"] = [None] * 12
        return empty_res
    driver_data: Dict[Any, List[Optional[float]]] = {}
    for grp, disp_name, match_key in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        matched = False
        monthly_accum = [0.0] * 12
        for r in rows:
            db_bb_name = str(r[0] or "")
            if _matches_driver(db_bb_name, grp, disp_name, match_key):
                matched = True
                for m_idx in range(12):
                    val = float(r[m_idx + 1] or 0.0)
                    monthly_accum[m_idx] += val
        if matched:
            final_vals = [round(v, 4) for v in monthly_accum]
        else:
            final_vals = [None] * 12
        driver_data[disp_name] = final_vals
        driver_data[(grp, disp_name)] = final_vals
        driver_data[f"{grp}_{disp_name}"] = final_vals
    return driver_data


# ─── 5. AGGREGATIONS & MATRIX ENGINE ────────────────────────────────────────

def calc_totals(monthly_vals: List[Optional[float]], cutoff_month: int = 0) -> Dict[str, Optional[float]]:
    """
    Calculates Q1..Q4, FY, YTD, and YTG totals.
    If all 12 months are None (blank driver), returns None for all totals so that the row stays completely blank.
    """
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


def compute_shipment_summary_matrix(models: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Computes complete Shipment Summary matrix:
    1. Loads Price Index from PostgreSQL table public.model_price_index
    2. Computes Factory POS $ = POS Plan $ * Price Index
    3. Populates GTS actuals from Snowflake VW_FACT_F360_SHIPMENTS
    4. Projects future months as Factory POS + Sum(Shipment Building Blocks)
    5. Calculates GTS YoY % against base_year GTS
    """
    base_year, plan_year = get_active_years()

    # 1. Hierarchy rules from PostgreSQL shipment_hierarchy_mapping
    rules = load_shipment_model_rules(models)

    # 2. Snowflake GTS $ actuals for base_year and plan_year
    gts_base, gts_plan_actual = fetch_snowflake_monthly_gts(rules, base_year, plan_year)

    # 3. Live shipment building blocks from PostgreSQL (Exact pivoted query)
    drivers = load_live_shipment_building_blocks(models, plan_year)

    # 4. Compute Factory POS $ = POS Plan $ * Price Index (from public.model_price_index)
    price_indices = load_price_index_from_postgres(models, plan_year)

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
        print(f"[Factory POS Engine Notice]: {e}")

    factory_pos = [0.0] * 12
    for i in range(12):
        month_num = i + 1
        pos_val = pos_plan[i]
        idx_mult = price_indices.get(month_num, 1.0)
        factory_pos[i] = round(pos_val * idx_mult, 2)

    # 5. Sum all shipment building blocks for each month
    total_shipment_bb = [0.0] * 12
    for grp, disp_name, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        d_vals = drivers.get((grp, disp_name)) or drivers.get(disp_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                total_shipment_bb[i] += d_vals[i]

    # 6. Dynamically detect cutoff month from Snowflake plan_year GTS actuals
    # A month with actual GTS (positive, zero, or negative) is recognized using `is not None`
    detected_gts_cutoff = 0
    for idx, v in enumerate(gts_plan_actual):
        if v is not None:
            detected_gts_cutoff = idx + 1

    # Safe dynamic fallback:
    # If GTS actuals exist in Snowflake, use detected_gts_cutoff.
    # Otherwise, inherit Consumption Summary's cutoff if available; else safely default to 0 (all forecast).
    if detected_gts_cutoff > 0:
        cutoff_month = detected_gts_cutoff
    elif cons_cutoff > 0:
        cutoff_month = cons_cutoff
    else:
        cutoff_month = 0

    # 7. Plan Year GTS Row Population:
    # Actuals for months <= cutoff_month (0-indexed i < cutoff_month) where gts_plan_actual is not None;
    # Preserves valid zero and negative actuals. Forecast (Factory POS + Building Blocks) for future/incomplete months.
    gts_plan = [0.0] * 12
    for i in range(12):
        if i < cutoff_month and gts_plan_actual[i] is not None:
            gts_plan[i] = round(gts_plan_actual[i], 2)
        else:
            fp = factory_pos[i] or 0.0
            bb = total_shipment_bb[i] or 0.0
            gts_plan[i] = round(fp + bb, 2)

    # 8. GTS YoY % Calculation
    gts_yoy_pct = [0.0] * 12
    for i in range(12):
        b_val = gts_base[i]
        p_val = gts_plan[i]
        if b_val and b_val > 0 and p_val is not None:
            gts_yoy_pct[i] = ((p_val - b_val) / b_val) * 100.0
        else:
            gts_yoy_pct[i] = 0.0

    # 9. Totals across quarters, FY, YTD, YTG
    totals_factory_pos = calc_totals(factory_pos, cutoff_month)
    totals_gts = calc_totals(gts_plan, cutoff_month)
    totals_base = calc_totals(gts_base, cutoff_month)

    totals_yoy = {}
    for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        b_tot = totals_base.get(col, 0.0)
        p_tot = totals_gts.get(col, 0.0)
        if b_tot and b_tot > 0 and p_tot is not None:
            totals_yoy[col] = ((p_tot - b_tot) / b_tot) * 100.0
        else:
            totals_yoy[col] = 0.0

    driver_totals = {}
    for grp, disp_name, _ in SHIPMENT_DRIVER_ROW_DEFINITIONS:
        vals = drivers.get((grp, disp_name)) or drivers.get(disp_name, [None] * 12)
        tot = calc_totals(vals, cutoff_month)
        driver_totals[disp_name] = tot
        driver_totals[(grp, disp_name)] = tot
        driver_totals[f"{grp}_{disp_name}"] = tot

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "cutoff_month": cutoff_month,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "label_factory_pos": f"{plan_year} FACTORY POS",
        "label_gts": f"{plan_year} GTS",
        "models": models,
        "factory_pos": factory_pos,
        "totals_factory_pos": totals_factory_pos,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "gts_plan": gts_plan,
        "totals_gts": totals_gts,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_yoy_pct": gts_yoy_pct,
        "totals_yoy": totals_yoy,
    }
