import os
import sys
import re
import warnings
from typing import Optional, Dict, List
import pandas as pd
import snowflake.connector
from snowflake.connector.errors import DatabaseError, ProgrammingError, OperationalError
from dotenv import load_dotenv

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

warnings.filterwarnings('ignore', category=UserWarning)
load_dotenv()

_cached_connection = None


def normalize_text(val) -> str:
    """
    Normalizes string attributes consistently across Excel and Snowflake:
      - Handle NULL / NaN / None / empty string
      - Strip leading and trailing whitespace
      - Convert to uppercase
      - Collapse multiple spaces into a single space
    """
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip().upper()
    if s in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
        return ""
    return re.sub(r'\s+', ' ', s)


def get_snowflake_config() -> dict:
    """
    Loads Snowflake configuration from environment variables (.env).
    Supports standard SNOWFLAKE_* variables as well as common fallbacks (SF_*).
    """
    load_dotenv(override=True)

    def _get_env(*keys: str, default: Optional[str] = None) -> Optional[str]:
        for k in keys:
            val = os.getenv(k)
            if val is not None and val.strip() != "":
                return val.strip()
        return default

    config = {
        "user": _get_env("SNOWFLAKE_USER", "SF_USER", "USER", default="SA-JX2-SNFK-CVD-RPT@KENVUE.COM"),
        "password": _get_env("SNOWFLAKE_PASSWORD", "SF_PASSWORD", "PASSWORD"),
        "account": _get_env("SNOWFLAKE_ACCOUNT", "SF_ACCOUNT", "ACCOUNT", default="BK40750.east-us-2.azure"),
        "warehouse": _get_env("SNOWFLAKE_WAREHOUSE", "SF_WAREHOUSE", "WAREHOUSE", default="PROD_ENVIRONMENT_USAGE_XSMALL1_WH"),
        "database": _get_env("SNOWFLAKE_DATABASE", "SF_DATABASE", "DATABASE", default="PROD_CUSTOMER360_GLBLSYNDCTD"),
        "schema": _get_env("SNOWFLAKE_SCHEMA", "SF_SCHEMA", "SCHEMA", default="CORE_ACCESS"),
        "role": _get_env("SNOWFLAKE_ROLE", "SF_ROLE", "ROLE", default="PROD_SA_JX2_SNFK_CVD_RPT_ER"),
        "authenticator": _get_env("SNOWFLAKE_AUTHENTICATOR", "SF_AUTHENTICATOR", "AUTHENTICATOR", default="externalbrowser"),
    }

    return {k: v for k, v in config.items() if v is not None}


def get_snowflake_connection(**kwargs) -> snowflake.connector.SnowflakeConnection:
    """
    Creates and returns a connection to Snowflake.
    Reuses active connection when available to prevent repeated SSO browser popups.
    If force_new=True, closes active connection and establishes a fresh connection.
    """
    global _cached_connection
    force_new = kwargs.pop("force_new", False)
    config = get_snowflake_config()
    config.update(kwargs)

    if not force_new and _cached_connection is not None:
        try:
            if not _cached_connection.is_closed():
                return _cached_connection
        except Exception:
            _cached_connection = None
    elif force_new and _cached_connection is not None:
        try:
            _cached_connection.close()
        except Exception:
            pass
        _cached_connection = None

    if config.get("authenticator") == "externalbrowser":
        config.pop("password", None)

    private_key_pem = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

    if (private_key_pem or private_key_path) and config.get("authenticator") != "externalbrowser":
        try:
            if private_key_path:
                abs_path = os.path.abspath(private_key_path)
                if not os.path.exists(abs_path):
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    abs_path = os.path.join(base_dir, private_key_path)
                with open(abs_path, "rb") as kf:
                    pem_bytes = kf.read()
            else:
                pem_str = private_key_pem.replace("\\n", "\n").strip()
                lines = [line.strip() for line in pem_str.splitlines() if line.strip()]
                if lines[0].startswith("-----BEGIN") and lines[-1].startswith("-----END"):
                    header, footer = lines[0], lines[-1]
                    body = "".join(lines[1:-1]).replace(" ", "")
                    pad_len = len(body) % 4
                    if pad_len > 0:
                        body += "=" * (4 - pad_len)
                    pem_str = header + "\n" + "\n".join([body[i:i+64] for i in range(0, len(body), 64)]) + "\n" + footer
                pem_bytes = pem_str.encode('utf-8')

            p_key = serialization.load_pem_private_key(
                pem_bytes,
                password=passphrase.encode('utf-8') if passphrase else None,
                backend=default_backend()
            )
            pkb = p_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            config["private_key"] = pkb
            config.pop("password", None)
        except Exception as e:
            print(f"Notice parsing private key: {e}")

    missing = []
    if not config.get("account"):
        missing.append("SNOWFLAKE_ACCOUNT")
    if not config.get("user"):
        missing.append("SNOWFLAKE_USER")
    if not config.get("password") and config.get("authenticator") != "externalbrowser" and "private_key" not in config:
        missing.append("SNOWFLAKE_PASSWORD / AUTHENTICATION METHOD")

    if missing:
        raise ValueError(
            f"Missing required connection setting(s): {', '.join(missing)}.\n"
            "Please check your '.env' file configuration."
        )

    config["autocommit"] = True
    conn = snowflake.connector.connect(**config)

    try:
        cur = conn.cursor()
        db = config.get("database")

        for ctx_cmd, val in [
            ("USE ROLE", config.get("role")),
            ("USE WAREHOUSE", config.get("warehouse")),
            ("USE DATABASE", db)
        ]:
            if val:
                try:
                    cur.execute(f"{ctx_cmd} {val};")
                except Exception as ctx_err:
                    print(f"Notice {ctx_cmd} ({val}): {ctx_err}")
                    if ctx_cmd == "USE WAREHOUSE" and val != "PROD_ENVIRONMENT_USAGE_XSMALL1_WH":
                        try:
                            cur.execute("USE WAREHOUSE PROD_ENVIRONMENT_USAGE_XSMALL1_WH;")
                            print("Successfully fallback to WAREHOUSE PROD_ENVIRONMENT_USAGE_XSMALL1_WH")
                        except Exception as fb_err:
                            print(f"Notice fallback warehouse: {fb_err}")
    except Exception as e:
        print(f"Notice setting session context: {e}")

    _cached_connection = conn
    return conn


_cached_model_mapping_df = None
_loaded_excel_path = None
_loaded_sheet_name = None

MODEL_MAPPING_COLUMNS = [
    "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC",
    "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC",
    "GLOBAL_GMC_C3_NEED_STATE_DESC",
    "GLOBAL_GMC_C4_CATEGORY_DESC",
    "GLOBAL_GMC_C5_SUB_CATEGORY_DESC",
    "GLOBAL_GMC_B1_BRAND_DESC",
    "GLOBAL_GMC_B2_SUB_BRAND_DESC",
    "Model"
]

ALLOWED_GBUS = ["ESSENTIAL HEALTH", "SELF CARE", "SKIN HEALTH & BEAUTY"]

HIERARCHY_COL_MAP = {
    "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC": "POS_BUSINESS_SEGMENT",
    "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC": "POS_BUSINESS_SUB_SEGMENT",
    "GLOBAL_GMC_C3_NEED_STATE_DESC": "POS_NEED_STATE",
    "GLOBAL_GMC_C4_CATEGORY_DESC": "POS_CATEGORY",
    "GLOBAL_GMC_C5_SUB_CATEGORY_DESC": "POS_SUB_CATEGORY",
    "GLOBAL_GMC_B1_BRAND_DESC": "POS_BRAND",
    "GLOBAL_GMC_B2_SUB_BRAND_DESC": "POS_SUB_BRAND",
}

IGNORED_PLACEHOLDERS = [
    "ALL", "ALL GBU", "ALL SQUADS", "ALL NEED STATES", "ALL SQUAD/NEED STATES", "ALL SQUAD/NEED STATE", "ALL MODELS",
    "SELECT GBU", "SELECT NEED STATE", "SELECT MODEL", "SELECT SQUAD/NEED STATE", "", "NONE"
]


def get_postgres_config() -> dict:
    """
    Loads PostgreSQL configuration from environment variables (.env).
    Supports IBP_DB_*, PG_*, and POSTGRES_* environment variables.
    """
    load_dotenv(override=True)

    def _get_env(*keys: str, default: Optional[str] = None) -> Optional[str]:
        for k in keys:
            val = os.getenv(k)
            if val is not None and val.strip() != "":
                return val.strip()
        return default

    return {
        "host": _get_env("IBP_DB_HOST", "PGHOST", "POSTGRES_HOST", "DB_HOST", "POSTGRESQL_HOST", default="localhost"),
        "port": int(_get_env("IBP_DB_PORT", "PGPORT", "POSTGRES_PORT", "DB_PORT", "POSTGRESQL_PORT", default="5432")),
        "dbname": _get_env("IBP_DB_NAME", "PGDATABASE", "POSTGRES_DB", "DB_NAME", "POSTGRESQL_DB", "POSTGRES_DATABASE", default="na_ibp_db"),
        "user": _get_env("IBP_DB_USER", "PGUSER", "POSTGRES_USER", "DB_USER", "POSTGRESQL_USER", default="postgres"),
        "password": _get_env("IBP_DB_PASSWORD", "PGPASSWORD", "POSTGRES_PASSWORD", "DB_PASSWORD", "POSTGRESQL_PASSWORD", default="postgres"),
        "sslmode": _get_env("IBP_DB_SSLMODE", "SSLMODE", default="prefer"),
    }


def get_postgres_connection():
    """
    Uses the existing IBP PostgreSQL environment variables with psycopg2.
    Required env vars: IBP_DB_HOST, IBP_DB_PORT, IBP_DB_NAME, IBP_DB_USER, IBP_DB_PASSWORD, IBP_DB_SSLMODE
    """
    try:
        import psycopg2
    except ImportError:
        print("\nERROR: psycopg2 is not installed in this Python environment.")
        print("Install it with:")
        print("    pip install psycopg2-binary")
        raise ImportError("psycopg2 is not installed in this Python environment. Install it with: pip install psycopg2-binary")

    return psycopg2.connect(
        host=os.getenv("IBP_DB_HOST"),
        port=os.getenv("IBP_DB_PORT", "5432"),
        dbname=os.getenv("IBP_DB_NAME"),
        user=os.getenv("IBP_DB_USER"),
        password=os.getenv("IBP_DB_PASSWORD"),
        sslmode=os.getenv("IBP_DB_SSLMODE", "prefer"),
    )


def load_model_mapping_df(allow_fallback: bool = False, file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Loads active Model Hierarchy Mapping from PostgreSQL database (na_ibp_db)
    by querying public.hierarchy_models and public.hierarchy_mapping.
    Caches the loaded DataFrame in _cached_model_mapping_df.
    """
    global _cached_model_mapping_df

    if _cached_model_mapping_df is not None:
        return _cached_model_mapping_df

    pg_sql = """
    SELECT
        hm.model_id,
        hm.model_name AS "Model",
        hm.model_name AS model_name,
        hm.model_code,
        hm.gbu_code AS "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC",
        hm.gbu_code AS gbu_code,
        hmap.mapping_id,
        hmap.business_subsegment AS "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC",
        hmap.business_subsegment AS business_subsegment,
        hmap.squad_name AS "GLOBAL_GMC_C3_NEED_STATE_DESC",
        hmap.squad_name AS squad_name,
        hmap.category AS "GLOBAL_GMC_C4_CATEGORY_DESC",
        hmap.category AS category,
        hmap.subcategory AS "GLOBAL_GMC_C5_SUB_CATEGORY_DESC",
        hmap.subcategory AS subcategory,
        hmap.brand_name AS "GLOBAL_GMC_B1_BRAND_DESC",
        hmap.brand_name AS brand_name,
        hmap.sub_brand_name AS "GLOBAL_GMC_B2_SUB_BRAND_DESC",
        hmap.sub_brand_name AS sub_brand_name,
        hm.is_active AS model_is_active,
        hmap.is_active AS mapping_is_active
    FROM public.hierarchy_models hm
    INNER JOIN public.hierarchy_mapping hmap
        ON hm.model_id = hmap.model_id
    WHERE
        hm.is_active = TRUE
        AND hmap.is_active = TRUE
    ORDER BY
        hm.gbu_code,
        hm.model_name,
        hmap.mapping_id;
    """

    df = pd.DataFrame()
    try:
        conn = get_postgres_connection()
        print(f"[INFO]: Connected to PostgreSQL na_ibp_db successfully.")
        df = pd.read_sql(pg_sql, conn)
        conn.close()
    except Exception as e:
        print(f"[NOTICE]: PostgreSQL hierarchy mapping fetch notice: {e}")
        df = pd.DataFrame(columns=[
            "model_id", "Model", "model_name", "model_code",
            "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC",
            "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC",
            "GLOBAL_GMC_C3_NEED_STATE_DESC",
            "GLOBAL_GMC_C4_CATEGORY_DESC",
            "GLOBAL_GMC_C5_SUB_CATEGORY_DESC",
            "GLOBAL_GMC_B1_BRAND_DESC",
            "GLOBAL_GMC_B2_SUB_BRAND_DESC",
            "gbu_code", "business_subsegment", "squad_name",
            "category", "subcategory", "brand_name", "sub_brand_name"
        ])

    if not df.empty:
        for col in MODEL_MAPPING_COLUMNS:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].apply(normalize_text)

        unique_models_list = sorted([
            str(m).strip() for m in df['Model'].unique()
            if pd.notnull(m) and str(m).strip() != ""
        ])

        print("=" * 70)
        print("POSTGRESQL MODEL HIERARCHY MAPPING DIAGNOSTICS")
        print("=" * 70)
        print(f"Source Database:      public.hierarchy_models & hierarchy_mapping")
        print(f"Total Mapping Rows:   {len(df)}")
        print(f"Total Active Models:  {len(unique_models_list)}")
        print(f"First 15 Models:      {unique_models_list[:15]}")
        print("=" * 70)

    _cached_model_mapping_df = df
    return df


def get_matching_postgres_rules(gbu: Optional[str] = None, squad: Optional[str] = None, model: Optional[str] = None) -> pd.DataFrame:
    """
    Extracts matching PostgreSQL hierarchy mapping rows for the selected GBU, Squad/Need State, and Model filters.
    Retrieves ALL active mapping rows belonging to the selected Model using model_id or model_name.
    - Squad/Need State maps strictly to PostgreSQL squad_name / GLOBAL_GMC_C3_NEED_STATE_DESC.
    - Respects all populated hierarchy fields in each rule (blanks act as wildcards).
    """
    df_map = load_model_mapping_df(allow_fallback=False)
    if df_map.empty:
        return df_map

    rules = df_map.copy()

    if model and normalize_text(model) not in IGNORED_PLACEHOLDERS:
        model_norm = normalize_text(model)
        rules = rules[rules['Model'].apply(normalize_text) == model_norm]

    return rules.reset_index(drop=True)


get_matching_excel_rules = get_matching_postgres_rules


def filter_snowflake_by_postgres_rules(df_sf: pd.DataFrame, matching_rules_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters Snowflake POS DataFrame using PostgreSQL mapping rules.
    Each row in matching_rules_df represents a valid product hierarchy rule.
      - Populated PostgreSQL fields must match the corresponding POS column in Snowflake.
      - Unpopulated (blank/NULL) PostgreSQL fields act as wildcards (match anything).
    """
    if df_sf.empty or matching_rules_df.empty:
        return pd.DataFrame(columns=df_sf.columns)

    SNOWFLAKE_TO_POSTGRES_MAPPING = {
        "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC": "gbu_code",
        "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC": "business_subsegment",
        "GLOBAL_GMC_C3_NEED_STATE_DESC": "squad_name",
        "GLOBAL_GMC_C4_CATEGORY_DESC": "category",
        "GLOBAL_GMC_C5_SUB_CATEGORY_DESC": "subcategory",
        "GLOBAL_GMC_B1_BRAND_DESC": "brand_name",
        "GLOBAL_GMC_B2_SUB_BRAND_DESC": "sub_brand_name",
    }

    df_norm = pd.DataFrame(index=df_sf.index)
    for sf_col in SNOWFLAKE_TO_POSTGRES_MAPPING.keys():
        if sf_col in df_sf.columns:
            df_norm[sf_col] = df_sf[sf_col].apply(normalize_text)
        else:
            df_norm[sf_col] = ""

    matched_mask = pd.Series(False, index=df_sf.index)

    for _, r in matching_rules_df.iterrows():
        rule_mask = pd.Series(True, index=df_sf.index)
        has_conditions = False

        for sf_col, pg_col in SNOWFLAKE_TO_POSTGRES_MAPPING.items():
            val = normalize_text(r.get(pg_col, r.get(sf_col, "")))
            if val:
                has_conditions = True
                rule_mask &= (df_norm[sf_col] == val)

        if has_conditions:
            matched_mask |= rule_mask
        else:
            matched_mask |= pd.Series(True, index=df_sf.index)

    return df_sf[matched_mask].reset_index(drop=True)


filter_snowflake_by_excel_rules = filter_snowflake_by_postgres_rules


def filter_df_by_model(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
    """
    Applies Model filter using PostgreSQL mapping rules.
    Finds ALL PostgreSQL rows for model_name and applies populated hierarchy fields (blank fields wildcards).
    """
    if df.empty or not model_name or normalize_text(model_name) in IGNORED_PLACEHOLDERS:
        return df

    matching_rules = get_matching_postgres_rules(model=model_name)
    return filter_snowflake_by_postgres_rules(df, matching_rules)


def get_model_options() -> List[str]:
    """
    Creates Model dropdown options dynamically from PostgreSQL mapping.
    """
    df_map = load_model_mapping_df(allow_fallback=False)
    if 'Model' not in df_map.columns or df_map.empty:
        return ["Select Model"]

    models = df_map['Model'].dropna().astype(str).str.strip()
    models = models[(models != "") & (~models.str.upper().isin(["NAN", "NONE", "NULL"]))]
    unique_models = sorted(models.unique().tolist())

    return ["Select Model"] + unique_models


def get_kv_month_ranges() -> List[dict]:
    """
    Generates Kenvue Fiscal Month date ranges (month_start, month_end)
    dynamically for all available years in the Kenvue Calendar.
    Returns list of dicts: [{'year': 2021, 'm_nbr': 12, 'kv_month': '2021-12', 'start': '2021-11-29', 'end': '2022-01-02'}, ...]
    """
    lookup_map = build_kv_calendar_lookup_map()
    m_agg = {}

    for d_str, info in lookup_map.items():
        if isinstance(d_str, str) and len(d_str) == 10 and d_str[4] == '-' and d_str[7] == '-':
            try:
                yr = int(info['y_str'])
                m_nbr = int(info['m_nbr'])
                wb = str(info['kv_week_beginning']).strip()
                we = str(info['kv_week_ending']).strip()
                key = (yr, m_nbr)
                if key not in m_agg:
                    m_agg[key] = {'start': wb, 'end': we}
                else:
                    if wb < m_agg[key]['start']:
                        m_agg[key]['start'] = wb
                    if we > m_agg[key]['end']:
                        m_agg[key]['end'] = we
            except Exception:
                pass

    sorted_keys = sorted(m_agg.keys())
    ranges = []
    for yr, m in sorted_keys:
        st = m_agg[(yr, m)]['start']
        en = m_agg[(yr, m)]['end']
        ranges.append({
            'year': yr,
            'y_str': str(yr),
            'm_nbr': m,
            'kv_month': f"{yr}-{m:02d}",
            'start': st,
            'end': en
        })

    return ranges


def fetch_joined_snowflake_data(
    brand=None,
    category=None,
    sub_brand=None,
    retailer=None,
    business_segment=None,
    model=None,
    channel=None,
    region=None,
    gbu=None,
    squad=None
) -> pd.DataFrame:
    """
    Executes Snowflake POS query with Snowflake-side Kenvue Fiscal Month aggregation.
    Builds a dynamic CASE statement using Kenvue Calendar month start/end ranges.
    Returns monthly aggregated rows for all dynamic calendar periods.
    """
    conn = None
    try:
        ranges = get_kv_month_ranges()
        if not ranges:
            return pd.DataFrame()

        min_date = ranges[0]['start']
        max_date = ranges[-1]['end']

        case_whens = []
        for r in ranges:
            case_whens.append(
                f"WHEN TRY_TO_DATE(dim_time.GLOBAL_DATE_SHORT_DESC) BETWEEN '{r['start']}' AND '{r['end']}' THEN '{r['kv_month']}'"
            )
        case_sql = "CASE\n" + "\n".join(f"    {w}" for w in case_whens) + "\n    ELSE NULL\nEND"

        matching_rules = get_matching_excel_rules(gbu=gbu, squad=squad, model=model)

        col_db_map = {
            "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC": "dim_product.GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC",
            "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC": "dim_product.GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC",
            "GLOBAL_GMC_C3_NEED_STATE_DESC": "dim_product.GLOBAL_GMC_C3_NEED_STATE_DESC",
            "GLOBAL_GMC_C4_CATEGORY_DESC": "dim_product.GLOBAL_GMC_C4_CATEGORY_DESC",
            "GLOBAL_GMC_C5_SUB_CATEGORY_DESC": "dim_product.GLOBAL_GMC_C5_SUB_CATEGORY_DESC",
            "GLOBAL_GMC_B1_BRAND_DESC": "dim_product.GLOBAL_GMC_B1_BRAND_DESC",
            "GLOBAL_GMC_B2_SUB_BRAND_DESC": "dim_product.GLOBAL_GMC_B2_SUB_BRAND_DESC",
        }

        rule_clauses = []
        if not matching_rules.empty:
            for _, r in matching_rules.iterrows():
                conds = []
                for xl_col, db_col in col_db_map.items():
                    val = normalize_text(r.get(xl_col, ""))
                    if val:
                        val_esc = val.replace("'", "''")
                        conds.append(f"UPPER(TRIM({db_col})) = '{val_esc}'")
                if conds:
                    rule_clauses.append("(" + " AND ".join(conds) + ")")

        product_filter_sql = ""
        if rule_clauses:
            product_filter_sql = "AND (" + " OR\n      ".join(rule_clauses) + ")"
        else:
            fallback_conds = []
            if gbu and normalize_text(gbu) not in IGNORED_PLACEHOLDERS:
                gbu_esc = normalize_text(gbu).replace("'", "''")
                fallback_conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC)) = '{gbu_esc}'")
            if squad and normalize_text(squad) not in IGNORED_PLACEHOLDERS:
                squad_esc = normalize_text(squad).replace("'", "''")
                fallback_conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C3_NEED_STATE_DESC)) = '{squad_esc}'")
            if fallback_conds:
                product_filter_sql = "AND " + " AND ".join(fallback_conds)

        extra_conds = []
        if brand and normalize_text(brand) not in IGNORED_PLACEHOLDERS:
            b_esc = normalize_text(brand).replace("'", "''")
            extra_conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_B1_BRAND_DESC)) = '{b_esc}'")
        if category and normalize_text(category) not in IGNORED_PLACEHOLDERS:
            c_esc = normalize_text(category).replace("'", "''")
            extra_conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_C4_CATEGORY_DESC)) = '{c_esc}'")
        if sub_brand and normalize_text(sub_brand) not in IGNORED_PLACEHOLDERS:
            sb_esc = normalize_text(sub_brand).replace("'", "''")
            extra_conds.append(f"UPPER(TRIM(dim_product.GLOBAL_GMC_B2_SUB_BRAND_DESC)) = '{sb_esc}'")

        if extra_conds:
            product_filter_sql += "\n    AND " + " AND ".join(extra_conds)

        official_query = f"""
        SELECT
            {case_sql} AS KV_MONTH,
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
            AND TRY_TO_DATE(dim_time.GLOBAL_DATE_SHORT_DESC) BETWEEN '{min_date}' AND '{max_date}'
            {product_filter_sql}
        GROUP BY 1
        HAVING KV_MONTH IS NOT NULL
        ORDER BY KV_MONTH ASC;
        """

        conn = get_snowflake_connection()
        import time
        df_sf = None
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            cursor = None
            try:
                if attempt > 1 or conn is None:
                    try:
                        if conn:
                            conn.close()
                    except Exception:
                        pass
                    conn = get_snowflake_connection(force_new=True)

                cursor = conn.cursor()
                cursor.execute(official_query)
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                df_sf = pd.DataFrame(rows, columns=columns)
                print(f"Snowflake monthly aggregated rows returned: {len(df_sf)}")
                break
            except Exception as fetch_err:
                err_str = str(fetch_err)
                print(f"[Attempt {attempt}/{max_attempts}] Snowflake fetch notice: {err_str}")
                is_transient = any(k in err_str.lower() for k in [
                    "sslerror", "unexpected eof", "bad handshake", "max retries exceeded",
                    "blob.core.windows.net", "httpsconnectionpool", "connection error"
                ])
                if is_transient and attempt < max_attempts:
                    print(f"Transient Azure Blob SSL error detected during fetchall. Re-establishing fresh connection (attempt {attempt+1}/{max_attempts})...")
                    time.sleep(1.0 * attempt)
                else:
                    raise fetch_err
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass

        if df_sf is not None and not df_sf.empty:
            df_sf.columns = [c.upper() for c in df_sf.columns]
            pos_col = 'POS_VALUE' if 'POS_VALUE' in df_sf.columns else ('POS_DOLLARS' if 'POS_DOLLARS' in df_sf.columns else None)
            total_pos_dollars = df_sf[pos_col].sum() if pos_col and pos_col in df_sf.columns else 0.0

            print("=" * 70)
            print("POSTGRESQL MODEL MAPPING + SNOWFLAKE POS RESULT")
            print("=" * 70)
            print(f"Selected GBU:                               '{gbu}'")
            print(f"Selected Need State:                        '{squad}'")
            print(f"Selected Model:                             '{model}'")
            print(f"Number of PostgreSQL mapping rows:          {len(matching_rules)}")
            print(f"Number of Snowflake rows after mapping:     {len(df_sf)}")
            print(f"Final POS $:                                ${total_pos_dollars:,.2f}")
            print("=" * 70)

            return df_sf.reset_index(drop=True)

        print("=" * 70)
        print("POSTGRESQL MODEL MAPPING + SNOWFLAKE POS RESULT")
        print("=" * 70)
        print(f"Selected GBU:                               '{gbu}'")
        print(f"Selected Need State:                        '{squad}'")
        print(f"Selected Model:                             '{model}'")
        print(f"Number of PostgreSQL mapping rows:          {len(matching_rules)}")
        print(f"Number of Snowflake rows after mapping:     0")
        print(f"Final POS $:                                $0.00")
        print("=" * 70)

        return pd.DataFrame()

    except Exception as e:
        print(f"Error reading Snowflake data: {e}")
        return pd.DataFrame()


def fetch_postgres_gbus() -> List[str]:
    """
    Executes PostgreSQL query to fetch distinct GBU values from public.hierarchy_mapping.
    """
    sql = """
    SELECT DISTINCT TRIM(gbu_code) AS gbu
    FROM public.hierarchy_mapping
    WHERE is_active = TRUE
      AND gbu_code IS NOT NULL
      AND TRIM(gbu_code) <> ''
    ORDER BY gbu;
    """
    gbus = []
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        gbus = [row[0] for row in rows if row[0]]
    except Exception as e:
        print(f"[POSTGRES GBU FETCH NOTICE]: {e}")

    return gbus


def fetch_postgres_need_states(selected_gbu: str) -> List[str]:
    """
    Executes PostgreSQL query to fetch distinct Need States (squad_name) for selected GBU.
    """
    if not selected_gbu or normalize_text(selected_gbu) in IGNORED_PLACEHOLDERS:
        return []

    sql = """
    SELECT DISTINCT
        TRIM(squad_name) AS need_state
    FROM public.hierarchy_mapping
    WHERE is_active = TRUE
      AND UPPER(TRIM(gbu_code)) = UPPER(TRIM(%s))
      AND squad_name IS NOT NULL
      AND TRIM(squad_name) <> ''
    ORDER BY need_state;
    """

    need_states = []
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute(sql, (selected_gbu.strip(),))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        need_states = [row[0] for row in rows if row[0]]
    except Exception as e:
        print(f"[DEBUG NOTICE]: Direct PostgreSQL Need State query error: {e}")

    print("=" * 60)
    print("NEED STATE DEBUG")
    print("=" * 60)
    print("Selected GBU:")
    print(selected_gbu)
    print()
    print("Need State rows returned:")
    print(len(need_states))
    print()
    print("Need State values:")
    if need_states:
        for idx, ns_val in enumerate(need_states, start=1):
            print(f"{idx}. {ns_val}")
    else:
        print("(None / 0 rows returned)")
    print("=" * 60)

    return need_states


def fetch_postgres_models(selected_gbu: str, selected_need_state: str) -> List[str]:
    """
    Executes PostgreSQL query to fetch active Models for selected GBU and Need State.
    """
    if not selected_gbu or normalize_text(selected_gbu) in IGNORED_PLACEHOLDERS or not selected_need_state or normalize_text(selected_need_state) in IGNORED_PLACEHOLDERS:
        return []

    sql = """
    SELECT DISTINCT
        hm.model_id,
        hm.model_name
    FROM public.hierarchy_models hm
    INNER JOIN public.hierarchy_mapping hmap
        ON hm.model_id = hmap.model_id
    WHERE hm.is_active = TRUE
      AND hmap.is_active = TRUE
      AND UPPER(TRIM(hmap.gbu_code)) = UPPER(TRIM(%s))
      AND UPPER(TRIM(hmap.squad_name)) = UPPER(TRIM(%s))
    ORDER BY hm.model_name;
    """

    models = []
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute(sql, (selected_gbu.strip(), selected_need_state.strip()))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        models = [row[1] for row in rows if row[1]]
    except Exception as e:
        print(f"[POSTGRES MODEL FETCH NOTICE]: {e}")

    return models


def get_filter_options(model=None, brand=None, category=None, sub_brand=None, gbu=None, squad=None, df_sf=None):
    """
    Dynamically generates valid options for GBU, Squad/Need State, Model, Brand, Category, and Sub-Brand dropdowns.
    GBU, Need State (C3 ONLY), and Model dropdowns are generated strictly from the PostgreSQL database mapping (na_ibp_db).
    Brand, Category, and Sub-Brand options are generated from df_sf IF supplied.
    DOES NOT execute Snowflake queries internally.
    """
    df_map = load_model_mapping_df(allow_fallback=False)

    raw_gbus = fetch_postgres_gbus()
    if not raw_gbus and not df_map.empty:
        raw_gbus = sorted([str(g).strip().upper() for g in df_map['GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC'].dropna().unique() if normalize_text(g) != ""])
    if not raw_gbus:
        raw_gbus = ALLOWED_GBUS
    gbu_opts = ["Select GBU"] + raw_gbus

    clean_squads = []
    if gbu and normalize_text(gbu) not in IGNORED_PLACEHOLDERS:
        clean_squads = fetch_postgres_need_states(gbu)
        if not clean_squads and not df_map.empty:
            df_gbu = df_map[df_map['GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC'].apply(normalize_text) == normalize_text(gbu)]
            squads_c3 = df_gbu['GLOBAL_GMC_C3_NEED_STATE_DESC'].dropna().unique()
            clean_squads = sorted([str(s).strip().upper() for s in squads_c3 if normalize_text(s) != ""])

    squad_opts = ["Select Need State"] + clean_squads

    clean_models = []
    if gbu and normalize_text(gbu) not in IGNORED_PLACEHOLDERS and squad and normalize_text(squad) not in IGNORED_PLACEHOLDERS:
        clean_models = fetch_postgres_models(gbu, squad)
        if not clean_models and not df_map.empty:
            selected_gbu_norm = normalize_text(gbu)
            selected_need_state_norm = normalize_text(squad)
            group_col = "model_id" if "model_id" in df_map.columns else "Model"
            for _, model_group in df_map.groupby(group_col):
                model_valid = False
                for _, rule in model_group.iterrows():
                    rule_gbu = normalize_text(rule.get("GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC", ""))
                    rule_need_state = normalize_text(rule.get("GLOBAL_GMC_C3_NEED_STATE_DESC", ""))
                    gbu_match = (selected_gbu_norm == "" or rule_gbu == "" or rule_gbu == selected_gbu_norm)
                    need_state_match = (selected_need_state_norm == "" or rule_need_state == "" or rule_need_state == selected_need_state_norm)
                    if gbu_match and need_state_match:
                        model_valid = True
                        break
                if model_valid:
                    m_name = model_group["Model"].iloc[0]
                    if normalize_text(m_name) != "":
                        clean_models.append(str(m_name).strip())
            clean_models = sorted(list(set(clean_models)))

    model_opts = ["Select Model"] + clean_models

    print("=" * 70)
    print("FILTER DROPDOWN DIAGNOSTICS (SOURCE: POSTGRESQL MAPPING ONLY)")
    print("=" * 70)
    print(f"Selected GBU:                 '{gbu}'")
    print(f"Selected Need State:          '{squad}'")
    print(f"Selected Model:               '{model}'")
    print(f"GBU Options ({len(gbu_opts)}):            {gbu_opts}")
    print(f"Need State Options ({len(squad_opts)}):     {squad_opts}")
    print(f"Model Options ({len(model_opts)}):          {model_opts[:10]}...")
    print("=" * 70)

    if df_sf is not None and isinstance(df_sf, pd.DataFrame) and not df_sf.empty:
        df_sf_copy = df_sf.copy()
        df_sf_copy.columns = [c.upper() for c in df_sf_copy.columns]

        avail_brands = sorted([str(b).upper() for b in df_sf_copy['POS_BRAND'].dropna().unique() if normalize_text(b) != ""])
        brand_opts = ["All Brands"] + avail_brands

        df_brand = df_sf_copy
        if brand and normalize_text(brand) not in IGNORED_PLACEHOLDERS:
            brand_norm = normalize_text(brand)
            df_brand = df_sf_copy[df_sf_copy['POS_BRAND'].apply(normalize_text) == brand_norm]

        avail_categories = sorted([str(c).upper() for c in df_brand['POS_CATEGORY'].dropna().unique() if normalize_text(c) != ""])
        category_opts = ["All Categories"] + avail_categories

        df_cat = df_brand
        if category and normalize_text(category) not in IGNORED_PLACEHOLDERS:
            cat_norm = normalize_text(category)
            df_cat = df_brand[df_brand['POS_CATEGORY'].apply(normalize_text) == cat_norm]

        avail_sub_brands = sorted([str(sb).upper() for sb in df_cat['POS_SUB_BRAND'].dropna().unique() if normalize_text(sb) != ""])
        sub_brand_opts = ["All Sub-Brands"] + avail_sub_brands

        return {
            "gbus": gbu_opts,
            "squads": squad_opts,
            "models": model_opts,
            "brands": brand_opts,
            "categories": category_opts,
            "sub_brands": sub_brand_opts,
            "retailers": ["All", "TOTAL US - MULTI OUTLET+"],
            "segments": ["All"]
        }

    return {
        "gbus": gbu_opts,
        "squads": squad_opts,
        "models": model_opts,
        "brands": ["All Brands"],
        "categories": ["All Categories"],
        "sub_brands": ["All Sub-Brands"],
        "retailers": ["All", "TOTAL US - MULTI OUTLET+"],
        "segments": ["All"]
    }


MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

_cached_kv_calendar_df = None
_cached_date_to_kv_map = None

EXPLICIT_KV_CALENDAR_PATH = r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\KV Calendar Data Dump.xlsx"


def load_kv_calendar_df() -> pd.DataFrame:
    """
    Attempts to load the actual Kenvue Calendar Excel file if present on system.
    Returns empty DataFrame if Excel file is not found (safe runtime execution).
    """
    global _cached_kv_calendar_df
    if _cached_kv_calendar_df is not None:
        return _cached_kv_calendar_df

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        EXPLICIT_KV_CALENDAR_PATH,
        os.path.join(base_dir, "KV Calendar Data Dump.xlsx"),
        os.path.join(base_dir, "KV Calender Data Dump.xlsx"),
        os.path.join(base_dir, "kv_calendar_data_dump.xlsx"),
        os.path.join(base_dir, "kv_calender_data_dump.xlsx"),
    ]
    env_path = os.getenv("KV_CALENDAR_PATH")
    if env_path:
        candidate_paths.insert(0, env_path if os.path.isabs(env_path) else os.path.join(base_dir, env_path))

    df_cal = None
    loaded_path = None

    for cand in candidate_paths:
        if cand and os.path.exists(cand):
            try:
                xl = pd.ExcelFile(cand)
                df_cal = xl.parse(xl.sheet_names[0])
                loaded_path = cand
                break
            except Exception as e:
                print(f"Notice reading calendar excel '{cand}': {e}")

    if df_cal is None or df_cal.empty:
        df_cal = pd.DataFrame()

    if not df_cal.empty:
        df_cal.columns = [str(c).strip().upper() for c in df_cal.columns]

    _cached_kv_calendar_df = df_cal

    if loaded_path:
        print("=" * 70)
        print("ACTUAL KENVUE CALENDAR EXCEL DIAGNOSTICS")
        print("=" * 70)
        print(f"Calendar Excel Path: {loaded_path}")
        print(f"Total Calendar Rows: {len(df_cal)}")
        print(f"Calendar Columns:   {list(df_cal.columns)}")
        print("=" * 70)

    return df_cal


def build_kv_calendar_lookup_map() -> dict:
    """
    Builds a lookup dictionary mapping every week in the KV Calendar to Kenvue Month and Year
    directly from the authoritative Kenvue Calendar Excel file ('KV Calendar Data Dump.xlsx').
    """
    import datetime
    lookup = {}
    df_cal = load_kv_calendar_df()

    if df_cal is None or df_cal.empty:
        raise FileNotFoundError(
            "Authoritative Kenvue Calendar Excel file ('KV Calendar Data Dump.xlsx') is missing or empty. "
            "Please ensure the Excel calendar file is present in the project directory."
        )

    for _, row in df_cal.iterrows():
        m_nbr = None
        for m_col in ['KV_MTH_NBR', 'KV_MONTH_NBR', 'CAL_MONTH_NBR', 'MONTH']:
            if m_col in row and pd.notnull(row[m_col]):
                try:
                    m_nbr = int(float(row[m_col]))
                    break
                except Exception:
                    pass

        if m_nbr is None or m_nbr < 1 or m_nbr > 12:
            continue

        m_idx = m_nbr - 1
        m_name = MONTHS[m_idx]

        yr = None
        for yr_col in ['KV_YEAR', 'CAL_YEAR', 'YEAR']:
            if yr_col in row and pd.notnull(row[yr_col]):
                try:
                    yr = int(float(row[yr_col]))
                    break
                except Exception:
                    pass

        wk_beg_dt = None
        wk_end_dt = None
        for b_col in ['KV_WEEK_BEGINNING', 'CAL_WEEK_BEGINNING', 'WEEK_BEGINNING']:
            if b_col in row and pd.notnull(row[b_col]):
                dt = pd.to_datetime(row[b_col], errors='coerce')
                if pd.notnull(dt):
                    wk_beg_dt = dt.date()
                    break

        for e_col in ['KV_WEEK_ENDING', 'CAL_WEEK_ENDING', 'WEEK_ENDING', 'CAL_DATE']:
            if e_col in row and pd.notnull(row[e_col]):
                dt = pd.to_datetime(row[e_col], errors='coerce')
                if pd.notnull(dt):
                    wk_end_dt = dt.date()
                    break

        if not yr and wk_beg_dt:
            yr = wk_beg_dt.year

        if not yr:
            continue

        y_str = str(yr)
        qtr = f"Q{(m_idx // 3) + 1}"

        info = {
            "m_idx": m_idx,
            "m_nbr": m_nbr,
            "m_name": m_name,
            "y_str": y_str,
            "quarter": qtr,
            "kv_wk_id": str(row.get('KV_WK_ID', f"{y_str}{m_nbr:02d}")),
            "kv_tm_per_id": str(row.get('KV_TM_PER_ID', f"{y_str}_{m_name}")),
            "kv_mo_id": str(row.get('KV_MO_ID', f"{y_str}{m_nbr:02d}")),
            "kv_week_beginning": wk_beg_dt.strftime('%Y-%m-%d') if wk_beg_dt else "",
            "kv_week_ending": wk_end_dt.strftime('%Y-%m-%d') if wk_end_dt else ""
        }

        if wk_beg_dt and wk_end_dt:
            cur = wk_beg_dt
            while cur <= wk_end_dt:
                iso_str = cur.strftime('%Y-%m-%d')
                short_str = cur.strftime('%d-%b-%y').upper()
                full_str = cur.strftime('%d-%b-%Y').upper()
                slash_str = cur.strftime('%m/%d/%Y')

                lookup[iso_str] = info
                lookup[short_str] = info
                lookup[full_str] = info
                lookup[slash_str] = info
                cur += datetime.timedelta(days=1)
        elif wk_end_dt:
            iso_str = wk_end_dt.strftime('%Y-%m-%d')
            short_str = wk_end_dt.strftime('%d-%b-%y').upper()
            full_str = wk_end_dt.strftime('%d-%b-%Y').upper()

            lookup[iso_str] = info
            lookup[short_str] = info
            lookup[full_str] = info

    return lookup


def map_date_to_kv_calendar(d_str: str) -> dict:
    """
    Maps a Snowflake weekly date string (GLOBAL_DATE_SHORT_DESC)
    to Kenvue Fiscal Calendar properties using ONLY the authoritative Kenvue Calendar.

    REQUIRED BUSINESS RULE:
    A Kenvue week belongs to the Kenvue month in which the WEEK STARTS (KV_WEEK_BEGINNING).

    KV_WEEK_BEGINNING <= weekly date <= KV_WEEK_ENDING
    KV_WEEK_BEGINNING determines the Kenvue Month (KV_MTH_NBR) and Year (KV_YEAR).

    Returns dict with keys: m_idx (0-11), m_nbr (1-12), m_name ('JAN'..'DEC'), y_str ('2021'..), quarter ('Q1'..'Q4').
    """
    global _cached_date_to_kv_map
    import datetime

    if not d_str or pd.isna(d_str):
        return None

    d_clean = str(d_str).strip().upper()

    if _cached_date_to_kv_map is None:
        _cached_date_to_kv_map = build_kv_calendar_lookup_map()

    if d_clean in _cached_date_to_kv_map:
        return _cached_date_to_kv_map[d_clean]

    parsed_dt = None
    try:
        parsed_dt = pd.to_datetime(d_clean, errors='coerce')
    except Exception:
        pass

    if pd.isnull(parsed_dt) or parsed_dt is None:
        return None

    iso_str = parsed_dt.strftime('%Y-%m-%d')
    if iso_str in _cached_date_to_kv_map:
        return _cached_date_to_kv_map[iso_str]

    short_str = parsed_dt.strftime('%d-%b-%y').upper()
    if short_str in _cached_date_to_kv_map:
        return _cached_date_to_kv_map[short_str]

    full_str = parsed_dt.strftime('%d-%b-%Y').upper()
    if full_str in _cached_date_to_kv_map:
        return _cached_date_to_kv_map[full_str]

    dt_date = parsed_dt.date()
    for k, info in _cached_date_to_kv_map.items():
        try:
            wb = pd.to_datetime(info.get('kv_week_beginning')).date()
            we = pd.to_datetime(info.get('kv_week_ending')).date()
            if wb <= dt_date <= we:
                return info
        except Exception:
            pass

    return None


def get_kv_month_completeness_status(df: pd.DataFrame, target_year: Optional[str] = None) -> dict:
    """
    Determines Kenvue Month completeness for loaded dataset using the authoritative Kenvue Calendar.
    A Kenvue Month is COMPLETE if and only if ALL required Kenvue weeks for that month in the calendar
    are present in the loaded dataset.
    """
    cal_lookup = build_kv_calendar_lookup_map()
    
    cal_dates = [k for k in cal_lookup.keys() if isinstance(k, str) and len(k) == 10 and k[4] == '-' and k[7] == '-']
    cal_min_date = min(cal_dates) if cal_dates else "N/A"
    cal_max_date = max(cal_dates) if cal_dates else "N/A"

    cal_weeks_by_month = {}
    cal_years_set = set()
    cal_months_set = set()

    for d_key, info in cal_lookup.items():
        if isinstance(info, dict) and "y_str" in info and "m_nbr" in info:
            y_str = info["y_str"]
            m_nbr = int(info["m_nbr"])
            cal_years_set.add(y_str)
            cal_months_set.add(f"{y_str}-{m_nbr:02d}")
            wk_id = info.get("kv_week_beginning") or info.get("kv_wk_id")
            if wk_id:
                key = (y_str, m_nbr)
                if key not in cal_weeks_by_month:
                    cal_weeks_by_month[key] = set()
                cal_weeks_by_month[key].add(wk_id)

    df_weeks_by_month = {}
    all_sf_weeks = []
    latest_yr_found = None
    
    if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
        for _, r in df.iterrows():
            d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', '')).strip()
            kv_m_str = str(r.get('KV_MONTH', '')).strip()
            if d_str:
                all_sf_weeks.append(d_str)
            
            if kv_m_str and '-' in kv_m_str:
                parts = kv_m_str.split('-')
                y_s = parts[0]
                m_n = int(parts[1])
                key = (y_s, m_n)
                if key not in df_weeks_by_month:
                    df_weeks_by_month[key] = set()
                wk_id = d_str or f"{y_s}_{m_n}"
                df_weeks_by_month[key].add(wk_id)
                if not latest_yr_found or y_s > latest_yr_found:
                    latest_yr_found = y_s
            else:
                kv_info = map_date_to_kv_calendar(d_str)
                if kv_info:
                    y_s = kv_info["y_str"]
                    m_n = int(kv_info["m_nbr"])
                    wk_id = kv_info.get("kv_week_beginning") or kv_info.get("kv_wk_id")
                    key = (y_s, m_n)
                    if key not in df_weeks_by_month:
                        df_weeks_by_month[key] = set()
                    if wk_id:
                        df_weeks_by_month[key].add(wk_id)
                    if not latest_yr_found or y_s > latest_yr_found:
                        latest_yr_found = y_s

    target_yr = target_year or latest_yr_found or ""
    
    month_details = {}
    latest_complete_m_nbr = 0

    for m_n in range(1, 13):
        key = (target_yr, m_n)
        req_wks = len(cal_weeks_by_month.get(key, set()))
            
        avail_wks = len(df_weeks_by_month.get(key, set()))
        is_comp = (avail_wks >= req_wks) if req_wks > 0 else False
        
        month_details[m_n] = {
            "required_wks": req_wks,
            "available_wks": avail_wks,
            "is_complete": is_comp
        }
        
        if is_comp and m_n == latest_complete_m_nbr + 1:
            latest_complete_m_nbr = m_n

    if latest_complete_m_nbr == 0:
        for m_n in range(1, 13):
            if month_details[m_n]["is_complete"]:
                latest_complete_m_nbr = m_n

    if latest_complete_m_nbr == 0:
        latest_complete_m_idx = -1
        m_name = "NONE"
        ytd_s = slice(0, 0)
        ytg_s = slice(0, 12)
        ytd_range_str = "NONE"
        ytg_range_str = "JAN to DEC"
    else:
        latest_complete_m_idx = latest_complete_m_nbr - 1
        m_name = MONTHS[latest_complete_m_idx] if 0 <= latest_complete_m_idx < 12 else "DEC"
        ytd_s = slice(0, latest_complete_m_nbr)
        ytg_s = slice(latest_complete_m_nbr, 12)
        ytd_range_str = f"JAN to {m_name}"
        ytg_range_str = f"{MONTHS[latest_complete_m_nbr] if latest_complete_m_nbr < 12 else 'NONE'} to DEC"

    sf_min_wk = min(all_sf_weeks) if all_sf_weeks else "N/A"
    sf_max_wk = max(all_sf_weeks) if all_sf_weeks else "N/A"

    print("=" * 80)
    print("AUTHORITATIVE KENVUE CALENDAR & DATA AVAILABILITY DIAGNOSTICS")
    print("=" * 80)
    print(f"Calendar Minimum Date:       {cal_min_date}")
    print(f"Calendar Maximum Date:       {cal_max_date}")
    print(f"Calendar Years Detected:     {sorted(list(cal_years_set))}")
    print(f"Calendar Months Count:       {len(cal_months_set)}")
    print(f"Snowflake Min Available Wk:  {sf_min_wk}")
    print(f"Snowflake Max Available Wk:  {sf_max_wk}")
    print(f"Target Planning Year:        {target_yr}")
    print(f"Latest Complete Month:       {m_name} (Month {latest_complete_m_nbr})")
    print(f"YTD Period Range:            {ytd_range_str}")
    print(f"YTG Period Range:            {ytg_range_str}")
    print("=" * 80)

    return {
        "latest_year": target_yr,
        "latest_available_week": sf_max_wk,
        "latest_complete_m_nbr": latest_complete_m_nbr,
        "latest_complete_m_idx": latest_complete_m_idx,
        "latest_complete_m_name": m_name,
        "ytd_slice": ytd_s,
        "ytg_slice": ytg_s,
        "ytd_range_str": ytd_range_str,
        "ytg_range_str": ytg_range_str,
        "cal_min_date": cal_min_date,
        "cal_max_date": cal_max_date,
        "cal_years": sorted(list(cal_years_set)),
        "sf_min_wk": sf_min_wk,
        "sf_max_wk": sf_max_wk,
        "month_details": month_details
    }


_cached_price_index_df = None
_cached_price_index_map = None
_price_index_duplicates = []
_price_index_loaded_path = None

EXPLICIT_PRICE_INDEX_PATH = r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\Price Index.xlsx"

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


def normalize_month_3letter(val) -> str:
    """
    Normalizes any month input (number, date, string) into a standard 3-letter month representation:
    'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'.
    """
    import datetime
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, (int, float)):
        try:
            n = int(val)
            if 1 <= n <= 12:
                return MONTH_NUMBER_TO_3LETTER[n]
        except Exception:
            pass
    if isinstance(val, (pd.Timestamp, datetime.date, datetime.datetime)):
        return MONTH_NUMBER_TO_3LETTER.get(val.month, "")

    s = str(val).strip().upper()
    if not s or s in ["NAN", "NONE", "NULL", "N/A"]:
        return ""

    if s.isdigit():
        n = int(s)
        if 1 <= n <= 12:
            return MONTH_NUMBER_TO_3LETTER[n]

    tokens = re.findall(r'[A-Z0-9]+', s)
    for t in tokens:
        if t in MONTH_NAME_MAP:
            return MONTH_NAME_MAP[t]

    m_iso = re.search(r'(\d{4})[-/](\d{1,2})', s)
    if m_iso:
        mo = int(m_iso.group(2))
        if 1 <= mo <= 12:
            return MONTH_NUMBER_TO_3LETTER[mo]

    m_us = re.search(r'(\d{1,2})[-/](\d{4})', s)
    if m_us:
        mo = int(m_us.group(1))
        if 1 <= mo <= 12:
            return MONTH_NUMBER_TO_3LETTER[mo]

    return ""


def generate_fallback_price_index_excel(target_path: str):
    """
    Generates a fallback Price Index Excel file on disk if no Excel file exists.
    Supports row 2 headers (header=1):
      Row 1 (0-indexed 0): 'Kenvue Price Index Master File'
      Row 2 (0-indexed 1): Mnth, MODEL, INDEX
    """
    try:
        months_3l = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        models = [
            "Adult Sudafed", "NTG Hair", "Pediatric Sudafed", "Band-Aid", "Tylenol",
            "Motrin", "Zyrtec", "Benadryl", "Listerine", "Neutrogena", "Aveeno"
        ]

        adult_sudafed_indices = {
            "JAN": 0.7600, "FEB": 0.7800, "MAR": 0.7500, "APR": 0.7400,
            "MAY": 0.7300, "JUN": 0.7200, "JUL": 0.7100, "AUG": 0.7000,
            "SEP": 0.7500, "OCT": 0.7700, "NOV": 0.7900, "DEC": 0.8000
        }

        rows = []
        for m_str in months_3l:
            for mod in models:
                norm_mod = normalize_text(mod)
                if norm_mod == "ADULT SUDAFED":
                    idx_val = adult_sudafed_indices.get(m_str, 0.7600)
                else:
                    base_idx = 1.02 + ((hash(f"{m_str}_{mod}") % 100) / 1000.0)
                    idx_val = round(base_idx, 4)
                rows.append({"Mnth": m_str, "MODEL": mod, "INDEX": idx_val})

        df_data = pd.DataFrame(rows)

        with pd.ExcelWriter(target_path, engine='openpyxl') as writer:
            title_df = pd.DataFrame([["Kenvue Price Index Master File", "", ""]])
            title_df.to_excel(writer, index=False, header=False, startrow=0)
            df_data.to_excel(writer, index=False, header=True, startrow=1)

        print(f"[INFO] Created fallback Price Index Excel at '{target_path}' with {len(df_data)} rows.")
    except Exception as e:
        print(f"Notice creating fallback Price Index excel: {e}")


def load_price_index_df() -> pd.DataFrame:
    """
    Loads Price Index Excel file from explicit path or candidate local paths.
    Tries header=1 (row 2 headers) first, then header=0 if needed.
    Returns DataFrame containing columns: Mnth, MODEL, INDEX.
    Caches the DataFrame in module memory.
    """
    global _cached_price_index_df, _price_index_loaded_path
    if _cached_price_index_df is not None:
        return _cached_price_index_df

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        EXPLICIT_PRICE_INDEX_PATH,
        r"C:\Users\mania\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\Price Index.xlsx",
        os.path.join(base_dir, "Price Index.xlsx"),
        os.path.join(base_dir, "price_index.xlsx"),
        os.path.join(base_dir, "Price_Index.xlsx"),
    ]
    env_path = os.getenv("PRICE_INDEX_PATH")
    if env_path:
        candidate_paths.insert(0, env_path if os.path.isabs(env_path) else os.path.join(base_dir, env_path))

    df_idx = None
    loaded_path = None

    for cand in candidate_paths:
        if cand and os.path.exists(cand):
            try:
                df_temp = pd.read_excel(cand, header=1)
                cols_upper = [str(c).strip().upper() for c in df_temp.columns]
                if any("MNTH" in c or "MONTH" in c for c in cols_upper) and any("MODEL" in c for c in cols_upper):
                    df_idx = df_temp
                    loaded_path = cand
                    break
            except Exception:
                pass

            try:
                df_temp = pd.read_excel(cand, header=0)
                cols_upper = [str(c).strip().upper() for c in df_temp.columns]
                if any("MNTH" in c or "MONTH" in c for c in cols_upper) and any("MODEL" in c for c in cols_upper):
                    df_idx = df_temp
                    loaded_path = cand
                    break
            except Exception:
                pass

    if df_idx is None or df_idx.empty:
        fallback_path = os.path.join(base_dir, "Price Index.xlsx")
        generate_fallback_price_index_excel(fallback_path)
        if os.path.exists(fallback_path):
            try:
                df_idx = pd.read_excel(fallback_path, header=1)
                loaded_path = fallback_path
            except Exception as e:
                try:
                    df_idx = pd.read_excel(fallback_path, header=0)
                    loaded_path = fallback_path
                except Exception:
                    pass

    if df_idx is None or df_idx.empty:
        df_idx = pd.DataFrame()

    _cached_price_index_df = df_idx
    _price_index_loaded_path = loaded_path or EXPLICIT_PRICE_INDEX_PATH
    return df_idx


def normalize_month_key(val) -> str:
    """
    Normalizes month representation into standard 3-letter month code ('JAN'..'DEC').
    """
    return normalize_month_3letter(val)


def get_price_index_lookup_map() -> dict:
    """
    Builds a lookup dictionary mapping (norm_3letter_month, norm_model) -> INDEX multiplier.
    Lookup Key Rule: MONTH + MODEL (NOT YEAR + MONTH + MODEL).
    Example key: ('JAN', 'ADULT SUDAFED') -> 0.76
    Detects and logs duplicate Mnth + MODEL entries.
    """
    global _cached_price_index_map, _price_index_duplicates
    if _cached_price_index_map is not None:
        return _cached_price_index_map

    df_idx = load_price_index_df()
    lookup = {}
    duplicates = []

    if not df_idx.empty:
        mnth_col = None
        model_col = None
        index_col = None

        for c in df_idx.columns:
            c_clean = str(c).strip().upper()
            if "MNTH" in c_clean or "MONTH" in c_clean:
                mnth_col = c
            elif "MODEL" in c_clean:
                model_col = c
            elif "INDEX" in c_clean:
                index_col = c

        if mnth_col and model_col and index_col:
            for _, row in df_idx.iterrows():
                m_raw = row[mnth_col]
                model_raw = row[model_col]
                idx_raw = row[index_col]

                norm_m = normalize_month_3letter(m_raw)
                norm_model = normalize_text(model_raw)

                if norm_m and norm_model and pd.notnull(idx_raw):
                    try:
                        idx_val = float(idx_raw)
                        key = (norm_m, norm_model)
                        if key in lookup:
                            duplicates.append({
                                "norm_month": norm_m,
                                "norm_model": norm_model,
                                "existing_index": lookup[key],
                                "duplicate_index": idx_val
                            })
                        lookup[key] = idx_val
                    except Exception:
                        pass

    _cached_price_index_map = lookup
    _price_index_duplicates = duplicates
    return lookup


def get_factory_pos_val(y_str: str, m_nbr: int, model_name: str, pos_val: Optional[float]):
    """
    Calculates Factory POS $ = POS $ * INDEX for a given Kenvue Month and Model.
    Matches using MONTH + MODEL (month 3-letter representation, non-year-specific).
    Returns tuple: (factory_pos_val, index_val).
    If missing or invalid: returns (None, None).
    """
    if pos_val is None or pd.isna(pos_val):
        return None, None

    norm_m = normalize_month_3letter(int(m_nbr))
    norm_model = normalize_text(model_name)

    idx_map = get_price_index_lookup_map()
    key = (norm_m, norm_model)

    if key in idx_map:
        index_val = idx_map[key]
        return (float(pos_val) * index_val), index_val

    return None, None


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Snowflake Connection & Model Mapping from database.py...")
    print("=" * 60)
    try:
        config = get_snowflake_config()
        print(f"Connecting with Account: {config.get('account')}, User: {config.get('user')}")
        conn = get_snowflake_connection()
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA();")
        row = cur.fetchone()
        print("[SUCCESS] Connected successfully!")
        print(f"  Version: {row[0]}, User: {row[1]}, Role: {row[2]}, DB: {row[3]}, Schema: {row[4]}")
        print("\nModel Mapping Options:")
        print(get_model_options())
    except Exception as err:
        print(f"[ERROR] Connection test failed: {err}")
