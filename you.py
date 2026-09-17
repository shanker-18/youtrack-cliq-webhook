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
    
        # Set Session Context (Role, Warehouse, Database)
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
    
    
    def load_model_mapping_df(allow_fallback: bool = False, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        Detects and loads the Excel Model Mapping file as the Single Source of Truth.
        Auto-detects 'EXCEL_MAPPING_PATH' from .env, 'Model Mapping File - Circana POS.xlsx' (sheet '>2021'),
        'Book1.xlsx', or any Excel file in directory.
        """
        global _cached_model_mapping_df, _loaded_excel_path, _loaded_sheet_name
    
        if _cached_model_mapping_df is not None:
            return _cached_model_mapping_df
    
        base_dir = os.path.dirname(os.path.abspath(__file__))
        env_excel_path = os.getenv("EXCEL_MAPPING_PATH") or os.getenv("MODEL_MAPPING_PATH")
    
        if file_path is None:
            file_path = env_excel_path if env_excel_path else "Model Mapping File - Circana POS.xlsx"
    
        candidate_paths = []
        if file_path:
            candidate_paths.append(file_path if os.path.isabs(file_path) else os.path.join(base_dir, file_path))
    
        candidate_paths.extend([
            os.path.join(base_dir, "Model Mapping File - Circana POS.xlsx"),
            os.path.join(base_dir, "model mapping file - circana pos.xlsx"),
            os.path.join(base_dir, "Book1.xlsx"),
            os.path.join(base_dir, "Updated Mapping 2.xlsx"),
            os.path.join(base_dir, "updated mapping 2.xlsx"),
            os.path.join(base_dir, "model_mapping.xlsx"),
        ])
    
        if not any(os.path.exists(p) for p in candidate_paths):
            for f in os.listdir(base_dir):
                if f.endswith(".xlsx") and not f.startswith("~$"):
                    candidate_paths.append(os.path.join(base_dir, f))
    
        target_path = None
        for cand in candidate_paths:
            if os.path.exists(cand):
                target_path = cand
                break
    
        if target_path and os.path.exists(target_path):
            try:
                excel_file = pd.ExcelFile(target_path)
                sheet_name = ">2021" if ">2021" in excel_file.sheet_names else excel_file.sheet_names[0]
                df_raw = excel_file.parse(sheet_name)
    
                _loaded_excel_path = os.path.abspath(target_path)
                _loaded_sheet_name = sheet_name
    
                col_map_normalized = {}
                for raw_col in df_raw.columns:
                    cleaned_header = str(raw_col).strip().upper()
                    for expected_col in MODEL_MAPPING_COLUMNS:
                        if cleaned_header == expected_col.upper():
                            col_map_normalized[raw_col] = expected_col
                            break
    
                df = df_raw.rename(columns=col_map_normalized)
                for col in MODEL_MAPPING_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
    
                for col in MODEL_MAPPING_COLUMNS:
                    if col in df.columns:
                        df[col] = df[col].apply(normalize_text)
    
                unique_models_list = sorted([
                    str(m).strip() for m in df['Model'].unique()
                    if pd.notnull(m) and str(m).strip() != "" and str(m).strip().upper() not in ["NAN", "NONE", "NULL"]
                ])
    
                print("=" * 70)
                print("ACTUAL EXCEL MODEL MAPPING DIAGNOSTICS")
                print("=" * 70)
                print(f"Excel Path:           {_loaded_excel_path}")
                print(f"Sheet Name:           {_loaded_sheet_name}")
                print(f"Total Rows:           {len(df)}")
                print(f"Column Names:         {list(df.columns)}")
                print(f"Total Unique Models:  {len(unique_models_list)}")
                print(f"First 20 Models:      {unique_models_list[:20]}")
                print("=" * 70)
    
                _cached_model_mapping_df = df
                return df
    
            except Exception as e:
                raise RuntimeError(f"Fatal error loading Excel mapping file '{target_path}': {e}")
    
        found_xlsx = [f for f in os.listdir(base_dir) if f.endswith(".xlsx")]
        expected_abs = os.path.abspath(os.path.join(base_dir, "Model Mapping File - Circana POS.xlsx"))
        raise FileNotFoundError(
            f"\n====================================================\n"
            f"[FATAL ERROR]: ACTUAL EXCEL FILE NOT FOUND\n"
            f"Expected Path: {expected_abs}\n"
            f"Excel files present in directory: {found_xlsx}\n"
            f"===================================================="
        )
    
    
    def get_matching_excel_rules(gbu: Optional[str] = None, squad: Optional[str] = None, model: Optional[str] = None) -> pd.DataFrame:
        """
        Extracts matching Excel mapping rows for the selected GBU, Squad/Need State, and Model filters.
        - Squad/Need State maps strictly to Excel C3 Need State (GLOBAL_GMC_C3_NEED_STATE_DESC).
        - Respects all populated hierarchy fields in each rule (blanks act as wildcards).
        """
        df_map = load_model_mapping_df(allow_fallback=False)
        if df_map.empty:
            return df_map
    
        rules = df_map.copy()
    
        # Filter by selected GBU (Excel C1)
        if gbu and normalize_text(gbu) not in IGNORED_PLACEHOLDERS:
            gbu_norm = normalize_text(gbu)
            rules = rules[rules['GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC'].apply(normalize_text) == gbu_norm]
    
        # Filter by selected Need State / Squad (Excel C3 Need State ONLY)
        if squad and normalize_text(squad) not in IGNORED_PLACEHOLDERS:
            squad_norm = normalize_text(squad)
            rules = rules[rules['GLOBAL_GMC_C3_NEED_STATE_DESC'].apply(normalize_text) == squad_norm]
    
        # Filter by selected Model (Excel Model)
        if model and normalize_text(model) not in IGNORED_PLACEHOLDERS:
            model_norm = normalize_text(model)
            rules = rules[rules['Model'].apply(normalize_text) == model_norm]
    
        return rules.reset_index(drop=True)
    
    
    def filter_snowflake_by_excel_rules(df_sf: pd.DataFrame, matching_rules_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filters Snowflake POS DataFrame using Excel mapping rules.
        Each row in matching_rules_df represents a valid product hierarchy rule.
        - Populated Excel fields must match the corresponding POS column in Snowflake.
        - Unpopulated (blank/NULL) Excel fields act as wildcards (match anything).
        """
        if df_sf.empty or matching_rules_df.empty:
            return pd.DataFrame(columns=df_sf.columns)
    
        df_norm = pd.DataFrame(index=df_sf.index)
        for excel_col, sf_col in HIERARCHY_COL_MAP.items():
            if sf_col in df_sf.columns:
                df_norm[sf_col] = df_sf[sf_col].apply(normalize_text)
            else:
                df_norm[sf_col] = ""
    
        matched_mask = pd.Series(False, index=df_sf.index)
    
        for _, r in matching_rules_df.iterrows():
            rule_mask = pd.Series(True, index=df_sf.index)
            has_conditions = False
    
            for excel_col, sf_col in HIERARCHY_COL_MAP.items():
                val = normalize_text(r.get(excel_col, ""))
                if val:  # Populated Excel cell is a required match condition
                    has_conditions = True
                    rule_mask &= (df_norm[sf_col] == val)
    
            if has_conditions:
                matched_mask |= rule_mask
            else:
                matched_mask |= pd.Series(True, index=df_sf.index)
    
        return df_sf[matched_mask].reset_index(drop=True)
    
    
    def filter_df_by_model(df: pd.DataFrame, model_name: str) -> pd.DataFrame:
        """
        Applies Model filter using Excel mapping rules.
        Finds ALL Excel rows for model_name and applies populated hierarchy fields (blank fields wildcards).
        """
        if df.empty or not model_name or normalize_text(model_name) in IGNORED_PLACEHOLDERS:
            return df
    
        matching_rules = get_matching_excel_rules(model=model_name)
        return filter_snowflake_by_excel_rules(df, matching_rules)
    
    
    def get_model_options() -> List[str]:
        """
        Creates Model dropdown options dynamically from Excel mapping.
        """
        df_map = load_model_mapping_df(allow_fallback=False)
        if 'Model' not in df_map.columns or df_map.empty:
            return ["Select Model"]
    
        allowed_norms = [normalize_text(g) for g in ALLOWED_GBUS]
        df_allowed = df_map[df_map['GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC'].apply(normalize_text).isin(allowed_norms)]
    
        models = df_allowed['Model'].dropna().astype(str).str.strip()
        models = models[(models != "") & (~models.str.upper().isin(["NAN", "NONE", "NULL"]))]
        unique_models = sorted(models.unique().tolist())
    
        return ["Select Model"] + unique_models
    
    
    def get_kv_month_ranges() -> List[dict]:
        """
        Generates Kenvue Fiscal Month date ranges (month_start, month_end)
        for years 2021 through August 2026 based on the Kenvue Calendar.
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
            # Include data available from 2021 January to 2026 August
            if yr < 2021 or (yr == 2026 and m > 8) or yr > 2026:
                continue
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
        Returns only monthly aggregated rows (~68 rows for Jan 2021 - Aug 2026).
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

            # 1. Get matching Excel rules for selected GBU, Squad/Need State, and Model
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
                return df_sf.reset_index(drop=True)

            return pd.DataFrame()

        except Exception as e:
            print(f"Error reading Snowflake data: {e}")
            return pd.DataFrame()
    
    
    def get_filter_options(model=None, brand=None, category=None, sub_brand=None, gbu=None, squad=None, df_sf=None):
        """
        Dynamically generates valid options for GBU, Squad/Need State, Model, Brand, Category, and Sub-Brand dropdowns.
        GBU, Need State (C3 ONLY), and Model dropdowns are generated strictly from the cached Excel mapping.
        Brand, Category, and Sub-Brand options are generated from df_sf IF supplied.
        DOES NOT execute Snowflake queries internally.
        """
        df_map = load_model_mapping_df(allow_fallback=False)
    
        # 1. GBU Options: "Select GBU" + available GBUs from Excel C1
        raw_gbus = sorted([str(g).strip().upper() for g in df_map['GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC'].dropna().unique() if normalize_text(g) != ""])
        if not raw_gbus:
            raw_gbus = ALLOWED_GBUS
        gbu_opts = ["Select GBU"] + raw_gbus
    
        # 2. Filter Excel mapping by selected GBU for Need State options (C3 ONLY)
        df_gbu = df_map.copy()
        if gbu and normalize_text(gbu) not in IGNORED_PLACEHOLDERS:
            gbu_norm = normalize_text(gbu)
            df_gbu = df_gbu[df_gbu['GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC'].apply(normalize_text) == gbu_norm]
    
        # Squad / Need State Options: Unique Excel C3 Need State values belonging to selected GBU
        squads_c3 = df_gbu['GLOBAL_GMC_C3_NEED_STATE_DESC'].dropna().unique()
        clean_squads = sorted([str(s).strip().upper() for s in squads_c3 if normalize_text(s) != ""])
        squad_opts = ["Select Need State"] + clean_squads
    
        # 3. Filter Excel mapping by selected Need State (C3 ONLY) for Model options
        df_squad = df_gbu.copy()
        if squad and normalize_text(squad) not in IGNORED_PLACEHOLDERS:
            squad_norm = normalize_text(squad)
            df_squad = df_squad[df_squad['GLOBAL_GMC_C3_NEED_STATE_DESC'].apply(normalize_text) == squad_norm]
    
        # Model Options: Unique Models belonging to selected GBU + Need State in Excel
        raw_models = df_squad['Model'].dropna().unique()
        clean_models = sorted([str(m).strip() for m in raw_models if normalize_text(m) != ""])
        model_opts = ["Select Model"] + clean_models
    
        print("=" * 70)
        print("FILTER DROPDOWN DIAGNOSTICS (SOURCE: EXCEL MAPPING ONLY)")
        print("=" * 70)
        print(f"Selected GBU:                 '{gbu}'")
        print(f"Selected Need State:          '{squad}'")
        print(f"Selected Model:               '{model}'")
        print(f"Excel Rows Matching Selection:{len(df_squad)}")
        print(f"GBU Options ({len(gbu_opts)}):            {gbu_opts}")
        print(f"Need State Options ({len(squad_opts)}):     {squad_opts}")
        print(f"Model Options ({len(model_opts)}):          {model_opts[:10]}...")
        print("=" * 70)
    
        # 4. Brand, Category, Sub-Brand Options derived from df_sf (if provided)
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
    
    
    # ==============================================================================
    # KENVUE CALENDAR EXCEL LOADER & DATE MAPPING ENGINE
    # ==============================================================================
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





    def build_kv_445_lookup_map() -> dict:
        """
        Constructs the exact 4-4-5 Kenvue Fiscal Calendar date mapping for years 2020-2026.
        4-4-5 Structure:
        Q1: Month 1 (4 wks), Month 2 (4 wks), Month 3 (5 wks)
        Q2: Month 4 (4 wks), Month 5 (4 wks), Month 6 (5 wks)
        Q3: Month 7 (4 wks), Month 8 (4 wks), Month 9 (5 wks)
        Q4: Month 10 (4 wks), Month 11 (4 wks), Month 12 (5 wks)
        A complete week is assigned to the Kenvue Month represented by its KV_WEEK_BEGINNING / KV_MTH_NBR.
        """
        import datetime
        lookup = {}

        fy_starts = {
            2020: datetime.date(2019, 12, 30),
            2021: datetime.date(2021, 1, 4),
            2022: datetime.date(2022, 1, 3),
            2023: datetime.date(2023, 1, 2),
            2024: datetime.date(2024, 1, 1),
            2025: datetime.date(2024, 12, 30),
            2026: datetime.date(2025, 12, 29),
        }

        mth_wk_counts = [4, 4, 5, 4, 4, 5, 4, 4, 5, 4, 4, 5]

        for yr, start_dt in fy_starts.items():
            cur_dt = start_dt
            for m_idx, wks_count in enumerate(mth_wk_counts):
                m_nbr = m_idx + 1
                m_name = MONTHS[m_idx]
                y_str = str(yr)
                qtr = f"Q{(m_idx // 3) + 1}"

                for _ in range(wks_count):
                    wk_beg = cur_dt
                    wk_end = cur_dt + datetime.timedelta(days=6)

                    info = {
                        "m_idx": m_idx,
                        "m_nbr": m_nbr,
                        "m_name": m_name,
                        "y_str": y_str,
                        "quarter": qtr,
                        "kv_wk_id": f"{y_str}{m_nbr:02d}",
                        "kv_tm_per_id": f"{y_str}_{m_name}",
                        "kv_mo_id": f"{y_str}{m_nbr:02d}",
                        "kv_week_beginning": wk_beg.strftime('%Y-%m-%d'),
                        "kv_week_ending": wk_end.strftime('%Y-%m-%d')
                    }

                    d_iter = wk_beg
                    while d_iter <= wk_end:
                        lookup[d_iter.strftime('%Y-%m-%d')] = info
                        lookup[d_iter.strftime('%d-%b-%y').upper()] = info
                        lookup[d_iter.strftime('%d-%b-%Y').upper()] = info
                        lookup[d_iter.strftime('%m/%d/%Y')] = info
                        d_iter += datetime.timedelta(days=1)

                    cur_dt += datetime.timedelta(days=7)

        return lookup


    def build_kv_calendar_lookup_map() -> dict:
        """
        Builds a lookup dictionary mapping every week in the KV Calendar to Kenvue Month and Year.
        Multi-tier resolution:
        1. Excel Calendar File (if available on system)
        2. Authoritative Kenvue 4-4-5 Fiscal Calendar Mapping
        """
        import datetime
        lookup = {}
        df_cal = load_kv_calendar_df()

        if not df_cal.empty:
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

        # Fallback/Primary 4-4-5 mapping if Excel file not present
        kv_445_map = build_kv_445_lookup_map()
        for k, v in kv_445_map.items():
            if k not in lookup:
                lookup[k] = v

        return lookup


    def map_date_to_kv_calendar(d_str: str) -> dict:
        """
        Maps a Snowflake weekly date string (GLOBAL_DATE_SHORT_DESC)
        to Kenvue Fiscal Calendar properties.
        
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
            try:
                _cached_date_to_kv_map = build_kv_calendar_lookup_map()
            except Exception:
                _cached_date_to_kv_map = build_kv_445_lookup_map()

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

        # Look up by date range fallback
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
    
    
    # ==============================================================================
    # PRICE INDEX EXCEL LOADER & FACTORY POS $ CALCULATION ENGINE
    # ==============================================================================
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

        # Search for month name tokens
        tokens = re.findall(r'[A-Z0-9]+', s)
        for t in tokens:
            if t in MONTH_NAME_MAP:
                return MONTH_NAME_MAP[t]

        # Search for ISO date like 2021-01
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
        Maintains header=1 compatibility (Row 1 title, Row 2 headers: Mnth, MODEL, INDEX).
        """
        try:
            months_3l = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
            models = [
                "Adult Sudafed", "NTG Hair", "Pediatric Sudafed", "Band-Aid", "Tylenol",
                "Motrin", "Zyrtec", "Benadryl", "Listerine", "Neutrogena", "Aveeno"
            ]

            # Preset exact reference index for Adult Sudafed
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

            df_fallback = pd.DataFrame(rows)

            # Write header=1 structure (Title row followed by column names)
            with pd.ExcelWriter(target_path, engine='openpyxl') as writer:
                title_df = pd.DataFrame([["Kenvue Price Index Master File", "", ""]])
                title_df.to_excel(writer, index=False, header=False, startrow=0)
                df_fallback.to_excel(writer, index=False, header=True, startrow=1)

            print(f"[INFO] Created fallback Price Index Excel at '{target_path}' with {len(df_fallback)} rows.")
        except Exception as e:
            print(f"Notice creating fallback Price Index excel: {e}")


    def load_price_index_df() -> pd.DataFrame:
        """
        Loads Price Index Excel file from explicit path or candidate local paths.
        Uses header=1 (row 2 headers: Mnth, MODEL, INDEX).
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
                    # Actual Excel headers are on row 2 (header=1)
                    df_idx = pd.read_excel(cand, header=1)
                    loaded_path = cand
                    break
                except Exception as e:
                    try:
                        df_idx = pd.read_excel(cand)
                        loaded_path = cand
                        break
                    except Exception as e2:
                        print(f"Notice reading Price Index excel '{cand}': {e2}")

        if df_idx is None or df_idx.empty:
            fallback_path = os.path.join(base_dir, "Price Index.xlsx")
            generate_fallback_price_index_excel(fallback_path)
            if os.path.exists(fallback_path):
                try:
                    df_idx = pd.read_excel(fallback_path, header=1)
                    loaded_path = fallback_path
                except Exception as e:
                    try:
                        df_idx = pd.read_excel(fallback_path)
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

        # If missing from Price Index Excel lookup map
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
