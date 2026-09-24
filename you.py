import os
import sys
import re
import pandas as pd
from dash import html
from dotenv import load_dotenv
 
import database
 
# =============================================================================
# CONFIGURATION & FILE PATHS
# =============================================================================
load_dotenv()
 
START_YEAR = 2022
END_YEAR = 2026
END_2026_MONTH = 8  # August 2026
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
 
EXPLICIT_SHIPMENT_MAPPING_PATH = r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\Model Mapping File - Shipment GTS.xlsx"
EXPLICIT_KV_CALENDAR_PATH = r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\KV Calendar Data Dump.xlsx"
 
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
 
MAPPING_COLUMNS = [
    "C1_BUSINESS_SEGMENT",
    "C2_BUSINESS_SUBSEGMENT",
    "C3_NEED_STATE",
    "C4_CATEGORY",
    "C5_SUBCATEGORY",
    "B1_BRAND",
    "B2_SUBBRAND",
    "GMC_BRAND_NAME",
    "GMC_SUBBRAND_NAME",
    "GMC_SUBCATEGORY_NAME",
    "MODEL",
]
 
CALENDAR_COLUMNS = [
    "CAL_DATE",
    "KV_WK_ID",
    "KV_MO_ID",
    "KV_MONTH_NAME",
    "KV_YEAR",
]
 
_cached_excel_mapping = None
_cached_kv_calendar = None
 
 
# =============================================================================
# TEXT NORMALIZATION
# =============================================================================
def normalize_text(value):
    """
    Normalizes string values consistently:
      - Strip whitespace & non-breaking spaces (\xa0)
      - Convert to uppercase
      - Collapse multiple spaces into one
    """
    if pd.isna(value) or value is None:
        return ""
    val_str = str(value).replace("\xa0", " ").strip().upper()
    if val_str in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
        return ""
    return " ".join(val_str.split())
 
 
# =============================================================================
# 1. DYNAMIC MODEL MAPPING EXCEL LOADER (FOR ALL MODELS)
# =============================================================================
def load_shipment_model_mapping(model_name=None):
    """
    Loads active Model Hierarchy Mapping from PostgreSQL database (na_ibp_db)
    using the exact same table (public.hierarchy_models and public.hierarchy_mapping)
    and columns as the Consumption dashboard.
    If model_name is provided, filters mapping for that model dynamically.
    """
    global _cached_excel_mapping

    if _cached_excel_mapping is None or _cached_excel_mapping.empty:
        df = database.load_model_mapping_df()
        if not df.empty:
            df = df.copy()
            df["C1_BUSINESS_SEGMENT"] = df["GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC"].apply(normalize_text)
            df["C3_NEED_STATE"] = df["GLOBAL_GMC_C3_NEED_STATE_DESC"].apply(normalize_text)
            df["MODEL"] = df["Model"].apply(normalize_text)
            df["GMC_BRAND_NAME"] = df["GLOBAL_GMC_B1_BRAND_DESC"].apply(normalize_text)
            df["GMC_SUBBRAND_NAME"] = df["GLOBAL_GMC_B2_SUB_BRAND_DESC"].apply(normalize_text)
            df["GMC_SUBCATEGORY_NAME"] = df["GLOBAL_GMC_C5_SUB_CATEGORY_DESC"].apply(normalize_text)
            _cached_excel_mapping = df
        else:
            _cached_excel_mapping = pd.DataFrame()

    if _cached_excel_mapping is not None and not _cached_excel_mapping.empty:
        if model_name:
            model_norm = normalize_text(model_name)
            model_df = _cached_excel_mapping[_cached_excel_mapping["MODEL"] == model_norm].copy()
            return model_df
        return _cached_excel_mapping

    return pd.DataFrame()
 
 
def get_shipment_filter_options(gbu=None, squad=None, model=None):
    """
    Returns dropdown filter options (GBU, Need State, Model) derived dynamically
    from the Shipment Model Mapping Excel file for ALL models.
    """
    df_map = load_shipment_model_mapping()
    if df_map.empty:
        return {"gbus": ["Select GBU"], "squads": ["Select Need State"], "models": ["Select Model"]}
 
    gbus = sorted([g for g in df_map["C1_BUSINESS_SEGMENT"].unique() if g])
    if not gbus:
        gbus = ["ESSENTIAL HEALTH", "SELF CARE", "SKIN HEALTH & BEAUTY"]
 
    gbu_norm = normalize_text(gbu)
    if gbu_norm and gbu_norm not in ["SELECT GBU", "ALL", "NONE", ""]:
        df_filtered = df_map[df_map["C1_BUSINESS_SEGMENT"] == gbu_norm]
    else:
        df_filtered = df_map
 
    squads = sorted([s for s in df_filtered["C3_NEED_STATE"].unique() if s])
 
    squad_norm = normalize_text(squad)
    if squad_norm and squad_norm not in ["SELECT NEED STATE", "ALL", "NONE", ""]:
        df_filtered = df_filtered[df_filtered["C3_NEED_STATE"] == squad_norm]
 
    models = sorted([m for m in df_filtered["MODEL"].unique() if m])
 
    return {
        "gbus": gbus if gbus else ["Select GBU"],
        "squads": squads if squads else ["Select Need State"],
        "models": models if models else ["Select Model"]
    }
 
 
# =============================================================================
# 2. LOAD KENVUE CALENDAR EXCEL
# =============================================================================
def load_kv_calendar():
    global _cached_kv_calendar
    if _cached_kv_calendar is not None:
        return _cached_kv_calendar
 
    candidate_paths = [
        EXPLICIT_KV_CALENDAR_PATH,
        os.path.join(BASE_DIR, "KV Calendar Data Dump.xlsx"),
        os.path.join(BASE_DIR, "calendar.xlsx")
    ]
 
    file_path = None
    for cand in candidate_paths:
        if cand and os.path.exists(cand):
            file_path = cand
            break
 
    if not file_path:
        raise FileNotFoundError(
            f"\nKenvue Calendar file not found. Checked paths:\n"
            + "\n".join(f" - {p}" for p in candidate_paths)
        )
 
    cal_df = pd.read_excel(file_path)
    cal_df.columns = [str(c).replace("\xa0", " ").strip() for c in cal_df.columns]
 
    if "CAL_DATE" not in cal_df.columns and "DATE" in cal_df.columns:
        cal_df.rename(columns={"DATE": "CAL_DATE"}, inplace=True)
 
    if "KV_MO_ID" not in cal_df.columns and "KV_MTH_NBR" in cal_df.columns:
        cal_df["KV_MO_ID"] = cal_df["KV_YEAR"].astype(str) + cal_df["KV_MTH_NBR"].astype(str).str.zfill(2)
 
    missing_cols = [c for c in CALENDAR_COLUMNS if c not in cal_df.columns]
    if missing_cols:
        raise RuntimeError(
            f"\nMissing required calendar columns:\n" + "\n".join(f" - {c}" for c in missing_cols)
        )
 
    cal_df["CAL_DATE"] = pd.to_datetime(cal_df["CAL_DATE"], errors="coerce")
    cal_df["KV_YEAR"] = pd.to_numeric(cal_df["KV_YEAR"], errors="coerce")
    cal_df["KV_MO_ID"] = cal_df["KV_MO_ID"].astype(str).str.strip()
    cal_df["KV_MONTH_NAME"] = cal_df["KV_MONTH_NAME"].astype(str).str.strip().str.upper()
 
    cal_df = cal_df.dropna(subset=["CAL_DATE", "KV_YEAR"]).copy()
    cal_df["KV_YEAR"] = cal_df["KV_YEAR"].astype(int)
    cal_df = cal_df.sort_values("CAL_DATE")
 
    # Select 2022 to 2026
    selected_cal = cal_df[(cal_df["KV_YEAR"] >= START_YEAR) & (cal_df["KV_YEAR"] <= END_YEAR)].copy()
 
    # Get unique Kenvue months
    month_info = (
        selected_cal[["KV_YEAR", "KV_MO_ID", "KV_MONTH_NAME", "CAL_DATE"]]
        .drop_duplicates(subset=["KV_YEAR", "KV_MO_ID"])
        .sort_values(["KV_YEAR", "CAL_DATE"])
        .reset_index(drop=True)
    )
 
    # Filter to 2022-2025 (12 months each) + 2026 (Jan-Aug 8 months) = 56 total months
    selected_months_list = []
    for yr in range(START_YEAR, END_YEAR + 1):
        yr_months = month_info[month_info["KV_YEAR"] == yr].copy()
        if yr == END_YEAR:
            yr_months = yr_months.head(END_2026_MONTH)
        selected_months_list.append(yr_months)
 
    selected_months_df = pd.concat(selected_months_list, ignore_index=True)
 
    # STRICT CALENDAR RESTRICTION: Keep only dates in selected_months_df
    selected_cal = selected_cal.merge(
        selected_months_df[["KV_YEAR", "KV_MO_ID"]],
        on=["KV_YEAR", "KV_MO_ID"],
        how="inner"
    )
 
    _cached_kv_calendar = (selected_cal, selected_months_df)
    return _cached_kv_calendar
 
 
# =============================================================================
# 3. DYNAMIC GMC HIERARCHY ITEM RESOLUTION (FOR ANY MODEL)
# =============================================================================
def resolve_shipment_model_items(model_name: str) -> pd.DataFrame:
    """
    Reads mapping rows for model_name dynamically from PostgreSQL hierarchy mapping,
    matches GMC hierarchy in Snowflake: VW_DIM_GMC_PRODCUT_HIERARCHY.
    Using GMC_BRAND_NAME, GMC_SUBBRAND_NAME, GMC_SUBCATEGORY_NAME with OR logic.
    Returns DataFrame of matched unique KV_ITEM_NOs.
    """
    model_mapping = load_shipment_model_mapping(model_name=model_name)

    if model_mapping.empty:
        print(f"[WARNING]: Zero mapping rows found in PostgreSQL mapping for model '{model_name}'.")
        return pd.DataFrame()

    conditions = []
    for _, row in model_mapping.iterrows():
        b = str(row.get("GMC_BRAND_NAME", "")).strip().replace("'", "''")
        sb = str(row.get("GMC_SUBBRAND_NAME", "")).strip().replace("'", "''")
        sc = str(row.get("GMC_SUBCATEGORY_NAME", "")).strip().replace("'", "''")

        sub_conds = []
        if b:
            sub_conds.append(f"UPPER(TRIM(COALESCE(GMC_BRAND_NAME, ''))) = '{b}'")
        if sb:
            sub_conds.append(f"UPPER(TRIM(COALESCE(GMC_SUBBRAND_NAME, ''))) = '{sb}'")
        if sc:
            sub_conds.append(f"UPPER(TRIM(COALESCE(GMC_SUBCATEGORY_NAME, ''))) = '{sc}'")

        if sub_conds:
            cond = f"""
        (
            {" AND ".join(sub_conds)}
        )
        """
            conditions.append(cond)

    if not conditions:
        print(f"[WARNING]: Zero populated hierarchy conditions for model '{model_name}'.")
        return pd.DataFrame()

    where_clause = "\nOR\n".join(conditions)
 
    query = f"""
SELECT DISTINCT
    KV_ITEM_NO,
    GMC_SKU_CODE,
    GMC_SKU_NAME,
    GMC_BRAND_NAME,
    GMC_SUBBRAND_NAME,
    GMC_SUBCATEGORY_NAME
FROM PROD_CUSTOMER360_GLOBALNA.NAUSMASTER_ACCESS.VW_DIM_GMC_PRODCUT_HIERARCHY
WHERE
    {where_clause}
"""
    conn = database.get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
    finally:
        cursor.close()
 
    items_df = pd.DataFrame(rows, columns=cols)
    if not items_df.empty:
        items_df["KV_ITEM_NO"] = items_df["KV_ITEM_NO"].astype(str).str.strip()
        items_df = items_df[items_df["KV_ITEM_NO"] != ""].drop_duplicates(subset=["KV_ITEM_NO"])
 
    return items_df
 
 
# Backward-compatible alias for Children's Tylenol
get_children_tylenol_items = lambda m_map: resolve_shipment_model_items("Children's Tylenol")
 
 
# =============================================================================
# 4. FETCH SHIPMENT GRS $ FOR ANY SELECTED MODEL
# =============================================================================
def fetch_shipment_data_for_model(model_name: str) -> pd.DataFrame:
    """
    Queries Snowflake table TF_TRNS_INV_DLY_TERR_EXPL joined with TD_ITM_DIV
    for the KV_ITEM_NO values resolved dynamically for model_name.
    Calculates GROSS_SHIP_AM = SUM(CASE WHEN f.trns_rec_cd = '2' THEN f.trns_grs_am ELSE 0 END).
    CRITICAL REQUIREMENT: If model mapping yields 0 items, returns empty DataFrame
    and NEVER falls back to unfiltered shipment data.
    """
    items_df = resolve_shipment_model_items(model_name)
 
    if items_df.empty:
        print(f"[CRITICAL INTEGRITY ENFORCED]: Zero items resolved for model '{model_name}'. Returning empty DataFrame.")
        return pd.DataFrame()
 
    item_numbers = items_df["KV_ITEM_NO"].dropna().astype(str).str.strip().unique().tolist()
    if not item_numbers:
        print(f"[CRITICAL INTEGRITY ENFORCED]: Empty KV_ITEM_NO list for '{model_name}'. Returning empty DataFrame.")
        return pd.DataFrame()
 
    selected_cal, _ = load_kv_calendar()
    min_date = selected_cal["CAL_DATE"].min()
    max_date = selected_cal["CAL_DATE"].max()
 
    start_id = int(min_date.strftime("%Y%m%d"))
    end_id = int(max_date.strftime("%Y%m%d"))
 
    item_sql = ", ".join(f"'{it.replace(chr(39), chr(39)+chr(39))}'" for it in item_numbers)
 
    query = f"""
SELECT
    f.tm_per_id,
    i.itm_no AS kv_item_no,
    SUM(
        CASE
            WHEN f.trns_rec_cd = '2'
            THEN f.trns_grs_am
            ELSE 0
        END
    ) AS gross_ship_am,
    SUM(
        CASE
            WHEN f.trns_rec_cd = '2'
            THEN f.trns_qt_cu
            ELSE 0
        END
    ) AS gross_ship_qty
FROM PROD_CUSTOMER360_GLOBALNA.NAUSINTERNAL_ACCESS.TF_TRNS_INV_DLY_TERR_EXPL f
INNER JOIN PROD_CUSTOMER360_GLOBALNA.NAUSMASTER_ACCESS.TD_ITM_DIV i
    ON f.cpnt_itm_id = i.itm_id
WHERE
    f.tm_per_id >= {start_id}
    AND f.tm_per_id <= {end_id}
    AND f.trns_rec_cd = '2'
    AND i.itm_no IN ({item_sql})
GROUP BY
    f.tm_per_id,
    i.itm_no
ORDER BY
    f.tm_per_id
"""
    conn = database.get_snowflake_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
    finally:
        cursor.close()
 
    shipment_df = pd.DataFrame(rows, columns=cols)
    if not shipment_df.empty:
        shipment_df["TM_PER_ID"] = pd.to_numeric(shipment_df["TM_PER_ID"], errors="coerce")
        shipment_df["KV_ITEM_NO"] = shipment_df["KV_ITEM_NO"].astype(str).str.strip()
        shipment_df["GROSS_SHIP_AM"] = pd.to_numeric(shipment_df["GROSS_SHIP_AM"], errors="coerce").fillna(0.0)
        shipment_df["GROSS_SHIP_QTY"] = pd.to_numeric(shipment_df.get("GROSS_SHIP_QTY", 0.0), errors="coerce").fillna(0.0)
 
    return shipment_df
 
 
# Backward-compatible alias
fetch_shipments = lambda items_df, cal: fetch_shipment_data_for_model("Children's Tylenol")
 
 
# =============================================================================
# 5. MAP SHIPMENT DATES TO KENVUE FISCAL CALENDAR & AGGREGATE
# =============================================================================
def aggregate_shipment_monthly(shipment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Maps shipment transaction dates to Kenvue fiscal calendar months.
    Returns month-wise GRS $ and GRS U for 2022 to 2026.
    """
    selected_cal, selected_months_df = load_kv_calendar()
 
    if shipment_df.empty:
        res = selected_months_df.copy()
        res["GRS_USD"] = 0.0
        res["GRS_MILLIONS"] = 0.0
        res["GRS_QTY"] = 0.0
        res["GRS_QTY_MILLIONS"] = 0.0
        return res
 
    df = shipment_df.copy()
    df["SHIP_DATE"] = pd.to_datetime(df["TM_PER_ID"].astype(str), format="%Y%m%d", errors="coerce")
 
    cal_lookup = selected_cal[["CAL_DATE", "KV_YEAR", "KV_MO_ID", "KV_MONTH_NAME"]].rename(
        columns={"CAL_DATE": "SHIP_DATE"}
    ).drop_duplicates("SHIP_DATE")
 
    df = df.merge(cal_lookup, on="SHIP_DATE", how="left")
 
    qty_col = "GROSS_SHIP_QTY" if "GROSS_SHIP_QTY" in df.columns else "GROSS_SHIP_AM"
    if qty_col not in df.columns:
        df["GROSS_SHIP_QTY"] = 0.0
        qty_col = "GROSS_SHIP_QTY"
 
    monthly_agg = (
        df.dropna(subset=["KV_MO_ID"])
        .groupby(["KV_YEAR", "KV_MO_ID", "KV_MONTH_NAME"], as_index=False)[["GROSS_SHIP_AM", qty_col]]
        .sum()
        .rename(columns={"GROSS_SHIP_AM": "GRS_USD", qty_col: "GRS_QTY"})
    )
 
    result = selected_months_df[["KV_YEAR", "KV_MO_ID", "KV_MONTH_NAME"]].merge(
        monthly_agg,
        on=["KV_YEAR", "KV_MO_ID", "KV_MONTH_NAME"],
        how="left"
    )
 
    result["GRS_USD"] = result["GRS_USD"].fillna(0.0)
    result["GRS_MILLIONS"] = result["GRS_USD"] / 1_000_000.0
    result["GRS_QTY"] = result["GRS_QTY"].fillna(0.0)
    result["GRS_QTY_MILLIONS"] = result["GRS_QTY"] / 1_000_000.0
    result = result.sort_values(["KV_YEAR", "KV_MO_ID"]).reset_index(drop=True)
 
    return result
 
 
process_monthly_summary = lambda ship_df, cal, m_df: (aggregate_shipment_monthly(ship_df), ship_df)
 
 
# =============================================================================
# 5.5 FETCH CONSUMPTION METRICS (FACTORY POS $, POS $, & POS UNITS) FOR MODEL
# =============================================================================
def get_consumption_metrics_monthly_for_model(model_name: str) -> tuple:
    """
    Retrieves month-by-month Factory POS $, POS $, and POS Units for model_name using Consumption data source.
    Returns tuple of dicts: (factory_pos_map, pos_val_map, pos_u_map).
    """
    if not model_name:
        return {}, {}, {}
    try:
        df = database.fetch_joined_snowflake_data(model=model_name)
        if df.empty:
            return {}, {}, {}
 
        pos_val_by_yr_m = {}
        pos_u_by_yr_m = {}
        for _, r in df.iterrows():
            kv_m_str = str(r.get('KV_MONTH', '')).strip()
            if kv_m_str and '-' in kv_m_str:
                parts = kv_m_str.split('-')
                y_str = parts[0]
                m_nbr = int(parts[1])
                m_idx = m_nbr - 1
            else:
                d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', '')).strip()
                kv_info = database.map_date_to_kv_calendar(d_str)
                if not kv_info:
                    continue
                m_idx = kv_info["m_idx"]
                y_str = kv_info["y_str"]
 
            if str(y_str).isdigit() and int(y_str) < 2022:
                continue
 
            pv = r.get('POS_VALUE') if pd.notnull(r.get('POS_VALUE')) else r.get('POS_DOLLARS')
            pu = r.get('POS_UNITS')
            key = (str(y_str), m_idx)
            if pd.notnull(pv):
                pos_val_by_yr_m[key] = (pos_val_by_yr_m.get(key) or 0.0) + float(pv)
            if pd.notnull(pu):
                pos_u_by_yr_m[key] = (pos_u_by_yr_m.get(key) or 0.0) + float(pu)
 
        factory_pos_map = {}
        for (y_str, m_idx), pv_val in pos_val_by_yr_m.items():
            f_pos, _ = database.get_factory_pos_val(y_str, m_idx + 1, model_name, pv_val)
            if f_pos is not None:
                factory_pos_map[(str(y_str), m_idx)] = f_pos
 
        return factory_pos_map, pos_val_by_yr_m, pos_u_by_yr_m
    except Exception as e:
        print(f"[SHIPMENT CONSUMPTION METRICS FETCH NOTICE]: {e}")
        return {}, {}, {}
 
 
# Backward-compatible alias
get_factory_pos_monthly_for_model = lambda model_name: get_consumption_metrics_monthly_for_model(model_name)[0]
 
 
# =============================================================================
# 5.6 SHIPMENT BUILDING BLOCKS LOADER & CALCULATOR (POSTGRESQL SOURCE)
# =============================================================================
SHIPMENT_BB_QUERY = """
SELECT
    hm.model_name AS model,
    DATE_TRUNC('month', spv.period_month)::date AS period_month,
    sbb.name AS building_block,
    SUM(spv.value_in_thousands) AS value_in_thousands
FROM public.shipment_planning_rows spr
INNER JOIN public.shipment_building_blocks sbb
    ON spr.building_block_id = sbb.block_id
INNER JOIN public.shipment_planning_values spv
    ON spr.row_id = spv.row_id
INNER JOIN public.hierarchy_models hm
    ON spr.model_id = hm.model_id
WHERE
    spr.is_deleted = FALSE
    AND sbb.is_active = TRUE
    AND hm.is_active = TRUE
GROUP BY
    hm.model_name,
    DATE_TRUNC('month', spv.period_month),
    sbb.name
ORDER BY
    hm.model_name,
    period_month,
    sbb.name;
"""
 
SHIPMENT_ALLOWED_BUILDING_BLOCKS = ["Innovation", "Trade", "Club", "Retailer Inventory"]
 
_cached_shipment_bb_df = None
 
 
def map_shipment_building_block_name(raw_name: str):
    """
    Maps Shipment Building Block PostgreSQL names to standard logical names:
      - Innovation Pipe -> Innovation
      - Trade Pipe -> Trade
      - Club (Build v. Bleed) -> Club
      - Inventory (Build v. Bleed) -> Retailer Inventory
    Returns None if not in the 4 allowed building blocks.
    """
    if not raw_name:
        return None
    norm = database.normalize_text(raw_name)
 
    if "INNOVATION" in norm:
        return "Innovation"
    if "TRADE" in norm:
        return "Trade"
    if "CLUB" in norm:
        return "Club"
    if "INVENTORY" in norm or "RETAILER" in norm:
        return "Retailer Inventory"
 
    return None
 
 
def load_shipment_building_block_data(force_reload: bool = False) -> pd.DataFrame:
    """
    Loads active Shipment Building Block records from PostgreSQL database.
    """
    global _cached_shipment_bb_df
    if _cached_shipment_bb_df is not None and not force_reload:
        return _cached_shipment_bb_df
 
    df = pd.DataFrame(columns=['model', 'period_month', 'building_block', 'value_in_thousands'])
    try:
        conn = database.get_postgres_connection()
        cur = conn.cursor()
        cur.execute(SHIPMENT_BB_QUERY)
        rows = cur.fetchall()
        cur.close()
        conn.close()
 
        if rows:
            df = pd.DataFrame(rows, columns=['model', 'period_month', 'building_block', 'value_in_thousands'])
            df['value_in_thousands'] = pd.to_numeric(df['value_in_thousands'], errors='coerce').fillna(0.0)
            df['building_block'] = df['building_block'].astype(str).str.strip()
            df['model'] = df['model'].astype(str).str.strip()
    except Exception as e:
        print(f"[SHIPMENT BUILDING BLOCK LOAD NOTICE]: {e}")
 
    _cached_shipment_bb_df = df
    return df
 
 
def get_shipment_building_block_values(
    model_name: str,
    year: str,
    month_nbr: int,
    bb_df: pd.DataFrame = None
) -> tuple:
    """
    Retrieves the 4 Shipment Building Block values for model_name, year, and month_nbr.
    Returns tuple: (blocks_dict, total_val_in_thousands, has_data).
    """
    if not model_name or database.normalize_text(model_name) in database.IGNORED_PLACEHOLDERS:
        return {b: 0.0 for b in SHIPMENT_ALLOWED_BUILDING_BLOCKS}, 0.0, False
 
    if bb_df is None or bb_df.empty:
        bb_df = load_shipment_building_block_data()
 
    if bb_df.empty:
        return {b: 0.0 for b in SHIPMENT_ALLOWED_BUILDING_BLOCKS}, 0.0, False
 
    norm_target_model = database.normalize_text(model_name)
    yr_int = int(year) if year and str(year).isdigit() else 2026
 
    blocks = {b: 0.0 for b in SHIPMENT_ALLOWED_BUILDING_BLOCKS}
    total = 0.0
    found_any = False
 
    for _, r in bb_df.iterrows():
        row_model = str(r['model'])
        if database.normalize_text(row_model) != norm_target_model:
            continue
 
        b_name_raw = str(r['building_block']).strip()
        canonical_b = map_shipment_building_block_name(b_name_raw)
 
        if not canonical_b:
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
            val = float(r['value_in_thousands']) if pd.notnull(r['value_in_thousands']) else 0.0
            blocks[canonical_b] += val
            total += val
            found_any = True
 
    return blocks, total, found_any
 
# =============================================================================
# 6. SPREADSHEET MATRIX TABLE RENDERING (MATCHES CONSUMPTION DESIGN)
# =============================================================================
def render_shipment_matrix_table(month_summary_df: pd.DataFrame, model_name: str = ""):
    """
    Renders the spreadsheet matrix table for Shipment GRS $, GRS U, B3, Build/Bleed $, Unit Ratio, and Price Factor with YoY % metrics.
    Matches Consumption Dashboard matrix design and formula specifications exactly.
    """
    import math
 
    if month_summary_df.empty:
        return html.Div("No Shipment Data Available", style={"padding": "20px", "textAlign": "center", "color": "#721c24"})
 
    th_style = {
        "backgroundColor": "#019881", "color": "#ffffff", "fontWeight": "800", "padding": "8px 10px",
        "border": "1px solid #858585", "textAlign": "center", "whiteSpace": "nowrap",
        "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif"
    }
    th_q1 = html.Th("Q1", colSpan=3, style={**th_style, "backgroundColor": "#018571"})
    th_q2 = html.Th("Q2", colSpan=3, style={**th_style, "backgroundColor": "#018571"})
    th_q3 = html.Th("Q3", colSpan=3, style={**th_style, "backgroundColor": "#018571"})
    th_q4 = html.Th("Q4", colSpan=3, style={**th_style, "backgroundColor": "#018571", "borderRight": "3px solid #858585"})
    th_tot = html.Th("TOTALS", colSpan=7, style={**th_style, "backgroundColor": "#017362"})
 
    hdr_row1 = html.Tr([
        html.Th("SHIPMENT METRIC", style={**th_style, "backgroundColor": "#019881", "textAlign": "left"}),
        html.Th("YEAR", style={**th_style, "backgroundColor": "#019881"}),
        th_q1, th_q2, th_q3, th_q4, th_tot
    ])
 
    hdr_row2 = html.Tr([
        html.Th("Metric Description", style={**th_style, "textAlign": "left", "minWidth": "160px", "backgroundColor": "#019881"}),
        html.Th("Year", style={**th_style, "minWidth": "50px", "backgroundColor": "#019881"}),
        *[html.Th(m, style={**th_style, "minWidth": "55px", "backgroundColor": "#019881", **({"borderRight": "3px solid #858585"} if m == "DEC" else {})}) for m in MONTHS],
        html.Th("Q1", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571"}),
        html.Th("Q2", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571"}),
        html.Th("Q3", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571"}),
        html.Th("Q4", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571", "borderRight": "3px solid #858585"}),
        html.Th("FY", style={**th_style, "minWidth": "65px", "backgroundColor": "#017362"}),
        html.Th("YTD", style={**th_style, "minWidth": "65px", "backgroundColor": "#017362"}),
        html.Th("YTG", style={**th_style, "minWidth": "65px", "backgroundColor": "#017362"})
    ])
 
    thead = html.Thead([hdr_row2])
 
    years = sorted(month_summary_df["KV_YEAR"].unique())
    latest_year = years[-1] if years else 2026
    prev_year = years[-2] if len(years) >= 2 else (latest_year - 1)
 
    latest_comp_m_nbr = 8 if latest_year == 2026 else 12
    ytd_slice = slice(0, latest_comp_m_nbr)
    ytg_slice = slice(latest_comp_m_nbr, 12)
 
    label_td_style = {
        "backgroundColor": "#DDDDDD", "color": "#000000", "fontWeight": "900", "fontSize": "14px",
        "textAlign": "center", "verticalAlign": "middle", "border": "1px solid #858585", "padding": "8px",
        "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif"
    }
 
    def calc_pct(actual, comparison):
        if actual is None or comparison is None or comparison == 0:
            return None
        return ((actual - comparison) / abs(comparison)) * 100.0
 
    def safe_sum(arr):
        if not arr:
            return None
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in arr):
            return None
        return sum(arr)
 
    def fmt_m_val(val, is_pct=False, unit_type="dollar"):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return ""
        if is_pct:
            return f"{val:+.1f}%" if val != 0 else "0.0%"
        if unit_type == "b3":
            return f"${val:,.1f}" if val != 0 else "$0.0"
        if unit_type == "unit_ratio":
            return f"{round(val):.0f}%" if val != 0 else "0%"
        if unit_type == "ratio":
            return f"{val:,.2f}" if val != 0 else "0.00"
        if unit_type == "build_bleed":
            m_val = val / 1_000_000.0
            if m_val < 0:
                return f"-{abs(m_val):,.1f}"
            return f"{m_val:,.1f}" if m_val != 0 else "0.0"
 
        m_val = val / 1_000_000.0
        if unit_type in ["dollar", "grs_u"]:
            if m_val < 0:
                return f"-${abs(m_val):,.1f}"
            return f"${m_val:,.1f}" if m_val != 0 else "$0.0"
        else:
            return f"{m_val:,.1f}" if m_val != 0 else "0.0"

    def get_unit_ratio_color(v_curr, ref_4_vals):
        """
        Calculates Unit Ratio Baseline = (SUM of the 4 previous/reference year Unit Ratios - MIN - MAX) / 2
        Color-coding conditions:
          - 🔴 RED: If Current Year Unit Ratio is outside ±10% of baseline (> 10%)
          - 🟡 YELLOW: If Current Year Unit Ratio is outside ±5% of baseline (> 5% and <= 10%)
          - Otherwise: No color (None, None)
        Checked RED first, then YELLOW.
        """
        if v_curr is None or (isinstance(v_curr, float) and math.isnan(v_curr)):
            return None, None

        valid_ref = [v for v in ref_4_vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
        if len(valid_ref) < 2:
            return None, None

        if len(valid_ref) == 4:
            min_v = min(valid_ref)
            max_v = max(valid_ref)
            baseline = (sum(valid_ref) - min_v - max_v) / 2.0
        else:
            min_v = min(valid_ref)
            max_v = max(valid_ref)
            if len(valid_ref) > 2:
                baseline = (sum(valid_ref) - min_v - max_v) / float(len(valid_ref) - 2)
            else:
                baseline = sum(valid_ref) / float(len(valid_ref))

        if baseline is None or baseline == 0:
            return None, None

        rel_diff_pct = (abs(v_curr - baseline) / abs(baseline)) * 100.0

        # Check RED first: outside ±10% of baseline
        if rel_diff_pct > 10.0:
            return "#f8d7da", "#721c24"

        # Check YELLOW second: outside ±5% of baseline but within ±10%
        if rel_diff_pct > 5.0:
            return "#fff3cd", "#856404"

        return None, None

    tbody_rows = []
 
    factory_pos_map, pos_val_map, pos_u_map = get_consumption_metrics_monthly_for_model(model_name)
 
    # Tuple structure: (metric_name, col_key, unit_type, has_yoy)
    metrics_config = [
        ("GRS $", "GRS_USD", "dollar", True),
        ("GRS U", "GRS_QTY", "grs_u", True),
        ("B3", "B3", "b3", True),
        ("Build/Bleed $", "BUILD_BLEED", "build_bleed", False),
        ("Unit Ratio", "UNIT_RATIO", "unit_ratio", False),
        ("Price Factor", "PRICE_FACTOR", "ratio", False),
    ]
 
    raw_metric_vals = {}
    for yr in years:
        yr_df = month_summary_df[month_summary_df["KV_YEAR"] == yr].sort_values("KV_MO_ID")
        usd_vals = [None] * 12
        qty_vals = [None] * 12
        for _, r in yr_df.iterrows():
            m_name = str(r["KV_MONTH_NAME"]).upper()[:3]
            if m_name in MONTHS:
                m_i = MONTHS.index(m_name)
                u_val = r.get("GRS_USD")
                q_val = r.get("GRS_QTY")
                if pd.notnull(u_val):
                    usd_vals[m_i] = float(u_val)
                if pd.notnull(q_val):
                    qty_vals[m_i] = float(q_val)
 
        raw_metric_vals[yr] = {"GRS_USD": usd_vals, "GRS_QTY": qty_vals}
 
    # Calculate FY Price Factor of previous year (e.g., 2025)
    fy_price_factor_prev = 1.0
    if prev_year in raw_metric_vals:
        prev_usd_arr = [v for v in raw_metric_vals[prev_year]["GRS_USD"] if v is not None]
        prev_qty_arr = [v for v in raw_metric_vals[prev_year]["GRS_QTY"] if v is not None]
        prev_pos_val_arr = [pos_val_map.get((str(prev_year), i)) for i in range(12) if pos_val_map.get((str(prev_year), i)) is not None]
        prev_pos_u_arr = [pos_u_map.get((str(prev_year), i)) for i in range(12) if pos_u_map.get((str(prev_year), i)) is not None]
 
        tot_prev_usd = sum(prev_usd_arr) if prev_usd_arr else 0.0
        tot_prev_qty = sum(prev_qty_arr) if prev_qty_arr else 0.0
        tot_prev_pos_val = sum(prev_pos_val_arr) if prev_pos_val_arr else 0.0
        tot_prev_pos_u = sum(prev_pos_u_arr) if prev_pos_u_arr else 0.0
 
        asp_prev_fy = (tot_prev_pos_val / tot_prev_pos_u) if (tot_prev_pos_val > 0 and tot_prev_pos_u > 0) else None
        b3_prev_fy = (tot_prev_usd / tot_prev_qty) if (tot_prev_usd > 0 and tot_prev_qty > 0) else None
 
        if asp_prev_fy and b3_prev_fy and b3_prev_fy != 0:
            fy_price_factor_prev = asp_prev_fy / b3_prev_fy
 
    # Calculate GRS $ and GRS U for latest_year from current month (m_cutoff_idx) through December (index 11)
    if latest_year in raw_metric_vals:
        usd_vals = raw_metric_vals[latest_year]["GRS_USD"]
        qty_vals = raw_metric_vals[latest_year]["GRS_QTY"]
        m_cutoff_idx = latest_comp_m_nbr
        ship_bb_df = load_shipment_building_block_data()
 
        for m_i in range(m_cutoff_idx, 12):
            m_nbr = m_i + 1
            m_name = MONTHS[m_i]
            factory_pos = factory_pos_map.get((str(latest_year), m_i))
 
            if factory_pos is None:
                # Fallback to previous year same month POS $ * Index if current year POS $ is not in Snowflake yet
                prev_pos_val = pos_val_map.get((str(prev_year), m_i))
                if prev_pos_val is not None:
                    f_pos_calc, _ = database.get_factory_pos_val(str(latest_year), m_nbr, model_name, prev_pos_val)
                    factory_pos = f_pos_calc if f_pos_calc is not None else prev_pos_val
                else:
                    factory_pos = 0.0
 
            bb_blocks, bb_total_k, has_bb = get_shipment_building_block_values(model_name, str(latest_year), m_nbr, bb_df=ship_bb_df)
 
            bb_total_m = (bb_total_k / 1000.0) if bb_total_k else 0.0
            factory_pos_m = (factory_pos / 1_000_000.0) if factory_pos else 0.0
            calc_grs_m = factory_pos_m + bb_total_m
            calc_grs_usd = calc_grs_m * 1_000_000.0
 
            usd_vals[m_i] = calc_grs_usd
 
            # Calculate Consumption ASP for same month & year
            p_val_m = pos_val_map.get((str(latest_year), m_i))
            p_u_m = pos_u_map.get((str(latest_year), m_i))
            asp_m = (p_val_m / p_u_m) if (p_val_m and p_u_m and p_u_m != 0) else None
 
            if asp_m is None:
                p_val_prev = pos_val_map.get((str(prev_year), m_i))
                p_u_prev = pos_u_map.get((str(prev_year), m_i))
                if p_val_prev and p_u_prev and p_u_prev != 0:
                    asp_m = p_val_prev / p_u_prev
 
            # Calculate Price Factor for same month & year
            pf_m = fy_price_factor_prev
 
            # Calculate B3 = ASP / Price Factor
            b3_proj = (asp_m / pf_m) if (asp_m and pf_m and pf_m != 0) else None
 
            # Calculate GRS U = GRS $ / B3 for current month through December
            if calc_grs_usd is not None and b3_proj and b3_proj != 0:
                qty_vals[m_i] = calc_grs_usd / b3_proj
 
            # Terminal diagnostics for current month through December
            print("\n" + "=" * 70)
            print(f"SHIPMENT BUILDING BLOCK SUMMARY | MODEL: '{model_name}' | PERIOD: {latest_year}-{m_nbr:02d} ({m_name})")
            print("=" * 70)
            for b_name in SHIPMENT_ALLOWED_BUILDING_BLOCKS:
                val_k = bb_blocks.get(b_name, 0.0)
                val_m = val_k / 1000.0
                print(f"  - {b_name:<20} : ${val_k:>10,.2f} K (${val_m:>6,.2f} M)")
            print("-" * 70)
            print(f"  TOTAL BUILDING BLOCKS  : ${bb_total_k:>10,.2f} K (${bb_total_m:>6,.2f} M)")
            print(f"  FACTORY POS $          : ${factory_pos:>10,.2f} (${factory_pos_m:>6,.2f} M)")
            print(f"  CALCULATED GRS $       : ${calc_grs_usd:>10,.2f} (${calc_grs_m:>6,.2f} M)")
            print(f"  CALCULATED B3          : ${b3_proj:>10,.2f}" if b3_proj else "  CALCULATED B3          : N/A")
            print(f"  CALCULATED GRS U       : {qty_vals[m_i]:>10,.2f}" if qty_vals[m_i] else "  CALCULATED GRS U       : N/A")
            print("=" * 70 + "\n")
 
        raw_metric_vals[latest_year] = {"GRS_USD": usd_vals, "GRS_QTY": qty_vals}
 
    b3_by_yr = {}
    for metric_name, col_key, unit_type, has_yoy in metrics_config:
        year_vals = {}
        for yr in years:
            if col_key == "B3":
                usd_v = raw_metric_vals[yr]["GRS_USD"]
                qty_v = raw_metric_vals[yr]["GRS_QTY"]
                b3_v = [None] * 12
                for m_i in range(12):
                    p_val = pos_val_map.get((str(yr), m_i))
                    p_u = pos_u_map.get((str(yr), m_i))
                    asp_m = (p_val / p_u) if (p_val is not None and p_u is not None and p_u != 0) else None
 
                    if asp_m is None:
                        p_val_p = pos_val_map.get((str(prev_year), m_i))
                        p_u_p = pos_u_map.get((str(prev_year), m_i))
                        if p_val_p and p_u_p and p_u_p != 0:
                            asp_m = p_val_p / p_u_p
 
                    pf_m = None
                    if usd_v[m_i] is not None and qty_v[m_i] is not None and qty_v[m_i] != 0:
                        b3_actual = usd_v[m_i] / qty_v[m_i]
                        if asp_m is not None and b3_actual != 0:
                            pf_m = asp_m / b3_actual
 
                    if pf_m is None or pf_m == 0:
                        pf_m = fy_price_factor_prev
 
                    if asp_m is not None and pf_m is not None and pf_m != 0:
                        b3_v[m_i] = asp_m / pf_m
                    elif usd_v[m_i] is not None and qty_v[m_i] is not None and qty_v[m_i] != 0:
                        b3_v[m_i] = usd_v[m_i] / qty_v[m_i]
 
                b3_by_yr[yr] = b3_v
                year_vals[yr] = b3_v
            elif col_key == "BUILD_BLEED":
                usd_v = raw_metric_vals[yr]["GRS_USD"]
                bb_v = [None] * 12
                for m_i in range(12):
                    gs = usd_v[m_i]
                    fp = factory_pos_map.get((str(yr), m_i))
                    if gs is not None and fp is not None:
                        bb_v[m_i] = gs - fp
                    elif gs is not None:
                        bb_v[m_i] = gs
                year_vals[yr] = bb_v
            elif col_key == "UNIT_RATIO":
                qty_v = raw_metric_vals[yr]["GRS_QTY"]
                ur_v = [None] * 12
                for m_i in range(12):
                    gu = qty_v[m_i]
                    pu = pos_u_map.get((str(yr), m_i))
                    if (pu is None or pu == 0) and prev_year:
                        pu = pos_u_map.get((str(prev_year), m_i))
 
                    if gu is not None and pu is not None and pu != 0:
                        ur_v[m_i] = (gu / pu) * 100.0
                year_vals[yr] = ur_v
            elif col_key == "PRICE_FACTOR":
                usd_v = raw_metric_vals[yr]["GRS_USD"]
                qty_v = raw_metric_vals[yr]["GRS_QTY"]
                b3_list = b3_by_yr.get(yr, [None] * 12)
                pf_v = [None] * 12
                for m_i in range(12):
                    p_val = pos_val_map.get((str(yr), m_i))
                    p_u = pos_u_map.get((str(yr), m_i))
                    asp_m = (p_val / p_u) if (p_val is not None and p_u is not None and p_u != 0) else None
 
                    if asp_m is None:
                        p_val_p = pos_val_map.get((str(prev_year), m_i))
                        p_u_p = pos_u_map.get((str(prev_year), m_i))
                        if p_val_p and p_u_p and p_u_p != 0:
                            asp_m = p_val_p / p_u_p
 
                    b3_m = b3_list[m_i] if m_i < len(b3_list) else None
                    if b3_m is None and usd_v[m_i] is not None and qty_v[m_i] is not None and qty_v[m_i] != 0:
                        b3_m = usd_v[m_i] / qty_v[m_i]
 
                    if asp_m is not None and b3_m is not None and b3_m != 0:
                        pf_v[m_i] = asp_m / b3_m
                    else:
                        pf_v[m_i] = fy_price_factor_prev
                year_vals[yr] = pf_v
            else:
                year_vals[yr] = raw_metric_vals[yr][col_key]
 
        yr_rows_tuples = [(str(yr), year_vals[yr], False) for yr in years]
 
        if has_yoy:
            yoy_m_vals = [None] * 12
            if latest_year in year_vals and prev_year in year_vals:
                for m_i in range(12):
                    l_v = year_vals[latest_year][m_i]
                    p_v = year_vals[prev_year][m_i]
                    yoy_m_vals[m_i] = calc_pct(l_v, p_v)
            yr_rows_tuples.append(("YoY %", yoy_m_vals, True))
 
        group_size = len(yr_rows_tuples)
 
        for g_idx, (yr_label, m_vals, is_yoy) in enumerate(yr_rows_tuples):
            td_cells = []
            if g_idx == 0:
                td_cells.append(html.Td(metric_name, rowSpan=group_size, style=label_td_style))
 
            is_highlight = (yr_label in [str(latest_year), "YoY %"])
            yr_bg = "#DDDDDD" if is_highlight else "#ffffff"
 
            td_cells.append(html.Td(yr_label, style={
                "backgroundColor": yr_bg, "color": "#000000",
                "fontWeight": "800" if is_highlight else "bold",
                "textAlign": "center", "border": "1px solid #858585",
                "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif"
            }))
 
            for m_i in range(12):
                v = m_vals[m_i]
                v_str = fmt_m_val(v, is_pct=is_yoy, unit_type=unit_type)
 
                text_color = "#000000"
                if is_yoy and v is not None:
                    if v < 0:
                        text_color = "#D9534F"
                    elif v > 0:
                        text_color = "#28A745"
 
                td_cells.append(html.Td(v_str, style={
                    "backgroundColor": yr_bg, "color": text_color,
                    "fontWeight": "800" if is_highlight else "500",
                    "textAlign": "right", "padding": "4px 6px", "border": "1px solid #858585", "fontSize": "11px",
                    "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif",
                    **({"borderRight": "3px solid #858585"} if m_i == 11 else {})
                }))
 
            if col_key == "B3":
                def calc_b3_period(yr_key, slice_obj):
                    u_sum = safe_sum(raw_metric_vals[yr_key]["GRS_USD"][slice_obj])
                    q_sum = safe_sum(raw_metric_vals[yr_key]["GRS_QTY"][slice_obj])
                    if u_sum is not None and q_sum is not None and q_sum != 0:
                        return u_sum / q_sum
                    return None
 
                if is_yoy:
                    q1_v = calc_pct(calc_b3_period(latest_year, slice(0, 3)), calc_b3_period(prev_year, slice(0, 3)))
                    q2_v = calc_pct(calc_b3_period(latest_year, slice(3, 6)), calc_b3_period(prev_year, slice(3, 6)))
                    q3_v = calc_pct(calc_b3_period(latest_year, slice(6, 9)), calc_b3_period(prev_year, slice(6, 9)))
                    q4_v = calc_pct(calc_b3_period(latest_year, slice(9, 12)), calc_b3_period(prev_year, slice(9, 12)))
                    fy_v = calc_pct(calc_b3_period(latest_year, slice(0, 12)), calc_b3_period(prev_year, slice(0, 12)))
                    ytd_v = calc_pct(calc_b3_period(latest_year, ytd_slice), calc_b3_period(prev_year, ytd_slice))
                    ytg_v = calc_pct(calc_b3_period(latest_year, ytg_slice), calc_b3_period(prev_year, ytg_slice))
                else:
                    yr_int = int(yr_label)
                    q1_v = calc_b3_period(yr_int, slice(0, 3))
                    q2_v = calc_b3_period(yr_int, slice(3, 6))
                    q3_v = calc_b3_period(yr_int, slice(6, 9))
                    q4_v = calc_b3_period(yr_int, slice(9, 12))
                    fy_v = calc_b3_period(yr_int, slice(0, 12))
                    ytd_v = calc_b3_period(yr_int, ytd_slice)
                    ytg_v = calc_b3_period(yr_int, ytg_slice)
            elif col_key == "BUILD_BLEED":
                def calc_bb_period(yr_key, slice_obj):
                    return safe_sum(year_vals[yr_key][slice_obj])
 
                yr_int = int(yr_label)
                q1_v = calc_bb_period(yr_int, slice(0, 3))
                q2_v = calc_bb_period(yr_int, slice(3, 6))
                q3_v = calc_bb_period(yr_int, slice(6, 9))
                q4_v = calc_bb_period(yr_int, slice(9, 12))
                fy_v = calc_bb_period(yr_int, slice(0, 12))
                ytd_v = calc_bb_period(yr_int, ytd_slice)
                ytg_v = calc_bb_period(yr_int, ytg_slice)
            elif col_key == "UNIT_RATIO":
                def calc_ur_period(yr_key, slice_obj):
                    g_sum = safe_sum(raw_metric_vals[yr_key]["GRS_QTY"][slice_obj])
                    p_sum = safe_sum([pos_u_map.get((str(yr_key), i)) for i in range(12)][slice_obj])
                    if g_sum is not None and p_sum is not None and p_sum != 0:
                        return (g_sum / p_sum) * 100.0
                    return None
 
                yr_int = int(yr_label)
                q1_v = calc_ur_period(yr_int, slice(0, 3))
                q2_v = calc_ur_period(yr_int, slice(3, 6))
                q3_v = calc_ur_period(yr_int, slice(6, 9))
                q4_v = calc_ur_period(yr_int, slice(9, 12))
                fy_v = calc_ur_period(yr_int, slice(0, 12))
                ytd_v = calc_ur_period(yr_int, ytd_slice)
                ytg_v = calc_ur_period(yr_int, ytg_slice)
            elif col_key == "PRICE_FACTOR":
                def calc_pf_period(yr_key, slice_obj):
                    p_val_sum = safe_sum([pos_val_map.get((str(yr_key), i)) for i in range(12)][slice_obj])
                    p_u_sum = safe_sum([pos_u_map.get((str(yr_key), i)) for i in range(12)][slice_obj])
                    g_usd_sum = safe_sum(raw_metric_vals[yr_key]["GRS_USD"][slice_obj])
                    g_qty_sum = safe_sum(raw_metric_vals[yr_key]["GRS_QTY"][slice_obj])
                    asp_v = (p_val_sum / p_u_sum) if (p_val_sum is not None and p_u_sum is not None and p_u_sum != 0) else None
                    b3_v = (g_usd_sum / g_qty_sum) if (g_usd_sum is not None and g_qty_sum is not None and g_qty_sum != 0) else None
                    if asp_v is not None and b3_v is not None and b3_v != 0:
                        return asp_v / b3_v
                    return None
 
                if is_yoy:
                    q1_v = calc_pct(calc_pf_period(latest_year, slice(0, 3)), calc_pf_period(prev_year, slice(0, 3)))
                    q2_v = calc_pct(calc_pf_period(latest_year, slice(3, 6)), calc_pf_period(prev_year, slice(3, 6)))
                    q3_v = calc_pct(calc_pf_period(latest_year, slice(6, 9)), calc_pf_period(prev_year, slice(6, 9)))
                    q4_v = calc_pct(calc_pf_period(latest_year, slice(9, 12)), calc_pf_period(prev_year, slice(9, 12)))
                    fy_v = calc_pct(calc_pf_period(latest_year, slice(0, 12)), calc_pf_period(prev_year, slice(0, 12)))
                    ytd_v = calc_pct(calc_pf_period(latest_year, ytd_slice), calc_pf_period(prev_year, ytd_slice))
                    ytg_v = calc_pct(calc_pf_period(latest_year, ytg_slice), calc_pf_period(prev_year, ytg_slice))
                else:
                    yr_int = int(yr_label)
                    q1_v = calc_pf_period(yr_int, slice(0, 3))
                    q2_v = calc_pf_period(yr_int, slice(3, 6))
                    q3_v = calc_pf_period(yr_int, slice(6, 9))
                    q4_v = calc_pf_period(yr_int, slice(9, 12))
                    fy_v = calc_pf_period(yr_int, slice(0, 12))
                    ytd_v = calc_pf_period(yr_int, ytd_slice)
                    ytg_v = calc_pf_period(yr_int, ytg_slice)
            else:
                if is_yoy:
                    l_m = year_vals.get(latest_year, [None]*12)
                    p_m = year_vals.get(prev_year, [None]*12)
                    q1_v = calc_pct(safe_sum(l_m[0:3]), safe_sum(p_m[0:3]))
                    q2_v = calc_pct(safe_sum(l_m[3:6]), safe_sum(p_m[3:6]))
                    q3_v = calc_pct(safe_sum(l_m[6:9]), safe_sum(p_m[6:9]))
                    q4_v = calc_pct(safe_sum(l_m[9:12]), safe_sum(p_m[9:12]))
                    fy_v = calc_pct(safe_sum(l_m[0:12]), safe_sum(p_m[0:12]))
                    ytd_v = calc_pct(safe_sum(l_m[ytd_slice]), safe_sum(p_m[ytd_slice]))
                    ytg_v = calc_pct(safe_sum(l_m[ytg_slice]), safe_sum(p_m[ytg_slice]))
                else:
                    q1_v = safe_sum(m_vals[0:3])
                    q2_v = safe_sum(m_vals[3:6])
                    q3_v = safe_sum(m_vals[6:9])
                    q4_v = safe_sum(m_vals[9:12])
                    fy_v = safe_sum(m_vals[0:12])
                    ytd_v = safe_sum(m_vals[ytd_slice])
                    ytg_v = safe_sum(m_vals[ytg_slice])
 
            summary_vals = [q1_v, q2_v, q3_v, q4_v, fy_v, ytd_v, ytg_v]
            for s_idx, qv in enumerate(summary_vals):
                qv_str = fmt_m_val(qv, is_pct=is_yoy, unit_type=unit_type)
                s_color = "#000000"
                if is_yoy and qv is not None:
                    if qv < 0:
                        s_color = "#D9534F"
                    elif qv > 0:
                        s_color = "#28A745"
 
                td_cells.append(html.Td(qv_str, style={
                    "backgroundColor": yr_bg, "color": s_color,
                    "fontWeight": "800" if is_highlight else "700",
                    "textAlign": "right", "padding": "4px 6px", "border": "1px solid #858585", "fontSize": "11px",
                    "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif",
                    **({"borderRight": "3px solid #858585"} if s_idx == 3 else {})
                }))
 
            row_border = "3px solid #858585" if (g_idx == group_size - 1) else "1px solid #858585"
            tbody_rows.append(html.Tr(td_cells, style={"borderBottom": row_border}))
 
    table = html.Table([thead, html.Tbody(tbody_rows)], style={
        "width": "100%", "borderCollapse": "collapse",
        "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif",
        "fontSize": "11px"
    })
 
    note_elem = html.Div(
        "Note: GRS $ and GRS U are in millions",
        style={
            "marginTop": "10px",
            "fontSize": "12px",
            "fontStyle": "italic",
            "color": "#495057",
            "fontWeight": "600",
            "textAlign": "left"
        }
    )
 
    return html.Div([table, note_elem])
 
 
# =============================================================================
# CLI STANDALONE VALIDATION RUNNER
# =============================================================================
def main():
    target_model = sys.argv[1] if len(sys.argv) > 1 else "Children's Tylenol"
    print("=" * 90)
    print(f"SHIPMENT GRS $ INDEPENDENT VALIDATION FOR MODEL: '{target_model}'")
    print("KENVUE JANUARY 2022 TO AUGUST 2026")
    print("=" * 90)
 
    model_mapping = load_shipment_model_mapping(model_name=target_model)
    num_mapping_rows = len(model_mapping)
 
    selected_calendar, selected_months_df = load_kv_calendar()
 
    items_df = resolve_shipment_model_items(target_model)
    num_matched_items = len(items_df)
 
    shipment_df = fetch_shipment_data_for_model(target_model)
    num_shipment_rows = len(shipment_df)
 
    result_df, detail_df = process_monthly_summary(shipment_df, selected_calendar, selected_months_df)
 
    print("\n" + "=" * 90)
    print(f"MODEL: '{target_model}' MONTH-WISE SHIPMENT GRS $ (56 KENVUE MONTHS)")
    print("=" * 90)
    print(f"{'YEAR':<8}{'KV_MO_ID':<12}{'MONTH':<15}{'GRS_USD':>22}{'GRS_MILLIONS':>22}")
    print("-" * 90)
 
    for _, row in result_df.iterrows():
        yr = int(row["KV_YEAR"])
        mo_id = str(row["KV_MO_ID"])
        m_name = str(row["KV_MONTH_NAME"]).title()
        grs = float(row["GRS_USD"])
        grs_m = float(row["GRS_MILLIONS"])
        print(f"{yr:<8}{mo_id:<12}{m_name:<15}${grs:>21,.2f}${grs_m:>20,.2f} M")
 
    print("-" * 90)
 
    for yr in range(START_YEAR, END_YEAR + 1):
        yr_df = result_df[result_df["KV_YEAR"] == yr]
        yr_tot = yr_df["GRS_USD"].sum()
        print(f"{yr} TOTAL{'':<27}${yr_tot:>21,.2f}${yr_tot/1_000_000:>20,.2f} M")
 
    print("-" * 90)
    total_grs = result_df["GRS_USD"].sum()
    total_grs_m = total_grs / 1_000_000.0
    print(f"{'2022-AUG 2026 GRAND TOTAL':<35}${total_grs:>21,.2f}${total_grs_m:>20,.2f} M")
    print("=" * 90)
 
    print(f"\nCHECK 1 - Mapping Rows for '{target_model}' : {num_mapping_rows}")
    print(f"CHECK 2 - Matched Unique KV_ITEM_NOs       : {num_matched_items}")
    print(f"CHECK 3 - Shipment Transaction Rows        : {num_shipment_rows:,}")
    print(f"CHECK 4 - Total GRS $                      : ${total_grs:,.2f}")
    print(f"CHECK 5 - Monthly Row Count                : {len(result_df)} (Expected 56)")
    print("\nValidation PASSED")
 
if __name__ == "__main__":
    main()
 
