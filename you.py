# --- 7. Cross-Page Session Synchronization ------------------------------------
def _infer_var_squad_from_model(target_model: Any, gbu_codes: list) -> list[str]:
    """Infers variance squad from target model name and GBU codes."""
    t_mod = target_model[0] if isinstance(target_model, (list, tuple, set)) and target_model else target_model
    if not t_mod:
        return []
    try:
        from repositories.hierarchy_repository import get_all_models  # pylint: disable=import-outside-toplevel
        all_m = get_all_models(gbu_codes)
    except Exception as e:
        logger.warning("Could not fetch all models for GBU %s: %s", gbu_codes, e)
        return []
    matched_m = next((m for m in all_m if m["model_name"].upper() == str(t_mod).upper()), None)
    if matched_m and matched_m.get("primary_need_state"):
        return [matched_m["primary_need_state"].upper()]
    return []


def _resolve_variance_sync_squad(
    target_squad: Any, target_model: Any, gbu_codes: list, squad_list: list,
) -> Tuple[List[str], str, Any]:
    target_squad_names = []
    if isinstance(target_squad, (list, tuple, set)):
        target_squad_names = [str(s).upper() for s in target_squad if s]
    elif target_squad:
        target_squad_names = [str(target_squad).upper()]
    if not target_squad_names and target_model:
        target_squad_names = _infer_var_squad_from_model(target_model, gbu_codes)
    matched_squads = [
        s["squad_name"] for s in squad_list
        if s["squad_name"].upper() in target_squad_names
    ]
    if matched_squads:
        active_squads = matched_squads
    elif squad_list:
        active_squads = [squad_list[0]["squad_name"]]
    else:
        active_squads = []
    squad_pill_lbl = format_var_squad_pill_label(active_squads, len(squad_list))
    squad_items = build_var_squad_menu_items(squad_list, active_squad_name=active_squads)
    return active_squads, squad_pill_lbl, squad_items


def _match_var_sync_models(
    pool: list[dict], all_models: list[dict], target_model_names: list[str]
) -> tuple[list[str], list[dict]]:
    matched_models = [m["model_name"] for m in pool if m["model_name"].upper() in target_model_names]
    matched_in_all = [m["model_name"] for m in all_models if m["model_name"].upper() in target_model_names]
    if matched_models:
        return matched_models, pool
    if matched_in_all:
        return matched_in_all, all_models
    if pool:
        return [pool[0]["model_name"]], pool
    return [], pool


def _resolve_variance_sync_model(
    target_model: Any, active_squad: str | list[str], gbu_codes: list, domain: str,
) -> Tuple[List[str], str, Any]:
    dom_upper = (domain or "consumption").upper()
    flag_key = "has_shipment" if dom_upper == "SHIPMENT" else "has_pos"
    squad_list = [active_squad] if isinstance(active_squad, str) else list(active_squad or [])
    all_models = _get_models_for_squads(squad_list, gbu_codes)
    avail_models = [m for m in all_models if m.get(flag_key)]
    target_model_names = []
    if isinstance(target_model, (list, tuple, set)):
        target_model_names = [str(m).upper() for m in target_model if m]
    elif target_model:
        target_model_names = [str(target_model).upper()]
    pool = avail_models or all_models
    active_models, menu_models = _match_var_sync_models(pool, all_models, target_model_names)
    active_model_lbl = format_var_model_pill_label(active_models, len(pool))
    model_items = build_var_model_menu_items(
        menu_models, active_model_name=active_models, has_squad=bool(squad_list),
    )
    return active_models, active_model_lbl, model_items


def _resolve_sync_persona_and_gbus(session_ad: Any, current_ad: Any) -> Tuple[str, Dict[str, Any], List[str]]:
    new_ad = session_ad.get("persona_key") if session_ad and isinstance(session_ad, dict) else current_ad
    new_ad = new_ad or "COM-APP-NA-IBP-SELFCARE"
    persona = AD_PERSONAS.get(new_ad, AD_PERSONAS["COM-APP-NA-IBP-SELFCARE"])
    mapping = get_ad_group_mapping([new_ad]) if new_ad else None
    gbu_codes = mapping["gbu_codes"] if mapping and mapping.get("gbu_codes") else persona["gbus"]
    return new_ad, persona, gbu_codes


def _extract_sync_target_squad_and_model(
    session_model: Any, current_squad: Any, current_model: Any
) -> tuple[Any, Any]:
    if isinstance(session_model, dict):
        s_sqs = session_model.get("selected_squads")
        target_squads = s_sqs if s_sqs else ([session_model.get("squad_name")] if session_model.get("squad_name") else current_squad)
        s_mods = session_model.get("selected_models")
        target_models = s_mods if s_mods else ([session_model.get("model_name")] if session_model.get("model_name") else current_model)
        return target_squads, target_models
    return current_squad, current_model


def _is_session_source(session_obj: Any, src_name: str) -> bool:
    return bool(isinstance(session_obj, dict) and session_obj.get("source") == src_name)


def _is_variance_sync_needed(
    current_ad: Any, new_ad: Any, current_squad: Any, target_squads: Any,
    current_model: Any, target_models: Any,
) -> bool:
    if current_ad and new_ad and current_ad != new_ad:
        return True
    curr_sq_set = {s.upper() for s in _normalize_squad_list(current_squad)}
    target_sq_set = {s.upper() for s in _normalize_squad_list(target_squads)}
    if curr_sq_set != target_sq_set:
        return True
    curr_mod_set = {m.upper() for m in _normalize_model_list(current_model)}
    target_mod_set = {m.upper() for m in _normalize_model_list(target_models)}
    return curr_mod_set != target_mod_set


def _is_variance_sync_suppressed(
    trig_id: Any, is_model_self: bool, is_ad_self: bool, ad_changed: bool,
    session_model: Any = None, current_squad: Any = None, current_model: Any = None,
) -> bool:
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


def _update_user_ad_group_if_needed(curr_user: Any, new_ad: Any):
    if curr_user and new_ad and curr_user.get("ad_group") != new_ad:
        curr_user["ad_group"] = new_ad
        set_user_session(curr_user)


@callback(
    Output("session-active-model-store", "data", allow_duplicate=True),
    Input("filter-var-model", "data"),
    State("filter-var-squad", "data"),
    State("session-active-model-store", "data"),
    prevent_initial_call="initial_duplicate",
)
def sync_variance_initial_model_to_session(current_model, current_squad, session_data):
    """Seed session-active-model-store on initial load if empty."""
    if session_data:
        return no_update
    clean_mods = _normalize_model_list(current_model)
    clean_sqs = _normalize_squad_list(current_squad)
    if not clean_mods:
        return no_update
    return {
        "model_id": None,
        "model_name": clean_mods[0],
        "squad_name": clean_sqs[0] if clean_sqs else "",
        "selected_models": clean_mods,
        "selected_squads": clean_sqs,
        "source": "variance",
    }


@callback(
    Output("var-header-ad-switcher", "data", allow_duplicate=True),
    Output("var-header-ad-badge", "children", allow_duplicate=True),
    Output("var-header-role-badge", "children", allow_duplicate=True),
    Output("var-header-role-badge", "color", allow_duplicate=True),
    Output("var-header-user-email", "children", allow_duplicate=True),
    Output("menu-var-ad-switcher", "children", allow_duplicate=True),
    Output("filter-var-squad", "data", allow_duplicate=True),
    Output("selected-var-squad-label", "children", allow_duplicate=True),
    Output("menu-var-squad", "children", allow_duplicate=True),
    Output("filter-var-model", "data", allow_duplicate=True),
    Output("selected-var-model-label", "children", allow_duplicate=True),
    Output("menu-var-model", "children", allow_duplicate=True),
    Output("var-model-staging-store", "data", allow_duplicate=True),
    Output("var-squad-staging-store", "data", allow_duplicate=True),
    Input("url", "pathname"),
    Input("session-active-model-store", "data"),
    Input("session-active-ad-group-store", "data"),
    State("var-header-ad-switcher", "data"),
    State("filter-var-squad", "data"),
    State("filter-var-model", "data"),
    State("filter-var-domain", "data"),
    prevent_initial_call="initial_duplicate",
)
def sync_session_to_variance(pathname, session_model, session_ad, current_ad, current_squad, current_model, domain):
    """
    Synchronize model and AD group from Planning/Summary/Validation to Variance Dashboard
    whenever navigating between pages or when session stores change.
    """
    if not pathname or not pathname.startswith("/variance"):
        return (no_update,) * 14
    if not session_model and not session_ad:
        return (no_update,) * 14
    new_ad, persona, gbu_codes = _resolve_sync_persona_and_gbus(session_ad, current_ad)
    ad_changed = bool(current_ad and new_ad and current_ad != new_ad)
    is_model_self = _is_session_source(session_model, "variance")
    is_ad_self = _is_session_source(session_ad, "variance")
    try:
        trig_id = callback_context.triggered_id if callback_context.triggered else None
    except Exception:
        trig_id = None
    if _is_variance_sync_suppressed(
        trig_id, is_model_self, is_ad_self, ad_changed,
        session_model=session_model, current_squad=current_squad, current_model=current_model,
    ):
        return (no_update,) * 14
    target_squad, target_model = _extract_sync_target_squad_and_model(
        session_model, current_squad, current_model
    )
    if trig_id != "url" and not _is_variance_sync_needed(
        current_ad, new_ad, current_squad, target_squad, current_model, target_model
    ):
        return (no_update,) * 14
    ad_items = build_var_ad_switcher_menu_items(active_key=new_ad)
    squad_list = _build_squad_list_from_gbu(gbu_codes)
    active_squad, active_squad_disp, squad_items = _resolve_variance_sync_squad(
        target_squad, target_model, gbu_codes, squad_list
    )
    active_models, active_model_lbl, model_items = _resolve_variance_sync_model(
        target_model, active_squad, gbu_codes, domain
    )
    user_email_elem = _build_variance_user_identity_elem(persona["email"])
    _update_user_ad_group_if_needed(get_current_user(), new_ad)
    return (
        new_ad, persona["name"], persona["role_label"], persona["role_color"],
        user_email_elem, ad_items, active_squad, active_squad_disp, squad_items,
        active_models, active_model_lbl, model_items, None, None,
    )
