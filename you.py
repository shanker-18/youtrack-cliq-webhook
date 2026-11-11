# pylint: disable=too-many-lines,too-many-return-statements
"""
NA IBP Planning Application — Summary Dashboard Callbacks
=========================================================
Handles all interactive callbacks for the Summary Dashboard:
- 4-Domain card toggling (Consumption, Shipment, GTS YoY, GTS CoC)
- Cascading hierarchy in native Dash HTML (Squad -> Peach Model) governed by active AD Group
- Pure HTML dropdown menu toggles via fast clientside callback (<1ms)
- Automatic, fast Snowflake and PostgreSQL data load on model selection (Zero refresh button!)
- In-memory server caching in _SUM_SNOWFLAKE_CACHE for instantaneous transitions
- Seamless two-way state persistence with Planning Workspace & Validation via session stores
- Helpful empty-state guidance when a model is not available in a toggled domain
- Pure Python implementation (zero pandas dependency)
"""
 
import os
import time
from datetime import date
from typing import Optional, Dict, Any, List, Tuple
import psycopg2
import snowflake.connector
from dash import callback, clientside_callback, Output, Input, State, callback_context, no_update, html, ALL
from dash.exceptions import MissingCallbackContextException
 
from services.summary_calculations import (
    compute_consumption_summary_matrix,
    compute_shipment_summary_matrix,
    compute_gts_summary_matrix,
    compute_gtscoc_summary_matrix,
)
from services.kv_calendar import KenvueCalendar
from services.validation_service import normalize_text
from repositories.hierarchy_repository import (
    get_squads_by_gbu,
    get_models_by_squad,
    get_model_by_id,
    get_all_models,
)
from repositories.security_repository import get_ad_group_mapping
from callbacks.filter_callbacks import AD_PERSONAS
from components.summary_grid import render_summary_matrix_table
from pages.summary import (
    build_sum_ad_switcher_menu_items,
    build_sum_squad_menu_items,
    build_sum_model_menu_items,
    format_sum_squad_pill_label,
    format_sum_model_pill_label,
    render_empty_domain_alert,
    render_empty_selection_card,
    TILE_ACTIVE_STYLE,
    TILE_INACTIVE_STYLE,
)
 
from utils.constants import GBU_PAIN_CARE
from utils.logger import get_logger
from auth.session import get_current_user, set_user_session
 
logger = get_logger(__name__)
 
_SELECT_MODEL = "Select Model"
_SELECT_SQUAD = "Select Squad"
_PREFIX_UNAVAILABLE = "UNAVAILABLE:"
 
 
def _build_summary_user_identity_elem(persona_email: str) -> list:
    """Build stacked user identity element (Name bold on top, Email underneath)."""
    user = get_current_user() or {}
    user_name = user.get("display_name", "")
    user_email = user.get("email") or persona_email
    if not user_name and user_email:
        user_name = user_email.split("@")[0].replace(".", " ").title()
    elif not user_name:
        user_name = "User"
    return [
        html.Span(user_name, className="fw-bold text-dark lh-sm", style={"fontSize": "12px"}),
        html.Span(user_email, className="text-muted lh-sm", style={"fontSize": "11px"}),
    ]
 
 
# Server-side in-memory cache for raw Summary matrix computations (30-min TTL + fiscal rollover key)
_SUM_SNOWFLAKE_CACHE: Dict[str, Dict[str, Any]] = {}
_SUM_SNOWFLAKE_CACHE_TS: Dict[str, float] = {}
_SUM_CACHE_TTL_SECONDS = 1800.0
 
 
def _get_sum_fiscal_context() -> tuple[str, str]:
    """Return (cache_fiscal_tag, live_fiscal_badge_text) derived dynamically from KenvueCalendar."""
    today_dt = date.today()
    env_year = os.getenv("IBP_PLAN_YEAR")
    try:
        d_info = KenvueCalendar.get_date_info(today_dt)
        plan_yr = int(env_year) if (env_year and env_year.isdigit()) else d_info.kv_year
        fiscal_tag = f"{plan_yr}:{d_info.kv_mo_id}"
        badge_text = f"Fiscal: {d_info.kv_month_abbr} {plan_yr}"
        return fiscal_tag, badge_text
    except Exception:
        yr_str = env_year if (env_year and env_year.isdigit()) else today_dt.strftime("%Y")
        return f"{yr_str}:{today_dt.strftime('%Y-%m')}", f"Fiscal: {today_dt.strftime('%b').upper()} {yr_str}"
 
 
def _is_sum_cache_valid(cache_key: str) -> bool:
    """Check whether cached Summary matrix entry exists and is within TTL."""
    if cache_key not in _SUM_SNOWFLAKE_CACHE:
        return False
    ts = _SUM_SNOWFLAKE_CACHE_TS.get(cache_key, 0.0)
    if (time.monotonic() - ts) > _SUM_CACHE_TTL_SECONDS:
        _SUM_SNOWFLAKE_CACHE.pop(cache_key, None)
        _SUM_SNOWFLAKE_CACHE_TS.pop(cache_key, None)
        return False
    return True
 
 
def clear_summary_cache() -> None:
    """Clears the server-side summary cache."""
    _SUM_SNOWFLAKE_CACHE.clear()
    _SUM_SNOWFLAKE_CACHE_TS.clear()
 
 
# ─── 0. Pure HTML Dropdown Menu Open/Close State Manager (Clientside) ─────────
 
clientside_callback(
    """
    function(n_ad, n_squad, n_model,
             ad_clicks, squad_clicks, model_clicks, action_clicks, squad_action_clicks,
             currentOpen) {
 
        var MENU_MAP = {
            "btn-sum-ad-group-switcher": { key: "ad",    menuId: "menu-sum-ad-switcher", baseCls: "header-dropdown-menu" },
            "pill-sum-squad":            { key: "squad", menuId: "menu-sum-squad",       baseCls: "sidebar-dropdown-menu" },
            "pill-sum-model":            { key: "model", menuId: "menu-sum-model",       baseCls: "sidebar-dropdown-menu" }
        };
 
        var ALL_MENUS = [
            { id: "menu-sum-ad-switcher", baseCls: "header-dropdown-menu", key: "ad" },
            { id: "menu-sum-squad",       baseCls: "sidebar-dropdown-menu", key: "squad" },
            { id: "menu-sum-model",       baseCls: "sidebar-dropdown-menu", key: "model" }
        ];
 
        var ctx = window.dash_clientside.callback_context;
        if (!ctx || !ctx.triggered || ctx.triggered.length === 0) {
            return window.dash_clientside.no_update;
        }
 
        var clickTrigger = ctx.triggered.find(function(t) {
            return t.value !== null && t.value !== undefined && t.value > 0;
        });
        if (!clickTrigger) {
            return window.dash_clientside.no_update;
        }
 
        var triggeredId = clickTrigger.prop_id.split(".")[0];
        var parsedId = null;
        try { parsedId = JSON.parse(triggeredId); } catch(e) {}
 
        var newOpenKey = null;
 
        if (parsedId && typeof parsedId === "object" && parsedId.type) {
            if (parsedId.type === "sum-model-select-item") {
                newOpenKey = "model";
                var mBodySel = document.getElementById("sum-model-dropdown-body");
                if (mBodySel) { window._sumModelScroll = mBodySel.scrollTop; }
            } else if (parsedId.type === "sum-model-action") {
                if (parsedId.action === "apply") {
                    newOpenKey = null;
                    window._sumModelScroll = 0;
                } else if (parsedId.action === "reset") {
                    newOpenKey = "model";
                    window._sumModelScroll = 0;
                    var mBodyRst = document.getElementById("sum-model-dropdown-body");
                    if (mBodyRst) { mBodyRst.scrollTop = 0; }
                } else {
                    newOpenKey = "model";
                    var mBodyAct = document.getElementById("sum-model-dropdown-body");
                    if (mBodyAct) { window._sumModelScroll = mBodyAct.scrollTop; }
                }
            } else if (parsedId.type === "sum-squad-select-item") {
                newOpenKey = "squad";
                var sBodySel = document.getElementById("sum-squad-dropdown-body");
                if (sBodySel) { window._sumSquadScroll = sBodySel.scrollTop; }
            } else if (parsedId.type === "sum-squad-action") {
                if (parsedId.action === "apply") {
                    newOpenKey = null;
                    window._sumSquadScroll = 0;
                } else if (parsedId.action === "reset") {
                    newOpenKey = "squad";
                    window._sumSquadScroll = 0;
                    var sBodyRst = document.getElementById("sum-squad-dropdown-body");
                    if (sBodyRst) { sBodyRst.scrollTop = 0; }
                } else {
                    newOpenKey = "squad";
                    var sBodyAct = document.getElementById("sum-squad-dropdown-body");
                    if (sBodyAct) { window._sumSquadScroll = sBodyAct.scrollTop; }
                }
            } else {
                newOpenKey = null;
            }
        } else {
            var entry = MENU_MAP[triggeredId];
            if (entry) {
                newOpenKey = (currentOpen === entry.key) ? null : entry.key;
                if (newOpenKey === "squad" && currentOpen !== "squad") {
                    window._sumSquadScroll = 0;
                    var sBodyOpen = document.getElementById("sum-squad-dropdown-body");
                    if (sBodyOpen) { sBodyOpen.scrollTop = 0; }
                }
                if (newOpenKey === "model" && currentOpen !== "model") {
                    window._sumModelScroll = 0;
                    var mBodyOpen = document.getElementById("sum-model-dropdown-body");
                    if (mBodyOpen) { mBodyOpen.scrollTop = 0; }
                }
            }
        }
 
        ALL_MENUS.forEach(function(m) {
            var el = document.getElementById(m.id);
            if (!el) return;
            var shouldShow = (newOpenKey === m.key);
            el.className = shouldShow ? m.baseCls + " show" : m.baseCls;
        });
 
        return [
            newOpenKey,
            ALL_MENUS[0].baseCls + (newOpenKey === "ad"    ? " show" : ""),
            ALL_MENUS[1].baseCls + (newOpenKey === "squad" ? " show" : ""),
            ALL_MENUS[2].baseCls + (newOpenKey === "model" ? " show" : "")
        ];
    }
    """,
    Output("sum-open-menu-store", "data"),
    Output("menu-sum-ad-switcher", "className"),
    Output("menu-sum-squad", "className"),
    Output("menu-sum-model", "className"),
    Input("btn-sum-ad-group-switcher", "n_clicks"),
    Input("pill-sum-squad", "n_clicks"),
    Input("pill-sum-model", "n_clicks"),
    Input({"type": "sum-ad-select-item", "key": ALL}, "n_clicks"),
    Input({"type": "sum-squad-select-item", "name": ALL, "disp": ALL}, "n_clicks"),
    Input({"type": "sum-model-select-item", "id": ALL, "name": ALL}, "n_clicks"),
    Input({"type": "sum-model-action", "action": ALL}, "n_clicks"),
    Input({"type": "sum-squad-action", "action": ALL}, "n_clicks"),
    State("sum-open-menu-store", "data"),
    prevent_initial_call=True,
)
 
 
def _normalize_squad_list(active_squads: str | list[str] | None) -> list[str]:
    """Extract list of valid squad names excluding DEFAULT_SQUAD_LABEL."""
    if not active_squads:
        return []
    if isinstance(active_squads, str):
        return [active_squads] if active_squads != _SELECT_SQUAD else []
    if isinstance(active_squads, (list, tuple, set)):
        return [str(s) for s in active_squads if s and str(s) != _SELECT_SQUAD]
    return []
 
 
def _normalize_model_list(models: str | list[str] | None) -> list[str]:
    """Extract list of valid model names excluding DEFAULT_MODEL_LABEL."""
    if not models:
        return []
    if isinstance(models, str):
        return [models] if models != _SELECT_MODEL else []
    if isinstance(models, (list, tuple, set)):
        return [str(m) for m in models if m and str(m) != _SELECT_MODEL]
    return []
 
 
def _pick_active_models(
    avail_models: list[dict], curr_models_list: list[str]
) -> tuple[list[str], int | None]:
    """Pick preserved or default active models and primary model ID."""
    avail_names_upper = {m["model_name"].upper(): m["model_name"] for m in avail_models if m.get("model_name")}
    preserved = [avail_names_upper[m.upper()] for m in curr_models_list if m.upper() in avail_names_upper]
    if preserved:
        matched = next((m for m in avail_models if m["model_name"].upper() == preserved[0].upper()), None)
        return preserved, matched.get("model_id") if matched else None
    if avail_models:
        return [avail_models[0]["model_name"]], avail_models[0].get("model_id")
    return [], None
 
 
def _safe_get_squads_by_gbu(gbu_codes: list) -> list:
    """Fetch squads for authorized GBU(s) safely with fallback on DB error."""
    try:
        return get_squads_by_gbu(gbu_codes)
    except Exception as e:
        logger.warning("Could not fetch squads for GBU %s: %s", gbu_codes, e)
        return []
 
 
def _get_models_for_squads(squad_names: List[str], gbu_codes: Optional[list]) -> List[Dict[str, Any]]:
    """Fetch distinct models for a list of squads, attaching squad_name to each model dict."""
    combined_models: List[Dict[str, Any]] = []
    seen_ids = set()
    for sq in squad_names:
        if not sq or sq == _SELECT_SQUAD:
            continue
        try:
            models = get_models_by_squad(sq, gbu_codes)
        except Exception as e:
            logger.warning("Could not fetch models for squad %s: %s", sq, e)
            models = []
        for m in models:
            m_id = m.get("model_id")
            if m_id not in seen_ids:
                seen_ids.add(m_id)
                m_copy = dict(m)
                m_copy["squad_name"] = sq
                combined_models.append(m_copy)
    return combined_models
 
 
def _resolve_sum_squad_selection(
    gbu_codes: list, current_squad: str | list[str] | None
) -> Tuple[List[str], str, Any]:
    squad_rows = _safe_get_squads_by_gbu(gbu_codes)
    squad_list = []
    for s in squad_rows:
        s_name = s["squad_name"]
        gbu_c = s.get("gbu_code", gbu_codes[0] if gbu_codes else "")
        gbu_n = s.get("gbu_name", gbu_c)
        squad_list.append({
            "squad_name": s_name,
            "display_name": s_name.title(),
            "gbu": gbu_c,
            "gbu_short": gbu_n.split()[0].title() if gbu_n else "",
        })
 
    target_squads = [current_squad] if isinstance(current_squad, str) else list(current_squad or [])
    clean_target = [str(s).upper() for s in target_squads if s and str(s) != _SELECT_SQUAD]
 
    matched_squads = [
        s["squad_name"] for s in squad_list
        if s["squad_name"].upper() in clean_target
    ]
    if matched_squads:
        active_squads = matched_squads
    elif squad_list:
        active_squads = [squad_list[0]["squad_name"]]
    else:
        active_squads = ["BABY CARE"]
 
    squad_pill_lbl = format_sum_squad_pill_label(active_squads, len(squad_list))
    squad_items = build_sum_squad_menu_items(squad_list, active_squad_name=active_squads)
    return active_squads, squad_pill_lbl, squad_items
 
 
def _resolve_sum_model_selection(
    active_squads: str | list[str],
    gbu_codes: list,
    domain: Optional[str],
    current_model: str | list[str] | None,
) -> Tuple[List[str], Optional[int], Any, str]:
    domain = (domain or "CONSUMPTION").upper()
    flag_key = "has_shipment" if domain in ["SHIPMENT", "GTS", "GTSCOC"] else "has_pos"
 
    squad_list = _normalize_squad_list(active_squads)
    all_models = _get_models_for_squads(squad_list, gbu_codes) if squad_list else []
    avail_models = [m for m in all_models if m.get(flag_key)] or all_models
    curr_models_list = _normalize_model_list(current_model)
 
    selected_models, primary_id = _pick_active_models(avail_models, curr_models_list)
 
    model_items = build_sum_model_menu_items(
        avail_models,
        active_model_name=selected_models,
        has_squad=bool(squad_list),
    )
    model_pill_lbl = format_sum_model_pill_label(selected_models, total_models=len(avail_models))
    return selected_models, primary_id, model_items, model_pill_lbl
 
 
# ─── 1. AD Persona Switcher in Summary Dashboard ─────────────────────────────
 
@callback(
    Output("sum-header-ad-switcher", "data"),
    Output("sum-header-ad-badge", "children"),
    Output("sum-header-role-badge", "children"),
    Output("sum-header-role-badge", "color"),
    Output("sum-header-user-email", "children"),
    Output("menu-sum-ad-switcher", "children"),
    Output("menu-sum-squad", "children", allow_duplicate=True),
    Output("selected-sum-squad-label", "children", allow_duplicate=True),
    Output("filter-sum-squad", "data", allow_duplicate=True),
    Output("menu-sum-model", "children", allow_duplicate=True),
    Output("selected-sum-model-label", "children", allow_duplicate=True),
    Output("filter-sum-model", "data", allow_duplicate=True),
    Output("session-active-ad-group-store", "data", allow_duplicate=True),
    Output("sum-model-staging-store", "data", allow_duplicate=True),
    Output("sum-squad-staging-store", "data", allow_duplicate=True),
    Output("session-active-model-store", "data", allow_duplicate=True),
    Input({"type": "sum-ad-select-item", "key": ALL}, "n_clicks"),
    State("sum-header-ad-switcher", "data"),
    State("filter-sum-domain", "data"),
    State("filter-sum-squad", "data"),
    State("filter-sum-model", "data"),
    prevent_initial_call=True,
)
def handle_sum_ad_persona_selection(n_clicks, current_key, domain, current_squad, current_model):
    """Update active AD persona in Summary Dashboard and cascade authorized squads & models."""
    trig = callback_context.triggered_id
    if not isinstance(trig, dict) or not any(n_clicks):
        return (no_update,) * 16
 
    key = trig.get("key", "COM-APP-NA-IBP-SELFCARE")
    if current_key and key == current_key:
        return (no_update,) * 16
 
    curr_user = get_current_user()
    user_groups = curr_user.get("all_ad_groups", []) if curr_user else []
    if user_groups and key not in user_groups:
        return (no_update,) * 16
 
    persona = AD_PERSONAS.get(key, AD_PERSONAS["COM-APP-NA-IBP-SELFCARE"])
    mapping = get_ad_group_mapping([key])
    gbu_codes = mapping["gbu_codes"] if mapping and mapping.get("gbu_codes") else persona["gbus"]
 
    ad_items = build_sum_ad_switcher_menu_items(active_key=key)
    active_squads, active_squad_disp, squad_items = _resolve_sum_squad_selection(gbu_codes, current_squad)
    active_models, _, model_items, active_pill_lbl = _resolve_sum_model_selection(
        active_squads, gbu_codes, domain, current_model
    )
 
    user_email_elem = _build_summary_user_identity_elem(persona["email"])
    session_ad_data = {"persona_key": key, "source": "summary"}
    curr_user = get_current_user()
    if curr_user:
        curr_user["ad_group"] = key
        set_user_session(curr_user)
 
    p_squad = active_squads[0] if active_squads else ""
    p_model = active_models[0] if active_models else ""
    session_model_data = {
        "model_id": None,
        "model_name": p_model,
        "squad_name": p_squad,
        "selected_models": active_models,
        "selected_squads": active_squads,
        "source": "summary",
    }
 
    return (
        key,
        persona["name"],
        persona["role_label"],
        persona["role_color"],
        user_email_elem,
        ad_items,
        squad_items,
        active_squad_disp,
        active_squads,
        model_items,
        active_pill_lbl,
        active_models,
        session_ad_data,
        None,
        None,
        session_model_data,
    )
 
 
# ─── 2. Multi-Squad Selection Callbacks (Staging & Apply) ─────────────────────
 
def _get_staging_squads_list(staging_store: Any, committed_squad: Any) -> List[str]:
    """Extract current active staging squads list from store or committed squad."""
    if staging_store is not None:
        if isinstance(staging_store, (list, tuple, set)):
            return [str(s) for s in staging_store if s and str(s) != _SELECT_SQUAD]
        if staging_store and str(staging_store) != _SELECT_SQUAD:
            return [str(staging_store)]
        return []
    if committed_squad:
        if isinstance(committed_squad, (list, tuple, set)):
            return [str(s) for s in committed_squad if s and str(s) != _SELECT_SQUAD]
        if str(committed_squad) != _SELECT_SQUAD:
            return [str(committed_squad)]
    return []
 
 
def _calculate_next_squad_staging(
    trig: dict,
    current_staging: list[str],
    all_squad_names: list[str],
) -> list[str] | None:
    """Compute new squad staging list based on menu action or item click."""
    action = trig.get("action")
    if action == "reset":
        return []
 
    current_staging_set = {s.upper() for s in current_staging}
    if action == "select-all":
        is_all = all_squad_names and all(name.upper() in current_staging_set for name in all_squad_names)
        return [] if is_all else list(all_squad_names)
 
    if trig.get("type") == "sum-squad-select-item":
        clicked_name = trig.get("name")
        if clicked_name:
            if clicked_name.upper() in current_staging_set:
                return [s for s in current_staging if s.upper() != clicked_name.upper()]
            return current_staging + [clicked_name]
 
    return None
 
 
def _is_staging_callback_active(select_clicks: Any, action_clicks: Any, trig: Any) -> bool:
    """Validate that the callback was triggered by a valid staging click action."""
    has_select_click = any(c for c in (select_clicks or []) if c)
    has_action_click = any(c for c in (action_clicks or []) if c)
    if not has_select_click and not has_action_click:
        return False
    if not isinstance(trig, dict) or trig.get("action") == "apply":
        return False
    return True
 
 
def _resolve_staging_gbu_codes(persona_key: Optional[str]) -> list:
    """Resolve GBU codes for active persona from DB mapping or fallback config."""
    persona = AD_PERSONAS.get(persona_key, AD_PERSONAS["COM-APP-NA-IBP-SELFCARE"])
    mapping = get_ad_group_mapping([persona_key]) if persona_key else None
    if mapping and mapping.get("gbu_codes"):
        return mapping["gbu_codes"]
    return persona["gbus"]
 
 
@callback(
    Output("sum-squad-staging-store", "data", allow_duplicate=True),
    Output("menu-sum-squad", "children", allow_duplicate=True),
    Input({"type": "sum-squad-select-item", "name": ALL, "disp": ALL}, "n_clicks"),
    Input({"type": "sum-squad-action", "action": ALL}, "n_clicks"),
    State("sum-squad-staging-store", "data"),
    State("filter-sum-squad", "data"),
    State("sum-header-ad-switcher", "data"),
    prevent_initial_call=True,
)
def handle_sum_squad_staging(select_clicks, action_clicks, staging_store, committed_squad, persona_key):
    """Handle checkbox toggling, Select All, and Reset within the multi-squad dropdown menu."""
    trig = callback_context.triggered_id
    if not _is_staging_callback_active(select_clicks, action_clicks, trig):
        return no_update, no_update
 
    gbu_codes = _resolve_staging_gbu_codes(persona_key)
    squad_rows = _safe_get_squads_by_gbu(gbu_codes)
    default_gbu = gbu_codes[0] if gbu_codes else ""
    squad_list = [
        {
            "squad_name": s["squad_name"],
            "display_name": s["squad_name"].title(),
            "gbu": s.get("gbu_code", default_gbu),
            "gbu_short": (s.get("gbu_name", "")).split()[0].title() if s.get("gbu_name") else "",
        }
        for s in squad_rows
    ]
    all_squad_names = [s["squad_name"] for s in squad_list]
 
    current_staging = _get_staging_squads_list(staging_store, committed_squad)
    new_staging = _calculate_next_squad_staging(trig, current_staging, all_squad_names)
    if new_staging is None:
        return no_update, no_update
 
    squad_items = build_sum_squad_menu_items(squad_list, active_squad_name=new_staging)
    return new_staging, squad_items
 
 
@callback(
    Output("filter-sum-squad", "data", allow_duplicate=True),
    Output("selected-sum-squad-label", "children", allow_duplicate=True),
    Output("menu-sum-squad", "children", allow_duplicate=True),
    Output("sum-squad-staging-store", "data", allow_duplicate=True),
    Output("filter-sum-model", "data", allow_duplicate=True),
    Output("selected-sum-model-label", "children", allow_duplicate=True),
    Output("menu-sum-model", "children", allow_duplicate=True),
    Output("sum-model-staging-store", "data", allow_duplicate=True),
    Output("session-active-model-store", "data", allow_duplicate=True),
    Input({"type": "sum-squad-action", "action": ALL}, "n_clicks"),
    State("sum-squad-staging-store", "data"),
    State("filter-sum-squad", "data"),
    State("filter-sum-model", "data"),
    State("sum-header-ad-switcher", "data"),
    State("filter-sum-domain", "data"),
    prevent_initial_call=True,
)
def handle_sum_squad_apply(action_clicks, staging_store, committed_squad, current_model, persona_key, domain):
    """Commit multi-squad selection, cascade to model options, and sync primary model to session store."""
    has_action_click = any(c for c in (action_clicks or []) if c)
    trig = callback_context.triggered_id
    if not isinstance(trig, dict) or trig.get("action") != "apply" or not has_action_click:
        return (no_update,) * 9
 
    gbu_codes = _resolve_staging_gbu_codes(persona_key)
    squad_rows = _safe_get_squads_by_gbu(gbu_codes)
    default_gbu = gbu_codes[0] if gbu_codes else ""
    squad_list = [
        {
            "squad_name": s["squad_name"],
            "display_name": s["squad_name"].title(),
            "gbu": s.get("gbu_code", default_gbu),
            "gbu_short": (s.get("gbu_name", "")).split()[0].title() if s.get("gbu_name") else "",
        }
        for s in squad_rows
    ]
 
    selected_squads = _get_staging_squads_list(staging_store, committed_squad)
    squad_pill_lbl = format_sum_squad_pill_label(selected_squads, total_squads=len(squad_list))
    squad_items = build_sum_squad_menu_items(squad_list, active_squad_name=selected_squads)
 
    selected_models, primary_id, model_items, model_pill_lbl = _resolve_sum_model_selection(
        selected_squads, gbu_codes, domain, current_model
    )
 
    primary_squad = selected_squads[0] if selected_squads else ""
    primary_model = selected_models[0] if selected_models else ""
    session_model_data = {
        "model_id": primary_id,
        "model_name": primary_model,
        "squad_name": primary_squad,
        "selected_models": selected_models,
        "selected_squads": selected_squads,
        "source": "summary",
    }
 
    return (
        selected_squads,
        squad_pill_lbl,
        squad_items,
        None,
        selected_models,
        model_pill_lbl,
        model_items,
        None,
        session_model_data,
    )
 
 
# ─── 3. Multi-Model Selection Callbacks (Staging & Apply) ─────────────────────
 
def _get_staging_models_list(staging_store: Any, committed_model: Any) -> List[str]:
    """Extract current active staging models list from store or committed model."""
    if staging_store is not None:
        if isinstance(staging_store, (list, tuple, set)):
            return [str(m) for m in staging_store if m and str(m) != _SELECT_MODEL]
        if staging_store and str(staging_store) != _SELECT_MODEL:
            return [str(staging_store)]
        return []
    if committed_model:
        if isinstance(committed_model, (list, tuple, set)):
            return [str(m) for m in committed_model if m and str(m) != _SELECT_MODEL]
        if str(committed_model) != _SELECT_MODEL:
            return [str(committed_model)]
    return []
 
 
def _calculate_next_model_staging(
    trig: dict,
    current_staging: list[str],
    all_avail_names: list[str],
) -> list[str] | None:
    """Compute new model staging list based on menu action or item click."""
    action = trig.get("action")
    if action == "reset":
        return []
 
    current_staging_set = {m.upper() for m in current_staging}
    if action == "select-all":
        is_all = all_avail_names and all(name.upper() in current_staging_set for name in all_avail_names)
        return [] if is_all else list(all_avail_names)
 
    if trig.get("type") == "sum-model-select-item":
        clicked_name = trig.get("name")
        if clicked_name:
            if clicked_name.upper() in current_staging_set:
                return [m for m in current_staging if m.upper() != clicked_name.upper()]
            return current_staging + [clicked_name]
 
    return None
 
 
def _resolve_available_staging_models(
    persona_key: Optional[str], domain: Optional[str], squad_name: Any
) -> list[dict]:
    """Resolve list of active models filtered by domain for staging dropdown."""
    gbu_codes = _resolve_staging_gbu_codes(persona_key)
    dom_upper = (domain or "CONSUMPTION").upper()
    flag_key = "has_shipment" if dom_upper in ["SHIPMENT", "GTS", "GTSCOC"] else "has_pos"
    squad_list = [squad_name] if isinstance(squad_name, str) else list(squad_name or [])
    all_models = _get_models_for_squads(squad_list or [GBU_PAIN_CARE], gbu_codes)
    return [m for m in all_models if m.get(flag_key)] or all_models
 
 
@callback(
    Output("sum-model-staging-store", "data", allow_duplicate=True),
    Output("menu-sum-model", "children", allow_duplicate=True),
    Output("session-active-model-store", "data", allow_duplicate=True),
    Input({"type": "sum-model-select-item", "id": ALL, "name": ALL}, "n_clicks"),
    Input({"type": "sum-model-action", "action": ALL}, "n_clicks"),
    State("sum-model-staging-store", "data"),
    State("filter-sum-model", "data"),
    State("sum-header-ad-switcher", "data"),
    State("filter-sum-domain", "data"),
    State("filter-sum-squad", "data"),
    prevent_initial_call=True,
)
def handle_sum_model_staging(select_clicks, action_clicks, staging_store, committed_model, persona_key, domain, squad_name):
    """Handle checkbox toggling, Select All, and Reset within the multi-model dropdown menu."""
    trig = callback_context.triggered_id
    if not _is_staging_callback_active(select_clicks, action_clicks, trig):
        return no_update, no_update, no_update
 
    avail_models = _resolve_available_staging_models(persona_key, domain, squad_name)
    all_avail_names = [m["model_name"] for m in avail_models if m.get("model_name")]
 
    current_staging = _get_staging_models_list(staging_store, committed_model)
    new_staging = _calculate_next_model_staging(trig, current_staging, all_avail_names)
    if new_staging is None:
        return no_update, no_update, no_update
 
    model_items = build_sum_model_menu_items(avail_models, active_model_name=new_staging)
 
    session_data = no_update
    if new_staging:
        squad_list = [squad_name] if isinstance(squad_name, str) else list(squad_name or [])
        primary_model = new_staging[0]
        primary_squad = squad_list[0] if squad_list else ""
        session_data = _build_model_apply_session_data(
            primary_model,
            primary_squad,
            avail_models,
            selected_models=new_staging,
            selected_squads=squad_list,
        )
 
    return new_staging, model_items, session_data
 
 
def _build_model_apply_session_data(
    primary_model: str,
    primary_squad: str,
    avail_models: list[dict],
    selected_models: Optional[list[str]] = None,
    selected_squads: Optional[list[str]] = None,
) -> dict:
    """Build session store payload for model sync across dashboards."""
    primary_id = None
    if primary_model:
        matched = next((m for m in avail_models if m.get("model_name", "").upper() == primary_model.upper()), None)
        if matched:
            primary_id = matched.get("model_id")
 
    s_mods = [str(m) for m in selected_models if m] if selected_models else ([primary_model] if primary_model else [])
    s_sqs = [str(s) for s in selected_squads if s] if selected_squads else ([primary_squad] if primary_squad else [])
 
    return {
        "model_id": primary_id,
        "model_name": primary_model,
        "squad_name": primary_squad,
        "selected_models": s_mods,
        "selected_squads": s_sqs,
        "source": "summary",
    }
 
 
@callback(
    Output("filter-sum-model", "data", allow_duplicate=True),
    Output("selected-sum-model-label", "children", allow_duplicate=True),
    Output("session-active-model-store", "data", allow_duplicate=True),
    Output("sum-model-staging-store", "data", allow_duplicate=True),
    Output("menu-sum-model", "children", allow_duplicate=True),
    Input({"type": "sum-model-action", "action": ALL}, "n_clicks"),
    State("sum-model-staging-store", "data"),
    State("filter-sum-model", "data"),
    State("filter-sum-squad", "data"),
    State("sum-header-ad-switcher", "data"),
    State("filter-sum-domain", "data"),
    prevent_initial_call=True,
)
def handle_sum_model_apply(action_clicks, staging_store, committed_model, squad_name, persona_key, domain):
    """Finalize multi-model selection on Apply click and synchronize primary model to session store."""
    has_action_click = any(c for c in (action_clicks or []) if c)
    trig = callback_context.triggered_id
    if not isinstance(trig, dict) or trig.get("action") != "apply" or not has_action_click:
        return (no_update,) * 5
 
    avail_models = _resolve_available_staging_models(persona_key, domain, squad_name)
    selected_models = _get_staging_models_list(staging_store, committed_model)
    pill_label = format_sum_model_pill_label(selected_models, total_models=len(avail_models))
 
    squad_list = [squad_name] if isinstance(squad_name, str) else list(squad_name or [])
    primary_model = selected_models[0] if selected_models else ""
    primary_squad = squad_list[0] if squad_list else ""
    session_model_data = _build_model_apply_session_data(
        primary_model,
        primary_squad,
        avail_models,
        selected_models=selected_models,
        selected_squads=squad_list,
    )
    model_items = build_sum_model_menu_items(avail_models, active_model_name=selected_models)
 
    return selected_models, pill_label, session_model_data, None, model_items
 
 
# ─── 4. Domain Card Toggle (Consumption vs Shipment vs GTS YoY vs GTS CoC) ───
 
def _resolve_sum_domain_trigger(n_ship: Any, n_gts: Any, n_coc: Any) -> str:
    try:
        if callback_context.triggered:
            return callback_context.triggered[0]["prop_id"].split(".")[0]
    except (IndexError, KeyError, AttributeError, MissingCallbackContextException):
        pass
    if n_coc:
        return "card-sum-gtscoc"
    if n_gts:
        return "card-sum-gts"
    if n_ship:
        return "card-sum-shipment"
    return "card-sum-consumption"
 
 
def _clean_toggle_model_input(current_model: Any) -> str | list[str]:
    """Clean current model name removing UNAVAILABLE: prefix if present."""
    if isinstance(current_model, str):
        return current_model.replace(_PREFIX_UNAVAILABLE, "") if current_model else ""
    if isinstance(current_model, (list, tuple, set)):
        return [str(m).replace(_PREFIX_UNAVAILABLE, "") for m in current_model if m]
    return ""
 
 
def _resolve_sum_toggle_model(
    clean_model: str | list[str],
    avail_models: list,
    all_models: list,
    has_squad: bool = True,
) -> Tuple[str | list[str], str, Any]:
    if isinstance(clean_model, str):
        is_model_available = any(
            m["model_name"].upper() == clean_model.upper() for m in avail_models
        )
        if is_model_available:
            new_model_data = clean_model
            new_model_label = clean_model
            model_items = build_sum_model_menu_items(
                avail_models or all_models,
                active_model_name=[clean_model],
                has_squad=has_squad,
            )
        else:
            new_model_data = f"{_PREFIX_UNAVAILABLE}{clean_model}" if clean_model else _SELECT_MODEL
            new_model_label = _SELECT_MODEL
            model_items = build_sum_model_menu_items(
                avail_models or all_models,
                active_model_name=[],
                has_squad=has_squad,
            )
        return new_model_data, new_model_label, model_items
 
    clean_list = [str(m).strip() for m in clean_model if m]
    avail_names_set = {m["model_name"].upper() for m in avail_models}
    valid_selected = [m for m in clean_list if m.upper() in avail_names_set]
 
    if valid_selected:
        new_model_data = valid_selected
        new_model_label = format_sum_model_pill_label(valid_selected, len(avail_models))
        model_items = build_sum_model_menu_items(
            avail_models or all_models,
            active_model_name=valid_selected,
            has_squad=has_squad,
        )
    elif avail_models:
        fallback = avail_models[0]["model_name"]
        new_model_data = [fallback]
        new_model_label = fallback
        model_items = build_sum_model_menu_items(
            avail_models or all_models,
            active_model_name=[fallback],
            has_squad=has_squad,
        )
    else:
        new_model_data = _SELECT_MODEL
        new_model_label = _SELECT_MODEL
        model_items = build_sum_model_menu_items(
            avail_models or all_models,
            active_model_name=[],
            has_squad=has_squad,
        )
 
    return new_model_data, new_model_label, model_items
 
 
def _resolve_domain_from_trigger(trig: str) -> Tuple[str, str]:
    """Maps card trigger ID to active domain and domain title."""
    mapping = {
        "card-sum-gtscoc": ("gtscoc", "GTS CHANGE OF CYCLE (CoC)"),
        "card-sum-gts": ("gts", "GTS YOY"),
        "card-sum-shipment": ("shipment", "SHIPMENT"),
    }
    return mapping.get(trig, ("consumption", "CONSUMPTION"))
 
 
def _resolve_domain_tile_styles(active_domain: str) -> Tuple[str, str, str, str, dict, dict, dict, dict]:
    """Generates class and style dicts for all 4 domain toggle tiles."""
    domains = ["consumption", "shipment", "gts", "gtscoc"]
    classes = [
        "val-tile-stacked active-domain" if d == active_domain else "val-tile-stacked inactive-domain"
        for d in domains
    ]
    styles = [
        TILE_ACTIVE_STYLE if d == active_domain else TILE_INACTIVE_STYLE
        for d in domains
    ]
    return (
        classes[0], classes[1], classes[2], classes[3],
        styles[0], styles[1], styles[2], styles[3]
    )
 
 
@callback(
    Output("card-sum-consumption", "className"),
    Output("card-sum-shipment", "className"),
    Output("card-sum-gts", "className"),
    Output("card-sum-gtscoc", "className"),
    Output("card-sum-consumption", "style"),
    Output("card-sum-shipment", "style"),
    Output("card-sum-gts", "style"),
    Output("card-sum-gtscoc", "style"),
    Output("filter-sum-domain", "data"),
    Output("menu-sum-model", "children", allow_duplicate=True),
    Output("selected-sum-model-label", "children", allow_duplicate=True),
    Output("filter-sum-model", "data", allow_duplicate=True),
    Output("ribbon-sum-domain-title", "children"),
    Input("card-sum-consumption", "n_clicks"),
    Input("card-sum-shipment", "n_clicks"),
    Input("card-sum-gts", "n_clicks"),
    Input("card-sum-gtscoc", "n_clicks"),
    State("filter-sum-domain", "data"),
    State("sum-header-ad-switcher", "data"),
    State("filter-sum-squad", "data"),
    State("filter-sum-model", "data"),
    prevent_initial_call=True,
)
def handle_sum_domain_toggle(n_cons, n_ship, n_gts, n_coc, current_domain, persona_key, squad_name, current_model):
    """
    Toggle between 4 domains: Consumption, Shipment, GTS YoY, and GTS CoC.
    Preserves model if supported by domain or presents empty state guidance.
    """
    _ = (n_cons, current_domain)
    trig = _resolve_sum_domain_trigger(n_ship, n_gts, n_coc)
    active_domain, domain_title = _resolve_domain_from_trigger(trig)
    c_cls, s_cls, g_cls, coc_cls, c_stl, s_stl, g_stl, coc_stl = _resolve_domain_tile_styles(active_domain)
 
    persona = AD_PERSONAS.get(persona_key, AD_PERSONAS["COM-APP-NA-IBP-SELFCARE"])
    mapping = get_ad_group_mapping([persona_key]) if persona_key else None
    gbu_codes = mapping["gbu_codes"] if mapping and mapping.get("gbu_codes") else persona["gbus"]
 
    flag_key = "has_shipment" if active_domain in ["shipment", "gts", "gtscoc"] else "has_pos"
    squad_list = [squad_name] if isinstance(squad_name, str) else list(squad_name or [])
    all_models = _get_models_for_squads(squad_list or [GBU_PAIN_CARE], gbu_codes)
    avail_models = [m for m in all_models if m.get(flag_key)]
 
    clean_model = _clean_toggle_model_input(current_model)
    has_squad = bool([s for s in squad_list if s and s != _SELECT_SQUAD])
    new_model_data, new_model_label, model_items = _resolve_sum_toggle_model(
        clean_model, avail_models, all_models, has_squad=has_squad
    )
 
    return (
        c_cls,
        s_cls,
        g_cls,
        coc_cls,
        c_stl,
        s_stl,
        g_stl,
        coc_stl,
        active_domain,
        model_items,
        new_model_label,
        new_model_data,
        domain_title,
    )
 
 
# ─── 5. Auto-Load Data & Render Matrix Table (Zero Refresh Button!) ───────────
 
def _resolve_clean_models(model: Any) -> list[str]:
    """Extract clean valid model names from model input."""
    if isinstance(model, (list, tuple, set)):
        model_list = [str(m) for m in model if m]
    elif isinstance(model, str):
        model_list = [model] if model else []
    else:
        model_list = []
 
    return [
        m for m in model_list
        if normalize_text(m) not in [_SELECT_MODEL.upper(), "ALL", "NONE", ""]
    ]
 
 
def _compute_ribbon_title(clean_models: list[str], squad_list: list[str], domain: str) -> str:
    """Determine header ribbon title for single or multi-model consolidated views."""
    if len(clean_models) == 1:
        return clean_models[0]
 
    flag_key = "has_shipment" if (domain or "").lower() in ["shipment", "gts", "gtscoc"] else "has_pos"
    try:
        all_squad_models = _get_models_for_squads(squad_list, None) if squad_list else []
        avail_models = [m for m in all_squad_models if m.get(flag_key)] or all_squad_models
        total_avail = len(avail_models)
    except (psycopg2.Error, KeyError, IndexError, ValueError):
        total_avail = 0
 
    if 0 < total_avail <= len(clean_models):
        return f"Consolidated (All {len(clean_models)} Models)"
    return f"Consolidated ({len(clean_models)} Models)"
 
 
def _compute_summary_matrix_for_domain(domain: str, clean_models: list) -> dict:
    """Dispatches matrix calculation to the appropriate domain engine."""
    dispatch = {
        "consumption": compute_consumption_summary_matrix,
        "shipment": compute_shipment_summary_matrix,
        "gts": compute_gts_summary_matrix,
        "gtscoc": compute_gtscoc_summary_matrix,
    }
    func = dispatch.get(domain, compute_consumption_summary_matrix)
    return func(clean_models)
 
 
def _resolve_summary_status_text(domain: str) -> str:
    """Returns domain unit notice."""
    notices = {
        "consumption": "POS $ are in millions.",
        "shipment": "Factory POS $ and GTS $ are in millions.",
        "gts": "GTS $ are in millions.",
        "gtscoc": "",
    }
    return notices.get(domain, "")
 
 
def _render_summary_calc_error(err: Exception) -> html.Div:
    """Renders formatted notice card on calculation or database failure."""
    return html.Div(
        html.Div([
            html.H6("Calculation / Database Connection Notice", style={"color": "#D9534F", "fontWeight": "700"}),
            html.P(str(err), style={"color": "#721c24", "fontSize": "13px"}),
        ], style={
            "textAlign": "center", "padding": "32px", "backgroundColor": "#f8d7da",
            "borderRadius": "10px", "border": "1px solid #f5c6cb"
        }),
        style={"padding": "16px"}
    )
 
 
@callback(
    Output("sum-grid-container", "children"),
    Output("sum-status-badge", "children"),
    Output("ribbon-sum-model-title", "children"),
    Output("sum-cache-store", "data"),
    Output("sum-fiscal-badge", "children"),
    Input("filter-sum-model", "data"),
    Input("filter-sum-domain", "data"),
    Input("filter-sum-squad", "data"),
    State("sum-cache-store", "data"),
    prevent_initial_call=False,
)
def handle_sum_auto_load_grid(model, domain, squad_name, cache_store):
    """
    Automatically queries Snowflake & PostgreSQL and renders the summary matrix table.
    Supports single-model and multi-model consolidated calculations across all 4 domains:
    1. Consumption Summary
    2. Shipment Summary
    3. GTS YoY Summary
    4. GTS CoC Summary
    """
    domain = (domain or "consumption").lower()
 
    if model is None or squad_name is None:
        return no_update, no_update, no_update, no_update, no_update
 
    fiscal_tag, fiscal_badge = _get_sum_fiscal_context()
 
    squad_list = _normalize_squad_list(squad_name)
    if not squad_list:
        empty_card = render_empty_selection_card("squad", domain)
        status_msg = "Please select a squad from the Squad dropdown above."
        return empty_card, status_msg, _SELECT_SQUAD, {"status": "empty_squad"}, fiscal_badge
 
    if isinstance(model, str) and model.startswith(_PREFIX_UNAVAILABLE):
        unavailable_model = model.replace(_PREFIX_UNAVAILABLE, "").strip()
        alert_card = render_empty_domain_alert(unavailable_model, domain)
        status_msg = f"No {domain.title()} records mapped for '{unavailable_model}'"
        return alert_card, status_msg, _SELECT_MODEL, {"status": "unavailable", "model": unavailable_model}, fiscal_badge
 
    clean_models = _resolve_clean_models(model)
    if not clean_models:
        empty_card = render_empty_selection_card("model", domain)
        status_msg = "Please select a model above to view summary data."
        return empty_card, status_msg, _SELECT_MODEL, {"status": "empty_model"}, fiscal_badge
 
    cache_key = f"{domain.upper()}:{fiscal_tag}:{','.join(sorted(clean_models)).upper()}"
    ribbon_title = _compute_ribbon_title(clean_models, squad_list, domain)
    model_disp = clean_models[0] if len(clean_models) == 1 else f"Consolidated ({len(clean_models)} Models)"
 
    try:
        is_cached = False
        if _is_sum_cache_valid(cache_key):
            matrix_data = _SUM_SNOWFLAKE_CACHE[cache_key]
            is_cached = True
        else:
            matrix_data = _compute_summary_matrix_for_domain(domain, clean_models)
            _SUM_SNOWFLAKE_CACHE[cache_key] = matrix_data
            _SUM_SNOWFLAKE_CACHE_TS[cache_key] = time.monotonic()
 
        grid_elem = render_summary_matrix_table(matrix_data, domain=domain.upper(), model_name=model_disp)
        status_text = _resolve_summary_status_text(domain)
        return grid_elem, status_text, ribbon_title, {"last_loaded": cache_key, "cached": is_cached}, fiscal_badge
 
    except Exception as err:
        logger.error("Error computing summary matrix for models %s in domain %s: %s", clean_models, domain, err)
        err_elem = _render_summary_calc_error(err)
        return err_elem, f"Notice: {str(err)[:60]}...", ribbon_title, {"error": str(err)[:100]}, fiscal_badge
 
 
# ─── 6. Cross-Page Session Synchronization ────────────────────────────────────
 
def _resolve_summary_sync_squad(
    target_squad: Any,
    target_model: Any,
    gbu_codes: list,
    squad_list: list,
) -> Tuple[List[str], str, Any]:
    target_squad_names = []
    if isinstance(target_squad, (list, tuple, set)):
        target_squad_names = [str(s).upper() for s in target_squad if s]
    elif target_squad:
        target_squad_names = [str(target_squad).upper()]
 
    if not target_squad_names and target_model:
        t_mod = target_model[0] if isinstance(target_model, (list, tuple, set)) and target_model else target_model
        if t_mod:
            try:
                all_m = get_all_models(gbu_codes)
            except Exception as e:
                logger.warning("Could not fetch all models for GBU %s: %s", gbu_codes, e)
                all_m = []
            matched_m = next((m for m in all_m if m["model_name"].upper() == str(t_mod).upper()), None)
            if matched_m and matched_m.get("primary_need_state"):
                target_squad_names = [matched_m["primary_need_state"].upper()]
 
    matched_squads = [
        s["squad_name"] for s in squad_list
        if s["squad_name"].upper() in target_squad_names
    ]
    if matched_squads:
        active_squads = matched_squads
    elif squad_list:
        active_squads = [squad_list[0]["squad_name"]]
    else:
        active_squads = ["BABY CARE"]
 
    squad_pill_lbl = format_sum_squad_pill_label(active_squads, len(squad_list))
    squad_items = build_sum_squad_menu_items(squad_list, active_squad_name=active_squads)
    return active_squads, squad_pill_lbl, squad_items
 
 
def _pick_sync_model_state(
    target_str: str,
    avail_models: list[dict],
    all_models: list[dict],
) -> tuple[str, str]:
    """Resolve active model identifier and display label during synchronization."""
    if target_str:
        matched = next((m for m in avail_models if m["model_name"].upper() == target_str.upper()), None)
        if matched:
            return matched["model_name"], matched["model_name"]
        if any(m["model_name"].upper() == target_str.upper() for m in all_models):
            return f"{_PREFIX_UNAVAILABLE}{target_str}", _SELECT_MODEL
 
    fallback = avail_models[0]["model_name"] if avail_models else _SELECT_MODEL
    return fallback, fallback
 
 
def _resolve_summary_sync_model(
    target_model: Any,
    active_squad: str | list[str],
    gbu_codes: list,
    domain: str,
) -> Tuple[List[str], str, Any]:
    dom_upper = (domain or "CONSUMPTION").upper()
    flag_key = "has_shipment" if dom_upper in ["SHIPMENT", "GTS", "GTSCOC"] else "has_pos"
    squad_list = [active_squad] if isinstance(active_squad, str) else list(active_squad or [])
    all_models = _get_models_for_squads(squad_list, gbu_codes)
    avail_models = [m for m in all_models if m.get(flag_key)]
 
    target_model_names = []
    if isinstance(target_model, (list, tuple, set)):
        target_model_names = [str(m).upper() for m in target_model if m]
    elif target_model:
        target_model_names = [str(target_model).upper()]
 
    pool = avail_models or all_models
    matched_models = [
        m["model_name"] for m in pool
        if m["model_name"].upper() in target_model_names
    ]
    matched_in_all = [
        m["model_name"] for m in all_models
        if m["model_name"].upper() in target_model_names
    ]
    if matched_models:
        active_models = matched_models
    elif matched_in_all:
        active_models = matched_in_all
    elif pool:
        active_models = [pool[0]["model_name"]]
    else:
        active_models = []
 
    active_model_lbl = format_sum_model_pill_label(active_models, len(pool))
    has_squad = bool([s for s in squad_list if s and s != _SELECT_SQUAD])
    model_items = build_sum_model_menu_items(
        all_models if (not matched_models and matched_in_all) else pool,
        active_model_name=active_models,
        has_squad=has_squad,
    )
    active_model_res: Any = (
        active_models[0]
        if (len(active_models) == 1 and (isinstance(target_model, str) or len(target_model_names) <= 1))
        else active_models
    )
    return active_model_res, active_model_lbl, model_items
 
 
def _resolve_sync_persona_and_gbus(session_ad: Any, current_ad: Any) -> Tuple[str, Dict[str, Any], List[str]]:
    new_ad = session_ad.get("persona_key") if session_ad and isinstance(session_ad, dict) else current_ad
    new_ad = new_ad or "COM-APP-NA-IBP-SELFCARE"
    persona = AD_PERSONAS.get(new_ad, AD_PERSONAS["COM-APP-NA-IBP-SELFCARE"])
    mapping = get_ad_group_mapping([new_ad]) if new_ad else None
    gbu_codes = mapping["gbu_codes"] if mapping and mapping.get("gbu_codes") else persona["gbus"]
    return new_ad, persona, gbu_codes
 
 
def _build_summary_squad_list(gbu_codes: List[str]) -> List[Dict[str, str]]:
    squad_rows = _safe_get_squads_by_gbu(gbu_codes)
    squad_list = []
    default_gbu = gbu_codes[0] if gbu_codes else ""
    for s in squad_rows:
        s_name = s["squad_name"]
        gbu_c = s.get("gbu_code", default_gbu)
        gbu_n = s.get("gbu_name", gbu_c)
        squad_list.append({
            "squad_name": s_name,
            "display_name": s_name.title(),
            "gbu": gbu_c,
            "gbu_short": gbu_n.split()[0].title() if gbu_n else "",
        })
    return squad_list
 
 
def _is_summary_sync_needed(
    current_ad: Any,
    new_ad: Any,
    current_squad: Any,
    target_squads: Any,
    current_model: Any,
    target_models: Any,
) -> bool:
    """Checks whether any filter on summary dashboard differs from target session state."""
    if current_ad and new_ad and current_ad != new_ad:
        return True
 
    curr_sq_set = {s.upper() for s in _normalize_squad_list(current_squad)}
    target_sq_set = {s.upper() for s in _normalize_squad_list(target_squads)}
    if curr_sq_set != target_sq_set:
        return True
 
    curr_mod_set = {m.upper() for m in _normalize_model_list(current_model)}
    target_mod_set = {m.upper() for m in _normalize_model_list(target_models)}
    if curr_mod_set != target_mod_set:
        return True
 
    return False
 
 
def _is_summary_sync_suppressed(
    trig_id: Any,
    is_model_self: bool,
    is_ad_self: bool,
    ad_changed: bool,
    session_model: Any = None,
    current_squad: Any = None,
    current_model: Any = None,
) -> bool:
    """Checks whether session sync to summary dashboard should be suppressed to avoid self-updates."""
    if ad_changed or trig_id == "url":
        return False
    if is_model_self:
        if trig_id == "session-active-model-store":
            return True
        if trig_id is None:
            if session_model and (current_squad is not None or current_model is not None):
                target_squad, target_model = _extract_sync_target_squad_and_model(
                    session_model, current_squad, current_model
                )
                curr_sq_set = {s.upper() for s in _normalize_squad_list(current_squad)}
                target_sq_set = {s.upper() for s in _normalize_squad_list(target_squad)}
                curr_mod_set = {m.upper() for m in _normalize_model_list(current_model)}
                target_mod_set = {m.upper() for m in _normalize_model_list(target_model)}
 
                return bool(curr_sq_set == target_sq_set and target_mod_set and target_mod_set.issubset(curr_mod_set))
            return True
    return bool(is_ad_self and (trig_id == "session-active-ad-group-store" or trig_id is None))
 
 
def _extract_sync_target_squad_and_model(
    session_model: Any, current_squad: Any, current_model: Any
) -> tuple[Any, Any]:
    """Extracts target squad and model from session store or current filter state."""
    if isinstance(session_model, dict):
        s_sqs = session_model.get("selected_squads")
        target_squads = s_sqs if s_sqs else ([session_model.get("squad_name")] if session_model.get("squad_name") else current_squad)
        s_mods = session_model.get("selected_models")
        target_models = s_mods if s_mods else ([session_model.get("model_name")] if session_model.get("model_name") else current_model)
        return (target_squads, target_models)
    return current_squad, current_model
 
 
def _update_user_ad_group_if_needed(curr_user: Any, new_ad: Any):
    """Updates user session store if AD group changed."""
    if curr_user and new_ad and curr_user.get("ad_group") != new_ad:
        curr_user["ad_group"] = new_ad
        set_user_session(curr_user)
 
 
def _is_session_source(session_obj: Any, src_name: str) -> bool:
    """Checks whether a session store object originated from a specific source."""
    return bool(isinstance(session_obj, dict) and session_obj.get("source") == src_name)
 
 
@callback(
    Output("session-active-model-store", "data", allow_duplicate=True),
    Input("filter-sum-model", "data"),
    State("filter-sum-squad", "data"),
    State("session-active-model-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def sync_summary_initial_model_to_session(current_model, current_squad, session_data):
    """Seed session-active-model-store on initial load if empty."""
    if session_data:
        return no_update
    clean_models = _resolve_clean_models(current_model)
    clean_squads = _normalize_squad_list(current_squad)
    if not clean_models:
        return no_update
    p_model = clean_models[0]
    p_squad = clean_squads[0] if clean_squads else ""
    return {
        "model_id": None,
        "model_name": p_model,
        "squad_name": p_squad,
        "selected_models": clean_models,
        "selected_squads": clean_squads,
        "source": "summary",
    }
 
 
@callback(
    Output("sum-header-ad-switcher", "data", allow_duplicate=True),
    Output("sum-header-ad-badge", "children", allow_duplicate=True),
    Output("sum-header-role-badge", "children", allow_duplicate=True),
    Output("sum-header-role-badge", "color", allow_duplicate=True),
    Output("sum-header-user-email", "children", allow_duplicate=True),
    Output("menu-sum-ad-switcher", "children", allow_duplicate=True),
    Output("filter-sum-squad", "data", allow_duplicate=True),
    Output("selected-sum-squad-label", "children", allow_duplicate=True),
    Output("menu-sum-squad", "children", allow_duplicate=True),
    Output("filter-sum-model", "data", allow_duplicate=True),
    Output("selected-sum-model-label", "children", allow_duplicate=True),
    Output("menu-sum-model", "children", allow_duplicate=True),
    Output("sum-model-staging-store", "data", allow_duplicate=True),
    Output("sum-squad-staging-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    Input("session-active-model-store", "data"),
    Input("session-active-ad-group-store", "data"),
    State("sum-header-ad-switcher", "data"),
    State("filter-sum-squad", "data"),
    State("filter-sum-model", "data"),
    State("filter-sum-domain", "data"),
    prevent_initial_call="initial_duplicate",
)
def sync_session_to_summary(pathname, session_model, session_ad, current_ad, current_squad, current_model, domain):
    """
    Synchronize model and AD group from Planning Workspace or Validation to Summary Dashboard
    whenever navigating between pages or when session stores change.
    """
    if not pathname or not pathname.startswith("/summary"):
        return (no_update,) * 14
 
    if not session_model and not session_ad:
        return (no_update,) * 14
 
    new_ad, persona, gbu_codes = _resolve_sync_persona_and_gbus(session_ad, current_ad)
    ad_changed = bool(current_ad and new_ad and current_ad != new_ad)
    is_model_self = _is_session_source(session_model, "summary")
    is_ad_self = _is_session_source(session_ad, "summary")
 
    try:
        trig_id = callback_context.triggered_id if callback_context.triggered else None
    except (MissingCallbackContextException, Exception):
        trig_id = None
 
    if _is_summary_sync_suppressed(
        trig_id,
        is_model_self,
        is_ad_self,
        ad_changed,
        session_model=session_model,
        current_squad=current_squad,
        current_model=current_model,
    ):
        return (no_update,) * 14
 
    target_squad, target_model = _extract_sync_target_squad_and_model(
        session_model, current_squad, current_model
    )
 
    # When navigating via url, always sync: State values may be stale (from previous
    # visit) before layout dcc.Stores reinitialize, so the equality check is unreliable.
    if trig_id != "url" and not _is_summary_sync_needed(
        current_ad, new_ad, current_squad, target_squad, current_model, target_model
    ):
        return (no_update,) * 14
 
    ad_items = build_sum_ad_switcher_menu_items(active_key=new_ad)
    squad_list = _build_summary_squad_list(gbu_codes)
 
    active_squad, active_squad_disp, squad_items = _resolve_summary_sync_squad(
        target_squad, target_model, gbu_codes, squad_list
    )
    active_model, active_model_lbl, model_items = _resolve_summary_sync_model(
        target_model, active_squad, gbu_codes, domain
    )
 
    user_email_elem = _build_summary_user_identity_elem(persona["email"])
    _update_user_ad_group_if_needed(get_current_user(), new_ad)
 
    return (
        new_ad,
        persona["name"],
        persona["role_label"],
        persona["role_color"],
        user_email_elem,
        ad_items,
        active_squad,
        active_squad_disp,
        squad_items,
        active_model,
        active_model_lbl,
        model_items,
        None,
        None,
    )
