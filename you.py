                html.Div(
                    id=action_container_id,
                    className="d-flex align-items-center gap-2",
                    children=[
                        html.Button(
                            [html.I(className="bi bi-arrow-counterclockwise me-1"), "Undo"],
                            id=f"btn-undo-year-{year_num_id}",
                            type="button",
                            className="btn-undo-action",
                            disabled=True,
                            n_clicks=0,
                            title="Undo Last Action (Ctrl + Z) — Up to 10 actions",
                        ),
                        html.Button(
                            [html.I(className="bi bi-plus-circle me-1"), "Add Row"],
                            id=btn_id,
                            type="button",
                            className="btn-add-row",
                            n_clicks=0,
                            title="Add Row (Creates synchronized row across Year 1 and Year 2)",
                        ),
                        html.Span(
                            id=f"{btn_id}-badge",
                            className="badge-locked-pill d-none",
                            style={"display": "none"},
                            children="",
                        ),
                    ],
                ),
