    mock_load.return_value = (
        {"row_id": 185, "item": "Motrin Adult", "description": "Desc", "is_deleted": False},
        [
            {
                "eventType": "ROW_RESTORED", "eventLabel": "Row Restored",
                "oldVal": "\u2014", "newVal": "\u2014", "deltaVal": "\u2014", "deltaType": "zero",
                "userEmail": "alex.morgan@kenvue.com", "deptName": "Finance",
            },
            {
                "eventType": "ROW_DELETED", "eventLabel": "Row Deleted",
                "oldVal": "\u2014", "newVal": "\u2014", "deltaVal": "\u2014", "deltaType": "zero",
                "userEmail": "alex.morgan@kenvue.com", "deptName": "Finance",
            },
            {
                "eventType": "VALUE_UPDATED", "eventLabel": "Value Edit",
                "oldVal": "0.00", "newVal": "100.00", "deltaVal": "+100.00 (+100.0%)", "deltaType": "pos",
                "userEmail": "alex.morgan@kenvue.com", "deptName": "Finance",
            },
        ],
        "100.00",
    )
