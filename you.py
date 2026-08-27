import dash
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc
from server import server
import config
from components.header import render_global_header

app = Dash(
    __name__,
    server=server,
    use_pages=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True
)

app.title = "Kenvue Integrated Business Planning"

app.layout = html.Div([
    render_global_header(),
    html.Div(dash.page_container)
])

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
