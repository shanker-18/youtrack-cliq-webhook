import os
import datetime
import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import database
import sync
import style

db_init_result = database.initialize_database()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Kenvue NA IBP Validation Dashboard"
)
server = app.server

COLOR_TRUST_GREEN = style.COLOR_TRUST_GREEN
COLOR_CARE_YELLOW = style.COLOR_CARE_YELLOW
COLOR_EMPATHY_PURPLE = style.COLOR_EMPATHY_PURPLE
COLOR_COURAGE_CORAL = style.COLOR_COURAGE_CORAL

app.layout = html.Div([
    html.Div([
        html.Div([
            html.Span("KENVUE", className="kenvue-logo-badge"),
            html.H1("Kenvue NA IBP Validation Dashboard")
        ], className="kenvue-brand-title"),
        html.Div(id="header-last-updated", className="kenvue-header-timestamp")
    ], className="kenvue-header"),

    html.Div([
        dbc.Tabs([
            dbc.Tab(label="Validation Dashboard", tab_id="tab-dashboard", label_style={"cursor": "pointer"}),
            dbc.Tab(label="Planning", tab_id="tab-planning", label_style={"cursor": "pointer"}),
        ], id="main-tabs", active_tab="tab-dashboard", className="kenvue-tabs"),

        html.Div(id="page-content")
    ], className="kenvue-container"),

    dcc.Store(id="sync-trigger-store", data=0),
    dcc.Store(id="crud-trigger-store", data=0),

    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Add New Planning Record")),
        dbc.ModalBody([
            dbc.Form([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Planning Date", html_for="add-date"),
                        dbc.Input(type="date", id="add-date", value=datetime.date.today().strftime("%Y-%m-%d")),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Product Name", html_for="add-product"),
                        dbc.Input(type="text", id="add-product", placeholder="e.g. Tylenol Extra Strength"),
                    ], width=4),
                    dbc.Col([
                        dbc.Label("Product Category", html_for="add-category"),
                        dbc.Input(type="text", id="add-category", placeholder="e.g. Pain Care"),
                    ], width=4),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Region", html_for="add-region"),
                        dbc.Input(type="text", id="add-region", placeholder="e.g. US East"),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Business Unit", html_for="add-bu"),
                        dbc.Input(type="text", id="add-bu", placeholder="e.g. Self Care"),
                    ], width=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Planned Volume", html_for="add-planned-vol"),
                        dbc.Input(type="number", id="add-planned-vol", value=0),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Actual Consumption", html_for="add-actual-cons"),
                        dbc.Input(type="number", id="add-actual-cons", value=0),
                    ], width=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Status", html_for="add-status"),
                        dbc.Select(
                            id="add-status",
                            options=[
                                {"label": "Draft", "value": "Draft"},
                                {"label": "Active", "value": "Active"},
                                {"label": "Approved", "value": "Approved"},
                                {"label": "Under Review", "value": "Under Review"},
                            ],
                            value="Active"
                        ),
                    ], width=12),
                ], className="mb-3"),
            ])
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-cancel-add", className="me-2", color="secondary"),
            dbc.Button("Save Record", id="btn-save-add", color="success", className="btn-kenvue-primary"),
        ]),
    ], id="modal-add-record", is_open=False, size="lg"),

    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Edit Planning Record")),
        dbc.ModalBody([
            dbc.Form([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Planning ID", html_for="edit-id"),
                        dbc.Input(type="text", id="edit-id", disabled=True),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Planning Date", html_for="edit-date"),
                        dbc.Input(type="text", id="edit-date"),
                    ], width=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Product Name", html_for="edit-product"),
                        dbc.Input(type="text", id="edit-product"),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Product Category", html_for="edit-category"),
                        dbc.Input(type="text", id="edit-category"),
                    ], width=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Region", html_for="edit-region"),
                        dbc.Input(type="text", id="edit-region"),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Business Unit", html_for="edit-bu"),
                        dbc.Input(type="text", id="edit-bu"),
                    ], width=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Planned Volume", html_for="edit-planned-vol"),
                        dbc.Input(type="number", id="edit-planned-vol"),
                    ], width=6),
                    dbc.Col([
                        dbc.Label("Actual Consumption", html_for="edit-actual-cons"),
                        dbc.Input(type="number", id="edit-actual-cons"),
                    ], width=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Status", html_for="edit-status"),
                        dbc.Select(
                            id="edit-status",
                            options=[
                                {"label": "Draft", "value": "Draft"},
                                {"label": "Active", "value": "Active"},
                                {"label": "Approved", "value": "Approved"},
                                {"label": "Under Review", "value": "Under Review"},
                            ]
                        ),
                    ], width=12),
                ], className="mb-3"),
            ])
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-cancel-edit", className="me-2", color="secondary"),
            dbc.Button("Update Record", id="btn-save-edit", color="primary", className="btn-kenvue-primary"),
        ]),
    ], id="modal-edit-record", is_open=False, size="lg"),
])

def build_dashboard_layout():
    data = database.fetch_dashboard_data()
    sync_banner = html.Div(id="sync-status-alert")

    if not data["has_data"]:
        return html.Div([
            html.Div([
                html.Div([
                    html.H4("Source Synchronization", style={"margin": 0, "color": COLOR_TRUST_GREEN, "fontWeight": "700"}),
                    html.P("Refresh latest IBP datasets directly from Snowflake source tables.", style={"margin": 0, "color": "#6c757d", "fontSize": "13px"})
                ]),
                dbc.Button([
                    "SYNC DATA FROM SNOWFLAKE"
                ], id="btn-sync-snowflake", className="btn-sync-snowflake", n_clicks=0),
            ], className="sync-section"),

            sync_banner,

            html.Div([
                html.Div("📊", className="empty-state-icon"),
                html.Div("No Data Available in Snowflake", className="empty-state-title"),
                html.Div("The Snowflake database currently contains no records. Please click 'SYNC DATA FROM SNOWFLAKE' above to refresh source data.", className="empty-state-text"),
            ], className="empty-state-card")
        ])

    kpis = data["kpis"]
    planning_df = data["planning_df"]
    consumption_df = data["consumption_df"]
    shipment_df = data["shipment_df"]

    categories = sorted(planning_df["product_category"].dropna().unique().tolist()) if not planning_df.empty and "product_category" in planning_df.columns else []
    products = sorted(planning_df["product"].dropna().unique().tolist()) if not planning_df.empty and "product" in planning_df.columns else []

    category_options = [{"label": "All Categories", "value": "ALL"}] + [{"label": c, "value": c} for c in categories]
    product_options = [{"label": "All Products", "value": "ALL"}] + [{"label": p, "value": p} for p in products]

    additional_charts = []

    if not consumption_df.empty and "consumption_date" in consumption_df.columns and "consumption_volume" in consumption_df.columns:
        consumption_df['date_str'] = pd.to_datetime(consumption_df['consumption_date']).dt.strftime('%Y-%m-%d')
        agg_cons = consumption_df.groupby("date_str")["consumption_volume"].sum().reset_index()
        fig2 = px.line(
            agg_cons,
            x="date_str",
            y="consumption_volume",
            markers=True,
            title="Consumption Volume Trend over Date",
            labels={"consumption_volume": "Consumption Volume", "date_str": "Date"},
            color_discrete_sequence=[COLOR_EMPATHY_PURPLE]
        )
        fig2.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
        additional_charts.append(dbc.Col(html.Div([
            html.Div("Consumption Volume Trend", className="chart-title"),
            dcc.Graph(figure=fig2)
        ], className="chart-card"), width=6))

    if not shipment_df.empty and "shipment_date" in shipment_df.columns and "actual_shipment_volume" in shipment_df.columns:
        shipment_df['date_str'] = pd.to_datetime(shipment_df['shipment_date']).dt.strftime('%Y-%m-%d')
        agg_ship = shipment_df.groupby("date_str")[["planned_shipment_volume", "actual_shipment_volume"]].sum().reset_index()
        fig3 = px.line(
            agg_ship,
            x="date_str",
            y=["planned_shipment_volume", "actual_shipment_volume"],
            markers=True,
            title="Planned vs Actual Shipment Volume Trend",
            labels={"value": "Shipment Volume", "date_str": "Date", "variable": "Metric"},
            color_discrete_sequence=[COLOR_COURAGE_CORAL, COLOR_TRUST_GREEN]
        )
        fig3.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
        additional_charts.append(dbc.Col(html.Div([
            html.Div("Shipment Trend", className="chart-title"),
            dcc.Graph(figure=fig3)
        ], className="chart-card"), width=6))

    table_columns = [{"name": c.replace("_", " ").title(), "id": c} for c in planning_df.columns] if not planning_df.empty else []

    return html.Div([
        html.Div([
            html.Div([
                html.H4("Source Synchronization", style={"margin": 0, "color": COLOR_TRUST_GREEN, "fontWeight": "700"}),
                html.P("Refresh latest IBP datasets directly from Snowflake source tables.", style={"margin": 0, "color": "#6c757d", "fontSize": "13px"})
            ]),
            dbc.Button([
                "SYNC DATA FROM SNOWFLAKE"
            ], id="btn-sync-snowflake", className="btn-sync-snowflake", n_clicks=0),
        ], className="sync-section"),

        sync_banner,

        html.Div([
            html.Div([
                html.Div("Total Planning Records", className="kpi-title"),
                html.Div(f"{kpis['total_planning_records']:,}", className="kpi-value")
            ], className="kpi-card"),
            html.Div([
                html.Div("Total Consumption Volume", className="kpi-title"),
                html.Div(f"{kpis['total_consumption']:,.1f}", className="kpi-value")
            ], className="kpi-card yellow"),
            html.Div([
                html.Div("Total Shipment Volume", className="kpi-title"),
                html.Div(f"{kpis['total_shipments']:,.1f}", className="kpi-value")
            ], className="kpi-card purple"),
            html.Div([
                html.Div("Planned Volume", className="kpi-title"),
                html.Div(f"{kpis['planned_volume']:,.1f}", className="kpi-value")
            ], className="kpi-card"),
            html.Div([
                html.Div("Actual Volume", className="kpi-title"),
                html.Div(f"{kpis['actual_volume']:,.1f}", className="kpi-value")
            ], className="kpi-card coral"),
            html.Div([
                html.Div("Plan Variance", className="kpi-title"),
                html.Div(f"{kpis['variance']:,.1f}", className="kpi-value")
            ], className="kpi-card"),
        ], className="kpi-grid"),

        html.Div([
            html.H5("Interactive Volume Comparison Filter", style={"color": COLOR_TRUST_GREEN, "fontWeight": "700", "marginBottom": "16px"}),
            dbc.Row([
                dbc.Col([
                    html.Label("Select Product Category:", style={"fontWeight": "600", "fontSize": "14px", "marginBottom": "6px"}),
                    dcc.Dropdown(
                        id="filter-category",
                        options=category_options,
                        value="ALL",
                        clearable=False,
                        placeholder="Select Category..."
                    )
                ], width=6),
                dbc.Col([
                    html.Label("Select Product Name:", style={"fontWeight": "600", "fontSize": "14px", "marginBottom": "6px"}),
                    dcc.Dropdown(
                        id="filter-product",
                        options=product_options,
                        value="ALL",
                        clearable=False,
                        placeholder="Select Product..."
                    )
                ], width=6),
            ]),
        ], className="chart-card", style={"marginBottom": "20px"}),

        html.Div([
            html.Div(id="interactive-chart-heading", className="chart-title"),
            dcc.Graph(id="interactive-planned-vs-actual-graph")
        ], className="chart-card"),

        dbc.Row(additional_charts) if additional_charts else html.Div(),

        html.Div([
            html.H5("Snowflake Validation Data Summary", style={"color": COLOR_TRUST_GREEN, "fontWeight": "700", "marginBottom": "16px"}),
            dash_table.DataTable(
                data=planning_df.to_dict("records") if not planning_df.empty else [],
                columns=table_columns,
                page_size=10,
                sort_action="native",
                filter_action="native",
                style_table={'overflowX': 'auto'},
                style_header={
                    'backgroundColor': COLOR_TRUST_GREEN,
                    'color': 'white',
                    'fontWeight': 'bold',
                    'textAlign': 'left'
                },
                style_cell={
                    'textAlign': 'left',
                    'padding': '12px',
                    'fontSize': '14px',
                    'fontFamily': 'sans-serif'
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#F8F9FA'}
                ]
            )
        ], className="datatable-card")
    ])

def build_planning_layout():
    df = database.fetch_planning_data()
    table_columns = [{"name": c.replace("_", " ").title(), "id": c} for c in df.columns] if not df.empty else []

    return html.Div([
        html.Div(id="planning-crud-alert"),

        html.Div([
            html.Div([
                html.H4("Planning Records Management", style={"margin": 0, "color": COLOR_TRUST_GREEN, "fontWeight": "700"}),
                html.P("Manage and update Planning data stored in Snowflake database.", style={"margin": 0, "color": "#6c757d", "fontSize": "13px"})
            ]),
            html.Div([
                dbc.Button("ADD PLANNING RECORD", id="btn-open-add", color="success", className="btn-kenvue-primary me-2"),
                dbc.Button("EDIT SELECTED", id="btn-open-edit", color="primary", className="me-2"),
                dbc.Button("DELETE SELECTED", id="btn-delete-record", color="danger"),
            ], className="d-flex align-items-center")
        ], className="sync-section"),

        html.Div([
            dash_table.DataTable(
                id="planning-datatable",
                data=df.to_dict("records") if not df.empty else [],
                columns=table_columns,
                row_selectable="single",
                selected_rows=[],
                page_size=12,
                sort_action="native",
                filter_action="native",
                style_table={'overflowX': 'auto'},
                style_header={
                    'backgroundColor': COLOR_TRUST_GREEN,
                    'color': 'white',
                    'fontWeight': 'bold',
                    'textAlign': 'left'
                },
                style_cell={
                    'textAlign': 'left',
                    'padding': '12px',
                    'fontSize': '14px',
                    'fontFamily': 'sans-serif'
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#F8F9FA'},
                    {'if': {'column_id': 'is_manually_edited'}, 'fontWeight': 'bold', 'color': COLOR_COURAGE_CORAL}
                ]
            )
        ], className="datatable-card")
    ])

@app.callback(
    Output("header-last-updated", "children"),
    [Input("sync-trigger-store", "data"), Input("crud-trigger-store", "data")]
)
def update_header_timestamp(sync_trig, crud_trig):
    info = database.get_last_sync_info()
    if info and info.get("sync_completed_at"):
        ts = info["sync_completed_at"].strftime("%Y-%m-%d %H:%M:%S")
        status = info.get("status", "SUCCESS")
        return f"Last Snowflake Sync: {ts} ({status})"
    return "Last Snowflake Sync: Not Yet Synced"

@app.callback(
    Output("page-content", "children"),
    [Input("main-tabs", "active_tab"),
     Input("sync-trigger-store", "data"),
     Input("crud-trigger-store", "data")]
)
def render_page_content(active_tab, sync_trig, crud_trig):
    if active_tab == "tab-planning":
        return build_planning_layout()
    return build_dashboard_layout()

@app.callback(
    Output("filter-product", "options"),
    Input("filter-category", "value")
)
def update_product_dropdown(selected_category):
    data = database.fetch_dashboard_data()
    planning_df = data["planning_df"]
    
    if planning_df.empty or "product" not in planning_df.columns:
        return [{"label": "All Products", "value": "ALL"}]

    if selected_category and selected_category != "ALL" and "product_category" in planning_df.columns:
        filtered = planning_df[planning_df["product_category"] == selected_category]
        products = sorted(filtered["product"].dropna().unique().tolist())
    else:
        products = sorted(planning_df["product"].dropna().unique().tolist())

    return [{"label": "All Products", "value": "ALL"}] + [{"label": p, "value": p} for p in products]

@app.callback(
    [Output("interactive-planned-vs-actual-graph", "figure"),
     Output("interactive-chart-heading", "children")],
    [Input("filter-category", "value"),
     Input("filter-product", "value"),
     Input("sync-trigger-store", "data"),
     Input("crud-trigger-store", "data")]
)
def update_interactive_chart(selected_category, selected_product, sync_trig, crud_trig):
    data = database.fetch_dashboard_data()
    planning_df = data["planning_df"]

    if planning_df.empty or "planned_volume" not in planning_df.columns or "actual_consumption" not in planning_df.columns:
        fig = px.bar(title="No Data Available for Planned vs Consumption Volume")
        fig.update_layout(template="plotly_white")
        return fig, "Planned Volume vs Actual Consumption"

    filtered_df = planning_df.copy()

    cat_label = selected_category if selected_category and selected_category != "ALL" else "All Categories"
    prod_label = selected_product if selected_product and selected_product != "ALL" else "All Products"

    if selected_category and selected_category != "ALL" and "product_category" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["product_category"] == selected_category]

    if selected_product and selected_product != "ALL" and "product" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["product"] == selected_product]

    if filtered_df.empty:
        fig = px.bar(title="No matching records found for selected filters")
        fig.update_layout(template="plotly_white")
        return fig, f"Planned Volume vs Actual Consumption — Category: {cat_label} | Product: {prod_label}"

    if "planning_date" in filtered_df.columns:
        filtered_df["planning_date"] = pd.to_datetime(filtered_df["planning_date"]).dt.strftime("%Y-%m-%d")

    group_col = "product" if ("product" in filtered_df.columns and len(filtered_df["product"].unique()) > 1) else "planning_date"
    if group_col not in filtered_df.columns:
        group_col = filtered_df.columns[0]

    agg_df = filtered_df.groupby(group_col)[["planned_volume", "actual_consumption"]].sum().reset_index()

    fig = px.bar(
        agg_df,
        x=group_col,
        y=["planned_volume", "actual_consumption"],
        barmode="group",
        title=f"Planned Volume vs Actual Consumption ({cat_label} - {prod_label})",
        labels={"value": "Volume (Units)", group_col: group_col.replace("_", " ").title(), "variable": "Volume Metric"},
        color_discrete_map={
            "planned_volume": COLOR_TRUST_GREEN,
            "actual_consumption": COLOR_CARE_YELLOW
        }
    )
    fig.update_xaxes(type='category')
    fig.update_layout(
        template="plotly_white",
        legend_title_text="Metric",
        margin=dict(l=20, r=20, t=50, b=20),
        font=dict(family="sans-serif", size=13)
    )

    heading = f"Planned Volume vs Actual Consumption — Category: {cat_label} | Product: {prod_label}"
    return fig, heading

@app.callback(
    [Output("sync-status-alert", "children"),
     Output("sync-trigger-store", "data")],
    Input("btn-sync-snowflake", "n_clicks"),
    State("sync-trigger-store", "data"),
    prevent_initial_call=True
)
def handle_snowflake_sync(n_clicks, current_trig):
    if not n_clicks:
        return dash.no_update, dash.no_update

    res = sync.sync_snowflake_to_postgres()
    
    if res["success"]:
        color = "success" if res.get("status") == "SUCCESS" else "warning"
        msg = res["message"]
    else:
        color = "danger"
        msg = f"Sync Error: {res['message']}"

    alert = dbc.Alert(msg, color=color, dismissable=True, className="mt-3 mb-3")
    return alert, (current_trig or 0) + 1

@app.callback(
    Output("modal-add-record", "is_open"),
    [Input("btn-open-add", "n_clicks"), Input("btn-cancel-add", "n_clicks"), Input("btn-save-add", "n_clicks")],
    State("modal-add-record", "is_open"),
    prevent_initial_call=True
)
def toggle_add_modal(open_clicks, cancel_clicks, save_clicks, is_open):
    return not is_open

@app.callback(
    [Output("crud-trigger-store", "data"), Output("planning-crud-alert", "children")],
    Input("btn-save-add", "n_clicks"),
    [State("add-date", "value"),
     State("add-product", "value"),
     State("add-category", "value"),
     State("add-region", "value"),
     State("add-bu", "value"),
     State("add-planned-vol", "value"),
     State("add-actual-cons", "value"),
     State("add-status", "value"),
     State("crud-trigger-store", "data")],
    prevent_initial_call=True
)
def save_new_record(n_clicks, planning_date, product, category, region, bu, planned_vol, actual_cons, status, current_trig):
    if not n_clicks:
        return dash.no_update, dash.no_update

    record = {
        "planning_date": planning_date,
        "product": product,
        "product_category": category,
        "region": region,
        "business_unit": bu,
        "planned_volume": planned_vol,
        "actual_consumption": actual_cons,
        "status": status
    }
    res = database.insert_planning_record(record)
    
    color = "success" if res["success"] else "danger"
    alert = dbc.Alert(res["message"], color=color, dismissable=True, className="mb-3")
    return (current_trig or 0) + 1, alert

@app.callback(
    [Output("modal-edit-record", "is_open"),
     Output("edit-id", "value"),
     Output("edit-date", "value"),
     Output("edit-product", "value"),
     Output("edit-category", "value"),
     Output("edit-region", "value"),
     Output("edit-bu", "value"),
     Output("edit-planned-vol", "value"),
     Output("edit-actual-cons", "value"),
     Output("edit-status", "value")],
    [Input("btn-open-edit", "n_clicks"), Input("btn-cancel-edit", "n_clicks")],
    [State("planning-datatable", "selected_rows"),
     State("planning-datatable", "data"),
     State("modal-edit-record", "is_open")],
    prevent_initial_call=True
)
def populate_and_toggle_edit(open_clicks, cancel_clicks, selected_rows, table_data, is_open):
    ctx = callback_context
    if not ctx.triggered:
        return False, "", "", "", "", "", "", 0, 0, "Active"

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "btn-cancel-edit":
        return False, "", "", "", "", "", "", 0, 0, "Active"

    if button_id == "btn-open-edit":
        if not selected_rows or not table_data:
            return False, "", "", "", "", "", "", 0, 0, "Active"

        row = table_data[selected_rows[0]]
        return (
            True,
            str(row.get("planning_id", "")),
            str(row.get("planning_date", "")),
            str(row.get("product", "")),
            str(row.get("product_category", "")),
            str(row.get("region", "")),
            str(row.get("business_unit", "")),
            row.get("planned_volume", 0),
            row.get("actual_consumption", 0),
            str(row.get("status", "Active"))
        )

    return is_open, "", "", "", "", "", "", 0, 0, "Active"

@app.callback(
    [Output("crud-trigger-store", "data", allow_duplicate=True),
     Output("planning-crud-alert", "children", allow_duplicate=True),
     Output("modal-edit-record", "is_open", allow_duplicate=True)],
    Input("btn-save-edit", "n_clicks"),
    [State("edit-id", "value"),
     State("edit-date", "value"),
     State("edit-product", "value"),
     State("edit-category", "value"),
     State("edit-region", "value"),
     State("edit-bu", "value"),
     State("edit-planned-vol", "value"),
     State("edit-actual-cons", "value"),
     State("edit-status", "value"),
     State("crud-trigger-store", "data")],
    prevent_initial_call=True
)
def update_existing_record(n_clicks, planning_id, planning_date, product, category, region, bu, planned_vol, actual_cons, status, current_trig):
    if not n_clicks or not planning_id:
        return dash.no_update, dash.no_update, True

    record = {
        "planning_date": planning_date,
        "product": product,
        "product_category": category,
        "region": region,
        "business_unit": bu,
        "planned_volume": planned_vol,
        "actual_consumption": actual_cons,
        "status": status
    }
    res = database.update_planning_record(planning_id, record)
    
    color = "success" if res["success"] else "danger"
    alert = dbc.Alert(res["message"], color=color, dismissable=True, className="mb-3")
    return (current_trig or 0) + 1, alert, False

@app.callback(
    [Output("crud-trigger-store", "data", allow_duplicate=True),
     Output("planning-crud-alert", "children", allow_duplicate=True)],
    Input("btn-delete-record", "n_clicks"),
    [State("planning-datatable", "selected_rows"),
     State("planning-datatable", "data"),
     State("crud-trigger-store", "data")],
    prevent_initial_call=True
)
def delete_record(n_clicks, selected_rows, table_data, current_trig):
    if not n_clicks or not selected_rows or not table_data:
        return dash.no_update, dash.no_update

    row = table_data[selected_rows[0]]
    planning_id = row.get("planning_id")
    
    if not planning_id:
        alert = dbc.Alert("Select a valid row with a Planning ID to delete.", color="warning", dismissable=True, className="mb-3")
        return dash.no_update, alert

    res = database.delete_planning_record(planning_id)
    color = "success" if res["success"] else "danger"
    alert = dbc.Alert(res["message"], color=color, dismissable=True, className="mb-3")
    return (current_trig or 0) + 1, alert

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8050"))
    debug = os.getenv("DEBUG", "True").lower() in ["true", "1", "t"]
    
    print(f"Starting Kenvue NA IBP Validation Dashboard at http://{host}:{port}...")
    app.run(host=host, port=port, debug=debug)
