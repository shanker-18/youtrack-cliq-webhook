import os
import math
import pandas as pd
import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

import database

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Consumption Validation Dashboard"
)
server = app.server

# Months Constant
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Python Pure Calculation Helpers
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
    if unit == "$":
        return f"${val:,.0f}"
    elif unit == "Units":
        return f"{val:,.0f}"
    elif unit == "%":
        return f"{val:.1f}%"
    elif unit == "Status":
        return status
    return f"{val:,.2f}"

def format_total(val_list, unit_str):
    valid_vals = [v for v in val_list if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not valid_vals:
        return ""
    tot = sum(valid_vals) if unit_str in ["$", "Units"] else (sum(valid_vals) / len(valid_vals))
    return fmt_val(tot, unit_str, "VALID")

# Load initial dropdown filter options from Snowflake
filter_opts = database.get_filter_options()

app.layout = html.Div([
    # Centered Pink Header Box
    html.Div([
        html.H1(["CONSUMPTION", html.Br(), "VALIDATION"], style={
            "color": "#880e4f",
            "fontWeight": "900",
            "fontSize": "26px",
            "letterSpacing": "1.5px",
            "margin": "0",
            "textTransform": "uppercase",
            "lineHeight": "1.2"
        })
    ], style={
        "backgroundColor": "#fce4ec",
        "border": "2px solid #f8bbd0",
        "borderRadius": "8px",
        "padding": "18px 24px",
        "marginBottom": "20px",
        "textAlign": "center",
        "boxShadow": "0 4px 12px rgba(233, 30, 99, 0.08)"
    }),

    # Compact Filter Control Bar
    html.Div([
        html.Div([
            html.Span("🔍 ", style={"fontSize": "15px"}),
            html.Span("Snowflake Live Data Filters & Tolerance Parameters", style={"fontWeight": "700", "fontSize": "13px", "color": "#263238"}),
            html.Span(id="live-record-count", style={"float": "right", "fontSize": "12px", "color": "#000000", "fontWeight": "600"})
        ], style={"marginBottom": "10px", "borderBottom": "1px solid #e0e0e0", "paddingBottom": "4px"}),

        dbc.Row([
            dbc.Col([
                html.Label("Brand:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-brand",
                    options=[{"label": b, "value": b} for b in filter_opts.get("brands", ["All"])],
                    value="All", clearable=False, style={"fontSize": "12px"}
                )
            ], width=3),
            dbc.Col([
                html.Label("Category:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-category",
                    options=[{"label": c, "value": c} for c in filter_opts.get("categories", ["All"])],
                    value="All", clearable=False, style={"fontSize": "12px"}
                )
            ], width=3),
            dbc.Col([
                html.Label("Retailer:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-retailer",
                    options=[{"label": r, "value": r} for r in filter_opts.get("retailers", ["All"])],
                    value="All", clearable=False, style={"fontSize": "12px"}
                )
            ], width=2),
            dbc.Col([
                html.Label("Tolerance %:", style={"fontWeight": "600", "fontSize": "11px", "marginBottom": "2px"}),
                dcc.Dropdown(
                    id="filter-tolerance",
                    options=[
                        {"label": "5.0% (Strict)", "value": 5.0},
                        {"label": "10.0% (Default)", "value": 10.0},
                        {"label": "15.0% (Relaxed)", "value": 15.0},
                    ],
                    value=10.0, clearable=False, style={"fontSize": "12px"}
                )
            ], width=2),
            dbc.Col([
                html.Label("\u00a0", style={"display": "block", "marginBottom": "2px"}),
                dbc.Button("REFRESH DATA", id="btn-refresh", color="dark", n_clicks=0, style={
                    "backgroundColor": "#000000", "color": "#ffffff", "fontWeight": "700", "fontSize": "12px", "padding": "6px 12px", "width": "100%", "border": "none"
                })
            ], width=2),
        ])
    ], style={
        "backgroundColor": "#ffffff", "border": "1px solid #e9ecef", "borderRadius": "10px", "padding": "14px 20px", "marginBottom": "16px", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)"
    }),

    # Main Spreadsheet Table Card
    html.Div([
        html.Div(id="spreadsheet-container", style={"overflowX": "auto", "border": "1px solid #cfd8dc", "borderRadius": "6px"})
    ], style={"backgroundColor": "#ffffff", "borderRadius": "10px", "boxShadow": "0 4px 12px rgba(0,0,0,0.05)", "border": "1px solid #e9ecef", "padding": "16px", "marginBottom": "16px"}),

    # Legend Footer
    html.Div([
        html.Span("STATUS LEGEND: ", style={"fontWeight": "700", "fontSize": "11px", "color": "#37474f", "marginRight": "12px"}),
        html.Span("□ VALID / NORMAL DATA (WHITE)", style={"backgroundColor": "#ffffff", "color": "#212529", "border": "1px solid #cfd8dc", "fontWeight": "700", "fontSize": "11px", "padding": "3px 8px", "marginRight": "12px", "borderRadius": "4px"}),
        html.Span("■ EXCEPTION (RED, e.g. 1.16)", style={"backgroundColor": "#fce8e6", "color": "#c5221f", "border": "1px solid #fca5a5", "fontWeight": "800", "fontSize": "11px", "padding": "3px 8px", "marginRight": "12px", "borderRadius": "4px"}),
        html.Span("■ METRIC / YOY HEADER (DARK SLATE)", style={"backgroundColor": "#37474f", "color": "#ffffff", "fontWeight": "800", "fontSize": "11px", "padding": "3px 8px", "borderRadius": "4px"}),
        html.Span(" | Snowflake Read-Only Engine", style={"float": "right", "fontSize": "11px", "color": "#000000", "fontWeight": "600"})
    ], style={"textAlign": "left", "padding": "10px 16px", "backgroundColor": "#ffffff", "borderRadius": "8px", "border": "1px solid #cfd8dc", "marginBottom": "24px"})

], style={"maxWidth": "1500px", "margin": "0 auto", "padding": "16px", "backgroundColor": "#f8f9fa", "fontFamily": "sans-serif"})


@app.callback(
    [Output("live-record-count", "children"),
     Output("spreadsheet-container", "children")],
    [Input("btn-refresh", "n_clicks"),
     Input("filter-brand", "value"),
     Input("filter-category", "value"),
     Input("filter-retailer", "value"),
     Input("filter-tolerance", "value")]
)
def update_dashboard(n_clicks, brand, category, retailer, tolerance):
    tol = float(tolerance or 10.0)

    # Read live data strictly READ-ONLY from Snowflake
    df = database.fetch_joined_snowflake_data(brand=brand, category=category, retailer=retailer)
    rec_count = len(df)
    record_str = f"Snowflake Joined Records: {rec_count} | Read-Only"

    month_idx_map = {m: i for i, m in enumerate(MONTHS)}

    data_by_year = {}
    if not df.empty:
        for _, r in df.iterrows():
            d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', ''))
            parts = d_str.split('-')
            if len(parts) == 2:
                m_str, y_str = parts[0].upper(), parts[1]
                m_idx = month_idx_map.get(m_str)
                if m_idx is not None:
                    if y_str not in data_by_year:
                        data_by_year[y_str] = {
                            "pos_val": [None]*12, "pos_u": [None]*12,
                            "gross_ship": [None]*12, "return_ship": [None]*12,
                            "gross_case": [None]*12, "return_case": [None]*12,
                            "gross_cu": [None]*12, "return_cu": [None]*12
                        }
                    d_dict = data_by_year[y_str]
                    pv, pu = r.get('POS_VALUE'), r.get('POS_UNITS')
                    gs, rs = r.get('GROSS_SHIPMENT_AM'), r.get('RETURN_SHIP_AM')
                    gqc, rqc = r.get('GROSS_QTY_CASE'), r.get('RETURN_QTY_CASE')
                    gcu, rcu = r.get('GROSS_QTY_CU'), r.get('RETURN_QTY_CU')

                    d_dict["pos_val"][m_idx] = (d_dict["pos_val"][m_idx] or 0.0) + float(pv) if pd.notnull(pv) else d_dict["pos_val"][m_idx]
                    d_dict["pos_u"][m_idx] = (d_dict["pos_u"][m_idx] or 0.0) + float(pu) if pd.notnull(pu) else d_dict["pos_u"][m_idx]
                    d_dict["gross_ship"][m_idx] = (d_dict["gross_ship"][m_idx] or 0.0) + float(gs) if pd.notnull(gs) else d_dict["gross_ship"][m_idx]
                    d_dict["return_ship"][m_idx] = (d_dict["return_ship"][m_idx] or 0.0) + float(rs) if pd.notnull(rs) else d_dict["return_ship"][m_idx]
                    d_dict["gross_case"][m_idx] = (d_dict["gross_case"][m_idx] or 0.0) + float(gqc) if pd.notnull(gqc) else d_dict["gross_case"][m_idx]
                    d_dict["return_case"][m_idx] = (d_dict["return_case"][m_idx] or 0.0) + float(rqc) if pd.notnull(rqc) else d_dict["return_case"][m_idx]
                    d_dict["gross_cu"][m_idx] = (d_dict["gross_cu"][m_idx] or 0.0) + float(gcu) if pd.notnull(gcu) else d_dict["gross_cu"][m_idx]
                    d_dict["return_cu"][m_idx] = (d_dict["return_cu"][m_idx] or 0.0) + float(rcu) if pd.notnull(rcu) else d_dict["return_cu"][m_idx]

    sorted_years = sorted(list(data_by_year.keys())) if data_by_year else ["2026"]
    primary_year = sorted_years[-1]

    # Calculate net shipment, ASP, Build, Share per year
    year_metrics = {}
    for yr in sorted_years:
        d = data_by_year.get(yr, {
            "pos_val": [None]*12, "pos_u": [None]*12,
            "gross_ship": [None]*12, "return_ship": [None]*12,
            "gross_case": [None]*12, "return_case": [None]*12,
            "gross_cu": [None]*12, "return_cu": [None]*12
        })
        net_ship = [calc_net(d["gross_ship"][i], d["return_ship"][i]) for i in range(12)]
        net_case = [calc_net(d["gross_case"][i], d["return_case"][i]) for i in range(12)]
        net_cu = [calc_net(d["gross_cu"][i], d["return_cu"][i]) for i in range(12)]
        asp = [calc_asp(d["pos_val"][i], d["pos_u"][i]) for i in range(12)]
        build = [calc_asp(d["pos_val"][i], net_ship[i]) for i in range(12)]
        
        tot_pos = sum([v for v in d["pos_val"] if v is not None])
        share = [calc_share(d["pos_val"][i], tot_pos) for i in range(12)]
        
        variance = [calc_variance(d["pos_val"][i], net_ship[i]) for i in range(12)]
        var_pct = [calc_pct_var(d["pos_val"][i], net_ship[i]) for i in range(12)]

        year_metrics[yr] = {
            "pos_val": d["pos_val"], "pos_u": d["pos_u"],
            "gross_ship": d["gross_ship"], "return_ship": d["return_ship"], "net_ship": net_ship,
            "gross_case": d["gross_case"], "return_case": d["return_case"], "net_case": net_case,
            "gross_cu": d["gross_cu"], "return_cu": d["return_cu"], "net_cu": net_cu,
            "asp": asp, "build": build, "share": share,
            "variance": variance, "var_pct": var_pct
        }

    # Build Header Rows (BLACK Background)
    th_style = {"backgroundColor": "#000000", "color": "#ffffff", "fontWeight": "800", "padding": "7px 8px", "border": "1px solid #424242", "textAlign": "center", "whiteSpace": "nowrap"}
    
    th_q1 = html.Th("Q1", colSpan=3, style={**th_style, "backgroundColor": "#1c1c1c"})
    th_q2 = html.Th("Q2", colSpan=3, style={**th_style, "backgroundColor": "#1c1c1c"})
    th_q3 = html.Th("Q3", colSpan=3, style={**th_style, "backgroundColor": "#1c1c1c"})
    th_q4 = html.Th("Q4", colSpan=3, style={**th_style, "backgroundColor": "#1c1c1c"})
    th_tot = html.Th("TOTALS", colSpan=7, style={**th_style, "backgroundColor": "#1c1c1c"})

    hdr_row1 = html.Tr([
        html.Th("METRIC NAME", style={**th_style, "backgroundColor": "#000000", "textAlign": "left"}),
        html.Th("YEAR", style={**th_style, "backgroundColor": "#000000"}),
        th_q1, th_q2, th_q3, th_q4, th_tot
    ])

    hdr_row2 = html.Tr([
        html.Th("Metric Description", style={**th_style, "textAlign": "left", "minWidth": "160px"}),
        html.Th("Ver/Yr", style={**th_style, "minWidth": "50px"}),
        *[html.Th(m, style={**th_style, "minWidth": "55px"}) for m in MONTHS],
        html.Th("Q1", style={**th_style, "minWidth": "60px", "backgroundColor": "#eceff1", "color": "#000000"}),
        html.Th("Q2", style={**th_style, "minWidth": "60px", "backgroundColor": "#eceff1", "color": "#000000"}),
        html.Th("Q3", style={**th_style, "minWidth": "60px", "backgroundColor": "#eceff1", "color": "#000000"}),
        html.Th("Q4", style={**th_style, "minWidth": "60px", "backgroundColor": "#eceff1", "color": "#000000"}),
        html.Th("FY", style={**th_style, "minWidth": "65px", "backgroundColor": "#cfd8dc", "color": "#000000"}),
        html.Th("YTD", style={**th_style, "minWidth": "65px", "backgroundColor": "#cfd8dc", "color": "#000000"}),
        html.Th("YTG", style={**th_style, "minWidth": "65px", "backgroundColor": "#cfd8dc", "color": "#000000"})
    ])

    thead = html.Thead([hdr_row1, hdr_row2])

    tbody_rows = []

    # MERGED VERTICAL METRIC BOX (rowSpan) WITH MATCHING YoY % COLOR STYLING
    def make_grouped_rows(metric_name, unit, yr_val_tuples, var_pcts_dict=None, highlight_exception_val=None):
        group_rows = []
        group_size = len(yr_val_tuples)

        label_td_style = {
            "backgroundColor": "#37474f",
            "color": "#ffffff",
            "fontWeight": "800",
            "fontSize": "13px",
            "textAlign": "center",
            "verticalAlign": "middle",
            "border": "1px solid #cfd8dc",
            "padding": "8px"
        }

        for idx, (yr, vals) in enumerate(yr_val_tuples):
            td_cells = []

            # Single merged vertical Td box in Column 1
            if idx == 0:
                td_cells.append(html.Td(metric_name, rowSpan=group_size, style=label_td_style))

            # Column 2 Year Cell:
            if yr == "YoY %":
                yr_style = {
                    "backgroundColor": "#37474f",
                    "color": "#ffffff",
                    "fontWeight": "800",
                    "textAlign": "center",
                    "padding": "5px 8px",
                    "border": "1px solid #cfd8dc"
                }
                current_unit = "%"
            else:
                yr_style = {
                    "backgroundColor": "#f8f9fa",
                    "color": "#212529",
                    "fontWeight": "700",
                    "textAlign": "center",
                    "padding": "5px 8px",
                    "border": "1px solid #cfd8dc"
                }
                current_unit = unit

            td_cells.append(html.Td(yr, style=yr_style))

            var_pcts = var_pcts_dict.get(yr) if var_pcts_dict else None

            for i in range(12):
                v = vals[i] if i < len(vals) else None
                vp = var_pcts[i] if (var_pcts and i < len(var_pcts)) else None

                is_red_exception = False
                if highlight_exception_val is not None and v is not None:
                    if abs(v - highlight_exception_val) < 0.02:
                        is_red_exception = True

                if vp is not None and abs(vp) > tol:
                    is_red_exception = True

                if is_red_exception:
                    c_style = {"backgroundColor": "#fce8e6", "color": "#c5221f", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
                    st = "EXCEPTION"
                elif v is None:
                    c_style = {"backgroundColor": "#ffffff", "color": "#adb5bd", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
                    st = "EMPTY"
                else:
                    c_style = {"backgroundColor": "#ffffff", "color": "#212529", "fontWeight": "400", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
                    st = "VALID"

                formatted = fmt_val(v, current_unit, st)
                td_cells.append(html.Td(formatted, style=c_style))

            q_style = {"backgroundColor": "#eceff1", "color": "#212529", "fontWeight": "700", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
            s_style = {"backgroundColor": "#cfd8dc", "color": "#000000", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}

            q1_t = format_total(vals[0:3], current_unit)
            q2_t = format_total(vals[3:6], current_unit)
            q3_t = format_total(vals[6:9], current_unit)
            q4_t = format_total(vals[9:12], current_unit)

            fy_t = format_total(vals, current_unit)
            ytd_t = format_total(vals[0:7], current_unit)
            ytg_t = format_total(vals[7:12], current_unit)

            td_cells.extend([
                html.Td(q1_t, style=q_style), html.Td(q2_t, style=q_style),
                html.Td(q3_t, style=q_style), html.Td(q4_t, style=q_style),
                html.Td(fy_t, style=s_style), html.Td(ytd_t, style=s_style), html.Td(ytg_t, style=s_style)
            ])
            group_rows.append(html.Tr(td_cells))
        return group_rows

    def make_single_data_row(name, yr, unit, vals, var_pcts=None):
        td_cells = [
            html.Td(name, colSpan=2, style={"fontWeight": "600", "textAlign": "left", "padding": "5px 8px", "border": "1px solid #cfd8dc", "backgroundColor": "#ffffff", "color": "#212529"})
        ]

        for i in range(12):
            v = vals[i] if i < len(vals) else None
            vp = var_pcts[i] if (var_pcts and i < len(var_pcts)) else None

            if vp is not None and abs(vp) > tol:
                c_style = {"backgroundColor": "#fce8e6", "color": "#c5221f", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
                st = "EXCEPTION"
            elif v is None:
                c_style = {"backgroundColor": "#ffffff", "color": "#adb5bd", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
                st = "EMPTY"
            else:
                c_style = {"backgroundColor": "#ffffff", "color": "#212529", "fontWeight": "400", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
                st = "VALID"

            formatted = fmt_val(v, unit, st)
            td_cells.append(html.Td(formatted, style=c_style))

        q_style = {"backgroundColor": "#eceff1", "color": "#212529", "fontWeight": "700", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}
        s_style = {"backgroundColor": "#cfd8dc", "color": "#000000", "fontWeight": "800", "padding": "5px 8px", "border": "1px solid #cfd8dc", "textAlign": "right"}

        q1_t = format_total(vals[0:3], unit)
        q2_t = format_total(vals[3:6], unit)
        q3_t = format_total(vals[6:9], unit)
        q4_t = format_total(vals[9:12], unit)

        fy_t = format_total(vals, unit)
        ytd_t = format_total(vals[0:7], unit)
        ytg_t = format_total(vals[7:12], unit)

        td_cells.extend([
            html.Td(q1_t, style=q_style), html.Td(q2_t, style=q_style),
            html.Td(q3_t, style=q_style), html.Td(q4_t, style=q_style),
            html.Td(fy_t, style=s_style), html.Td(ytd_t, style=s_style), html.Td(ytg_t, style=s_style)
        ])
        return html.Tr(td_cells)

    # Build Multi-Year Metric Tuples dynamically for all years in Snowflake
    pos_dollar_tuples = [(yr, year_metrics[yr]["pos_val"]) for yr in sorted_years]
    pos_u_tuples = [(yr, year_metrics[yr]["pos_u"]) for yr in sorted_years]
    asp_tuples = [(yr, year_metrics[yr]["asp"]) for yr in sorted_years]
    build_tuples = [(yr, year_metrics[yr]["build"]) for yr in sorted_years]
    share_tuples = [(yr, year_metrics[yr]["share"]) for yr in sorted_years]

    # Calculate YoY % if multi-year data exists
    if len(sorted_years) > 1:
        prev_yr, curr_yr = sorted_years[-2], sorted_years[-1]
        yoy_pos = [calc_pct_var(year_metrics[curr_yr]["pos_val"][i], year_metrics[prev_yr]["pos_val"][i]) for i in range(12)]
        yoy_u = [calc_pct_var(year_metrics[curr_yr]["pos_u"][i], year_metrics[prev_yr]["pos_u"][i]) for i in range(12)]
        pos_dollar_tuples.append(("YoY %", yoy_pos))
        pos_u_tuples.append(("YoY %", yoy_u))

    # POS $
    tbody_rows.extend(make_grouped_rows("POS $", "$", pos_dollar_tuples))

    # POS U
    tbody_rows.extend(make_grouped_rows("POS U", "Units", pos_u_tuples))

    # ASP
    tbody_rows.extend(make_grouped_rows("ASP", "$", asp_tuples))

    # Build (POS / Net Shipment Ratio)
    tbody_rows.extend(make_grouped_rows("Build", "Ratio", build_tuples))

    # % of Year (Monthly Share)
    tbody_rows.extend(make_grouped_rows("% of Year", "%", share_tuples))

    # 2. SHIPMENT METRICS Section Header
    tbody_rows.append(html.Tr([
        html.Td("SHIPMENT METRICS (SNOWFLAKE READ-ONLY)", colSpan=21, style={
            "backgroundColor": "#000000", "color": "#ffffff", "fontWeight": "800", "fontSize": "12px", "padding": "8px 12px", "textAlign": "left"
        })
    ]))

    p_metrics = year_metrics[primary_year]
    tbody_rows.append(make_single_data_row("Gross Shipment Amount ($)", primary_year, "$", p_metrics["gross_ship"]))
    tbody_rows.append(make_single_data_row("Return Shipment Amount ($)", primary_year, "$", p_metrics["return_ship"]))
    tbody_rows.append(make_single_data_row("Net Shipment Amount ($)", primary_year, "$", p_metrics["net_ship"]))
    tbody_rows.append(make_single_data_row("Gross Quantity Case", primary_year, "Units", p_metrics["gross_case"]))
    tbody_rows.append(make_single_data_row("Return Quantity Case", primary_year, "Units", p_metrics["return_case"]))
    tbody_rows.append(make_single_data_row("Net Quantity Case", primary_year, "Units", p_metrics["net_case"]))

    # 3. CONSUMPTION VALIDATION Section Header
    tbody_rows.append(html.Tr([
        html.Td("CONSUMPTION VALIDATION (POS vs SHIPMENT)", colSpan=21, style={
            "backgroundColor": "#000000", "color": "#ffffff", "fontWeight": "800", "fontSize": "12px", "padding": "8px 12px", "textAlign": "left"
        })
    ]))

    tbody_rows.append(make_single_data_row("POS Consumption ($)", primary_year, "$", p_metrics["pos_val"]))
    tbody_rows.append(make_single_data_row("Net Shipment ($)", primary_year, "$", p_metrics["net_ship"]))
    tbody_rows.append(make_single_data_row("Variance ($)", primary_year, "$", p_metrics["variance"]))
    tbody_rows.append(make_single_data_row("Variance Percentage (%)", primary_year, "%", p_metrics["var_pct"], var_pcts=p_metrics["var_pct"]))
    tbody_rows.append(make_single_data_row("Validation Status", primary_year, "Status", p_metrics["pos_val"], var_pcts=p_metrics["var_pct"]))

    # 4. BRAND LEVEL BREAKDOWN
    if not df.empty and 'POS_BRAND' in df.columns:
        tbody_rows.append(html.Tr([
            html.Td("BRAND LEVEL BREAKDOWN (SNOWFLAKE JOINED)", colSpan=21, style={
                "backgroundColor": "#000000", "color": "#ffffff", "fontWeight": "800", "fontSize": "12px", "padding": "8px 12px", "textAlign": "left"
            })
        ]))

        for b_name, grp in df.groupby('POS_BRAND'):
            if not b_name: continue
            b_vals = [None] * 12
            for _, r in grp.iterrows():
                d_str = str(r.get('GLOBAL_DATE_SHORT_DESC', ''))
                parts = d_str.split('-')
                if len(parts) == 2:
                    m_str = parts[0].upper()
                    idx = month_idx_map.get(m_str)
                    if idx is not None:
                        pv = r.get('POS_VALUE')
                        b_vals[idx] = (b_vals[idx] or 0.0) + float(pv) if pd.notnull(pv) else b_vals[idx]
            tbody_rows.append(make_single_data_row(f"Brand: {b_name} ($)", "2026", "$", b_vals))

    tbody = html.Tbody(tbody_rows)
    table_elem = html.Table([thead, tbody], style={
        "width": "100%", "borderCollapse": "collapse", "fontFamily": "sans-serif", "fontSize": "11px"
    })

    return record_str, table_elem


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8050"))
    debug = os.getenv("DEBUG", "True").lower() in ["true", "1", "t"]

    print(f"Starting Consumption Validation Dashboard at http://{host}:{port}...")
    app.run(host=host, port=port, debug=debug)
