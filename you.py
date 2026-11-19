@patch("callbacks.audit_callbacks._load_audit_row_and_events")
def test_modal_state_open_cycle_edit(mock_load):
    """Verify open cycle cell opens with enabled inputs, green pencil, and OPEN CYCLE CELL badge."""
    mock_load.return_value = (
        {"row_id": 101, "item": "MOTRIN IB", "description": "Tablet", "is_deleted": False},
        [],
        "0.00",
    )
