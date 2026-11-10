# pylint: disable=too-many-lines,too-many-locals,too-many-branches,broad-except
"""
NA IBP Planning Application — Variance Grid Component
=====================================================
Pure Python Dash HTML table renderers for the Variance Dashboard:
1. Consumption Variance Table (IBP & BP modes)
2. Shipment Variance Table (IBP & BP modes)
"""

import math
from typing import Optional, Dict, List, Any
from dash import html

from services.variance_service import (
    CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS,
    SHIPMENT_VARIANCE_DRIVER_DEFINITIONS,
)

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
SUB_DRIVERS = {"Innovation", "Cannibalization", "Price", "Elasticity"}

COLOR_B600 = "var(--b600, #2E2E2E)"
CLASS_ROW_YEAR_LABEL = "sum-driver-label sum-row-year-label fw-bold"
CLASS_DRIVER_SUB = "sum-driver-label sum-driver-sub"


def fmt_variance_number(val: Optional[float], decimals: int = 2, is_driver: bool = True) -> str:
    """
    Formats Variance numbers:
    - None / NaN -> '' (clean blank cell)
    - Negative with is_driver=True -> (0.14) (financial parentheses)
    - Negative with is_driver=False -> -0.14
    - True Zero -> 0.00
    """
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return ""
    v = float(val)
    rounded_val = round(abs(v), decimals)
    if rounded_val == 0:
        return f"{0.0:.{decimals}f}"
    if v < 0:
        return f"({rounded_val:.{decimals}f})" if is_driver else f"-{rounded_val:.{decimals}f}"
    return f"{rounded_val:.{decimals}f}"


def get_variance_heatmap_style(val: Optional[float], max_pos: float, max_neg_mag: float) -> tuple[str, str, str]:
    if val is None or (isinstance(val, float) and math.isnan(val)) or abs(val) < 0.0001:
        return "transparent", COLOR_B600, "normal"

    v = float(val)
    if v > 0:
        norm = min(1.0, v / (max_pos if max_pos > 0 else 1.0))
        if norm >= 0.8:
            return "#00695C", "#FFFFFF", "bold"
        if norm >= 0.6:
            return "#00897B", "#FFFFFF", "bold"
        if norm >= 0.4:
            return "#4DB6AC", "#1A202C", "600"
        if norm >= 0.2:
            return "#80CBC4", "#1A202C", "normal"
        return "#B2DFDB", "#1A202C", "normal"
    else:
        norm = min(1.0, abs(v) / (max_neg_mag if max_neg_mag > 0 else 1.0))
        if norm >= 0.8:
            return "#C62828", "#FFFFFF", "bold"
        if norm >= 0.6:
            return "#E53935", "#FFFFFF", "bold"
        if norm >= 0.4:
            return "#EF5350", "#FFFFFF", "600"
        if norm >= 0.2:
            return "#E57373", "#1A202C", "normal"
        return "#FFCDD2", "#1A202C", "normal"


def _get_thead(category_title: str = "CATEGORY", driver_title: str = "DRIVER") -> html.Thead:
    hdr_row1 = html.Tr([
        html.Th(category_title, rowSpan=2, className="sum-th-category"),
        html.Th(driver_title, rowSpan=2, className="sum-th-driver"),
        html.Th("Q1", colSpan=3, className="sum-th-quarter"),
        html.Th("Q2", colSpan=3, className="sum-th-quarter"),
        html.Th("Q3", colSpan=3, className="sum-th-quarter"),
        html.Th("Q4", colSpan=3, className="sum-th-quarter sum-col-quarter-end"),
        html.Th("TOTALS", colSpan=7, className="sum-th-total"),
    ], className="sum-thead-tier1")

    periods = ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]
    hdr_cells = []
    for idx, m in enumerate(MONTHS):
        cls = "sum-th-month sum-col-quarter-end" if idx in {2, 5, 8, 11} else "sum-th-month"
        hdr_cells.append(html.Th(m, className=cls))

    for p in periods:
        cls = "sum-th-period sum-col-quarter-end" if p == "Q4" else "sum-th-period"
        hdr_cells.append(html.Th(p, className=cls))

    hdr_row2 = html.Tr(hdr_cells, className="sum-thead-tier2")
    return html.Thead([hdr_row1, hdr_row2])


def _render_styled_cell(
    val: Optional[float],
    max_pos: float,
    max_neg_mag: float,
    is_driver: bool,
    decimals: int,
    is_quarter_end: bool,
    is_total: bool,
) -> html.Td:
    txt = fmt_variance_number(val, decimals=decimals, is_driver=is_driver)
    base_cls = "sum-summary-cell" if is_total else "sum-num-cell"
    cls_list = [base_cls]
    if is_quarter_end:
        cls_list.append("sum-col-quarter-end")

    style_dict = {}
    if is_driver and txt != "":
        bg_col, txt_col, font_wt = get_variance_heatmap_style(val, max_pos, max_neg_mag)
        style_dict = {"backgroundColor": bg_col, "color": txt_col, "fontWeight": font_wt}

    return html.Td(txt, className=" ".join(cls_list), style=style_dict if style_dict else None)


def build_variance_data_cells(
    m_vals: List[Optional[float]],
    totals: Dict[str, Optional[float]],
    max_pos: float,
    max_neg_mag: float,
    is_driver: bool = True,
    decimals: int = 2,
) -> List[html.Td]:
    cells = [
        _render_styled_cell(
            val, max_pos, max_neg_mag, is_driver, decimals,
            is_quarter_end=(m_idx in {2, 5, 8, 11}), is_total=False
        )
        for m_idx, val in enumerate(m_vals)
    ]
    for col_name in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        val = totals.get(col_name) if totals else None
        cells.append(
            _render_styled_cell(
                val, max_pos, max_neg_mag, is_driver, decimals,
                is_quarter_end=(col_name == "Q4"), is_total=True
            )
        )
    return cells


def _build_placeholder_dash_cells() -> List[html.Td]:
    cells = []
    for m_idx in range(12):
        cls_list = ["sum-num-cell"]
        if m_idx in {2, 5, 8, 11}:
            cls_list.append("sum-col-quarter-end")
        cells.append(html.Td("-", className=" ".join(cls_list)))

    for col_name in ["Q1", "Q2", "Q3", "Q4", "FY", "YTD", "YTG"]:
        cls_list = ["sum-summary-cell"]
        if col_name == "Q4":
            cls_list.append("sum-col-quarter-end")
        cells.append(html.Td("-", className=" ".join(cls_list)))
    return cells


def _render_grouped_driver_rows(
    definitions: list,
    drivers_dict: dict,
    driver_totals_dict: dict,
    max_pos: float,
    max_neg_mag: float,
    is_shipment: bool = False,
) -> List[html.Tr]:
    group_counts: Dict[str, int] = {}
    for grp, _, _ in definitions:
        group_counts[grp] = group_counts.get(grp, 0) + 1

    seen_groups = set()
    group_rows_counter: Dict[str, int] = {}
    rows = []

    for grp, driver_name, _ in definitions:
        cells = []
        if grp not in seen_groups:
            seen_groups.add(grp)
            group_rows_counter[grp] = 0
            cells.append(html.Td(grp, rowSpan=group_counts[grp], className="sum-category-label"))

        group_rows_counter[grp] += 1
        is_last_in_group = (group_rows_counter[grp] == group_counts[grp])

        is_sub = driver_name in SUB_DRIVERS and not is_shipment
        driver_cls = CLASS_DRIVER_SUB if is_sub else "sum-driver-label"
        cells.append(html.Td(driver_name, className=driver_cls))

        d_vals = (
            drivers_dict.get((grp, driver_name))
            or drivers_dict.get(driver_name, [None] * 12)
        )
        d_totals = (
            driver_totals_dict.get((grp, driver_name))
            or driver_totals_dict.get(driver_name, {})
        )

        cells.extend(build_variance_data_cells(d_vals, d_totals, max_pos, max_neg_mag, is_driver=True, decimals=2))

        row_cls = "sum-row-group-bottom" if is_last_in_group else None
        rows.append(html.Tr(cells, className=row_cls))

    return rows


def _render_base_row_cells(data: Dict[str, Any], max_pos: float, max_neg_mag: float) -> List[html.Td]:
    base_vals = data.get("base_row_vals") or [None] * 12
    if any(v is not None for v in base_vals):
        return build_variance_data_cells(
            base_vals, data.get("totals_base", {}), max_pos, max_neg_mag, is_driver=False, decimals=2
        )
    return _build_placeholder_dash_cells()


def _render_bp_missing_notice(plan_year: Any, domain: str) -> html.Div:
    return html.Div(
        className="p-5 bg-white rounded border text-center my-4",
        style={"boxShadow": "0 1px 3px rgba(0, 0, 0, 0.05)", "maxWidth": "720px", "margin": "40px auto"},
        children=[
            html.I(className="bi bi-calendar-x text-warning fs-1 mb-3 d-block"),
            html.H5(f"No {domain.title()} BP Snapshot Found for {plan_year}", className="fw-bold text-dark mb-2"),
            html.P(
                f"There is no locked BP snapshot recorded for planning year {plan_year}. "
                "Switch back to IBP to compare Current Cycle vs Prior Cycle.",
                className="text-muted mb-0",
                style={"fontSize": "13px"},
            ),
        ],
    )


def render_consumption_variance_table(data: Dict[str, Any]) -> html.Div:
    if data.get("bp_missing"):
        return _render_bp_missing_notice(data.get("plan_year"), "Consumption")

    drivers_dict = data.get("drivers", {})
    driver_totals_dict = data.get("driver_totals", {})
    max_pos = data.get("max_pos", 1.0)
    max_neg_mag = data.get("max_neg_mag", 1.0)

    thead = _get_thead(category_title="CATEGORY", driver_title="DRIVER")
    tbody_rows = [
        html.Tr([
            html.Td("", className="sum-category-label"),
            html.Td(str(data.get("label_base") or data.get("base_year", "Base")), className=CLASS_ROW_YEAR_LABEL),
            *_render_base_row_cells(data, max_pos, max_neg_mag),
        ], className="sum-row-base")
    ]

    tbody_rows.extend(_render_grouped_driver_rows(
        CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS, drivers_dict, driver_totals_dict, max_pos, max_neg_mag, is_shipment=False
    ))

    plan_lbl = str(data.get("label_plan") or data.get("plan_year") or "Plan")
    tbody_rows.append(html.Tr([
        html.Td("", className="sum-category-label"),
        html.Td(plan_lbl, className=CLASS_ROW_YEAR_LABEL),
        *build_variance_data_cells(
            data.get("plan_row_vals", [None] * 12), data.get("totals_plan", {}), max_pos, max_neg_mag, is_driver=False, decimals=2
        ),
    ], className="sum-row-active"))

    return html.Div(
        [html.Table([thead, html.Tbody(tbody_rows)], className="summary-table")],
        className="summary-grid-card"
    )


def render_shipment_variance_table(data: Dict[str, Any]) -> html.Div:
    if data.get("bp_missing"):
        return _render_bp_missing_notice(data.get("plan_year"), "Shipment")

    drivers_dict = data.get("drivers", {})
    driver_totals_dict = data.get("driver_totals", {})
    max_pos = data.get("max_pos", 1.0)
    max_neg_mag = data.get("max_neg_mag", 1.0)

    thead = _get_thead(category_title="CATEGORY", driver_title="DRIVER")
    tbody_rows = [
        html.Tr([
            html.Td("", className="sum-category-label"),
            html.Td(str(data.get("label_base") or data.get("base_year", "Base")), className=CLASS_ROW_YEAR_LABEL),
            *_render_base_row_cells(data, max_pos, max_neg_mag),
        ], className="sum-row-base")
    ]

    tbody_rows.extend(_render_grouped_driver_rows(
        SHIPMENT_VARIANCE_DRIVER_DEFINITIONS, drivers_dict, driver_totals_dict, max_pos, max_neg_mag, is_shipment=True
    ))

    plan_lbl = str(data.get("label_plan") or data.get("plan_year") or "Plan")
    tbody_rows.append(html.Tr([
        html.Td("", className="sum-category-label"),
        html.Td(plan_lbl, className=CLASS_ROW_YEAR_LABEL),
        *build_variance_data_cells(
            data.get("plan_row_vals", [None] * 12), data.get("totals_plan", {}), max_pos, max_neg_mag, is_driver=False, decimals=2
        ),
    ], className="sum-row-active"))

    return html.Div(
        [html.Table([thead, html.Tbody(tbody_rows)], className="summary-table")],
        className="summary-grid-card"
    )


def render_variance_matrix_table(
    data: Dict[str, Any], domain: str = "CONSUMPTION", model_name: str = ""
) -> html.Div:
    """Master entry point for rendering the active variance dashboard matrix."""
    if not data or not data.get("plan_year"):
        return html.Div(html.P("No variance data loaded.", className="text-muted p-4 text-center"), className="summary-grid-card")

    dom = domain.upper()
    if dom in ["SHIPMENT", "SHIPMENT VARIANCE"]:
        return render_shipment_variance_table(data)
    return render_consumption_variance_table(data)
