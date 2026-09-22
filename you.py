import os
import math
import statistics
import base64
import flask
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
 
import database
 
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Consumption Validation Dashboard"
)
server = app.server
 
# Explicit File Paths for Assets (Can be overridden via environment variables or modified directly here)
LOGO_PATH = os.getenv("LOGO_PATH", r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\assests\logo.png")
CONSUMPTION_ICON_PATH = os.getenv("CONSUMPTION_ICON_PATH", r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\assests\consumption.png")
SHIPMENT_ICON_PATH = os.getenv("SHIPMENT_ICON_PATH", r"C:\Users\maniav1\OneDrive - Kenvue Brands LLC\Desktop\Dashboard\assests\shipment.png")
 
 
def get_asset_src(path_or_filename: str) -> str:
    """
    Encodes an image file as a Base64 data URI given its full file path or filename.
    Resolves explicit full file path directly, or falls back to local project 'assests/' folder.
    """
    filepath = path_or_filename
    if not os.path.exists(filepath):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        fname = os.path.basename(path_or_filename)
        cand = os.path.join(base_dir, "assests", fname)
        if os.path.exists(cand):
            filepath = cand
 
    if os.path.exists(filepath):
        try:
            with open(filepath, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                ext = os.path.splitext(filepath)[1].lower().replace(".", "")
                mime = f"image/{ext}" if ext in ["png", "jpeg", "jpg", "gif", "svg"] else "image/png"
                return f"data:{mime};base64,{b64}"
        except Exception:
            pass
 
    return f"/assests/{os.path.basename(path_or_filename)}"
 
 
@server.route('/assests/<path:filename>')
def serve_assests(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_assests = os.path.join(base_dir, "assests")
    if os.path.exists(local_assests):
        return flask.send_from_directory(local_assests, filename)
    default_dir = os.path.dirname(LOGO_PATH)
    if os.path.exists(default_dir):
        return flask.send_from_directory(default_dir, filename)
    return "", 404
 
 
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
 
 
def calc_net(gross, ret):
    if gross is None:
        return None
    return gross - (ret if ret is not None else 0.0)
 
 
def calc_asp(pos_val, pos_units):
    if pos_val is None or pos_units is None or pos_units == 0:
        return None
    return pos_val / pos_units
 
 
def calc_variance(actual, comparison):
    if actual is None or comparison is None:
        return None
    return actual - comparison
 
 
def calc_pct_var(actual, comparison):
    if actual is None or comparison is None or comparison == 0:
        return None
    return ((actual - comparison) / abs(comparison)) * 100.0
 
 
def calc_share(month_val, total_val):
    if month_val is None or total_val is None or total_val == 0:
        return None
    return (month_val / total_val) * 100.0
 
 
def fmt_val(val, unit, status):
    if status == "EMPTY" or val is None or math.isnan(val):
        return ""
    if unit == "$M":
        val_m = val / 1_000_000.0
        if val_m < 0:
            return f"-${abs(val_m):,.1f}"
        return f"${val_m:,.1f}"
    elif unit == "UnitsM":
        val_m = val / 1_000_000.0
        return f"{val_m:,.1f}"
    elif unit == "$":
        if val < 0:
            abs_v = abs(val)
            if isinstance(abs_v, float) and abs_v != int(abs_v) and abs_v < 1000 and round(abs_v, 2) != round(abs_v, 0):
                return f"-${abs_v:,.2f}"
            return f"-${abs_v:,.0f}"
        else:
            if isinstance(val, float) and val != int(val) and abs(val) < 1000 and round(val, 2) != round(val, 0):
                return f"${val:,.2f}"
            return f"${val:,.0f}"
    elif unit == "Units":
        return f"{val:,.0f}"
    elif unit == "%":
        return f"{val:.1f}%"
    elif unit == "Status":
        return status
    return f"{val:,.2f}"
 
 
filter_opts = database.get_filter_options()
 
sidebar = html.Div([
    dcc.Store(id="active-tab", data="consumption"),
    dcc.Store(id="loaded-dashboard-data", data=None),
    html.Div([
        html.Img(
            src=get_asset_src(LOGO_PATH),
            style={"maxHeight": "55px", "maxWidth": "125px", "objectFit": "contain"}
        )
    ], style={"marginTop": "24px", "marginBottom": "40px", "textAlign": "center", "width": "100%"}),
 
    html.Div([
        dbc.Button([
            html.Img(
                src=get_asset_src(CONSUMPTION_ICON_PATH),
                style={"width": "44px", "height": "44px", "marginBottom": "8px", "pointerEvents": "none"}
            ),
            html.Span("Consumption", style={
                "color": "#ffffff", "fontSize": "16px", "fontWeight": "700", "textAlign": "center", "lineHeight": "1.2", "pointerEvents": "none"
            })
        ], id="nav-consumption", color="link", n_clicks=0, style={
            "backgroundColor": "#00B097",
            "width": "134px",
            "padding": "12px 8px",
            "minHeight": "105px",
            "borderRadius": "12px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "cursor": "pointer",
            "boxShadow": "0 2px 6px rgba(0,0,0,0.2)",
            "border": "none",
            "textDecoration": "none"
        }),
 
        dbc.Button([
            html.Img(
                src=get_asset_src(SHIPMENT_ICON_PATH),
                style={"width": "44px", "height": "44px", "marginBottom": "8px", "pointerEvents": "none"}
            ),
            html.Span("Shipment", style={
                "color": "#ffffff", "fontSize": "16px", "fontWeight": "700", "textAlign": "center", "lineHeight": "1.2", "pointerEvents": "none"
            })
        ], id="nav-shipments", color="link", n_clicks=0, style={
            "width": "134px",
            "padding": "12px 8px",
            "minHeight": "105px",
            "borderRadius": "12px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "justifyContent": "center",
            "cursor": "pointer",
            "opacity": "0.85",
            "backgroundColor": "transparent",
            "border": "none",
            "textDecoration": "none"
        })
    ], style={"display": "flex", "flexDirection": "column", "gap": "24px", "alignItems": "center", "width": "100%"})
], style={
    "position": "fixed",
    "top": "0",
    "left": "0",
    "bottom": "0",
    "width": "156px",
    "backgroundColor": "#00B097",
    "zIndex": "1000",
    "display": "flex",
    "flexDirection": "column",
    "alignItems": "center",
    "boxShadow": "2px 0 10px rgba(0,0,0,0.15)"
})
 
main_content = html.Div([
    html.Div([
        html.Span(id="live-record-count", style={"display": "none"}),
 
        dbc.Row([
            dbc.Col([
                html.Label("GBU:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-gbu",
                    options=[{"label": g, "value": g} for g in filter_opts.get("gbus", ["Select GBU"])],
                    value="Select GBU", clearable=False, style={"fontSize": "12px"}
                )
            ], width=3),
            dbc.Col([
                html.Label("Need State:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-squad",
                    options=[{"label": "Select Need State", "value": "Select Need State"}],
                    value="Select Need State", disabled=True, clearable=False, style={"fontSize": "12px"}
                )
            ], width=4),
            dbc.Col([
                html.Label("Model:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-model",
                    options=[{"label": "Select Model", "value": "Select Model"}],
                    value="Select Model", disabled=True, clearable=False, style={"fontSize": "12px"}
                )
            ], width=3),
            dbc.Col([
                html.Label("\u00a0", style={"display": "block", "marginBottom": "2px"}),
                dbc.Button("REFRESH DATA", id="btn-refresh", color="success", n_clicks=0, disabled=True, style={
                    "backgroundColor": "#6c757d", "color": "#ffffff", "fontWeight": "700", "fontSize": "12px", "padding": "6px 12px", "width": "100%", "border": "none", "cursor": "not-allowed", "opacity": "0.6"
                })
            ], width=2),
        ])
    ], style={
        "backgroundColor": "#ffffff", "border": "1px solid #e9ecef", "borderRadius": "10px", "padding": "14px 20px", "marginBottom": "16px", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)"
    }),
 
    html.Div([
        html.Div(id="spreadsheet-container", style={"overflowX": "auto", "border": "1px solid #858585", "borderRadius": "6px"})
    ], style={"backgroundColor": "#ffffff", "borderRadius": "10px", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)", "border": "1px solid #e9ecef", "padding": "16px", "marginBottom": "24px"})
], style={
    "marginLeft": "156px",
    "padding": "16px 24px",
    "maxWidth": "calc(100% - 156px)",
    "backgroundColor": "#f8f9fa",
    "fontFamily": "sans-serif",
    "minHeight": "100vh"
})
 
app.layout = html.Div([
    sidebar,
    main_content
])


def parse_date_to_month_year(d_str: str):
    """
    Parses a date string into (m_idx [0-11], y_str).
    Uses data-driven Kenvue Calendar Excel mapping from database.py.
    """
    cal_info = database.map_date_to_kv_calendar(d_str)
    if cal_info:
        return cal_info["m_idx"], cal_info["y_str"]
    print(f"[WARNING]: Kenvue Calendar mapping not found for date '{d_str}'. Skipping unmapped record.")
    return None, None
 
 
@app.callback(
    [Output("active-tab", "data"),
     Output("loaded-dashboard-data", "data"),
     Output("live-record-count", "children"),
     Output("spreadsheet-container", "children"),
     Output("filter-gbu", "options"),
     Output("filter-squad", "options"),
     Output("filter-model", "options"),
     Output("filter-gbu", "value"),
     Output("filter-squad", "value"),
     Output("filter-model", "value"),
     Output("filter-squad", "disabled"),
     Output("filter-model", "disabled"),
     Output("btn-refresh", "disabled"),
     Output("btn-refresh", "style"),
     Output("nav-consumption", "style"),
     Output("nav-shipments", "style")],
    [Input("btn-refresh", "n_clicks"),
     Input("filter-gbu", "value"),
     Input("filter-squad", "value"),
     Input("filter-model", "value"),
     Input("nav-consumption", "n_clicks"),
     Input("nav-shipments", "n_clicks")],
    [State("active-tab", "data"),
     State("loaded-dashboard-data", "data")]
)
def update_dashboard(n_clicks, gbu, squad, model, c_clicks, s_clicks, active_tab_state, loaded_dashboard_state):
    triggered_id = dash.ctx.triggered_id if dash.ctx.triggered_id else None
    if triggered_id == "nav-shipments":
        active_tab = "shipments"
    elif triggered_id == "nav-consumption":
        active_tab = "consumption"
    else:
        active_tab = active_tab_state if active_tab_state else "consumption"
 
    if triggered_id == "filter-gbu":
        squad = "Select Need State"
        model = "Select Model"
    elif triggered_id == "filter-squad":
        model = "Select Model"
 
    gbu_norm = database.normalize_text(gbu)
    is_gbu_valid = bool(gbu and gbu_norm not in database.IGNORED_PLACEHOLDERS)
    squad_disabled = not is_gbu_valid
 
    opts = database.get_filter_options(gbu=gbu, squad=squad, model=model)
 
    gbu_opts = [{"label": g, "value": g} for g in opts.get("gbus", ["Select GBU"])]
    valid_gbus_norm = [database.normalize_text(g["value"]) for g in gbu_opts]
    if database.normalize_text(gbu) not in valid_gbus_norm:
        gbu = "Select GBU"
        is_gbu_valid = False
        squad_disabled = True

    if is_gbu_valid:
        squad_opts = [{"label": s, "value": s} for s in opts.get("squads", ["Select Need State"])]
        if squad and database.normalize_text(squad) not in database.IGNORED_PLACEHOLDERS:
            if not any(database.normalize_text(s["value"]) == database.normalize_text(squad) for s in squad_opts):
                squad_opts.append({"label": squad, "value": squad})
    else:
        squad_opts = [{"label": "Select Need State", "value": "Select Need State"}]
        squad = "Select Need State"

    squad_norm = database.normalize_text(squad)
    is_squad_valid = bool(squad and squad_norm not in database.IGNORED_PLACEHOLDERS)
    model_disabled = not (is_gbu_valid and is_squad_valid)

    if is_gbu_valid and is_squad_valid:
        model_opts = [{"label": m, "value": m} for m in opts.get("models", ["Select Model"])]
        if model and database.normalize_text(model) not in database.IGNORED_PLACEHOLDERS:
            if not any(database.normalize_text(m["value"]) == database.normalize_text(model) for m in model_opts):
                model_opts.append({"label": model, "value": model})
    else:
        model_opts = [{"label": "Select Model", "value": "Select Model"}]
        model = "Select Model"

    model_norm = database.normalize_text(model)
    is_model_valid = bool(model and model_norm not in database.IGNORED_PLACEHOLDERS)
 
    can_refresh = (is_gbu_valid and is_squad_valid and is_model_valid)
    btn_disabled = not can_refresh
 
    btn_style = {
        "backgroundColor": "#019881" if can_refresh else "#6c757d",
        "color": "#ffffff",
        "fontWeight": "700",
        "fontSize": "12px",
        "padding": "6px 12px",
        "width": "100%",
        "border": "none",
        "cursor": "pointer" if can_refresh else "not-allowed",
        "opacity": "1.0" if can_refresh else "0.6"
    }
 
    should_fetch_snowflake = (triggered_id == "btn-refresh" and can_refresh)
 
    print("=" * 70)
    print("DASHBOARD CALLBACK DIAGNOSTICS")
    print("=" * 70)
    print(f"Triggered ID:                 '{triggered_id}'")
    print(f"Selected GBU:                 '{gbu}' (Valid: {is_gbu_valid})")
    print(f"Selected Need State:          '{squad}' (Valid: {is_squad_valid}, Disabled: {squad_disabled})")
    print(f"Selected Model:               '{model}' (Valid: {is_model_valid}, Disabled: {model_disabled})")
    print(f"Can Refresh (Button Enabled): {can_refresh}")
    print(f"Fetching Snowflake POS Data:  {should_fetch_snowflake}")
    print("=" * 70)
 
    current_loaded_store = loaded_dashboard_state

    if should_fetch_snowflake:
        df = database.fetch_joined_snowflake_data(gbu=gbu, squad=squad, model=model)
        rec_count = len(df)
        record_str = f"Snowflake Mapped Records: {rec_count} | Read-Only"
        if not df.empty:
            current_loaded_store = {
                "records": df.to_dict("records"),
                "rec_count": rec_count,
                "gbu": gbu,
                "squad": squad,
                "model": model
            }
        else:
            current_loaded_store = None
    else:
        # Filter changes / Tab switches: DO NOT query Snowflake. Use stored dashboard dataset if available.
        if current_loaded_store and isinstance(current_loaded_store, dict) and "records" in current_loaded_store:
            df = pd.DataFrame(current_loaded_store["records"])
            rec_count = current_loaded_store.get("rec_count", len(df))
            loaded_model = current_loaded_store.get("model", "Loaded Model")
            record_str = f"Snowflake Mapped Records: {rec_count} | Read-Only (Loaded for '{loaded_model}')"
        else:
            df = pd.DataFrame()
            record_str = "Filter Selection (PostgreSQL Hierarchy - Click REFRESH DATA to fetch Snowflake)"
 
    active_nav_style = {
        "backgroundColor": "#019881",
        "color": "#ffffff",
        "width": "134px",
        "padding": "12px 8px",
        "minHeight": "105px",
        "borderRadius": "12px",
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "justifyContent": "center",
        "cursor": "pointer",
        "boxShadow": "0 2px 6px rgba(0,0,0,0.2)",
        "border": "none",
        "textDecoration": "none"
    }
    inactive_nav_style = {
        "backgroundColor": "transparent",
        "color": "#ffffff",
        "width": "134px",
        "padding": "12px 8px",
        "minHeight": "105px",
        "borderRadius": "12px",
        "display": "flex",
        "flexDirection": "column",
        "alignItems": "center",
        "justifyContent": "center",
        "cursor": "pointer",
        "opacity": "0.85",
        "border": "none",
        "textDecoration": "none"
    }
 
    if active_tab == "shipments":
        nav_cons_style = inactive_nav_style
        nav_ship_style = active_nav_style
    else:
        nav_cons_style = active_nav_style
        nav_ship_style = inactive_nav_style
 
    if not df.empty:
        data_by_year = {}
        sample_logs = []
        unmapped_dates = []

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
                    if d_str and d_str not in unmapped_dates:
                        unmapped_dates.append(d_str)
                        print(f"[WARNING]: Authoritative Kenvue Calendar mapping not found for date '{d_str}'. Skipping record.")
                    continue

                m_idx = kv_info["m_idx"]
                y_str = kv_info["y_str"]

            if y_str not in data_by_year:
                data_by_year[y_str] = {
                    "pos_val": [None]*12, "factory_pos": [None]*12, "pos_u": [None]*12,
                    "gross_ship": [None]*12, "return_ship": [None]*12,
                    "gross_case": [None]*12, "return_case": [None]*12,
                    "gross_cu": [None]*12, "return_cu": [None]*12
                }
            d_dict = data_by_year[y_str]
            pv = r.get('POS_VALUE') if pd.notnull(r.get('POS_VALUE')) else r.get('POS_DOLLARS')
            pu = r.get('POS_UNITS')
            gs = r.get('GROSS_SHIPMENT_AM')
            rs = r.get('RETURN_SHIP_AM')
            gqc = r.get('GROSS_QTY_CASE')
            rqc = r.get('RETURN_QTY_CASE')
            gcu = r.get('GROSS_QTY_CU')
            rcu = r.get('RETURN_QTY_CU')

            d_dict["pos_val"][m_idx] = (d_dict["pos_val"][m_idx] or 0.0) + float(pv) if pd.notnull(pv) else d_dict["pos_val"][m_idx]
            d_dict["pos_u"][m_idx] = (d_dict["pos_u"][m_idx] or 0.0) + float(pu) if pd.notnull(pu) else d_dict["pos_u"][m_idx]
            d_dict["gross_ship"][m_idx] = (d_dict["gross_ship"][m_idx] or 0.0) + float(gs) if pd.notnull(gs) else d_dict["gross_ship"][m_idx]
            d_dict["return_ship"][m_idx] = (d_dict["return_ship"][m_idx] or 0.0) + float(rs) if pd.notnull(rs) else d_dict["return_ship"][m_idx]
            d_dict["gross_case"][m_idx] = (d_dict["gross_case"][m_idx] or 0.0) + float(gqc) if pd.notnull(gqc) else d_dict["gross_case"][m_idx]
            d_dict["return_case"][m_idx] = (d_dict["return_case"][m_idx] or 0.0) + float(rqc) if pd.notnull(rqc) else d_dict["return_case"][m_idx]
            d_dict["gross_cu"][m_idx] = (d_dict["gross_cu"][m_idx] or 0.0) + float(gcu) if pd.notnull(gcu) else d_dict["gross_cu"][m_idx]
            d_dict["return_cu"][m_idx] = (d_dict["return_cu"][m_idx] or 0.0) + float(rcu) if pd.notnull(rcu) else d_dict["return_cu"][m_idx]

        # FACTORY POS $ CALCULATION & CONCISE TERMINAL SUMMARY
        pos_monthly_records = []
        for yr_k in sorted(data_by_year.keys()):
            for m_i in range(12):
                pv = data_by_year[yr_k]["pos_val"][m_i]
                if pv is not None:
                    norm_m = f"{yr_k}-{m_i+1:02d}"
                    pos_monthly_records.append({
                        "year": yr_k, "m_nbr": m_i + 1,
                        "norm_m": norm_m, "pos_val": pv
                    })

        print("=" * 70)
        print("FACTORY POS $ CALCULATION")
        print("=" * 70)
        match_count = 0
        missing_count = 0

        for rec in pos_monthly_records:
            yr_key = rec["year"]
            m_nbr = rec["m_nbr"]
            m_i = m_nbr - 1
            pv_val = rec["pos_val"]
            norm_m = rec["norm_m"]

            f_pos, idx_val = database.get_factory_pos_val(yr_key, m_nbr, model, pv_val)
            data_by_year[yr_key]["factory_pos"][m_i] = f_pos

            if idx_val is not None:
                match_count += 1
                pos_str = f"{pv_val:,.2f}"
                idx_str = f"{idx_val:.4f}"
                fac_str = f"{f_pos:,.2f}"
                print(f"{norm_m} | {model:<20} | POS $ {pos_str:>14} | INDEX {idx_str:>6} | FACTORY POS $ {fac_str:>16}")
            else:
                missing_count += 1
                print(f"[MISSING INDEX] {norm_m} | {model:<20} | POS $ {pv_val:,.2f} | INDEX N/A | FACTORY POS $ BLANK")

        print("=" * 70)
        print(f"Total Factory POS records:  {len(pos_monthly_records)}")
        print(f"Successful INDEX matches:   {match_count}")
        print(f"Missing INDEX matches:      {missing_count}")
        print("=" * 70)

        if sample_logs:
            print("=" * 90)
            print("KENVUE FISCAL CALENDAR WEEK-TO-MONTH AGGREGATION DIAGNOSTICS")
            print("=" * 90)
            for log_line in sample_logs[:20]:
                print(log_line)
            print("=" * 90)

        m_name_title = str(model) if model else "SELECTED MODEL"
        for dbg_yr in sorted(list(data_by_year.keys()))[:2]:
            if dbg_yr in data_by_year:
                print("=" * 65)
                print(f"{m_name_title} - KENVUE {dbg_yr}")
                print("=" * 65)
                month_full_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                pos_vals = data_by_year[dbg_yr]["pos_val"]
                pos_units = data_by_year[dbg_yr]["pos_u"]
                for m_i, m_full in enumerate(month_full_names):
                    v = pos_vals[m_i]
                    u = pos_units[m_i]
                    v_str = f"{v:,.2f}" if v is not None else "0.00"
                    u_str = f"{u:,.2f}" if u is not None else "0.00"
                    print(f"{m_full:<10} POS $ = {v_str:>15}    POS U = {u_str:>15}")
                print("=" * 65)

        all_years = sorted([str(yr) for yr in data_by_year.keys() if str(yr).isdigit()])
        if all_years:
            latest_year = all_years[-1]
            prev_year = str(int(latest_year) - 1)
            latest_year_int = int(latest_year)
            hist_years = [str(latest_year_int - 5 + i) for i in range(5)]
            comp_status = database.get_kv_month_completeness_status(df, target_year=latest_year)
            latest_comp_m_nbr = comp_status["latest_complete_m_nbr"]
            ytd_slice = comp_status["ytd_slice"]
            ytg_slice = comp_status["ytg_slice"]
        else:
            latest_year = ""
            prev_year = ""
            hist_years = []
            comp_status = database.get_kv_month_completeness_status(df, target_year=None)
            latest_comp_m_nbr = 0
            ytd_slice = slice(0, 0)
            ytg_slice = slice(0, 12)

        print("=" * 70)
        print("DYNAMIC KENVUE CALENDAR & TIME PERIOD DIAGNOSTICS")
        print("=" * 70)
        print(f"Current Planning Year:       {latest_year}")
        print(f"Previous Year (YoY Compare): {prev_year}")
        print(f"Historical Comparison Years: {hist_years}")
        print(f"Display Years ({len(all_years)}):        {all_years}")
        print(f"Latest Available Week:       {comp_status['latest_available_week']}")
        print(f"Latest Complete Month:       {comp_status['latest_complete_m_name']} (Month {comp_status['latest_complete_m_nbr']})")
        print(f"YTD Period Range:            JAN to {comp_status['latest_complete_m_name']}")
        print(f"YTG Period Range:            {MONTHS[latest_comp_m_nbr] if latest_comp_m_nbr < 12 else 'NONE'} to DEC")
        print("=" * 70)

        year_metrics = {}
        for yr in all_years:
            d = data_by_year.get(yr, {
                "pos_val": [None]*12, "factory_pos": [None]*12, "pos_u": [None]*12,
                "gross_ship": [None]*12, "return_ship": [None]*12,
                "gross_case": [None]*12, "return_case": [None]*12,
                "gross_cu": [None]*12, "return_cu": [None]*12
            })
            net_ship = [calc_net(d["gross_ship"][i], d["return_ship"][i]) for i in range(12)]
            net_case = [calc_net(d["gross_case"][i], d["return_case"][i]) for i in range(12)]
            net_cu = [calc_net(d["gross_cu"][i], d["return_cu"][i]) for i in range(12)]
            asp = [calc_asp(d["pos_val"][i], d["pos_u"][i]) for i in range(12)]
 
            prev_year_str = str(int(yr) - 1) if yr.isdigit() else None
            prev_year_dec_pos = None
            if prev_year_str and prev_year_str in data_by_year:
                prev_year_dec_pos = data_by_year[prev_year_str]["pos_val"][11]
 
            build = [None] * 12
            for i in range(12):
                cur_pos = d["pos_val"][i]
                prev_pos = (d["pos_val"][i-1] if i > 0 else prev_year_dec_pos)
                if cur_pos is not None and prev_pos is not None and prev_pos != 0:
                    build[i] = cur_pos / prev_pos
 
            tot_pos = sum([v for v in d["pos_val"] if v is not None])
            share = [calc_share(d["pos_val"][i], tot_pos) for i in range(12)]
            variance = [calc_variance(d["pos_val"][i], net_ship[i]) for i in range(12)]
            var_pct = [calc_pct_var(d["pos_val"][i], net_ship[i]) for i in range(12)]
 
            year_metrics[yr] = {
                "pos_val": d["pos_val"], "factory_pos": d.get("factory_pos", [None]*12), "pos_u": d["pos_u"],
                "gross_ship": d["gross_ship"], "return_ship": d["return_ship"], "net_ship": net_ship,
                "gross_case": d["gross_case"], "return_case": d["return_case"], "net_case": net_case,
                "gross_cu": d["gross_cu"], "return_cu": d["return_cu"], "net_cu": net_cu,
                "asp": asp, "build": build, "share": share,
                "variance": variance, "var_pct": var_pct
            }
 
        th_style = {
            "backgroundColor": "#019881", "color": "#ffffff", "fontWeight": "800", "padding": "8px 10px", "border": "1px solid #858585", "textAlign": "center", "whiteSpace": "nowrap"
        }
        th_q1 = html.Th("Q1", colSpan=3, style={**th_style, "backgroundColor": "#018571"})
        th_q2 = html.Th("Q2", colSpan=3, style={**th_style, "backgroundColor": "#018571"})
        th_q3 = html.Th("Q3", colSpan=3, style={**th_style, "backgroundColor": "#018571"})
        th_q4 = html.Th("Q4", colSpan=3, style={**th_style, "backgroundColor": "#018571", "borderRight": "3px solid #858585"})
        th_tot = html.Th("TOTALS", colSpan=7, style={**th_style, "backgroundColor": "#017362"})
 
        hdr_row1 = html.Tr([
            html.Th("METRIC NAME", style={**th_style, "backgroundColor": "#019881", "textAlign": "left"}),
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
                "backgroundColor": "#DDDDDD", "color": "#000000", "fontWeight": "900", "fontSize": "14px",
                "textAlign": "center", "verticalAlign": "middle", "border": "1px solid #858585", "padding": "8px"
            }
 
            def calc_period_val(target_yr, slice_obj):
                if target_yr == "YoY %":
                    val_latest = calc_period_val(latest_year, slice_obj) if latest_year else None
                    val_prev = calc_period_val(prev_year, slice_obj) if prev_year else None
                    return calc_pct_var(val_latest, val_prev)
 
                ym = year_metrics.get(target_yr)
                if not ym:
                    return None
 
                if metric_key in ["pos_val", "factory_pos", "pos_u", "gross_ship", "gross_case", "net_ship", "share"]:
                    arr = ym.get(metric_key, [None]*12)[slice_obj]
                    valid_vals = [v for v in arr if v is not None and not (isinstance(v, float) and math.isnan(v))]
                    return sum(valid_vals) if valid_vals else None
                elif metric_key == "build":
                    arr = ym.get("build", [None]*12)[slice_obj]
                    valid_vals = [v for v in arr if v is not None and not (isinstance(v, float) and math.isnan(v))]
                    return (sum(valid_vals) / len(valid_vals)) if valid_vals else None
                elif metric_key == "asp":
                    pos_v_sum = sum([v for v in ym["pos_val"][slice_obj] if v is not None and not (isinstance(v, float) and math.isnan(v))])
                    pos_u_sum = sum([v for v in ym["pos_u"][slice_obj] if v is not None and not (isinstance(v, float) and math.isnan(v))])
                    if pos_u_sum == 0:
                        return None
                    return pos_v_sum / pos_u_sum
                else:
                    arr = ym.get(metric_key, [None]*12)[slice_obj]
                    valid_vals = [v for v in arr if v is not None and not (isinstance(v, float) and math.isnan(v))]
                    return sum(valid_vals) if valid_vals else None
 
            for idx, (yr, m_vals) in enumerate(yr_val_tuples):
                td_cells = []
                if idx == 0:
                    td_cells.append(html.Td(metric_name, rowSpan=group_size, style=label_td_style))
 
                is_grey_highlight = (yr in [latest_year, "YoY %"])
                yr_bg_color = "#DDDDDD" if is_grey_highlight else "#ffffff"

                td_cells.append(html.Td(yr, style={
                    "backgroundColor": yr_bg_color, "color": "#000000",
                    "fontWeight": "800" if is_grey_highlight else "bold",
                    "textAlign": "center", "border": "1px solid #858585"
                }))

                cell_unit = "%" if yr == "YoY %" else unit

                for m_idx in range(12):
                    v = m_vals[m_idx] if m_idx < len(m_vals) else None
                    cell_str = fmt_val(v, cell_unit, "VALID")

                    cell_bg = yr_bg_color
                    text_color = "#000000"
                    font_wt = "800" if is_grey_highlight else "500"

                    if metric_key == "build" and yr == latest_year:
                        if v is not None and not (isinstance(v, float) and math.isnan(v)):
                            val_float_2d = round(float(v), 2)
                            hist_builds = []
                            for h_yr in hist_years:
                                b_val = year_metrics.get(h_yr, {}).get("build", [None]*12)[m_idx]
                                if b_val is not None and not (isinstance(b_val, float) and math.isnan(b_val)):
                                    hist_builds.append(round(float(b_val), 2))

                            if len(hist_builds) >= 2:
                                try:
                                    h_mean_2d = round(statistics.mean(hist_builds), 2)
                                    h_std = statistics.stdev(hist_builds) if len(hist_builds) > 1 else statistics.pstdev(hist_builds)
                                    two_std_2d = round(2.0 * h_std, 2)
                                    abs_diff_2d = round(abs(val_float_2d - h_mean_2d), 2)

                                    is_red = (abs_diff_2d > two_std_2d)

                                    m_name = MONTHS[m_idx] if m_idx < len(MONTHS) else f"Month {m_idx+1}"
                                    print(f"{latest_year} BUILD DAX RED CHECK [{m_name}]:")
                                    print(f"  {latest_year} Current Value: {val_float_2d:.2f}")
                                    print(f"  Mean (2d):          {h_mean_2d:.2f}")
                                    print(f"  ABS Diff (2d):      {abs_diff_2d:.2f}")
                                    print(f"  STD (unrounded):    {h_std:.6f}")
                                    print(f"  2*STD (2d):         {two_std_2d:.2f}")
                                    print(f"  Red Check (ABS > 2*STD): {abs_diff_2d:.2f} > {two_std_2d:.2f} -> RED: {'YES' if is_red else 'NO'}")

                                    if is_red:
                                        cell_bg = "#F8696B"
                                        text_color = "#ffffff"
                                        font_wt = "800"
                                except Exception as calc_err:
                                    print(f"Notice calculating {latest_year} Build Red status: {calc_err}")

                    border_style = "1px solid #858585"
                    td_cells.append(html.Td(cell_str, style={
                        "backgroundColor": cell_bg, "color": text_color, "fontWeight": font_wt,
                        "textAlign": "right", "border": border_style, "padding": "6px 8px",
                        **({"borderRight": "3px solid #858585"} if m_idx == 11 else {})
                    }))
 
                q1_val = calc_period_val(yr, slice(0, 3))
                q2_val = calc_period_val(yr, slice(3, 6))
                q3_val = calc_period_val(yr, slice(6, 9))
                q4_val = calc_period_val(yr, slice(9, 12))
                fy_val = calc_period_val(yr, slice(0, 12))
                ytd_val = calc_period_val(yr, ytd_slice)
                ytg_val = calc_period_val(yr, ytg_slice)
 
                summary_cells = [
                    (q1_val, "#ffffff"), (q2_val, "#ffffff"), (q3_val, "#ffffff"), (q4_val, "#ffffff"),
                    (fy_val, "#ffffff"), (ytd_val, "#ffffff"), (ytg_val, "#ffffff")
                ]
 
                for s_idx, (s_val, s_bg) in enumerate(summary_cells):
                    s_str = fmt_val(s_val, cell_unit, "VALID")
                    final_s_bg = yr_bg_color if is_grey_highlight else s_bg
                    td_cells.append(html.Td(s_str, style={
                        "backgroundColor": final_s_bg, "color": "#000000",
                        "fontWeight": "800" if is_grey_highlight else "bold",
                        "textAlign": "right", "border": "1px solid #858585", "padding": "6px 8px",
                        **({"borderRight": "3px solid #858585"} if s_idx == 3 else {})
                    }))
 
                row_border_bottom = "3px solid #858585" if (idx == group_size - 1) else "1px solid #858585"
                group_rows.append(html.Tr(td_cells, style={"borderBottom": row_border_bottom}))
 
            return group_rows
 
        display_years = all_years
        latest_metrics = year_metrics.get(latest_year, {})
        prev_metrics = year_metrics.get(prev_year, {})

        if active_tab == "shipments":
            gts_dollar_tuples = [(yr, year_metrics[yr]["gross_ship"]) for yr in display_years]
            gst_u_tuples = [(yr, year_metrics[yr]["gross_case"]) for yr in display_years]
            b3_tuples = [(yr, year_metrics[yr]["net_ship"]) for yr in display_years]
            build_bleed_tuples = [(yr, year_metrics[yr]["build"]) for yr in display_years]
            unit_ratio_tuples = [(yr, year_metrics[yr]["share"]) for yr in display_years]
 
            yoy_gts = [calc_pct_var(latest_metrics.get("gross_ship", [None]*12)[i], prev_metrics.get("gross_ship", [None]*12)[i]) for i in range(12)]
            yoy_gstu = [calc_pct_var(latest_metrics.get("gross_case", [None]*12)[i], prev_metrics.get("gross_case", [None]*12)[i]) for i in range(12)]
            yoy_b3 = [calc_pct_var(latest_metrics.get("net_ship", [None]*12)[i], prev_metrics.get("net_ship", [None]*12)[i]) for i in range(12)]
            yoy_build_bleed = [calc_pct_var(latest_metrics.get("build", [None]*12)[i], prev_metrics.get("build", [None]*12)[i]) for i in range(12)]
            yoy_unit_ratio = [calc_pct_var(latest_metrics.get("share", [None]*12)[i], prev_metrics.get("share", [None]*12)[i]) for i in range(12)]
 
            gts_dollar_tuples.append(("YoY %", yoy_gts))
            gst_u_tuples.append(("YoY %", yoy_gstu))
            b3_tuples.append(("YoY %", yoy_b3))
            build_bleed_tuples.append(("YoY %", yoy_build_bleed))
            unit_ratio_tuples.append(("YoY %", yoy_unit_ratio))
 
            tbody_rows.extend(make_grouped_rows("GTS $", "$", gts_dollar_tuples, "gross_ship", year_metrics))
            tbody_rows.extend(make_grouped_rows("GST U", "Units", gst_u_tuples, "gross_case", year_metrics))
            tbody_rows.extend(make_grouped_rows("B3", "$", b3_tuples, "net_ship", year_metrics))
            tbody_rows.extend(make_grouped_rows("Build/Bleed $", "$", build_bleed_tuples, "build", year_metrics))
            tbody_rows.extend(make_grouped_rows("Unit Ratio", "Ratio", unit_ratio_tuples, "share", year_metrics))
        else:
            pos_dollar_tuples = [(yr, year_metrics[yr]["pos_val"]) for yr in display_years]
            factory_pos_tuples = [(yr, year_metrics[yr]["factory_pos"]) for yr in display_years]
            pos_u_tuples = [(yr, year_metrics[yr]["pos_u"]) for yr in display_years]
            asp_tuples = [(yr, year_metrics[yr]["asp"]) for yr in display_years]
            build_tuples = [(yr, year_metrics[yr]["build"]) for yr in display_years]
            share_tuples = [(yr, year_metrics[yr]["share"]) for yr in display_years]
 
            yoy_pos = [calc_pct_var(latest_metrics.get("pos_val", [None]*12)[i], prev_metrics.get("pos_val", [None]*12)[i]) for i in range(12)]
            yoy_factory = [calc_pct_var(latest_metrics.get("factory_pos", [None]*12)[i], prev_metrics.get("factory_pos", [None]*12)[i]) for i in range(12)]
            yoy_u = [calc_pct_var(latest_metrics.get("pos_u", [None]*12)[i], prev_metrics.get("pos_u", [None]*12)[i]) for i in range(12)]
            yoy_asp = [calc_pct_var(latest_metrics.get("asp", [None]*12)[i], prev_metrics.get("asp", [None]*12)[i]) for i in range(12)]
            yoy_build = [calc_pct_var(latest_metrics.get("build", [None]*12)[i], prev_metrics.get("build", [None]*12)[i]) for i in range(12)]
            yoy_share = [calc_pct_var(latest_metrics.get("share", [None]*12)[i], prev_metrics.get("share", [None]*12)[i]) for i in range(12)]
 
            pos_dollar_tuples.append(("YoY %", yoy_pos))
            factory_pos_tuples.append(("YoY %", yoy_factory))
            pos_u_tuples.append(("YoY %", yoy_u))
            asp_tuples.append(("YoY %", yoy_asp))
            build_tuples.append(("YoY %", yoy_build))
            share_tuples.append(("YoY %", yoy_share))
 
            tbody_rows.extend(make_grouped_rows("POS $", "$M", pos_dollar_tuples, "pos_val", year_metrics))
            tbody_rows.extend(make_grouped_rows("FACTORY POS $", "$M", factory_pos_tuples, "factory_pos", year_metrics))
            tbody_rows.extend(make_grouped_rows("POS U", "UnitsM", pos_u_tuples, "pos_u", year_metrics))
            tbody_rows.extend(make_grouped_rows("ASP", "$", asp_tuples, "asp", year_metrics))
            tbody_rows.extend(make_grouped_rows("Build", "Ratio", build_tuples, "build", year_metrics))
            tbody_rows.extend(make_grouped_rows("% of Year", "%", share_tuples, "share", year_metrics))
 
        tbody = html.Tbody(tbody_rows)
        table_elem = html.Table([thead, tbody], style={
            "width": "100%", "borderCollapse": "collapse", "fontFamily": "sans-serif", "fontSize": "11px"
        })
    else:
        if not can_refresh:
            if not is_gbu_valid:
                prompt_text = "Please select a GBU to begin."
            elif not is_squad_valid:
                prompt_text = "Please select a Need State."
            else:
                prompt_text = "Please select a Model."
        else:
            if should_fetch_snowflake and df.empty:
                prompt_text = f"No POS records found in Snowflake for GBU: '{gbu}', Need State: '{squad}', Model: '{model}'."
            else:
                prompt_text = "All selections complete. Click REFRESH DATA to load the dashboard."
 
        dash_title = "Shipment Validation Dashboard" if active_tab == "shipments" else "Consumption Validation Dashboard"
        table_elem = html.Div([
            html.Div([
                html.H6(dash_title, style={"color": "#00B097", "fontWeight": "700", "marginBottom": "8px", "fontSize": "16px"}),
                html.P(prompt_text, style={"color": "#495057", "fontSize": "13px", "marginBottom": "0", "fontWeight": "500"})
            ], style={"textAlign": "center", "padding": "48px 24px", "backgroundColor": "#ffffff", "borderRadius": "10px", "border": "1px dashed #00B097", "boxShadow": "0 2px 8px rgba(0,0,0,0.04)"})
        ])
 
    return (
        active_tab,
        current_loaded_store,
        record_str,
        table_elem,
        gbu_opts,
        squad_opts,
        model_opts,
        gbu,
        squad,
        model,
        squad_disabled,
        model_disabled,
        btn_disabled,
        btn_style,
        nav_cons_style,
        nav_ship_style
    )


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8050"))
    debug = os.getenv("DEBUG", "True").lower() in ["true", "1", "t"]
    print(f"Starting Consumption Validation Dashboard at http://{host}:{port}...")
    app.run(host=host, port=port, debug=debug, dev_tools_ui=False)
