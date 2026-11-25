# pylint: disable=missing-function-docstring,redefined-outer-name
"""
Unit tests for Variance Dashboard components.
Covers:
- variance_grid: fmt_variance_number, get_variance_heatmap_style
- variance_calculations: calc_variance_totals, calculate_driver_heatmap_ranges
- variance_service: parse_month_num, _compute_driver_variance_monthly, _matches_consumption_driver_name
"""
import math
from datetime import date
import pytest
from components.variance_grid import (
    fmt_variance_number,
    get_variance_heatmap_style,
    _get_positive_heatmap,
    _get_negative_heatmap,
)
from services.variance_calculations import (
    calc_variance_totals,
    calculate_driver_heatmap_ranges,
    _round_driver_values,
    _sum_parent_drivers,
)
from services.variance_service import (
    parse_month_num,
    _compute_driver_variance_monthly,
    _compute_compound_driver,
    _matches_consumption_driver_name,
)


# -- fmt_variance_number -------------------------------------------------------
class TestFmtVarianceNumber:
    """Tests for variance number formatting."""

    def test_none_returns_blank(self):
        assert fmt_variance_number(None) == ""

    def test_nan_returns_blank(self):
        assert fmt_variance_number(float("nan")) == ""

    def test_inf_returns_blank(self):
        assert fmt_variance_number(float("inf")) == ""

    def test_zero_returns_blank(self):
        assert fmt_variance_number(0.0) == ""

    def test_tiny_value_shows_zero(self):
        assert fmt_variance_number(0.001) == "0.00"

    def test_very_tiny_value_shows_zero(self):
        assert fmt_variance_number(0.00004) == "0.00"

    def test_positive_value(self):
        assert fmt_variance_number(1.23) == "1.23"

    def test_negative_driver_parentheses(self):
        assert fmt_variance_number(-0.14, is_driver=True) == "(0.14)"

    def test_negative_non_driver_minus(self):
        assert fmt_variance_number(-0.14, is_driver=False) == "-0.14"

    def test_large_positive(self):
        assert fmt_variance_number(123.456) == "123.46"

    def test_large_negative_driver(self):
        assert fmt_variance_number(-99.999, is_driver=True) == "(100.00)"

    def test_custom_decimals(self):
        assert fmt_variance_number(1.5, decimals=0) == "2"

    def test_negative_zero_returns_blank(self):
        assert fmt_variance_number(-0.0) == ""


# -- get_variance_heatmap_style ------------------------------------------------
class TestVarianceHeatmapStyle:
    """Tests for heatmap color styling."""

    def test_none_transparent(self):
        bg, _, _ = get_variance_heatmap_style(None, 1.0, 1.0)
        assert bg == "transparent"

    def test_nan_transparent(self):
        bg, _, _ = get_variance_heatmap_style(float("nan"), 1.0, 1.0)
        assert bg == "transparent"

    def test_near_zero_transparent(self):
        bg, _, _ = get_variance_heatmap_style(0.00001, 1.0, 1.0)
        assert bg == "transparent"

    def test_positive_returns_green(self):
        bg, _, _ = get_variance_heatmap_style(0.9, 1.0, 1.0)
        assert bg.startswith("#0")

    def test_negative_returns_red(self):
        bg, _, _ = get_variance_heatmap_style(-0.9, 1.0, 1.0)
        assert bg.startswith("#")
        assert "C" in bg or "E" in bg or "F" in bg


# -- _get_positive_heatmap / _get_negative_heatmap -----------------------------
class TestHeatmapBands:
    """Tests for positive and negative heatmap band functions."""

    def test_positive_high_norm(self):
        bg, color, weight = _get_positive_heatmap(0.9)
        assert color == "#FFFFFF"
        assert weight == "bold"

    def test_positive_low_norm(self):
        bg, color, weight = _get_positive_heatmap(0.1)
        assert weight == "normal"

    def test_negative_high_norm(self):
        bg, color, weight = _get_negative_heatmap(0.9)
        assert color == "#FFFFFF"
        assert weight == "bold"

    def test_negative_low_norm(self):
        bg, color, weight = _get_negative_heatmap(0.1)
        assert weight == "normal"


# -- calc_variance_totals ------------------------------------------------------
class TestCalcVarianceTotals:
    """Tests for quarterly and annual total calculations."""

    def test_all_none_returns_none(self):
        result = calc_variance_totals([None] * 12)
        assert all(v is None for v in result.values())

    def test_q1_sum(self):
        vals = [1.0, 2.0, 3.0] + [None] * 9
        result = calc_variance_totals(vals)
        assert result["Q1"] == pytest.approx(6.0)

    def test_q2_sum(self):
        vals = [None] * 3 + [4.0, 5.0, 6.0] + [None] * 6
        result = calc_variance_totals(vals)
        assert result["Q2"] == pytest.approx(15.0)

    def test_fy_sum(self):
        vals = [1.0] * 12
        result = calc_variance_totals(vals)
        assert result["FY"] == pytest.approx(12.0)

    def test_ytd_with_cutoff(self):
        vals = [1.0] * 12
        result = calc_variance_totals(vals, cutoff_month=6)
        assert result["YTD"] == pytest.approx(6.0)
        assert result["YTG"] == pytest.approx(6.0)

    def test_ytd_zero_cutoff(self):
        vals = [1.0] * 12
        result = calc_variance_totals(vals, cutoff_month=0)
        assert result["YTD"] is None
        assert result["YTG"] == pytest.approx(12.0)

    def test_mixed_none_and_values(self):
        vals = [1.0, None, 2.0] + [None] * 9
        result = calc_variance_totals(vals)
        assert result["Q1"] == pytest.approx(3.0)


# -- calculate_driver_heatmap_ranges -------------------------------------------
class TestDriverHeatmapRanges:
    """Tests for heatmap range calculation."""

    def test_empty_drivers(self):
        max_pos, max_neg = calculate_driver_heatmap_ranges({})
        assert max_pos == 1.0
        assert max_neg == 1.0

    def test_positive_only(self):
        drivers = {"Base Trend": [1.0, 2.0, 3.0] + [None] * 9}
        max_pos, max_neg = calculate_driver_heatmap_ranges(drivers)
        assert max_pos == 3.0
        assert max_neg == 1.0

    def test_negative_only(self):
        drivers = {"Base Trend": [-5.0, -2.0] + [None] * 10}
        max_pos, max_neg = calculate_driver_heatmap_ranges(drivers)
        assert max_pos == 1.0
        assert max_neg == 5.0

    def test_mixed_values(self):
        drivers = {"d1": [10.0, -3.0] + [None] * 10}
        max_pos, max_neg = calculate_driver_heatmap_ranges(drivers)
        assert max_pos == 10.0
        assert max_neg == 3.0

    def test_includes_totals(self):
        drivers = {"d1": [1.0] + [None] * 11}
        totals = {"d1": {"Q1": 5.0, "FY": -8.0}}
        max_pos, max_neg = calculate_driver_heatmap_ranges(drivers, totals)
        assert max_pos == 5.0
        assert max_neg == 8.0


# -- _round_driver_values ------------------------------------------------------
class TestRoundDriverValues:
    """Tests for in-place driver rounding."""

    def test_rounds_values(self):
        drivers = {"d1": [1.123456789012, None, 0.0]}
        _round_driver_values(drivers)
        assert drivers["d1"][0] == pytest.approx(1.123456789, abs=1e-10)
        assert drivers["d1"][1] is None
        assert drivers["d1"][2] == pytest.approx(0.0)

    def test_nan_becomes_none(self):
        drivers = {"d1": [float("nan")]}
        _round_driver_values(drivers)
        assert drivers["d1"][0] is None


# -- _sum_parent_drivers -------------------------------------------------------
class TestSumParentDrivers:
    """Tests for parent driver summation."""

    def test_basic_sum(self):
        drivers = {"A": [1.0, 2.0] + [None] * 10, "B": [3.0, None] + [None] * 10}
        result = _sum_parent_drivers(drivers, ["A", "B"])
        assert result[0] == pytest.approx(4.0)
        assert result[1] == pytest.approx(2.0)

    def test_all_none(self):
        drivers = {"A": [None] * 12}
        result = _sum_parent_drivers(drivers, ["A"])
        assert all(v is None for v in result)

    def test_missing_driver_ignored(self):
        drivers = {"A": [1.0] + [None] * 11}
        result = _sum_parent_drivers(drivers, ["A", "Missing"])
        assert result[0] == pytest.approx(1.0)


# -- parse_month_num -----------------------------------------------------------
class TestParseMonthNum:
    """Tests for month number parsing."""

    def test_none(self):
        assert parse_month_num(None) is None

    def test_date_object(self):
        assert parse_month_num(date(2026, 3, 15)) == 3

    def test_digit_string(self):
        assert parse_month_num("7") == 7

    def test_month_name(self):
        assert parse_month_num("JANUARY") == 1

    def test_month_abbr(self):
        assert parse_month_num("MAR") == 3

    def test_iso_format(self):
        assert parse_month_num("2026-11-01") == 11

    def test_out_of_range(self):
        assert parse_month_num("13") is None

    def test_invalid_string(self):
        assert parse_month_num("INVALID") is None


# -- _compute_driver_variance_monthly ------------------------------------------
class TestComputeDriverVarianceMonthly:
    """Tests for monthly variance computation."""

    def test_both_empty(self):
        result = _compute_driver_variance_monthly({}, {})
        assert result == [None] * 12

    def test_current_only(self):
        result = _compute_driver_variance_monthly({1: 5.0}, {})
        assert result[0] == pytest.approx(5.0)
        assert result[1] is None

    def test_base_only(self):
        result = _compute_driver_variance_monthly({}, {1: 3.0})
        assert result[0] == pytest.approx(-3.0)

    def test_both_present(self):
        result = _compute_driver_variance_monthly({1: 10.0}, {1: 4.0})
        assert result[0] == pytest.approx(6.0)

    def test_both_zero_returns_none(self):
        result = _compute_driver_variance_monthly({1: 0.0}, {1: 0.0})
        assert result[0] is None

    def test_equal_values_returns_zero(self):
        result = _compute_driver_variance_monthly({1: 5.0}, {1: 5.0})
        assert result[0] == pytest.approx(0.0)


# -- _compute_compound_driver --------------------------------------------------
class TestComputeCompoundDriver:
    """Tests for compound driver summation."""

    def test_both_none(self):
        result = _compute_compound_driver([None] * 12, [None] * 12)
        assert result == [None] * 12

    def test_one_none(self):
        v1 = [1.0] + [None] * 11
        v2 = [None] * 12
        result = _compute_compound_driver(v1, v2)
        assert result[0] == pytest.approx(1.0)

    def test_both_present(self):
        v1 = [2.0] + [None] * 11
        v2 = [3.0] + [None] * 11
        result = _compute_compound_driver(v1, v2)
        assert result[0] == pytest.approx(5.0)

    def test_negative_values(self):
        v1 = [1.0] + [None] * 11
        v2 = [-3.0] + [None] * 11
        result = _compute_compound_driver(v1, v2)
        assert result[0] == pytest.approx(-2.0)


# -- _matches_consumption_driver_name ------------------------------------------
class TestMatchesConsumptionDriverName:
    """Tests for consumption driver name matching."""

    def test_base_trend(self):
        assert _matches_consumption_driver_name("BASE TREND", "BASE TREND") is True

    def test_season(self):
        assert _matches_consumption_driver_name("SEASON", "SEASON") is True

    def test_innovation_excludes_net(self):
        assert _matches_consumption_driver_name("NET INNOVATION", "INNOVATION") is False

    def test_innovation_excludes_cannibalization(self):
        assert _matches_consumption_driver_name("CANNIBALIZATION", "INNOVATION") is False

    def test_innovation_matches(self):
        assert _matches_consumption_driver_name("INNOVATION", "INNOVATION") is True

    def test_price_excludes_elasticity(self):
        assert _matches_consumption_driver_name("ELASTICITY", "PRICE") is False

    def test_price_matches(self):
        assert _matches_consumption_driver_name("PRICE", "PRICE") is True

    def test_other_excludes_overlay(self):
        assert _matches_consumption_driver_name("OVERLAY OTHER", "OTHER") is False

    def test_other_matches(self):
        assert _matches_consumption_driver_name("OTHER", "OTHER") is True

    def test_competition(self):
        assert _matches_consumption_driver_name("COMPETITION DRIVER", "COMPETITION") is True

    def test_no_match(self):
        assert _matches_consumption_driver_name("RANDOM TEXT", "CLUB") is False
