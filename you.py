import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from components.header import render_global_header

dash.register_page(__name__, path="/", name="Home", title="Home - NA IBP Planning")

TRUST_GREEN = "#019881"
DARK_TEAL = "#006857"
LIGHT_MINT = "#E6F5F2"
MINT_BORDER = "#BCE5DC"
MINT_HEADER_BG = "#DDF0EC"
BG = "#F4FAF8"
SIDEBAR_BG = "#FFFFFF"
BORDER = "#E2E8F0"
BORDER_LIGHT = "#F1F5F9"
TEXT_DARK = "#0F172A"
TEXT_SECONDARY = "#334155"
TEXT_MUTED = "#64748B"

PREDICTABLE_EFFICIENT_ACCOUNTABLE = [
    ("Predictable", "Our top 10 brands require higher accuracy, earlier signal detection and tighter assumption management.", ["Delivering a reliable, consumption-based, assumption-driven plan that is more accurate for priority brands.", "Improve BIAS/MAPE and clearly explains monthly changes."]),
    ("Efficient", "Reduce waste & Increase Discipline with Directionally Accurate > Precisely Wrong.", ["Eliminating duplicate work and repeated content across Forums (DR, PMR and MBR)", "Simplifying building blocks", "Reducing manual effort", "Standardizing templates & expectations", "Making DR/PMR/MBR decisive, not performative"]),
    ("Accountable", "Strengthen Long-Term, Cross-Functional Accountability", ["The top 10 priority brands get deeper scenario planning, stronger BB ownership, and more robust R&Os.", "Mid-tier brands follow a streamlined, standardized process", "Long-tail brands rely more heavily on baseline+few/select BBs"])
]

PURPOSE = {
    "title": "Purpose:",
    "main_points": ["The purpose of the IBP application is to define the requirements and process steps for implementing a centralized consumption-based forecasting platform and delivers a single aligned demand plan (\"One Number\") for Kenvue.", "This IBP application ensures:"],
    "sub_points": ["Standardization of forecasting inputs and calculations", "Improved forecast accuracy and bias reduction", "Alignment across Brand, Sales, Finance, and Supply", "Reduction in manual reconciliation and inefficiencies"],
    "conclusion": "This supports the IBP transformation objective of a single consumption-based plan with improved predictability, efficiency, and accountability."
}

SCOPE = {
    "title": "Scope",
    "text": "This procedure covers the end-to-end forecasting process, beginning with data ingestion and building block input collection through forecast calculation, validation, and final consensus alignment (Demand Review output).",
    "applies_to": ["Demand Planning", "Brand / Marketing", "Sales", "Finance", "Business Analytics (BP&A)", "IT / Data teams"]
}

KEY_TERMS = [
    ("Consumption Forecast", "Forecast based on POS Circana Data (consumer demand)"),
    ("Building Blocks (BBs)", "Explicit drivers of forecast adjustments"),
    ("Statistical Baseline", "Trend/seasonality-driven starting forecast for the Bottoms-up approach"),
    ("GTS", "Shipment-based financial output"),
    ("Build/Bleed", "Inventory adjustments between POS and shipments"),
    ("One Number", "Final aligned demand plan"),
    ("IBP Cycle", "Monthly planning cadence")
]

ROLES_AND_RESPONSIBILITIES = [
    ("Brand / Marketing", "Input Marketing building blocks"),
    ("Sales", "Input Sales assumptions"),
    ("Finance", "Validate plan vs financial targets"),
    ("Demand Planning", "Own statistical baseline and forecast validation")
]

POS_BASED_FORECASTING = [
    "Forecasts anchored in actual consumer purchases layered with inventory build/bleeds driven by retailer insights",
    "Clean demand signal with reduced noise and bias",
    "Earlier detection of trends, seasonality, and disruptions",
    "Easier decomp to understand baseline vs. promotional lift",
    "Consumer-centric planning aligned with retail partners"
]

CONSUMPTION_EQ = "2025 Circana POS $ + Consumption driving POS $ \u0394 versus YA = 2026 POS $"
SHIPMENT_EQ = "2026 Factory POS $ + Non-POS drivers accounting for pipe, phasing, and seasonal build/bleed behaviors = 2026 GTS $"

FUTURE_STATE = {
    "vision": "A centralized, consumption-based forecasting platform that replaces Excel and delivers a single aligned demand plan across functions",
    "core_capabilities": [
        ("1. Integrated Data Foundation", ["Automated ingestion: POS (Circana), Shipments (SAP), Statistical baseline (Pecan)", "Central storage & version control"]),
        ("2. Standardized Building Block Inputs", []),
        ("3. Automated Forecast Engine", ["Backend calcs & auto conversions"]),
        ("4. Validation & Governance", ["Flags outliers vs historical trend & Imbalanced phasing"]),
        ("5. Visualization & Decision Support", ["Dynamic dashboards: One Number vs Plan vs PY (+ Cycle-to-cycle changes)", "Driver decomposition (Future State: AI generated)"])
    ]
}

VALUE_TO_BUSINESS = [
    "Single source of truth (\"One Number\")",
    "Reduced manual effort & errors",
    "Faster, more efficient IBP cycle",
    "Improved forecast accuracy & bias reduction",
    "Clear accountability by driver"
]

CONSUMER_POS_BUILDING_BLOCKS = [
    ("Base Trend", "Captures demand trend outside of all other building blocks, including major market/brand factors\nProjected category growth rate should be utilized as validation vs. input", "I. Circana Complete Why Tool (Trend/Driver Isolation) | {Upcoming Tool Training}\nII. Utilize \"Other\" block until \"trend\" can be appropriately defined"),
    ("Season", "Seasonal Incidences (CCFS/Allergy/Sun)", "I. Regression Model (Seasonal drivers vs. Historical Category POS Units)\nII. Determine seasonal baseline assumption & apply to regression formula\nIII. Apply monthly PY brand unit share for monthly projections\nIV. Capture high & low scenario with R+O's"),
    ("Trade & Promotion", "Incremental volume from meaningful national promo changes (ex. DFSI/FSI)", "I. Promo lift (estimated/actual) vs YA baseline"),
    ("Media", "Incremental volume from media spend & allocation changes; excludes innovation", "I. \u0394 Channel Spend \u00d7 Marginal ROI {Upcoming Tool Training}"),
    ("Competition", "Impact of competitor actions (recalls, new launches, expanded distro, price, etc.)", "I. Assumption Approach: Volume/Share impact % \u00d7 Impacted Brand Volume\nII. Modeling Approach: Circana Assortment Model (Forecast) & Source of Volume (Actuals)")
]

RETAILER_POS_BUILDING_BLOCKS = [
    ("Distribution", "Volume from distribution changes on volume (ex. door counts, adds, or deletes)\nExcludes national discontinuations and innovations\nIncludes new channels distribution expansions", "Distro POS:\nI. Units/Store/Week \u00d7 Customer Door Changes \u00d7 Weeks \u00d7 Avg. Base Price\nII. Apply incrementality/cannibalization assumptions (if needed)\nDistro Pipe: Pipe units/store \u00d7 doors"),
    ("Pricing", "Impact of price changes and elasticity", "I. POS Gross price realization: (New Price - Old Price) \u00d7 Volume\nII. POS Price elasticity:\nI. Volume % Change = Price % Change \u00d7 Elasticity\nII. New Volume = Old Volume \u00d7 (1 + Volume % Change)\nIII. (New Volume - Old Volume) \u00d7 New Price"),
    ("Trade & Promotion", "Incremental volume from meaningful promo changes (includes changes coming from price promo, feature, display, & new retailer strategies)", "I. Trade POS: Promo lift (estimated/actual) vs YA baseline\nII. Trade Pipe: Pipe volume build with subsequent bleed assumptions (Net = 0)"),
    ("Club", "YoY impact of club sell-in activity across key club customers - Costco, Sam's, BJ's (distribution, new item, promo shifts, etc.)", "I. Club POS: NEW Club POS forecast\nII. Club Pipe (Shipments): Output of Club alignment forecast & actuals")
]

OPERATIONAL_CONVERSION_BUILDING_BLOCKS = [
    ("Retail Inventory", "Impact of retailer stock build/bleed; excludes club/trade/innovation/distribution pipe & pent-up demand", "I. Utilize Ship vs. POS gap trends from PY (available via validation charts) to align on expectations"),
    ("Other", "Residual drivers not accounted for in other building blocks\nIncludes: quality issues (demand), supply disruptions, one-time events, pent up demand re-pipe, and unconfirmed driver (up to 3 cycles).", "I. Categorized Factors (Supply, Liquidation, 53rd Week)\nII. Hold for remaining variance (within tolerance threshold or temporary volume for reallocation to other BB)")
]

PORTFOLIO_CHANGES_BUILDING_BLOCKS = [
    ("Innovation", "Volume from new product launches net of cannibalization", "I. Innovation POS:\nI. Business case adjusted for media/distro/promo minus cannibalization\nII. Customer informed forecast (velocity & door assumptions)\nII. Innovation Pipe (Shipments): Estimated retailer pipe/stores \u00d7 doors"),
    ("Renovation", "Impact of product improvements/changes\nLabelling / artwork changes to improve, maintain or prevent degradation\nChanges in formulation or packaging composition\nExclusive of media impact", "I. Estimate expected impact from BASES / concept testing, or benchmark similar renovations in the portfolio/category\nII. Remove any expected cannibalization to account for sourced volume"),
    ("Discontinuation", "Volume loss from production/distribution stop for a product nationally", "I. (-PY POS Volume) + Transferability")
]

def section_header(title):
    return html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px", "paddingLeft": "2px"}, children=[
        html.Div(style={"width": "4px", "height": "20px", "backgroundColor": TRUST_GREEN, "borderRadius": "2px"}),
        html.H3(title, style={"fontSize": "1.08rem", "fontWeight": "900", "color": TRUST_GREEN, "margin": "0", "letterSpacing": "-0.01em"})
    ])

def divider():
    return html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "24px 0"})

def make_table(title, headers, rows_data, is_bb=False):
    rows = []
    for idx, row in enumerate(rows_data):
        bg = "#FFFFFF" if idx % 2 == 0 else "#F9FCFB"
        if is_bb:
            col1 = html.Span(row[0], style={"backgroundColor": LIGHT_MINT, "color": DARK_TEAL, "padding": "4px 10px", "borderRadius": "4px", "fontSize": "0.8rem", "fontWeight": "800", "display": "inline-block"})
            c2_content = [html.Div(l, style={"wordWrap": "break-word", "wordBreak": "break-word"}) for l in row[1].split("\n")]
            c3_content = [html.Div(l, style={"wordWrap": "break-word", "wordBreak": "break-word"}) for l in row[2].split("\n")]
            tds = [
                html.Td(col1, style={"padding": "12px 14px", "verticalAlign": "top", "width": "22%", "boxSizing": "border-box"}),
                html.Td(c2_content, style={"padding": "12px 14px", "fontSize": "0.81rem", "color": TEXT_SECONDARY, "lineHeight": "1.55", "verticalAlign": "top", "width": "38%", "wordWrap": "break-word", "wordBreak": "break-word", "whiteSpace": "normal", "boxSizing": "border-box"}),
                html.Td(c3_content, style={"padding": "12px 14px", "fontSize": "0.81rem", "color": TEXT_DARK, "lineHeight": "1.55", "verticalAlign": "top", "width": "40%", "wordWrap": "break-word", "wordBreak": "break-word", "whiteSpace": "normal", "boxSizing": "border-box"})
            ]
        else:
            tds = [
                html.Td(row[0], style={"padding": "10px 14px", "fontSize": "0.82rem", "fontWeight": "800", "color": DARK_TEAL, "width": "30%", "verticalAlign": "top", "wordWrap": "break-word", "wordBreak": "break-word", "boxSizing": "border-box"}),
                html.Td(row[1], style={"padding": "10px 14px", "fontSize": "0.81rem", "color": TEXT_SECONDARY, "lineHeight": "1.5", "verticalAlign": "top", "width": "70%", "wordWrap": "break-word", "wordBreak": "break-word", "whiteSpace": "normal", "boxSizing": "border-box"})
            ]
        rows.append(html.Tr(style={"borderBottom": f"1px solid {BORDER_LIGHT}", "backgroundColor": bg}, children=tds))

    th_bg, th_color = (TRUST_GREEN, "#ffffff") if is_bb else (MINT_HEADER_BG, DARK_TEAL)
    widths = ["22%", "38%", "40%"] if is_bb else ["30%", "70%"]
    header_ths = [html.Th(h, style={"padding": "10px 14px", "fontSize": "0.76rem", "fontWeight": "800", "color": th_color, "textAlign": "left", "width": widths[i], "letterSpacing": "0.03em", "boxSizing": "border-box"}) for i, h in enumerate(headers)]

    return html.Div([
        section_header(title),
        html.Div(style={"borderRadius": "8px", "overflow": "hidden", "border": f"1px solid {BORDER}", "boxShadow": "0 2px 6px rgba(0,0,0,0.02)", "width": "100%", "maxWidth": "100%", "boxSizing": "border-box"}, children=[
            html.Table(style={"width": "100%", "maxWidth": "100%", "tableLayout": "fixed", "borderCollapse": "collapse", "backgroundColor": "#ffffff", "boxSizing": "border-box"}, children=[
                html.Thead(html.Tr(style={"backgroundColor": th_bg}, children=header_ths)),
                html.Tbody(rows)
            ])
        ])
    ])

def build_sidebar():
    nav = html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "8px", "padding": "10px 16px", "color": DARK_TEAL, "backgroundColor": LIGHT_MINT, "borderRadius": "8px", "fontSize": "0.88rem", "fontWeight": "800", "margin": "16px 12px", "boxSizing": "border-box"},
        children=[html.I(className="bi bi-house-door-fill", style={"fontSize": "1rem"}), html.Span("Home")]
    )

    footer = html.Div(
        style={"padding": "12px 18px", "borderTop": f"1px solid {BORDER}", "fontSize": "0.72rem", "color": TEXT_MUTED, "fontWeight": "600", "display": "flex", "alignItems": "center", "justifyContent": "space-between", "boxSizing": "border-box"},
        children=[html.Span("IBP"), html.Span("v1.1", style={"backgroundColor": LIGHT_MINT, "color": DARK_TEAL, "padding": "2px 8px", "borderRadius": "4px", "fontWeight": "800"})]
    )

    return html.Div(
        style={"width": "280px", "minWidth": "280px", "backgroundColor": SIDEBAR_BG, "borderRight": f"1px solid {BORDER}", "display": "flex", "flexDirection": "column", "position": "fixed", "top": "64px", "bottom": "0", "left": "0", "zIndex": "100", "boxSizing": "border-box"},
        children=[nav, html.Div(style={"flex": "1"}), footer]
    )

def build_home_content():
    sec1_cards = [html.Div(style={"backgroundColor": "rgba(255, 255, 255, 0.12)", "border": "1px solid rgba(255, 255, 255, 0.22)", "borderRadius": "8px", "padding": "16px 20px", "flex": "1 1 240px", "minWidth": "200px", "boxSizing": "border-box"}, children=[html.Div(t, style={"fontSize": "1rem", "fontWeight": "900", "color": "#ffffff", "marginBottom": "4px"}), html.Div(d, style={"fontSize": "0.81rem", "fontWeight": "700", "color": "#E6F5F2", "marginBottom": "10px", "lineHeight": "1.4"}), html.Ul(style={"margin": "0", "paddingLeft": "18px", "fontSize": "0.78rem", "color": "#FFFFFF", "lineHeight": "1.55"}, children=[html.Li(b) for b in buls])]) for t, d, buls in PREDICTABLE_EFFICIENT_ACCOUNTABLE]
    hero = html.Div(style={"background": f"linear-gradient(135deg, {TRUST_GREEN} 0%, {DARK_TEAL} 100%)", "borderRadius": "10px", "padding": "24px 28px", "marginBottom": "24px", "boxShadow": "0 8px 24px -4px rgba(1, 152, 129, 0.22)", "width": "100%", "boxSizing": "border-box"}, children=[html.Div("INTEGRATED BUSINESS PLANNING FRAMEWORK", style={"fontSize": "0.75rem", "fontWeight": "800", "color": "#E6F5F2", "textTransform": "uppercase", "letterSpacing": "0.08em", "marginBottom": "6px"}), html.H2("Predictable. Efficient. Accountable.", style={"fontSize": "1.45rem", "fontWeight": "900", "color": "#ffffff", "margin": "0 0 18px 0"}), html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "width": "100%", "boxSizing": "border-box"}, children=sec1_cards)])
    purpose = html.Div([section_header("Purpose:"), html.Div(style={"backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px 20px", "width": "100%", "boxSizing": "border-box"}, children=[html.P(PURPOSE["main_points"][0], style={"fontSize": "0.84rem", "color": TEXT_DARK, "lineHeight": "1.6", "marginBottom": "10px"}), html.P(PURPOSE["main_points"][1], style={"fontSize": "0.84rem", "fontWeight": "800", "color": DARK_TEAL, "marginBottom": "6px"}), html.Ul(style={"margin": "0 0 10px 0", "paddingLeft": "22px", "fontSize": "0.82rem", "color": TEXT_SECONDARY, "lineHeight": "1.6"}, children=[html.Li(sp) for sp in PURPOSE["sub_points"]]), html.Div(PURPOSE["conclusion"], style={"fontSize": "0.82rem", "color": DARK_TEAL, "fontWeight": "800", "backgroundColor": LIGHT_MINT, "padding": "8px 14px", "borderRadius": "6px", "boxSizing": "border-box"})])])
    scope = html.Div([section_header("Scope"), html.Div(style={"backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px 20px", "width": "100%", "boxSizing": "border-box"}, children=[html.P(SCOPE["text"], style={"fontSize": "0.84rem", "color": TEXT_DARK, "lineHeight": "1.6", "marginBottom": "12px"}), html.Div("This IBP application applies to:", style={"fontSize": "0.84rem", "fontWeight": "800", "color": DARK_TEAL, "marginBottom": "6px"}), html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "8px"}, children=[html.Span(t, style={"backgroundColor": LIGHT_MINT, "color": DARK_TEAL, "padding": "4px 12px", "borderRadius": "20px", "fontSize": "0.78rem", "fontWeight": "800"}) for t in SCOPE["applies_to"]])])])
    eq_box = lambda title, eq: html.Div([section_header(title), html.Div(style={"backgroundColor": LIGHT_MINT, "border": f"1px solid {MINT_BORDER}", "borderLeft": f"5px solid {TRUST_GREEN}", "borderRadius": "6px", "padding": "14px 20px", "fontFamily": "monospace", "fontSize": "0.88rem", "fontWeight": "800", "color": DARK_TEAL, "width": "100%", "wordWrap": "break-word", "wordBreak": "break-word", "whiteSpace": "normal", "boxSizing": "border-box"}, children=[eq])])
    list_box = lambda title, items: html.Div([section_header(title), html.Div(style={"backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "16px 20px", "width": "100%", "boxSizing": "border-box"}, children=[html.Ul(style={"margin": "0", "paddingLeft": "20px", "fontSize": "0.84rem", "color": TEXT_DARK, "lineHeight": "1.7"}, children=[html.Li(x) for x in items])])])
    future = html.Div([section_header("Future State:"), html.Div(style={"backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "8px", "padding": "18px 22px", "width": "100%", "boxSizing": "border-box"}, children=[html.Div([html.Strong("Vision: ", style={"color": TRUST_GREEN, "fontWeight": "900"}), html.Span(FUTURE_STATE["vision"], style={"fontSize": "0.86rem", "fontWeight": "700", "color": TEXT_DARK})], style={"marginBottom": "14px"}), html.H4("Core Capabilities of the Tool", style={"fontSize": "0.9rem", "fontWeight": "900", "color": DARK_TEAL, "marginBottom": "10px"}), html.Div([html.Div(style={"padding": "12px 14px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "6px", "marginBottom": "8px", "boxSizing": "border-box"}, children=[html.Div(ct, style={"fontSize": "0.84rem", "fontWeight": "800", "color": DARK_TEAL}), html.Ul(style={"margin": "4px 0 0 0", "paddingLeft": "18px", "fontSize": "0.78rem", "color": TEXT_SECONDARY, "lineHeight": "1.5"}, children=[html.Li(b) for b in cbuls]) if cbuls else []]) for ct, cbuls in FUTURE_STATE["core_capabilities"]])])])
    doc_container = html.Div(style={"backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "10px", "padding": "28px 32px", "width": "100%", "maxWidth": "100%", "boxSizing": "border-box", "boxShadow": "0 4px 20px -2px rgba(1, 152, 129, 0.06)", "overflowX": "hidden"}, children=[hero, purpose, divider(), scope, divider(), make_table("Key Terms:", ["Term", "Definition"], KEY_TERMS), divider(), make_table("Roles and Responsibilities", ["Role", "Responsibilities"], ROLES_AND_RESPONSIBILITIES), divider(), list_box("POS-Based Forecasting", POS_BASED_FORECASTING), divider(), eq_box("Consumption:", CONSUMPTION_EQ), divider(), eq_box("Shipments:", SHIPMENT_EQ), divider(), future, divider(), list_box("Value to the Business:", VALUE_TO_BUSINESS), divider(), make_table("1) Consumer POS Consumption Building Blocks (Marketing)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], CONSUMER_POS_BUILDING_BLOCKS, is_bb=True), divider(), make_table("2) Retailer POS & Shipment Building Blocks (Sales Strategy)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], RETAILER_POS_BUILDING_BLOCKS, is_bb=True), divider(), make_table("3) Operational/Conversion Shipment Building Blocks (All)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], OPERATIONAL_CONVERSION_BUILDING_BLOCKS, is_bb=True), divider(), make_table("4) Portfolio Changes POS & Shipment Building Blocks (Marketing)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], PORTFOLIO_CHANGES_BUILDING_BLOCKS, is_bb=True)])
    return html.Div(style={"padding": "20px 24px", "width": "100%", "maxWidth": "100%", "boxSizing": "border-box"}, children=[doc_container])

def layout():
    return html.Div(
        style={
            "display": "flex",
            "minHeight": "100vh",
            "width": "100%",
            "backgroundColor": BG,
            "fontFamily": "'Inter', 'Kenvue Sans', system-ui, -apple-system, sans-serif",
            "color": TEXT_DARK,
            "overflowX": "hidden",
            "boxSizing": "border-box",
        },
        children=[
            build_sidebar(),
            html.Div(
                style={
                    "marginLeft": "280px",
                    "flex": "1",
                    "minHeight": "100vh",
                    "backgroundColor": BG,
                    "overflowX": "hidden",
                    "boxSizing": "border-box",
                },
                children=[
                    render_global_header(),
                    html.Div(
                        id="content",
                        children=build_home_content(),
                        style={"flex": "1", "width": "100%", "boxSizing": "border-box"},
                    ),
                ],
            ),
        ],
    )
