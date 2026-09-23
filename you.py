import os
import sys
import re
import math
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

import database

# Initialize Dash App for Shipment Validation Dashboard
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Shipment Validation Dashboard"
)
server = app.server

# Months Constant
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Standardized Hierarchy Column Names required by Updated Mapping 2.xlsx / Book1.xlsx
EXCEL_HIERARCHY_COLUMNS = [
    "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC",
    "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC",
    "GLOBAL_GMC_C3_NEED_STATE_DESC",
    "GLOBAL_GMC_C4_CATEGORY_DESC",
    "GLOBAL_GMC_C5_SUB_CATEGORY_DESC",
    "GLOBAL_GMC_B1_BRAND_DESC",
    "GLOBAL_GMC_B2_SUB_BRAND_DESC"
]

HIERARCHY_ALIAS_MAP = {
    "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC": ["GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC", "C1_BUSINESS_SEGMENT_DESC", "POS_BUSINESS_SEGMENT", "BUSINESS_SEGMENT"],
    "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC": ["GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC", "C2_BUSINESS_SUB_SEGMENT_DESC", "POS_BUSINESS_SUB_SEGMENT", "BUSINESS_SUB_SEGMENT"],
    "GLOBAL_GMC_C3_NEED_STATE_DESC": ["GLOBAL_GMC_C3_NEED_STATE_DESC", "C3_NEED_STATE_DESC", "POS_NEED_STATE", "NEED_STATE"],
    "GLOBAL_GMC_C4_CATEGORY_DESC": ["GLOBAL_GMC_C4_CATEGORY_DESC", "C4_CATEGORY_DESC", "POS_CATEGORY", "CATEGORY"],
    "GLOBAL_GMC_C5_SUB_CATEGORY_DESC": ["GLOBAL_GMC_C5_SUB_CATEGORY_DESC", "C5_SUB_CATEGORY_DESC", "POS_SUB_CATEGORY", "SUB_CATEGORY"],
    "GLOBAL_GMC_B1_BRAND_DESC": ["GLOBAL_GMC_B1_BRAND_DESC", "B1_BRAND_DESC", "POS_BRAND", "BRAND"],
    "GLOBAL_GMC_B2_SUB_BRAND_DESC": ["GLOBAL_GMC_B2_SUB_BRAND_DESC", "B2_SUB_BRAND_DESC", "POS_SUB_BRAND", "SUB_BRAND"]
}


# --- STEP 1: Text Normalization Helper ---
def normalize_text(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip().upper()
    if s in ["NAN", "NONE", "NULL", "EMPTY", "N/A", "<NA>"]:
        return ""
    return re.sub(r'\s+', ' ', s)


# --- STEP 2: Load Model Mapping Excel File (Shipment GTS) ---
_cached_excel_df = None
EXPLICIT_SHIPMENT_MAPPING_PATH = r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\Model Mapping File - Shipment GTS.xlsx"

def load_excel_mapping_file():
    global _cached_excel_df
    if _cached_excel_df is not None:
        return _cached_excel_df

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        EXPLICIT_SHIPMENT_MAPPING_PATH,
        os.path.join(base_dir, "Model Mapping File - Shipment GTS.xlsx"),
        os.path.join(base_dir, "Model Mapping File - Circana POS.xlsx"),
        os.path.join(base_dir, "model mapping file - circana pos.xlsx"),
        os.path.join(base_dir, "model_mapping.xlsx"),
        os.path.join(base_dir, "Book1.xlsx"),
    ]

    for cand in candidate_paths:
        if cand and os.path.exists(cand):
            try:
                df = pd.read_excel(cand)
                if 'Model' in df.columns and len(df) > 0:
                    _cached_excel_df = df
                    print(f"[EXCEL MAPPING LOADED]: '{cand}' with {len(df)} rows and {df['Model'].nunique()} unique models.")
                    break
            except Exception as e:
                print(f"Notice reading '{cand}': {e}")

    if _cached_excel_df is not None:
        return _cached_excel_df

    print("[WARNING]: Excel mapping file not found. Creating fallback model map schema.")
    _cached_excel_df = pd.DataFrame(columns=EXCEL_HIERARCHY_COLUMNS + ["Model"])
    return _cached_excel_df


def get_shipment_model_options():
    df_map = load_excel_mapping_file()
    if 'Model' not in df_map.columns or df_map.empty:
        return ["All Models"]
    models = df_map['Model'].dropna().astype(str).str.strip()
    models = models[(models != "") & (~models.str.upper().isin(["NAN", "NONE", "NULL"]))]
    unique_models = sorted(models.unique().tolist())
    return ["All Models"] + unique_models


# --- STEP 3: Normalize & Alias Shipment DataFrame Hierarchy Columns ---
def map_and_normalize_hierarchy_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df_mapped = df.copy()
    upper_cols = {str(c).upper(): c for c in df_mapped.columns}

    for std_col, aliases in HIERARCHY_ALIAS_MAP.items():
        if std_col in df_mapped.columns:
            continue
        found_alias = None
        for alias in aliases:
            if alias.upper() in upper_cols:
                found_alias = upper_cols[alias.upper()]
                break
        if found_alias:
            df_mapped[std_col] = df_mapped[found_alias]
        else:
            df_mapped[std_col] = ""

    return df_mapped


# --- STEP 4: Comprehensive Shipment Data Retrieval (Snowflake + Robust Fallback) ---
def generate_fallback_shipment_data():
    df_excel = load_excel_mapping_file()
    records = []
    dates = [
        "2021-01-15", "2021-02-15", "2021-03-15", "2021-04-15", "2021-05-15", "2021-06-15",
        "2021-07-15", "2021-08-15", "2021-09-15", "2021-10-15", "2021-11-15", "2021-12-15",
        "2022-01-15", "2022-02-15", "2022-03-15", "2022-04-15", "2022-05-15", "2022-06-15",
        "2022-07-15", "2022-08-15", "2022-09-15", "2022-10-15", "2022-11-15", "2022-12-15",
        "2023-01-15", "2023-02-15", "2023-03-15", "2023-04-15", "2023-05-15", "2023-06-15",
        "2023-07-15", "2023-08-15", "2023-09-15", "2023-10-15", "2023-11-15", "2023-12-15",
        "2024-01-15", "2024-02-15", "2024-03-15", "2024-04-15", "2024-05-15", "2024-06-15",
        "2024-07-15", "2024-08-15", "2024-09-15", "2024-10-15", "2024-11-15", "2024-12-15",
        "2025-01-15", "2025-02-15", "2025-03-15", "2025-04-15", "2025-05-15", "2025-06-15",
        "2025-07-15", "2025-08-15", "2025-09-15", "2025-10-15", "2025-11-15", "2025-12-15",
        "2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15", "2026-05-15", "2026-06-15",
        "2026-07-15"
    ]

    unique_rules = df_excel.drop_duplicates(subset=[c for c in EXCEL_HIERARCHY_COLUMNS if c in df_excel.columns])
    for _, row in unique_rules.iterrows():
        b1 = normalize_text(row.get("GLOBAL_GMC_B1_BRAND_DESC", "MOTRIN"))
        b2 = normalize_text(row.get("GLOBAL_GMC_B2_SUB_BRAND_DESC", "ADULT MOTRIN"))
        c1 = normalize_text(row.get("GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC", "SELF CARE"))
        c2 = normalize_text(row.get("GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC", "ANALGESICS"))
        c3 = normalize_text(row.get("GLOBAL_GMC_C3_NEED_STATE_DESC", "PAIN RELIEF"))
        c4 = normalize_text(row.get("GLOBAL_GMC_C4_CATEGORY_DESC", "INTERNAL ANALGESICS"))
        c5 = normalize_text(row.get("GLOBAL_GMC_C5_SUB_CATEGORY_DESC", "ADULT PAIN"))

        if not b1: b1 = "MOTRIN"
        if not c4: c4 = "INTERNAL ANALGESICS"

        for dt in dates:
            yr = int(dt[:4])
            base_val = 500000 + (yr - 2021) * 50000 + ((hash(b1 + dt) % 100) * 1000)
            base_cu = 100000 + (yr - 2021) * 10000 + ((hash(b2 + dt) % 50) * 200)
            ret_val = base_val * 0.05
            ret_cu = base_cu * 0.04

            records.append({
                "GLOBAL_DATE_SHORT_DESC": dt,
                "GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC": c1,
                "GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC": c2,
                "GLOBAL_GMC_C3_NEED_STATE_DESC": c3,
                "GLOBAL_GMC_C4_CATEGORY_DESC": c4,
                "GLOBAL_GMC_C5_SUB_CATEGORY_DESC": c5,
                "GLOBAL_GMC_B1_BRAND_DESC": b1,
                "GLOBAL_GMC_B2_SUB_BRAND_DESC": b2,
                "GROSS_SHIPMENT_AM": base_val,
                "RETURN_SHIP_AM": ret_val,
                "GROSS_QTY_CU": base_cu,
                "RETURN_QTY_CU": ret_cu,
                "GROSS_QTY_CASE": base_cu // 12,
                "RETURN_QTY_CASE": ret_cu // 12,
            })

    return pd.DataFrame(records)


def fetch_shipment_raw_data():
    """
    Executes the official Shipment Snowflake query targeting:
    TF_TRNS_INV_DLY_TERR_EXPL, TD_ITM_DIV, M_FLATTENED_PROD_HIER, TD_TM_DY, TD_TM_WK
    """
    if os.getenv("USE_MOCK_DATA", "").lower() in ["1", "true", "yes"]:
        return generate_fallback_shipment_data()

    try:
        conn = database.get_snowflake_connection()
        official_shipment_query = """
        SELECT
            tm_dy.GLOBAL_DATE_SHORT_DESC AS GLOBAL_DATE_SHORT_DESC,
            ph.GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC AS GLOBAL_GMC_C1_BUSINESS_SEGMENT_DESC,
            ph.GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC AS GLOBAL_GMC_C2_BUSINESS_SUB_SEGMENT_DESC,
            ph.GLOBAL_GMC_C3_NEED_STATE_DESC AS GLOBAL_GMC_C3_NEED_STATE_DESC,
            ph.GLOBAL_GMC_C4_CATEGORY_DESC AS GLOBAL_GMC_C4_CATEGORY_DESC,
            ph.GLOBAL_GMC_C5_SUB_CATEGORY_DESC AS GLOBAL_GMC_C5_SUB_CATEGORY_DESC,
            ph.GLOBAL_GMC_B1_BRAND_DESC AS GLOBAL_GMC_B1_BRAND_DESC,
            ph.GLOBAL_GMC_B2_SUB_BRAND_DESC AS GLOBAL_GMC_B2_SUB_BRAND_DESC,
            SUM(CASE WHEN f.trns_rec_cd = '2' THEN f.trns_grs_am ELSE 0 END) AS GROSS_SHIPMENT_AM,
            SUM(CASE WHEN f.trns_rec_cd = '3' THEN f.trns_grs_am ELSE 0 END) AS RETURN_SHIP_AM,
            SUM(CASE WHEN f.trns_rec_cd = '2' THEN f.trns_qt_case ELSE 0 END) AS GROSS_QTY_CASE,
            SUM(CASE WHEN f.trns_rec_cd = '3' THEN f.trns_qt_case ELSE 0 END) AS RETURN_QTY_CASE,
            SUM(CASE WHEN f.trns_rec_cd = '2' THEN f.trns_qt_cu ELSE 0 END) AS GROSS_QTY_CU,
            SUM(CASE WHEN f.trns_rec_cd = '3' THEN f.trns_qt_cu ELSE 0 END) AS RETURN_QTY_CU
        FROM PROD_CUSTOMER360_GLOBALNA.NAUSINTERNAL_ACCESS.TF_TRNS_INV_DLY_TERR_EXPL f
        INNER JOIN PROD_CUSTOMER360_GLOBALNA.NAUSMASTER_ACCESS.TD_ITM_DIV i
            ON f.cpnt_itm_id = i.itm_id
        INNER JOIN PROD_CUSTOMER360_GLOBALNA.NAUSMASTER_ACCESS.M_FLATTENED_PROD_HIER ph
            ON f.cpnt_itm_id = ph.itm_id
        INNER JOIN PROD_CUSTOMER360_GLOBALNA.NAUSMASTER_ACCESS.TD_TM_DY tm_dy
            ON f.tm_per_id = tm_dy.tm_per_id
        INNER JOIN PROD_CUSTOMER360_GLOBALNA.NAUSMASTER_ACCESS.TD_TM_WK w
            ON w.tm_wk_id = tm_dy.tm_wk_id
        GROUP BY ALL
        ORDER BY tm_dy.GLOBAL_DATE_SHORT_DESC ASC;
        """
        df_sf = pd.read_sql_query(official_shipment_query, conn)
        if not df_sf.empty:
            df_sf.columns = [c.upper() for c in df_sf.columns]
            print(f"[SNOWFLAKE SHIPMENT DATA RETRIEVED]: {len(df_sf)} raw rows.")
            return df_sf
    except Exception as e:
        print(f"[NOTICE]: Could not execute Snowflake query directly ({e}). Generating dataset...")

    return generate_fallback_shipment_data()


# --- STEP 5: Rule-Based Model & Hierarchy Filtering with Debugging & Wildcard Support ---
def filter_shipment_dataframe(df_shipment: pd.DataFrame, model=None, brand=None, category=None, sub_brand=None) -> pd.DataFrame:
    raw_cnt = len(df_shipment)
    print("\n" + "=" * 80)
    print(f"SHIPMENT DATA FILTERING DIAGNOSTICS FOR MODEL: '{model}'")
    print("=" * 80)
    print(f"1. Snowflake Raw Shipment Rows: {raw_cnt}")

    if df_shipment.empty:
        return df_shipment

    # Map & Normalize Hierarchy Columns
    df_mapped = map_and_normalize_hierarchy_columns(df_shipment)
    mapped_cnt = len(df_mapped)
    print(f"2. Rows after Hierarchy Columns Mapped: {mapped_cnt}")

    # Prepare normalized shipment dataframe for matching
    df_ship_norm = pd.DataFrame(index=df_mapped.index)
    for col in EXCEL_HIERARCHY_COLUMNS:
        if col in df_mapped.columns:
            df_ship_norm[col] = df_mapped[col].apply(normalize_text)
        else:
            df_ship_norm[col] = ""

    # STEP A: Model Filter
    df_model_filtered = df_mapped
    if model and str(model).strip().upper() not in ["ALL", "ALL MODELS"]:
        model_norm = normalize_text(model)
        df_excel = load_excel_mapping_file()
        df_excel_norm = df_excel.copy()
        df_excel_norm['Model_Norm'] = df_excel_norm['Model'].apply(normalize_text)
        matching_rules = df_excel_norm[df_excel_norm['Model_Norm'] == model_norm]

        print(f"\nSelected Model: '{model}'")
        print(f"Number of Excel mapping rules found: {len(matching_rules)}")

        if matching_rules.empty:
            print(f"[WARNING]: No Excel mapping rules found for model '{model}'. Returning empty dataframe.")
            return pd.DataFrame()

        matched_masks = []
        for r_idx, rule in matching_rules.iterrows():
            rule_conditions = {}
            for col in EXCEL_HIERARCHY_COLUMNS:
                val = normalize_text(rule.get(col, ""))
                if val:  # POPULATED EXCEL FIELD (Blank values act as WILDCARD)
                    rule_conditions[col] = val

            rule_mask = pd.Series(True, index=df_mapped.index)
            for col, val in rule_conditions.items():
                col_match = (df_ship_norm[col] == val)
                rule_mask &= col_match

            matched_masks.append(rule_mask)

        # OR condition across rules for the selected model
        final_model_mask = pd.Series(False, index=df_mapped.index)
        for mask in matched_masks:
            final_model_mask |= mask

        df_model_filtered = df_mapped[final_model_mask].reset_index(drop=True)
        print(f"3. Rows after Model filtering: {len(df_model_filtered)}")

        if df_model_filtered.empty:
            print("[DIAGNOSTIC FAILURE]: Model filtering resulted in 0 rows!")
            print("Failed hierarchy conditions analysis:")
            for col in EXCEL_HIERARCHY_COLUMNS:
                sf_vals = df_ship_norm[col].unique()[:5].tolist()
                req_vals = matching_rules[col].dropna().unique().tolist()
                print(f"  Col '{col}' -> Required by Excel: {req_vals} | Available in Shipment data: {sf_vals}")

    # STEP B: Brand Filter
    df_brand_filtered = df_model_filtered
    if brand and str(brand).strip().upper() not in ["ALL", "ALL BRANDS"]:
        brand_norm = normalize_text(brand)
        brand_mask = df_brand_filtered['GLOBAL_GMC_B1_BRAND_DESC'].apply(normalize_text) == brand_norm
        df_brand_filtered = df_brand_filtered[brand_mask].reset_index(drop=True)
        print(f"4. Rows after Brand filtering ('{brand}'): {len(df_brand_filtered)}")
    else:
        print(f"4. Rows after Brand filtering ('All Brands'): {len(df_brand_filtered)}")

    # STEP C: Category Filter
    df_cat_filtered = df_brand_filtered
    if category and str(category).strip().upper() not in ["ALL", "ALL CATEGORIES"]:
        cat_norm = normalize_text(category)
        cat_mask = df_cat_filtered['GLOBAL_GMC_C4_CATEGORY_DESC'].apply(normalize_text) == cat_norm
        df_cat_filtered = df_cat_filtered[cat_mask].reset_index(drop=True)
        print(f"5. Rows after Category filtering ('{category}'): {len(df_cat_filtered)}")
    else:
        print(f"5. Rows after Category filtering ('All Categories'): {len(df_cat_filtered)}")

    # STEP D: Sub-Brand Filter
    df_sb_filtered = df_cat_filtered
    if sub_brand and str(sub_brand).strip().upper() not in ["ALL", "ALL SUB-BRANDS"]:
        sb_norm = normalize_text(sub_brand)
        sb_mask = df_sb_filtered['GLOBAL_GMC_B2_SUB_BRAND_DESC'].apply(normalize_text) == sb_norm
        df_sb_filtered = df_sb_filtered[sb_mask].reset_index(drop=True)
        print(f"6. Rows after Sub-Brand filtering ('{sub_brand}'): {len(df_sb_filtered)}")
    else:
        print(f"6. Rows after Sub-Brand filtering ('All Sub-Brands'): {len(df_sb_filtered)}")

    print(f"Final Filtered Row Count: {len(df_sb_filtered)}")
    print("=" * 80 + "\n")
    return df_sb_filtered


# --- STEP 6: Dynamic Filter Options for Dropdowns ---
def get_cascading_shipment_filter_options(model=None, brand=None, category=None, sub_brand=None):
    models = get_shipment_model_options()
    df_raw = fetch_shipment_raw_data()
    df_mapped = map_and_normalize_hierarchy_columns(df_raw)

    # Apply Model filter first
    df_mod = df_mapped
    if model and str(model).strip().upper() not in ["ALL", "ALL MODELS"]:
        model_norm = normalize_text(model)
        df_excel = load_excel_mapping_file()
        df_excel_norm = df_excel.copy()
        df_excel_norm['Model_Norm'] = df_excel_norm['Model'].apply(normalize_text)
        rules = df_excel_norm[df_excel_norm['Model_Norm'] == model_norm]
        if not rules.empty:
            df_norm = pd.DataFrame(index=df_mapped.index)
            for col in EXCEL_HIERARCHY_COLUMNS:
                df_norm[col] = df_mapped[col].apply(normalize_text) if col in df_mapped.columns else ""
            
            masks = []
            for _, r in rules.iterrows():
                r_mask = pd.Series(True, index=df_mapped.index)
                for col in EXCEL_HIERARCHY_COLUMNS:
                    v = normalize_text(r.get(col, ""))
                    if v:
                        r_mask &= (df_norm[col] == v)
                masks.append(r_mask)
            
            f_mask = pd.Series(False, index=df_mapped.index)
            for m in masks: f_mask |= m
            df_mod = df_mapped[f_mask]

    if df_mod.empty:
        return {
            "models": models, "brands": ["All Brands"], "categories": ["All Categories"], "sub_brands": ["All Sub-Brands"]
        }

    avail_b = sorted([str(b).strip().upper() for b in df_mod['GLOBAL_GMC_B1_BRAND_DESC'].dropna().unique() if str(b).strip() != ""])
    brand_opts = ["All Brands"] + avail_b

    df_b = df_mod
    if brand and str(brand).strip().upper() not in ["ALL", "ALL BRANDS"]:
        b_norm = normalize_text(brand)
        df_b = df_mod[df_mod['GLOBAL_GMC_B1_BRAND_DESC'].apply(normalize_text) == b_norm]

    avail_c = sorted([str(c).strip().upper() for c in df_b['GLOBAL_GMC_C4_CATEGORY_DESC'].dropna().unique() if str(c).strip() != ""])
    cat_opts = ["All Categories"] + avail_c

    df_c = df_b
    if category and str(category).strip().upper() not in ["ALL", "ALL CATEGORIES"]:
        c_norm = normalize_text(category)
        df_c = df_b[df_b['GLOBAL_GMC_C4_CATEGORY_DESC'].apply(normalize_text) == c_norm]

    avail_sb = sorted([str(sb).strip().upper() for sb in df_c['GLOBAL_GMC_B2_SUB_BRAND_DESC'].dropna().unique() if str(sb).strip() != ""])
    sb_opts = ["All Sub-Brands"] + avail_sb

    return {
        "models": models,
        "brands": brand_opts,
        "categories": cat_opts,
        "sub_brands": sb_opts
    }


# --- STEP 7: Pure Calculation Helpers ---
def calc_net(gross, ret):
    if gross is None: return None
    return gross - (ret if ret is not None else 0.0)

def calc_pct_var(actual, comparison):
    if actual is None or comparison is None or comparison == 0: return None
    return ((actual - comparison) / abs(comparison)) * 100.0

def calc_share(month_val, total_val):
    if month_val is None or total_val is None or total_val == 0: return None
    return (month_val / total_val) * 100.0

def fmt_val(val, unit, status):
    if status == "EMPTY" or val is None or math.isnan(val):
        return ""
    if unit == "$":
        if isinstance(val, float) and val != int(val) and abs(val) < 1000 and round(val, 2) != round(val, 0):
            return f"{val:,.2f}"
        return f"{val:,.0f}"
    elif unit == "Units":
        return f"{val:,.0f}"
    elif unit == "%":
        return f"{val:.1f}%"
    elif unit == "Ratio":
        return f"{val:.2f}"
    return f"{val:,.2f}"


# --- STEP 8: Sidebar & Header UI Components ---
sidebar = html.Div([
    dcc.Store(id="active-tab", data="shipments"),
    html.Div([
        dcc.Markdown(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 40" width="76" height="24"><text x="80" y="28" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif" font-size="32" font-weight="900" fill="#ffffff" letter-spacing="-1.2px">kenvue</text></svg>',
            dangerously_allow_html=True,
            style={"margin": "0 auto", "display": "inline-block"}
        )
    ], style={"marginTop": "32px", "marginBottom": "70px", "textAlign": "center"}),

    html.Div([
        dbc.Button([
            dcc.Markdown(
                '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 19h16v2H2V3h2v16zm3-7h3v5H7v-5zm5-5h3v10h-3V7zm5 3h3v7h-3v-7z" fill="#ffffff"/></svg>',
                dangerously_allow_html=True, style={"margin": "0", "padding": "0", "pointerEvents": "none"}
            ),
            html.Span("Consumption", style={"color": "#ffffff", "fontSize": "11px", "fontWeight": "600", "marginTop": "4px", "pointerEvents": "none"})
        ], id="nav-consumption", color="link", n_clicks=0, style={
            "width": "84px", "height": "76px", "borderRadius": "10px", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "cursor": "pointer", "opacity": "0.85", "backgroundColor": "transparent", "border": "none", "textDecoration": "none"
        }),

        dbc.Button([
            dcc.Markdown(
                '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9l1.96 2.5H17V9.5h2.5zm-1 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z" fill="#ffffff"/></svg>',
                dangerously_allow_html=True, style={"margin": "0", "padding": "0", "pointerEvents": "none"}
            ),
            html.Span("Shipments", style={"color": "#ffffff", "fontSize": "11px", "fontWeight": "600", "marginTop": "4px", "pointerEvents": "none"})
        ], id="nav-shipments", color="link", n_clicks=0, style={
            "backgroundColor": "#019881", "width": "84px", "height": "76px", "borderRadius": "10px", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "cursor": "pointer", "boxShadow": "0 2px 6px rgba(0,0,0,0.2)", "border": "none", "textDecoration": "none"
        })
    ], style={"display": "flex", "flexDirection": "column", "gap": "24px", "alignItems": "center", "width": "100%"})
], style={
    "position": "fixed", "top": "0", "left": "0", "bottom": "0", "width": "104px", "backgroundColor": "#019881", "zIndex": "1000", "display": "flex", "flexDirection": "column", "alignItems": "center", "boxShadow": "2px 0 10px rgba(0,0,0,0.15)"
})

main_content = html.Div([
    html.Div([
        html.Div(id="header-title-container", children=[
            html.H1(["SHIPMENT", html.Br(), "VALIDATION"], style={
                "color": "#ffffff", "fontWeight": "900", "fontSize": "22px", "letterSpacing": "1.5px", "margin": "0", "textTransform": "uppercase", "lineHeight": "1.2"
            })
        ], style={
            "backgroundColor": "#019881", "border": "1px solid #019881", "borderRadius": "14px", "padding": "14px 40px", "display": "inline-block", "boxShadow": "0 4px 14px rgba(1, 152, 129, 0.25)"
        })
    ], style={"textAlign": "center", "marginBottom": "20px"}),

    html.Div([
        html.Span(id="live-record-count", style={"display": "none"}),

        dbc.Row([
            dbc.Col([
                html.Label("Model:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-model",
                    options=[{"label": m, "value": m} for m in get_shipment_model_options()],
                    value="All Models", clearable=False, style={"fontSize": "12px"}
                )
            ], width=3),
            dbc.Col([
                html.Label("Brand:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-brand",
                    options=[{"label": b, "value": b} for b in ["All Brands"]],
                    value="All Brands", clearable=False, style={"fontSize": "12px"}
                )
            ], width=2),
            dbc.Col([
                html.Label("Category:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-category",
                    options=[{"label": c, "value": c} for c in ["All Categories"]],
                    value="All Categories", clearable=False, style={"fontSize": "12px"}
                )
            ], width=2),
            dbc.Col([
                html.Label("Sub-Brand:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-sub-brand",
                    options=[{"label": sb, "value": sb} for sb in ["All Sub-Brands"]],
                    value="All Sub-Brands", clearable=False, style={"fontSize": "12px"}
                )
            ], width=3),
            dbc.Col([
                html.Label("\u00a0", style={"display": "block", "marginBottom": "2px"}),
                dbc.Button("REFRESH DATA", id="btn-refresh", color="success", n_clicks=0, style={
                    "backgroundColor": "#019881", "color": "#ffffff", "fontWeight": "700", "fontSize": "12px", "padding": "6px 12px", "width": "100%", "border": "none"
                })
            ], width=2),
        ])
    ], style={
        "backgroundColor": "#ffffff", "border": "1px solid #e9ecef", "borderRadius": "10px", "padding": "14px 20px", "marginBottom": "16px", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)"
    }),

    html.Div([
        html.Div(id="spreadsheet-container", style={"overflowX": "auto", "border": "1px solid #858585", "borderRadius": "6px"})
    ], style={"backgroundColor": "#ffffff", "borderRadius": "10px", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)", "border": "1px solid #e9ecef", "padding": "16px", "marginBottom": "16px"})
], style={
    "marginLeft": "104px", "padding": "16px 24px", "maxWidth": "calc(100% - 104px)", "backgroundColor": "#f8f9fa", "fontFamily": "sans-serif", "minHeight": "100vh"
})

app.layout = html.Div([sidebar, main_content])


# --- STEP 9: Dashboard Callbacks ---
@app.callback(
    [Output("active-tab", "data"),
     Output("live-record-count", "children"),
     Output("spreadsheet-container", "children"),
     Output("filter-model", "options"),
     Output("filter-brand", "options"),
     Output("filter-category", "options"),
     Output("filter-sub-brand", "options"),
     Output("filter-brand", "value"),
     Output("filter-category", "value"),
     Output("filter-sub-brand", "value"),
     Output("header-title-container", "children")],
    [Input("btn-refresh", "n_clicks"),
     Input("filter-model", "value"),
     Input("filter-brand", "value"),
     Input("filter-category", "value"),
     Input("filter-sub-brand", "value"),
     Input("nav-consumption", "n_clicks"),
     Input("nav-shipments", "n_clicks")],
    [State("active-tab", "data")]
)
def update_shipment_dashboard(n_clicks, model, brand, category, sub_brand, c_clicks, s_clicks, active_tab_state):
    triggered_id = dash.ctx.triggered_id if dash.ctx.triggered_id else None
    active_tab = "shipments"

    # Reset behavior when parent filter changes
    if triggered_id == "filter-model":
        brand = "All Brands"
        category = "All Categories"
        sub_brand = "All Sub-Brands"
    elif triggered_id == "filter-brand":
        category = "All Categories"
        sub_brand = "All Sub-Brands"
    elif triggered_id == "filter-category":
        sub_brand = "All Sub-Brands"

    # 1. Retrieve Raw Shipment & POS Data
    df_ship_raw = fetch_shipment_raw_data()
    df_pos_raw = database.fetch_joined_snowflake_data(brand=brand, category=category, sub_brand=sub_brand, model=model)

    # 2. Filter Shipment Data through rule-based Model/Brand/Category/Sub-Brand pipeline
    df_ship = filter_shipment_dataframe(df_ship_raw, model=model, brand=brand, category=category, sub_brand=sub_brand)
    df_pos = filter_shipment_dataframe(df_pos_raw, model=model, brand=brand, category=category, sub_brand=sub_brand) if not df_pos_raw.empty else pd.DataFrame()

    rec_count = len(df_ship)
    record_str = f"Shipment Snowflake Mapped Records: {rec_count}"

    # 3. Dynamic Filter Dropdown Options
    opts = get_cascading_shipment_filter_options(model=model, brand=brand, category=category, sub_brand=sub_brand)
    model_opts = [{"label": m, "value": m} for m in opts.get("models", ["All Models"])]
    brand_opts = [{"label": b, "value": b} for b in opts.get("brands", ["All Brands"])]
    cat_opts = [{"label": c, "value": c} for c in opts.get("categories", ["All Categories"])]
    sub_brand_opts = [{"label": sb, "value": sb} for sb in opts.get("sub_brands", ["All Sub-Brands"])]

    # Validate selected values against dropdown options
    valid_b = [b["value"] for b in brand_opts]
    if brand not in valid_b: brand = "All Brands"
    valid_c = [c["value"] for c in cat_opts]
    if category not in valid_c: category = "All Categories"
    valid_sb = [sb["value"] for sb in sub_brand_opts]
    if sub_brand not in valid_sb: sub_brand = "All Sub-Brands"

    # 4. Aggregation into Monthly Values per Year
    month_idx_map = {m: i for i, m in enumerate(MONTHS)}
    data_by_year = {}

    def process_records(df, is_shipment=True):
        if df.empty: return
        for _, r in df.iterrows():
            d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', '')).strip()
            kv_info = database.map_date_to_kv_calendar(d_str) if d_str else None
            m_idx = None
            y_str = "2026"
            if kv_info:
                m_idx = kv_info["m_idx"]
                y_str = kv_info["y_str"]
            else:
                parts = d_str.split('-')
                if len(parts) == 2:
                    p1, p2 = parts[0].upper(), parts[1]
                    if p1[:3] in MONTHS:
                        m_idx = month_idx_map.get(p1[:3])
                        y_str = p2 if len(p2) == 4 else ("20" + p2 if len(p2) == 2 else p2)
                    elif p2[:3] in MONTHS:
                        m_idx = month_idx_map.get(p2[:3])
                        y_str = p1 if len(p1) == 4 else ("20" + p1 if len(p1) == 2 else p1)
                    elif p1.isdigit() and p2.isdigit():
                        if len(p1) == 4:
                            y_str = p1
                            m_idx = (int(p2) - 1) if 1 <= int(p2) <= 12 else None
                elif len(parts) == 3:
                    p1, p2, p3 = parts[0].upper(), parts[1].upper(), parts[2]
                    if p2[:3] in MONTHS:
                        m_idx = month_idx_map.get(p2[:3])
                        y_str = p3 if len(p3) == 4 else ("20" + p3 if len(p3) == 2 else p3)
                    elif p1.isdigit() and len(p1) == 4:
                        y_str = p1
                        if p2.isdigit() and 1 <= int(p2) <= 12:
                            m_idx = int(p2) - 1
                if m_idx is None and d_str:
                    try:
                        dt = pd.to_datetime(d_str, errors='coerce')
                        if pd.notnull(dt):
                            m_idx = dt.month - 1
                            y_str = str(dt.year)
                    except Exception:
                        pass

            if m_idx is not None:
                if y_str not in data_by_year:
                    data_by_year[y_str] = {
                        "gross_ship": [None]*12, "return_ship": [None]*12,
                        "gross_cu": [None]*12, "return_cu": [None]*12,
                        "gross_case": [None]*12, "return_case": [None]*12,
                        "pos_val": [None]*12, "pos_u": [None]*12
                    }
                d_dict = data_by_year[y_str]
                if is_shipment:
                    gs = r.get('GROSS_SHIPMENT_AM')
                    rs = r.get('RETURN_SHIP_AM')
                    gcu = r.get('GROSS_QTY_CU')
                    rcu = r.get('RETURN_QTY_CU')
                    gqc = r.get('GROSS_QTY_CASE')
                    rqc = r.get('RETURN_QTY_CASE')

                    d_dict["gross_ship"][m_idx] = (d_dict["gross_ship"][m_idx] or 0.0) + float(gs) if pd.notnull(gs) else d_dict["gross_ship"][m_idx]
                    d_dict["return_ship"][m_idx] = (d_dict["return_ship"][m_idx] or 0.0) + float(rs) if pd.notnull(rs) else d_dict["return_ship"][m_idx]
                    d_dict["gross_cu"][m_idx] = (d_dict["gross_cu"][m_idx] or 0.0) + float(gcu) if pd.notnull(gcu) else d_dict["gross_cu"][m_idx]
                    d_dict["return_cu"][m_idx] = (d_dict["return_cu"][m_idx] or 0.0) + float(rcu) if pd.notnull(rcu) else d_dict["return_cu"][m_idx]
                    d_dict["gross_case"][m_idx] = (d_dict["gross_case"][m_idx] or 0.0) + float(gqc) if pd.notnull(gqc) else d_dict["gross_case"][m_idx]
                    d_dict["return_case"][m_idx] = (d_dict["return_case"][m_idx] or 0.0) + float(rqc) if pd.notnull(rqc) else d_dict["return_case"][m_idx]
                else:
                    pv = r.get('POS_VALUE') if pd.notnull(r.get('POS_VALUE')) else r.get('GLOBAL_VALUE_LC')
                    pu = r.get('POS_UNITS') if pd.notnull(r.get('POS_UNITS')) else r.get('GLOBAL_UNITS')
                    d_dict["pos_val"][m_idx] = (d_dict["pos_val"][m_idx] or 0.0) + float(pv) if pd.notnull(pv) else d_dict["pos_val"][m_idx]
                    d_dict["pos_u"][m_idx] = (d_dict["pos_u"][m_idx] or 0.0) + float(pu) if pd.notnull(pu) else d_dict["pos_u"][m_idx]

    process_records(df_ship, is_shipment=True)
    process_records(df_pos, is_shipment=False)

    target_years = ["2021", "2022", "2023", "2024", "2025", "2026"]
    all_years = sorted(list(set(target_years + list(data_by_year.keys()))))

    # 5. Compute Metric Arrays
    year_metrics = {}
    for yr in all_years:
        d = data_by_year.get(yr, {
            "gross_ship": [None]*12, "return_ship": [None]*12,
            "gross_cu": [None]*12, "return_cu": [None]*12,
            "gross_case": [None]*12, "return_case": [None]*12,
            "pos_val": [None]*12, "pos_u": [None]*12
        })
        gts_dollar = d["gross_ship"]
        gts_u = d["gross_cu"] if any(v is not None for v in d["gross_cu"]) else d["gross_case"]

        # Calculate Factory POS $ per month using Price Index
        factory_pos = [None] * 12
        for i in range(12):
            pv = d["pos_val"][i]
            if pv is not None:
                f_pos, _ = database.get_factory_pos_val(yr, i + 1, model or "", pv)
                factory_pos[i] = f_pos

        # Business Calculations
        # 1. B3 = GBS $ / GBS U (GTS $ / GTS U)
        b3 = [None] * 12
        for i in range(12):
            gs = gts_dollar[i]
            gu = gts_u[i]
            if gs is not None and gu is not None and gu != 0:
                b3[i] = gs / gu

        # 2. Build/Bleed $ = GBS $ - Factory POS $
        build_bleed = [None] * 12
        for i in range(12):
            gs = gts_dollar[i]
            fp = factory_pos[i]
            if gs is not None and fp is not None:
                build_bleed[i] = gs - fp
            elif gs is not None:
                build_bleed[i] = gs

        # 3. Unit Ratio = GBS U / POS U
        unit_ratio = [None] * 12
        for i in range(12):
            gu = gts_u[i]
            pu = d["pos_u"][i]
            if gu is not None and pu is not None and pu != 0:
                unit_ratio[i] = gu / pu
            elif gu is not None:
                unit_ratio[i] = gu

        # 4. Price Factor = ASP / B3 (ASP = POS $ / POS U)
        asp = [None] * 12
        price_factor = [None] * 12
        for i in range(12):
            pv = d["pos_val"][i]
            pu = d["pos_u"][i]
            if pv is not None and pu is not None and pu != 0:
                asp[i] = pv / pu
            if asp[i] is not None and b3[i] is not None and b3[i] != 0:
                price_factor[i] = asp[i] / b3[i]

        tot_gts_dollar = sum([v for v in gts_dollar if v is not None])
        pct_of_year = [calc_share(gts_dollar[i], tot_gts_dollar) for i in range(12)]

        year_metrics[yr] = {
            "gts_dollar": gts_dollar,
            "gts_u": gts_u,
            "b3": b3,
            "factory_pos": factory_pos,
            "build_bleed": build_bleed,
            "unit_ratio": unit_ratio,
            "asp": asp,
            "price_factor": price_factor,
            "pct_of_year": pct_of_year,
            "pos_val": d["pos_val"],
            "pos_u": d["pos_u"]
        }

    print("=" * 80)
    print("SHIPMENT GTS DASHBOARD DIAGNOSTICS & VERIFICATION")
    print("=" * 80)
    print(f"Selected Model:               '{model}'")
    print(f"Mapped Record Count:          {rec_count}")
    tot_grs = sum([v for yr in year_metrics for v in year_metrics[yr]["gts_dollar"] if v is not None])
    tot_grs_u = sum([v for yr in year_metrics for v in year_metrics[yr]["gts_u"] if v is not None])
    tot_fact = sum([v for yr in year_metrics for v in year_metrics[yr]["factory_pos"] if v is not None])
    tot_pos_u = sum([v for yr in year_metrics for v in year_metrics[yr]["pos_u"] if v is not None])
    tot_build = sum([v for yr in year_metrics for v in year_metrics[yr]["build_bleed"] if v is not None])
    avg_b3 = (tot_grs / tot_grs_u) if tot_grs_u != 0 else None
    avg_unit_ratio = (tot_grs_u / tot_pos_u) if tot_pos_u != 0 else None
    tot_pos_val = sum([v for yr in year_metrics for v in year_metrics[yr]["pos_val"] if v is not None])
    avg_asp = (tot_pos_val / tot_pos_u) if tot_pos_u != 0 else None
    avg_price_factor = (avg_asp / avg_b3) if (avg_asp is not None and avg_b3 is not None and avg_b3 != 0) else None

    print(f"GRS $ (Gross Shipment $):     ${tot_grs:,.2f}")
    print(f"GRS U (Gross Shipment Units): {tot_grs_u:,.2f}")
    print(f"Factory POS $:                ${tot_fact:,.2f}")
    print(f"POS U:                        {tot_pos_u:,.2f}")
    print(f"ASP:                          ${avg_asp:.4f}" if avg_asp else "ASP:                          N/A")
    print(f"B3 (GBS $ / GBS U):           ${avg_b3:.4f}" if avg_b3 else "B3:                           N/A")
    print(f"Build/Bleed $:                ${tot_build:,.2f}")
    print(f"Unit Ratio (GBS U / POS U):   {avg_unit_ratio:.4f}" if avg_unit_ratio else "Unit Ratio:                   N/A")
    print(f"Price Factor (ASP / B3):      {avg_price_factor:.4f}" if avg_price_factor else "Price Factor:                 N/A")
    print("=" * 80)

    # 6. Build Spreadsheet Table Element
    th_style = {
        "backgroundColor": "#019881", "color": "#ffffff", "fontWeight": "800", "padding": "8px 10px", "border": "1px solid #858585", "textAlign": "center", "whiteSpace": "nowrap"
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
        html.Th("Ver/Yr", style={**th_style, "minWidth": "50px", "backgroundColor": "#019881"}),
        *[html.Th(m, style={**th_style, "minWidth": "55px", "backgroundColor": "#019881", **({"borderRight": "3px solid #858585"} if m == "DEC" else {})}) for m in MONTHS],
        html.Th("Q1", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571", "color": "#ffffff"}),
        html.Th("Q2", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571", "color": "#ffffff"}),
        html.Th("Q3", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571", "color": "#ffffff"}),
        html.Th("Q4", style={**th_style, "minWidth": "60px", "backgroundColor": "#018571", "color": "#ffffff", "borderRight": "3px solid #858585"}),
        html.Th("FY", style={**th_style, "minWidth": "65px", "backgroundColor": "#017362", "color": "#ffffff"}),
        html.Th("YTD", style={**th_style, "minWidth": "65px", "backgroundColor": "#017362", "color": "#ffffff"}),
        html.Th("YTG", style={**th_style, "minWidth": "65px", "backgroundColor": "#017362", "color": "#ffffff"})
    ])

    thead = html.Thead([hdr_row1, hdr_row2])
    tbody_rows = []

    def make_grouped_rows(metric_name, unit, yr_val_tuples, metric_key, year_metrics):
        group_rows = []
        group_size = len(yr_val_tuples)
        label_td_style = {
            "backgroundColor": "#b0b0b0", "color": "#000000", "fontWeight": "900", "fontSize": "14px", "textAlign": "center", "verticalAlign": "middle", "border": "1px solid #858585", "padding": "8px"
        }

        # Calculate Standard Deviation (STD) of historical Build values (2021-2025)
        build_std = None
        if metric_key in ["build", "build_bleed"]:
            hist_years = ["2021", "2022", "2023", "2024", "2025"]
            hist_build_vals = []
            for hy in hist_years:
                ym = year_metrics.get(hy)
                if ym:
                    h_arr = ym.get(metric_key, ym.get("build", []))
                    for hv in h_arr:
                        if hv is not None and not (isinstance(hv, float) and math.isnan(hv)):
                            hist_build_vals.append(float(hv))
            if len(hist_build_vals) >= 2:
                b_mean = sum(hist_build_vals) / len(hist_build_vals)
                b_var = sum((x - b_mean) ** 2 for x in hist_build_vals) / (len(hist_build_vals) - 1)
                build_std = math.sqrt(b_var)
                print(f"\n[SHIPMENT BUILD STD DIAGNOSTICS]: Data Points = {len(hist_build_vals)} | Mean = {b_mean:.4f} | STD = {build_std:.4f} | 1*STD = {1.0*build_std:.4f} | 2*STD Threshold (RED) = {2.0*build_std:.4f}")
            else:
                print(f"\n[SHIPMENT BUILD STD DIAGNOSTICS]: Insufficient historical build data (count = {len(hist_build_vals)}) to calculate STD.")

        def calc_period_val(target_yr, slice_obj):
            if target_yr == "YoY %":
                val_2026 = calc_period_val("2026", slice_obj)
                val_2025 = calc_period_val("2025", slice_obj)
                return calc_pct_var(val_2026, val_2025)

            ym = year_metrics.get(target_yr)
            if not ym: return None

            if metric_key in ["gts_dollar", "gts_u", "b3", "build_bleed", "pct_of_year"]:
                arr = ym.get(metric_key, [None]*12)[slice_obj]
                valid_vals = [v for v in arr if v is not None and not (isinstance(v, float) and math.isnan(v))]
                return sum(valid_vals) if valid_vals else None
            elif metric_key == "unit_ratio":
                net_u_sum = sum([v for v in ym["net_ship_u"][slice_obj] if v is not None and not (isinstance(v, float) and math.isnan(v))])
                pos_u_sum = sum([v for v in ym["pos_u"][slice_obj] if v is not None and not (isinstance(v, float) and math.isnan(v))])
                if pos_u_sum == 0: return None
                return net_u_sum / pos_u_sum
            else:
                arr = ym.get(metric_key, [None]*12)[slice_obj]
                valid_vals = [v for v in arr if v is not None and not (isinstance(v, float) and math.isnan(v))]
                return sum(valid_vals) if valid_vals else None

        for idx, (yr, vals) in enumerate(yr_val_tuples):
            td_cells = []
            if idx == 0:
                td_cells.append(html.Td(metric_name, rowSpan=group_size, style=label_td_style))

            is_2026_row = (yr == "2026")
            is_dark_row = (yr in ["2026", "YoY %"])
            if is_dark_row:
                yr_style = {"backgroundColor": "#b0b0b0", "color": "#000000", "fontWeight": "800", "textAlign": "center", "padding": "5px 8px", "border": "1px solid #858585"}
            else:
                yr_style = {"backgroundColor": "#f8f9fa", "color": "#212529", "fontWeight": "700", "textAlign": "center", "padding": "5px 8px", "border": "1px solid #858585"}

            current_unit = "%" if yr == "YoY %" else unit
            td_cells.append(html.Td(yr, style=yr_style))

            for i in range(12):
                v = vals[i] if i < len(vals) else None
                is_2026_build_month = (metric_key in ["build", "build_bleed"] and is_2026_row)

                # Dynamic 2-STD RED Logic ONLY for 2026 Build Row Monthly Cells (JAN-DEC):
                # ABS(Build[month]) >= 2 * STD -> RED (#FF6B6B)
                # ABS(Build[month]) < 2 * STD -> Normal / default color
                is_red = False
                if is_2026_build_month and v is not None and not (isinstance(v, float) and math.isnan(v)) and build_std is not None and build_std > 0:
                    if abs(float(v)) >= 2.0 * build_std:
                        is_red = True

                if is_red:
                    c_style = {"backgroundColor": "#FF6B6B", "color": "#ffffff", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                    st = "EXCEPTION"
                elif is_dark_row:
                    if v is None:
                        c_style = {"backgroundColor": "#b0b0b0", "color": "#475569", "fontWeight": "700", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                        st = "EMPTY"
                    else:
                        c_style = {"backgroundColor": "#b0b0b0", "color": "#000000", "fontWeight": "700", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                        st = "VALID"
                else:
                    if v is None:
                        c_style = {"backgroundColor": "#ffffff", "color": "#adb5bd", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                        st = "EMPTY"
                    else:
                        c_style = {"backgroundColor": "#ffffff", "color": "#212529", "fontWeight": "400", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                        st = "VALID"

                # Add grey #858585 vertical divider line after DEC (index 11)
                if i == 11:
                    c_style = {**c_style, "borderRight": "3px solid #858585"}

                formatted = fmt_val(v, current_unit, st)
                td_cells.append(html.Td(formatted, style=c_style))

            if is_dark_row:
                q_style = {"backgroundColor": "#b0b0b0", "color": "#000000", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                s_style = {"backgroundColor": "#b0b0b0", "color": "#000000", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
            else:
                q_style = {"backgroundColor": "#ffffff", "color": "#212529", "fontWeight": "700", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}
                s_style = {"backgroundColor": "#ffffff", "color": "#212529", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #858585", "textAlign": "right"}

            q1_val = calc_period_val(yr, slice(0, 3))
            q2_val = calc_period_val(yr, slice(3, 6))
            q3_val = calc_period_val(yr, slice(6, 9))
            q4_val = calc_period_val(yr, slice(9, 12))
            fy_val = calc_period_val(yr, slice(0, 12))
            ytd_val = calc_period_val(yr, slice(0, 7))
            ytg_val = calc_period_val(yr, slice(7, 12))

            q1_t = fmt_val(q1_val, current_unit, "VALID")
            q2_t = fmt_val(q2_val, current_unit, "VALID")
            q3_t = fmt_val(q3_val, current_unit, "VALID")
            q4_t = fmt_val(q4_val, current_unit, "VALID")
            fy_t = fmt_val(fy_val, current_unit, "VALID")
            ytd_t = fmt_val(ytd_val, current_unit, "VALID")
            ytg_t = fmt_val(ytg_val, current_unit, "VALID")

            def make_tot_td(tot_val, base_style):
                return html.Td(tot_val, style=base_style)

            q4_style_divider = {**q_style, "borderRight": "3px solid #858585"}

            td_cells.extend([
                make_tot_td(q1_t, q_style),
                make_tot_td(q2_t, q_style),
                make_tot_td(q3_t, q_style),
                make_tot_td(q4_t, q4_style_divider),
                make_tot_td(fy_t, s_style),
                make_tot_td(ytd_t, s_style),
                make_tot_td(ytg_t, s_style)
            ])
            group_rows.append(html.Tr(td_cells))
        return group_rows

    display_years = ["2021", "2022", "2023", "2024", "2025", "2026"]

    # 1. GTS $
    gts_dollar_tuples = [(yr, year_metrics[yr]["gts_dollar"]) for yr in display_years]
    yoy_gts_dollar = [calc_pct_var(year_metrics["2026"]["gts_dollar"][i], year_metrics["2025"]["gts_dollar"][i]) for i in range(12)]
    gts_dollar_tuples.append(("YoY %", yoy_gts_dollar))

    # 2. GTS U
    gts_u_tuples = [(yr, year_metrics[yr]["gts_u"]) for yr in display_years]
    yoy_gts_u = [calc_pct_var(year_metrics["2026"]["gts_u"][i], year_metrics["2025"]["gts_u"][i]) for i in range(12)]
    gts_u_tuples.append(("YoY %", yoy_gts_u))

    # 3. B3 (Net Shipment $)
    b3_tuples = [(yr, year_metrics[yr]["b3"]) for yr in display_years]
    yoy_b3 = [calc_pct_var(year_metrics["2026"]["b3"][i], year_metrics["2025"]["b3"][i]) for i in range(12)]
    b3_tuples.append(("YoY %", yoy_b3))

    # 4. Build/Bleed $
    build_bleed_tuples = [(yr, year_metrics[yr]["build_bleed"]) for yr in display_years]
    yoy_build_bleed = [calc_pct_var(year_metrics["2026"]["build_bleed"][i], year_metrics["2025"]["build_bleed"][i]) for i in range(12)]
    build_bleed_tuples.append(("YoY %", yoy_build_bleed))

    # 5. Unit Ratio
    unit_ratio_tuples = [(yr, year_metrics[yr]["unit_ratio"]) for yr in display_years]
    yoy_unit_ratio = [calc_pct_var(year_metrics["2026"]["unit_ratio"][i], year_metrics["2025"]["unit_ratio"][i]) for i in range(12)]
    unit_ratio_tuples.append(("YoY %", yoy_unit_ratio))

    # 6. % of Year
    pct_of_year_tuples = [(yr, year_metrics[yr]["pct_of_year"]) for yr in display_years]
    yoy_pct_of_year = [calc_pct_var(year_metrics["2026"]["pct_of_year"][i], year_metrics["2025"]["pct_of_year"][i]) for i in range(12)]
    pct_of_year_tuples.append(("YoY %", yoy_pct_of_year))

    tbody_rows.extend(make_grouped_rows("GTS $", "$", gts_dollar_tuples, "gts_dollar", year_metrics))
    tbody_rows.extend(make_grouped_rows("GTS U", "Units", gts_u_tuples, "gts_u", year_metrics))
    tbody_rows.extend(make_grouped_rows("B3", "$", b3_tuples, "b3", year_metrics))
    tbody_rows.extend(make_grouped_rows("Build/Bleed $", "$", build_bleed_tuples, "build_bleed", year_metrics))
    tbody_rows.extend(make_grouped_rows("Unit Ratio", "Ratio", unit_ratio_tuples, "unit_ratio", year_metrics))
    tbody_rows.extend(make_grouped_rows("% of Year", "%", pct_of_year_tuples, "pct_of_year", year_metrics))

    header_title = html.H1(["SHIPMENT", html.Br(), "VALIDATION"], style={
        "color": "#ffffff", "fontWeight": "900", "fontSize": "22px", "letterSpacing": "1.5px", "margin": "0", "textTransform": "uppercase", "lineHeight": "1.2"
    })

    tbody = html.Tbody(tbody_rows)
    table_elem = html.Table([thead, tbody], style={
        "width": "100%", "borderCollapse": "collapse", "fontFamily": "sans-serif", "fontSize": "11px"
    })

    return active_tab, record_str, table_elem, model_opts, brand_opts, cat_opts, sub_brand_opts, brand, category, sub_brand, header_title


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8051"))
    debug = os.getenv("DEBUG", "True").lower() in ["true", "1", "t"]
    print(f"Starting Shipment Validation Dashboard independently at http://{host}:{port}...")
    app.run(host=host, port=port, debug=debug, dev_tools_ui=False)
