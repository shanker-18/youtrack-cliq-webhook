    def test_no_change_returns_4_tuple(self):
        c = {"old_val": "10.00", "new_val": "10.00", "period_iso": "2026-03-01", "row_id": "42"}
        result = _parse_batch_cell(c)
        assert result == (42, date(2026, 3, 1), 10.0, 10.0)
