:root {
  --kenvue-trust-green: #005A38;
  --kenvue-trust-green-dark: #004229;
  --kenvue-care-yellow: #FFB800;
  --kenvue-empathy-purple: #6A2676;
  --kenvue-courage-coral: #E05A47;
  --kenvue-bg-light: #F8F9FA;
  --kenvue-card-bg: #FFFFFF;
  --kenvue-text-main: #212529;
  --kenvue-text-muted: #6C757D;
  --kenvue-border: #E9ECEF;
  --kenvue-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

body {
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: var(--kenvue-bg-light);
  color: var(--kenvue-text-main);
  -webkit-font-smoothing: antialiased;
}

.kenvue-header {
  background-color: var(--kenvue-trust-green);
  color: #ffffff;
  padding: 16px 32px;
  box-shadow: 0 2px 10px rgba(0, 90, 56, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kenvue-brand-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.kenvue-logo-badge {
  background-color: var(--kenvue-care-yellow);
  color: #000000;
  font-weight: 800;
  font-size: 14px;
  padding: 4px 10px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}

.kenvue-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
}

.kenvue-header-timestamp {
  font-size: 13px;
  opacity: 0.9;
  background: rgba(255, 255, 255, 0.15);
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.kenvue-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.kenvue-tabs {
  margin-bottom: 24px;
}

.nav-tabs .nav-link {
  font-size: 15px;
  font-weight: 600;
  color: var(--kenvue-text-muted);
  border: none !important;
  padding: 12px 24px;
  border-radius: 8px 8px 0 0 !important;
  transition: all 0.2s ease;
}

.nav-tabs .nav-link:hover {
  color: var(--kenvue-trust-green);
}

.nav-tabs .nav-link.active {
  color: var(--kenvue-trust-green) !important;
  background-color: transparent !important;
  border-bottom: 3px solid var(--kenvue-trust-green) !important;
}

.sync-section {
  background: var(--kenvue-card-bg);
  padding: 20px 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--kenvue-border);
}

.btn-sync-snowflake {
  background-color: var(--kenvue-trust-green) !important;
  color: #ffffff !important;
  font-weight: 700 !important;
  font-size: 14px !important;
  padding: 10px 24px !important;
  border-radius: 8px !important;
  border: none !important;
  box-shadow: 0 4px 8px rgba(0, 90, 56, 0.25) !important;
  transition: all 0.2s ease !important;
  cursor: pointer;
}

.btn-sync-snowflake:hover {
  background-color: var(--kenvue-trust-green-dark) !important;
  transform: translateY(-1px);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.kpi-card {
  background: var(--kenvue-card-bg);
  padding: 20px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border-left: 5px solid var(--kenvue-trust-green);
  border-top: 1px solid var(--kenvue-border);
  border-right: 1px solid var(--kenvue-border);
  border-bottom: 1px solid var(--kenvue-border);
  transition: transform 0.2s ease;
}

.kpi-card:hover {
  transform: translateY(-2px);
}

.kpi-card.yellow {
  border-left-color: var(--kenvue-care-yellow);
}

.kpi-card.purple {
  border-left-color: var(--kenvue-empathy-purple);
}

.kpi-card.coral {
  border-left-color: var(--kenvue-courage-coral);
}

.kpi-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--kenvue-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.kpi-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--kenvue-text-main);
}

.chart-card {
  background: var(--kenvue-card-bg);
  padding: 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border: 1px solid var(--kenvue-border);
  margin-bottom: 24px;
}

.chart-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--kenvue-trust-green);
  margin-bottom: 16px;
}

.empty-state-card {
  background: var(--kenvue-card-bg);
  padding: 48px 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border: 2px dashed var(--kenvue-border);
  text-align: center;
  margin-bottom: 24px;
}

.empty-state-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-state-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--kenvue-trust-green);
  margin-bottom: 8px;
}

.empty-state-text {
  font-size: 15px;
  color: var(--kenvue-text-muted);
  max-width: 500px;
  margin: 0 auto;
}

.datatable-card {
  background: var(--kenvue-card-bg);
  padding: 24px;
  border-radius: 12px;
  box-shadow: var(--kenvue-shadow);
  border: 1px solid var(--kenvue-border);
  margin-bottom: 24px;
}

.modal-header {
  background-color: var(--kenvue-trust-green);
  color: #ffffff;
  border-radius: 8px 8px 0 0;
}

.modal-header .btn-close {
  filter: invert(1);
}

.btn-kenvue-primary {
  background-color: var(--kenvue-trust-green) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
}

.btn-kenvue-primary:hover {
  background-color: var(--kenvue-trust-green-dark) !important;
}

.btn-kenvue-coral {
  background-color: var(--kenvue-courage-coral) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
}

import os
import datetime
import dash
from dash import dcc, html, dash_table, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

import database
import sync

db_init_result = database.initialize_database()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Kenvue NA IBP Validation Dashboard"
)
server = app.server

COLOR_TRUST_GREEN = "#005A38"
COLOR_CARE_YELLOW = "#FFB800"
COLOR_EMPATHY_PURPLE = "#6A2676"
COLOR_COURAGE_CORAL = "#E05A47"

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
                    html.P("Copy latest IBP datasets from Snowflake into PostgreSQL application database.", style={"margin": 0, "color": "#6c757d", "fontSize": "13px"})
                ]),
                dbc.Button([
                    "SYNC DATA FROM SNOWFLAKE"
                ], id="btn-sync-snowflake", className="btn-sync-snowflake", n_clicks=0),
            ], className="sync-section"),

            sync_banner,

            html.Div([
                html.Div("📊", className="empty-state-icon"),
                html.Div("No Data Available in PostgreSQL", className="empty-state-title"),
                html.Div("The PostgreSQL application database is currently empty. Please click 'SYNC DATA FROM SNOWFLAKE' above to fetch real data from Snowflake source tables.", className="empty-state-text"),
            ], className="empty-state-card")
        ])

    kpis = data["kpis"]
    planning_df = data["planning_df"]
    consumption_df = data["consumption_df"]
    shipment_df = data["shipment_df"]

    charts_list = []

    if not planning_df.empty and "product" in planning_df.columns and "planned_volume" in planning_df.columns and "actual_consumption" in planning_df.columns:
        agg_plan = planning_df.groupby("product")[["planned_volume", "actual_consumption"]].sum().reset_index()
        fig1 = px.bar(
            agg_plan,
            x="product",
            y=["planned_volume", "actual_consumption"],
            barmode="group",
            title="Planned Volume vs Actual Consumption by Product",
            labels={"value": "Volume (Units)", "product": "Product", "variable": "Metric"},
            color_discrete_sequence=[COLOR_TRUST_GREEN, COLOR_CARE_YELLOW]
        )
        fig1.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
        charts_list.append(dbc.Col(html.Div([
            html.Div("Planned Volume vs Actual Consumption", className="chart-title"),
            dcc.Graph(figure=fig1)
        ], className="chart-card"), width=6))

    if not consumption_df.empty and "consumption_date" in consumption_df.columns and "consumption_volume" in consumption_df.columns:
        consumption_df['date_str'] = pd.to_datetime(consumption_df['consumption_date']).dt.strftime('%Y-%m-%d')
        agg_cons = consumption_df.groupby("date_str")["consumption_volume"].sum().reset_index()
        fig2 = px.line(
            agg_cons,
            x="date_str",
            y="consumption_volume",
            markers=True,
            title="Consumption Trend over Date",
            labels={"consumption_volume": "Consumption Volume", "date_str": "Date"},
            color_discrete_sequence=[COLOR_EMPATHY_PURPLE]
        )
        fig2.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
        charts_list.append(dbc.Col(html.Div([
            html.Div("Consumption Trend", className="chart-title"),
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
        charts_list.append(dbc.Col(html.Div([
            html.Div("Shipment Trend", className="chart-title"),
            dcc.Graph(figure=fig3)
        ], className="chart-card"), width=6))

    if not planning_df.empty and "region" in planning_df.columns and "plan_variance" in planning_df.columns:
        agg_var = planning_df.groupby("region")["plan_variance"].sum().reset_index()
        fig4 = px.bar(
            agg_var,
            x="region",
            y="plan_variance",
            title="Planning Variance by Region",
            labels={"plan_variance": "Plan Variance", "region": "Region"},
            color_discrete_sequence=[COLOR_TRUST_GREEN]
        )
        fig4.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
        charts_list.append(dbc.Col(html.Div([
            html.Div("Planning Variance by Region", className="chart-title"),
            dcc.Graph(figure=fig4)
        ], className="chart-card"), width=6))

    table_columns = [{"name": c.replace("_", " ").title(), "id": c} for c in planning_df.columns] if not planning_df.empty else []

    return html.Div([
        html.Div([
            html.Div([
                html.H4("Source Synchronization", style={"margin": 0, "color": COLOR_TRUST_GREEN, "fontWeight": "700"}),
                html.P("Copy latest IBP datasets from Snowflake into PostgreSQL application database.", style={"margin": 0, "color": "#6c757d", "fontSize": "13px"})
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

        dbc.Row(charts_list) if charts_list else html.Div(),

        html.Div([
            html.H5("PostgreSQL Validation Data Summary", style={"color": COLOR_TRUST_GREEN, "fontWeight": "700", "marginBottom": "16px"}),
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
                html.P("Manage and update Planning data stored in PostgreSQL application database.", style={"margin": 0, "color": "#6c757d", "fontSize": "13px"})
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


import os
import uuid
import datetime
import warnings
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

warnings.filterwarnings('ignore', category=UserWarning)

load_dotenv()

def get_postgres_connection():
    load_dotenv(override=True)
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DATABASE", "kenvue_ibp")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    if not database or not user:
        raise ValueError("PostgreSQL environment variables (POSTGRES_DATABASE, POSTGRES_USER) must be set.")

    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password
    )
    return conn

def initialize_database():
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS planning_data (
                planning_id VARCHAR(50) PRIMARY KEY,
                planning_date DATE,
                region VARCHAR(100),
                business_unit VARCHAR(100),
                product VARCHAR(150),
                product_category VARCHAR(100),
                planned_volume NUMERIC(18,2),
                actual_consumption NUMERIC(18,2),
                forecast_accuracy NUMERIC(5,2),
                plan_variance NUMERIC(10,2),
                status VARCHAR(50),
                created_at TIMESTAMP,
                data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
                is_manually_edited BOOLEAN DEFAULT FALSE,
                last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS consumption_data (
                consumption_id VARCHAR(50) PRIMARY KEY,
                consumption_date DATE,
                region VARCHAR(100),
                business_unit VARCHAR(100),
                product VARCHAR(150),
                product_category VARCHAR(100),
                consumption_volume NUMERIC(18,2),
                previous_month_volume NUMERIC(18,2),
                consumption_growth NUMERIC(10,2),
                status VARCHAR(50),
                created_at TIMESTAMP,
                data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
                is_manually_edited BOOLEAN DEFAULT FALSE,
                last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS shipment_data (
                shipment_id VARCHAR(50) PRIMARY KEY,
                shipment_date DATE,
                region VARCHAR(100),
                business_unit VARCHAR(100),
                product VARCHAR(150),
                product_category VARCHAR(100),
                planned_shipment_volume NUMERIC(18,2),
                actual_shipment_volume NUMERIC(18,2),
                fulfillment_rate NUMERIC(5,2),
                shipment_status VARCHAR(50),
                created_at TIMESTAMP,
                data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
                is_manually_edited BOOLEAN DEFAULT FALSE,
                last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id SERIAL PRIMARY KEY,
                sync_started_at TIMESTAMP,
                sync_completed_at TIMESTAMP,
                status VARCHAR(50),
                planning_records_synced INTEGER DEFAULT 0,
                consumption_records_synced INTEGER DEFAULT 0,
                shipment_records_synced INTEGER DEFAULT 0,
                error_message TEXT
            );
        """)

        conn.commit()
        cur.close()
        return {"success": True, "message": "PostgreSQL database initialized successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"PostgreSQL initialization failed: {str(e)}"}
    finally:
        if conn:
            conn.close()

def fetch_planning_data():
    conn = None
    try:
        conn = get_postgres_connection()
        query = "SELECT * FROM planning_data ORDER BY planning_date DESC, product ASC;"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception:
        cols = ["planning_id", "planning_date", "region", "business_unit", "product", "product_category", "planned_volume", "actual_consumption", "forecast_accuracy", "plan_variance", "status", "created_at", "data_source", "is_manually_edited", "last_modified_at"]
        return pd.DataFrame(columns=cols)
    finally:
        if conn:
            conn.close()

def insert_planning_record(data_dict):
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        planning_id = data_dict.get("planning_id") or f"PLN-{uuid.uuid4().hex[:8].upper()}"
        planning_date = data_dict.get("planning_date") or datetime.date.today().strftime("%Y-%m-%d")
        region = data_dict.get("region", "")
        business_unit = data_dict.get("business_unit", "")
        product = data_dict.get("product", "")
        product_category = data_dict.get("product_category", "")
        
        try:
            planned_vol = float(data_dict.get("planned_volume", 0) or 0)
        except (ValueError, TypeError):
            planned_vol = 0.0

        try:
            actual_cons = float(data_dict.get("actual_consumption", 0) or 0)
        except (ValueError, TypeError):
            actual_cons = 0.0

        plan_variance = planned_vol - actual_cons
        forecast_acc = ((1 - abs(plan_variance) / planned_vol) * 100) if planned_vol > 0 else 0.0
        status = data_dict.get("status", "Active")

        query = """
            INSERT INTO planning_data (
                planning_id, planning_date, region, business_unit, product, product_category,
                planned_volume, actual_consumption, forecast_accuracy, plan_variance, status,
                created_at, data_source, is_manually_edited, last_modified_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'MANUAL_PLANNING', TRUE, CURRENT_TIMESTAMP);
        """
        cur.execute(query, (planning_id, planning_date, region, business_unit, product, product_category, planned_vol, actual_cons, forecast_acc, plan_variance, status))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' inserted successfully.", "id": planning_id}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Failed to insert planning record: {str(e)}"}
    finally:
        if conn:
            conn.close()

def update_planning_record(planning_id, data_dict):
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        planning_date = data_dict.get("planning_date") or datetime.date.today().strftime("%Y-%m-%d")
        region = data_dict.get("region", "")
        business_unit = data_dict.get("business_unit", "")
        product = data_dict.get("product", "")
        product_category = data_dict.get("product_category", "")

        try:
            planned_vol = float(data_dict.get("planned_volume", 0) or 0)
        except (ValueError, TypeError):
            planned_vol = 0.0

        try:
            actual_cons = float(data_dict.get("actual_consumption", 0) or 0)
        except (ValueError, TypeError):
            actual_cons = 0.0

        plan_variance = planned_vol - actual_cons
        forecast_acc = ((1 - abs(plan_variance) / planned_vol) * 100) if planned_vol > 0 else 0.0
        status = data_dict.get("status", "Active")

        query = """
            UPDATE planning_data SET
                planning_date = %s,
                region = %s,
                business_unit = %s,
                product = %s,
                product_category = %s,
                planned_volume = %s,
                actual_consumption = %s,
                forecast_accuracy = %s,
                plan_variance = %s,
                status = %s,
                is_manually_edited = TRUE,
                last_modified_at = CURRENT_TIMESTAMP
            WHERE planning_id = %s;
        """
        cur.execute(query, (planning_date, region, business_unit, product, product_category, planned_vol, actual_cons, forecast_acc, plan_variance, status, planning_id))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' updated successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Failed to update planning record: {str(e)}"}
    finally:
        if conn:
            conn.close()

def delete_planning_record(planning_id):
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM planning_data WHERE planning_id = %s;", (planning_id,))
        conn.commit()
        cur.close()
        return {"success": True, "message": f"Planning record '{planning_id}' deleted successfully."}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Failed to delete planning record: {str(e)}"}
    finally:
        if conn:
            conn.close()

def fetch_dashboard_data():
    conn = None
    try:
        conn = get_postgres_connection()
        
        try:
            planning_df = pd.read_sql_query("SELECT * FROM planning_data;", conn)
        except Exception:
            planning_df = pd.DataFrame()

        try:
            consumption_df = pd.read_sql_query("SELECT * FROM consumption_data;", conn)
        except Exception:
            consumption_df = pd.DataFrame()

        try:
            shipment_df = pd.read_sql_query("SELECT * FROM shipment_data;", conn)
        except Exception:
            shipment_df = pd.DataFrame()

        total_planning_records = len(planning_df)
        total_consumption = float(consumption_df['consumption_volume'].sum()) if not consumption_df.empty and 'consumption_volume' in consumption_df.columns else 0.0
        total_shipments = float(shipment_df['actual_shipment_volume'].sum()) if not shipment_df.empty and 'actual_shipment_volume' in shipment_df.columns else 0.0

        planned_vol = float(planning_df['planned_volume'].sum()) if not planning_df.empty and 'planned_volume' in planning_df.columns else 0.0
        actual_cons = float(planning_df['actual_consumption'].sum()) if not planning_df.empty and 'actual_consumption' in planning_df.columns else 0.0
        variance = planned_vol - actual_cons

        kpis = {
            "total_planning_records": total_planning_records,
            "total_consumption": total_consumption,
            "total_shipments": total_shipments,
            "planned_volume": planned_vol,
            "actual_volume": actual_cons,
            "variance": variance
        }

        return {
            "has_data": not (planning_df.empty and consumption_df.empty and shipment_df.empty),
            "kpis": kpis,
            "planning_df": planning_df,
            "consumption_df": consumption_df,
            "shipment_df": shipment_df
        }
    except Exception as e:
        return {
            "has_data": False,
            "kpis": {
                "total_planning_records": 0,
                "total_consumption": 0.0,
                "total_shipments": 0.0,
                "planned_volume": 0.0,
                "actual_volume": 0.0,
                "variance": 0.0
            },
            "planning_df": pd.DataFrame(),
            "consumption_df": pd.DataFrame(),
            "shipment_df": pd.DataFrame(),
            "error": str(e)
        }
    finally:
        if conn:
            conn.close()

def get_last_sync_info():
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM sync_logs ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        if conn:
            conn.close()



dash>=2.14.0
dash-bootstrap-components>=1.5.0
pandas>=2.0.0
plotly>=5.18.0
snowflake-connector-python>=3.5.0
psycopg2-binary>=2.9.9
python-dotenv>=1.0.0




import os
import re
import datetime
import pandas as pd
import psycopg2
from dotenv import load_dotenv

from database import get_postgres_connection

load_dotenv()

def normalize_column_name(col_name):
    if not col_name:
        return "unnamed_column"
    
    col = str(col_name).strip()
    col = re.sub(r'[^a-zA-Z0-9]', '_', col)
    col = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', col)
    col = re.sub(r'_+', '_', col)
    return col.strip('_').lower()

def check_column_collisions(snowflake_cols):
    normalized_mapping = {}
    reverse_mapping = {}

    for orig_col in snowflake_cols:
        norm = normalize_column_name(orig_col)
        normalized_mapping[orig_col] = norm
        
        if norm in reverse_mapping:
            reverse_mapping[norm].append(orig_col)
        else:
            reverse_mapping[norm] = [orig_col]

    collisions = {norm: cols for norm, cols in reverse_mapping.items() if len(cols) > 1}
    
    if collisions:
        details = [f"Normalized column '{norm}' collides with original Snowflake columns: {cols}" for norm, cols in collisions.items()]
        err_msg = "SYNC ABORTED — Normalized column collision detected: " + "; ".join(details)
        return True, err_msg, normalized_mapping

    return False, "", normalized_mapping

def verify_unique_keys(normalized_cols, target_keys):
    missing_keys = [k for k in target_keys if k not in normalized_cols]
    if missing_keys:
        return False, missing_keys
    return True, []

def infer_pg_data_type(series):
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    elif pd.api.types.is_float_dtype(series):
        return "NUMERIC"
    elif pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    elif pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    else:
        return "TEXT"

def safe_align_postgres_schema(pg_conn, table_name, df, unique_keys):
    cur = pg_conn.cursor()
    
    key_defs = ", ".join([f"{k} VARCHAR(255)" for k in unique_keys])
    create_stmt = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {key_defs},
            data_source VARCHAR(50) DEFAULT 'SNOWFLAKE',
            is_manually_edited BOOLEAN DEFAULT FALSE,
            last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """
    cur.execute(create_stmt)

    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s;
    """, (table_name,))
    existing_pg_cols = {row[0].lower() for row in cur.fetchall()}

    for col in df.columns:
        if col.lower() not in existing_pg_cols:
            pg_type = infer_pg_data_type(df[col])
            alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col} {pg_type};"
            cur.execute(alter_stmt)

    index_name = f"idx_unique_{table_name}_" + "_".join(unique_keys)
    keys_clause = ", ".join(unique_keys)
    
    cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({keys_clause});")
    cur.close()

def upsert_dataframe_to_postgres(pg_conn, table_name, df, unique_keys):
    if df.empty:
        return 0

    cur = pg_conn.cursor()
    cols = list(df.columns)
    
    if 'data_source' not in cols:
        df['data_source'] = 'SNOWFLAKE'
        cols.append('data_source')
    if 'is_manually_edited' not in cols:
        df['is_manually_edited'] = False
        cols.append('is_manually_edited')
    if 'last_modified_at' not in cols:
        df['last_modified_at'] = datetime.datetime.now()
        cols.append('last_modified_at')

    non_key_cols = [c for c in cols if c not in unique_keys and c != 'is_manually_edited']
    
    cols_str = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    conflict_keys_str = ", ".join(unique_keys)

    if non_key_cols:
        update_set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in non_key_cols])
        upsert_query = f"""
            INSERT INTO {table_name} ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_keys_str})
            DO UPDATE SET {update_set_clause}
            WHERE {table_name}.is_manually_edited = FALSE;
        """
    else:
        upsert_query = f"""
            INSERT INTO {table_name} ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_keys_str})
            DO NOTHING;
        """

    records_synced = 0
    for _, row in df.iterrows():
        val_tuple = tuple(None if pd.isna(val) else val for val in row[cols])
        cur.execute(upsert_query, val_tuple)
        records_synced += 1

    cur.close()
    return records_synced

def sync_single_dataset(pg_conn, sf_conn, sf_table_name, pg_table_name, unique_key_env_var):
    if not sf_table_name:
        return False, 0, f"Snowflake table name for '{pg_table_name}' is not configured in .env."

    unique_keys_raw = os.getenv(unique_key_env_var, "").strip()
    if not unique_keys_raw:
        return False, 0, f"Unique key environment variable '{unique_key_env_var}' is not configured."

    unique_keys = [normalize_column_name(k) for k in unique_keys_raw.split(",") if k.strip()]

    try:
        sf_cur = sf_conn.cursor()
        sf_cur.execute(f"SELECT * FROM {sf_table_name};")
        sf_data = sf_cur.fetchall()
        sf_cols = [desc[0] for desc in sf_cur.description]
        sf_cur.close()

        if not sf_data:
            return True, 0, f"No records found in Snowflake source table '{sf_table_name}'."

        df = pd.DataFrame(sf_data, columns=sf_cols)

        has_collision, collision_err, norm_map = check_column_collisions(sf_cols)
        if has_collision:
            return False, 0, collision_err

        df.columns = [norm_map[c] for c in df.columns]

        keys_valid, missing_keys = verify_unique_keys(list(df.columns), unique_keys)
        if not keys_valid:
            return False, 0, f"SYNC ABORTED — Configured unique key(s) {missing_keys} missing from Snowflake table '{sf_table_name}'."

        pg_conn.rollback()

        safe_align_postgres_schema(pg_conn, pg_table_name, df, unique_keys)
        count = upsert_dataframe_to_postgres(pg_conn, pg_table_name, df, unique_keys)
        pg_conn.commit()

        return True, count, ""

    except Exception as e:
        try:
            pg_conn.rollback()
        except Exception:
            pass
        return False, 0, f"Dataset sync failed for '{pg_table_name}': {str(e)}"

def sync_snowflake_to_postgres():
    load_dotenv(override=True)
    sync_started_at = datetime.datetime.now()
    
    sf_account = os.getenv("SNOWFLAKE_ACCOUNT")
    sf_user = os.getenv("SNOWFLAKE_USER")
    sf_password = os.getenv("SNOWFLAKE_PASSWORD")
    sf_warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    sf_database = os.getenv("SNOWFLAKE_DATABASE")
    sf_schema = os.getenv("SNOWFLAKE_SCHEMA")
    sf_role = os.getenv("SNOWFLAKE_ROLE")

    if not sf_account or not sf_user or not sf_password:
        err_msg = "Snowflake connection parameters are missing. Please populate SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, and SNOWFLAKE_PASSWORD in .env."
        log_sync_result(sync_started_at, datetime.datetime.now(), "FAILED", 0, 0, 0, err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "message": err_msg,
            "timestamp": sync_started_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    sf_conn = None
    pg_conn = None
    try:
        import snowflake.connector

        sf_conn = snowflake.connector.connect(
            account=sf_account,
            user=sf_user,
            password=sf_password,
            warehouse=sf_warehouse,
            database=sf_database,
            schema=sf_schema,
            role=sf_role
        )

        pg_conn = get_postgres_connection()

        datasets = [
            ("SNOWFLAKE_PLANNING_TABLE", "planning_data", "POSTGRES_PLANNING_KEY"),
            ("SNOWFLAKE_CONSUMPTION_TABLE", "consumption_data", "POSTGRES_CONSUMPTION_KEY"),
            ("SNOWFLAKE_SHIPMENT_TABLE", "shipment_data", "POSTGRES_SHIPMENT_KEY")
        ]

        synced_counts = {"planning_data": 0, "consumption_data": 0, "shipment_data": 0}
        dataset_errors = []
        dataset_successes = []

        for sf_env_var, pg_table, key_env_var in datasets:
            sf_table = os.getenv(sf_env_var)
            if not sf_table:
                dataset_errors.append(f"Table name variable '{sf_env_var}' not configured.")
                continue

            success, count, err = sync_single_dataset(pg_conn, sf_conn, sf_table, pg_table, key_env_var)
            if success:
                synced_counts[pg_table] = count
                dataset_successes.append(f"{pg_table}: {count} records")
            else:
                dataset_errors.append(err)

        sync_completed_at = datetime.datetime.now()

        if len(dataset_successes) == len(datasets):
            status = "SUCCESS"
            summary_msg = f"Data sync completed successfully. ({', '.join(dataset_successes)})"
        elif len(dataset_successes) > 0:
            status = "PARTIAL_SUCCESS"
            summary_msg = f"Partial sync completed. Success: {', '.join(dataset_successes)}. Errors: {'; '.join(dataset_errors)}"
        else:
            status = "FAILED"
            summary_msg = f"Sync failed. Errors: {'; '.join(dataset_errors)}"

        log_sync_result(
            sync_started_at,
            sync_completed_at,
            status,
            synced_counts["planning_data"],
            synced_counts["consumption_data"],
            synced_counts["shipment_data"],
            "; ".join(dataset_errors) if dataset_errors else None
        )

        return {
            "success": status in ["SUCCESS", "PARTIAL_SUCCESS"],
            "status": status,
            "message": summary_msg,
            "timestamp": sync_completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "counts": synced_counts
        }

    except Exception as e:
        sync_completed_at = datetime.datetime.now()
        err_msg = f"Snowflake sync error: {str(e)}"
        log_sync_result(sync_started_at, sync_completed_at, "FAILED", 0, 0, 0, err_msg)
        return {
            "success": False,
            "status": "FAILED",
            "message": err_msg,
            "timestamp": sync_completed_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    finally:
        if sf_conn:
            try:
                sf_conn.close()
            except Exception:
                pass
        if pg_conn:
            try:
                pg_conn.close()
            except Exception:
                pass

def log_sync_result(started_at, completed_at, status, plan_cnt, cons_cnt, ship_cnt, err_msg):
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        query = """
            INSERT INTO sync_logs (
                sync_started_at, sync_completed_at, status, 
                planning_records_synced, consumption_records_synced, shipment_records_synced, 
                error_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cur.execute(query, (started_at, completed_at, status, plan_cnt, cons_cnt, ship_cnt, err_msg))
        conn.commit()
        cur.close()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()
