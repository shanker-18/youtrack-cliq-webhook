# pylint: disable=missing-function-docstring,redefined-outer-name
"""
Comprehensive unit tests for the Variance Dashboard.
Covers: variance_grid, variance_calculations, variance_service,
variance_callbacks helpers, and pages/variance UI builders.
"""
import math
from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from dash import html

from components.variance_grid import (
    fmt_variance_number,
    get_variance_heatmap_style,
    _get_positive_heatmap,
    _get_negative_heatmap,
    _get_thead,
    _render_styled_cell,
    build_variance_data_cells,
    _build_placeholder_dash_cells,
    _render_grouped_driver_rows,
    _render_base_row_cells,
    _render_bp_missing_notice,
    _render_variance_table_body,
    render_consumption_variance_table,
    render_shipment_variance_table,
    render_variance_matrix_table,
)
from services.variance_calculations import (
    calc_variance_totals,
    calculate_driver_heatmap_ranges,
    _round_driver_values,
    _sum_parent_drivers,
    _sum_shipment_parent_drivers,
    _build_consumption_driver_totals,
    _build_shipment_driver_totals,
    _resolve_cutoff_month,
)
from services.variance_service import (
    parse_month_num,
    get_active_years,
    _compute_driver_variance_monthly,
    _compute_compound_driver,
    _matches_consumption_driver_name,
    _matches_shipment_section,
    _matches_shipment_other,
    _matches_shipment_keyword,
    _matches_shipment_driver_name,
    _aggregate_consumption_driver,
    _aggregate_shipment_driver,
    _resolve_active_cycle_month,
    CycleSnapshotInfo,
    _resolve_consumption_snap_filter,
    _resolve_shipment_snap_filter,
    CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS,
    SHIPMENT_VARIANCE_DRIVER_DEFINITIONS,
)
from callbacks.variance_callbacks import (
    _normalize_squad_list,
    _normalize_model_list,
    _pick_active_models,
    _resolve_clean_models,
    _build_squad_list_from_gbu,
    _build_model_apply_session_data,
    _get_staging_squads_list,
    _get_staging_models_list,
    _calculate_next_squad_staging,
    _calculate_next_model_staging,
    _is_staging_callback_active,
    _build_variance_user_identity_elem,
    _get_var_fiscal_context,
    _is_var_cache_valid,
    clear_variance_cache,
    _is_session_source,
    _is_variance_sync_needed,
    _extract_sync_target_squad_and_model,
)
from pages.variance import (
    build_var_mode_menu_items,
    format_var_squad_pill_label,
    format_var_model_pill_label,
    render_empty_selection_card,
    render_empty_domain_alert,
    _render_ad_switcher_item,
    _build_ad_switcher_from_personas,
    _build_var_squad_header,
    _build_var_squad_footer,
    _build_var_model_header,
    _build_var_model_footer,
    _render_var_squad_item,
    _render_var_model_item,
    build_var_squad_menu_items,
    build_var_model_menu_items,
    _build_var_gbu_squad_rows,
    _build_var_squad_model_rows,
    TILE_ACTIVE_STYLE,
    TILE_INACTIVE_STYLE,
)


# ==============================================================================
# 1. fmt_variance_number
# ==============================================================================
class TestFmtVarianceNumber:
    def test_none_blank(self):
        assert fmt_variance_number(None) == ""

    def test_nan_blank(self):
        assert fmt_variance_number(float("nan")) == ""

    def test_inf_blank(self):
        assert fmt_variance_number(float("inf")) == ""

    def test_neg_inf_blank(self):
        assert fmt_variance_number(float("-inf")) == ""

    def test_true_zero_blank(self):
        assert fmt_variance_number(0.0) == ""

    def test_neg_zero_blank(self):
        assert fmt_variance_number(-0.0) == ""

    def test_tiny_positive_shows_zero(self):
        assert fmt_variance_number(0.001) == "0.00"

    def test_tiny_negative_shows_zero(self):
        assert fmt_variance_number(-0.001) == "0.00"

    def test_very_tiny_shows_zero(self):
        assert fmt_variance_number(0.00004) == "0.00"

    def test_positive_value(self):
        assert fmt_variance_number(1.23) == "1.23"

    def test_negative_driver_parens(self):
        assert fmt_variance_number(-0.14, is_driver=True) == "(0.14)"

    def test_negative_non_driver_minus(self):
        assert fmt_variance_number(-0.14, is_driver=False) == "-0.14"

    def test_large_positive(self):
        assert fmt_variance_number(123.456) == "123.46"

    def test_large_negative_driver(self):
        assert fmt_variance_number(-99.999, is_driver=True) == "(100.00)"

    def test_custom_decimals_zero(self):
        assert fmt_variance_number(1.5, decimals=0) == "2"

    def test_custom_decimals_three(self):
        assert fmt_variance_number(1.2345, decimals=3) == "1.235"

    def test_integer_input(self):
        assert fmt_variance_number(5) == "5.00"

    def test_negative_integer_driver(self):
        assert fmt_variance_number(-3, is_driver=True) == "(3.00)"

    def test_negative_integer_non_driver(self):
        assert fmt_variance_number(-3, is_driver=False) == "-3.00"


# ==============================================================================
# 2. Heatmap Styles
# ==============================================================================
class TestHeatmapStyle:
    def test_none_transparent(self):
        bg, _, _ = get_variance_heatmap_style(None, 1.0, 1.0)
        assert bg == "transparent"

    def test_nan_transparent(self):
        bg, _, _ = get_variance_heatmap_style(float("nan"), 1.0, 1.0)
        assert bg == "transparent"

    def test_near_zero_transparent(self):
        bg, _, _ = get_variance_heatmap_style(0.00001, 1.0, 1.0)
        assert bg == "transparent"

    def test_positive_colored(self):
        bg, _, _ = get_variance_heatmap_style(0.9, 1.0, 1.0)
        assert bg != "transparent"

    def test_negative_colored(self):
        bg, _, _ = get_variance_heatmap_style(-0.9, 1.0, 1.0)
        assert bg != "transparent"

    def test_zero_max_pos_safe(self):
        bg, _, _ = get_variance_heatmap_style(0.5, 0.0, 1.0)
        assert bg != "transparent"

    def test_zero_max_neg_safe(self):
        bg, _, _ = get_variance_heatmap_style(-0.5, 1.0, 0.0)
        assert bg != "transparent"


class TestHeatmapBands:
    def test_pos_band_08(self):
        _, c, w = _get_positive_heatmap(0.9)
        assert c == "#FFFFFF" and w == "bold"

    def test_pos_band_06(self):
        _, c, w = _get_positive_heatmap(0.7)
        assert w == "bold"

    def test_pos_band_04(self):
        _, _, w = _get_positive_heatmap(0.5)
        assert w == "600"

    def test_pos_band_02(self):
        _, _, w = _get_positive_heatmap(0.3)
        assert w == "normal"

    def test_pos_band_00(self):
        _, _, w = _get_positive_heatmap(0.1)
        assert w == "normal"

    def test_neg_band_08(self):
        _, c, w = _get_negative_heatmap(0.9)
        assert c == "#FFFFFF" and w == "bold"

    def test_neg_band_06(self):
        _, _, w = _get_negative_heatmap(0.7)
        assert w == "bold"

    def test_neg_band_04(self):
        _, _, w = _get_negative_heatmap(0.5)
        assert w == "600"

    def test_neg_band_02(self):
        _, _, w = _get_negative_heatmap(0.3)
        assert w == "normal"

    def test_neg_band_00(self):
        _, _, w = _get_negative_heatmap(0.1)
        assert w == "normal"


# ==============================================================================
# 3. Grid Cell Rendering
# ==============================================================================
class TestGridCells:
    def test_thead_default(self):
        assert _get_thead() is not None

    def test_thead_custom(self):
        assert _get_thead("CAT", "DRV") is not None

    def test_styled_cell_blank(self):
        td = _render_styled_cell(None, 1.0, 1.0, True, 2, False, False)
        assert td.children == ""

    def test_styled_cell_positive_driver(self):
        td = _render_styled_cell(0.5, 1.0, 1.0, True, 2, False, False)
        assert td.children == "0.50"
        assert td.style is not None

    def test_styled_cell_quarter_end(self):
        td = _render_styled_cell(0.5, 1.0, 1.0, True, 2, True, False)
        assert "sum-col-quarter-end" in td.className

    def test_styled_cell_total(self):
        td = _render_styled_cell(0.5, 1.0, 1.0, True, 2, False, True)
        assert "sum-summary-cell" in td.className

    def test_styled_cell_non_driver_no_color(self):
        td = _render_styled_cell(0.5, 1.0, 1.0, False, 2, False, False)
        assert td.style is None

    def test_data_cells_count(self):
        totals = {"Q1": 3.0, "Q2": 3.0, "Q3": 3.0, "Q4": 3.0, "FY": 12.0, "YTD": 6.0, "YTG": 6.0}
        cells = build_variance_data_cells([1.0] * 12, totals, 1.0, 1.0)
        assert len(cells) == 19

    def test_data_cells_none_totals(self):
        cells = build_variance_data_cells([None] * 12, None, 1.0, 1.0)
        assert len(cells) == 19

    def test_placeholder_cells_count(self):
        assert len(_build_placeholder_dash_cells()) == 19

    def test_placeholder_cells_content(self):
        cells = _build_placeholder_dash_cells()
        assert all(c.children == "-" for c in cells)


# ==============================================================================
# 4. Table Body & Full Rendering
# ==============================================================================
class TestTableRendering:
    def _make_data(self, bp_missing=False):
        return {
            "plan_year": 2026,
            "base_year": 2025,
            "label_base": "2025",
            "label_plan": "2026",
            "bp_missing": bp_missing,
            "drivers": {"Base Trend": [0.1] * 12, "Season": [None] * 12},
            "driver_totals": {"Base Trend": {"Q1": 0.3, "Q2": 0.3, "Q3": 0.3, "Q4": 0.3, "FY": 1.2, "YTD": 0.6, "YTG": 0.6}},
            "base_row_vals": [0.5] * 12,
            "plan_row_vals": [0.6] * 12,
            "totals_base": {"Q1": 1.5, "Q2": 1.5, "Q3": 1.5, "Q4": 1.5, "FY": 6.0, "YTD": 3.0, "YTG": 3.0},
            "totals_plan": {"Q1": 1.8, "Q2": 1.8, "Q3": 1.8, "Q4": 1.8, "FY": 7.2, "YTD": 3.6, "YTG": 3.6},
            "max_pos": 1.0,
            "max_neg_mag": 1.0,
        }

    def test_bp_missing_notice(self):
        div = _render_bp_missing_notice(2026, "Consumption")
        assert div is not None

    def test_bp_missing_notice_shipment(self):
        div = _render_bp_missing_notice(2026, "Shipment")
        assert div is not None

    def test_variance_table_body(self):
        data = self._make_data()
        rows = _render_variance_table_body(data, CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS, is_shipment=False)
        assert len(rows) > 2

    def test_render_consumption_table(self):
        data = self._make_data()
        div = render_consumption_variance_table(data)
        assert div is not None

    def test_render_consumption_table_bp_missing(self):
        data = self._make_data(bp_missing=True)
        div = render_consumption_variance_table(data)
        assert div is not None

    def test_render_shipment_table(self):
        data = self._make_data()
        div = render_shipment_variance_table(data)
        assert div is not None

    def test_render_shipment_table_bp_missing(self):
        data = self._make_data(bp_missing=True)
        div = render_shipment_variance_table(data)
        assert div is not None

    def test_master_entry_empty(self):
        div = render_variance_matrix_table({})
        assert div is not None

    def test_master_entry_no_plan_year(self):
        div = render_variance_matrix_table({"plan_year": None})
        assert div is not None

    def test_master_entry_consumption(self):
        data = self._make_data()
        div = render_variance_matrix_table(data, domain="CONSUMPTION")
        assert div is not None

    def test_master_entry_shipment(self):
        data = self._make_data()
        div = render_variance_matrix_table(data, domain="SHIPMENT")
        assert div is not None

    def test_master_entry_shipment_variance(self):
        data = self._make_data()
        div = render_variance_matrix_table(data, domain="SHIPMENT VARIANCE")
        assert div is not None

    def test_base_row_cells_with_data(self):
        data = {"base_row_vals": [1.0] * 12, "totals_base": {"Q1": 3.0, "Q2": 3.0, "Q3": 3.0, "Q4": 3.0, "FY": 12.0, "YTD": 6.0, "YTG": 6.0}}
        cells = _render_base_row_cells(data, 1.0, 1.0)
        assert len(cells) == 19

    def test_base_row_cells_all_none(self):
        cells = _render_base_row_cells({"base_row_vals": [None] * 12}, 1.0, 1.0)
        assert len(cells) == 19

    def test_base_row_cells_missing(self):
        cells = _render_base_row_cells({}, 1.0, 1.0)
        assert len(cells) == 19

    def test_grouped_driver_rows(self):
        defs = [("External", "Base Trend", "BASE TREND"), ("External", "Season", "SEASON")]
        drivers = {"Base Trend": [0.1] * 12, "Season": [0.2] * 12}
        totals = {"Base Trend": {"Q1": 0.3}, "Season": {"Q1": 0.6}}
        rows = _render_grouped_driver_rows(defs, drivers, totals, 1.0, 1.0, is_shipment=False)
        assert len(rows) == 2

    def test_grouped_driver_rows_shipment(self):
        defs = [("Inventory", "Distribution", "DISTRIBUTION")]
        drivers = {("Inventory", "Distribution"): [0.1] * 12}
        totals = {("Inventory", "Distribution"): {"Q1": 0.3}}
        rows = _render_grouped_driver_rows(defs, drivers, totals, 1.0, 1.0, is_shipment=True)
        assert len(rows) == 1


# ==============================================================================
# 5. calc_variance_totals
# ==============================================================================
class TestCalcVarianceTotals:
    def test_all_none(self):
        r = calc_variance_totals([None] * 12)
        assert all(v is None for v in r.values())

    def test_q1(self):
        assert calc_variance_totals([1.0, 2.0, 3.0] + [None] * 9)["Q1"] == pytest.approx(6.0)

    def test_q2(self):
        assert calc_variance_totals([None] * 3 + [4.0, 5.0, 6.0] + [None] * 6)["Q2"] == pytest.approx(15.0)

    def test_q3(self):
        assert calc_variance_totals([None] * 6 + [1.0, 2.0, 3.0] + [None] * 3)["Q3"] == pytest.approx(6.0)

    def test_q4(self):
        assert calc_variance_totals([None] * 9 + [1.0, 2.0, 3.0])["Q4"] == pytest.approx(6.0)

    def test_fy(self):
        assert calc_variance_totals([1.0] * 12)["FY"] == pytest.approx(12.0)

    def test_ytd_cutoff_6(self):
        r = calc_variance_totals([1.0] * 12, cutoff_month=6)
        assert r["YTD"] == pytest.approx(6.0) and r["YTG"] == pytest.approx(6.0)

    def test_ytd_cutoff_0(self):
        r = calc_variance_totals([1.0] * 12, cutoff_month=0)
        assert r["YTD"] is None

    def test_ytd_cutoff_12(self):
        r = calc_variance_totals([1.0] * 12, cutoff_month=12)
        assert r["YTD"] == pytest.approx(12.0) and r["YTG"] is None

    def test_mixed_none(self):
        assert calc_variance_totals([1.0, None, 2.0] + [None] * 9)["Q1"] == pytest.approx(3.0)

    def test_nan_values_ignored(self):
        assert calc_variance_totals([float("nan")] * 12)["FY"] is None


# ==============================================================================
# 6. Heatmap Ranges & Driver Helpers
# ==============================================================================
class TestDriverHelpers:
    def test_heatmap_ranges_empty(self):
        assert calculate_driver_heatmap_ranges({}) == (1.0, 1.0)

    def test_heatmap_ranges_positive(self):
        assert calculate_driver_heatmap_ranges({"d": [3.0, 1.0] + [None] * 10})[0] == 3.0

    def test_heatmap_ranges_negative(self):
        assert calculate_driver_heatmap_ranges({"d": [-5.0] + [None] * 11})[1] == 5.0

    def test_heatmap_ranges_with_totals(self):
        p, n = calculate_driver_heatmap_ranges({"d": [1.0] + [None] * 11}, {"d": {"Q1": 5.0, "FY": -8.0}})
        assert p == 5.0 and n == 8.0

    def test_heatmap_ranges_nan_ignored(self):
        assert calculate_driver_heatmap_ranges({"d": [float("nan")] * 12}) == (1.0, 1.0)

    def test_round_driver_values(self):
        d = {"x": [1.123456789012, None, float("nan")]}
        _round_driver_values(d)
        assert d["x"][0] == pytest.approx(1.123456789)
        assert d["x"][1] is None
        assert d["x"][2] is None

    def test_sum_parent_drivers(self):
        d = {"A": [1.0, 2.0] + [None] * 10, "B": [3.0, None] + [None] * 10}
        r = _sum_parent_drivers(d, ["A", "B"])
        assert r[0] == pytest.approx(4.0) and r[1] == pytest.approx(2.0)

    def test_sum_parent_drivers_all_none(self):
        assert all(v is None for v in _sum_parent_drivers({"A": [None] * 12}, ["A"]))

    def test_sum_parent_missing_key(self):
        assert _sum_parent_drivers({"A": [1.0] + [None] * 11}, ["A", "Z"])[0] == pytest.approx(1.0)

    def test_sum_shipment_parent(self):
        defs = [("Inventory", "Distribution", "DISTRIBUTION")]
        d = {("Inventory", "Distribution"): [2.0] + [None] * 11}
        assert _sum_shipment_parent_drivers(d, defs)[0] == pytest.approx(2.0)

    def test_build_consumption_totals(self):
        d = {"Base Trend": [1.0] * 12}
        t = _build_consumption_driver_totals(d, 6)
        assert "Base Trend" in t

    def test_build_shipment_totals(self):
        d = {("Inventory", "Distribution"): [1.0] * 12, "Distribution": [1.0] * 12}
        t = _build_shipment_driver_totals(d, 6)
        assert "Distribution" in t

    def test_resolve_cutoff_env(self):
        with patch.dict("os.environ", {"IBP_CUTOFF_MONTH": "9"}):
            assert _resolve_cutoff_month(None) == 9

    def test_resolve_cutoff_active(self):
        assert _resolve_cutoff_month(7) == 7

    def test_resolve_cutoff_invalid_env(self):
        with patch.dict("os.environ", {"IBP_CUTOFF_MONTH": "99"}):
            assert _resolve_cutoff_month(5) == 5


# ==============================================================================
# 7. Variance Service: Parsing & Matching
# ==============================================================================
class TestParseMonthNum:
    def test_none(self):
        assert parse_month_num(None) is None

    def test_date(self):
        assert parse_month_num(date(2026, 3, 15)) == 3

    def test_digit(self):
        assert parse_month_num("7") == 7

    def test_name(self):
        assert parse_month_num("JANUARY") == 1

    def test_abbr(self):
        assert parse_month_num("MAR") == 3

    def test_iso(self):
        assert parse_month_num("2026-11-01") == 11

    def test_out_of_range(self):
        assert parse_month_num("13") is None

    def test_invalid(self):
        assert parse_month_num("INVALID") is None

    def test_zero(self):
        assert parse_month_num("0") is None

    def test_slash_format(self):
        assert parse_month_num("2026/06/01") == 6


class TestConsumptionDriverMatching:
    def test_base_trend(self):
        assert _matches_consumption_driver_name("BASE TREND", "BASE TREND") is True

    def test_season(self):
        assert _matches_consumption_driver_name("SEASON", "SEASON") is True

    def test_competition(self):
        assert _matches_consumption_driver_name("COMPETITION X", "COMPETITION") is True

    def test_distribution(self):
        assert _matches_consumption_driver_name("DISTRIBUTION", "DISTRIBUTION") is True

    def test_innovation_match(self):
        assert _matches_consumption_driver_name("INNOVATION", "INNOVATION") is True

    def test_innovation_excludes_net(self):
        assert _matches_consumption_driver_name("NET INNOVATION", "INNOVATION") is False

    def test_innovation_excludes_cannibal(self):
        assert _matches_consumption_driver_name("CANNIBALIZATION", "INNOVATION") is False

    def test_cannibalization(self):
        assert _matches_consumption_driver_name("CANNIBALIZATION", "CANNIBALIZATION") is True

    def test_price_match(self):
        assert _matches_consumption_driver_name("PRICE", "PRICE") is True

    def test_price_excludes_elast(self):
        assert _matches_consumption_driver_name("ELASTICITY", "PRICE") is False

    def test_elasticity(self):
        assert _matches_consumption_driver_name("ELASTICITY", "ELASTICITY") is True

    def test_other_match(self):
        assert _matches_consumption_driver_name("OTHER", "OTHER") is True

    def test_other_excludes_overlay(self):
        assert _matches_consumption_driver_name("OVERLAY OTHER", "OTHER") is False

    def test_renovation(self):
        assert _matches_consumption_driver_name("RENOVATION DRIVER", "RENOVATION") is True

    def test_discontinuations(self):
        assert _matches_consumption_driver_name("DISCONTINUATIONS", "DISCONTINUATIONS") is True

    def test_media(self):
        assert _matches_consumption_driver_name("MEDIA", "MEDIA") is True

    def test_trade(self):
        assert _matches_consumption_driver_name("TRADE", "TRADE") is True

    def test_club(self):
        assert _matches_consumption_driver_name("CLUB", "CLUB") is True

    def test_no_match(self):
        assert _matches_consumption_driver_name("RANDOM", "CLUB") is False

    def test_fallback_match(self):
        assert _matches_consumption_driver_name("XYZ_UNKNOWN", "XYZ_UNKNOWN") is True


class TestShipmentDriverMatching:
    def test_section_match(self):
        assert _matches_shipment_section("INVENTORY", "INVENTORY") is True

    def test_section_empty(self):
        assert _matches_shipment_section("", "INVENTORY") is True

    def test_section_mismatch(self):
        assert _matches_shipment_section("OVERLAYS", "INVENTORY") is False

    def test_other_inv(self):
        assert _matches_shipment_other("", "OTHER_INV", "", "Inventory") is True

    def test_other_overlay(self):
        assert _matches_shipment_other("", "OVERLAY_OTHER", "", "IBP Overlays") is True

    def test_other_in_name_inventory(self):
        assert _matches_shipment_other("OTHER STUFF", "", "", "Inventory") is True

    def test_other_overlay_in_name(self):
        assert _matches_shipment_other("OVERLAY OTHER", "", "", "IBP Overlays") is True

    def test_keyword_retail(self):
        assert _matches_shipment_keyword("RETAILER_INVENTORY", "RETAIL INV", "") is True

    def test_keyword_supply(self):
        assert _matches_shipment_keyword("SUPPLY_CONSTRAINTS", "SUPPLY CHAIN", "") is True

    def test_keyword_liquidat(self):
        assert _matches_shipment_keyword("LIQUIDAT", "", "LIQUIDAT_CODE") is True

    def test_keyword_no_match(self):
        assert _matches_shipment_keyword("INNOVATION", "SOMETHING", "") is False

    def test_driver_name_basic(self):
        assert _matches_shipment_driver_name("DISTRIBUTION", "Inventory", "DISTRIBUTION") is True

    def test_driver_name_with_separator(self):
        assert _matches_shipment_driver_name("INVENTORY::DIST_CODE::DISTRIBUTION", "Inventory", "DISTRIBUTION") is True

    def test_driver_name_other_inventory(self):
        assert _matches_shipment_driver_name("OTHER", "Inventory", "OTHER") is True

    def test_driver_name_section_mismatch(self):
        assert _matches_shipment_driver_name("OVERLAYS::CODE::ITEM", "Inventory", "DISTRIBUTION") is False


# ==============================================================================
# 8. Monthly Variance Computation
# ==============================================================================
class TestVarianceComputation:
    def test_both_empty(self):
        assert _compute_driver_variance_monthly({}, {}) == [None] * 12

    def test_current_only(self):
        r = _compute_driver_variance_monthly({1: 5.0}, {})
        assert r[0] == pytest.approx(5.0) and r[1] is None

    def test_base_only(self):
        assert _compute_driver_variance_monthly({}, {1: 3.0})[0] == pytest.approx(-3.0)

    def test_both_present(self):
        assert _compute_driver_variance_monthly({1: 10.0}, {1: 4.0})[0] == pytest.approx(6.0)

    def test_both_zero_none(self):
        assert _compute_driver_variance_monthly({1: 0.0}, {1: 0.0})[0] is None

    def test_equal_returns_zero(self):
        assert _compute_driver_variance_monthly({1: 5.0}, {1: 5.0})[0] == pytest.approx(0.0)

    def test_all_months(self):
        c = {m: float(m) for m in range(1, 13)}
        b = {m: 1.0 for m in range(1, 13)}
        r = _compute_driver_variance_monthly(c, b)
        assert r[0] == pytest.approx(0.0) and r[11] == pytest.approx(11.0)

    def test_compound_both_none(self):
        assert _compute_compound_driver([None] * 12, [None] * 12) == [None] * 12

    def test_compound_one_none(self):
        assert _compute_compound_driver([1.0] + [None] * 11, [None] * 12)[0] == pytest.approx(1.0)

    def test_compound_both(self):
        assert _compute_compound_driver([2.0] + [None] * 11, [3.0] + [None] * 11)[0] == pytest.approx(5.0)

    def test_compound_negative(self):
        assert _compute_compound_driver([1.0] + [None] * 11, [-3.0] + [None] * 11)[0] == pytest.approx(-2.0)

    def test_aggregate_consumption(self):
        curr = {"BASE TREND VALUE": {1: 10.0, 2: 20.0}}
        base = {"BASE TREND VALUE": {1: 5.0, 2: 15.0}}
        r = _aggregate_consumption_driver(curr, base, "BASE TREND")
        assert r[0] == pytest.approx(5.0) and r[1] == pytest.approx(5.0)

    def test_aggregate_consumption_no_match(self):
        r = _aggregate_consumption_driver({"X": {1: 10.0}}, {"X": {1: 5.0}}, "BASE TREND")
        assert r == [None] * 12

    def test_aggregate_shipment(self):
        curr = {"INVENTORY::DIST::DISTRIBUTION": {1: 8.0}}
        base = {"INVENTORY::DIST::DISTRIBUTION": {1: 3.0}}
        r = _aggregate_shipment_driver(curr, base, "Inventory", "DISTRIBUTION")
        assert r[0] == pytest.approx(5.0)

    def test_resolve_active_cycle_month_from_args(self):
        assert _resolve_active_cycle_month(5, None) == 5

    def test_resolve_active_cycle_month_fallback(self):
        m = _resolve_active_cycle_month(None, None)
        assert 1 <= m <= 12


class TestSnapshotFilters:
    def test_consumption_bp_filter_none(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, None, 6)
        assert _resolve_consumption_snap_filter(snap, "BP", 2026, None) is None

    def test_consumption_bp_filter_found(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, 10, None, 6)
        f = _resolve_consumption_snap_filter(snap, "BP", 2026, None)
        assert "10" in f

    def test_consumption_prior_filter_none(self):
        snap = CycleSnapshotInfo(1, None, 3, 4, None, None, 6)
        assert _resolve_consumption_snap_filter(snap, "PRIOR", 2026, None) is None

    def test_consumption_prior_filter_found(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, None, 6)
        f = _resolve_consumption_snap_filter(snap, "PRIOR", 2026, None)
        assert "2" in f

    def test_consumption_current_filter(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, None, 6)
        f = _resolve_consumption_snap_filter(snap, "CURRENT", 2026, None)
        assert "1" in f

    def test_consumption_current_filter_no_id(self):
        snap = CycleSnapshotInfo(None, 2, 3, 4, None, None, 6)
        f = _resolve_consumption_snap_filter(snap, "CURRENT", 2026, None)
        assert "NULL" in f

    def test_shipment_bp_filter_none(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, None, 6)
        assert _resolve_shipment_snap_filter(snap, "BP", 2026, None) is None

    def test_shipment_bp_filter_found(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, 10, 6)
        f = _resolve_shipment_snap_filter(snap, "BP", 2026, None)
        assert "10" in f

    def test_shipment_prior_filter(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, None, 6)
        f = _resolve_shipment_snap_filter(snap, "PRIOR", 2026, None)
        assert "4" in f

    def test_shipment_current_filter(self):
        snap = CycleSnapshotInfo(1, 2, 3, 4, None, None, 6)
        f = _resolve_shipment_snap_filter(snap, "CURRENT", 2026, None)
        assert "3" in f


# ==============================================================================
# 9. Callback Helpers
# ==============================================================================
class TestNormalizeLists:
    def test_squad_none(self):
        assert _normalize_squad_list(None) == []

    def test_squad_empty(self):
        assert _normalize_squad_list("") == []

    def test_squad_string(self):
        assert _normalize_squad_list("PAIN CARE") == ["PAIN CARE"]

    def test_squad_select_squad(self):
        assert _normalize_squad_list("Select Squad") == []

    def test_squad_list(self):
        assert _normalize_squad_list(["A", "B"]) == ["A", "B"]

    def test_squad_list_filters(self):
        assert _normalize_squad_list(["A", "", "Select Squad"]) == ["A"]

    def test_model_none(self):
        assert _normalize_model_list(None) == []

    def test_model_empty(self):
        assert _normalize_model_list("") == []

    def test_model_string(self):
        assert _normalize_model_list("Motrin") == ["Motrin"]

    def test_model_select_model(self):
        assert _normalize_model_list("Select Model") == []

    def test_model_list(self):
        assert _normalize_model_list(["A", "B"]) == ["A", "B"]

    def test_model_list_filters(self):
        assert _normalize_model_list(["A", "", "Select Model"]) == ["A"]


class TestPickActiveModels:
    def test_matched(self):
        avail = [{"model_name": "Motrin", "model_id": 1}, {"model_name": "Tylenol", "model_id": 2}]
        models, mid = _pick_active_models(["Motrin"], avail, avail)
        assert models == ["Motrin"] and mid == 1

    def test_no_match_fallback(self):
        avail = [{"model_name": "Motrin", "model_id": 1}]
        models, mid = _pick_active_models(["Unknown"], avail, avail)
        assert models == ["Motrin"] and mid == 1

    def test_empty_pool(self):
        models, mid = _pick_active_models(["X"], [], [])
        assert models == [] and mid is None

    def test_case_insensitive(self):
        avail = [{"model_name": "Motrin", "model_id": 1}]
        models, _ = _pick_active_models(["motrin"], avail, avail)
        assert models == ["Motrin"]


class TestResolveCleanModels:
    def test_none(self):
        assert _resolve_clean_models(None) == []

    def test_string(self):
        assert _resolve_clean_models("Motrin") == ["Motrin"]

    def test_select_model(self):
        assert _resolve_clean_models("Select Model") == []

    def test_list(self):
        assert _resolve_clean_models(["A", "B"]) == ["A", "B"]

    def test_empty_string(self):
        assert _resolve_clean_models("") == []

    def test_list_with_blanks(self):
        assert _resolve_clean_models(["A", "", "Select Model"]) == ["A"]


class TestStagingHelpers:
    def test_staging_squads_from_store(self):
        assert _get_staging_squads_list(["A", "B"], ["C"]) == ["A", "B"]

    def test_staging_squads_from_committed(self):
        assert _get_staging_squads_list(None, ["C"]) == ["C"]

    def test_staging_squads_none(self):
        assert _get_staging_squads_list(None, None) == []

    def test_staging_models_from_store(self):
        assert _get_staging_models_list(["X"], ["Y"]) == ["X"]

    def test_staging_models_from_committed(self):
        assert _get_staging_models_list(None, ["Y"]) == ["Y"]

    def test_staging_models_none(self):
        assert _get_staging_models_list(None, None) == []

    def test_next_squad_staging_add(self):
        t = {"type": "var-squad-select-item", "name": "NEW"}
        r = _calculate_next_squad_staging(t, ["OLD"], ["OLD", "NEW"])
        assert "NEW" in r

    def test_next_squad_staging_remove(self):
        t = {"type": "var-squad-select-item", "name": "OLD"}
        r = _calculate_next_squad_staging(t, ["OLD"], ["OLD", "NEW"])
        assert r == []

    def test_next_squad_staging_select_all(self):
        t = {"type": "var-squad-action", "action": "select-all"}
        r = _calculate_next_squad_staging(t, [], ["A", "B"])
        assert r == ["A", "B"]

    def test_next_squad_staging_deselect_all(self):
        t = {"type": "var-squad-action", "action": "select-all"}
        r = _calculate_next_squad_staging(t, ["A", "B"], ["A", "B"])
        assert r == []

    def test_next_squad_staging_reset(self):
        t = {"type": "var-squad-action", "action": "reset"}
        assert _calculate_next_squad_staging(t, ["A"], ["A"]) == []

    def test_next_squad_staging_unknown(self):
        assert _calculate_next_squad_staging({"type": "unknown"}, [], []) is None

    def test_next_model_staging_add(self):
        t = {"type": "var-model-select-item", "name": "M2"}
        r = _calculate_next_model_staging(t, ["M1"], ["M1", "M2"])
        assert "M2" in r

    def test_next_model_staging_remove(self):
        t = {"type": "var-model-select-item", "name": "M1"}
        r = _calculate_next_model_staging(t, ["M1"], ["M1", "M2"])
        assert r == []

    def test_next_model_staging_select_all(self):
        t = {"type": "var-model-action", "action": "select-all"}
        assert _calculate_next_model_staging(t, [], ["A", "B"]) == ["A", "B"]

    def test_next_model_staging_reset(self):
        t = {"type": "var-model-action", "action": "reset"}
        assert _calculate_next_model_staging(t, ["A"], ["A"]) == []

    def test_is_staging_active_true(self):
        assert _is_staging_callback_active([1], [0], {"type": "x"}) is True

    def test_is_staging_active_no_clicks(self):
        assert _is_staging_callback_active([0], [0], {"type": "x"}) is False

    def test_is_staging_active_apply(self):
        assert _is_staging_callback_active([1], [0], {"action": "apply"}) is False

    def test_is_staging_active_not_dict(self):
        assert _is_staging_callback_active([1], [0], "string") is False


class TestModelSessionData:
    def test_basic(self):
        avail = [{"model_name": "Motrin", "model_id": 1}]
        d = _build_model_apply_session_data("Motrin", "PAIN CARE", avail)
        assert d["model_id"] == 1 and d["model_name"] == "Motrin"

    def test_with_selections(self):
        avail = [{"model_name": "Motrin", "model_id": 1}]
        d = _build_model_apply_session_data("Motrin", "PAIN", avail, ["Motrin", "Tylenol"], ["PAIN"])
        assert len(d["selected_models"]) == 2

    def test_no_match(self):
        d = _build_model_apply_session_data("Unknown", "SQ", [])
        assert d["model_id"] is None

    def test_empty_primary(self):
        d = _build_model_apply_session_data("", "", [])
        assert d["selected_models"] == []


class TestSyncHelpers:
    def test_is_session_source_true(self):
        assert _is_session_source({"source": "variance"}, "variance") is True

    def test_is_session_source_false(self):
        assert _is_session_source({"source": "summary"}, "variance") is False

    def test_is_session_source_not_dict(self):
        assert _is_session_source("string", "variance") is False

    def test_sync_needed_ad_changed(self):
        assert _is_variance_sync_needed("A", "B", [], [], [], []) is True

    def test_sync_needed_squad_changed(self):
        assert _is_variance_sync_needed("A", "A", ["X"], ["Y"], [], []) is True

    def test_sync_needed_model_changed(self):
        assert _is_variance_sync_needed("A", "A", ["X"], ["X"], ["M1"], ["M2"]) is True

    def test_sync_not_needed(self):
        assert _is_variance_sync_needed("A", "A", ["X"], ["X"], ["M1"], ["M1"]) is False

    def test_extract_target_dict(self):
        s = {"selected_squads": ["SQ"], "selected_models": ["MOD"]}
        sq, mo = _extract_sync_target_squad_and_model(s, ["OLD_SQ"], ["OLD_MOD"])
        assert sq == ["SQ"] and mo == ["MOD"]

    def test_extract_target_fallback(self):
        s = {"squad_name": "SQ", "model_name": "MOD"}
        sq, mo = _extract_sync_target_squad_and_model(s, ["OLD"], ["OLD"])
        assert sq == ["SQ"] and mo == ["MOD"]

    def test_extract_target_not_dict(self):
        sq, mo = _extract_sync_target_squad_and_model("x", ["A"], ["B"])
        assert sq == ["A"] and mo == ["B"]


class TestUserIdentityElem:
    @patch("callbacks.variance_callbacks.get_current_user")
    def test_with_user(self, mock_user):
        mock_user.return_value = {"display_name": "John", "email": "john@test.com"}
        elems = _build_variance_user_identity_elem("fallback@test.com")
        assert len(elems) == 2

    @patch("callbacks.variance_callbacks.get_current_user")
    def test_no_user(self, mock_user):
        mock_user.return_value = {}
        elems = _build_variance_user_identity_elem("fallback@test.com")
        assert len(elems) == 2


class TestFiscalContext:
    @patch("callbacks.variance_callbacks.KenvueCalendar")
    def test_fiscal_context(self, mock_kv):
        mock_info = MagicMock()
        mock_info.kv_year = 2026
        mock_info.kv_mo_id = "2026-12"
        mock_info.kv_month_abbr = "DEC"
        mock_kv.get_date_info.return_value = mock_info
        tag, badge = _get_var_fiscal_context()
        assert "2026" in tag and "DEC" in badge

    @patch("callbacks.variance_callbacks.KenvueCalendar")
    def test_fiscal_context_error(self, mock_kv):
        mock_kv.get_date_info.side_effect = Exception("fail")
        tag, badge = _get_var_fiscal_context()
        assert tag and badge


class TestVarCache:
    def test_cache_invalid_missing(self):
        assert _is_var_cache_valid("nonexistent_key") is False

    def test_clear_cache(self):
        clear_variance_cache()


class TestBuildSquadListFromGbu:
    @patch("callbacks.variance_callbacks._safe_get_squads_by_gbu")
    def test_basic(self, mock_squads):
        mock_squads.return_value = [{"squad_name": "PAIN CARE", "gbu_code": "PC", "gbu_name": "Pain Care"}]
        result = _build_squad_list_from_gbu(["PC"])
        assert len(result) == 1 and result[0]["squad_name"] == "PAIN CARE"

    @patch("callbacks.variance_callbacks._safe_get_squads_by_gbu")
    def test_empty(self, mock_squads):
        mock_squads.return_value = []
        assert _build_squad_list_from_gbu([]) == []


# ==============================================================================
# 10. Pages/Variance: Menu Builders & Labels
# ==============================================================================
class TestModeMenuItems:
    def test_ibp_default(self):
        items = build_var_mode_menu_items("IBP")
        assert len(items) == 3

    def test_bp_selected(self):
        items = build_var_mode_menu_items("BP")
        assert len(items) == 3

    def test_none_defaults_ibp(self):
        items = build_var_mode_menu_items(None)
        assert len(items) == 3


class TestSquadPillLabel:
    def test_none(self):
        assert format_var_squad_pill_label(None) == "Select Squad"

    def test_empty_list(self):
        assert format_var_squad_pill_label([]) == "Select Squad"

    def test_single_string(self):
        assert format_var_squad_pill_label("Pain Care") == "Pain Care"

    def test_single_list(self):
        assert format_var_squad_pill_label(["PAIN CARE"]) == "Pain Care"

    def test_multiple(self):
        assert "2 Squads" in format_var_squad_pill_label(["A", "B"])

    def test_all_squads(self):
        assert "All Squads" in format_var_squad_pill_label(["A", "B"], total_squads=2)

    def test_select_squad_filtered(self):
        assert format_var_squad_pill_label(["Select Squad"]) == "Select Squad"


class TestModelPillLabel:
    def test_none(self):
        assert format_var_model_pill_label(None) == "Select Model"

    def test_single_string(self):
        assert format_var_model_pill_label("Motrin") == "Motrin"

    def test_single_list(self):
        assert format_var_model_pill_label(["Motrin"]) == "Motrin"

    def test_multiple(self):
        assert "2 Models" in format_var_model_pill_label(["A", "B"])

    def test_all_models(self):
        assert "All Models" in format_var_model_pill_label(["A", "B"], total_models=2)


class TestEmptyCards:
    def test_squad_card(self):
        div = render_empty_selection_card("squad", "CONSUMPTION")
        assert div is not None

    def test_model_card(self):
        div = render_empty_selection_card("model", "SHIPMENT")
        assert div is not None

    def test_domain_alert(self):
        div = render_empty_domain_alert("Motrin", "consumption")
        assert div is not None

    def test_domain_alert_shipment(self):
        div = render_empty_domain_alert("Motrin", "shipment")
        assert div is not None


class TestAdSwitcherItem:
    def test_active(self):
        div = _render_ad_switcher_item("key1", "Name", "Sub", True)
        assert "active" in div.className

    def test_inactive(self):
        div = _render_ad_switcher_item("key1", "Name", "Sub", False)
        assert "active" not in div.className


class TestAdSwitcherFromPersonas:
    def test_builds_items(self):
        items = _build_ad_switcher_from_personas("COM-APP-NA-IBP-SELFCARE")
        assert len(items) > 0


class TestSquadMenuBuilders:
    def test_header(self):
        h = _build_var_squad_header(False, 0, 5)
        assert h is not None

    def test_header_all_selected(self):
        h = _build_var_squad_header(True, 5, 5)
        assert h is not None

    def test_footer(self):
        f = _build_var_squad_footer(3)
        assert f is not None

    def test_footer_zero(self):
        f = _build_var_squad_footer(0)
        assert f is not None

    def test_squad_item_checked(self):
        s = {"squad_name": "PAIN", "display_name": "Pain"}
        div = _render_var_squad_item(s, True)
        assert div is not None

    def test_squad_item_unchecked(self):
        s = {"squad_name": "PAIN", "display_name": "Pain"}
        div = _render_var_squad_item(s, False)
        assert div is not None

    def test_squad_menu_empty(self):
        items = build_var_squad_menu_items([])
        assert len(items) == 1

    def test_squad_menu_with_data(self):
        squads = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        items = build_var_squad_menu_items(squads, active_squad_name="PAIN")
        assert len(items) == 3

    def test_squad_menu_list_active(self):
        squads = [{"squad_name": "A", "display_name": "A", "gbu": "X"}, {"squad_name": "B", "display_name": "B", "gbu": "X"}]
        items = build_var_squad_menu_items(squads, active_squad_name=["A"])
        assert len(items) == 3

    def test_gbu_squad_rows(self):
        gbus = {"PC": [{"squad_name": "PAIN", "display_name": "Pain"}]}
        rows = _build_var_gbu_squad_rows(gbus, {"PAIN"})
        assert len(rows) == 2


class TestModelMenuBuilders:
    def test_header(self):
        h = _build_var_model_header(False, 0, 5)
        assert h is not None

    def test_header_all(self):
        h = _build_var_model_header(True, 5, 5)
        assert h is not None

    def test_footer(self):
        f = _build_var_model_footer(2)
        assert f is not None

    def test_model_item_checked(self):
        m = {"model_id": 1, "model_name": "Motrin"}
        div = _render_var_model_item(m, True)
        assert div is not None

    def test_model_item_unchecked(self):
        m = {"model_id": 1, "model_name": "Motrin"}
        div = _render_var_model_item(m, False)
        assert div is not None

    def test_model_item_no_id(self):
        m = {"model_name": "Motrin"}
        div = _render_var_model_item(m, False)
        assert div is not None

    def test_model_menu_empty(self):
        items = build_var_model_menu_items([])
        assert len(items) == 1

    def test_model_menu_empty_no_squad(self):
        items = build_var_model_menu_items([], has_squad=False)
        assert len(items) == 1

    def test_model_menu_with_data(self):
        models = [{"model_id": 1, "model_name": "Motrin", "squad_name": "PAIN"}]
        items = build_var_model_menu_items(models, active_model_name="Motrin")
        assert len(items) == 3

    def test_model_menu_list_active(self):
        models = [{"model_id": 1, "model_name": "A"}, {"model_id": 2, "model_name": "B"}]
        items = build_var_model_menu_items(models, active_model_name=["A"])
        assert len(items) == 3

    def test_squad_model_rows(self):
        models = [{"model_name": "M1", "squad_name": "SQ1"}, {"model_name": "M2", "squad_name": "SQ2"}]
        rows = _build_var_squad_model_rows(models, {"M1"})
        assert len(rows) >= 2

    def test_squad_model_rows_single_group(self):
        models = [{"model_name": "M1", "squad_name": "SQ1"}, {"model_name": "M2", "squad_name": "SQ1"}]
        rows = _build_var_squad_model_rows(models, set())
        assert len(rows) >= 2


class TestTileStyles:
    def test_active_has_bg(self):
        assert "backgroundColor" in TILE_ACTIVE_STYLE

    def test_inactive_white(self):
        assert TILE_INACTIVE_STYLE["backgroundColor"] == "#ffffff"

    def test_active_has_shadow(self):
        assert TILE_ACTIVE_STYLE["boxShadow"] != "none"

    def test_inactive_no_shadow(self):
        assert TILE_INACTIVE_STYLE["boxShadow"] == "none"
