from dash import html, dcc, Input, Output, State, callback, ctx
import dash_bootstrap_components as dbc

def render_login_modal() -> dbc.Modal:
    left_panel = html.Div(
        style={
            "flex": "1 1 48%",
            "minWidth": "280px",
            "background": "linear-gradient(180deg, #022B35 0%, #044350 100%)",
            "borderRadius": "12px",
            "padding": "36px 28px",
            "color": "#FFFFFF",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center"
        },
        children=[
            html.H2(
                "Welcome to\nNA IBP Planning",
                style={"fontSize": "1.65rem", "fontWeight": "900", "color": "#FFFFFF", "lineHeight": "1.25", "marginBottom": "16px", "whiteSpace": "pre-line"}
            ),
            html.P(
                "Capture, validate, and manage your planning in one place.",
                style={"color": "#2DD4BF", "fontSize": "0.92rem", "fontWeight": "600", "lineHeight": "1.5", "marginBottom": "32px"}
            ),
            html.Div(
                style={"display": "flex", "flexDirection": "column", "gap": "18px"},
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px"},
                        children=[
                            html.I(className="bi bi-check-circle", style={"fontSize": "1.15rem", "color": "#2DD4BF"}),
                            html.Span("Fast structured data entry", style={"fontSize": "0.86rem", "fontWeight": "600", "color": "#FFFFFF"})
                        ]
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px"},
                        children=[
                            html.I(className="bi bi-check-circle", style={"fontSize": "1.15rem", "color": "#2DD4BF"}),
                            html.Span("Built-in field validation", style={"fontSize": "0.86rem", "fontWeight": "600", "color": "#FFFFFF"})
                        ]
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px"},
                        children=[
                            html.I(className="bi bi-check-circle", style={"fontSize": "1.15rem", "color": "#2DD4BF"}),
                            html.Span("Searchable record update history", style={"fontSize": "0.86rem", "fontWeight": "600", "color": "#FFFFFF"})
                        ]
                    )
                ]
            )
        ]
    )

    right_panel = html.Div(
        style={
            "flex": "1 1 48%",
            "minWidth": "280px",
            "padding": "24px 20px",
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center",
            "gap": "20px"
        },
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "16px"},
                children=[
                    html.Div(style={"flex": "1", "height": "1px", "backgroundColor": "#E2E8F0"}),
                    html.Span("Login as a SSO", style={"fontSize": "0.82rem", "fontWeight": "700", "color": "#64748B"}),
                    html.Div(style={"flex": "1", "height": "1px", "backgroundColor": "#E2E8F0"})
                ]
            ),
            dbc.Button(
                [
                    html.I(className="bi bi-grid-fill me-2.5", style={"fontSize": "1.1rem", "color": "#0F172A"}),
                    html.Span("Login with Microsoft Entra ID", style={"fontWeight": "800", "color": "#0F172A", "fontSize": "0.92rem"})
                ],
                id="btn-microsoft-sso",
                href="/login",
                external_link=True,
                style={
                    "backgroundColor": "#FFFFFF",
                    "borderColor": "#CBD5E1",
                    "borderRadius": "8px",
                    "padding": "14px",
                    "boxShadow": "0 1px 3px rgba(0,0,0,0.05)"
                },
                className="w-100 d-flex align-items-center justify-content-center"
            ),
            dbc.Button(
                "Close",
                id="login-modal-close-btn",
                style={
                    "backgroundColor": "#1D61E7",
                    "borderColor": "#1D61E7",
                    "borderRadius": "8px",
                    "padding": "14px",
                    "fontSize": "0.92rem",
                    "fontWeight": "800"
                },
                className="w-100 text-white"
            )
        ]
    )

    content_grid = html.Div(
        style={"display": "flex", "flexWrap": "wrap", "gap": "24px", "alignItems": "center"},
        children=[left_panel, right_panel]
    )

    return dbc.Modal(
        id="login-sso-modal",
        is_open=False,
        centered=True,
        size="lg",
        backdrop=True,
        className="login-modal",
        children=[
            html.Div(
                style={
                    "height": "5px",
                    "background": "linear-gradient(90deg, var(--g, #019881) 0 62%, var(--y, #D97706) 62% 76%, var(--p, #5B86E5) 76% 89%, var(--c, #E55B5B) 89%)",
                    "borderRadius": "8px 8px 0 0"
                }
            ),
            dbc.ModalHeader(
                dbc.ModalTitle(
                    html.Div(
                        className="d-flex align-items-center gap-2",
                        children=[
                            html.Img(
                                src="/assets/kenvue-logo-black-rgb.svg",
                                alt="Kenvue",
                                style={"height": "24px", "width": "auto"}
                            ),
                            html.Span("|", className="text-muted fs-5", style={"opacity": "0.3"}),
                            html.Span("NA IBP Planning Workspace", className="fs-6 fw-bold text-dark")
                        ]
                    )
                ),
                close_button=True
            ),
            dbc.ModalBody(
                style={"padding": "24px"},
                children=[content_grid]
            )
        ]
    )

@callback(
    Output("login-sso-modal", "is_open"),
    [
        Input("header-signin-btn", "n_clicks"),
        Input("login-modal-close-btn", "n_clicks")
    ],
    [State("login-sso-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_login_modal(n_signin, n_close, is_open):
    if ctx.triggered_id == "header-signin-btn":
        return True
    if ctx.triggered_id == "login-modal-close-btn":
        return False
    return is_open
