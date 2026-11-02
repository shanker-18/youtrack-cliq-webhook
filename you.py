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


def get_kenvue_retail_date_info(d: Optional[datetime.date] = None):
    """
    Derives Kenvue 4-4-5 Retail Calendar attributes for date d (default: today).
    In Kenvue Retail / Circana POS calendar, weeks run Sunday -> Saturday.
    Aligns Sundays to the retail week (evaluating as d + 1 day).
    """
    target_d = d or datetime.date.today()
    eval_date = target_d + datetime.timedelta(days=1) if target_d.weekday() == 6 else target_d
    return KenvueCalendar.get_date_info(eval_date)


def get_current_kenvue_month(d: Optional[datetime.date] = None) -> int:
    """Returns the current Kenvue 4-4-5 Retail Fiscal Month (1..12)."""
    return get_kenvue_retail_date_info(d).kv_month_num


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
    s = re.sub(r"\s+", " ", s)
    return s


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
        password=os.getenv("IBP_DB_PASSWORD", "postgres")
    )


def get_snowflake_connection():
    """Connects to Snowflake for historical GTS."""
    import snowflake.connector
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT", ""),
        user=os.getenv("SNOWFLAKE_USER", ""),
        password=os.getenv("SNOWFLAKE_PASSWORD", ""),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "NA_IBP_DB"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
        role=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
    )


# ─── 1. GTS CoC DRIVER DEFINITIONS & DISPLAY ORDER ───────────────────────────
# Format: (Category, Driver Display Name, [Aliases for DB Matching])
GTS_COC_DRIVER_DEFINITIONS = [
    ("External", "Base Trend", ["BASE TREND", "BASE_TREND", "BASETREND", "BASE"]),
    ("External", "Season", ["SEASON", "SEASONALITY", "SEASONAL"]),
    ("External", "Competition", ["COMPETITION", "COMP"]),
    ("Distribution", "Distribution", ["DISTRIBUTION", "DIST", "TDP"]),
    ("Innovation", "Net Innovation", ["NET INNOVATION", "NET_INNOVATION"]),
    ("Innovation", "Innovation", ["INNOVATION", "INNO", "NEW PRODUCT"]),
    ("Innovation", "Cannibalization", ["CANNIBALIZATION", "CANNIBAL"]),
    ("Innovation", "Discontinuations", ["DISCONTINUATIONS", "DISCONTINUATION", "DISCO", "DISCONTINUED"]),
    ("Innovation", "Renovation", ["RENOVATION", "RENO", "RENOVATIONS"]),
    ("Investment", "Media", ["MEDIA", "ADVERTISING", "A&P"]),
    ("Investment", "Trade", ["TRADE", "PROMO", "PROMOTIONS"]),
    ("Price", "Net Price", ["NET PRICE", "NET_PRICE"]),
    ("Price", "Price", ["PRICE", "PRICE INCREASE", "PRICING"]),
    ("Price", "Elasticity", ["ELASTICITY", "PRICE ELASTICITY"]),
    ("Other", "Club", ["CLUB", "CLUB EXPANSION"]),
    ("Other", "Other (Not Defined)", ["OTHER", "OTHER (NOT DEFINED)", "NOT DEFINED", "UNALLOCATED"]),
    ("Other", "Inventory", ["INVENTORY", "INV", "STOCK"]),
]

SUB_DRIVERS = {"Innovation", "Cannibalization", "Price", "Elasticity"}


# ─── 2. HIERARCHY RULES & EXCEL INTEGRATION ──────────────────────────────────

def load_model_rules(models: Union[str, List[str]]) -> List[Dict[str, str]]:
    """Loads filtering rules for model(s) from Excel."""
    if isinstance(models, str):
        models = [models]
    model_set = {normalize_text(m) for m in models}

    excel_paths = [
        os.path.join(os.getcwd(), "Model Mapping File - Circana POS.xlsx"),
        os.path.join(os.getcwd(), "Model Mapping.xlsx"),
        os.path.join(os.getcwd(), "Book1.xlsx")
    ]
    path = next((p for p in excel_paths if os.path.exists(p)), None)
    if not path:
        return [{"B1_BRAND": m} for m in models]

    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    sheet = wb.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return [{"B1_BRAND": m} for m in models]

    headers = [normalize_text(h) for h in rows[0]]
    matched_rules = []

    for r in rows[1:]:
        r_dict = {headers[i]: r[i] for i in range(min(len(headers), len(r)))}
        model_name = normalize_text(r_dict.get("MODEL") or r_dict.get("MODEL NAME"))
        if model_name in model_set:
            rule = {}
            for col in ["B1_BRAND", "B2_NEED_STATE", "B3_SEGMENT", "B4_SUB_SEGMENT", "B5_FORM"]:
                val = r_dict.get(col)
                if val:
                    rule[col] = str(val).strip()
            if rule:
                matched_rules.append(rule)

    return matched_rules or [{"B1_BRAND": m} for m in models]


def load_price_factor_from_postgres(models: Union[str, List[str]], plan_year: int) -> Dict[int, float]:
    """
    Loads monthly Price Factors from public.consumption_price_factor (or price_index).
    Returns dict mapping month (1..12) -> float (default 1.0).
    """
    if isinstance(models, str):
        models = [models]
    model_set = {normalize_text(m) for m in models}
    monthly_indices: Dict[int, List[float]] = {m: [] for m in range(1, 13)}

    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND (table_name LIKE '%price%factor%' OR table_name LIKE '%price%index%');
        """)
        found_tables = [r[0] for r in cur.fetchall()]

        table_candidates = ["consumption_price_factor", "price_index", "price_factors"] + found_tables
        target_table = None
        for t in table_candidates:
            if t in found_tables:
                target_table = t
                break

        if not target_table:
            cur.close()
            conn.close()
            return {m: 1.0 for m in range(1, 13)}

        cur.execute(f"SELECT * FROM public.{target_table} LIMIT 1;")
        col_names = [desc[0].lower() for desc in cur.description]

        query = f"SELECT * FROM public.{target_table}"
        where_clauses = []
        params = []

        if "planning_year" in col_names:
            where_clauses.append("planning_year = %s")
            params.append(plan_year)
        elif "year" in col_names:
            where_clauses.append("year = %s")
            params.append(plan_year)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for row in rows:
            row_dict = {col_names[i]: row[i] for i in range(len(col_names))}
            row_model = normalize_text(
                row_dict.get("model") or row_dict.get("model_name") or
                row_dict.get("brand") or row_dict.get("need_state")
            )
            if model_set and row_model and row_model not in model_set:
                continue

            raw_month = (
                row_dict.get("month") or row_dict.get("month_num") or
                row_dict.get("cycle_month") or row_dict.get("planning_month") or
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
        print(f"[PostgreSQL Price Factor Notice]: {e}")

    result = {}
    for m in range(1, 13):
        if monthly_indices[m]:
            result[m] = sum(monthly_indices[m]) / len(monthly_indices[m])
        else:
            result[m] = 1.0

    return result


# ─── 3. HISTORICAL GTS SHIPMENTS FROM SNOWFLAKE ──────────────────────────────

def fetch_snowflake_monthly_gts(rules: List[Dict[str, str]], base_year: int) -> List[Optional[float]]:
    """
    Fetches actual GTS Shipments ($M) for base_year from Snowflake.
    Table: NA_IBP_DB.PUBLIC.ANALYTICS_ACTUALS_LINE_ITEM
    Column: GROSS_TRADE_SALES_AMT
    """
    gts_base: List[Optional[float]] = [None] * 12
    if not rules:
        return gts_base

    clauses = []
    for r in rules:
        conds = []
        for k, v in r.items():
            conds.append(f"{k} = '{v.replace(\"'\", \"''\")}'")
        if conds:
            clauses.append("(" + " AND ".join(conds) + ")")

    if not clauses:
        return gts_base

    rule_filter = " OR ".join(clauses)
    query = f"""
        SELECT 
            KV_MTH_NBR,
            SUM(GROSS_TRADE_SALES_AMT) AS GTS_AMT
        FROM NA_IBP_DB.PUBLIC.ANALYTICS_ACTUALS_LINE_ITEM
        WHERE KV_YEAR = {base_year}
          AND ({rule_filter})
        GROUP BY KV_MTH_NBR
        ORDER BY KV_MTH_NBR;
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
              AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
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
              AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
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
                  AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
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
              AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
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
              AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
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
                  AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
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
                  AND (pc.planning_year_start = %(plan_year)s OR pc.planning_year_start IS NULL)
                ORDER BY pc.cycle_month DESC NULLS LAST
                LIMIT 1;
            """, {"plan_year": plan_year})
            row = cur.fetchone()
            if row and row[0]:
                m_num = parse_month_num(row[0])
                if m_num and 1 <= m_num <= 12:
                    active_cycle_month = m_num

        if not active_cycle_month:
            active_cycle_month = get_current_kenvue_month()

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Cycle Discovery Notice]: {e}")
        if not active_cycle_month:
            active_cycle_month = get_current_kenvue_month()

    return CycleSnapshotInfo(curr_cs_id, prior_cs_id, curr_ss_id, prior_ss_id, active_cycle_month)


def _fetch_cycle_building_blocks(
    models: List[str], plan_year: int, is_prior: bool = False
) -> Dict[str, Dict[int, float]]:
    """
    Safely fetches raw monthly building block values (in Thousands) from PostgreSQL:
    - If is_prior=False: looks up CURRENT cycle snapshots
    - If is_prior=True:  looks up PRIOR cycle snapshots
    Returns: dict mapping driver_name -> {month_num (1..12): float_val}
    """
    snap_info = get_cycle_snapshot_ids(plan_year)
    target_cs_id = snap_info.prior_cs_id if is_prior else snap_info.curr_cs_id
    target_ss_id = snap_info.prior_ss_id if is_prior else snap_info.curr_ss_id

    result: Dict[str, Dict[int, float]] = {}

    def _match_driver(raw_name: str) -> Optional[str]:
        n = normalize_text(raw_name)
        for _, disp_name, aliases in GTS_COC_DRIVER_DEFINITIONS:
            if n == normalize_text(disp_name) or any(n == normalize_text(a) for a in aliases):
                return disp_name
        return None

    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        # 1. Fetch from consumption_line_items
        if target_cs_id:
            query = """
                SELECT 
                    bb.building_block_name,
                    cli.period_month,
                    SUM(cli.value) AS total_val
                FROM public.consumption_line_items cli
                JOIN public.building_blocks bb ON cli.building_block_id = bb.building_block_id
                JOIN public.consumption_hierarchy_mapping chm ON cli.hierarchy_id = chm.hierarchy_id
                WHERE cli.snapshot_id = %s
                  AND (cli.planning_year = %s OR cli.planning_year IS NULL)
            """
            params = [target_cs_id, plan_year]
            if models:
                query += " AND UPPER(chm.need_state) = ANY(%s)"
                params.append([m.upper() for m in models])
            query += " GROUP BY bb.building_block_name, cli.period_month;"

            cur.execute(query, tuple(params))
            for bb_name, p_month, val in cur.fetchall():
                d_name = _match_driver(bb_name)
                m_num = parse_month_num(p_month)
                if d_name and m_num and 1 <= m_num <= 12 and val is not None:
                    result.setdefault(d_name, {})
                    result[d_name][m_num] = result[d_name].get(m_num, 0.0) + float(val)

        # 2. Fetch from shipment_line_items
        if target_ss_id:
            query = """
                SELECT 
                    bb.building_block_name,
                    sli.period_month,
                    SUM(sli.value) AS total_val
                FROM public.shipment_line_items sli
                JOIN public.building_blocks bb ON sli.building_block_id = bb.building_block_id
                JOIN public.shipment_hierarchy_mapping shm ON sli.hierarchy_id = shm.hierarchy_id
                WHERE sli.snapshot_id = %s
                  AND (sli.planning_year = %s OR sli.planning_year IS NULL)
            """
            params = [target_ss_id, plan_year]
            if models:
                query += " AND UPPER(shm.need_state) = ANY(%s)"
                params.append([m.upper() for m in models])
            query += " GROUP BY bb.building_block_name, sli.period_month;"

            cur.execute(query, tuple(params))
            for bb_name, p_month, val in cur.fetchall():
                d_name = _match_driver(bb_name)
                m_num = parse_month_num(p_month)
                if d_name and m_num and 1 <= m_num <= 12 and val is not None:
                    result.setdefault(d_name, {})
                    result[d_name][m_num] = result[d_name].get(m_num, 0.0) + float(val)

        # Fallback if no snapshots found in DB
        if not target_cs_id and not target_ss_id:
            query = """
                SELECT 
                    bb.building_block_name,
                    COALESCE(cli.period_month, 1),
                    SUM(cli.value) AS total_val
                FROM public.consumption_line_items cli
                JOIN public.building_blocks bb ON cli.building_block_id = bb.building_block_id
                JOIN public.consumption_hierarchy_mapping chm ON cli.hierarchy_id = chm.hierarchy_id
                WHERE (cli.planning_year = %s OR cli.planning_year IS NULL)
            """
            params = [plan_year]
            if models:
                query += " AND UPPER(chm.need_state) = ANY(%s)"
                params.append([m.upper() for m in models])
            query += " GROUP BY bb.building_block_name, cli.period_month;"
            cur.execute(query, tuple(params))
            for bb_name, p_month, val in cur.fetchall():
                d_name = _match_driver(bb_name)
                m_num = parse_month_num(p_month)
                if d_name and m_num and 1 <= m_num <= 12 and val is not None:
                    result.setdefault(d_name, {})
                    result[d_name][m_num] = result[d_name].get(m_num, 0.0) + float(val)

        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Cycle Building Blocks Fetch Notice]: {e}")

    return result


def load_coc_building_blocks(
    models: Union[str, List[str]], plan_year: int, price_factors: Dict[int, float]
) -> Dict[str, List[Optional[float]]]:
    """
    Computes Change of Cycle (CoC) Building Blocks in Millions ($M):
        CoC[m] = (Current Cycle Value[m] - Previous Cycle Value[m]) * Price Factor[m]
    Compound drivers:
        Net Innovation = Innovation + Cannibalization
        Net Price = Price + Elasticity
    """
    if isinstance(models, str):
        models = [models]

    curr_bb = _fetch_cycle_building_blocks(models, plan_year, is_prior=False)
    prior_bb = _fetch_cycle_building_blocks(models, plan_year, is_prior=True)

    coc_drivers: Dict[str, List[Optional[float]]] = {}

    for _, disp_name, _ in GTS_COC_DRIVER_DEFINITIONS:
        monthly_coc = [None] * 12
        for m in range(1, 13):
            m_idx = m - 1
            has_curr = disp_name in curr_bb and m in curr_bb[disp_name]
            has_prior = disp_name in prior_bb and m in prior_bb[disp_name]

            if has_curr or has_prior:
                c_val = curr_bb.get(disp_name, {}).get(m, 0.0)
                p_val = prior_bb.get(disp_name, {}).get(m, 0.0)
                diff = c_val - p_val
                pf = price_factors.get(m, 1.0)
                coc_val_m = (diff * pf) / 1000.0  # Convert thousands to Millions
                monthly_coc[m_idx] = round(coc_val_m, 4)
            else:
                monthly_coc[m_idx] = None

        coc_drivers[disp_name] = monthly_coc

    # Compound Driver: Net Innovation = Innovation + Cannibalization
    inno_vals = coc_drivers.get("Innovation", [None] * 12)
    cann_vals = coc_drivers.get("Cannibalization", [None] * 12)
    net_inno = [None] * 12
    for i in range(12):
        iv = inno_vals[i]
        cv = cann_vals[i]
        if iv is not None or cv is not None:
            net_inno[i] = round((iv or 0.0) + (cv or 0.0), 4)
    coc_drivers["Net Innovation"] = net_inno

    # Compound Driver: Net Price = Price + Elasticity
    price_vals = coc_drivers.get("Price", [None] * 12)
    elas_vals = coc_drivers.get("Elasticity", [None] * 12)
    net_price = [None] * 12
    for i in range(12):
        pv = price_vals[i]
        ev = elas_vals[i]
        if pv is not None or ev is not None:
            net_price[i] = round((pv or 0.0) + (ev or 0.0), 4)
    coc_drivers["Net Price"] = net_price

    return coc_drivers


# ─── 5. NUMBER FORMATTING & DYNAMIC COLOR GRADIENT ───────────────────────────

def fmt_coc_number(val: Optional[float], decimals: int = 1) -> str:
    """
    Strict presentation formatting:
    - Positives: 0.1, 3.5, 10.9
    - Negatives: (0.1), (3.2), (0.6), (6.9) (financial parentheses notation)
    - Zeroes / Nulls: - (dash)
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "-"
    rounded = round(val, decimals)
    if abs(rounded) < (0.5 / (10 ** decimals)):
        return "-"
    if rounded < 0:
        pos_str = f"{abs(rounded):.{decimals}f}"
        return f"({pos_str})"
    return f"{rounded:.{decimals}f}"


def get_driver_heatmap_style(val: Optional[float], max_pos: float, max_neg_mag: float) -> Tuple[str, str, str]:
    """
    Calculates dynamic conditional formatting heat-map colors:
    - Negatives: soft coral red gradient
    - Positives: mint green gradient
    - Dash / Zero: pure white background
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "#ffffff", "#111827", "400"

    v = round(val, 4)
    if abs(v) < 0.00005:
        return "#ffffff", "#111827", "400"

    if v < 0:
        ratio = min(1.0, abs(v) / max(0.01, max_neg_mag))
        if ratio > 0.66:
            return "#fca5a5", "#7f1d1d", "700"  # Strong red
        elif ratio > 0.33:
            return "#fecaca", "#991b1b", "600"  # Medium red
        else:
            return "#fee2e2", "#b91c1c", "500"  # Light red

    ratio = min(1.0, v / max(0.01, max_pos))
    if ratio > 0.66:
        return "#86efac", "#14532d", "700"  # Strong green
    elif ratio > 0.33:
        return "#bbf7d0", "#166534", "600"  # Medium green
    else:
        return "#dcfce7", "#15803d", "500"  # Light green


def build_data_cells(
    monthly_vals: List[Optional[float]],
    totals: Dict[str, Optional[float]],
    max_pos: float,
    max_neg_mag: float,
    bg_override: Optional[str] = None,
    text_override: Optional[str] = None,
    is_driver: bool = False,
    decimals: int = 1
) -> List[html.Td]:
    """Generates standard HTML data cells for Jan..Dec and Q1..Q4, FY, YTD, YTG."""
    cells = []

    # Months: Jan..Dec
    for i in range(12):
        val = monthly_vals[i] if i < len(monthly_vals) else None
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

    # Dynamic Kenvue Retail 4-4-5 Fiscal Calendar Month for today
    current_retail_month = get_current_kenvue_month()

    env_cutoff = os.getenv("IBP_CUTOFF_MONTH")
    if env_cutoff and env_cutoff.isdigit():
        cutoff_month = int(env_cutoff)
    elif active_cycle_month and 1 <= active_cycle_month <= 12:
        cutoff_month = active_cycle_month
    else:
        cutoff_month = current_retail_month

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
        "current_month": current_retail_month,
        "models": models,
        "gts_base": gts_base,
        "totals_base": totals_base,
        "gts_plan": gts_plan,
        "totals_plan": totals_plan,
        "drivers": drivers,
        "driver_totals": driver_totals,
        "price_factors": price_factors,
    }


# ─── 7. TABLE RENDERER MATCHING THE OFFICIAL VISUAL SPEC ─────────────────────

def render_gtscoc_table(data: dict) -> html.Div:
    """
    Renders GTS CoC Summary Matrix matching visual specification:
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
