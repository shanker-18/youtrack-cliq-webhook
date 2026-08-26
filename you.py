import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from data import (
    NAV_ITEMS, HOW_TO_USE_STEPS, CELL_AUDIT_FEATURES,
    EDITABLE_CELLS_LEGEND, WHERE_TO_EDIT,
    CONSUMPTION_DRIVERS_FULL, INVENTORY_DRIVERS_FULL
)

TEAL = "#00A38D"
TEAL_DARK = "#008065"
TEAL_BG = "#E6F5F2"
TEAL_BORDER = "#BCE5DC"
TEAL_HEADER_BG = "#DDF0EC"
BG = "#F4FAF8"
SIDEBAR_BG = "#FFFFFF"
BORDER = "#E2E8F0"
BORDER_LIGHT = "#F1F5F9"
TEXT_DARK = "#0F172A"
TEXT_SECONDARY = "#334155"
TEXT_MUTED = "#64748B"

def make_driver_table(title, desc, drivers):
    rows = []
    for name, spec in drivers:
        rows.append(
            html.Tr(
                style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
                children=[
                    html.Td(name, style={"padding": "9px 14px", "fontSize": "0.82rem", "fontWeight": "700", "color": TEXT_DARK, "width": "230px", "verticalAlign": "top"}),
                    html.Td(spec, style={"padding": "9px 14px", "fontSize": "0.8rem", "color": TEXT_SECONDARY, "lineHeight": "1.5", "verticalAlign": "top"})
                ]
            )
        )
    return html.Div(
        children=[
            html.H3(title, style={"fontSize": "1.05rem", "fontWeight": "800", "color": TEAL_DARK, "margin": "0 0 4px 0"}),
            html.Div(desc, style={"fontSize": "0.78rem", "color": TEXT_MUTED, "marginBottom": "12px"}),
            html.Table(
                style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "4px", "overflow": "hidden"},
                children=[
                    html.Thead(
                        html.Tr(
                            style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"},
                            children=[
                                html.Th("Building block", style={"padding": "8px 14px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_DARK, "textAlign": "left"}),
                                html.Th("Description", style={"padding": "8px 14px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_DARK, "textAlign": "left"})
                            ]
                        )
                    ),
                    html.Tbody(rows)
                ]
            )
        ]
    )

def build_sidebar():
    brand = html.Div(
        style={"height": "64px", "padding": "0 18px", "display": "flex", "alignItems": "center", "gap": "10px", "borderBottom": f"1px solid {BORDER}"},
        children=[
            html.Div("K", style={"width": "32px", "height": "32px", "background": TEAL, "borderRadius": "6px", "display": "flex", "alignItems": "center", "justifyContent": "center", "color": "#ffffff", "fontWeight": "900", "fontSize": "1.1rem"}),
            html.Div([
                html.Div("KENVUE", style={"fontSize": "1rem", "fontWeight": "900", "color": TEAL, "letterSpacing": "0.02em"}),
                html.Div("IBP Planning", style={"fontSize": "0.72rem", "fontWeight": "700", "color": TEXT_DARK})
            ])
        ]
    )

    nav_item = html.Div(
        style={
            "display": "flex", "alignItems": "center", "gap": "8px", "padding": "8px 14px",
            "color": TEAL_DARK, "backgroundColor": TEAL_BG, "borderRadius": "6px",
            "fontSize": "0.84rem", "fontWeight": "700", "margin": "12px 10px", "cursor": "default"
        },
        children=[
            html.I(className="bi bi-house-door-fill", style={"fontSize": "0.95rem", "color": TEAL_DARK}),
            html.Span("Home")
        ]
    )

    footer = html.Div(
        style={"padding": "12px 18px", "borderTop": f"1px solid {BORDER}", "fontSize": "0.72rem", "color": TEXT_MUTED, "fontWeight": "600", "display": "flex", "alignItems": "center", "justifyContent": "space-between"},
        children=[
            html.Span("IBP"),
            html.Span("v1.1", style={"backgroundColor": TEAL_BG, "color": TEAL_DARK, "padding": "1px 6px", "borderRadius": "3px", "fontSize": "0.68rem", "fontWeight": "700"})
        ]
    )

    return html.Div(
        style={"width": "250px", "backgroundColor": SIDEBAR_BG, "borderRight": f"1px solid {BORDER}", "display": "flex", "flexDirection": "column", "position": "fixed", "top": "0", "bottom": "0", "left": "0", "zIndex": "100", "boxSizing": "border-box"},
        children=[brand, nav_item, html.Div(style={"flex": "1"}), footer]
    )

def build_header():
    title_box = html.Div([
        html.H1("Kenvue", style={"fontSize": "1.05rem", "fontWeight": "900", "color": TEAL, "margin": "0", "display": "inline-block", "marginRight": "6px"}),
        html.Span("|", style={"color": BORDER, "marginRight": "8px", "fontWeight": "300"}),
        html.Span("Integrated Business Planning", style={"fontSize": "0.8rem", "color": TEXT_MUTED, "fontWeight": "500"})
    ], style={"display": "flex", "alignItems": "center"})

    login_btn = html.Button(
        [html.Span("Login")],
        id="btn-login-header",
        style={
            "backgroundColor": TEAL, "color": "#ffffff", "border": "none",
            "padding": "6px 20px", "borderRadius": "4px", "fontWeight": "700",
            "fontSize": "0.82rem", "cursor": "pointer"
        }
    )

    return html.Header(
        style={"height": "64px", "backgroundColor": "#ffffff", "borderBottom": f"1px solid {BORDER}", "padding": "0 24px", "display": "flex", "alignItems": "center", "justifyContent": "space-between", "position": "sticky", "top": "0", "zIndex": "90", "boxSizing": "border-box"},
        children=[title_box, login_btn]
    )

def build_home_content():
    hero = html.Div(
        style={
            "backgroundColor": TEAL_BG,
            "border": f"1px solid {TEAL_BORDER}",
            "borderRadius": "6px",
            "padding": "20px 24px",
            "marginBottom": "24px",
            "width": "100%",
            "boxSizing": "border-box"
        },
        children=[
            html.H2("IBP", style={"fontSize": "1.35rem", "fontWeight": "900", "color": TEAL_DARK, "margin": "0 0 4px 0"}),
            html.Div("Integrated Business Planning for Retail, Consumption, Inventory and Shipment Forecasting", style={"fontSize": "0.92rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "4px"}),
            html.P("Model Business Outcome by Adjusting Key Driver Assumption at the Brand and Sub-Brand Levels.", style={"fontSize": "0.84rem", "color": TEXT_SECONDARY, "margin": "0", "lineHeight": "1.5"})
        ]
    )

    how_to_use_section = html.Div([
        html.H3("How to use", style={"fontSize": "1.05rem", "fontWeight": "800", "color": TEAL_DARK, "marginBottom": "10px"}),
        html.Ol(
            style={"margin": "0", "paddingLeft": "20px", "fontSize": "0.82rem", "color": TEXT_DARK, "lineHeight": "1.65"},
            children=[
                html.Li([html.Strong(f"{idx + 1}. {title} "), html.Span(desc)]) for idx, (title, desc) in enumerate(HOW_TO_USE_STEPS)
            ]
        )
    ])

    divider1 = html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "20px 0"})

    cell_audit_items = [
        html.Li([html.Strong(f"{feature}: "), html.Span(desc)]) for feature, desc in CELL_AUDIT_FEATURES
    ]
    cell_audit_section = html.Div([
        html.H3("Cell Audit modal", style={"fontSize": "1.05rem", "fontWeight": "800", "color": TEAL_DARK, "marginBottom": "8px"}),
        html.P("Single-click any numeric cell on a CDM Input tab to open the Cell Audit modal. Use it to document assumptions and, on editable driver cells, update monthly forecast values.", style={"fontSize": "0.82rem", "color": TEXT_DARK, "marginBottom": "10px", "lineHeight": "1.5"}),
        html.Ul(
            style={"margin": "0", "paddingLeft": "20px", "fontSize": "0.82rem", "color": TEXT_DARK, "lineHeight": "1.65"},
            children=cell_audit_items
        )
    ])

    divider2 = html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "20px 0"})

    legend_rows = [
        html.Tr(
            style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
            children=[
                html.Td(
                    title,
                    style={
                        "padding": "9px 14px", "fontSize": "0.82rem", "fontWeight": "700",
                        "color": TEXT_DARK, "backgroundColor": bg, "width": "230px", "verticalAlign": "top"
                    }
                ),
                html.Td(
                    desc,
                    style={
                        "padding": "9px 14px", "fontSize": "0.8rem", "color": TEXT_SECONDARY,
                        "lineHeight": "1.5", "verticalAlign": "top"
                    }
                )
            ]
        ) for title, desc, bg in EDITABLE_CELLS_LEGEND
    ]

    legend_table = html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "4px", "overflow": "hidden"},
        children=[html.Tbody(legend_rows)]
    )

    legend_section = html.Div([
        html.H3("Editable cells & row legend", style={"fontSize": "1.05rem", "fontWeight": "800", "color": TEAL_DARK, "marginBottom": "10px"}),
        legend_table
    ])

    divider3 = html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "20px 0"})

    where_items = [
        html.Div(
            style={"padding": "8px 12px", "borderBottom": f"1px solid {BORDER_LIGHT}", "display": "flex", "alignItems": "baseline", "gap": "12px"},
            children=[
                html.Span(tab, style={"fontSize": "0.82rem", "fontWeight": "700", "color": TEAL_DARK, "width": "200px"}),
                html.Span(scope, style={"fontSize": "0.8rem", "color": TEXT_SECONDARY})
            ]
        ) for tab, scope in WHERE_TO_EDIT
    ]
    where_to_edit_section = html.Div([
        html.H3("Where you can edit values", style={"fontSize": "1.05rem", "fontWeight": "800", "color": TEAL_DARK, "marginBottom": "8px"}),
        html.Div(where_items)
    ])

    divider4 = html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "20px 0"})

    consumption_section = make_driver_table(
        "Consumption drivers",
        "Building blocks that explain changes in retail and factory POS forecasts. Edit these on the Consumption LE tab.",
        CONSUMPTION_DRIVERS_FULL
    )

    divider5 = html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "20px 0"})

    inventory_section = make_driver_table(
        "Inventory drivers",
        "Building blocks that explain start inventory, flows, and ending inventory. Edit these on the Inventory LE tab.",
        INVENTORY_DRIVERS_FULL
    )

    document_container = html.Div(
        style={
            "backgroundColor": "#FFFFFF",
            "border": f"1px solid {BORDER}",
            "borderRadius": "8px",
            "padding": "24px 28px",
            "boxSizing": "border-box",
            "width": "100%"
        },
        children=[
            hero,
            how_to_use_section,
            divider1,
            cell_audit_section,
            divider2,
            legend_section,
            divider3,
            where_to_edit_section,
            divider4,
            consumption_section,
            divider5,
            inventory_section
        ]
    )

    return html.Div(
        style={"padding": "20px 24px", "boxSizing": "border-box", "width": "100%"},
        children=[document_container]
    )

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Kenvue Integrated Business Planning"

app.layout = html.Div(
    style={"display": "flex", "minHeight": "100vh", "width": "100%", "backgroundColor": BG, "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "color": TEXT_DARK, "lineHeight": "1.4", "overflowX": "hidden", "boxSizing": "border-box"},
    children=[
        build_sidebar(),
        html.Div(
            style={"marginLeft": "250px", "flex": "1", "display": "flex", "flexDirection": "column", "backgroundColor": BG, "minHeight": "100vh", "width": "calc(100% - 250px)", "boxSizing": "border-box"},
            children=[build_header(), html.Div(id="content", children=build_home_content(), style={"flex": "1", "boxSizing": "border-box"})]
        )
    ]
)

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
