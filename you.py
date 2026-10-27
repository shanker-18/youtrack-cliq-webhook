"""
gtscoc.py
=========
Authoritative Calculation Engine and UI Presentation for GTS CoC (Change of Cycle) Dashboard.
Matches the official visual layout and formulas:
1. Header Row: Medium Grey (#808080) background with bold white text.
2. Top Row: {base_year} (e.g. 2025) - Medium Grey (#808080) background with white text and dashes (-).
3. 13 Driver Rows across 6 Categories:
     - External: Base Trend, Season, Competition
     - Distribution: Distribution
     - Innovation: Net Innovation, Innovation (sub), Cannibalization (sub), Discontinuations, Renovation
     - Investment: Media, Trade
     - Price: Net Price, Price (sub), Elasticity (sub)
     - Other: Club, Other (Not Defined), Inventory
4. Exact CoC Formula for each Building Block:
     CoC Value[m] = (Current Cycle POS[m] - Previous Cycle POS[m]) * Price Factor[m]
     - Net Innovation = Innovation CoC + Cannibalization CoC
     - Net Price = Price CoC + Elasticity CoC
5. Bottom Row: {plan_year} (e.g. 2026) - Medium Grey (#808080) background with bold white text.
     Sum of all active Building Blocks for each month:
     Base Trend + Season + Competition + Distribution + Net Innovation +
     Discontinuations + Renovation + Media + Trade + Net Price + Club + Other + Inventory.
6. Number Formatting & Presentation:
     - Positives: 0.1, 3.5, 10.9
     - Negatives: (0.1), (3.2), (0.6), (6.9) (parentheses notation, no negative zero)
     - Zeroes / Nulls: - (dash)
7. Dynamic Conditional Formatting Heatmap:
     - Red/Coral gradient for negatives (#F8696B / #FCAEA8 / #F9DCE1)
     - Green/Mint gradient for positives (#63BE7B / #98D2A5 / #C3E5CE)
     - White for dashes / zero
"""

import os
import re
import math
import datetime
import warnings
import sys
import types
from typing import Optional, Dict, List, Tuple, Any, Union, NamedTuple
from dotenv import load_dotenv
from dash import html

warnings.filterwarnings("ignore")
load_dotenv()

# ─── 0. DYNAMIC KENVUE 4-4-5 FISCAL CALENDAR (FROM kv_calender.py) ───────────
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

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

MONTH_NAME_MAP = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12
}


def get_active_years() -> Tuple[int, int]:
    """Dynamically determines base_year and plan_year using Kenvue 4-4-5 Fiscal Calendar."""
    env_year = os.getenv("IBP_PLAN_YEAR")
    if env_year and env_year.isdigit():
        plan_year = int(env_year)
    else:
        plan_year = KenvueCalendar.get_date_info(datetime.date.today()).kv_year
    base_year = plan_year - 1
    return base_year, plan_year


def normalize_text(val: Any) -> str:
    """Normalizes string values consistently."""
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


# ─── DRIVER ROW DEFINITIONS MATCHING THE OFFICIAL IMAGE ──────────────────────
GTS_COC_DRIVER_DEFINITIONS = [
    # (Category Group, Display Name, DB Match Key)
    ("External",     "Base Trend",          "BASE TREND"),
    ("External",     "Season",              "SEASON"),
    ("External",     "Competition",         "COMPETITION"),
    ("Distribution", "Distribution",        "DISTRIBUTION"),
    ("Innovation",   "Net Innovation",      "COMPOUND_NET_INNOVATION"),  # Innovation + Cannibalization
    ("Innovation",   "Innovation",          "INNOVATION"),
    ("Innovation",   "Cannibalization",     "CANNIBALIZATION"),
    ("Innovation",   "Discontinuations",    "DISCONTINUATIONS"),
    ("Innovation",   "Renovation",          "RENOVATION"),
    ("Investment",   "Media",               "MEDIA"),
    ("Investment",   "Trade",               "TRADE"),
    ("Price",        "Net Price",           "COMPOUND_NET_PRICE"),       # Price + Elasticity
    ("Price",        "Price",               "PRICE"),
    ("Price",        "Elasticity",          "ELASTICITY"),
    ("Other",        "Club",                "CLUB"),
    ("Other",        "Other (Not Defined)", "OTHER"),
    ("Other",        "Inventory",           "INVENTORY"),
]

SUB_DRIVERS = {"Innovation", "Cannibalization", "Price", "Elasticity"}


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


# ─── 2. POSTGRESQL MODEL PRICE FACTOR / PRICE INDEX MULTIPLIERS ─────────────

def load_price_factor_from_postgres(
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

    models_std = model_list
    models_upper = [m.upper() for m in model_list]
    models_clean = [m.replace("'", "") for m in models_upper]
    all_search_models = list(set(models_std + models_upper + models_clean))

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
            WHERE mm.model_name = ANY(%s) OR UPPER(TRIM(mm.model_name)) = ANY(%s);
            """,
            """
            SELECT mpi.*
            FROM public.model_price_index mpi
            WHERE (mpi.model_name = ANY(%s) OR UPPER(TRIM(mpi.model_name)) = ANY(%s));
            """
        ]

        rows = []
        col_names = []
        for q in queries:
            try:
                cur.execute(q, (all_search_models, all_search_models))
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
            raw_factor = (
                row_dict.get("price_factor") or row_dict.get("price_index") or
                row_dict.get("index") or row_dict.get("multiplier") or
                row_dict.get("index_value") or row_dict.get("factor")
            )
            if m_num and 1 <= m_num <= 12 and raw_factor is not None:
                try:
                    val = float(raw_factor)
                    if val > 0:
                        monthly_indices[m_num].append(val)
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"[Price Factor DB Notice]: {e}")

    final_factors = {}
    for m in range(1, 13):
        arr = monthly_indices[m]
        final_factors[m] = (sum(arr) / len(arr)) if arr else 1.0

    return final_factors


# ─── 3. SNOWFLAKE HISTORICAL GTS $ INGESTION ─────────────────────────────────

def fetch_snowflake_monthly_gts(
    rules: List[Dict[str, str]], base_year: int
) -> List[Optional[float]]:
    """
    Queries PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS in Snowflake.
    Returns 12 months of base_year GTS $ in Millions ($M).
    """
    gts_base = [None] * 12
    if not rules:
        return gts_base

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
        return gts_base

    where_clause = " OR\n        ".join(row_conditions)
    query = f"""
    SELECT
        MONTHNUMBER,
        SUM(GTS_AMT) AS GTS_AMT
    FROM PROD_CVD_DISC.NAIBP_ACCESS.VW_FACT_F360_SHIPMENTS
    WHERE
        ({where_clause})
        AND YEAR = {base_year}
    GROUP BY
        MONTHNUMBER
    ORDER BY
        MONTHNUMBER;
    """

    try:
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for mo_val, amt_val in rows:
            mo = int(mo_val or 0)
            if 1 <= mo <= 12:
                m_idx = mo - 1
                val_m = float(amt_val or 0.0) / 1_000_000.0  # Dollars to Millions ($M)
                gts_base[m_idx] = (gts_base[m_idx] or 0.0) + val_m
    except Exception as e:
        print(f"[Snowflake GTS Query Notice]: {e}")

    return gts_base


# ─── 4. SNAPSHOT DISCOVERY & CYCLE BUILDING BLOCKS FETCHING ───────────────────

class CycleSnapshotInfo(NamedTuple):
    curr_cs_id: Optional[int]
    prior_cs_id: Optional[int]
    curr_ss_id: Optional[int]
    prior_ss_id: Optional[int]
    active_cycle_month: Optional[int] = None


def get_cycle_snapshot_ids(plan_year: int) -> CycleSnapshotInfo:
    """
    Detects Current and Prior snapshot IDs for Consumption and Shipment scoped to plan_year.
    Also discovers active_cycle_month (1..12) from planning_cycles.
    Returns: CycleSnapshotInfo(curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id, active_cycle_month)
    """
    curr_cs_id = None
    prior_cs_id = None
    curr_ss_id = None
    prior_ss_id = None
    active_cycle_month = None

    try:
        conn = get_postgres_connection()
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Consumption Current Snapshot (scoped to plan_year)
        cur.execute("""
            SELECT cs.snapshot_id, pc.cycle_month 
            FROM public.consumption_snapshots cs
            JOIN public.planning_cycles pc ON cs.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%CURRENT%' OR pc.is_active = TRUE)
              AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
            ORDER BY pc.cycle_month DESC NULLS LAST, cs.snapshot_id DESC
            LIMIT 1;
        """, {"plan_year": plan_year})
        row = cur.fetchone()
        if row:
            curr_cs_id = row[0]
            if row[1]:
                m_num = parse_month_num(row[1])
                if m_num and 1 <= m_num <= 12:
                    active_cycle_month = m_num

        # 2. Consumption Prior Snapshot (scoped to plan_year)
        cur.execute("""
            SELECT cs.snapshot_id, pc.cycle_month 
            FROM public.consumption_snapshots cs
            JOIN public.planning_cycles pc ON cs.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PRIOR%'
               OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PREV%'
               OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%IBP-1%')
              AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
            ORDER BY pc.cycle_month DESC NULLS LAST, cs.snapshot_id DESC
            LIMIT 1;
        """, {"plan_year": plan_year})
        row = cur.fetchone()
        if row:
            prior_cs_id = row[0]
        elif curr_cs_id:
            # Fallback: immediate preceding snapshot within the same plan_year
            cur.execute("""
                SELECT cs.snapshot_id, pc.cycle_month 
                FROM public.consumption_snapshots cs
                JOIN public.planning_cycles pc ON cs.cycle_id = pc.cycle_id
                WHERE cs.snapshot_id < %(curr_cs_id)s
                  AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
                ORDER BY pc.cycle_month DESC NULLS LAST, cs.snapshot_id DESC
                LIMIT 1;
            """, {"curr_cs_id": curr_cs_id, "plan_year": plan_year})
            row = cur.fetchone()
            if row:
                prior_cs_id = row[0]

        # 3. Shipment Current Snapshot (scoped to plan_year)
        cur.execute("""
            SELECT ss.snapshot_id, pc.cycle_month 
            FROM public.shipment_snapshots ss
            JOIN public.planning_cycles pc ON ss.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%CURRENT%' OR pc.is_active = TRUE)
              AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
            ORDER BY pc.cycle_month DESC NULLS LAST, ss.snapshot_id DESC
            LIMIT 1;
        """, {"plan_year": plan_year})
        row = cur.fetchone()
        if row:
            curr_ss_id = row[0]
            if not active_cycle_month and row[1]:
                m_num = parse_month_num(row[1])
                if m_num and 1 <= m_num <= 12:
                    active_cycle_month = m_num

        # 4. Shipment Prior Snapshot (scoped to plan_year)
        cur.execute("""
            SELECT ss.snapshot_id, pc.cycle_month 
            FROM public.shipment_snapshots ss
            JOIN public.planning_cycles pc ON ss.cycle_id = pc.cycle_id
            WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PRIOR%'
               OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%PREV%'
               OR UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%IBP-1%')
              AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
            ORDER BY pc.cycle_month DESC NULLS LAST, ss.snapshot_id DESC
            LIMIT 1;
        """, {"plan_year": plan_year})
        row = cur.fetchone()
        if row:
            prior_ss_id = row[0]
        elif curr_ss_id:
            # Fallback: immediate preceding snapshot within the same plan_year
            cur.execute("""
                SELECT ss.snapshot_id, pc.cycle_month 
                FROM public.shipment_snapshots ss
                JOIN public.planning_cycles pc ON ss.cycle_id = pc.cycle_id
                WHERE ss.snapshot_id < %(curr_ss_id)s
                  AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
                ORDER BY pc.cycle_month DESC NULLS LAST, ss.snapshot_id DESC
                LIMIT 1;
            """, {"curr_ss_id": curr_ss_id, "plan_year": plan_year})
            row = cur.fetchone()
            if row:
                prior_ss_id = row[0]

        # 5. Fallback: query active cycle directly from planning_cycles if needed
        if not active_cycle_month:
            cur.execute("""
                SELECT pc.cycle_month 
                FROM public.planning_cycles pc
                WHERE (UPPER(COALESCE(pc.snapshot_type, '')) LIKE '%CURRENT%' OR pc.is_active = TRUE)
                  AND (pc.planning_year_start = %(plan_year)s OR EXTRACT(YEAR FROM pc.cycle_month) = %(plan_year)s)
                ORDER BY pc.cycle_month DESC NULLS LAST
                LIMIT 1;
            """, {"plan_year": plan_year})
            row = cur.fetchone()
            if row and row[0]:
                m_num = parse_month_num(row[0])
                if m_num and 1 <= m_num <= 12:
                    active_cycle_month = m_num

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Cycle Discovery Notice]: {e}")

    return CycleSnapshotInfo(curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id, active_cycle_month)


def _fetch_cycle_building_blocks(
    models: List[str], plan_year: int, is_prior: bool = False
) -> Dict[str, Dict[int, float]]:
    """
    Safely fetches raw monthly building block values (in Thousands) from PostgreSQL:
    - Uses named parameters to prevent any positional type mismatch.
    - Matches models case-insensitively.
    - Handles Current vs Prior snapshot logic transparently.
    """
    monthly_data: Dict[str, Dict[int, float]] = {}
    if not models:
        return monthly_data

    models_std = [str(m).strip() for m in models if m]
    models_upper = [m.upper().strip() for m in models_std]
    models_clean = [m.replace("'", "") for m in models_upper]

    snap_info = get_cycle_snapshot_ids(plan_year)
    curr_cs_id = snap_info[0] if len(snap_info) > 0 else None
    prior_cs_id = snap_info[1] if len(snap_info) > 1 else None
    curr_ss_id = snap_info[2] if len(snap_info) > 2 else None
    prior_ss_id = snap_info[3] if len(snap_info) > 3 else None

    # If asking for prior cycle but no prior snapshot exists in DB, return empty (0.0)
    if is_prior and prior_cs_id is None and prior_ss_id is None:
        return monthly_data

    # Build snapshot filter conditions
    if not is_prior:
        cpr_snap_filter = f"AND (cpr.snapshot_id = {curr_cs_id} OR cpr.snapshot_id IS NULL)" if curr_cs_id else ""
        spr_snap_filter = f"AND (spr.snapshot_id = {curr_ss_id} OR spr.snapshot_id IS NULL)" if curr_ss_id else ""
    else:
        cpr_snap_filter = f"AND cpr.snapshot_id = {prior_cs_id}" if prior_cs_id else "AND 1=0"
        spr_snap_filter = f"AND spr.snapshot_id = {prior_ss_id}" if prior_ss_id else "AND 1=0"

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
        (
            mm.model_name = ANY(%(models_std)s)
            OR UPPER(TRIM(mm.model_name)) = ANY(%(models_upper)s)
            OR REPLACE(UPPER(TRIM(mm.model_name)), '''', '') = ANY(%(models_clean)s)
        )
        AND cpr.is_deleted = FALSE
        AND cbb.is_active = TRUE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM cpv.period_month) = %(plan_year)s
        {cpr_snap_filter}
    GROUP BY cbb.name, month_num

    UNION ALL

    -- Shipment Building Blocks (e.g. Retailer Inventory / Inventory)
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
        (
            mm.model_name = ANY(%(models_std)s)
            OR UPPER(TRIM(mm.model_name)) = ANY(%(models_upper)s)
            OR REPLACE(UPPER(TRIM(mm.model_name)), '''', '') = ANY(%(models_clean)s)
        )
        AND spr.is_deleted = FALSE
        AND sbb.is_active = TRUE
        AND mm.is_active = TRUE
        AND EXTRACT(YEAR FROM spv.period_month) = %(plan_year)s
        {spr_snap_filter}
    GROUP BY sbb.name, month_num;
    """

    params = {
        "models_std": models_std,
        "models_upper": models_upper,
        "models_clean": models_clean,
        "plan_year": plan_year
    }

    rows = []
    try:
        conn = get_postgres_connection()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Cycle Query Notice ({'Prior' if is_prior else 'Current'})]: {e}")
        rows = []

    for bb_name, m_num, val_k in rows:
        norm_name = normalize_text(bb_name)
        if norm_name not in monthly_data:
            monthly_data[norm_name] = {}
        # Convert thousands ($K) to millions ($M)
        val_m = float(val_k or 0.0) / 1000.0
        monthly_data[norm_name][int(m_num)] = monthly_data[norm_name].get(int(m_num), 0.0) + val_m

    return monthly_data


# ─── 5. COMPUTE BUILDING BLOCKS CoC: (Current - Previous) * Price Factor ─────

def _matches_driver_name(db_bb_name: str, match_key: str) -> bool:
    """Robust pattern matching between PostgreSQL block name and logical driver."""
    norm = normalize_text(db_bb_name)
    if match_key == "INNOVATION":
        return "INNOVATION" in norm and "NET" not in norm and "CANNIBAL" not in norm
    if match_key == "CANNIBALIZATION":
        return "CANNIBAL" in norm
    if match_key == "PRICE":
        return "PRICE" in norm and "NET" not in norm and "ELAST" not in norm
    if match_key == "ELASTICITY":
        return "ELAST" in norm
    if match_key == "INVENTORY":
        return "INVENTORY" in norm or "RETAILER" in norm
    if match_key == "OTHER":
        return "OTHER" in norm and "OVERLAY" not in norm
    if match_key == "RENOVATION":
        return "RENOVAT" in norm
    if match_key == "DISCONTINUATIONS":
        return "DISCONTINU" in norm
    if match_key == "BASE TREND":
        return "BASE" in norm and "TREND" in norm
    if match_key == "SEASON":
        return "SEASON" in norm
    if match_key == "COMPETITION":
        return "COMPET" in norm
    if match_key == "DISTRIBUTION":
        return "DISTRIBUT" in norm
    if match_key == "MEDIA":
        return "MEDIA" in norm
    if match_key == "TRADE":
        return "TRADE" in norm
    if match_key == "CLUB":
        return "CLUB" in norm
    return match_key in norm


def load_coc_building_blocks(
    models: Union[str, List[str]], plan_year: int, price_factors: Dict[int, float]
) -> Dict[str, List[Optional[float]]]:
    """
    Computes CoC Building Blocks using the exact specified formula:
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

    def _get_driver_coc(match_key: str) -> List[Optional[float]]:
        # Find matching entries in current and prior data
        curr_dict: Dict[int, float] = {}
        for k, v in current_raw.items():
            if _matches_driver_name(k, match_key):
                for m, val in v.items():
                    curr_dict[m] = curr_dict.get(m, 0.0) + val

        prior_dict: Dict[int, float] = {}
        for k, v in prior_raw.items():
            if _matches_driver_name(k, match_key):
                for m, val in v.items():
                    prior_dict[m] = prior_dict.get(m, 0.0) + val

        res = [None] * 12
        has_any = False
        for m in range(1, 13):
            curr_val = curr_dict.get(m, 0.0)
            prior_val = prior_dict.get(m, 0.0)
            if m in curr_dict or m in prior_dict:
                # FORMULA: (Current Cycle - Previous Cycle) * Price Factor
                pf = price_factors.get(m, 1.0)
                coc_val = (curr_val - prior_val) * pf
                res[m - 1] = round(coc_val, 4)
                has_any = True

        return res if has_any else [None] * 12

    driver_data: Dict[str, List[Optional[float]]] = {}
    for _, disp_name, match_key in GTS_COC_DRIVER_DEFINITIONS:
        if match_key.startswith("COMPOUND_"):
            continue
        driver_data[disp_name] = _get_driver_coc(match_key)

    # Net Innovation = Innovation CoC + Cannibalization CoC
    net_inno = [None] * 12
    for i in range(12):
        iv = driver_data.get("Innovation", [None] * 12)[i]
        cv = driver_data.get("Cannibalization", [None] * 12)[i]
        if iv is not None or cv is not None:
            net_inno[i] = round((iv or 0.0) + (cv or 0.0), 4)
    driver_data["Net Innovation"] = net_inno

    # Net Price = Price CoC + Elasticity CoC
    net_price = [None] * 12
    for i in range(12):
        pv = driver_data.get("Price", [None] * 12)[i]
        ev = driver_data.get("Elasticity", [None] * 12)[i]
        if pv is not None or ev is not None:
            net_price[i] = round((pv or 0.0) + (ev or 0.0), 4)
    driver_data["Net Price"] = net_price

    return driver_data


# ─── 6. AGGREGATIONS & GTS CoC MATRIX ENGINE ─────────────────────────────────

def calc_totals(monthly_vals: List[Optional[float]], cutoff_month: int = 0) -> Dict[str, Optional[float]]:
    """Calculates Q1..Q4, FY, YTD, and YTG totals for GTS CoC."""
    has_data = any(v is not None for v in monthly_vals)
    if not has_data:
        return {col: None for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]}

    def _sum_range(st, en):
        if st >= en:
            return None
        arr = [v for v in monthly_vals[st:en] if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return round(sum(arr), 4) if arr else None

    safe_cutoff = max(0, min(12, int(cutoff_month or 0)))
    return {
        "Q1": _sum_range(0, 3),
        "Q2": _sum_range(3, 6),
        "Q3": _sum_range(6, 9),
        "Q4": _sum_range(9, 12),
        "FY": _sum_range(0, 12),
        "YTD": _sum_range(0, safe_cutoff),
        "YTG": _sum_range(safe_cutoff, 12),
    }


def compute_gtscoc_summary_matrix(models: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Computes complete GTS CoC Matrix:
    1. Top Row: {base_year} (dashes -)
    2. Driver Rows: (Current - Previous) * Price Factor
    3. Bottom Row: {plan_year} (Sum of all Building Blocks)
    """
    base_year, plan_year = get_active_years()
    rules = load_model_rules(models)

    # 1. Historical GTS from Snowflake (for base row reference)
    gts_base = fetch_snowflake_monthly_gts(rules, base_year)

    # 2. Discover cycles and active cycle month for dynamic cutoff
    snap_info = get_cycle_snapshot_ids(plan_year)
    active_cycle_month = snap_info[4] if len(snap_info) > 4 else getattr(snap_info, "active_cycle_month", None)

    env_cutoff = os.getenv("IBP_CUTOFF_MONTH")
    if env_cutoff and env_cutoff.isdigit():
        cutoff_month = int(env_cutoff)
    elif active_cycle_month and 1 <= active_cycle_month <= 12:
        cutoff_month = active_cycle_month
    else:
        cutoff_month = 0

    # 3. Price Factors from PostgreSQL
    price_factors = load_price_factor_from_postgres(models, plan_year)

    # 4. Building Blocks CoC: (Current - Previous) * Price Factor
    drivers = load_coc_building_blocks(models, plan_year, price_factors)

    # Official parent drivers that sum into the bottom {plan_year} row:
    parent_driver_names = [
        "Base Trend", "Season", "Competition", "Distribution", "Net Innovation",
        "Discontinuations", "Renovation", "Media", "Trade", "Net Price",
        "Club", "Other (Not Defined)", "Inventory"
    ]

    total_monthly_coc = [0.0] * 12
    has_coc_for_month = [False] * 12
    for d_name in parent_driver_names:
        d_vals = drivers.get(d_name, [None] * 12)
        for i in range(12):
            if d_vals[i] is not None:
                total_monthly_coc[i] += d_vals[i]
                has_coc_for_month[i] = True

    # Bottom Row: {plan_year}
    gts_plan = [None] * 12
    for i in range(12):
        if has_coc_for_month[i]:
            gts_plan[i] = round(total_monthly_coc[i], 4)
        else:
            gts_plan[i] = None

    totals_base = calc_totals(gts_base, cutoff_month)
    totals_plan = calc_totals(gts_plan, cutoff_month)

    driver_totals = {}
    for _, disp_name, _ in GTS_COC_DRIVER_DEFINITIONS:
        m_vals = drivers.get(disp_name, [None] * 12)
        driver_totals[disp_name] = calc_totals(m_vals, cutoff_month)

    return {
        "base_year": base_year,
        "plan_year": plan_year,
        "label_base": str(base_year),
        "label_plan": str(plan_year),
        "cutoff_month": cutoff_month,
        "models": models,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_plan": gts_plan,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
    }


# ─── 7. DYNAMIC HEATMAP & NUMBER FORMATTING HELPERS ──────────────────────────

def get_driver_heatmap_style(val: Optional[float], max_pos: float, max_neg_mag: float):
    """
    Excel-style 3-color conditional formatting matching the uploaded image:
    - Negatives: Soft Pink (#F9DCE1) -> Salmon (#FCAEA8) -> High Red (#F8696B / #FF6B6B)
    - Positives: Soft Mint (#EAF7EE) -> Light Green (#C3E5CE) -> Rich Green (#63BE7B)
    - Zero / None / Dash: White (#ffffff)
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "#ffffff", "#111827", "500"
    v = float(val)
    if abs(v) < 0.0001:
        return "#ffffff", "#111827", "500"

    if v > 0:
        ratio = (v / max_pos) if max_pos > 0 else 0
        if ratio >= 0.70:
            return "#63BE7B", "#ffffff", "700"  # Tier 4: Rich Green
        elif ratio >= 0.40:
            return "#98D2A5", "#111827", "600"  # Tier 3: Medium Green
        elif ratio >= 0.15:
            return "#C3E5CE", "#111827", "500"  # Tier 2: Light Green
        else:
            return "#EAF7EE", "#111827", "500"  # Tier 1: Soft Mint
    else:
        ratio = (abs(v) / max_neg_mag) if max_neg_mag > 0 else 0
        if ratio >= 0.70:
            return "#F8696B", "#ffffff", "700"  # Tier 4: High Red (#F8696B)
        elif ratio >= 0.40:
            return "#FCAEA8", "#111827", "600"  # Tier 3: Salmon Pink
        elif ratio >= 0.15:
            return "#F9DCE1", "#111827", "500"  # Tier 2: Soft Pink
        else:
            return "#FFF1F2", "#111827", "500"  # Tier 1: Pale Blush


def fmt_coc_number(val: Optional[float], decimals: int = 1) -> str:
    """
    Formats numbers matching the image:
    - Null / 0.0 -> '' (empty string)
    - Positive -> '0.1', '3.5', '11.5'
    - Negative -> '(0.1)', '(3.2)', '(6.9)'
    - Small negative rounding to 0.0 -> '(0.0)'
    - Small positive rounding to 0.0 -> '0.0'
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return ""
    v = float(val)
    if abs(v) < 0.000001:
        return ""

    rounded_val = round(abs(v), decimals)
    if v < 0:
        return f"({rounded_val:.{decimals}f})"
    else:
        return f"{rounded_val:.{decimals}f}"


def build_data_cells(m_vals, totals, max_pos, max_neg_mag, is_driver=False, bg_override=None, text_override=None, decimals=1):
    """Builds monthly, quarterly, and full-year table cells with exact image styling."""
    cells = []
    # 12 Months
    for val in m_vals:
        txt = fmt_coc_number(val, decimals=decimals)
        if bg_override:
            bg_col = bg_override
            txt_col = text_override or "#ffffff"
            font_wt = "700"
        elif is_driver and txt != "":
            bg_col, txt_col, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        else:
            bg_col = "#ffffff"
            txt_col = "#111827"
            font_wt = "500"

        cells.append(html.Td(txt, style={
            "padding": "4px 6px", "textAlign": "right", "fontSize": "11px",
            "backgroundColor": bg_col, "color": txt_col, "fontWeight": font_wt,
            "border": "1px solid #d1d5db", "minWidth": "38px"
        }))

    # Summary Columns: Q1, Q2, Q3, Q4, FY, YTD, YTG
    for col_name in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        val = totals.get(col_name)
        col_decimals = 2 if col_name == "FY" and is_driver is False and val is not None and abs(val) > 10 else decimals
        txt = fmt_coc_number(val, decimals=col_decimals)

        if bg_override:
            bg_col = bg_override
            txt_col = text_override or "#ffffff"
            font_wt = "700"
        elif is_driver and txt != "":
            bg_col, txt_col, font_wt = get_driver_heatmap_style(val, max_pos, max_neg_mag)
        else:
            bg_col = "#fbfbfb"
            txt_col = "#111827"
            font_wt = "700"

        b_left = "4px solid #ffffff" if col_name in ["Q1", "YTD"] else "1px solid #d1d5db"

        cells.append(html.Td(txt, style={
            "padding": "4px 6px", "textAlign": "right", "fontSize": "11px",
            "backgroundColor": bg_col, "color": txt_col, "fontWeight": font_wt,
            "border": "1px solid #d1d5db", "borderLeft": b_left, "minWidth": "42px"
        }))

    return cells


# ─── 8. GTS CoC TABLE RENDERER MATCHING THE IMAGE ────────────────────────────

def render_gtscoc_table(data: dict) -> html.Div:
    """
    Renders GTS CoC Summary Matrix with pixel-perfect match to the user's image:
    - Grey Header row (#808080)
    - Top Row: {base_year} (Grey #808080 with dashes -)
    - 13 Building Block Rows across 6 Categories
    - Bottom Row: {plan_year} (Grey #808080 with sum of all Building Blocks)
    """
    max_pos, max_neg_mag = 0.001, 0.001
    for d_name, m_vals in data["drivers"].items():
        for v in m_vals:
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                if v > max_pos:
                    max_pos = v
                elif v < 0 and abs(v) > max_neg_mag:
                    max_neg_mag = abs(v)

    # Header cell style
    th_style = {
        "backgroundColor": "#808080", "color": "#ffffff", "fontWeight": "800",
        "fontSize": "11px", "padding": "6px 8px", "border": "1px solid #6b7280",
        "textAlign": "center", "whiteSpace": "nowrap"
    }

    header_cells = [
        html.Th("", style={**th_style, "minWidth": "90px", "borderRight": "none"}),
        html.Th("", style={**th_style, "minWidth": "140px", "borderLeft": "none"}),
    ]

    for m in MONTHS:
        header_cells.append(html.Th(m, style=th_style))

    divider_style = {**th_style, "borderLeft": "4px solid #ffffff"}
    header_cells.append(html.Th("Q1", style=divider_style))
    header_cells.append(html.Th("Q2", style=th_style))
    header_cells.append(html.Th("Q3", style=th_style))
    header_cells.append(html.Th("Q4", style=th_style))
    header_cells.append(html.Th("FY", style={**th_style, "fontWeight": "900"}))
    header_cells.append(html.Th("YTD", style=divider_style))
    header_cells.append(html.Th("YTG", style=th_style))

    thead = html.Thead(html.Tr(header_cells))
    tbody_rows = []

    # 1. Top Row: base_year (Medium Grey #808080 background, dashes -)
    base_label = data.get("label_base") or (str(data.get("base_year")) if data.get("base_year") else "")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#808080", "border": "1px solid #6b7280"}),
        html.Td(base_label, style={
            "fontWeight": "800", "fontSize": "12px", "padding": "4px 8px",
            "backgroundColor": "#808080", "color": "#ffffff", "border": "1px solid #6b7280",
            "textAlign": "right"
        }),
        *build_data_cells(
            [None] * 12, {col: None for col in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]},
            max_pos, max_neg_mag, bg_override="#808080", text_override="#ffffff", decimals=1
        )
    ]))

    # 2. Driver Rows: 13 Building Blocks across 6 Categories
    group_counts = {}
    for grp, _, _ in GTS_COC_DRIVER_DEFINITIONS:
        group_counts[grp] = group_counts.get(grp, 0) + 1

    seen_groups = set()

    for grp, driver_name, _ in GTS_COC_DRIVER_DEFINITIONS:
        cells = []
        if grp not in seen_groups:
            seen_groups.add(grp)
            cells.append(html.Td(
                grp, rowSpan=group_counts[grp],
                style={
                    "textAlign": "center", "verticalAlign": "middle",
                    "backgroundColor": "#bfe6df", "color": "#064e3b",
                    "fontWeight": "800", "fontSize": "12px", "border": "1px solid #a7d9d0",
                    "padding": "6px 4px"
                }
            ))

        is_sub = driver_name in SUB_DRIVERS
        cells.append(html.Td(
            driver_name,
            style={
                "fontWeight": "600" if driver_name in ["Net Innovation", "Net Price"] else "400",
                "fontSize": "11px",
                "color": "#111827",
                "padding": "4px 8px",
                "paddingLeft": "18px" if is_sub else "8px",
                "fontStyle": "italic" if is_sub else "normal",
                "textAlign": "left",
                "border": "1px solid #d1d5db",
                "backgroundColor": "#ffffff"
            }
        ))

        d_vals = data["drivers"].get(driver_name, [None] * 12)
        d_totals = data["driver_totals"].get(driver_name, {})
        cells.extend(build_data_cells(d_vals, d_totals, max_pos, max_neg_mag, is_driver=True, decimals=1))
        tbody_rows.append(html.Tr(cells))

    # 3. Bottom Row: plan_year (Medium Grey #808080 background, sum of all Building Blocks)
    plan_label = data.get("label_plan") or (str(data.get("plan_year")) if data.get("plan_year") else "")
    tbody_rows.append(html.Tr([
        html.Td("", style={"backgroundColor": "#808080", "border": "1px solid #6b7280"}),
        html.Td(plan_label, style={
            "fontWeight": "800", "fontSize": "12px", "padding": "4px 8px",
            "backgroundColor": "#808080", "color": "#ffffff", "border": "1px solid #6b7280",
            "textAlign": "right"
        }),
        *build_data_cells(
            data["gts_plan"], data["totals_plan"], max_pos, max_neg_mag,
            bg_override="#808080", text_override="#ffffff", decimals=1
        )
    ]))

    return html.Div([
        html.Table([thead, html.Tbody(tbody_rows)], style={
            "width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff",
            "borderRadius": "4px", "boxShadow": "0 1px 4px rgba(0,0,0,0.06)"
        })
    ], style={"overflowX": "auto", "border": "1px solid #9ca3af", "borderRadius": "4px"})
