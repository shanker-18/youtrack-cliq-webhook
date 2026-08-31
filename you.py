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

    top_color_bar = html.Div(
        style={"display": "flex", "height": "4px", "width": "100%"},
        children=[
            html.Div(style={"backgroundColor": "#019881", "width": "64%", "height": "100%"}),
            html.Div(style={"backgroundColor": "#D97706", "width": "14%", "height": "100%"}),
            html.Div(style={"backgroundColor": "#5B86E5", "width": "14%", "height": "100%"}),
            html.Div(style={"backgroundColor": "#E55B5B", "width": "8%", "height": "100%"})
        ]
    )

    navbar_content = dbc.Navbar(
        className="navbar-kenvue shadow-sm px-4 py-2 bg-white border-bottom",
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

    return html.Div(
        className="sticky-top",
        style={"zIndex": "1030"},
        children=[top_color_bar, navbar_content]
    )
