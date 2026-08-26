import dash
from dash import html, dcc, Input, Output, callback_context, ALL
import dash_bootstrap_components as dbc
from data import CYCLES, MARKETS, BUS, STAGES, NAV_ITEMS, MODULES, DRIVERS, SUPPLY_CONCEPTS

TEAL = "#008F7A"
TEAL_ACTIVE = "#006857"
TEAL_BG = "#E8F4F1"
TEAL_HEADER_BG = "#DDF0EC"
TEAL_BORDER = "#C2E2DB"
PURPLE = "#7E22CE"
AMBER = "#D97706"
BLUE = "#2563EB"
BG = "#F5F4EF"
SIDEBAR_BG = "#FAF9F4"
BORDER = "#E2E0D8"
BORDER_LIGHT = "#EDECE6"
TEXT_DARK = "#1A202C"
TEXT_MUTED = "#5A6578"
CARD_BG = "#FFFFFF"

CARD_STYLE = {
    "backgroundColor": CARD_BG,
    "borderRadius": "8px",
    "border": f"1px solid {BORDER}",
    "padding": "16px 20px",
    "boxSizing": "border-box",
    "marginBottom": "16px"
}

BTN_PRIMARY = {
    "backgroundColor": TEAL,
    "color": "#ffffff",
    "border": "none",
    "padding": "6px 14px",
    "borderRadius": "4px",
    "fontWeight": "600",
    "fontSize": "0.78rem",
    "cursor": "pointer",
    "display": "inline-flex",
    "alignItems": "center",
    "gap": "6px"
}

BTN_OUTLINE = {
    "backgroundColor": "#ffffff",
    "color": TEXT_DARK,
    "border": f"1px solid {BORDER}",
    "padding": "6px 12px",
    "borderRadius": "4px",
    "fontWeight": "600",
    "fontSize": "0.78rem",
    "cursor": "pointer",
    "display": "inline-flex",
    "alignItems": "center",
    "gap": "6px"
}

def build_nav_links(active_tab="Home"):
    nav_links = []

    sections = [
        ("| WORKSPACE TABS", ["Home", "Consumption LE", "Inventory LE", "Shipment LE", "POS & Inventory Data"]),
        ("| PLANNING & REVIEW", ["Building Blocks", "Demand Review", "Dashboard"])
    ]

    for section_title, items in sections:
        nav_links.append(
            html.Div(section_title, style={"fontSize": "0.68rem", "fontWeight": "800", "color": TEXT_MUTED, "padding": "10px 12px 4px 12px", "letterSpacing": "0.04em"})
        )
        for label, icon in NAV_ITEMS:
            if label in items:
                is_active = (label == active_tab)
                nav_links.append(
                    html.Div(
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "8px",
                            "padding": "7px 12px",
                            "color": "#ffffff" if is_active else TEXT_DARK,
                            "backgroundColor": TEAL_ACTIVE if is_active else "transparent",
                            "borderRadius": "6px",
                            "fontSize": "0.8rem",
                            "fontWeight": "700" if is_active else "500",
                            "cursor": "pointer",
                            "margin": "2px 8px"
                        },
                        id={"type": "nav", "index": label},
                        children=[
                            html.I(className=f"bi {icon}", style={"fontSize": "0.9rem", "minWidth": "16px", "color": "#ffffff" if is_active else TEAL}),
                            html.Span(label)
                        ]
                    )
                )
    return nav_links

def build_sidebar(active_tab="Home"):
    brand = html.Div(
        style={"height": "64px", "padding": "0 16px", "display": "flex", "alignItems": "center", "gap": "10px", "borderBottom": f"1px solid {BORDER}"},
        children=[
            html.Div("K", style={"width": "32px", "height": "32px", "background": TEAL, "borderRadius": "6px", "display": "flex", "alignItems": "center", "justifyContent": "center", "color": "#ffffff", "fontWeight": "900", "fontSize": "1.1rem"}),
            html.Div([
                html.Div("KENVUE", style={"fontSize": "1rem", "fontWeight": "900", "color": TEAL, "letterSpacing": "0.02em"}),
                html.Div("IBP Workspace", style={"fontSize": "0.72rem", "fontWeight": "700", "color": TEXT_DARK})
            ])
        ]
    )

    nav_body = html.Div(
        id="sidebar-nav-container",
        children=build_nav_links(active_tab),
        style={"padding": "8px 0", "flex": "1", "display": "flex", "flexDirection": "column", "gap": "1px", "overflowY": "auto"}
    )

    footer = html.Div(
        style={"padding": "10px 16px", "borderTop": f"1px solid {BORDER}", "fontSize": "0.7rem", "color": TEXT_MUTED, "fontWeight": "600", "display": "flex", "alignItems": "center", "justifyContent": "space-between"},
        children=[
            html.Span("Kenvue Enterprise IBP"),
            html.Span("v2.4", style={"backgroundColor": TEAL_BG, "color": TEAL, "padding": "1px 5px", "borderRadius": "3px", "fontSize": "0.65rem", "fontWeight": "700"})
        ]
    )

    return html.Div(
        style={"width": "230px", "backgroundColor": SIDEBAR_BG, "borderRight": f"1px solid {BORDER}", "display": "flex", "flexDirection": "column", "position": "fixed", "top": "0", "bottom": "0", "left": "0", "zIndex": "100", "boxSizing": "border-box"},
        id="app-sidebar",
        children=[brand, nav_body, footer]
    )

def build_header():
    title_box = html.Div([
        html.H1("Kenvue", style={"fontSize": "1.05rem", "fontWeight": "900", "color": TEAL, "margin": "0", "display": "inline-block", "marginRight": "6px"}),
        html.Span("|", style={"color": BORDER, "marginRight": "8px", "fontWeight": "300"}),
        html.Span("Integrated Business Planning", style={"fontSize": "0.78rem", "color": TEXT_MUTED, "fontWeight": "500"})
    ], style={"display": "flex", "alignItems": "center"})

    def make_dropdown(label, options, default_val, width):
        return html.Div(style={"display": "flex", "alignItems": "center", "gap": "5px"}, children=[
            html.Span(label, style={"fontSize": "0.68rem", "fontWeight": "700", "color": TEXT_MUTED, "textTransform": "uppercase"}),
            html.Div(style={"width": width}, children=[dcc.Dropdown(options=[{"label": o, "value": o} for o in options], value=default_val, clearable=False, style={"fontSize": "0.76rem"})])
        ])

    controls = html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "wrap"},
        children=[
            make_dropdown("Cycle", CYCLES, CYCLES[0], "175px"),
            make_dropdown("Market", MARKETS, MARKETS[0], "130px"),
            make_dropdown("BU", BUS, BUS[0], "155px"),
            html.Button([html.I(className="bi bi-arrow-clockwise me-1"), html.Span("Refresh")], style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "padding": "4px 8px", "borderRadius": "4px", "fontSize": "0.74rem", "fontWeight": "600", "color": TEXT_DARK, "cursor": "pointer"}),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "5px", "padding": "2px 6px 2px 2px", "backgroundColor": TEAL_BG, "borderRadius": "12px", "border": f"1px solid {TEAL_BORDER}"}, children=[
                html.Div("KV", style={"width": "20px", "height": "20px", "borderRadius": "50%", "background": TEAL, "color": "#ffffff", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontWeight": "700", "fontSize": "0.65rem"}),
                html.Span("Kenvue Planner", style={"fontSize": "0.72rem", "fontWeight": "700", "color": TEAL_ACTIVE})
            ])
        ]
    )

    return html.Header(
        style={"height": "64px", "backgroundColor": "#ffffff", "borderBottom": f"1px solid {BORDER}", "padding": "0 18px", "display": "flex", "alignItems": "center", "justifyContent": "space-between", "position": "sticky", "top": "0", "zIndex": "90", "gap": "10px", "boxSizing": "border-box"},
        children=[title_box, controls]
    )

def build_home_content():
    guide_box = html.Div(
        style={"backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "boxSizing": "border-box"},
        children=[
            html.H2("Integrated Business Planning", style={"fontSize": "1.25rem", "fontWeight": "900", "color": TEAL, "margin": "0 0 4px 0"}),
            html.P("Kenvue Integrated Business Planning for retail consumption, inventory, and shipment forecasts. Model business outcomes by adjusting key driver assumptions at the brand and sub-brand level.", style={"fontSize": "0.82rem", "color": TEXT_DARK, "marginBottom": "12px", "lineHeight": "1.4"}),
            html.Div("How to use", style={"fontSize": "0.8rem", "fontWeight": "800", "color": TEAL_ACTIVE, "marginBottom": "6px"}),
            html.Ol(
                style={"margin": "0", "paddingLeft": "18px", "fontSize": "0.78rem", "color": TEXT_DARK, "lineHeight": "1.5"},
                children=[
                    html.Li([html.Strong("Select a market & business unit "), html.Span("from the top filter dropdowns. All tabs respect this selection.")]),
                    html.Li([html.Strong("Open a tab from the sidebar: "), html.Span("Consumption LE, Inventory LE, or Shipment LE for editable driver forecasts.")]),
                    html.Li([html.Strong("Compare Top Down vs Bottom Up "), html.Span("to identify variance gaps and align operational volume targets.")]),
                    html.Li([html.Strong("Inspect Building Blocks "), html.Span("and Inventory Health concepts below to understand volume drivers.")])
                ]
            )
        ]
    )

    rec_card_style = {"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "4px", "padding": "10px 12px", "boxSizing": "border-box"}
    reconciliation_card = html.Div(
        style=CARD_STYLE,
        children=[
            html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px", "flexWrap": "wrap", "gap": "10px"}, children=[
                html.Div([
                    html.Div([html.I(className="bi bi-arrows-collapse me-1", style={"color": TEAL}), html.Span("Top-Down vs Bottom-Up Reconciliation", style={"fontSize": "1rem", "fontWeight": "800", "color": TEXT_DARK})]),
                    html.Div("Comparison and alignment between strategic targets and driver-based forecasts", style={"fontSize": "0.76rem", "color": TEXT_MUTED, "marginTop": "1px"})
                ]),
                html.Button([html.I(className="bi bi-sliders me-1"), html.Span("Resolve Gap")], id={"type": "btn-action", "index": "REC_RESOLVE_BTN"}, style=BTN_OUTLINE)
            ]),
            html.Div(style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(210px, 1fr))", "gap": "8px"}, children=[
                html.Div(style=rec_card_style, children=[
                    html.Div("TOP DOWN", style={"fontSize": "0.7rem", "fontWeight": "800", "color": TEAL, "letterSpacing": "0.04em"}),
                    html.Div("Business / strategic forecast target established by executive leadership.", style={"fontSize": "0.75rem", "color": TEXT_DARK, "margin": "3px 0 6px 0"}),
                    html.Div([html.Span("Target Volume: ", style={"fontSize": "0.7rem", "color": TEXT_MUTED}), html.Span("—", style={"fontSize": "1rem", "fontWeight": "700", "color": TEXT_MUTED})])
                ]),
                html.Div(style=rec_card_style, children=[
                    html.Div("BOTTOM UP", style={"fontSize": "0.7rem", "fontWeight": "800", "color": TEAL, "letterSpacing": "0.04em"}),
                    html.Div("Driver-based operational forecast aggregated from commercial inputs.", style={"fontSize": "0.75rem", "color": TEXT_DARK, "margin": "3px 0 6px 0"}),
                    html.Div([html.Span("Operational Volume: ", style={"fontSize": "0.7rem", "color": TEXT_MUTED}), html.Span("—", style={"fontSize": "1rem", "fontWeight": "700", "color": TEXT_MUTED})])
                ]),
                html.Div(style={**rec_card_style, "backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}"}, children=[
                    html.Div("RECONCILIATION", style={"fontSize": "0.7rem", "fontWeight": "800", "color": TEAL_ACTIVE, "letterSpacing": "0.04em"}),
                    html.Div("Resolve differences and align operational demand with business targets.", style={"fontSize": "0.75rem", "color": TEXT_DARK, "margin": "3px 0 6px 0"}),
                    html.Div([
                        html.Div([html.Span("Variance Gap: ", style={"fontSize": "0.7rem", "fontWeight": "600", "color": TEXT_MUTED}), html.Span("—", style={"fontSize": "0.95rem", "fontWeight": "700", "color": TEXT_MUTED})]),
                        html.Div("Status: Awaiting data", style={"fontSize": "0.68rem", "color": TEXT_MUTED, "marginTop": "2px", "fontWeight": "500"})
                    ])
                ])
            ])
        ]
    )

    def make_mod_card(name, category, icon, desc):
        return html.Div(
            style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "4px", "padding": "10px 12px", "cursor": "pointer", "display": "flex", "flexDirection": "column", "justifyContent": "space-between", "minHeight": "105px", "boxSizing": "border-box"},
            id={"type": "card", "index": name},
            children=[
                html.Div([
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "6px", "marginBottom": "4px"}, children=[
                        html.I(className=f"bi {icon}", style={"fontSize": "0.95rem", "color": TEAL}),
                        html.Span(name, style={"fontSize": "0.84rem", "fontWeight": "700", "color": TEXT_DARK})
                    ]),
                    html.Div(desc, style={"fontSize": "0.74rem", "color": TEXT_MUTED})
                ]),
                html.Div(style={"marginTop": "6px", "paddingTop": "4px", "borderTop": f"1px solid {BORDER_LIGHT}", "display": "flex", "justifyContent": "space-between", "fontSize": "0.7rem", "fontWeight": "700", "color": TEAL}, children=[html.Span("Open Module"), html.I(className="bi bi-arrow-right")])
            ]
        )

    ws_cards = [make_mod_card(*m) for m in MODULES if m[1] == "Planning Workspace"]
    rev_cards = [make_mod_card(*m) for m in MODULES if m[1] == "Planning & Review"]

    modules_section = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "12px", "marginBottom": "16px"}, children=[
        html.Div([html.H3("Planning Workspace", style={"fontSize": "0.9rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "6px"}), html.Div(ws_cards, style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))", "gap": "8px"})]),
        html.Div([html.H3("Planning & Review", style={"fontSize": "0.9rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "6px"}), html.Div(rev_cards, style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(210px, 1fr))", "gap": "8px"})])
    ])

    driver_rows = []
    for name, dtype, desc in DRIVERS:
        driver_rows.append(
            html.Tr(
                style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
                children=[
                    html.Td(name, style={"padding": "7px 10px", "fontSize": "0.78rem", "fontWeight": "700", "color": TEXT_DARK}),
                    html.Td(dtype, style={"padding": "7px 10px", "fontSize": "0.72rem", "fontWeight": "600", "color": TEAL}),
                    html.Td(desc, style={"padding": "7px 10px", "fontSize": "0.74rem", "color": TEXT_MUTED}),
                    html.Td("Impact: —", style={"padding": "7px 10px", "fontSize": "0.74rem", "fontWeight": "600", "color": TEXT_MUTED, "textAlign": "right"})
                ]
            )
        )

    drivers_table = html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff"},
        children=[
            html.Thead(
                html.Tr(
                    style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"},
                    children=[
                        html.Th("Building block", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Category", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Description", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Volume Impact", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right"})
                    ]
                )
            ),
            html.Tbody(driver_rows)
        ]
    )

    drivers_section = html.Div(style=CARD_STYLE, children=[
        html.H3("Building Blocks / Demand Drivers", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "2px"}),
        html.Div("Building blocks that explain changes in retail and factory POS forecasts.", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginBottom": "8px"}),
        drivers_table
    ])

    inv_rows = []
    for title, desc in SUPPLY_CONCEPTS:
        inv_rows.append(
            html.Tr(
                style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
                children=[
                    html.Td(title, style={"padding": "7px 10px", "fontSize": "0.78rem", "fontWeight": "700", "color": TEXT_DARK}),
                    html.Td(desc, style={"fontSize": "0.74rem", "color": TEXT_MUTED, "padding": "7px 10px"}),
                    html.Td("Awaiting data", style={"fontSize": "0.7rem", "color": TEXT_MUTED, "padding": "7px 10px", "textAlign": "right"})
                ]
            )
        )

    inv_table = html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff"},
        children=[
            html.Thead(
                html.Tr(
                    style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"},
                    children=[
                        html.Th("Supply Health Concept", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Description", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Status", style={"padding": "6px 10px", "fontSize": "0.72rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right"})
                    ]
                )
            ),
            html.Tbody(inv_rows)
        ]
    )

    inv_section = html.Div(style=CARD_STYLE, children=[
        html.H3("Inventory & Supply Health Concepts", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "2px"}),
        html.Div("Supply chain feasibility, safety stock dynamics, and inventory position alignment.", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginBottom": "8px"}),
        inv_table
    ])

    checkpoints = ["Data Readiness", "Building Blocks", "Top Down Target", "Bottom Up Forecast", "Reconciliation", "Demand Review", "Consensus"]
    dr_items = [
        html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "5px 8px", "backgroundColor": BG, "borderRadius": "3px", "border": f"1px solid {BORDER}", "boxSizing": "border-box"}, children=[
            html.Span(cp, style={"fontSize": "0.74rem", "fontWeight": "600", "color": TEXT_DARK}),
            html.Span("Awaiting data", style={"fontSize": "0.65rem", "color": TEXT_MUTED, "backgroundColor": "#FFFFFF", "padding": "1px 5px", "borderRadius": "3px", "border": f"1px solid {BORDER}"})
        ]) for cp in checkpoints
    ]

    dr_section = html.Div(style=CARD_STYLE, children=[
        html.H3("Demand Review Gate Status", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "6px"}),
        html.Div(dr_items, style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(170px, 1fr))", "gap": "5px"})
    ])

    attention_section = html.Div(
        style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "4px", "padding": "14px", "textAlign": "center", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "boxSizing": "border-box", "marginBottom": "16px"},
        children=[
            html.Div(style={"width": "28px", "height": "28px", "borderRadius": "50%", "backgroundColor": TEAL_BG, "color": TEAL, "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "1rem", "marginBottom": "4px"}, children=[html.I(className="bi bi-check-circle-fill")]),
            html.Div("No items requiring attention", style={"fontSize": "0.82rem", "fontWeight": "700", "color": TEXT_DARK}),
            html.Div("Zero exception items logged for the selected planning context.", style={"fontSize": "0.72rem", "color": TEXT_MUTED, "marginTop": "1px"})
        ]
    )

    quick_actions = html.Div(
        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "padding": "8px 14px", "borderRadius": "4px", "flexWrap": "wrap", "gap": "6px", "boxSizing": "border-box"},
        children=[
            html.Div([html.I(className="bi bi-lightning-charge-fill me-1", style={"color": TEAL}), html.Span("QUICK ACTIONS", style={"fontSize": "0.72rem", "fontWeight": "800", "color": TEXT_DARK, "letterSpacing": "0.04em"})]),
            html.Div(style={"display": "flex", "gap": "5px", "flexWrap": "wrap"}, children=[
                html.Button(title, id={"type": "btn-action", "index": f"QA_{idx}"}, style={"backgroundColor": BG, "border": f"1px solid {BORDER}", "color": TEXT_DARK, "padding": "4px 8px", "borderRadius": "4px", "fontSize": "0.72rem", "fontWeight": "600", "cursor": "pointer"})
                for idx, title in enumerate(["Review Building Blocks", "Compare Top Down vs Bottom Up", "Open Demand Review"])
            ])
        ]
    )

    return html.Div(style={"padding": "14px 18px 32px 18px", "display": "flex", "flexDirection": "column", "boxSizing": "border-box", "width": "100%"}, children=[
        guide_box, reconciliation_card, modules_section, drivers_section, inv_section,
        html.Div(style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(240px, 1fr))", "gap": "10px"}, children=[dr_section, attention_section]), quick_actions
    ])

def build_module_view(module_name):
    if module_name == "Building Blocks":
        driver_rows = []
        for name, dtype, desc in DRIVERS:
            driver_rows.append(
                html.Tr(
                    style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
                    children=[
                        html.Td(name, style={"padding": "8px 12px", "fontSize": "0.8rem", "fontWeight": "700", "color": TEXT_DARK}),
                        html.Td(dtype, style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "600", "color": TEAL}),
                        html.Td(desc, style={"padding": "8px 12px", "fontSize": "0.76rem", "color": TEXT_MUTED}),
                        html.Td("Impact: —", style={"padding": "8px 12px", "fontSize": "0.76rem", "fontWeight": "600", "color": TEXT_MUTED, "textAlign": "right"}),
                        html.Td("Awaiting data", style={"padding": "8px 12px", "fontSize": "0.72rem", "color": TEXT_MUTED, "textAlign": "right"})
                    ]
                )
            )

        table = html.Table(
            style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff"},
            children=[
                html.Thead(
                    html.Tr(
                        style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"},
                        children=[
                            html.Th("Building Block / Driver", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                            html.Th("Category", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                            html.Th("Scope & Description", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                            html.Th("Volume Impact", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right"}),
                            html.Th("Status", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right"})
                        ]
                    )
                ),
                html.Tbody(driver_rows)
            ]
        )

        return html.Div(
            style={"padding": "14px 18px 32px 18px", "boxSizing": "border-box", "width": "100%"},
            children=[
                html.Div(
                    style={"backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": "12px"},
                    children=[
                        html.Div([
                            html.H2("Building Blocks Workspace", style={"fontSize": "1.25rem", "fontWeight": "900", "color": TEAL, "margin": "0 0 4px 0"}),
                            html.P("Commercial, operational, and supply drivers shaping baseline and incremental volume forecasts.", style={"fontSize": "0.82rem", "color": TEXT_DARK, "margin": "0"})
                        ]),
                        html.Button([html.I(className="bi bi-arrow-left me-1"), html.Span("Return to Home Landing Page")], id={"type": "btn-action", "index": "RETURN_HOME_BTN"}, style=BTN_OUTLINE)
                    ]
                ),
                html.Div(style=CARD_STYLE, children=[
                    html.H3("Building Blocks & Demand Drivers Table", style={"fontSize": "0.98rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "2px"}),
                    html.Div("Detailed view of driver assumptions, volume impact, and category classification.", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginBottom": "12px"}),
                    table
                ])
            ]
        )

    elif module_name == "Demand Review":
        checkpoints = ["Data Readiness", "Building Blocks", "Top Down Target", "Bottom Up Forecast", "Reconciliation", "Demand Review", "Consensus"]
        dr_rows = [
            html.Tr(
                style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
                children=[
                    html.Td(cp, style={"padding": "8px 12px", "fontSize": "0.8rem", "fontWeight": "700", "color": TEXT_DARK}),
                    html.Td("Cross-functional consensus review & validation gate", style={"padding": "8px 12px", "fontSize": "0.76rem", "color": TEXT_MUTED}),
                    html.Td("Awaiting data", style={"padding": "8px 12px", "fontSize": "0.72rem", "color": TEXT_MUTED, "textAlign": "right"})
                ]
            ) for cp in checkpoints
        ]

        table = html.Table(
            style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff"},
            children=[
                html.Thead(
                    html.Tr(
                        style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"},
                        children=[
                            html.Th("Gate Checkpoint", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                            html.Th("Description", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                            html.Th("Status", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right"})
                        ]
                    )
                ),
                html.Tbody(dr_rows)
            ]
        )

        return html.Div(
            style={"padding": "14px 18px 32px 18px", "boxSizing": "border-box", "width": "100%"},
            children=[
                html.Div(
                    style={"backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": "12px"},
                    children=[
                        html.Div([
                            html.H2("Demand Review Workspace", style={"fontSize": "1.25rem", "fontWeight": "900", "color": TEAL, "margin": "0 0 4px 0"}),
                            html.P("Cross-functional consensus review, gate status verification, and sign-off workspace.", style={"fontSize": "0.82rem", "color": TEXT_DARK, "margin": "0"})
                        ]),
                        html.Button([html.I(className="bi bi-arrow-left me-1"), html.Span("Return to Home Landing Page")], id={"type": "btn-action", "index": "RETURN_HOME_BTN"}, style=BTN_OUTLINE)
                    ]
                ),
                html.Div(style=CARD_STYLE, children=[
                    html.H3("Demand Review Gate Status", style={"fontSize": "0.98rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "2px"}),
                    html.Div("Consensus gate checkpoints and readiness status.", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginBottom": "12px"}),
                    table
                ])
            ]
        )

    inv_rows = [
        html.Tr(
            style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
            children=[
                html.Td(title, style={"padding": "8px 12px", "fontSize": "0.8rem", "fontWeight": "700", "color": TEXT_DARK}),
                html.Td(desc, style={"padding": "8px 12px", "fontSize": "0.76rem", "color": TEXT_MUTED}),
                html.Td("Awaiting data", style={"padding": "8px 12px", "fontSize": "0.72rem", "color": TEXT_MUTED, "textAlign": "right"})
            ]
        ) for title, desc in SUPPLY_CONCEPTS
    ]

    table = html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff"},
        children=[
            html.Thead(
                html.Tr(
                    style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"},
                    children=[
                        html.Th("Planning Item", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Description", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "left"}),
                        html.Th("Status", style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right"})
                    ]
                )
            ),
            html.Tbody(inv_rows)
        ]
    )

    return html.Div(
        style={"padding": "14px 18px 32px 18px", "boxSizing": "border-box", "width": "100%"},
        children=[
            html.Div(
                style={"backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": "12px"},
                children=[
                    html.Div([
                        html.H2(f"{module_name} Workspace", style={"fontSize": "1.25rem", "fontWeight": "900", "color": TEAL, "margin": "0 0 4px 0"}),
                        html.P(f"Detailed planning workspace module for {module_name}.", style={"fontSize": "0.82rem", "color": TEXT_DARK, "margin": "0"})
                    ]),
                    html.Button([html.I(className="bi bi-arrow-left me-1"), html.Span("Return to Home Landing Page")], id={"type": "btn-action", "index": "RETURN_HOME_BTN"}, style=BTN_OUTLINE)
                ]
            ),
            html.Div(style=CARD_STYLE, children=[
                html.H3(f"{module_name} Data & Driver Table", style={"fontSize": "0.98rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "2px"}),
                html.Div(f"Planning drivers and reference data for {module_name}.", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginBottom": "12px"}),
                table
            ])
        ]
    )

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Kenvue Integrated Business Planning"

app.layout = html.Div(
    style={"display": "flex", "minHeight": "100vh", "width": "100%", "backgroundColor": BG, "fontFamily": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "color": TEXT_DARK, "lineHeight": "1.4", "overflowX": "hidden", "boxSizing": "border-box"},
    children=[
        dcc.Store(id="active-tab-store", data="Home"),
        build_sidebar("Home"),
        html.Div(
            style={"marginLeft": "230px", "flex": "1", "display": "flex", "flexDirection": "column", "backgroundColor": BG, "minHeight": "100vh", "width": "calc(100% - 230px)", "boxSizing": "border-box"},
            children=[build_header(), html.Div(id="content", children=build_home_content(), style={"flex": "1", "boxSizing": "border-box"})]
        )
    ]
)

@app.callback(
    Output("active-tab-store", "data"),
    [
        Input({"type": "nav", "index": ALL}, "n_clicks"),
        Input({"type": "card", "index": ALL}, "n_clicks"),
        Input({"type": "btn-action", "index": ALL}, "n_clicks")
    ],
    prevent_initial_call=True
)
def update_tab(nav_clicks, card_clicks, btn_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update

    triggered_id = ctx.triggered_id
    if not triggered_id or not isinstance(triggered_id, dict) or "index" not in triggered_id:
        return dash.no_update

    triggered_val = ctx.triggered[0].get("value")
    if not triggered_val:
        return dash.no_update

    selected = triggered_id["index"]
    if selected in ["QA_2"]:
        return "Demand Review"
    elif selected in ["REC_RESOLVE_BTN", "QA_0", "QA_1"]:
        return "Building Blocks"
    elif selected == "RETURN_HOME_BTN":
        return "Home"
    return selected

@app.callback(
    [Output("content", "children"), Output("sidebar-nav-container", "children")],
    [Input("active-tab-store", "data")]
)
def render_page(active_tab):
    if not active_tab or active_tab == "Home":
        content = build_home_content()
    else:
        content = build_module_view(active_tab)
    nav_children = build_nav_links(active_tab)
    return content, nav_children

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)


CYCLES = ["Current Planning Cycle (Jun 2026)", "Jul 2026 (Draft Cycle)", "May 2026 (Locked Cycle)"]
MARKETS = ["Select Market", "US (United States)", "Canada", "Europe", "INDIA", "Global Total"]
BUS = ["Select Business Unit", "Consumer Healthcare", "Self-Care", "Skin Health & Beauty"]

STAGES = [
    ("01", "Baseline", "Statistical baseline demand forecast"),
    ("02", "Bottom-Up", "Sales & commercial driver-based inputs"),
    ("03", "Top-Down", "Strategic executive business plan target"),
    ("04", "Reconciliation", "Resolve differences between Top Down and Bottom Up"),
    ("05", "Demand Review", "Cross-functional consensus review"),
    ("06", "Consensus", "Formal sign-off by functional leads"),
    ("07", "One Volume Plan", "Single source of truth consensus plan"),
]

NAV_ITEMS = [
    ("Home", "bi-house-door-fill"),
    ("Consumption LE", "bi-graph-up"),
    ("Inventory LE", "bi-box-seam"),
    ("Shipment LE", "bi-truck"),
    ("POS & Inventory Data", "bi-database"),
    ("Building Blocks", "bi-building-blocks"),
    ("Demand Review", "bi-people-fill"),
    ("Dashboard", "bi-speedometer2"),
]

MODULES = [
    ("Consumption LE", "Planning Workspace", "bi-graph-up", "Latest Estimate consumption planning & scan data."),
    ("Inventory LE", "Planning Workspace", "bi-box-seam", "Inventory planning, projected positions & safety stock."),
    ("Shipment LE", "Planning Workspace", "bi-truck", "Primary shipment schedules & ex-factory projections."),
    ("POS & Inventory Data", "Planning Workspace", "bi-database", "POS retailer source data & channel inventory."),
    ("Building Blocks", "Planning & Review", "bi-building-blocks", "Business & demand drivers shaping volume."),
    ("Demand Review", "Planning & Review", "bi-people-fill", "Cross-functional demand review & consensus."),
    ("Dashboard", "Planning & Review", "bi-speedometer2", "Planning analytics & consensus reporting."),
]

DRIVERS = [
    ("Base Trends", "Demand Trend", "Organic baseline consumption momentum."),
    ("Seasonality", "Pattern", "Seasonal index shifts & historical velocity."),
    ("NPI", "Commercial", "New Product Introduction incremental volume."),
    ("NPI Cannibalization", "Commercial", "Estimated volume shift from legacy SKUs."),
    ("Merchandising", "Trade Promo", "Circular promo slots & display lifts."),
    ("Pricing", "Finance", "Price adjustments & elasticity impacts."),
    ("Store Openings", "Distribution", "Incremental door distribution points."),
    ("Store Closings", "Distribution", "Footprint reduction & door adjustments."),
    ("Innovation", "Product", "Packaging redesigns & line extensions."),
    ("Customer Target Adjust", "Account", "Retailer account volume adjustments."),
    ("Supply / Fill Rate", "Supply Chain", "Plant capacity & fill rate feasibility."),
    ("Shifting Placement / OSA", "Retail Ops", "On-shelf availability & placement changes."),
]

SUPPLY_CONCEPTS = [
    ("Inventory Build", "Pre-season accumulation for peak demand."),
    ("Store Openings", "Initial pipeline fill for new retail doors."),
    ("Store Closings", "Inventory buy-back & liquidation tracking."),
    ("Supply / Fill Rate", "Production alignment against demand."),
    ("Supply Vulnerability", "Raw material & lead-time risk assessment."),
    ("Inventory Drawdown", "Planned stock reduction during off-peak."),
]
