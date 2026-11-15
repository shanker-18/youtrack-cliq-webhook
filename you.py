def _build_action_cell(row_id: int, is_deleted: bool, is_editable: bool, is_bp: bool = False, year_index: int = 1):
    """Build the action cell with delete or restore button matching HTML prototype."""
    if is_bp or not is_editable:
        return html.Td(
            html.Button(
                html.I(className="bi bi-trash3"),
                type="button",
                className="btn-delete-row",
                disabled=True,
                tabIndex="-1",
                style={"opacity": "0.2", "cursor": "not-allowed"},
                id={"type": "btn-row-action", "row_id": row_id, "action": "delete", "year_idx": year_index},
                n_clicks=0,
                title="Delete Row (Read-Only in BP Mode)" if is_bp else "Delete Row (Read-Only)",
            ),
            className="cell-action",
        )
 
    if is_deleted:
        btn = html.Button(
            html.I(className="bi bi-arrow-counterclockwise"),
            type="button",
            className="btn-restore-row",
            tabIndex="-1",
            **{"data-row-id": str(row_id), "data-action": "restore"},
            id={"type": "btn-row-action", "row_id": row_id, "action": "restore", "year_idx": year_index},
            n_clicks=0,
            title="Restore Row",
        )
    else:
        btn = html.Button(
            html.I(className="bi bi-trash3"),
            type="button",
            className="btn-delete-row",
            tabIndex="-1",
            **{"data-row-id": str(row_id), "data-action": "delete"},
            id={"type": "btn-row-action", "row_id": row_id, "action": "delete", "year_idx": year_index},
            n_clicks=0,
            title="Delete Row",
        )
    return html.Td(btn, className="cell-action")
