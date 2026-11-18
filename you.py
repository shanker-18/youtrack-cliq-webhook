    return html.Div([
        html.Div([
            html.Div(
                className="spinner-border text-success",
                role="status",
                style={"width": "2.5rem", "height": "2.5rem", "marginTop": "40px"},
            ),
            html.Div(
                f"Loading {dom_label} Matrix...",
                style={"marginTop": "16px", "fontSize": "13.5px", "fontWeight": "600", "color": "var(--b600, #424242)"},
            ),
            html.Div(
                "Authoritative cycle data synchronizing from server",
                style={"marginTop": "6px", "fontSize": "12px", "color": "#888888"},
            ),
