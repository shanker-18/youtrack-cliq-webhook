# --- 8. Sync from Session Store on Page Load ---------------------------------
@callback(
    Output("filter-var-squad", "data", allow_duplicate=True),
    Output("selected-var-squad-label", "children", allow_duplicate=True),
    Output("menu-var-squad", "children", allow_duplicate=True),
    Output("filter-var-model", "data", allow_duplicate=True),
    Output("selected-var-model-label", "children", allow_duplicate=True),
    Output("menu-var-model", "children", allow_duplicate=True),
    Input("session-active-model-store", "data"),
    State("var-header-ad-switcher", "data"),
    State("filter-var-domain", "data"),
    prevent_initial_call=True,
)
def sync_session_to_variance(session_data, persona_key, domain):
    """Syncs squad/model selection from other pages into Variance on navigation."""
    if not session_data or not isinstance(session_data, dict):
        return (no_update,) * 6
    if session_data.get("source") == "variance":
        return (no_update,) * 6
    gbu_codes = _resolve_staging_gbu_codes(persona_key)
    session_squads = session_data.get("selected_squads", [])
    session_models = session_data.get("selected_models", [])
    if not session_squads and not session_models:
        return (no_update,) * 6
    active_squads, squad_disp, squad_items = _resolve_var_squad_selection(gbu_codes, session_squads)
    active_models, _, model_items, model_pill = _resolve_var_model_selection(
        active_squads, gbu_codes, domain, session_models
    )
    return active_squads, squad_disp, squad_items, active_models, model_pill, model_items
