    assert isinstance(context_data["is_editable"], bool)
    assert isinstance(context_data["is_locked"], bool)
    assert context_data["is_editable"] != context_data["is_locked"]
