    for c in items_to_process:
        if c.get("is_text"):
            t_saved, t_err = _process_text_paste_item(c, domain)
            text_saved += t_saved
            errors += t_err

    from services.planning_service import batch_save_cell_edits
    ctx = {"domain": domain, "snapshot_id": snapshot_id, "user_id": user_id,
           "dept_id": dept_id, "comment": shared_comment}
    batch_result = batch_save_cell_edits(items_to_process, ctx)
    saved = batch_result["saved"]
    errors += batch_result["errors"]
