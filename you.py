# ── 2. Save Paste Changes (with No-Comment Confirmation) ──────────────────────
def _execute_save_paste_changes(cells_preview, user_comment: str, context_data: dict):
    """Persist all changed cells from paste preview to PostgreSQL with shared audit comment."""
    domain      = context_data.get("domain", "CONSUMPTION")
    snapshot_id = context_data.get("snapshot_id")
    if not snapshot_id or not context_data.get("is_editable"):
        return False, no_update, {"message": "Cannot paste into a locked or uninitialized snapshot.", "header": "Paste Blocked"}
    dept_id     = context_data.get("dept_id", 2)
    active_user = get_current_user() or {}
    user_id     = active_user.get("user_id") or context_data.get("user_id", 1)
    shared_comment = user_comment if user_comment else ""

    text_saved = 0
    saved = 0
    errors = 0

    items_to_process = cells_preview if isinstance(cells_preview, list) else cells_preview.get("cells", [])

    for c in items_to_process:
        if c.get("is_text"):
            t_saved, t_err = _process_text_paste_item(c, domain)
            text_saved += t_saved
            errors += t_err
        else:
            n_saved, n_err = _process_numeric_paste_item(c, domain, snapshot_id, user_id, dept_id, shared_comment)
            saved += n_saved
            errors += n_err

    total_saved = text_saved + saved
    if total_saved > 0:
        invalidate_planning_cache(model_id=context_data.get("model_id"), domain=domain)

    refresh_token = {"trigger": "paste_save", "timestamp": time.time(), "saved": total_saved}
    toast = _build_paste_toast(total_saved, text_saved, saved, errors, user_comment)

    return False, refresh_token, toast


@callback(
    Output("modal-paste-preview", "is_open", allow_duplicate=True),
    Output("modal-paste-nocomment-confirm", "is_open", allow_duplicate=True),
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Input("btn-paste-save", "n_clicks"),
    Input("btn-paste-nocomment-save", "n_clicks"),
    State("paste-preview-cells-store", "data"),
    State("paste-comment-input", "value"),
    State("active-planning-context-store", "data"),
    prevent_initial_call=True,
)
def save_paste_changes(n_save, n_save_nocomment, cells_preview, comment, context_data):
    """
    Persist all changed cells from paste preview to PostgreSQL.
    If Save is clicked with an empty rationale comment, opens confirmation pop-up first.
    """
    trig_id = callback_context.triggered_id
    if trig_id == "btn-paste-nocomment-save":
        if not n_save_nocomment:
            return no_update, no_update, no_update, no_update
    elif not n_save:
        return no_update, no_update, no_update, no_update

    if not cells_preview or not context_data:
        return no_update, False, no_update, no_update

    user_comment = (comment or "").strip()
    if trig_id == "btn-paste-save" and not user_comment:
        return no_update, True, no_update, no_update

    modal_open, refresh_token, toast = _execute_save_paste_changes(
        cells_preview, user_comment, context_data
    )
    return modal_open, False, refresh_token, toast


@callback(
    Output("modal-paste-nocomment-confirm", "is_open", allow_duplicate=True),
    Input("btn-paste-nocomment-add", "n_clicks"),
    prevent_initial_call=True,
)
def handle_paste_nocomment_focus_comment(n_add):
    """Close no-comment confirmation pop-up so user can enter a comment."""
    if not n_add:
        return no_update
    return False


clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) {
            return window.dash_clientside.no_update;
        }
        setTimeout(function() {
            var el = document.getElementById("paste-comment-input");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "center" });
                el.focus();
            }
        }, 150);
        return window.dash_clientside.no_update;
    }
    """,
    Output("paste-comment-input", "id"),
    Input("btn-paste-nocomment-add", "n_clicks"),
    prevent_initial_call=True,
)


# ── 3. Cancel Paste Modal ─────────────────────────────────────────────────────
@callback(
    Output("modal-paste-preview", "is_open", allow_duplicate=True),
    Output("modal-paste-nocomment-confirm", "is_open", allow_duplicate=True),
    Input("btn-paste-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_paste_modal(n_cancel):
    """Close paste preview modal without saving."""
    if n_cancel:
        return False, False
    return no_update, no_update
