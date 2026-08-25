
import dash
from dash import html, dcc, Input, Output, callback_context, ALL
import dash_bootstrap_components as dbc
from data import CYCLES, MARKETS, BUS, STAGES, NAV_ITEMS, MODULES, DRIVERS, SUPPLY_CONCEPTS

# ==============================================================================
# SECTION 1: THEME COLORS & INLINE STYLE DICTIONARIES
# ==============================================================================
NAVY = "#0f172a"
NAVY_LIGHT = "#1e293b"
TEAL = "#0d9488"
BG = "#f8fafc"
BORDER = "#e2e8f0"
TEXT_DARK = "#0f172a"
TEXT_MUTED = "#64748b"

CARD_STYLE = {
    "backgroundColor": "#ffffff",
    "borderRadius": "12px",
    "border": f"1px solid {BORDER}",
    "boxShadow": "0 4px 6px -1px rgba(15, 23, 42, 0.04)",
    "padding": "24px 28px",
}

BTN_TEAL = {
    "backgroundColor": TEAL,
    "color": "#ffffff",
    "border": "none",
    "padding": "10px 20px",
    "borderRadius": "8px",
    "fontWeight": "600",
    "fontSize": "0.88rem",
    "cursor": "pointer",
    "display": "inline-flex",
    "alignItems": "center",
    "gap": "8px",
}

BTN_OUTLINE = {
    "backgroundColor": "#ffffff",
    "color": TEXT_DARK,
    "border": f"1px solid {BORDER}",
    "padding": "10px 18px",
    "borderRadius": "8px",
    "fontWeight": "600",
    "fontSize": "0.88rem",
    "cursor": "pointer",
    "display": "inline-flex",
    "alignItems": "center",
    "gap": "8px",
}

def grid(cols, gap="18px"):
    return {"display": "grid", "gridTemplateColumns": f"repeat({cols}, 1fr)", "gap": gap}

# ==============================================================================
# SECTION 2: COMPONENT LAYOUT BUILDERS
# ==============================================================================

def build_sidebar(active_tab="Home"):
    """Renders the fixed dark navy left sidebar (270px width)."""
    brand = html.Div(
        style={"height": "76px", "padding": "0 20px", "display": "flex", "alignItems": "center", "gap": "12px", "borderBottom": "1px solid rgba(255, 255, 255, 0.08)"},
        children=[
            html.Div("KV", style={"width": "38px", "height": "38px", "background": f"linear-gradient(135deg, {TEAL}, #059669)", "borderRadius": "10px", "display": "flex", "alignItems": "center", "justifyContent": "center", "color": "#ffffff", "fontWeight": "800", "fontSize": "1.15rem"}),
            html.Div([
                html.Div("KENVUE", style={"fontSize": "1.15rem", "fontWeight": "800", "color": "#ffffff", "letterSpacing": "0.06em"}),
                html.Div("IBP Workspace", style={"fontSize": "0.68rem", "color": "#94a3b8"})
            ])
        ]
    )

    nav_links = []
    for label, icon in NAV_ITEMS:
        is_active = (label == active_tab)
        nav_links.append(
            html.A(
                style={
                    "display": "flex", "alignItems": "center", "gap": "14px", "padding": "12px 18px",
                    "color": "#ffffff" if is_active else "#94a3b8",
                    "backgroundColor": "rgba(13, 148, 136, 0.25)" if is_active else "transparent",
                    "borderLeft": f"4px solid {TEAL}" if is_active else "4px solid transparent",
                    "borderRadius": "8px", "textDecoration": "none", "fontSize": "0.92rem",
                    "fontWeight": "600" if is_active else "500", "cursor": "pointer", "margin": "2px 0"
                },
                href="#",
                id={"type": "nav", "index": label},
                children=[
                    html.I(className=f"bi {icon}", style={"fontSize": "1.15rem", "minWidth": "24px", "textAlign": "center"}),
                    html.Span(label)
                ]
            )
        )

    nav_body = html.Div(nav_links, style={"padding": "20px 12px", "flex": "1", "display": "flex", "flexDirection": "column", "gap": "4px"})
    footer = html.Div("Kenvue IBP", style={"padding": "16px 20px", "borderTop": "1px solid rgba(255, 255, 255, 0.08)", "fontSize": "0.78rem", "color": TEXT_MUTED, "fontWeight": "600"})

    return html.Div(
        style={"width": "270px", "backgroundColor": NAVY, "color": "#ffffff", "display": "flex", "flexDirection": "column", "position": "fixed", "top": "0", "bottom": "0", "left": "0", "zIndex": "100", "boxShadow": "2px 0 12px rgba(0,0,0,0.15)"},
        id="app-sidebar",
        children=[brand, nav_body, footer]
    )

def build_header():
    """Renders the horizontal flex top header (76px height)."""
    title_box = html.Div([
        html.H1("Kenvue", style={"fontSize": "1.3rem", "fontWeight": "800", "color": TEXT_DARK, "margin": "0"}),
        html.P("Integrated Business Planning", style={"fontSize": "0.8rem", "color": TEXT_MUTED, "margin": "2px 0 0 0"})
    ], style={"minWidth": "300px"})

    def make_dropdown(label, options, default_val, width):
        return html.Div(style={"display": "flex", "alignItems": "center", "gap": "8px"}, children=[
            html.Span(label, style={"fontSize": "0.76rem", "fontWeight": "600", "color": TEXT_MUTED, "textTransform": "uppercase"}),
            html.Div(style={"width": width}, children=[dcc.Dropdown(options=[{"label": o, "value": o} for o in options], value=default_val, clearable=False, style={"fontSize": "0.84rem"})])
        ])

    controls = html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "20px"},
        children=[
            make_dropdown("Cycle", CYCLES, CYCLES[0], "210px"),
            make_dropdown("Market", MARKETS, MARKETS[0], "155px"),
            make_dropdown("Business Unit", BUS, BUS[0], "190px"),
            html.Button([html.I(className="bi bi-arrow-clockwise me-1"), html.Span("Refresh")], style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "padding": "8px 16px", "borderRadius": "8px", "fontSize": "0.84rem", "cursor": "pointer"}),
            html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "padding": "4px 12px 4px 4px", "backgroundColor": "#f1f5f9", "borderRadius": "30px", "border": f"1px solid {BORDER}"}, children=[
                html.Div("KV", style={"width": "32px", "height": "32px", "borderRadius": "50%", "background": f"linear-gradient(135deg, {NAVY_LIGHT}, {TEAL})", "color": "#ffffff", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontWeight": "700", "fontSize": "0.8rem"}),
                html.Span("Kenvue Planner", style={"fontSize": "0.82rem", "fontWeight": "600", "color": TEXT_DARK})
            ])
        ]
    )

    return html.Header(
        style={"height": "76px", "backgroundColor": "#ffffff", "borderBottom": f"1px solid {BORDER}", "padding": "0 40px", "display": "flex", "alignItems": "center", "justifyContent": "space-between", "position": "sticky", "top": "0", "zIndex": "90"},
        children=[title_box, controls]
    )

def build_home_content():
    """Assembles the primary Kenvue IBP Landing Page Cockpit."""
    # 1. Main Title Banner Card
    banner = html.Div(
        style={"background": f"linear-gradient(135deg, {NAVY} 0%, {NAVY_LIGHT} 100%)", "color": "#ffffff", "borderRadius": "14px", "padding": "32px 40px", "boxShadow": "0 10px 15px -3px rgba(15, 23, 42, 0.08)"},
        children=[
            html.Div("KENVUE INTEGRATED BUSINESS PLANNING", style={"fontSize": "0.85rem", "fontWeight": "800", "color": TEAL, "letterSpacing": "0.15em", "marginBottom": "6px"}),
            html.H1("Kenvue Integrated Business Planning", style={"fontSize": "2.2rem", "fontWeight": "800", "color": "#ffffff", "marginBottom": "6px"}),
            html.P("One Volume Plan | Demand Planning & Consensus Workspace", style={"fontSize": "1.05rem", "color": "#94a3b8", "margin": "0"})
        ]
    )

    # 2. One Volume Plan & Neutral 7-Stage Workflow
    nodes = []
    for idx, (step, name, desc) in enumerate(STAGES):
        nodes.append(
            html.Div(
                style={"flex": "1", "backgroundColor": "#f8fafc", "border": f"1px solid {BORDER}", "borderRadius": "10px", "padding": "14px 12px", "textAlign": "center"},
                title=desc,
                children=[
                    html.Div(f"STEP {step}", style={"fontSize": "0.7rem", "fontWeight": "800", "color": TEAL, "marginBottom": "2px"}),
                    html.Div(name, style={"fontSize": "0.88rem", "fontWeight": "700", "color": TEXT_DARK})
                ]
            )
        )
        if idx < len(STAGES) - 1:
            nodes.append(html.Div(html.I(className="bi bi-chevron-right", style={"color": TEXT_MUTED, "fontSize": "1.1rem"})))

    ovp_card = html.Div(
        style={**CARD_STYLE, "border": "1.5px solid #cbd5e1", "position": "relative"},
        children=[
            html.Div(style={"position": "absolute", "top": "0", "left": "0", "right": "0", "height": "4px", "background": f"linear-gradient(90deg, {TEAL}, #2563eb, #d97706)", "borderTopLeftRadius": "12px", "borderTopRightRadius": "12px"}),
            html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "24px"}, children=[
                html.Div([
                    html.H2("ONE VOLUME PLAN", style={"fontSize": "1.55rem", "fontWeight": "800", "color": TEXT_DARK, "margin": "0"}),
                    html.P("Cross-functional consensus forecast and strategic volume target", style={"fontSize": "0.88rem", "color": TEXT_MUTED, "margin": "4px 0 0 0"})
                ]),
                html.Button([html.I(className="bi bi-file-earmark-check-fill me-1"), html.Span("Review One Volume Plan")], style=BTN_TEAL)
            ]),
            html.Div([
                html.Div(style={"display": "flex", "justifyContent": "space-between", "marginBottom": "8px"}, children=[
                    html.Span("Consensus planning workflow", style={"fontSize": "0.82rem", "fontWeight": "700", "color": TEXT_MUTED}),
                    html.Span("Process Stages 01 to 07", style={"fontSize": "0.78rem", "fontWeight": "600", "color": TEXT_MUTED})
                ]),
                html.Div(nodes, style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "8px", "backgroundColor": "#ffffff", "padding": "18px", "borderRadius": "10px", "border": f"1px solid {BORDER}"})
            ])
        ]
    )

    # 3. Top-Down vs Bottom-Up Reconciliation Section
    rec_card_style = {"backgroundColor": "#f8fafc", "border": f"1px solid {BORDER}", "borderRadius": "10px", "padding": "18px 20px"}
    reconciliation_card = html.Div(
        style=CARD_STYLE,
        children=[
            html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "18px"}, children=[
                html.Div([
                    html.Div([html.I(className="bi bi-arrows-collapse me-2", style={"color": TEAL}), html.Span("Top-Down vs Bottom-Up Reconciliation", style={"fontSize": "1.2rem", "fontWeight": "800", "color": TEXT_DARK})]),
                    html.Div("Comparison and alignment between strategic targets and driver-based forecasts", style={"fontSize": "0.84rem", "color": TEXT_MUTED, "marginTop": "2px"})
                ]),
                html.Button([html.I(className="bi bi-sliders me-1"), html.Span("Resolve Gap")], style=BTN_OUTLINE)
            ]),
            html.Div(style=grid(3), children=[
                html.Div(style=rec_card_style, children=[
                    html.Div("TOP DOWN", style={"fontSize": "0.82rem", "fontWeight": "700", "color": TEXT_MUTED}),
                    html.Div("Business / strategic forecast target established by executive leadership.", style={"fontSize": "0.85rem", "color": TEXT_DARK, "margin": "6px 0 12px 0"}),
                    html.Div([html.Span("Target Volume: ", style={"fontSize": "0.78rem", "color": TEXT_MUTED}), html.Span("—", style={"fontSize": "1.3rem", "fontWeight": "700", "color": TEXT_MUTED})])
                ]),
                html.Div(style=rec_card_style, children=[
                    html.Div("BOTTOM UP", style={"fontSize": "0.82rem", "fontWeight": "700", "color": TEXT_MUTED}),
                    html.Div("Driver-based operational forecast aggregated from commercial inputs.", style={"fontSize": "0.85rem", "color": TEXT_DARK, "margin": "6px 0 12px 0"}),
                    html.Div([html.Span("Operational Volume: ", style={"fontSize": "0.78rem", "color": TEXT_MUTED}), html.Span("—", style={"fontSize": "1.3rem", "fontWeight": "700", "color": TEXT_MUTED})])
                ]),
                html.Div(style={**rec_card_style, "backgroundColor": "#ffffff", "border": "1px solid #cbd5e1"}, children=[
                    html.Div("RECONCILIATION", style={"fontSize": "0.82rem", "fontWeight": "700", "color": TEAL}),
                    html.Div("Resolve differences and align operational demand with business targets.", style={"fontSize": "0.85rem", "color": TEXT_DARK, "margin": "6px 0 12px 0"}),
                    html.Div([
                        html.Div([html.Span("Variance Gap: ", style={"fontSize": "0.78rem", "fontWeight": "600", "color": TEXT_MUTED}), html.Span("—", style={"fontSize": "1.1rem", "fontWeight": "700", "color": TEXT_MUTED})]),
                        html.Div("Status: Awaiting data", style={"fontSize": "0.76rem", "color": TEXT_MUTED, "marginTop": "4px"})
                    ])
                ])
            ])
        ]
    )

    # 4. Core IBP Modules Grid
    def make_mod_card(name, category, icon, desc):
        return html.Div(
            style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "14px", "padding": "22px 24px", "cursor": "pointer", "display": "flex", "flexDirection": "column", "justifyContent": "space-between", "minHeight": "170px"},
            id={"type": "card", "index": name},
            children=[
                html.Div([
                    html.Div(style={"width": "42px", "height": "42px", "borderRadius": "10px", "backgroundColor": "#f1f5f9", "color": NAVY, "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "1.3rem", "marginBottom": "14px"}, children=[html.I(className=f"bi {icon}")]),
                    html.Div(name, style={"fontSize": "1.05rem", "fontWeight": "700", "color": TEXT_DARK, "marginBottom": "4px"}),
                    html.Div(desc, style={"fontSize": "0.83rem", "color": TEXT_MUTED})
                ]),
                html.Div(style={"marginTop": "14px", "paddingTop": "10px", "borderTop": "1px solid #f1f5f9", "display": "flex", "justifyContent": "space-between", "fontSize": "0.78rem", "fontWeight": "600", "color": TEAL}, children=[html.Span("Open Module"), html.I(className="bi bi-arrow-right")])
            ]
        )

    ws_cards = [make_mod_card(*m) for m in MODULES if m[1] == "Planning Workspace"]
    rev_cards = [make_mod_card(*m) for m in MODULES if m[1] == "Planning & Review"]

    modules_section = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "28px"}, children=[
        html.Div([html.H3("Planning Workspace", style={"fontSize": "1.2rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "14px"}), html.Div(ws_cards, style=grid(4))]),
        html.Div([html.H3("Planning & Review", style={"fontSize": "1.2rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "14px"}), html.Div(rev_cards, style=grid(3))])
    ])

    # 5. Building Blocks / 12 Demand Drivers (Impact: —)
    driver_cards = [
        html.Div(
            style={"backgroundColor": "#ffffff", "border": f"1px solid {BORDER}", "borderRadius": "10px", "padding": "16px", "display": "flex", "flexDirection": "column", "justifyContent": "space-between"},
            children=[
                html.Div([
                    html.Div(dtype, style={"fontSize": "0.7rem", "fontWeight": "700", "color": TEAL, "textTransform": "uppercase"}),
                    html.Div(name, style={"fontSize": "0.95rem", "fontWeight": "700", "color": TEXT_DARK, "margin": "4px 0"}),
                    html.Div(desc, style={"fontSize": "0.8rem", "color": TEXT_MUTED})
                ]),
                html.Div(style={"marginTop": "10px", "paddingTop": "8px", "borderTop": "1px solid #f1f5f9", "display": "flex", "justifyContent": "space-between", "fontSize": "0.76rem"}, children=[
                    html.Span("Volume Impact", style={"color": TEXT_MUTED}),
                    html.Span("Impact: —", style={"fontWeight": "700", "color": TEXT_MUTED})
                ])
            ]
        ) for name, dtype, desc in DRIVERS
    ]

    drivers_section = html.Div(style=CARD_STYLE, children=[
        html.H3("Building Blocks / Demand Drivers", style={"fontSize": "1.2rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "4px"}),
        html.Div("Commercial, operational, and supply drivers shaping baseline and incremental volume", style={"fontSize": "0.84rem", "color": TEXT_MUTED, "marginBottom": "18px"}),
        html.Div(driver_cards, style=grid(4, "16px"))
    ])

    # 6. Inventory & Supply Concepts
    inv_cards = [
        html.Div(style={"backgroundColor": "#f8fafc", "border": f"1px solid {BORDER}", "borderRadius": "10px", "padding": "18px"}, children=[
            html.Div(title, style={"fontSize": "0.92rem", "fontWeight": "700", "color": TEXT_DARK, "marginBottom": "4px"}),
            html.Div(desc, style={"fontSize": "0.8rem", "color": TEXT_MUTED})
        ]) for title, desc in SUPPLY_CONCEPTS
    ]

    inv_section = html.Div(style=CARD_STYLE, children=[
        html.H3("Inventory & Supply Health Concepts", style={"fontSize": "1.2rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "4px"}),
        html.Div("Supply chain feasibility, safety stock dynamics, and inventory position alignment", style={"fontSize": "0.84rem", "color": TEXT_MUTED, "marginBottom": "18px"}),
        html.Div(inv_cards, style=grid(3))
    ])

    # 7. Demand Review Checkpoints & Attention Required Clean Empty State
    checkpoints = ["Data Readiness", "Building Blocks", "Top Down Target", "Bottom Up Forecast", "Reconciliation", "Demand Review", "Consensus", "One Volume Plan"]
    dr_items = [
        html.Div(style={"display": "flex", "justifyContent": "space-between", "padding": "10px 14px", "backgroundColor": "#f8fafc", "borderRadius": "8px", "border": f"1px solid {BORDER}"}, children=[
            html.Span(cp, style={"fontSize": "0.85rem", "fontWeight": "600", "color": TEXT_DARK}),
            html.Span("Awaiting data", style={"fontSize": "0.75rem", "color": TEXT_MUTED, "fontStyle": "italic"})
        ]) for cp in checkpoints
    ]

    dr_section = html.Div(style=CARD_STYLE, children=[
        html.H3("Demand Review Gate Status", style={"fontSize": "1.2rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "18px"}),
        html.Div(dr_items, style=grid(4, "12px"))
    ])

    attention_section = html.Div(
        style={"backgroundColor": "#ffffff", "border": "1px dashed #cbd5e1", "borderRadius": "14px", "padding": "28px", "textAlign": "center"},
        children=[
            html.I(className="bi bi-check-circle-fill", style={"fontSize": "2rem", "color": "#10b981", "marginBottom": "8px"}),
            html.Div("No items requiring attention", style={"fontSize": "0.98rem", "fontWeight": "700", "color": TEXT_DARK}),
            html.Div("Zero exception items logged for the selected planning context.", style={"fontSize": "0.82rem", "color": TEXT_MUTED, "marginTop": "2px"})
        ]
    )

    # 8. Executive Quick Actions Bar
    quick_actions = html.Div(
        style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "backgroundColor": NAVY, "padding": "18px 28px", "borderRadius": "14px"},
        children=[
            html.Div([html.I(className="bi bi-lightning-charge-fill me-2", style={"color": "#f59e0b"}), html.Span("QUICK ACTIONS", style={"fontSize": "0.95rem", "fontWeight": "700", "color": "#ffffff"})]),
            html.Div(style={"display": "flex", "gap": "10px"}, children=[
                html.Button(title, style={"background": "rgba(255, 255, 255, 0.1)", "border": "1px solid rgba(255, 255, 255, 0.2)", "color": "#ffffff", "padding": "8px 16px", "borderRadius": "8px", "fontSize": "0.82rem", "fontWeight": "600", "cursor": "pointer"})
                for title in ["Review One Volume Plan", "Review Building Blocks", "Compare Top Down vs Bottom Up", "Open Demand Review"]
            ])
        ]
    )

    return html.Div(style={"padding": "32px 40px 60px 40px", "display": "flex", "flexDirection": "column", "gap": "28px", "maxWidth": "1540px"}, children=[
        banner, ovp_card, reconciliation_card, modules_section, drivers_section, inv_section,
        html.Div(style=grid(2, "24px"), children=[dr_section, attention_section]), quick_actions
    ])

def build_module_view(module_name):
    """Renders a clean placeholder view when navigating to modules."""
    return html.Div(
        style={"padding": "32px 40px 60px 40px", "maxWidth": "1540px"},
        children=[
            html.Div(
                style={**CARD_STYLE, "padding": "40px", "textAlign": "center", "minHeight": "400px", "display": "flex", "flexDirection": "column", "justifyContent": "center", "alignItems": "center"},
                children=[
                    html.I(className="bi bi-box-arrow-in-right", style={"fontSize": "3rem", "color": TEAL, "marginBottom": "16px"}),
                    html.H2(f"Kenvue IBP — {module_name}", style={"fontSize": "1.6rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "8px"}),
                    html.P(f"Planning workspace module for {module_name}.", style={"fontSize": "0.95rem", "color": TEXT_MUTED, "marginBottom": "24px"}),
                    html.Button([html.I(className="bi bi-arrow-left me-1"), html.Span("Return to Home Landing Page")], id="btn-home", style=BTN_OUTLINE)
                ]
            )
        ]
    )

# ==============================================================================
# SECTION 3: DASH APP INITIALIZATION & MASTER LAYOUT
# ==============================================================================
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Kenvue Integrated Business Planning"

app.layout = html.Div(
    style={"display": "flex", "minHeight": "100vh", "width": "100vw", "backgroundColor": BG, "fontFamily": "'Inter', sans-serif", "color": TEXT_DARK, "lineHeight": "1.5"},
    children=[
        build_sidebar("Home"),
        html.Div(
            style={"marginLeft": "270px", "flex": "1", "display": "flex", "flexDirection": "column", "backgroundColor": BG, "minHeight": "100vh"},
            children=[build_header(), html.Div(build_home_content(), id="content")]
        )
    ]
)

# ==============================================================================
# SECTION 4: SINGLE EASY-TO-EXPLAIN NAVIGATION CALLBACK
# ==============================================================================
@app.callback(
    [Output("content", "children"), Output("app-sidebar", "children")],
    [Input({"type": "nav", "index": ALL}, "n_clicks"),
     Input({"type": "card", "index": ALL}, "n_clicks"),
     Input("btn-home", "n_clicks")],
    prevent_initial_call=True
)
def navigate(nav_clicks, card_clicks, home_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return build_home_content(), build_sidebar("Home").children

    trigger = ctx.triggered[0]["prop_id"]
    selected = "Home"

    if "btn-home" not in trigger:
        for input_list in ctx.inputs_list:
            if isinstance(input_list, list):
                for item in input_list:
                    if item.get("id") and isinstance(item["id"], dict) and item["id"]["index"] in trigger:
                        selected = item["id"]["index"]
                        break

    content = build_home_content() if selected == "Home" else build_module_view(selected)
    return content, build_sidebar(selected).children

# ==============================================================================
# SECTION 5: RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  Kenvue Integrated Business Planning")
    print("  Server starting at http://127.0.0.1:8050/")
    print("=" * 70)
    app.run(debug=False, host="127.0.0.1", port=8050)
