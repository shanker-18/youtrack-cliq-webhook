@callback(
    Output("modal-paste-preview", "is_open", allow_duplicate=True),
    Output("modal-paste-nocomment-confirm", "is_open", allow_duplicate=True),
    Output("active-grid-rows-store", "data", allow_duplicate=True),
    Output("toast-message-store", "data", allow_duplicate=True),
    Output("paste-undo-cells-store", "data", allow_duplicate=True),
