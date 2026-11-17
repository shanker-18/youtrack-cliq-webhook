html.Button(
    [html.I(className="bi bi-arrow-counterclockwise me-1"), "Undo"],
    id="btn-undo-action",
    type="button",
    className="btn btn-sm btn-outline-secondary",
    disabled=True,
    style={"fontSize": "11px", "borderRadius": "6px", "padding": "4px 12px"},
    title="Undo last action (Ctrl+Z)",
),
