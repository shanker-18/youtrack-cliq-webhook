from dash import html
import dash_bootstrap_components as dbc

def render_global_header():
    try:
        from auth.session import get_current_user, is_authenticated
        user = get_current_user() or {}
        authenticated = is_authenticated()
    except Exception:
        user = {}
        authenticated = False

    user_name = user.get("display_name", "Niranjan Sapkal")
    user_email = user.get("email", "")
    gbu_name = user.get("gbu_name", "No GBU")
    permission = user.get("permission", "VIEW")

    badge_color = "success" if "EDIT" in permission or "ADMIN" in permission else "info"

    if authenticated:
        user_section = html.Div(
            id="header-user-section",
            className="d-flex align-items-center ms-auto gap-3",
            children=[
                dbc.Badge(f"GBU: {gbu_name}", color="secondary", className="px-2 py-1 text-uppercase fw-semibold"),
                dbc.Badge(f"Role: {permission.replace('_', ' ')}", color=badge_color, className="px-2 py-1 text-uppercase fw-semibold"),
                html.Div(
                    className="d-flex flex-column text-end small",
                    children=[
                        html.Span(user_name, className="fw-bold text-dark"),
                        html.Span(user_email, className="text-muted")
                    ]
                ),
                dbc.Button([html.I(className="bi bi-box-arrow-right me-1"), "Sign Out"], href="/logout", external_link=True, color="outline-secondary", size="sm", className="px-3 rounded-pill")
            ]
        )
    else:
        user_section = html.Div(
            id="header-user-section",
            className="d-flex align-items-center ms-auto gap-2",
            children=[
                dbc.Button([html.I(className="bi bi-grid-fill me-1.5"), "Sign In"], href="/login", external_link=True, style={"backgroundColor": "#2563EB", "borderColor": "#2563EB", "fontWeight": "700", "fontSize": "0.85rem", "borderRadius": "8px", "padding": "8px 18px"})
            ]
        )

    k_logo = html.Div(
        "IBP",
        style={
            "backgroundColor": "#019881",
            "color": "#ffffff",
            "fontWeight": "900",
            "fontSize": "0.78rem",
            "padding": "6px 14px",
            "borderRadius": "18px",
            "letterSpacing": "0.04em",
            "marginRight": "12px",
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center"
        }
    )

    nav_links = html.Div(
        className="d-none d-lg-flex align-items-center justify-content-center gap-4 mx-auto small",
        children=[
            html.A("Benefits", href="#section-benefits", className="text-dark text-decoration-none fw-bold"),
            html.A("How It Works", href="#section-flow", className="text-dark text-decoration-none fw-bold"),
            html.A("Roles", href="#section-roles", className="text-dark text-decoration-none fw-bold"),
            html.A("Guidelines", href="#section-guidelines", className="text-dark text-decoration-none fw-bold"),
            html.Span("Building Blocks", id="nav-bb-btn", style={"cursor": "pointer"}, className="text-dark text-decoration-none fw-bold"),
            html.A("Glossary", href="#section-glossary", className="text-dark text-decoration-none fw-bold")
        ]
    )

    return dbc.Navbar(
        className="navbar-kenvue shadow-sm px-4 py-2 bg-white border-bottom sticky-top",
        children=[
            dbc.NavbarBrand(
                className="d-flex align-items-center text-decoration-none me-2",
                href="/",
                children=[
                    k_logo,
                    html.Span("Integrated Business Planning", className="fs-6 text-dark fw-bold")
                ]
            ),
            nav_links,
            user_section
        ]
    )





import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc

TRUST_GREEN = "#019881"
DARK_TEAL = "#006857"
LIGHT_MINT = "#E8F5F2"
MINT_BORDER = "#BCE5DC"
MINT_HEADER_BG = "#DDF0EC"
BG = "#F8FAFC"
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
    ("Consumption Forecast", "Forecast based on Circana POS data representing consumer demand."),
    ("Building Blocks (BBs)", "Explicit drivers used to adjust the forecast."),
    ("Statistical Baseline", "Trend and seasonality-driven starting point for the bottom-up forecast."),
    ("GTS", "Shipment-based financial output."),
    ("Build / Bleed", "Inventory adjustments between POS consumption and shipments."),
    ("One Number", "The final aligned demand plan."),
    ("IBP Cycle", "The monthly planning cadence."),
    ("POS", "Point-of-sale consumer purchase data used to anchor consumption forecasting.")
]

ROLES_AND_RESPONSIBILITIES = [
    ("Demand Planning", "DP", "Own the statistical baseline, coordinate forecast validation, challenge exceptions, and steward consensus alignment.", TRUST_GREEN),
    ("Brand / Marketing", "BM", "Maintain marketing and portfolio building blocks, including trend, season, media, competition, innovation, renovation, and discontinuation.", "#D97706"),
    ("Sales / Sales Strategy", "SS", "Enter retailer and commercial assumptions, including distribution, pricing, trade and promotion, club, and relevant shipment effects.", "#2563EB"),
    ("Finance", "FI", "Validate the demand plan against financial targets and support alignment between consumption and shipment-based outputs.", "#059669"),
    ("Business Analytics", "BA", "Support data interpretation, dashboards, driver decomposition, trend analysis, and planning insights.", "#7C3AED"),
    ("IT / Data Teams", "IT", "Support data ingestion, platform reliability, integrations, access, version control, and technical operations.", "#475569")
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

FLOW_STEPS = [
    ("1", "Ingest data", "Load POS, SAP shipments, and statistical baseline data."),
    ("2", "Establish baseline", "Demand Planning reviews trend and seasonality-driven forecast."),
    ("3", "Add building blocks", "Teams enter standardized assumptions and supporting rationale."),
    ("4", "Calculate", "Automated engine converts inputs into consumption and shipment views."),
    ("5", "Validate", "Review outliers, phasing, historical trends, scenarios, risks and opportunities."),
    ("6", "Align and publish", "Reach Demand Review consensus and publish the One Number plan.")
]

WHY_IBP_CARDS = [
    ("More predictable plans", "Use consumption signals, statistical baselines, and explicit assumptions to detect change earlier, improve accuracy and bias, and explain monthly movement.", "bi-arrow-up-right", TRUST_GREEN),
    ("A more efficient cycle", "Reduce duplicate work, manual reconciliation, repeated forum content, and inconsistent templates through a centralized workflow.", "bi-arrow-up-right", "#D97706"),
    ("Clear accountability", "Assign ownership to planning drivers, strengthen scenario planning for priority brands, and use a streamlined approach for mid-tier and long-tail brands.", "bi-check2", "#8B5CF6")
]

GUIDELINES = [
    "Begin with the statistical baseline and adjust only through a defined building block.",
    "Use POS-based consumer demand as the anchor; apply inventory build or bleed to translate to shipments.",
    "Enter assumptions with rationale, source, owner, period, and scenario.",
    "Review outliers, historical trends, cycle-to-cycle changes, and imbalanced phasing before approval.",
    "Use 'Other' only for residual or temporary drivers and reallocate when the true driver is confirmed.",
    "Keep the decision trail current so every change to the One Number can be explained."
]

CONTROLS = [
    "Role-based access and approval matrix.",
    "Monthly calendar, cut-off dates, and submission status.",
    "Required evidence and comment standards for assumptions.",
    "Version history, audit trail, and change-log visibility.",
    "Materiality and exception thresholds.",
    "Data freshness and source-system health indicators.",
    "Scenario naming and R&O classification rules.",
    "Help, training, support, contact, and issue reporting.",
    "Accessibility, browser, privacy, and data-handling notices."
]

def section_header(title, subtitle=None, category=None):
    elems = []
    if category:
        elems.append(html.Div(category, style={"fontSize": "0.72rem", "fontWeight": "800", "color": TEXT_MUTED, "letterSpacing": "0.08em", "textTransform": "uppercase", "marginBottom": "4px", "textAlign": "center"}))
    
    header_row = html.H3(title, style={"fontSize": "1.35rem", "fontWeight": "900", "color": TEXT_DARK, "margin": "0 0 6px 0", "textAlign": "center", "letterSpacing": "-0.02em"})
    elems.append(header_row)

    if subtitle:
        elems.append(html.P(subtitle, style={"fontSize": "0.85rem", "color": TEXT_MUTED, "margin": "0 auto", "fontWeight": "500", "textAlign": "center", "maxWidth": "720px", "lineHeight": "1.55"}))

    return html.Div(style={"marginBottom": "20px"}, children=elems)

def divider():
    return html.Hr(style={"border": "none", "borderTop": f"1px solid {BORDER}", "margin": "40px 0"})

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
        html.H5(title, style={"fontSize": "0.98rem", "fontWeight": "900", "color": DARK_TEAL, "marginBottom": "12px"}),
        html.Div(style={"borderRadius": "8px", "overflow": "hidden", "border": f"1px solid {BORDER}", "boxShadow": "0 2px 6px rgba(0,0,0,0.02)", "width": "100%", "maxWidth": "100%", "boxSizing": "border-box"}, children=[
            html.Table(style={"width": "100%", "maxWidth": "100%", "tableLayout": "fixed", "borderCollapse": "collapse", "backgroundColor": "#ffffff", "boxSizing": "border-box"}, children=[
                html.Thead(html.Tr(style={"backgroundColor": th_bg}, children=header_ths)),
                html.Tbody(rows)
            ])
        ])
    ])

def build_home_hero():
    hero_tagline = html.Div(
        style={"display": "inline-flex", "alignItems": "center", "gap": "6px", "fontSize": "0.76rem", "fontWeight": "800", "color": DARK_TEAL, "marginBottom": "16px", "letterSpacing": "0.05em", "textTransform": "uppercase"},
        children=[
            html.Span("\u2022", style={"color": "#D97706", "fontSize": "1.2rem", "lineHeight": "0"}),
            html.Span("KENVUE INTEGRATED BUSINESS PLANNING")
        ]
    )

    hero_headline = html.H1(
        style={"fontSize": "2.75rem", "fontWeight": "900", "color": TEXT_DARK, "lineHeight": "1.18", "marginBottom": "18px", "letterSpacing": "-0.03em"},
        children=[
            "One Number. One Plan. ",
            html.Span("One", style={"color": TRUST_GREEN}),
            " Source of Truth."
        ]
    )

    hero_left = html.Div(
        style={"flex": "1 1 540px", "minWidth": "320px", "display": "flex", "flexDirection": "column", "justifyContent": "center", "boxSizing": "border-box"},
        children=[
            hero_tagline,
            hero_headline,
            html.P(
                "A centralized planning experience that connects consumer demand, business assumptions, and cross-functional expertise to deliver an aligned demand plan.",
                style={"fontSize": "1rem", "color": TEXT_SECONDARY, "lineHeight": "1.65", "marginBottom": "12px", "fontWeight": "500"}
            ),
            html.P(
                "Build forecasts with confidence, improve visibility into key drivers, and collaborate across Brand, Sales, Finance, Demand Planning, Business Analytics, and Technology teams to make faster, more informed decisions.",
                style={"fontSize": "0.86rem", "color": TEXT_MUTED, "lineHeight": "1.6", "marginBottom": "20px"}
            ),
            html.Div(
                style={"display": "flex", "flexWrap": "wrap", "gap": "10px", "marginBottom": "28px"},
                children=[
                    html.Span("Predictable.", style={"color": TEXT_DARK, "fontSize": "0.95rem", "fontWeight": "800"}),
                    html.Span("Efficient.", style={"color": TEXT_DARK, "fontSize": "0.95rem", "fontWeight": "800"}),
                    html.Span("Accountable.", style={"color": TEXT_DARK, "fontSize": "0.95rem", "fontWeight": "800"})
                ]
            ),
            html.Div(
                style={"display": "flex", "flexWrap": "wrap", "gap": "14px"},
                children=[
                    dbc.Button("Explore the planning process", href="#section-flow", external_link=True, style={"backgroundColor": DARK_TEAL, "borderColor": DARK_TEAL, "fontWeight": "800", "fontSize": "0.86rem", "borderRadius": "24px", "padding": "12px 26px"}),
                    dbc.Button("View key definitions", href="#section-glossary", external_link=True, outline=True, style={"color": DARK_TEAL, "borderColor": TRUST_GREEN, "fontWeight": "800", "fontSize": "0.86rem", "borderRadius": "24px", "padding": "12px 26px", "backgroundColor": "#FFFFFF"})
                ]
            )
        ]
    )

    cycle_steps = [
        ("1", "Start with demand signals", "POS, shipments and statistical baseline", TRUST_GREEN, ">"),
        ("2", "Apply business drivers", "Standardized building blocks and assumptions", "#D97706", ">"),
        ("3", "Validate and align", "Exceptions, scenarios and financial targets", "#5B86E5", ">"),
        ("4", "Publish One Number", "Final aligned demand plan", "#E55B5B", "\u2713")
    ]

    cycle_step_cards = []
    for num, title, desc, color, icon in cycle_steps:
        cycle_step_cards.append(
            html.Div(
                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "12px", "padding": "14px 16px", "backgroundColor": "rgba(255, 255, 255, 0.9)", "border": f"1px solid {BORDER_LIGHT}", "borderRadius": "12px", "marginBottom": "12px", "boxShadow": "0 2px 6px rgba(0,0,0,0.015)"},
                children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "14px"}, children=[
                        html.Div(num, style={"width": "30px", "height": "30px", "borderRadius": "50%", "backgroundColor": color, "color": "#FFFFFF", "fontWeight": "900", "fontSize": "0.85rem", "display": "flex", "alignItems": "center", "justifyContent": "center", "flexShrink": "0"}),
                        html.Div([
                            html.Div(title, style={"fontSize": "0.88rem", "fontWeight": "800", "color": TEXT_DARK, "lineHeight": "1.25"}),
                            html.Div(desc, style={"fontSize": "0.77rem", "color": TEXT_MUTED, "marginTop": "2px"})
                        ])
                    ]),
                    html.Span(icon, style={"color": TEXT_MUTED, "fontSize": "0.88rem", "fontWeight": "800"})
                ]
            )
        )

    hero_right_header = html.Div(
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "14px"},
        children=[
            html.Div("MONTHLY IBP CYCLE", style={"fontSize": "0.74rem", "fontWeight": "800", "color": DARK_TEAL, "letterSpacing": "0.06em"}),
            html.Span("One Number", style={"backgroundColor": "#CBE4DE", "color": "#0F172A", "padding": "4px 14px", "borderRadius": "14px", "fontSize": "0.76rem", "fontWeight": "800"})
        ]
    )

    hero_right = html.Div(
        style={"flex": "1 1 440px", "minWidth": "320px", "backgroundColor": "rgba(255, 255, 255, 0.72)", "backdropFilter": "blur(12px)", "border": "1px solid rgba(188, 229, 220, 0.7)", "borderRadius": "26px", "padding": "32px 34px", "boxSizing": "border-box", "boxShadow": "0 20px 40px -15px rgba(0, 0, 0, 0.05)"},
        children=[
            hero_right_header,
            html.H4("From consumer signal to aligned plan", style={"fontSize": "1.2rem", "fontWeight": "900", "color": TEXT_DARK, "margin": "14px 0 20px 0"}),
            html.Div(children=cycle_step_cards)
        ]
    )

    hero_full_width_bg = html.Div(
        style={
            "width": "100%",
            "backgroundColor": "#E6F4F1",
            "backgroundImage": """
                radial-gradient(circle at 92% 20%, rgba(139, 161, 208, 0.45) 0%, rgba(139, 161, 208, 0) 420px),
                radial-gradient(circle at 75% 10%, rgba(158, 211, 202, 0.55) 0%, rgba(158, 211, 202, 0) 360px),
                radial-gradient(circle at 65% 90%, rgba(195, 233, 224, 0.5) 0%, rgba(195, 233, 224, 0) 380px),
                linear-gradient(135deg, #E6F4F1 0%, #EDF7F5 50%, #E4EFF6 100%)
            """,
            "padding": "56px 0 64px 0",
            "marginBottom": "52px",
            "boxSizing": "border-box"
        },
        children=[
            html.Div(
                style={"maxWidth": "1320px", "margin": "0 auto", "padding": "0 40px", "display": "flex", "flexWrap": "wrap", "gap": "48px", "alignItems": "center", "boxSizing": "border-box"},
                children=[hero_left, hero_right]
            )
        ]
    )

    return hero_full_width_bg

def build_home_content():
    hero_section = build_home_hero()

    why_cards = []
    for title, desc, icon, color in WHY_IBP_CARDS:
        why_cards.append(
            html.Div(
                style={"flex": "1 1 280px", "minWidth": "260px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderTop": f"4px solid {color}", "borderRadius": "12px", "padding": "26px", "boxSizing": "border-box", "boxShadow": "0 2px 8px rgba(0,0,0,0.02)"},
                children=[
                    html.Div(style={"width": "36px", "height": "36px", "borderRadius": "50%", "backgroundColor": LIGHT_MINT, "display": "flex", "alignItems": "center", "justifyContent": "center", "marginBottom": "16px"}, children=[html.I(className=f"bi {icon}", style={"fontSize": "1rem", "color": color})]),
                    html.H4(title, style={"fontSize": "1.02rem", "fontWeight": "900", "color": TEXT_DARK, "marginBottom": "10px"}),
                    html.P(desc, style={"fontSize": "0.82rem", "color": TEXT_SECONDARY, "lineHeight": "1.6", "margin": "0"})
                ]
            )
        )

    why_section = html.Div(
        id="section-benefits",
        children=[
            section_header("Predictable. Efficient. Accountable.", "A disciplined planning experience designed to improve forecast quality, reduce reconciliation effort, and make decision ownership visible.", category="WHY IBP"),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "18px", "width": "100%", "boxSizing": "border-box"}, children=why_cards)
        ]
    )

    flow_cards = []
    for idx, (num, title, desc) in enumerate(FLOW_STEPS):
        card = html.Div(
            style={"flex": "1 1 150px", "minWidth": "140px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "10px", "padding": "18px 14px", "boxSizing": "border-box", "textAlign": "center", "boxShadow": "0 2px 6px rgba(0,0,0,0.01)"},
            children=[
                html.Div(num, style={"width": "32px", "height": "32px", "borderRadius": "6px", "backgroundColor": LIGHT_MINT, "color": DARK_TEAL, "fontWeight": "900", "fontSize": "0.9rem", "display": "flex", "alignItems": "center", "justifyContent": "center", "margin": "0 auto 12px auto"}),
                html.Div(title, style={"fontSize": "0.84rem", "fontWeight": "800", "color": TEXT_DARK, "marginBottom": "6px"}),
                html.Div(desc, style={"fontSize": "0.75rem", "color": TEXT_MUTED, "lineHeight": "1.45"})
            ]
        )
        flow_cards.append(card)
        if idx < len(FLOW_STEPS) - 1:
            flow_cards.append(html.Div(">", style={"color": TEXT_MUTED, "alignSelf": "center", "fontWeight": "800", "fontSize": "1.1rem", "padding": "0 2px"}))

    flow_section = html.Div(
        id="section-flow",
        children=[
            section_header("End-to-end planning flow", "The monthly workflow moves from integrated source data through cross-functional assumptions, validation, consensus, and publication.", category="HOW THE APPLICATION WORKS"),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "10px", "alignItems": "center", "width": "100%", "boxSizing": "border-box"}, children=flow_cards)
        ]
    )

    role_cards = []
    for title, badge, desc, color in ROLES_AND_RESPONSIBILITIES:
        role_cards.append(
            html.Div(
                style={"flex": "1 1 360px", "minWidth": "300px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "12px", "padding": "20px 24px", "boxSizing": "border-box", "boxShadow": "0 2px 6px rgba(0,0,0,0.01)"},
                children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "10px"}, children=[
                        html.Span(badge, style={"backgroundColor": LIGHT_MINT, "color": color, "fontWeight": "900", "fontSize": "0.78rem", "padding": "3px 10px", "borderRadius": "12px"}),
                        html.H5(title, style={"fontSize": "0.94rem", "fontWeight": "800", "color": TEXT_DARK, "margin": "0"})
                    ]),
                    html.P(desc, style={"fontSize": "0.81rem", "color": TEXT_SECONDARY, "lineHeight": "1.55", "margin": "0"})
                ]
            )
        )

    roles_section = html.Div(
        id="section-roles",
        children=[
            section_header("Who uses IBP and what they own", "Role-based ownership keeps assumptions traceable and decisions aligned across functions.", category="APPLICATION USERS"),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "width": "100%", "boxSizing": "border-box"}, children=role_cards),
            html.P("Responsibilities for Business Analytics and IT / Data are recommended operating responsibilities. The source content identifies these groups as users but does not specify their duties.", style={"fontSize": "0.75rem", "color": TEXT_MUTED, "marginTop": "16px", "fontStyle": "italic"})
        ]
    )

    guidelines_left = html.Div(
        style={"backgroundColor": "#0F172A", "borderRadius": "14px", "padding": "28px 32px", "color": "#FFFFFF", "flex": "1 1 380px", "minWidth": "300px", "boxSizing": "border-box"},
        children=[
            html.Div("PLANNING GUIDELINES", style={"fontSize": "0.72rem", "fontWeight": "800", "color": "#94A3B8", "letterSpacing": "0.06em", "marginBottom": "6px"}),
            html.H4("Use the application consistently", style={"fontSize": "1.1rem", "fontWeight": "900", "marginBottom": "18px", "color": "#FFFFFF"}),
            html.Ul(
                style={"margin": "0", "padding": "0", "listStyle": "none"},
                children=[
                    html.Li(style={"display": "flex", "alignItems": "flex-start", "gap": "12px", "marginBottom": "14px", "fontSize": "0.82rem", "lineHeight": "1.55", "color": "#E2E8F0"}, children=[
                        html.Span("\u2713", style={"color": "#FFFFFF", "backgroundColor": TRUST_GREEN, "borderRadius": "50%", "width": "20px", "height": "20px", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "0.75rem", "fontWeight": "900", "flexShrink": "0", "marginTop": "2px"}),
                        html.Span(g)
                    ]) for g in GUIDELINES
                ]
            )
        ]
    )

    controls_right = html.Div(
        style={"backgroundColor": "#FAF5EF", "border": "1px solid #F3E8DC", "borderRadius": "14px", "padding": "28px 32px", "flex": "1 1 380px", "minWidth": "300px", "boxSizing": "border-box"},
        children=[
            html.Div("RECOMMENDED ADDITIONS", style={"fontSize": "0.72rem", "fontWeight": "800", "color": "#DC2626", "letterSpacing": "0.06em", "marginBottom": "6px"}),
            html.H4("Controls to include before launch", style={"fontSize": "1.1rem", "fontWeight": "900", "marginBottom": "18px", "color": TEXT_DARK}),
            html.Ul(
                style={"margin": "0", "paddingLeft": "18px", "fontSize": "0.82rem", "color": TEXT_SECONDARY, "lineHeight": "1.65"},
                children=[html.Li(c) for c in CONTROLS]
            )
        ]
    )

    guidelines_section = html.Div(
        id="section-guidelines",
        children=[
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "20px", "width": "100%", "boxSizing": "border-box"}, children=[guidelines_left, controls_right])
        ]
    )

    bb_pill_tabs = html.Div(
        style={"display": "flex", "flexWrap": "wrap", "gap": "12px", "justifyContent": "center", "marginBottom": "28px"},
        children=[
            html.Span("Marketing / Consumption", id="bb-tab-1", n_clicks=0, style={"backgroundColor": DARK_TEAL, "color": "#FFFFFF", "padding": "8px 20px", "borderRadius": "20px", "fontSize": "0.83rem", "fontWeight": "800", "cursor": "pointer", "boxShadow": "0 2px 6px rgba(0,104,87,0.15)"}),
            html.Span("Sales / Retailer", id="bb-tab-2", n_clicks=0, style={"backgroundColor": "#E8EEF5", "color": TEXT_SECONDARY, "padding": "8px 20px", "borderRadius": "20px", "fontSize": "0.83rem", "fontWeight": "700", "cursor": "pointer"}),
            html.Span("Operational / Conversion", id="bb-tab-3", n_clicks=0, style={"backgroundColor": "#E8EEF5", "color": TEXT_SECONDARY, "padding": "8px 20px", "borderRadius": "20px", "fontSize": "0.83rem", "fontWeight": "700", "cursor": "pointer"}),
            html.Span("Portfolio Changes", id="bb-tab-4", n_clicks=0, style={"backgroundColor": "#E8EEF5", "color": TEXT_SECONDARY, "padding": "8px 20px", "borderRadius": "20px", "fontSize": "0.83rem", "fontWeight": "700", "cursor": "pointer"})
        ]
    )

    bb_summary_cards = html.Div(
        style={"display": "flex", "flexWrap": "wrap", "gap": "16px"},
        children=[
            html.Div(
                id="bb-card-1",
                n_clicks=0,
                style={"flex": "1 1 240px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "12px", "padding": "22px 24px", "boxShadow": "0 2px 6px rgba(0,0,0,0.01)", "cursor": "pointer"},
                children=[
                    html.Div("Marketing / Consumption", style={"fontSize": "0.94rem", "fontWeight": "900", "color": TEXT_DARK, "marginBottom": "8px"}),
                    html.Div("Base Trend, Season, Trade & Promotion, Media, Competition", style={"fontSize": "0.81rem", "color": TEXT_MUTED, "lineHeight": "1.5"})
                ]
            ),
            html.Div(
                id="bb-card-2",
                n_clicks=0,
                style={"flex": "1 1 240px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "12px", "padding": "22px 24px", "boxShadow": "0 2px 6px rgba(0,0,0,0.01)", "cursor": "pointer"},
                children=[
                    html.Div("Sales / Retailer", style={"fontSize": "0.94rem", "fontWeight": "900", "color": TEXT_DARK, "marginBottom": "8px"}),
                    html.Div("Distribution, Pricing, Trade & Promotion, Club", style={"fontSize": "0.81rem", "color": TEXT_MUTED, "lineHeight": "1.5"})
                ]
            ),
            html.Div(
                id="bb-card-3",
                n_clicks=0,
                style={"flex": "1 1 240px", "backgroundColor": "#FFFFFF", "border": f"1px solid {BORDER}", "borderRadius": "12px", "padding": "22px 24px", "boxShadow": "0 2px 6px rgba(0,0,0,0.01)", "cursor": "pointer"},
                children=[
                    html.Div("Operations and Portfolio", style={"fontSize": "0.94rem", "fontWeight": "900", "color": TEXT_DARK, "marginBottom": "8px"}),
                    html.Div("Retail Inventory, Other, Innovation, Renovation, Discontinuation", style={"fontSize": "0.81rem", "color": TEXT_MUTED, "lineHeight": "1.5"})
                ]
            )
        ]
    )

    bb_section = html.Div(
        id="section-bbs",
        children=[
            section_header("Use standardized business drivers", "Building blocks explain why the plan changes and connect functional assumptions to forecast outcomes.", category="PLANNING BUILDING BLOCKS"),
            bb_pill_tabs,
            bb_summary_cards
        ]
    )

    bb_modal = dbc.Modal(
        id="bb-detail-modal",
        is_open=False,
        size="xl",
        children=[
            dbc.ModalHeader(
                dbc.ModalTitle("Building Blocks", style={"fontWeight": "900", "color": DARK_TEAL}),
                close_button=True
            ),
            dbc.ModalBody(
                style={"padding": "24px"},
                children=[
                    make_table("Consumer POS Consumption Building Blocks (Marketing)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], CONSUMER_POS_BUILDING_BLOCKS, is_bb=True),
                    html.Div(style={"height": "20px"}),
                    make_table("Retailer POS & Shipment Building Blocks (Sales Strategy)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], RETAILER_POS_BUILDING_BLOCKS, is_bb=True),
                    html.Div(style={"height": "20px"}),
                    make_table("Operational/Conversion Shipment Building Blocks (All)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], OPERATIONAL_CONVERSION_BUILDING_BLOCKS, is_bb=True),
                    html.Div(style={"height": "20px"}),
                    make_table("Portfolio Changes POS & Shipment Building Blocks (Marketing)", ["Building Block Name", "Definition", "Standardized Methodology/Approach"], PORTFOLIO_CHANGES_BUILDING_BLOCKS, is_bb=True)
                ]
            ),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-bb-modal-btn", className="ms-auto", color="secondary", style={"fontWeight": "800", "borderRadius": "20px", "padding": "8px 24px"})
            )
        ]
    )

    def_cards = []
    for term, definition in KEY_TERMS:
        def_cards.append(
            html.Div(
                style={
                    "flex": "1 1 450px",
                    "minWidth": "300px",
                    "backgroundColor": "#FFFFFF",
                    "border": f"1px solid {BORDER}",
                    "borderLeft": f"4px solid {DARK_TEAL}",
                    "borderRadius": "10px",
                    "padding": "18px 22px",
                    "boxSizing": "border-box",
                    "boxShadow": "0 2px 6px rgba(0,0,0,0.01)"
                },
                children=[
                    html.Div(term, style={"fontSize": "0.92rem", "fontWeight": "900", "color": TEXT_DARK, "marginBottom": "4px"}),
                    html.Div(definition, style={"fontSize": "0.81rem", "color": TEXT_MUTED, "lineHeight": "1.5"})
                ]
            )
        )

    glossary_section = html.Div(
        id="section-glossary",
        children=[
            section_header("Speak the same planning language", "Quick definitions for the terms used throughout the application.", category="KEY DEFINITIONS"),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "width": "100%", "boxSizing": "border-box"}, children=def_cards)
        ]
    )

    cta_banner = html.Div(
        style={"background": f"linear-gradient(135deg, {DARK_TEAL} 0%, {TRUST_GREEN} 100%)", "borderRadius": "16px", "padding": "36px 44px", "marginTop": "44px", "color": "#FFFFFF", "display": "flex", "flexWrap": "wrap", "alignItems": "center", "justifyContent": "space-between", "gap": "24px", "boxShadow": "0 10px 30px -5px rgba(1, 152, 129, 0.25)"},
        children=[
            html.Div(
                style={"flex": "1 1 380px"},
                children=[
                    html.Div("READY TO PLAN?", style={"fontSize": "0.72rem", "fontWeight": "800", "color": "#E6F5F2", "letterSpacing": "0.06em", "marginBottom": "4px"}),
                    html.H3("Start with the latest planning cycle", style={"fontSize": "1.35rem", "fontWeight": "900", "margin": "0 0 6px 0", "color": "#FFFFFF"}),
                    html.P("Review source-data status, complete your assigned assumptions, and resolve exceptions before Demand Review.", style={"fontSize": "0.85rem", "color": "#E6F5F2", "margin": "0"})
                ]
            ),
            html.Div(
                style={"display": "flex", "flexWrap": "wrap", "gap": "12px"},
                children=[
                    dbc.Button("Open planning workspace", href="/planning", external_link=True, style={"backgroundColor": "#FFFFFF", "color": DARK_TEAL, "fontWeight": "800", "fontSize": "0.85rem", "borderRadius": "24px", "padding": "10px 22px", "border": "none"}),
                    dbc.Button("View cycle calendar", href="#section-flow", external_link=True, outline=True, style={"color": "#FFFFFF", "borderColor": "rgba(255,255,255,0.4)", "fontWeight": "800", "fontSize": "0.85rem", "borderRadius": "24px", "padding": "10px 22px"})
                ]
            )
        ]
    )

    inner_content = html.Div(
        style={"maxWidth": "1280px", "margin": "0 auto", "padding": "0 24px 36px 24px", "width": "100%", "boxSizing": "border-box"},
        children=[
            why_section,
            divider(),
            flow_section,
            divider(),
            roles_section,
            divider(),
            guidelines_section,
            divider(),
            bb_section,
            divider(),
            glossary_section,
            cta_banner,
            bb_modal
        ]
    )

    return html.Div(children=[hero_section, inner_content])

@dash.callback(
    Output("bb-detail-modal", "is_open"),
    [
        Input("nav-bb-btn", "n_clicks"),
        Input("bb-tab-1", "n_clicks"),
        Input("bb-tab-2", "n_clicks"),
        Input("bb-tab-3", "n_clicks"),
        Input("bb-tab-4", "n_clicks"),
        Input("bb-card-1", "n_clicks"),
        Input("bb-card-2", "n_clicks"),
        Input("bb-card-3", "n_clicks"),
        Input("close-bb-modal-btn", "n_clicks")
    ],
    [State("bb-detail-modal", "is_open")]
)
def toggle_bb_modal(c_nav, t1, t2, t3, t4, c1, c2, c3, c_close, is_open):
    if c_nav or t1 or t2 or t3 or t4 or c1 or c2 or c3 or c_close:
        return not is_open
    return is_open

def layout():
    return html.Div(
        style={
            "minHeight": "calc(100vh - 64px)",
            "width": "100%",
            "backgroundColor": BG,
            "fontFamily": "'Inter', 'Kenvue Sans', system-ui, -apple-system, sans-serif",
            "color": TEXT_DARK,
            "overflowX": "hidden",
            "boxSizing": "border-box",
        },
        children=[build_home_content()]
    )

dash.register_page(__name__, path="/", name="Home", title="Home - NA IBP Planning")
