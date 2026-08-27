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

    user_name = user.get("display_name", "Guest User")
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
                dbc.Button([html.I(className="bi bi-box-arrow-right me-1"), "Sign Out"], href="/logout", external_link=True, color="outline-secondary", size="sm", className="px-3")
            ]
        )
    else:
        user_section = html.Div(
            id="header-user-section",
            className="d-flex align-items-center ms-auto gap-3",
            children=[
                dbc.Button([html.I(className="bi bi-microsoft me-1"), "Sign In"], href="/login", external_link=True, color="primary", size="sm", className="px-3")
            ]
        )

    k_logo = html.Div(
        "K",
        style={
            "width": "32px", "height": "32px", "backgroundColor": "#019881",
            "borderRadius": "6px", "display": "flex", "alignItems": "center",
            "justifyContent": "center", "color": "#ffffff", "fontWeight": "900",
            "fontSize": "1.1rem", "marginRight": "10px"
        }
    )

    return dbc.Navbar(
        className="navbar-kenvue shadow-sm px-4 py-2 mb-3 bg-white border-bottom",
        children=[
            dbc.NavbarBrand(
                className="d-flex align-items-center text-decoration-none",
                href="/",
                children=[
                    k_logo,
                    html.Span("KENVUE", className="fw-bold fs-4 me-2", style={"color": "#019881"}),
                    html.Span("NA IBP Planning", className="fs-5 text-dark fw-semibold")
                ]
            ),
            user_section
        ]
    )
