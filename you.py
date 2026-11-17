def _render_paste_nocomment_confirm_modal():
    """Render confirmation pop-up when user clicks Save in Paste Preview without entering a comment."""
    return dbc.Modal(
        id="modal-paste-nocomment-confirm",
        size="md",
        is_open=False,
        centered=True,
        backdrop="static",
        zIndex=1065,
        style={
            "--bs-modal-width": "580px",
            "fontFamily": "'Segoe UI', sans-serif",
        },
        children=[
            dbc.ModalHeader(
                dbc.ModalTitle(
                    html.Span(
                        [
                            html.I(
                                className="bi bi-chat-left-text-fill me-2",
                                style={"color": "var(--trust-green, #019881)"},
                            ),
                            "No Comment Entered",
                        ]
                    ),
                    className="fw-bold fs-5",
                    style={"fontFamily": "'Segoe UI', sans-serif", "color": "var(--b700, #1C1C1C)"},
                ),
                close_button=False,
                className="pb-2",
                style={"borderBottom": "1px solid var(--green-100, #B0DFD8)"},
            ),
            dbc.ModalBody(
                style={"fontFamily": "'Segoe UI', sans-serif"},
                children=[
                    html.Div(
                        className="p-3",
                        style={
                            "background": "var(--green-50, #E6F5F2)",
                            "border": "1px solid var(--green-100, #B0DFD8)",
                            "borderRadius": "6px",
                            "color": "var(--b600, #2E2E2E)",
                            "lineHeight": "1.6",
                        },
                        children=[
                            html.P(
                                "You have not entered any comment in Adjustment Rationale.",
                                className="mb-1 fw-semibold",
                                style={"fontSize": "13px", "color": "var(--b700, #1C1C1C)"},
                            ),
                            html.P(
                                "Would you like to go back and add a comment, or save the changes without a comment?",
                                className="mb-0",
                                style={"fontSize": "12px", "color": "var(--b600, #2E2E2E)"},
                            ),
                        ],
                    )
                ],
            ),
            dbc.ModalFooter(
                className="d-flex justify-content-end gap-2 pt-2 pb-2",
                style={"fontFamily": "'Segoe UI', sans-serif"},
                children=[
                    html.Button(
                        [html.I(className="bi bi-chat-text me-1"), "Comments"],
                        id="btn-paste-nocomment-add",
                        type="button",
                        className="btn-modal-cancel",
                        style={"fontFamily": "'Segoe UI', sans-serif"},
                    ),
                    html.Button(
                        [html.I(className="bi bi-check2 me-1"), "Save Without Comment"],
                        id="btn-paste-nocomment-save",
                        type="button",
                        className="btn-modal-save",
                        style={"fontFamily": "'Segoe UI', sans-serif"},
                    ),
                ],
            ),
        ],
    )
