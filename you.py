    if undo_type == "paste":
        if not paste_undo_cells:
            return no_update, {"message": "No paste data available to undo.", "header": "Undo Note"}
        reverted = 0
        for c in paste_undo_cells:
            try:
                old_val = round(float(str(c.get("old_val", "0")).replace(",", "")), 2)
                period_month = datetime.strptime(c["period_iso"], "%Y-%m-%d").date()
                cur_val = get_cell_current_value(domain=domain, row_id=c["row_id"], period_month=period_month)
                save_cell_edit(
                    domain=domain,
                    snapshot_id=snapshot_id,
                    row_id=int(c["row_id"]) if str(c["row_id"]).isdigit() else c["row_id"],
                    period_month=period_month,
                    old_value=cur_val,
                    new_value=old_val,
                    comment="Undo: paste reverted",
                    user_id=user_id,
                    dept_id=dept_id,
                )
                reverted += 1
            except (psycopg2.Error, ValueError, KeyError) as e:
                logger.exception("Failed to undo paste cell", extra={"context": {"error": str(e)}})
        if reverted > 0:
            invalidate_planning_cache(model_id=model_id, domain=domain)
            refresh = {"trigger": "undo_paste", "timestamp": time.time()}
            toast = {"message": f"Undo: {reverted} pasted cell(s) reverted.", "header": "Undo Applied"}
            return refresh, toast
        return no_update, {"message": "Failed to undo paste.", "header": "Error"}
