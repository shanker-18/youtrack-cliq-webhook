def _build_variance_sync_result(session_model, session_ad, current_ad, current_squad, current_model, domain):
    """Core logic for sync_session_to_variance, extracted to reduce CC."""
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
        return None
    target_squad, target_model = _extract_sync_target_squad_and_model(
        session_model, current_squad, current_model
    )
    if trig_id != "url" and not _is_variance_sync_needed(
        current_ad, new_ad, current_squad, target_squad, current_model, target_model
    ):
        return None
    return new_ad, persona, gbu_codes, target_squad, target_model


def _assemble_variance_sync_outputs(new_ad, persona, gbu_codes, target_squad, target_model, domain):
    """Assembles the final output tuple for sync_session_to_variance."""
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
