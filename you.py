# pylint: disable=missing-function-docstring,redefined-outer-name
"""
Unit tests for C2-C7 Performance Enhancement helpers.
Covers:
- C4: _extract_in_memory_current_value (paste_callbacks)
- C5: _parse_batch_cell (planning_service)
"""

from datetime import date
import pytest

from services.planning_service import _parse_batch_cell
from callbacks.paste_callbacks import _extract_in_memory_current_value


# ── C4: _extract_in_memory_current_value ─────────────────────────────────────

class TestExtractInMemoryCurrentValue:
    """Tests for in-memory cell value lookup (C4 N+1 elimination)."""

    def _make_row(self, y1_vals=None, y2_vals=None):
        return {
            "y1Vals": y1_vals or ["0.00"] * 12,
            "y2Vals": y2_vals or ["0.00"] * 12,
        }

    def test_returns_value_for_y1_month(self):
        row = self._make_row(y1_vals=["10.50", "20.00", "30.00"] + ["0.00"] * 9)
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2026, 1, 1), 2026)
        assert val == 10.50
        assert fmt == "10.50"

    def test_returns_value_for_y2_month(self):
        row = self._make_row(y2_vals=["5.00", "15.00"] + ["0.00"] * 10)
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2027, 2, 1), 2026)
        assert val == 15.00
        assert fmt == "15.00"

    def test_returns_none_for_missing_row(self):
        row_by_id = {}
        val, fmt = _extract_in_memory_current_value(row_by_id, "999", date(2026, 1, 1), 2026)
        assert val is None
        assert fmt == "0.00"

    def test_returns_none_for_out_of_range_month(self):
        row = self._make_row(y1_vals=["1.00", "2.00"])  # only 2 values
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2026, 5, 1), 2026)
        assert val is None
        assert fmt == "0.00"

    def test_handles_comma_in_value(self):
        row = self._make_row(y1_vals=["1,234.56"] + ["0.00"] * 11)
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2026, 1, 1), 2026)
        assert val == 1234.56
        assert fmt == "1234.56"

    def test_handles_empty_string_value(self):
        row = self._make_row(y1_vals=[""] + ["0.00"] * 11)
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2026, 1, 1), 2026)
        assert val == 0.0
        assert fmt == "0.00"

    def test_zero_value_returned_correctly(self):
        row = self._make_row(y1_vals=["0.00"] * 12)
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2026, 3, 1), 2026)
        assert val == 0.0
        assert fmt == "0.00"

    def test_negative_value_returned_correctly(self):
        row = self._make_row(y1_vals=["-5.50"] + ["0.00"] * 11)
        row_by_id = {"100": row}
        val, fmt = _extract_in_memory_current_value(row_by_id, "100", date(2026, 1, 1), 2026)
        assert val == -5.50
        assert fmt == "-5.50"


# ── C5: _parse_batch_cell ────────────────────────────────────────────────────

class TestParseBatchCell:
    """Tests for batch paste cell parser (C5 SonarQube refactor)."""

    def test_valid_changed_cell(self):
        c = {"old_val": "10.00", "new_val": "20.00", "period_iso": "2026-03-01", "row_id": "42"}
        result = _parse_batch_cell(c)
        assert result == (42, date(2026, 3, 1), 10.0, 20.0)

    def test_no_change_returns_empty_tuple(self):
        c = {"old_val": "10.00", "new_val": "10.00", "period_iso": "2026-03-01", "row_id": "42"}
        result = _parse_batch_cell(c)
        assert result == ()

    def test_invalid_value_returns_none(self):
        c = {"old_val": "abc", "new_val": "20.00", "period_iso": "2026-03-01", "row_id": "42"}
        result = _parse_batch_cell(c)
        assert result is None

    def test_missing_period_iso_returns_none(self):
        c = {"old_val": "10.00", "new_val": "20.00", "row_id": "42"}
        result = _parse_batch_cell(c)
        assert result is None

    def test_missing_row_id_returns_none(self):
        c = {"old_val": "10.00", "new_val": "20.00", "period_iso": "2026-03-01"}
        result = _parse_batch_cell(c)
        assert result is None

    def test_comma_in_values(self):
        c = {"old_val": "1,000.00", "new_val": "2,500.00", "period_iso": "2026-06-01", "row_id": "7"}
        result = _parse_batch_cell(c)
        assert result == (7, date(2026, 6, 1), 1000.0, 2500.0)

    def test_non_numeric_row_id_kept_as_string(self):
        c = {"old_val": "5.00", "new_val": "10.00", "period_iso": "2026-01-01", "row_id": "row-abc"}
        result = _parse_batch_cell(c)
        assert result is not None
        assert result[0] == "row-abc"

    def test_zero_old_val_defaults(self):
        c = {"new_val": "50.00", "period_iso": "2026-04-01", "row_id": "10"}
        result = _parse_batch_cell(c)
        assert result == (10, date(2026, 4, 1), 0.0, 50.0)

    def test_negative_values(self):
        c = {"old_val": "-10.00", "new_val": "-5.00", "period_iso": "2026-07-01", "row_id": "3"}
        result = _parse_batch_cell(c)
        assert result == (3, date(2026, 7, 1), -10.0, -5.0)

    def test_rounding_precision(self):
        c = {"old_val": "10.005", "new_val": "10.015", "period_iso": "2026-01-01", "row_id": "1"}
        result = _parse_batch_cell(c)
        rid, period, old_v, new_v = result
        assert old_v == 10.01
        assert new_v == 10.02

    def test_invalid_date_returns_none(self):
        c = {"old_val": "10.00", "new_val": "20.00", "period_iso": "not-a-date", "row_id": "1"}
        result = _parse_batch_cell(c)
        assert result is None
