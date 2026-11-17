    # Store cells preview for paste undo
    undo_cells = [c for c in cells_preview if c.get("changed") and not c.get("skipped") and not c.get("is_text")] if isinstance(cells_preview, list) else []
    return modal_open, False, refresh_token, toast, undo_cells
