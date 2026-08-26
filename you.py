import dash
from dash import html, dcc, Input, Output, callback_context, ALL
import dash_bootstrap_components as dbc
from data import (
    CYCLES, MARKETS, BUS, NAV_ITEMS, DRIVERS, SUPPLY_CONCEPTS,
    PLAN_TYPES, CURRENT_CYCLES, BP_YEARS, DEPARTMENTS, CYCLE_STATUSES,
    ANNOUNCEMENTS, SUMMARY_CARDS_DATA, RECENT_CYCLES, RECENT_ACTIVITY, USER_PERMISSIONS
)

TEAL = "#008F7A"
TEAL_ACTIVE = "#006857"
TEAL_BG = "#E8F4F1"
TEAL_HEADER_BG = "#DDF0EC"
TEAL_BORDER = "#C2E2DB"
BG = "#F5F4EF"
SIDEBAR_BG = "#FAF9F4"
BORDER = "#E2E0D8"
BORDER_LIGHT = "#EDECE6"
TEXT_DARK = "#1A202C"
TEXT_MUTED = "#5A6578"

CARD_STYLE = {
    "backgroundColor": "#FFFFFF",
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
    "padding": "8px 18px",
    "borderRadius": "4px",
    "fontWeight": "700",
    "fontSize": "0.82rem",
    "cursor": "pointer",
    "display": "inline-flex",
    "alignItems": "center",
    "gap": "8px"
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

def make_table(headers, rows):
    th_cells = [html.Th(h, style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "800", "color": TEAL_ACTIVE, "textAlign": "right" if idx == len(headers) - 1 else "left"}) for idx, h in enumerate(headers)]
    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse", "backgroundColor": "#ffffff"},
        children=[
            html.Thead(html.Tr(style={"backgroundColor": TEAL_HEADER_BG, "borderBottom": f"1px solid {TEAL_BORDER}"}, children=th_cells)),
            html.Tbody(rows)
        ]
    )

def build_nav_links(active_tab="Home"):
    nav_links = []
    sections = [
        ("| WORKSPACE TABS", ["Home", "Consumption LE", "Inventory LE", "Shipment LE", "POS & Inventory Data"]),
        ("| PLANNING & REVIEW", ["Building Blocks", "Demand Review", "Dashboard"])
    ]
    for section_title, items in sections:
        nav_links.append(html.Div(section_title, style={"fontSize": "0.68rem", "fontWeight": "800", "color": TEXT_MUTED, "padding": "10px 12px 4px 12px", "letterSpacing": "0.04em"}))
        for label, icon in NAV_ITEMS:
            if label in items:
                is_active = (label == active_tab)
                nav_links.append(
                    html.Div(
                        style={
                            "display": "flex", "alignItems": "center", "gap": "8px", "padding": "7px 12px",
                            "color": "#ffffff" if is_active else TEXT_DARK, "backgroundColor": TEAL_ACTIVE if is_active else "transparent",
                            "borderRadius": "6px", "fontSize": "0.8rem", "fontWeight": "700" if is_active else "500", "cursor": "pointer", "margin": "2px 8px"
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
                html.Div("IBP Planning", style={"fontSize": "0.72rem", "fontWeight": "700", "color": TEXT_DARK})
            ])
        ]
    )
    nav_body = html.Div(id="sidebar-nav-container", children=build_nav_links(active_tab), style={"padding": "8px 0", "flex": "1", "display": "flex", "flexDirection": "column", "gap": "1px", "overflowY": "auto"})
    footer = html.Div(
        style={"padding": "10px 16px", "borderTop": f"1px solid {BORDER}", "fontSize": "0.7rem", "color": TEXT_MUTED, "fontWeight": "600", "display": "flex", "alignItems": "center", "justifyContent": "space-between"},
        children=[html.Span("IBP Workspace"), html.Span("v1.1", style={"backgroundColor": TEAL_BG, "color": TEAL, "padding": "1px 5px", "borderRadius": "3px", "fontSize": "0.65rem", "fontWeight": "700"})]
    )
    return html.Div(
        style={"width": "230px", "backgroundColor": SIDEBAR_BG, "borderRight": f"1px solid {BORDER}", "display": "flex", "flexDirection": "column", "position": "fixed", "top": "0", "bottom": "0", "left": "0", "zIndex": "100", "boxSizing": "border-box"},
        id="app-sidebar", children=[brand, nav_body, footer]
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
            make_dropdown("Market", MARKETS, MARKETS[1], "140px"),
            make_dropdown("BU", BUS, BUS[1], "160px"),
            html.Button([html.I(className="bi bi-arrow-clockwise me-1"), html.Span("Refresh")], style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "padding": "4px 8px", "borderRadius": "4px", "fontSize": "0.74rem", "fontWeight": "600", "color": TEXT_DARK, "cursor": "pointer"}),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "5px", "padding": "2px 6px 2px 2px", "backgroundColor": TEAL_BG, "borderRadius": "12px", "border": f"1px solid {TEAL_BORDER}"}, children=[
                html.Div("KV", style={"width": "20px", "height": "20px", "borderRadius": "50%", "background": TEAL, "color": "#ffffff", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontWeight": "700", "fontSize": "0.65rem"}),
                html.Span(USER_PERMISSIONS["User"], style={"fontSize": "0.72rem", "fontWeight": "700", "color": TEAL_ACTIVE})
            ])
        ]
    )

    return html.Header(
        style={"height": "64px", "backgroundColor": "#ffffff", "borderBottom": f"1px solid {BORDER}", "padding": "0 18px", "display": "flex", "alignItems": "center", "justifyContent": "space-between", "position": "sticky", "top": "0", "zIndex": "90", "gap": "10px", "boxSizing": "border-box"},
        children=[title_box, controls]
    )

def build_home_content():
    welcome_banner = html.Div(
        style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "boxSizing": "border-box"},
        children=[
            html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": "12px"}, children=[
                html.Div([
                    html.H2(f"Welcome back, {USER_PERMISSIONS['User']}", style={"fontSize": "1.25rem", "fontWeight": "900", "color": TEXT_DARK, "margin": "0 0 2px 0"}),
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px", "fontSize": "0.78rem", "color": TEXT_MUTED, "flexWrap": "wrap"}, children=[
                        html.Span("IBP Planning", style={"fontWeight": "800", "color": TEAL}), html.Span("•"),
                        html.Span(f"Department: {USER_PERMISSIONS['Department']}"), html.Span("•"), html.Span(f"Role: {USER_PERMISSIONS['Role']}")
                    ])
                ]),
                html.Div(style={"display": "flex", "gap": "6px", "alignItems": "center"}, children=[
                    html.Span("EDIT ACCESS", style={"backgroundColor": TEAL_BG, "color": TEAL_ACTIVE, "border": f"1px solid {TEAL_BORDER}", "padding": "3px 8px", "borderRadius": "4px", "fontSize": "0.68rem", "fontWeight": "800"}),
                    html.Span("ACTIVE CYCLE", style={"backgroundColor": "#F3F4F6", "color": TEXT_DARK, "border": f"1px solid {BORDER}", "padding": "3px 8px", "borderRadius": "4px", "fontSize": "0.68rem", "fontWeight": "700"})
                ])
            ])
        ]
    )

    context_selector_card = html.Div(
        style=CARD_STYLE,
        children=[
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "12px"}, children=[
                html.I(className="bi bi-sliders", style={"color": TEAL, "fontSize": "1rem"}),
                html.H3("Planning Context", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "margin": "0"}),
                html.Span("Select plan type, cycle year, and department scope", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginLeft": "4px"})
            ]),
            html.Div(style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))", "gap": "12px"}, children=[
                html.Div([
                    html.Label("PLAN TYPE", style={"fontSize": "0.68rem", "fontWeight": "800", "color": TEXT_MUTED, "marginBottom": "4px", "display": "block", "letterSpacing": "0.04em"}),
                    dcc.Dropdown(id="plan-type-dropdown", options=[{"label": pt, "value": pt} for pt in PLAN_TYPES], value="Current Cycle", clearable=False, style={"fontSize": "0.8rem"})
                ]),
                html.Div([
                    html.Label("CYCLE / PLANNING YEAR", id="cycle-year-label", style={"fontSize": "0.68rem", "fontWeight": "800", "color": TEXT_MUTED, "marginBottom": "4px", "display": "block", "letterSpacing": "0.04em"}),
                    dcc.Dropdown(id="cycle-year-dropdown", options=[{"label": c, "value": c} for c in CURRENT_CYCLES], value="September 2026", clearable=False, style={"fontSize": "0.8rem"})
                ]),
                html.Div([
                    html.Label("DEPARTMENT", style={"fontSize": "0.68rem", "fontWeight": "800", "color": TEXT_MUTED, "marginBottom": "4px", "display": "block", "letterSpacing": "0.04em"}),
                    dcc.Dropdown(id="department-dropdown", options=[{"label": d, "value": d} for d in DEPARTMENTS], value="Marketing", clearable=False, style={"fontSize": "0.8rem"})
                ])
            ]),
            html.Div(
                id="cycle-status-banner",
                style={"marginTop": "14px", "padding": "10px 14px", "backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}", "borderRadius": "4px", "display": "flex", "alignItems": "center", "justifyContent": "space-between", "flexWrap": "wrap", "gap": "8px"},
                children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px"}, children=[
                        html.Span("September 2026", style={"fontSize": "0.82rem", "fontWeight": "800", "color": TEXT_DARK}),
                        html.Span("OPEN", style={"backgroundColor": TEAL, "color": "#ffffff", "padding": "2px 8px", "borderRadius": "3px", "fontSize": "0.68rem", "fontWeight": "800"})
                    ]),
                    html.Span("Planning is currently available. Open until Sep 30, 2026.", style={"fontSize": "0.76rem", "color": TEXT_DARK, "fontWeight": "500"})
                ]
            )
        ]
    )

    cta_card = html.Div(
        style={"backgroundColor": "#ffffff", "border": f"1px solid {TEAL_BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": "12px", "boxSizing": "border-box"},
        children=[
            html.Div([
                html.Div(style={"fontSize": "0.7rem", "fontWeight": "800", "color": TEAL, "letterSpacing": "0.04em", "marginBottom": "2px"}, children="PRIMARY ACTION"),
                html.H3("Active Planning Execution", style={"fontSize": "1.05rem", "fontWeight": "800", "color": TEXT_DARK, "margin": "0 0 2px 0"}),
                html.Div(id="cta-context-subtext", style={"fontSize": "0.76rem", "color": TEXT_MUTED}, children="Current Cycle • September 2026 • Marketing Department")
            ]),
            html.Button([html.Span("Continue Planning", id="cta-button-text"), html.I(className="bi bi-arrow-right")], id={"type": "btn-action", "index": "MAIN_PLANNING_CTA"}, style=BTN_PRIMARY)
        ]
    )

    cards_grid = html.Div(
        style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(210px, 1fr))", "gap": "10px", "marginBottom": "16px"},
        children=[
            html.Div(
                style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "4px", "padding": "12px 14px", "boxSizing": "border-box", "display": "flex", "flexDirection": "column", "justifyContent": "space-between", "minHeight": "100px"},
                children=[
                    html.Div([
                        html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "4px"}, children=[
                            html.Span(title, style={"fontSize": "0.68rem", "fontWeight": "800", "color": TEXT_MUTED, "letterSpacing": "0.04em"}),
                            html.I(className=f"bi {icon}", style={"color": TEAL, "fontSize": "0.9rem"})
                        ]),
                        html.Div(val, style={"fontSize": "1.2rem", "fontWeight": "900", "color": TEXT_DARK}),
                        html.Div(sub, style={"fontSize": "0.72rem", "color": TEXT_MUTED, "marginTop": "2px"})
                    ]),
                    html.Div(style={"marginTop": "8px", "paddingTop": "4px", "borderTop": f"1px solid {BORDER_LIGHT}"}, children=[
                        html.Button([html.Span(action_text), html.I(className="bi bi-arrow-right me-1")], id={"type": "btn-action", "index": action_id}, style={"backgroundColor": "transparent", "border": "none", "color": TEAL, "fontSize": "0.72rem", "fontWeight": "700", "padding": "0", "cursor": "pointer"})
                    ])
                ]
            ) for title, val, sub, action_text, icon, action_id in SUMMARY_CARDS_DATA
        ]
    )

    announcement_items = [
        html.Div(
            style={"padding": "10px 12px", "borderBottom": f"1px solid {BORDER_LIGHT}", "display": "flex", "alignItems": "flex-start", "gap": "10px"},
            children=[
                html.I(className=f"bi {icon}", style={"color": TEAL, "fontSize": "1.05rem", "marginTop": "2px"}),
                html.Div(style={"flex": "1"}, children=[
                    html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}, children=[
                        html.Span(title, style={"fontSize": "0.8rem", "fontWeight": "700", "color": TEXT_DARK}),
                        html.Span(dt, style={"fontSize": "0.68rem", "color": TEXT_MUTED})
                    ]),
                    html.Div(desc, style={"fontSize": "0.75rem", "color": TEXT_MUTED, "marginTop": "2px"})
                ])
            ]
        ) for title, desc, dt, cat, icon in ANNOUNCEMENTS
    ]

    announcements_card = html.Div(
        style=CARD_STYLE,
        children=[
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "6px"}, children=[
                html.I(className="bi bi-megaphone-fill", style={"color": TEAL, "fontSize": "0.95rem"}),
                html.H3("Important Announcements", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "margin": "0"})
            ]),
            html.Div(announcement_items)
        ]
    )

    cycle_rows = [
        html.Tr(
            style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
            children=[
                html.Td(cyc, style={"padding": "8px 10px", "fontSize": "0.78rem", "fontWeight": "700", "color": TEXT_DARK}),
                html.Td(ptype, style={"padding": "8px 10px", "fontSize": "0.74rem", "color": TEXT_MUTED}),
                html.Td(html.Span(stat, style={"backgroundColor": TEAL_BG if stat in ["OPEN", "Baseline"] else "#F3F4F6", "color": TEAL_ACTIVE if stat in ["OPEN", "Baseline"] else TEXT_MUTED, "padding": "2px 6px", "borderRadius": "3px", "fontSize": "0.65rem", "fontWeight": "700"}), style={"padding": "8px 10px"}),
                html.Td(pd, style={"padding": "8px 10px", "fontSize": "0.74rem", "color": TEXT_MUTED}),
                html.Td(lu, style={"padding": "8px 10px", "fontSize": "0.74rem", "color": TEXT_MUTED}),
                html.Td(html.Button("Open", id={"type": "btn-action", "index": f"RC_{idx}"}, style={"backgroundColor": "transparent", "border": f"1px solid {BORDER}", "color": TEAL, "padding": "2px 8px", "borderRadius": "3px", "fontSize": "0.7rem", "fontWeight": "700", "cursor": "pointer"}), style={"padding": "8px 10px", "textAlign": "right"})
            ]
        ) for idx, (cyc, ptype, stat, pd, lu) in enumerate(RECENT_CYCLES)
    ]

    recent_cycles_card = html.Div(
        style=CARD_STYLE,
        children=[
            html.H3("Recent Planning Cycles", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "2px"}),
            html.Div("Overview of recent active, locked, and baseline planning cycles.", style={"fontSize": "0.74rem", "color": TEXT_MUTED, "marginBottom": "8px"}),
            make_table(["Cycle", "Plan Type", "Status", "Period", "Last Updated", "Action"], cycle_rows)
        ]
    )

    activity_items = [
        html.Div(
            style={"padding": "8px 10px", "borderBottom": f"1px solid {BORDER_LIGHT}", "display": "flex", "alignItems": "center", "gap": "10px"},
            children=[
                html.Div(style={"width": "24px", "height": "24px", "borderRadius": "50%", "backgroundColor": TEAL_BG, "color": TEAL, "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "0.75rem"}, children=[html.I(className=f"bi {icon}")]),
                html.Div(style={"flex": "1"}, children=[
                    html.Div(act, style={"fontSize": "0.78rem", "fontWeight": "700", "color": TEXT_DARK}),
                    html.Div(desc, style={"fontSize": "0.72rem", "color": TEXT_MUTED})
                ]),
                html.Span(ts, style={"fontSize": "0.68rem", "color": TEXT_MUTED})
            ]
        ) for act, desc, ts, icon in RECENT_ACTIVITY
    ]

    recent_activity_card = html.Div(
        style=CARD_STYLE,
        children=[
            html.H3("Recent Activity Stream", style={"fontSize": "0.95rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "6px"}),
            html.Div(activity_items)
        ]
    )

    return html.Div(
        style={"padding": "14px 18px 32px 18px", "display": "flex", "flexDirection": "column", "boxSizing": "border-box", "width": "100%"},
        children=[
            welcome_banner, context_selector_card, cta_card, cards_grid, announcements_card,
            html.Div(style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))", "gap": "10px"}, children=[recent_cycles_card, recent_activity_card])
        ]
    )

def build_module_view(module_name):
    if module_name == "Building Blocks":
        driver_rows = [
            html.Tr(
                style={"borderBottom": f"1px solid {BORDER_LIGHT}"},
                children=[
                    html.Td(name, style={"padding": "8px 12px", "fontSize": "0.8rem", "fontWeight": "700", "color": TEXT_DARK}),
                    html.Td(dtype, style={"padding": "8px 12px", "fontSize": "0.74rem", "fontWeight": "600", "color": TEAL}),
                    html.Td(desc, style={"padding": "8px 12px", "fontSize": "0.76rem", "color": TEXT_MUTED}),
                    html.Td("Impact: —", style={"padding": "8px 12px", "fontSize": "0.76rem", "fontWeight": "600", "color": TEXT_MUTED, "textAlign": "right"}),
                    html.Td("Awaiting data", style={"padding": "8px 12px", "fontSize": "0.72rem", "color": TEXT_MUTED, "textAlign": "right"})
                ]
            ) for name, dtype, desc in DRIVERS
        ]
        table = make_table(["Building Block / Driver", "Category", "Scope & Description", "Volume Impact", "Status"], driver_rows)
        sub_title = "Building Blocks Workspace"
        sub_desc = "Commercial, operational, and supply drivers shaping baseline and incremental volume forecasts."
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
        table = make_table(["Gate Checkpoint", "Description", "Status"], dr_rows)
        sub_title = "Demand Review Workspace"
        sub_desc = "Cross-functional consensus review, gate status verification, and sign-off workspace."
    else:
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
        table = make_table(["Planning Item", "Description", "Status"], inv_rows)
        sub_title = f"{module_name} Workspace"
        sub_desc = f"Detailed planning workspace module for {module_name}."

    return html.Div(
        style={"padding": "14px 18px 32px 18px", "boxSizing": "border-box", "width": "100%"},
        children=[
            html.Div(
                style={"backgroundColor": TEAL_BG, "border": f"1px solid {TEAL_BORDER}", "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "16px", "display": "flex", "justifyContent": "space-between", "alignItems": "center", "flexWrap": "wrap", "gap": "12px"},
                children=[
                    html.Div([
                        html.H2(sub_title, style={"fontSize": "1.25rem", "fontWeight": "900", "color": TEAL, "margin": "0 0 4px 0"}),
                        html.P(sub_desc, style={"fontSize": "0.82rem", "color": TEXT_DARK, "margin": "0"})
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
app.title = "IBP Planning"

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
    [
        Output("cycle-year-dropdown", "options"),
        Output("cycle-year-dropdown", "value"),
        Output("cycle-status-banner", "children"),
        Output("cta-context-subtext", "children"),
        Output("cta-button-text", "children")
    ],
    [
        Input("plan-type-dropdown", "value"),
        Input("cycle-year-dropdown", "value"),
        Input("department-dropdown", "value")
    ]
)
def update_planning_context(plan_type, cycle_year, department):
    ctx = callback_context
    triggered_id = ctx.triggered_id if ctx.triggered else None

    if triggered_id == "plan-type-dropdown":
        options = [{"label": x, "value": x} for x in (BP_YEARS if plan_type == "BP" else CURRENT_CYCLES)]
        selected_year = options[0]["value"]
    else:
        valid_list = BP_YEARS if plan_type == "BP" else CURRENT_CYCLES
        options = [{"label": x, "value": x} for x in valid_list]
        selected_year = cycle_year if cycle_year in valid_list else valid_list[0]

    status_info = CYCLE_STATUSES.get(selected_year, {"status": "OPEN", "desc": "Planning is available.", "color": TEAL})
    st = status_info["status"]

    banner_children = [
        html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px"}, children=[
            html.Span(f"{plan_type} — {selected_year}", style={"fontSize": "0.82rem", "fontWeight": "800", "color": TEXT_DARK}),
            html.Span(st, style={"backgroundColor": status_info["color"], "color": "#ffffff", "padding": "2px 8px", "borderRadius": "3px", "fontSize": "0.68rem", "fontWeight": "800"})
        ]),
        html.Span(status_info["desc"], style={"fontSize": "0.76rem", "color": TEXT_DARK, "fontWeight": "500"})
    ]

    return options, selected_year, banner_children, f"{plan_type} • {selected_year} • {department} Department", ("Continue Planning" if st == "OPEN" else "View Planning Grid (Read-Only)")

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
    if selected in ["MAIN_PLANNING_CTA", "QA_CYCLE", "QA_ACTIONS", "RC_0"]:
        return "Consumption LE"
    elif selected in ["QA_BP", "RC_2"]:
        return "Building Blocks"
    elif selected in ["QA_STATUS", "RC_1", "RC_3"]:
        return "Demand Review"
    elif selected == "RETURN_HOME_BTN":
        return "Home"
    return selected

@app.callback(
    [Output("content", "children"), Output("sidebar-nav-container", "children")],
    [Input("active-tab-store", "data")]
)
def render_page(active_tab):
    content = build_home_content() if (not active_tab or active_tab == "Home") else build_module_view(active_tab)
    return content, build_nav_links(active_tab)

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)




CYCLES = ["Current Planning Cycle (Jun 2026)", "Jul 2026 (Draft Cycle)", "May 2026 (Locked Cycle)"]
MARKETS = ["Select Market", "US (United States)", "Canada", "Europe", "INDIA", "Global Total"]
BUS = ["Select Business Unit", "Consumer Healthcare", "Self-Care", "Skin Health & Beauty"]

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

PLAN_TYPES = ["Current Cycle", "BP"]
CURRENT_CYCLES = ["September 2026", "August 2026", "July 2026"]
BP_YEARS = ["2027", "2026", "2025"]
DEPARTMENTS = ["Marketing", "Customer Strategy", "Finance"]

CYCLE_STATUSES = {
    "September 2026": {"status": "OPEN", "badge": "OPEN", "desc": "Planning is currently available. Open until Sep 30, 2026.", "color": "#008F7A"},
    "August 2026": {"status": "LOCKED", "badge": "LOCKED", "desc": "Planning data is locked & read-only for consensus review.", "color": "#D97706"},
    "July 2026": {"status": "HISTORICAL", "badge": "HISTORICAL", "desc": "Historical cycle data archived in read-only mode.", "color": "#5A6578"},
    "2027": {"status": "OPEN", "badge": "OPEN", "desc": "24-month BP baseline available for commercial inputs.", "color": "#008F7A"},
    "2026": {"status": "HISTORICAL", "badge": "HISTORICAL", "desc": "Approved 2026 Business Plan historical record.", "color": "#5A6578"},
    "2025": {"status": "HISTORICAL", "badge": "HISTORICAL", "desc": "Historical Business Plan baseline archive.", "color": "#5A6578"}
}

ANNOUNCEMENTS = [
    ("September Cycle Now Open", "September 2026 planning cycle is open for commercial & marketing inputs until Sept 30.", "Aug 26, 2026", "OPEN", "bi-check-circle-fill"),
    ("BP 2027 Baseline Available", "BP 2027 24-month baseline forecast assumptions have been published by Finance.", "Aug 24, 2026", "INFO", "bi-info-circle-fill"),
    ("August 2026 Cycle Locked", "August 2026 cycle has been locked and submitted for executive consensus approval.", "Aug 20, 2026", "LOCKED", "bi-lock-fill")
]

SUMMARY_CARDS_DATA = [
    ("MY ACTIONS", "12", "Pending actions requiring review", "View actions", "bi-clipboard-check-fill", "QA_ACTIONS"),
    ("CURRENT CYCLE", "September 2026", "OPEN • Closes Sep 30, 2026", "View cycle", "bi-calendar-event-fill", "QA_CYCLE"),
    ("BP BASELINE", "BP 2027", "24-month strategic baseline", "View BP", "bi-layers-fill", "QA_BP"),
    ("DATA STATUS", "98%", "Data completeness & validation score", "View details", "bi-pie-chart-fill", "QA_STATUS")
]

RECENT_CYCLES = [
    ("September 2026", "Current Cycle", "OPEN", "Sep 2026", "10 mins ago"),
    ("August 2026", "Current Cycle", "LOCKED", "Aug 2026", "5 days ago"),
    ("BP 2027", "BP", "Baseline", "2026–2027", "2 days ago"),
    ("BP 2026", "BP", "Historical", "2025–2026", "1 month ago")
]

RECENT_ACTIVITY = [
    ("Updated Marketing Planning Data", "You updated Marketing volume inputs for September 2026 cycle.", "10 minutes ago", "bi-pencil-fill"),
    ("BP 2027 Baseline Snapshot Created", "Finance created 24-month baseline snapshot for Commercial planning.", "2 hours ago", "bi-camera-fill"),
    ("Demand Review Gate Consensus Approved", "Demand Review gate status signed off by Customer Strategy lead.", "1 day ago", "bi-check-all"),
    ("August 2026 Cycle Locked", "System admin locked August 2026 cycle for executive submission.", "5 days ago", "bi-lock-fill")
]

USER_PERMISSIONS = {
    "User": "Kenvue Planner",
    "Department": "Marketing",
    "Role": "Marketing Lead",
    "Permissions": ["VIEW", "COMMENT", "EDIT"],
    "AccessLevel": "Commercial Edit Access"
}
