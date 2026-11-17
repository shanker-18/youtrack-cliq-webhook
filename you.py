                            html.Button(
                                [html.I(className="bi bi-check2 me-1"), "Save Changes"],
                                id="btn-modal-save-action",
                                type="button",
                                className="btn-modal-save",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    return html.Div([audit_modal, _render_nocomment_confirm_modal()])


def render_comment_modal():
    """Render modal dialog for adding/viewing cell comments."""
    return dbc.Modal(
        id="modal-cell-comment",
        size="lg",
        is_open=False,
        centered=True,
        children=[
            dcc.Store(id="comment-target-row-id"),
            dcc.Store(id="comment-target-period"),
            dcc.Store(id="comment-target-cur-val"),
            dbc.ModalHeader(
                dbc.ModalTitle(
                    [html.I(className="bi bi-chat-left-text-fill me-2", style={"color": "#019881"}), "Cell Comment"],
                    className="fw-bold fs-5",
                ),
                close_button=True,
            ),
            dbc.ModalBody([
                html.Div(
                    className="modal-context-box p-3 mb-3 small",
                    style={"background": "#E6F5F2", "border": _BORDER_GREEN_100, "borderRadius": "6px"},
                    children=[
                        html.Div([html.Strong("Model: "), html.Span(id="comment-model-label")]),
                        html.Div([html.Strong("Line Item: "), html.Span(id="comment-row-label")]),
                        html.Div([html.Strong("Period: "), html.Span(id="comment-period-label")]),
                        html.Div([html.Strong("Current Value: "), html.Span(id="comment-curval-label", className="fw-bold")]),
                        html.Div(id="comment-status-line", className="mt-1 small"),
                    ],
                ),
                html.Label("Comment / Rationale (Optional)", className="fw-bold small mb-1", style={"color": _COLOR_GREEN_800}),
                dbc.Textarea(
                    id="comment-modal-textarea",
                    rows=3,
                    className="form-control-sm mb-3",
                    placeholder="Enter comment for this cell...",
                ),
                html.Label("Comment History", className="fw-bold small mb-1", style={"color": _COLOR_GREEN_800}),
                html.Div(
                    id="comment-history-table-container",
                    style={"maxHeight": "180px", "overflowY": "auto"},
                    className="border rounded bg-white",
                ),
            ]),
            dbc.ModalFooter([
                html.Button("Cancel", id="btn-close-comment-modal", type="button", className="btn-modal-cancel"),
                html.Button(
                    [html.I(className="bi bi-check2 me-1"), "Save"],
                    id="btn-save-comment-modal",
                    type="button",
                    className="btn-modal-save",
                ),
            ]),
        ],
    )
    
