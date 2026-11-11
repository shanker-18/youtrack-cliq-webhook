"""
NA IBP Planning Application — Validation Dashboard Page
========================================================
Route: /validation
100% Pure Python Dash Implementation aligned with Planning Workspace Design System:
- Top Brand Accent Multi-Color Bar & Navigation Bar with Page Switcher (Planning <-> Validation)
- Full AD Group Switcher on Navbar controlling GBU scope & user persona
- Right Navbar Badges: GBU Scope Badge, Role Badge, User Email, and Sign Out
- Left Sidebar: Compact 140px Dock with right border aligned to navbar logo pipe
- Top Horizon Bar above Workbench: 2-pill layout ([Squad] grouped by GBU -> Peach [Model])
- Zero Refresh Button: Fast, automatic loading upon model selection
- Seamless two-way state persistence with Planning Workspace
- Resilient domain toggle (Consumption <-> Shipment) with empty-state guidance
"""

from datetime import date
from typing import Optional, Dict, List, Any, Tuple, Set
from flask import has_request_context, request
import psycopg2
import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

from auth.session import get_current_user, is_authenticated
from config import config
from services.kv_calendar import KenvueCalendar
from repositories.hierarchy_repository import get_squads_by_gbu, get_models_by_squad
from repositories.security_repository import get_ad_group_mapping
from callbacks.filter_callbacks import AD_PERSONAS
from components.header import render_workbench_header
from components.validation_grid import render_validation_matrix_table, render_validation_loading_skeleton

VALIDATION_ROUTE = "/validation"

dash.register_page(__name__, path=VALIDATION_ROUTE, title="Working Validation Dashboard — NA IBP Planning")


# ─── Button & Tile Styles ─────────────────────────────────────────────────────

_COLOR_TRUST_GREEN = "var(--trust-green, #019881)"
_FONT_SIZE_SM_11_5 = "11.5px"
DEFAULT_SQUAD_LABEL = "Select Squad"
DEFAULT_MODEL_LABEL = "Select Model"
BG_GREEN_50 = "var(--green-50, #E6F5F2)"
ICON_CHECKBOX_UNCHECKED = "bi bi-square"
ICON_CHECKBOX_CHECKED = "bi bi-check-square-fill"

TILE_BASE_STYLE = {
    "display": "flex",
    "flexDirection": "column",
    "alignItems": "center",
    "justifyContent": "center",
    "padding": "10px 4px",
    "borderRadius": "8px",
    "cursor": "pointer",
    "userSelect": "none",
    "transition": "all 0.15s ease",
    "minHeight": "62px",
    "width": "100%",
    "textAlign": "center",
    "fontFamily": "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif",
}

TILE_ACTIVE_STYLE = {
    **TILE_BASE_STYLE,
    "backgroundColor": _COLOR_TRUST_GREEN,
    "color": "#ffffff",
    "border": f"1.5px solid {_COLOR_TRUST_GREEN}",
    "boxShadow": "0 2px 8px rgba(1, 152, 129, 0.25)",
}

TILE_INACTIVE_STYLE = {
    **TILE_BASE_STYLE,
    "backgroundColor": "#ffffff",
    "color": "var(--b700, #424242)",
    "border": "1.5px solid var(--b40, #E0E0E0)",
    "boxShadow": "none",
}


# ─── Pure HTML Dropdown Menu Builders ─────────────────────────────────────────

def _render_ad_switcher_item(key: str, name: str, sub: str, is_active: bool) -> html.Div:
    """Render a single AD switcher dropdown option item."""
    cls = "header-dropdown-item active" if is_active else "header-dropdown-item"
    children = [
        html.Div([
            html.Strong(name),
            html.Br(),
            html.Small(sub, className="text-muted"),
        ])
    ]
    if is_active:
        children.append(html.I(className="bi bi-check2"))
    return html.Div(
        className=cls,
        id={"type": "val-ad-select-item", "key": key},
        n_clicks=0,
        children=children,
    )


def _build_ad_switcher_from_db(db_mappings: list, active_key: str) -> list:
    """Build switcher items from database mappings."""
    items = []
    for m in db_mappings:
        group_key = m["ad_group_name"]
        perm = m.get("permission", "EDIT")
        name = m.get("display_name") or group_key
        sub = f"Role: {perm.title()}"
        items.append(_render_ad_switcher_item(group_key, name, sub, group_key == active_key))
    return items


def _build_ad_switcher_from_personas(active_key: str) -> list:
    """Build switcher items from static AD personas fallback."""
    items = []
    for key, p in AD_PERSONAS.items():
        sub = f"{p['role_label']} ({p['gbu_label']})"
        items.append(_render_ad_switcher_item(key, p["name"], sub, key == active_key))
    return items


def build_val_ad_switcher_menu_items(active_key: str = "COM-APP-NA-IBP-SELFCARE") -> list:
    """Build pure HTML AD switcher dropdown menu items dynamically from PostgreSQL."""
    curr_user = get_current_user() or {}
    user_groups = curr_user.get("all_ad_groups", [])

    try:
        from repositories.security_repository import get_all_ad_group_mappings, get_user_ad_group_mappings
        if user_groups:
            db_mappings = get_user_ad_group_mappings(user_groups)
        else:
            db_mappings = get_all_ad_group_mappings()
    except (psycopg2.Error, KeyError, ValueError):
        db_mappings = None

    header_title = "Active AD Group" if user_groups else "Simulate AD Group"
    items = [
        html.Div(header_title, className="header-dropdown-header"),
    ]
    if db_mappings:
        items.extend(_build_ad_switcher_from_db(db_mappings, active_key))
    else:
        items.extend(_build_ad_switcher_from_personas(active_key))
    return items


def format_val_squad_pill_label(selected_squads: str | list[str], total_squads: int = 0) -> str:
    """Format user-facing squad pill text based on selected squads count."""
    if not selected_squads:
        return DEFAULT_SQUAD_LABEL
    if isinstance(selected_squads, str):
        return selected_squads.title()
    clean_squads = [str(s) for s in selected_squads if s and str(s) != DEFAULT_SQUAD_LABEL]
    if not clean_squads:
        return DEFAULT_SQUAD_LABEL
    if len(clean_squads) == 1:
        return clean_squads[0].title()
    if 0 < total_squads <= len(clean_squads):
        return f"All Squads ({total_squads})"
    return f"{len(clean_squads)} Squads Selected"


def _render_val_squad_item(s: dict, is_checked: bool) -> html.Div:
    """Render individual multi-squad dropdown item with check icon."""
    s_name = s["squad_name"]
    disp_name = s.get("display_name", s_name.title())
    check_icon = ICON_CHECKBOX_CHECKED if is_checked else ICON_CHECKBOX_UNCHECKED
    check_color = "#019881" if is_checked else "#adb5bd"

    return html.Div(
        className="sidebar-dropdown-item",
        id={"type": "val-squad-select-item", "name": s_name, "disp": disp_name},
        n_clicks=0,
        style={
            "padding": "7px 14px",
            "cursor": "pointer",
            "backgroundColor": "#F4FBF9" if is_checked else "#ffffff",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "flex-start",
            "gap": "10px",
            "transition": "background 0.15s ease",
        },
        children=[
            html.I(className=check_icon, style={"color": check_color, "fontSize": "14px"}),
            html.Span(
                disp_name,
                style={
                    "fontSize": "12.5px",
                    "color": "#1A202C" if is_checked else "#4A5568",
                    "fontWeight": "600" if is_checked else "400",
                },
            ),
        ],
    )


def _build_val_squad_header(is_all_selected: bool, selected_count: int, total_count: int) -> html.Div:
    """Build squad dropdown header with select-all toggle and selection count."""
    return html.Div(
        className="d-flex align-items-center justify-content-between px-3 py-2 border-bottom user-select-none",
        style={
            "background": BG_GREEN_50,
            "fontSize": _FONT_SIZE_SM_11_5,
            "fontWeight": "600",
            "color": "var(--green-800, #004D40)",
        },
        children=[
            html.Div(
                id={"type": "val-squad-action", "action": "select-all"},
                className="d-flex align-items-center gap-2",
                n_clicks=0,
                style={"cursor": "pointer", "color": "#019881" if is_all_selected else "#495057"},
                children=[
                    html.I(
                        className=ICON_CHECKBOX_CHECKED if is_all_selected else ICON_CHECKBOX_UNCHECKED,
                        style={"color": "#019881" if is_all_selected else "#adb5bd", "fontSize": "13px"},
                    ),
                    html.Span("Select All"),
                ],
            ),
            html.Span(f"{selected_count}/{total_count} selected", style={"color": "#6c757d", "fontSize": "11px", "fontWeight": "500"}),
        ],
    )


def _build_val_squad_footer(selected_count: int) -> html.Div:
    """Build squad dropdown footer with count, Reset, and Apply buttons."""
    return html.Div(
        className="d-flex align-items-center justify-content-between px-3 py-2 border-top bg-light",
        children=[
            html.Span(
                f"{selected_count} selected",
                id="val-squad-dropdown-count",
                style={"fontSize": _FONT_SIZE_SM_11_5, "color": "#495057", "fontWeight": "600"},
            ),
            html.Div(
                className="d-flex gap-2",
                children=[
                    html.Button(
                        "Reset",
                        id={"type": "val-squad-action", "action": "reset"},
                        className="btn btn-sm btn-outline-secondary",
                        style={"fontSize": "11px", "padding": "2px 10px", "borderRadius": "4px", "fontWeight": "500"},
                        n_clicks=0,
                    ),
                    html.Button(
                        "Apply",
                        id={"type": "val-squad-action", "action": "apply"},
                        className="btn btn-sm text-white",
                        style={
                            "fontSize": "11px",
                            "padding": "2px 16px",
                            "backgroundColor": "#019881",
                            "borderColor": "#019881",
                            "fontWeight": "600",
                            "borderRadius": "4px",
                        },
                        n_clicks=0,
                    ),
                ],
            ),
        ],
    )


def _build_gbu_squad_rows(gbus: Dict[str, list], active_set: Set[str]) -> list:
    """Render list of GBU headers and child squad items."""
    squad_rows = []
    for gbu_name, gbu_squads in gbus.items():
        squad_rows.append(
            html.Div(
                children=[
                    html.I(className="bi bi-diagram-3 me-1"),
                    gbu_name,
                ],
                className="sidebar-dropdown-header",
                style={
                    "padding": "5px 12px",
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "color": _COLOR_TRUST_GREEN,
                    "textTransform": "uppercase",
                    "background": BG_GREEN_50,
                    "letterSpacing": "0.05em",
                    "borderBottom": "1px solid var(--green-100, #B0DFD8)",
                },
            )
        )
        for s in gbu_squads:
            is_checked = s.get("squad_name", "").upper() in active_set
            squad_rows.append(_render_val_squad_item(s, is_checked))
    return squad_rows


def build_val_squad_menu_items(squads: list, active_squad_name: str | list[str] = "PAIN CARE") -> list:
    """Build pure HTML multi-squad dropdown menu items grouped by GBU sections with Select All, Checkboxes, Reset, Apply."""
    if not squads:
        return [
            html.Div("No squads available", className="p-3 text-center text-muted small")
        ]

    total_count = len(squads)
    if isinstance(active_squad_name, str):
        active_set = {active_squad_name.upper()} if active_squad_name and active_squad_name != DEFAULT_SQUAD_LABEL else set()
    elif isinstance(active_squad_name, (list, tuple, set)):
        active_set = {str(s).upper() for s in active_squad_name if s and str(s) != DEFAULT_SQUAD_LABEL}
    else:
        active_set = set()

    selected_count = sum(1 for s in squads if s.get("squad_name", "").upper() in active_set)
    is_all_selected = (selected_count == total_count) if total_count > 0 else False

    gbus: Dict[str, list] = {}
    for s in squads:
        gbu = s.get("gbu", "ALL")
        gbus.setdefault(gbu, []).append(s)

    header_elem = _build_val_squad_header(is_all_selected, selected_count, total_count)
    body_elem = html.Div(
        id="val-squad-dropdown-body",
        className="val-squad-dropdown-body",
        style={"maxHeight": "260px", "overflowY": "auto", "padding": "4px 0"},
        children=_build_gbu_squad_rows(gbus, active_set),
    )
    footer_elem = _build_val_squad_footer(selected_count)

    return [header_elem, body_elem, footer_elem]


def format_val_model_pill_label(selected_models: str | list[str], total_models: int = 0) -> str:
    """Format user-facing pill text based on selected models count."""
    if not selected_models:
        return DEFAULT_MODEL_LABEL
    if isinstance(selected_models, str):
        return selected_models
    if len(selected_models) == 1:
        return selected_models[0]
    if 0 < total_models <= len(selected_models):
        return f"All Models ({total_models})"
    return f"{len(selected_models)} Models Selected"


def _render_val_model_item(m: dict, is_checked: bool) -> html.Div:
    """Render individual multi-model dropdown item with check icon."""
    m_id = m.get("model_id") if m.get("model_id") is not None else 0
    m_name = m.get("model_name", str(m))
    check_icon = ICON_CHECKBOX_CHECKED if is_checked else ICON_CHECKBOX_UNCHECKED
    check_color = "#019881" if is_checked else "#adb5bd"

    return html.Div(
        className="sidebar-dropdown-item",
        id={"type": "val-model-select-item", "id": m_id, "name": m_name},
        n_clicks=0,
        style={
            "padding": "7px 14px",
            "cursor": "pointer",
            "backgroundColor": "#F4FBF9" if is_checked else "#ffffff",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "flex-start",
            "gap": "10px",
            "transition": "background 0.15s ease",
        },
        children=[
            html.I(className=check_icon, style={"color": check_color, "fontSize": "14px"}),
            html.Span(
                m_name,
                style={
                    "fontSize": "12.5px",
                    "color": "#1A202C" if is_checked else "#4A5568",
                    "fontWeight": "600" if is_checked else "400",
                },
            ),
        ],
    )


def _build_val_model_header(is_all_selected: bool, selected_count: int, total_count: int) -> html.Div:
    """Build model dropdown header with select-all toggle and selection count."""
    return html.Div(
        className="d-flex align-items-center justify-content-between px-3 py-2 border-bottom user-select-none",
        style={
            "background": BG_GREEN_50,
            "fontSize": _FONT_SIZE_SM_11_5,
            "fontWeight": "600",
            "color": "var(--green-800, #004D40)",
        },
        children=[
            html.Div(
                id={"type": "val-model-action", "action": "select-all"},
                className="d-flex align-items-center gap-2",
                n_clicks=0,
                style={"cursor": "pointer", "color": "#019881" if is_all_selected else "#495057"},
                children=[
                    html.I(
                        className=ICON_CHECKBOX_CHECKED if is_all_selected else ICON_CHECKBOX_UNCHECKED,
                        style={"color": "#019881" if is_all_selected else "#adb5bd", "fontSize": "13px"},
                    ),
                    html.Span("Select All"),
                ],
            ),
            html.Span(f"{selected_count}/{total_count} selected", style={"color": "#6c757d", "fontSize": "11px", "fontWeight": "500"}),
        ],
    )


def _build_val_model_footer(selected_count: int) -> html.Div:
    """Build model dropdown footer with count and Apply / Reset buttons."""
    return html.Div(
        className="d-flex align-items-center justify-content-between px-3 py-2 border-top bg-light",
        children=[
            html.Span(
                f"{selected_count} selected",
                id="val-model-dropdown-count",
                style={"fontSize": _FONT_SIZE_SM_11_5, "color": "#495057", "fontWeight": "600"},
            ),
            html.Div(
                className="d-flex gap-2",
                children=[
                    html.Button(
                        "Reset",
                        id={"type": "val-model-action", "action": "reset"},
                        className="btn btn-sm btn-outline-secondary",
                        style={"fontSize": "11px", "padding": "2px 10px", "borderRadius": "4px", "fontWeight": "500"},
                        n_clicks=0,
                    ),
                    html.Button(
                        "Apply",
                        id={"type": "val-model-action", "action": "apply"},
                        className="btn btn-sm text-white",
                        style={
                            "fontSize": "11px",
                            "padding": "2px 16px",
                            "backgroundColor": "#019881",
                            "borderColor": "#019881",
                            "fontWeight": "600",
                            "borderRadius": "4px",
                        },
                        n_clicks=0,
                    ),
                ],
            ),
        ],
    )


def _build_squad_model_rows(models: list, active_set: Set[str]) -> list:
    """Render list of squad group headers and child model items."""
    squad_groups: Dict[str, list] = {}
    for m in models:
        sq = m.get("squad_name") or m.get("primary_need_state") or "Other"
        squad_groups.setdefault(sq, []).append(m)

    has_squad_headers = len(squad_groups) > 1 or (len(squad_groups) == 1 and "Other" not in squad_groups)
    model_rows = []

    for sq_name, sq_models in squad_groups.items():
        if has_squad_headers:
            model_rows.append(
                html.Div(
                    children=[
                        html.I(className="bi bi-diagram-3 me-1"),
                        sq_name.title(),
                    ],
                    className="sidebar-dropdown-header",
                    style={
                        "padding": "5px 12px",
                        "fontSize": "10px",
                        "fontWeight": "700",
                        "color": _COLOR_TRUST_GREEN,
                        "textTransform": "uppercase",
                        "background": BG_GREEN_50,
                        "letterSpacing": "0.05em",
                        "borderBottom": "1px solid var(--green-100, #B0DFD8)",
                    },
                )
            )

        for m in sq_models:
            m_name = m.get("model_name", str(m))
            is_checked = m_name.upper() in active_set
            model_rows.append(_render_val_model_item(m, is_checked))
    return model_rows


def build_val_model_menu_items(
    models: list,
    active_model_name: str | list[str] = "Adult Motrin",
    has_squad: bool = True,
) -> list:
    """Build pure HTML multi-model dropdown menu grouped by Squad with Select All, Checkboxes, and Apply button."""
    if not models:
        empty_prompt = (
            "No models available for this domain"
            if has_squad
            else "Please select a squad first to view available models."
        )
        return [
            html.Div(
                empty_prompt,
                className="p-3 text-center text-muted small",
            )
        ]

    total_count = len(models)
    if isinstance(active_model_name, str):
        active_set = {active_model_name.upper()} if active_model_name and active_model_name != DEFAULT_MODEL_LABEL else set()
    elif isinstance(active_model_name, (list, tuple, set)):
        active_set = {str(m).upper() for m in active_model_name if m and str(m) != DEFAULT_MODEL_LABEL}
    else:
        active_set = set()

    selected_count = sum(1 for m in models if m.get("model_name", "").upper() in active_set)
    is_all_selected = (selected_count == total_count) if total_count > 0 else False

    header_elem = _build_val_model_header(is_all_selected, selected_count, total_count)
    body_elem = html.Div(
        id="val-model-dropdown-body",
        className="val-model-dropdown-body",
        style={"maxHeight": "240px", "overflowY": "auto", "padding": "4px 0"},
        children=_build_squad_model_rows(models, active_set),
    )
    footer_elem = _build_val_model_footer(selected_count)

    return [header_elem, body_elem, footer_elem]


def render_empty_domain_alert(model_name: str, domain: str) -> html.Div:
    """Render helpful alert card when a model has no records in the active domain."""
    return html.Div(
        className="p-5 bg-white rounded border text-center my-4",
        style={"boxShadow": "0 1px 3px rgba(0, 0, 0, 0.05)", "maxWidth": "720px", "margin": "40px auto"},
        children=[
            html.I(className="bi bi-exclamation-triangle text-warning fs-1 mb-3 d-block"),
            html.H5(f"No {domain.title()} Data for '{model_name}'", className="fw-bold text-dark mb-2"),
            html.P(
                [
                    f"The model '{model_name}' is not configured with {domain.title()} data in Snowflake.",
                    html.Br(),
                    "Please select an available model from the Model dropdown above.",
                ],
                className="text-muted mb-0",
                style={"fontSize": "13px"},
            ),
        ],
    )


def render_empty_selection_card(empty_type: str = "model", domain: str = "CONSUMPTION") -> html.Div:
    """Render modern empty-state card when either no squad or no model is selected."""
    domain_title = (domain or "CONSUMPTION").title()
    if empty_type == "squad":
        icon_class = "bi bi-diagram-3 text-secondary fs-1 mb-3 d-block"
        title_text = "No Squad Selected"
        desc_text = "Please select one or more squads above to view available models and validation data."
    else:
        icon_class = "bi bi-grid-3x3 text-secondary fs-1 mb-3 d-block"
        title_text = "No Model Selected"
        desc_text = f"Please select one or more models from the Model dropdown above to view {domain_title} actuals."

    return html.Div(
        className="p-5 bg-white rounded border text-center my-4",
        style={"boxShadow": "0 1px 3px rgba(0, 0, 0, 0.05)", "maxWidth": "720px", "margin": "40px auto"},
        children=[
            html.I(className=icon_class),
            html.H5(title_text, className="fw-bold text-dark mb-2"),
            html.P(
                desc_text,
                className="text-muted mb-0",
                style={"fontSize": "13px"},
            ),
        ],
    )


# ─── Page Layout ──────────────────────────────────────────────────────────────

def _handle_validation_auth_redirect() -> Optional[dcc.Location]:
    """Handle authentication check and redirection for Validation Dashboard."""
    if not has_request_context():
        return None

    if not is_authenticated():
        if config.FLASK_ENV == "development":
            from auth.routes import establish_local_dev_session  # pylint: disable=import-outside-toplevel
            establish_local_dev_session()
        else:
            target_path = VALIDATION_ROUTE
            if request.query_string:
                target_path = f"{request.path}?{request.query_string.decode('utf-8')}"
            return dcc.Location(
                href=f"/auth/login?next={target_path}",
                id="validation-auth-redirect",
                refresh=True,
            )

    curr_user = get_current_user() or {}
    if not curr_user.get("ad_group"):
        return dcc.Location(
            href="/unauthorized",
            id="validation-unauth-redirect",
            refresh=True,
        )
    return None


def _resolve_validation_user_identity(user: dict, persona: dict) -> Tuple[str, str]:
    """Extract user display name and email with persona fallback."""
    user_name = user.get("display_name", "")
    user_email = user.get("email", "")
    if not user_name and user_email:
        user_name = user_email.split("@")[0].replace(".", " ").title()
    elif not user_name:
        user_name = "User"
    if not user_email:
        user_email = persona["email"]
    return user_name, user_email


def _get_initial_gbu_codes(initial_persona_key: str, persona: dict) -> list:
    """Extract authorized GBU codes for initial validation persona."""
    try:
        mapping = get_ad_group_mapping([initial_persona_key])
        if mapping and mapping.get("gbu_codes"):
            return mapping["gbu_codes"]
    except (psycopg2.Error, KeyError, IndexError, ValueError):
        pass
    return persona.get("gbus", [])


def _get_initial_squads(gbu_codes: list) -> Tuple[list, str, str]:
    """Retrieve and format initial squad list with active defaults."""
    try:
        squad_rows = get_squads_by_gbu(gbu_codes)
    except (psycopg2.Error, KeyError, IndexError, ValueError):
        squad_rows = []

    squads = []
    fallback_gbu = gbu_codes[0] if gbu_codes else ""
    for s in squad_rows:
        s_name = s["squad_name"]
        gbu_c = s.get("gbu_code", fallback_gbu)
        gbu_n = s.get("gbu_name", gbu_c)
        squads.append({
            "squad_name": s_name,
            "display_name": s_name.title(),
            "gbu": gbu_c,
            "gbu_short": gbu_n.split()[0].title() if gbu_n else "",
        })
    active_squad_name = squads[0]["squad_name"] if squads else "BABY CARE"
    active_squad_disp = squads[0]["display_name"] if squads else "Baby Care"
    return squads, active_squad_name, active_squad_disp


def _get_initial_models(active_squad_name: str, gbu_codes: list) -> Tuple[list, str]:
    """Retrieve initial models for squad, prioritizing models with POS data."""
    try:
        all_models = get_models_by_squad(active_squad_name, gbu_codes)
    except (psycopg2.Error, KeyError, IndexError, ValueError):
        all_models = []

    cons_models = [m for m in all_models if m.get("has_pos")]
    candidate_models = cons_models or all_models
    if candidate_models:
        active_model_name = candidate_models[0]["model_name"]
    else:
        active_model_name = "Adult Motrin"
    return candidate_models, active_model_name


def _load_initial_validation_data(initial_persona_key: str, persona: dict) -> dict:
    """Load initial database metadata for squads, models, and menus."""
    gbu_codes = _get_initial_gbu_codes(initial_persona_key, persona)
    squads, active_squad_name, active_squad_disp = _get_initial_squads(gbu_codes)
    candidate_models, active_model_name = _get_initial_models(active_squad_name, gbu_codes)

    return {
        "role_label": persona["role_label"],
        "role_color": persona["role_color"],
        "active_squad_name": active_squad_name,
        "active_squad_disp": active_squad_disp,
        "active_model_name": active_model_name,
        "ad_items": build_val_ad_switcher_menu_items(active_key=initial_persona_key),
        "squad_items": build_val_squad_menu_items(squads, active_squad_name=active_squad_name),
        "model_items": build_val_model_menu_items(candidate_models, active_model_name=active_model_name),
    }


def layout():
    """Pure Python Dash layout evaluated dynamically per request."""
    redirect = _handle_validation_auth_redirect()
    if redirect is not None:
        return redirect

    user = get_current_user() or {}
    curr_kv = KenvueCalendar.get_date_info(date.today())

    initial_persona_key = user.get("ad_group") or "COM-APP-NA-IBP-SELFCARE"
    if initial_persona_key not in AD_PERSONAS:
        initial_persona_key = "COM-APP-NA-IBP-SELFCARE"
    persona = AD_PERSONAS.get(initial_persona_key, AD_PERSONAS["COM-APP-NA-IBP-SELFCARE"])

    user_name, user_email = _resolve_validation_user_identity(user, persona)
    init_data = _load_initial_validation_data(initial_persona_key, persona)

    role_label = init_data["role_label"]
    role_color = init_data["role_color"]
    active_squad_name = init_data["active_squad_name"]
    active_model_name = init_data["active_model_name"]
    ad_items = init_data["ad_items"]
    squad_items = init_data["squad_items"]
    model_items = init_data["model_items"]

    return html.Div(
        id="validation-page-root",
        className="d-flex flex-column",
        style={"minHeight": "100vh", "backgroundColor": "var(--b10, #FAFAFA)"},
        children=[
            # ── State Stores ──────────────────────────────────────────────────
            dcc.Store(id="filter-val-domain", data="CONSUMPTION"),
            dcc.Store(id="filter-val-squad", data=[active_squad_name] if active_squad_name else []),
            dcc.Store(id="val-squad-staging-store", data=None),
            dcc.Store(id="filter-val-model", data=[active_model_name] if active_model_name else []),
            dcc.Store(id="val-model-staging-store", data=None),
            dcc.Store(id="val-header-ad-switcher", data=initial_persona_key),
            dcc.Store(id="val-open-menu-store", data=None),
            dcc.Store(id="val-cache-store", data={}),

            # ── 1. Top Brand Accent Multi-Color Bar ───────────────────────────
            html.Div(className="accent"),

            # ── 2. Top Navigation Bar ─────────────────────────────────────────
            render_workbench_header(
                page="validation",
                user_name=user_name,
                user_email=user_email,
                role_label=role_label,
                role_color=role_color,
                ad_items=ad_items,
                initial_ad_badge_text=persona["name"],
            ),

            # ── 3. Main Workspace Layout (Sidebar + Workbench) ────────────────
            html.Div(
                className="app-workspace",
                children=[
                    # ── Left Compact Dock (140px Width: perfectly aligned with logo pipe) ──
                    html.Aside(
                        id="val-sidebar",
                        className="planning-sidebar",
                        style={
                            "width": "140px",
                            "minWidth": "140px",
                            "maxWidth": "140px",
                            "padding": "16px 10px 16px 14px",
                            "display": "flex",
                            "flexDirection": "column",
                            "gap": "10px",
                        },
                        children=[
                            # Section: Dashboard
                            html.Div([
                                html.Div(
                                    className="sidebar-section-title mb-2",
                                    style={"justifyContent": "center"},
                                    children=[
                                        html.Span(
                                            "DASHBOARD",
                                            style={
                                                "fontSize": "11px",
                                                "fontWeight": "700",
                                                "letterSpacing": "0.06em",
                                                "color": "var(--b700, #1C1C1C)",
                                            },
                                        ),
                                    ],
                                ),

                                # Stacked Vertical Tiles
                                dcc.Loading(
                                    id="val-domain-loading",
                                    type="dot",
                                    color="#00B097",
                                    children=html.Div(
                                        className="d-flex flex-column gap-2",
                                        children=[
                                            # Consumption Tile (Active by default)
                                            html.Div(
                                                id="card-val-consumption",
                                                className="val-tile-stacked active-domain",
                                                style=TILE_ACTIVE_STYLE,
                                                n_clicks=0,
                                                children=[
                                                    html.I(className="bi bi-cart3 fs-5 mb-1"),
                                                    html.Span("Consumption", className="val-tile-label", style={"fontWeight": "700", "fontSize": _FONT_SIZE_SM_11_5}),
                                                ],
                                            ),

                                            # Shipment Tile (Inactive by default)
                                            html.Div(
                                                id="card-val-shipment",
                                                className="val-tile-stacked inactive-domain",
                                                style=TILE_INACTIVE_STYLE,
                                                n_clicks=0,
                                                children=[
                                                    html.I(className="bi bi-truck fs-5 mb-1"),
                                                    html.Span("Shipment", className="val-tile-label", style={"fontWeight": "700", "fontSize": _FONT_SIZE_SM_11_5}),
                                                ],
                                            ),
                                        ],
                                    ),
                                ),
                            ]),
                        ],
                    ),

                    # ── Right Main Workbench Area ─────────────────────────────
                    html.Main(
                        id="val-workbench",
                        className="planning-main",
                        children=[
                            # ── 1. Top Horizon Filter Bar (Squad -> Peach Model) ──
                            html.Section(
                                className="horizon-top-bar",
                                children=[
                                    # Left Horizon Group: Cascading Hierarchy (Squad -> Peach Model)
                                    html.Div(
                                        className="horizon-left-group",
                                        children=[
                                            # Need State / Squad Box (pure HTML with GBU section headers)
                                            html.Div(
                                                className="horizon-box horizon-squad-box",
                                                id="pill-val-squad",
                                                title="Select Need State / Squad",
                                                n_clicks=0,
                                                children=[
                                                    html.Div(
                                                        className="box-label",
                                                        children=[
                                                            html.I(className="bi bi-diagram-3 me-1 text-primary"),
                                                            html.Span("Squad"),
                                                            html.Span("\u25BC", className="caret ms-1"),
                                                        ],
                                                    ),
                                                    html.Span(format_val_squad_pill_label([active_squad_name]), className="box-value", id="selected-val-squad-label"),
                                                    # Squad Menu Popup
                                                    html.Div(
                                                        className="sidebar-dropdown-menu",
                                                        id="menu-val-squad",
                                                        children=squad_items,
                                                    ),
                                                ],
                                            ),

                                            # Model Box (Peach Background matching Planning Workspace)
                                            html.Div(
                                                className="horizon-box horizon-model-box",
                                                id="pill-val-model",
                                                title=DEFAULT_MODEL_LABEL,
                                                n_clicks=0,
                                                children=[
                                                    html.Div(
                                                        className="box-label",
                                                        children=[
                                                            html.I(className="bi bi-box-seam me-1 text-danger"),
                                                            html.Span("Model"),
                                                            html.Span("\u25BC", className="caret ms-1"),
                                                        ],
                                                    ),
                                                    html.Span(format_val_model_pill_label([active_model_name]), className="box-value", id="selected-val-model-label"),
                                                    # Model Menu Popup
                                                    html.Div(
                                                        className="sidebar-dropdown-menu",
                                                        id="menu-val-model",
                                                        children=model_items,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),

                            # ── 2. Authoritative Context Ribbon ───────────────────────
                            html.Div(
                                className="planning-context-ribbon",
                                children=[
                                    html.Div(
                                        className="ribbon-left d-flex align-items-center gap-2",
                                        children=[
                                            html.Span("▶", className="ribbon-play-icon", style={"color": _COLOR_TRUST_GREEN, "fontSize": "11px"}),
                                            html.Strong(id="ribbon-val-domain-title", children="CONSUMPTION", style={"fontSize": _FONT_SIZE_SM_11_5, "letterSpacing": "0.04em"}),
                                            html.Span(" — "),
                                            html.Strong(id="ribbon-val-model-title", children=active_model_name, style={"fontSize": _FONT_SIZE_SM_11_5}),
                                            html.Span("|", className="text-muted mx-1", style={"opacity": "0.4"}),
                                            html.Span(
                                                id="val-status-badge",
                                                children="POS $, Factory POS $, and POS U are in Millions.",
                                                style={"fontSize": _FONT_SIZE_SM_11_5, "color": "#495057", "fontWeight": "500", "fontStyle": "italic"},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="ribbon-badges",
                                        children=[
                                            dbc.Badge(
                                                f"Fiscal: {curr_kv.kv_month_abbr} {curr_kv.kv_year}",
                                                id="val-fiscal-badge",
                                                color="success",
                                                className="border",
                                                style={"fontSize": "11px", "borderRadius": "20px", "padding": "4px 12px", "backgroundColor": _COLOR_TRUST_GREEN},
                                            ),
                                        ],
                                    ),
                                ],
                            ),

                            # ── 3. Main Data Workbench Table Container ────────────────
                            dcc.Loading(
                                id="val-loading",
                                type="circle",
                                color="#00B097",
                                delay_show=0,
                                delay_hide=150,
                                overlay_style={"visibility": "visible", "opacity": 0.65, "backgroundColor": "rgba(255, 255, 255, 0.7)"},
                                children=html.Div(
                                    id="val-grid-container",
                                    children=render_validation_loading_skeleton("CONSUMPTION"),
                                ),
                            ),
                        ],
                    ),
                ],
            ),

            # ── 4. Global Footer (matching Planning Workspace footer.global-footer) ──
            html.Footer(
                className="global-footer",
                children=[
                    html.Div(
                        className="footer-left",
                        children=[
                            html.Span(
                                id="val-footer-status-indicator",
                                className="footer-status-indicator",
                                children=[
                                    html.Span(id="val-footer-status-dot", className="status-dot status-dot-online"),
                                    html.Span(id="val-footer-status-text", children="System Online"),
                                ],
                            ),
                            html.Span("|", className="footer-pipe text-muted", style={"opacity": "0.35", "margin": "0 8px"}),
                            html.Span(id="val-footer-db-status", children="Validation Diagnostics Active", className="text-muted"),
                        ],
                    ),
                    html.Div(
                        className="footer-right d-flex align-items-center",
                        children=[
                            html.Span(f"© {date.today().year} Kenvue Inc.", className="text-muted small"),
                            html.Span("|", className="footer-pipe text-muted", style={"opacity": "0.35", "margin": "0 8px"}),
                            html.Span("NA IBP Validation Dashboard v3.6", className="text-muted small"),
                        ],
                    ),
                ],
            ),
        ],
    )
