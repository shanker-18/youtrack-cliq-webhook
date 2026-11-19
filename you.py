    mock_row.return_value = {"row_id": 185, "item": "Motrin Adult", "description": "Desc", "is_deleted": False}
    mock_val.return_value = 100.0
    mock_audit.return_value = [...]@patch("callbacks.audit_callbacks._load_audit_row_and_events")
def test_modal_state_deleted_line_item(mock_load):
    """Verify soft-deleted line item renders red ROW DELETED badge and Restore button."""
    mock_load.return_value = (
        {"row_id": 101, "item": "MOTRIN IB", "description": "Tablet", "is_deleted": True},
        [{"eventType": "ROW_DELETED", "userEmail": "alex.morgan@kenvue.com", "deptName": "Marketing"}],
        "0.00",
    )
