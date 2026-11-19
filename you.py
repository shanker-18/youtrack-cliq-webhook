@patch("callbacks.audit_callbacks.get_model_by_id")
@patch("callbacks.audit_callbacks._load_audit_row_and_events")
def test_modal_model_name_resolved_from_model_id(mock_load, mock_get_model):
    """Verify modal audit displays dynamic model name from get_model_by_id when model_id is in context."""
    mock_load.return_value = (
        {"row_id": 101, "item": "TYLENOL EXTRA", "description": "Caplet", "is_deleted": False},
        [],
        "0.00",
    )
    mock_get_model.return_value = {"model_id": 3, "model_name": "Adult Tylenol"}
