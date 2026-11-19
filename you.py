@patch("callbacks.audit_callbacks._load_audit_row_and_events")
def test_modal_model_name_resolved_from_row_details(mock_load):
    """Verify modal audit displays dynamic model name from row_details when context model_name is generic."""
    mock_load.return_value = (
        {"row_id": 101, "item": "MOTRIN IB", "description": "Tablet", "is_deleted": False, "model_name": "Adult Motrin"},
        [],
        "0.00",
    )
