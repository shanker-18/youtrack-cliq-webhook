

# ==============================================================================
# 11. variance_service: DB-dependent functions (mocked get_db_cursor)
# ==============================================================================
class TestGetActiveYears:
    @patch("services.variance_service.KenvueCalendar")
    def test_from_calendar(self, mock_kv):
        mock_info = MagicMock()
        mock_info.kv_year = 2026
        mock_kv.get_date_info.return_value = mock_info
        with patch.dict("os.environ", {}, clear=True):
            base, plan = get_active_years()
        assert base == 2025 and plan == 2026

    def test_from_env(self):
        with patch.dict("os.environ", {"IBP_PLAN_YEAR": "2027"}):
            base, plan = get_active_years()
        assert base == 2026 and plan == 2027

    @patch("services.variance_service.KenvueCalendar")
    def test_no_env_uses_calendar(self, mock_kv):
        mock_info = MagicMock()
        mock_info.kv_year = 2025
        mock_kv.get_date_info.return_value = mock_info
        with patch.dict("os.environ", {}, clear=True):
            _, plan = get_active_years()
        assert plan == 2025


class TestGetCycleSnapshotIdsMocked:
    @patch("services.variance_service.get_db_cursor")
    def test_basic(self, mock_db):
        mock_cur = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.side_effect = [
            {"snapshot_id": 100, "cycle_month": "11"},
            {"snapshot_id": 90, "cycle_month": "10"},
            {"snapshot_id": 200, "cycle_month": "11"},
            {"snapshot_id": 190, "cycle_month": "10"},
            {"snapshot_id": 50},
            {"snapshot_id": 60},
        ]
        from services.variance_service import get_cycle_snapshot_ids
        result = get_cycle_snapshot_ids(2026)
        assert result.curr_cs_id is not None

    @patch("services.variance_service.get_db_cursor")
    def test_exception_handled(self, mock_db):
        mock_db.return_value.__enter__.side_effect = Exception("DB down")
        from services.variance_service import get_cycle_snapshot_ids
        result = get_cycle_snapshot_ids(2026)
        assert result is not None
        assert result.active_cycle_month is not None

    @patch("services.variance_service.get_db_cursor")
    def test_no_snapshots(self, mock_db):
        mock_cur = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = None
        from services.variance_service import get_cycle_snapshot_ids
        result = get_cycle_snapshot_ids(2026)
        assert result.curr_cs_id is None


class TestFetchConsumptionBlocks:
    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_basic_fetch(self, mock_snap, mock_db):
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_cur = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"building_block": "BASE TREND", "month_num": 1, "value_in_thousands": 10500.0},
            {"building_block": "BASE TREND", "month_num": 2, "value_in_thousands": 20300.0},
        ]
        from services.variance_service import _fetch_cycle_consumption_blocks
        result, found = _fetch_cycle_consumption_blocks(["Motrin"], 2026, baseline_mode="CURRENT")
        assert "BASE TREND" in result
        assert found is True

    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_empty_models(self, mock_snap, mock_db):
        from services.variance_service import _fetch_cycle_consumption_blocks
        result, found = _fetch_cycle_consumption_blocks([], 2026, baseline_mode="CURRENT")
        assert result == {} and found is False

    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_no_rows(self, mock_snap, mock_db):
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_cur = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        from services.variance_service import _fetch_cycle_consumption_blocks
        result, found = _fetch_cycle_consumption_blocks(["Motrin"], 2026, baseline_mode="CURRENT")
        assert result == {} and found is True

    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_db_exception(self, mock_snap, mock_db):
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_db.return_value.__enter__.side_effect = Exception("fail")
        from services.variance_service import _fetch_cycle_consumption_blocks
        result, found = _fetch_cycle_consumption_blocks(["Motrin"], 2026, baseline_mode="CURRENT")
        assert found is False

    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_bp_no_snapshot(self, mock_snap, mock_db):
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        from services.variance_service import _fetch_cycle_consumption_blocks
        result, found = _fetch_cycle_consumption_blocks(["Motrin"], 2026, baseline_mode="BP")
        assert found is False


class TestFetchShipmentBlocks:
    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_basic_fetch(self, mock_snap, mock_db):
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_cur = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"block_section": "Inventory", "block_code": "DIST", "building_block": "DISTRIBUTION", "month_num": 1, "value_in_thousands": 5000.0},
        ]
        from services.variance_service import _fetch_cycle_shipment_blocks
        result, found = _fetch_cycle_shipment_blocks(["Motrin"], 2026, baseline_mode="CURRENT")
        assert len(result) > 0 and found is True

    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_empty_models(self, mock_snap, mock_db):
        from services.variance_service import _fetch_cycle_shipment_blocks
        result, found = _fetch_cycle_shipment_blocks([], 2026, baseline_mode="CURRENT")
        assert result == {} and found is False

    @patch("services.variance_service.get_db_cursor")
    @patch("services.variance_service.get_cycle_snapshot_ids")
    def test_bp_no_snapshot(self, mock_snap, mock_db):
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        from services.variance_service import _fetch_cycle_shipment_blocks
        result, found = _fetch_cycle_shipment_blocks(["Motrin"], 2026, baseline_mode="BP")
        assert found is False


class TestLoadConsumptionDrivers:
    @patch("services.variance_service._fetch_cycle_consumption_blocks")
    def test_ibp_mode(self, mock_fetch):
        from services.variance_service import load_consumption_variance_drivers
        mock_fetch.side_effect = [
            ({"BASE TREND": {1: 10.0, 2: 20.0}}, True),
            ({"BASE TREND": {1: 5.0, 2: 15.0}}, True),
        ]
        drivers, has = load_consumption_variance_drivers("Motrin", 2026, "IBP")
        assert "Base Trend" in drivers
        assert has is True
        assert drivers["Base Trend"][0] == pytest.approx(5.0)

    @patch("services.variance_service._fetch_cycle_consumption_blocks")
    def test_bp_missing(self, mock_fetch):
        from services.variance_service import load_consumption_variance_drivers
        mock_fetch.side_effect = [
            ({}, True),
            ({}, False),
        ]
        drivers, has = load_consumption_variance_drivers("Motrin", 2026, "BP")
        assert has is False

    @patch("services.variance_service._fetch_cycle_consumption_blocks")
    def test_empty_models(self, mock_fetch):
        from services.variance_service import load_consumption_variance_drivers
        drivers, has = load_consumption_variance_drivers(None, 2026, "IBP")
        assert has is True

    @patch("services.variance_service._fetch_cycle_consumption_blocks")
    def test_string_model(self, mock_fetch):
        from services.variance_service import load_consumption_variance_drivers
        mock_fetch.side_effect = [({}, True), ({}, True)]
        drivers, _ = load_consumption_variance_drivers("Motrin", 2026, "IBP")
        assert "Base Trend" in drivers

    @patch("services.variance_service._fetch_cycle_consumption_blocks")
    def test_list_models(self, mock_fetch):
        from services.variance_service import load_consumption_variance_drivers
        mock_fetch.side_effect = [({}, True), ({}, True)]
        drivers, _ = load_consumption_variance_drivers(["Motrin", "Tylenol"], 2026, "IBP")
        assert "Base Trend" in drivers

    @patch("services.variance_service._fetch_cycle_consumption_blocks")
    def test_compound_drivers(self, mock_fetch):
        from services.variance_service import load_consumption_variance_drivers
        mock_fetch.side_effect = [
            ({"INNOVATION": {1: 5.0}, "CANNIBALIZATION": {1: -2.0}, "PRICE": {1: 3.0}, "ELASTICITY": {1: -1.0}}, True),
            ({"INNOVATION": {1: 2.0}, "CANNIBALIZATION": {1: -1.0}, "PRICE": {1: 1.0}, "ELASTICITY": {1: 0.0}}, True),
        ]
        drivers, _ = load_consumption_variance_drivers("Motrin", 2026, "IBP")
        assert "Net Innovation" in drivers
        assert "Net Price" in drivers


class TestLoadShipmentDrivers:
    @patch("services.variance_service._fetch_cycle_shipment_blocks")
    def test_ibp_mode(self, mock_fetch):
        from services.variance_service import load_shipment_variance_drivers
        mock_fetch.side_effect = [
            ({"INVENTORY::DIST::DISTRIBUTION": {1: 10.0}}, True),
            ({"INVENTORY::DIST::DISTRIBUTION": {1: 3.0}}, True),
        ]
        drivers, has = load_shipment_variance_drivers("Motrin", 2026, "IBP")
        assert has is True
        assert "Distribution" in drivers

    @patch("services.variance_service._fetch_cycle_shipment_blocks")
    def test_bp_missing(self, mock_fetch):
        from services.variance_service import load_shipment_variance_drivers
        mock_fetch.side_effect = [({}, True), ({}, False)]
        _, has = load_shipment_variance_drivers("Motrin", 2026, "BP")
        assert has is False

    @patch("services.variance_service._fetch_cycle_shipment_blocks")
    def test_empty(self, mock_fetch):
        from services.variance_service import load_shipment_variance_drivers
        drivers, has = load_shipment_variance_drivers(None, 2026, "IBP")
        assert has is True

    @patch("services.variance_service._fetch_cycle_shipment_blocks")
    def test_string_model(self, mock_fetch):
        from services.variance_service import load_shipment_variance_drivers
        mock_fetch.side_effect = [({}, True), ({}, True)]
        drivers, _ = load_shipment_variance_drivers("Motrin", 2026, "IBP")
        assert "Distribution" in drivers


# ==============================================================================
# 12. variance_calculations: compute_*_variance_matrix (mocked service)
# ==============================================================================
class TestComputeConsumptionMatrix:
    @patch("services.variance_calculations.load_consumption_variance_drivers")
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations.get_active_years")
    def test_ibp_basic(self, mock_years, mock_snap, mock_load):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_years.return_value = (2025, 2026)
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        empty = {d: [None] * 12 for _, d, _ in CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS}
        mock_load.return_value = (empty, True)
        result = compute_consumption_variance_matrix("Motrin", "IBP")
        assert result["plan_year"] == 2026
        assert result["bp_missing"] is False
        assert "drivers" in result

    @patch("services.variance_calculations.load_consumption_variance_drivers")
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations.get_active_years")
    def test_bp_missing(self, mock_years, mock_snap, mock_load):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_years.return_value = (2025, 2026)
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        empty = {d: [None] * 12 for _, d, _ in CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS}
        mock_load.side_effect = [(empty, True), (empty, False)]
        result = compute_consumption_variance_matrix("Motrin", "BP")
        assert result["bp_missing"] is True

    @patch("services.variance_calculations.load_consumption_variance_drivers")
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations.get_active_years")
    def test_with_data(self, mock_years, mock_snap, mock_load):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_years.return_value = (2025, 2026)
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        drivers = {d: [0.5] * 12 for _, d, _ in CONSUMPTION_VARIANCE_DRIVER_DEFINITIONS}
        mock_load.return_value = (drivers, True)
        result = compute_consumption_variance_matrix(["Motrin"], "IBP")
        assert result["max_pos"] > 0 or result["max_neg_mag"] > 0
        assert result["totals_plan"] is not None


class TestComputeShipmentMatrix:
    @patch("services.variance_calculations.load_shipment_variance_drivers")
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations.get_active_years")
    def test_ibp_basic(self, mock_years, mock_snap, mock_load):
        from services.variance_calculations import compute_shipment_variance_matrix
        mock_years.return_value = (2025, 2026)
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        empty = {}
        for g, d, _ in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS:
            empty[d] = [None] * 12
            empty[(g, d)] = [None] * 12
            empty[f"{g}_{d}"] = [None] * 12
        mock_load.return_value = (empty, True)
        result = compute_shipment_variance_matrix("Motrin", "IBP")
        assert result["plan_year"] == 2026
        assert result["bp_missing"] is False

    @patch("services.variance_calculations.load_shipment_variance_drivers")
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations.get_active_years")
    def test_bp_missing(self, mock_years, mock_snap, mock_load):
        from services.variance_calculations import compute_shipment_variance_matrix
        mock_years.return_value = (2025, 2026)
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        empty = {}
        for g, d, _ in SHIPMENT_VARIANCE_DRIVER_DEFINITIONS:
            empty[d] = [None] * 12
            empty[(g, d)] = [None] * 12
            empty[f"{g}_{d}"] = [None] * 12
        mock_load.side_effect = [(empty, True), (empty, False)]
        result = compute_shipment_variance_matrix("Motrin", "BP")
        assert result["bp_missing"] is True


# ==============================================================================
# 13. variance_callbacks: handler functions (mocked callback_context)
# ==============================================================================
class TestSafeGetSquadsByGbu:
    @patch("callbacks.variance_callbacks.get_squads_by_gbu")
    def test_returns_data(self, mock_sq):
        from callbacks.variance_callbacks import _safe_get_squads_by_gbu
        mock_sq.return_value = [{"squad_name": "PAIN"}]
        assert _safe_get_squads_by_gbu(["PC"]) == [{"squad_name": "PAIN"}]

    @patch("callbacks.variance_callbacks.get_squads_by_gbu")
    def test_returns_none(self, mock_sq):
        from callbacks.variance_callbacks import _safe_get_squads_by_gbu
        mock_sq.return_value = None
        assert _safe_get_squads_by_gbu(["PC"]) == []

    @patch("callbacks.variance_callbacks.get_squads_by_gbu")
    def test_exception(self, mock_sq):
        from callbacks.variance_callbacks import _safe_get_squads_by_gbu
        mock_sq.side_effect = KeyError("fail")
        assert _safe_get_squads_by_gbu(["PC"]) == []


class TestGetModelsForSquads:
    @patch("callbacks.variance_callbacks.get_models_by_squad")
    def test_returns_data(self, mock_mq):
        from callbacks.variance_callbacks import _get_models_for_squads
        mock_mq.return_value = [{"model_id": 1, "model_name": "Motrin"}]
        result = _get_models_for_squads(["PAIN"], ["PC"])
        assert len(result) == 1

    @patch("callbacks.variance_callbacks.get_models_by_squad")
    def test_empty_squads(self, mock_mq):
        from callbacks.variance_callbacks import _get_models_for_squads
        assert _get_models_for_squads([], None) == []

    @patch("callbacks.variance_callbacks.get_models_by_squad")
    def test_filters_select_squad(self, mock_mq):
        from callbacks.variance_callbacks import _get_models_for_squads
        assert _get_models_for_squads(["Select Squad"], None) == []

    @patch("callbacks.variance_callbacks.get_models_by_squad")
    def test_deduplicates(self, mock_mq):
        from callbacks.variance_callbacks import _get_models_for_squads
        mock_mq.return_value = [{"model_id": 1, "model_name": "Motrin"}]
        result = _get_models_for_squads(["PAIN", "ESSENTIAL"], ["PC"])
        assert len(result) == 1

    @patch("callbacks.variance_callbacks.get_models_by_squad")
    def test_exception_handled(self, mock_mq):
        from callbacks.variance_callbacks import _get_models_for_squads
        mock_mq.side_effect = KeyError("fail")
        assert _get_models_for_squads(["PAIN"], None) == []


class TestHandleVarModeSelection:
    @patch("callbacks.variance_callbacks.callback_context")
    def test_change_to_bp(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_mode_selection
        mock_ctx.triggered_id = {"type": "var-mode-btn", "mode": "BP"}
        result = handle_var_mode_selection([1], "IBP")
        assert result[0] == "BP"

    @patch("callbacks.variance_callbacks.callback_context")
    def test_same_mode_no_update(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_mode_selection
        from dash import no_update
        mock_ctx.triggered_id = {"type": "var-mode-btn", "mode": "IBP"}
        result = handle_var_mode_selection([1], "IBP")
        assert result[0] is no_update

    @patch("callbacks.variance_callbacks.callback_context")
    def test_no_clicks(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_mode_selection
        from dash import no_update
        mock_ctx.triggered_id = "not-a-dict"
        result = handle_var_mode_selection([0], "IBP")
        assert result[0] is no_update

    @patch("callbacks.variance_callbacks.callback_context")
    def test_change_to_ibp(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_mode_selection
        mock_ctx.triggered_id = {"type": "var-mode-btn", "mode": "IBP"}
        result = handle_var_mode_selection([1], "BP")
        assert result[0] == "IBP"


class TestHandleVarAutoLoadGrid:
    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_consumption_basic(self, mock_fiscal, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_cons.return_value = {
            "plan_year": 2026, "base_year": 2025, "bp_missing": False,
            "drivers": {"Base Trend": [0.1] * 12}, "driver_totals": {},
            "base_row_vals": [None] * 12, "plan_row_vals": [None] * 12,
            "totals_base": {}, "totals_plan": {},
            "max_pos": 1.0, "max_neg_mag": 1.0,
            "label_base": "2025", "label_plan": "2026",
        }
        result = handle_var_auto_load_grid(["Motrin"], "consumption", ["PAIN"], "IBP", None)
        assert result is not None
        assert len(result) == 6

    @patch("callbacks.variance_callbacks.compute_shipment_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_shipment_basic(self, mock_fiscal, mock_ship):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_ship.return_value = {
            "plan_year": 2026, "base_year": 2025, "bp_missing": False,
            "drivers": {}, "driver_totals": {},
            "base_row_vals": [None] * 12, "plan_row_vals": [None] * 12,
            "totals_base": {}, "totals_plan": {},
            "max_pos": 1.0, "max_neg_mag": 1.0,
            "label_base": "2025", "label_plan": "2026",
        }
        result = handle_var_auto_load_grid(["Motrin"], "shipment", ["PAIN"], "IBP", None)
        assert result is not None

    def test_none_model(self):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        from dash import no_update
        result = handle_var_auto_load_grid(None, "consumption", None, "IBP", None)
        assert result[0] is no_update

    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_empty_squad(self, mock_fiscal):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        result = handle_var_auto_load_grid(["Motrin"], "consumption", [], "IBP", None)
        assert "squad" in str(result[1]).lower()

    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_empty_model(self, mock_fiscal):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        result = handle_var_auto_load_grid([], "consumption", ["PAIN"], "IBP", None)
        assert "model" in str(result[1]).lower()

    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_exception_handled(self, mock_fiscal, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_cons.side_effect = Exception("DB error")
        result = handle_var_auto_load_grid(["Motrin"], "consumption", ["PAIN"], "IBP", None)
        assert "Error" in str(result[1])

    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_consolidated_models(self, mock_fiscal, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_cons.return_value = {
            "plan_year": 2026, "base_year": 2025, "bp_missing": False,
            "drivers": {}, "driver_totals": {},
            "base_row_vals": [None] * 12, "plan_row_vals": [None] * 12,
            "totals_base": {}, "totals_plan": {},
            "max_pos": 1.0, "max_neg_mag": 1.0,
            "label_base": "2025", "label_plan": "2026",
        }
        result = handle_var_auto_load_grid(["Motrin", "Tylenol"], "consumption", ["PAIN"], "IBP", None)
        assert "Consolidated" in result[3]


class TestSyncInitialModel:
    def test_has_session_data(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        from dash import no_update
        result = sync_variance_initial_model_to_session(["Motrin"], ["PAIN"], {"model_id": 1})
        assert result is no_update

    def test_no_session_seeds(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        result = sync_variance_initial_model_to_session(["Motrin"], ["PAIN"], None)
        assert isinstance(result, dict)
        assert result["model_name"] == "Motrin"
        assert result["source"] == "variance"

    def test_no_model_no_update(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        from dash import no_update
        result = sync_variance_initial_model_to_session(None, ["PAIN"], None)
        assert result is no_update

    def test_empty_model_no_update(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        from dash import no_update
        result = sync_variance_initial_model_to_session([], [], None)
        assert result is no_update

    def test_select_model_no_update(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        from dash import no_update
        result = sync_variance_initial_model_to_session("Select Model", "Select Squad", None)
        assert result is no_update

    def test_multiple_models(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        result = sync_variance_initial_model_to_session(["A", "B"], ["SQ"], None)
        assert result["selected_models"] == ["A", "B"]


class TestHandleVarDomainToggle:
    @patch("callbacks.variance_callbacks._get_models_for_squads")
    @patch("callbacks.variance_callbacks.get_ad_group_mapping")
    @patch("callbacks.variance_callbacks.callback_context")
    def test_to_shipment(self, mock_ctx, mock_map, mock_models):
        from callbacks.variance_callbacks import handle_var_domain_toggle
        mock_ctx.triggered_id = "card-var-shipment"
        mock_map.return_value = {"gbu_codes": ["PC"]}
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin", "has_shipment": True, "has_pos": True}]
        result = handle_var_domain_toggle(0, 1, "consumption", "COM-APP-NA-IBP-SELFCARE", ["PAIN"], ["Motrin"])
        assert result[4] == "shipment"

    @patch("callbacks.variance_callbacks._get_models_for_squads")
    @patch("callbacks.variance_callbacks.get_ad_group_mapping")
    @patch("callbacks.variance_callbacks.callback_context")
    def test_to_consumption(self, mock_ctx, mock_map, mock_models):
        from callbacks.variance_callbacks import handle_var_domain_toggle
        mock_ctx.triggered_id = "card-var-consumption"
        mock_map.return_value = {"gbu_codes": ["PC"]}
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin", "has_shipment": True, "has_pos": True}]
        result = handle_var_domain_toggle(1, 0, "shipment", "COM-APP-NA-IBP-SELFCARE", ["PAIN"], ["Motrin"])
        assert result[4] == "consumption"


class TestHandleVarSquadStaging:
    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    @patch("callbacks.variance_callbacks._resolve_staging_gbu_codes")
    @patch("callbacks.variance_callbacks.callback_context")
    def test_select_item(self, mock_ctx, mock_gbu, mock_squads):
        from callbacks.variance_callbacks import handle_var_squad_staging
        mock_ctx.triggered_id = {"type": "var-squad-select-item", "name": "PAIN"}
        mock_gbu.return_value = ["PC"]
        mock_squads.return_value = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        result = handle_var_squad_staging([1], [0], None, ["PAIN"], "COM-APP-NA-IBP-SELFCARE")
        assert result is not None

    @patch("callbacks.variance_callbacks.callback_context")
    def test_no_clicks(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_squad_staging
        from dash import no_update
        mock_ctx.triggered_id = {}
        result = handle_var_squad_staging([0], [0], None, [], "COM-APP-NA-IBP-SELFCARE")
        assert result[0] is no_update


class TestHandleVarModelStaging:
    @patch("callbacks.variance_callbacks._resolve_available_staging_models")
    @patch("callbacks.variance_callbacks.callback_context")
    def test_select_item(self, mock_ctx, mock_avail):
        from callbacks.variance_callbacks import handle_var_model_staging
        mock_ctx.triggered_id = {"type": "var-model-select-item", "name": "Motrin"}
        mock_avail.return_value = [{"model_id": 1, "model_name": "Motrin"}]
        result = handle_var_model_staging([1], [0], None, ["Motrin"], "COM-APP-NA-IBP-SELFCARE", "consumption", ["PAIN"])
        assert result is not None

    @patch("callbacks.variance_callbacks.callback_context")
    def test_no_clicks(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_model_staging
        from dash import no_update
        mock_ctx.triggered_id = {}
        result = handle_var_model_staging([0], [0], None, [], "KEY", "consumption", [])
        assert result[0] is no_update


class TestHandleVarSquadApply:
    @patch("callbacks.variance_callbacks._resolve_var_model_selection")
    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    @patch("callbacks.variance_callbacks._resolve_staging_gbu_codes")
    @patch("callbacks.variance_callbacks.callback_context")
    def test_apply(self, mock_ctx, mock_gbu, mock_squads, mock_model_sel):
        from callbacks.variance_callbacks import handle_var_squad_apply
        mock_ctx.triggered_id = {"type": "var-squad-action", "action": "apply"}
        mock_gbu.return_value = ["PC"]
        mock_squads.return_value = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        mock_model_sel.return_value = (["Motrin"], 1, [], "Motrin")
        result = handle_var_squad_apply([1], ["PAIN"], ["PAIN"], ["Motrin"], "COM-APP-NA-IBP-SELFCARE", "consumption")
        assert result is not None and len(result) == 9

    @patch("callbacks.variance_callbacks.callback_context")
    def test_not_apply(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_squad_apply
        from dash import no_update
        mock_ctx.triggered_id = {"type": "var-squad-action", "action": "reset"}
        result = handle_var_squad_apply([1], None, [], [], "KEY", "consumption")
        assert result[0] is no_update


class TestHandleVarModelApply:
    @patch("callbacks.variance_callbacks._resolve_available_staging_models")
    @patch("callbacks.variance_callbacks.callback_context")
    def test_apply(self, mock_ctx, mock_avail):
        from callbacks.variance_callbacks import handle_var_model_apply
        mock_ctx.triggered_id = {"type": "var-model-action", "action": "apply"}
        mock_avail.return_value = [{"model_id": 1, "model_name": "Motrin", "squad_name": "PAIN"}]
        result = handle_var_model_apply([1], ["Motrin"], ["Motrin"], ["PAIN"], "COM-APP-NA-IBP-SELFCARE", "consumption")
        assert result is not None and len(result) == 5

    @patch("callbacks.variance_callbacks.callback_context")
    def test_not_apply(self, mock_ctx):
        from callbacks.variance_callbacks import handle_var_model_apply
        from dash import no_update
        mock_ctx.triggered_id = {"type": "var-model-action", "action": "reset"}
        result = handle_var_model_apply([0], None, [], [], "KEY", "consumption")
        assert result[0] is no_update


class TestSyncSessionToVariance:
    def test_not_on_variance_page(self):
        from callbacks.variance_callbacks import sync_session_to_variance
        from dash import no_update
        result = sync_session_to_variance("/summary", None, None, None, [], [], "consumption")
        assert result is no_update

    def test_no_pathname(self):
        from callbacks.variance_callbacks import sync_session_to_variance
        from dash import no_update
        result = sync_session_to_variance(None, None, None, None, [], [], "consumption")
        assert result is no_update

    @patch("callbacks.variance_callbacks._resolve_var_model_selection")
    @patch("callbacks.variance_callbacks._resolve_var_squad_selection")
    @patch("callbacks.variance_callbacks._build_variance_user_identity_elem")
    @patch("callbacks.variance_callbacks.set_user_session")
    @patch("callbacks.variance_callbacks.get_current_user")
    @patch("callbacks.variance_callbacks.get_ad_group_mapping")
    @patch("callbacks.variance_callbacks.build_var_ad_switcher_menu_items")
    def test_on_variance_with_session_ad(self, mock_ad_items, mock_map, mock_user, mock_set, mock_email, mock_squad_sel, mock_model_sel):
        from callbacks.variance_callbacks import sync_session_to_variance
        mock_map.return_value = {"gbu_codes": ["PC"]}
        mock_user.return_value = {"ad_group": "COM-APP-NA-IBP-SELFCARE"}
        mock_email.return_value = [html.Span("user"), html.Span("email")]
        mock_squad_sel.return_value = (["PAIN"], "Pain Care", [])
        mock_model_sel.return_value = (["Motrin"], 1, [], "Motrin")
        mock_ad_items.return_value = []
        result = sync_session_to_variance(
            "/variance",
            {"model_name": "Motrin", "squad_name": "PAIN", "source": "summary"},
            {"persona_key": "COM-APP-NA-IBP-SELFCARE", "source": "summary"},
            "COM-APP-NA-IBP-SELFCARE", ["OLD"], ["OLD"], "consumption"
        )
        assert result is not None and len(result) == 14

    @patch("callbacks.variance_callbacks._resolve_var_model_selection")
    @patch("callbacks.variance_callbacks._resolve_var_squad_selection")
    @patch("callbacks.variance_callbacks._build_variance_user_identity_elem")
    @patch("callbacks.variance_callbacks.get_ad_group_mapping")
    @patch("callbacks.variance_callbacks.build_var_ad_switcher_menu_items")
    def test_on_variance_model_only(self, mock_ad_items, mock_map, mock_email, mock_squad_sel, mock_model_sel):
        from callbacks.variance_callbacks import sync_session_to_variance
        from dash import no_update
        mock_map.return_value = {"gbu_codes": ["PC"]}
        mock_email.return_value = [html.Span("u"), html.Span("e")]
        mock_squad_sel.return_value = (["PAIN"], "Pain Care", [])
        mock_model_sel.return_value = (["Motrin"], 1, [], "Motrin")
        mock_ad_items.return_value = []
        result = sync_session_to_variance(
            "/variance",
            {"model_name": "Motrin", "squad_name": "PAIN", "source": "summary"},
            None,
            "COM-APP-NA-IBP-SELFCARE", ["PAIN"], ["Motrin"], "consumption"
        )
        assert result is not None
