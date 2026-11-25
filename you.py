

# ==============================================================================
# 11. variance_calculations: compute_*_variance_matrix (mocked DB)
# ==============================================================================
class TestComputeConsumptionVarianceMatrix:
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_consumption_blocks")
    def test_ibp_mode_basic(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.return_value = {}
        result = compute_consumption_variance_matrix("Children's Motrin", "IBP")
        assert "drivers" in result
        assert "plan_year" in result
        assert result["bp_missing"] is False

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_consumption_blocks")
    def test_bp_mode_missing(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.return_value = {}
        result = compute_consumption_variance_matrix("Children's Motrin", "BP")
        assert result["bp_missing"] is True

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_consumption_blocks")
    def test_bp_mode_with_snap(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, 10, None, 11)
        mock_fetch.return_value = {}
        result = compute_consumption_variance_matrix("Children's Motrin", "BP")
        assert result["bp_missing"] is False

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_consumption_blocks")
    def test_list_models(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.return_value = {}
        result = compute_consumption_variance_matrix(["Children's Motrin", "Tylenol"], "IBP")
        assert "drivers" in result

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_consumption_blocks")
    def test_with_data(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.side_effect = [
            {"BASE TREND VALUE": {1: 10.0, 2: 20.0, 3: 15.0}},
            {"BASE TREND VALUE": {1: 5.0, 2: 10.0, 3: 8.0}},
        ]
        result = compute_consumption_variance_matrix("Children's Motrin", "IBP")
        assert result["drivers"]["Base Trend"][0] == pytest.approx(5.0)

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_consumption_blocks")
    def test_no_prior_snapshot(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_consumption_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, None, 3, 4, None, None, 11)
        mock_fetch.return_value = {}
        result = compute_consumption_variance_matrix("Children's Motrin", "IBP")
        assert "drivers" in result


class TestComputeShipmentVarianceMatrix:
    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_shipment_blocks")
    def test_ibp_mode_basic(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_shipment_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.return_value = {}
        result = compute_shipment_variance_matrix("Children's Motrin", "IBP")
        assert "drivers" in result
        assert result["bp_missing"] is False

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_shipment_blocks")
    def test_bp_mode_missing(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_shipment_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.return_value = {}
        result = compute_shipment_variance_matrix("Children's Motrin", "BP")
        assert result["bp_missing"] is True

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_shipment_blocks")
    def test_bp_mode_with_snap(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_shipment_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, 10, 11)
        mock_fetch.return_value = {}
        result = compute_shipment_variance_matrix("Children's Motrin", "BP")
        assert result["bp_missing"] is False

    @patch("services.variance_calculations.get_cycle_snapshot_ids")
    @patch("services.variance_calculations._fetch_cycle_shipment_blocks")
    def test_with_data(self, mock_fetch, mock_snap):
        from services.variance_calculations import compute_shipment_variance_matrix
        mock_snap.return_value = CycleSnapshotInfo(1, 2, 3, 4, None, None, 11)
        mock_fetch.side_effect = [
            {"INVENTORY::DIST::DISTRIBUTION": {1: 10.0}},
            {"INVENTORY::DIST::DISTRIBUTION": {1: 3.0}},
        ]
        result = compute_shipment_variance_matrix("Children's Motrin", "IBP")
        assert "drivers" in result


# ==============================================================================
# 12. variance_service: DB-dependent functions (mocked)
# ==============================================================================
class TestGetCycleSnapshotIds:
    @patch("services.variance_service.get_db_connection")
    def test_returns_snapshot_info(self, mock_conn):
        from services.variance_service import get_cycle_snapshot_ids
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1, 11),    # active cycle
            (100,),     # current cons snap
            (200,),     # current ship snap
            (90,),      # prior cons snap
            (190,),     # prior ship snap
            None,       # bp cons snap
            None,       # bp ship snap
        ]
        mock_cursor.fetchall.return_value = []
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = get_cycle_snapshot_ids("Children's Motrin")
        assert result is not None
        assert result.cs_id == 100

    @patch("services.variance_service.get_db_connection")
    def test_no_active_cycle(self, mock_conn):
        from services.variance_service import get_cycle_snapshot_ids
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = get_cycle_snapshot_ids("Children's Motrin")
        assert result is not None


class TestFetchBlocks:
    @patch("services.variance_service.get_db_connection")
    def test_fetch_consumption_blocks(self, mock_conn):
        from services.variance_service import _fetch_cycle_consumption_blocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("BASE TREND VALUE", date(2026, 1, 1), 10.5),
            ("BASE TREND VALUE", date(2026, 2, 1), 20.3),
        ]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = _fetch_cycle_consumption_blocks("snapshot_id = 1", "Children's Motrin", 2026)
        assert "BASE TREND VALUE" in result
        assert 1 in result["BASE TREND VALUE"]

    @patch("services.variance_service.get_db_connection")
    def test_fetch_consumption_no_rows(self, mock_conn):
        from services.variance_service import _fetch_cycle_consumption_blocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = _fetch_cycle_consumption_blocks("snapshot_id = 1", "Children's Motrin", 2026)
        assert result == {}

    @patch("services.variance_service.get_db_connection")
    def test_fetch_shipment_blocks(self, mock_conn):
        from services.variance_service import _fetch_cycle_shipment_blocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("Inventory", "DIST_CODE", "DISTRIBUTION", date(2026, 1, 1), 5.0),
        ]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = _fetch_cycle_shipment_blocks("snapshot_id = 1", "Children's Motrin", 2026)
        assert len(result) > 0

    @patch("services.variance_service.get_db_connection")
    def test_fetch_shipment_no_rows(self, mock_conn):
        from services.variance_service import _fetch_cycle_shipment_blocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = _fetch_cycle_shipment_blocks("snapshot_id = 1", "Children's Motrin", 2026)
        assert result == {}

    @patch("services.variance_service.get_db_connection")
    def test_fetch_consumption_multi_model(self, mock_conn):
        from services.variance_service import _fetch_cycle_consumption_blocks
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("SEASON VALUE", date(2026, 3, 1), 1.5),
        ]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = _fetch_cycle_consumption_blocks("snapshot_id = 1", ["A", "B"], 2026)
        assert "SEASON VALUE" in result


class TestGetActiveYears:
    @patch("services.variance_service.get_db_connection")
    def test_returns_years(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(2025,), (2026,)]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        result = get_active_years()
        assert 2026 in result

    @patch("services.variance_service.get_db_connection")
    def test_empty(self, mock_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value = ctx
        assert get_active_years() == []


# ==============================================================================
# 13. variance_callbacks: Dash callback handlers (mocked)
# ==============================================================================
class TestVarianceCallbackHandlers:
    @patch("callbacks.variance_callbacks._safe_get_personas_for_user")
    def test_handle_var_ad_persona(self, mock_personas):
        from callbacks.variance_callbacks import handle_var_ad_persona
        mock_personas.return_value = [
            {"ad_group": "COM-APP-NA-IBP-SELFCARE", "display_name": "Self Care", "gbu_codes": ["SC"]}
        ]
        result = handle_var_ad_persona("user@test.com")
        assert result is not None
        assert len(result) == 5

    @patch("callbacks.variance_callbacks._safe_get_personas_for_user")
    def test_handle_var_ad_persona_empty(self, mock_personas):
        from callbacks.variance_callbacks import handle_var_ad_persona
        mock_personas.return_value = []
        result = handle_var_ad_persona("user@test.com")
        assert result is not None

    @patch("callbacks.variance_callbacks._safe_get_personas_for_user")
    def test_handle_var_ad_persona_none(self, mock_personas):
        from callbacks.variance_callbacks import handle_var_ad_persona
        mock_personas.return_value = None
        result = handle_var_ad_persona("user@test.com")
        assert result is not None

    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    def test_handle_var_squad_staging(self, mock_squads):
        from callbacks.variance_callbacks import handle_var_squad_staging
        mock_squads.return_value = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        trigger = {"type": "var-squad-select-item", "name": "PAIN"}
        result = handle_var_squad_staging(
            [1], [0], trigger, ["PAIN"], None, ["PAIN"],
            "COM-APP-NA-IBP-SELFCARE", "consumption", ["PAIN"]
        )
        assert result is not None

    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    def test_handle_var_squad_staging_inactive(self, mock_squads):
        from callbacks.variance_callbacks import handle_var_squad_staging
        from dash.exceptions import PreventUpdate
        with pytest.raises(PreventUpdate):
            handle_var_squad_staging(
                [0], [0], {}, [], None, [],
                "COM-APP-NA-IBP-SELFCARE", "consumption", []
            )

    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    @patch("callbacks.variance_callbacks._safe_get_models_for_squads")
    def test_handle_var_squad_apply(self, mock_models, mock_squads):
        from callbacks.variance_callbacks import handle_var_squad_apply
        mock_squads.return_value = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin", "squad_name": "PAIN"}]
        result = handle_var_squad_apply(
            1, ["PAIN"], "COM-APP-NA-IBP-SELFCARE",
            "consumption", None, ["PAIN"]
        )
        assert result is not None

    @patch("callbacks.variance_callbacks._safe_get_models_for_squads")
    def test_handle_var_model_staging(self, mock_models):
        from callbacks.variance_callbacks import handle_var_model_staging
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin"}]
        trigger = {"type": "var-model-select-item", "name": "Motrin"}
        result = handle_var_model_staging(
            [1], [0], trigger, ["Motrin"], ["PAIN"], None,
            "COM-APP-NA-IBP-SELFCARE", "consumption", ["Motrin"]
        )
        assert result is not None

    @patch("callbacks.variance_callbacks._safe_get_models_for_squads")
    def test_handle_var_model_apply(self, mock_models):
        from callbacks.variance_callbacks import handle_var_model_apply
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin", "squad_name": "PAIN"}]
        result = handle_var_model_apply(
            1, ["Motrin"], ["PAIN"], "COM-APP-NA-IBP-SELFCARE",
            "consumption", None, ["Motrin"]
        )
        assert result is not None

    def test_handle_var_domain_toggle_consumption(self):
        from callbacks.variance_callbacks import handle_var_domain_toggle
        result = handle_var_domain_toggle(1, 0)
        assert result is not None
        assert result[0] == "consumption"

    def test_handle_var_domain_toggle_shipment(self):
        from callbacks.variance_callbacks import handle_var_domain_toggle
        result = handle_var_domain_toggle(0, 1)
        assert result is not None
        assert result[0] == "shipment"

    def test_handle_var_domain_toggle_default(self):
        from callbacks.variance_callbacks import handle_var_domain_toggle
        result = handle_var_domain_toggle(0, 0)
        assert result[0] == "consumption"

    def test_handle_var_mode_select_ibp(self):
        from callbacks.variance_callbacks import handle_var_mode_select
        result = handle_var_mode_select("IBP")
        assert result is not None

    def test_handle_var_mode_select_bp(self):
        from callbacks.variance_callbacks import handle_var_mode_select
        result = handle_var_mode_select("BP")
        assert result is not None

    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks.compute_shipment_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_handle_var_auto_load_grid(self, mock_fiscal, mock_ship, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_cons.return_value = {
            "plan_year": 2026, "base_year": 2025,
            "drivers": {"Base Trend": [0.1] * 12},
            "driver_totals": {}, "base_row_vals": [None] * 12,
            "plan_row_vals": [None] * 12, "totals_base": {},
            "totals_plan": {}, "max_pos": 1.0, "max_neg_mag": 1.0,
            "bp_missing": False, "label_base": "2025", "label_plan": "2026",
        }
        mock_ship.return_value = mock_cons.return_value
        result = handle_var_auto_load_grid(
            ["Motrin"], ["PAIN"], "consumption", "IBP",
            "COM-APP-NA-IBP-SELFCARE", None
        )
        assert result is not None

    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_handle_var_auto_load_grid_cached(self, mock_fiscal, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid, _VAR_CACHE, _VAR_CACHE_TS
        import time
        cache_key = "test_cached_key"
        _VAR_CACHE[cache_key] = {
            "plan_year": 2026, "base_year": 2025,
            "drivers": {}, "driver_totals": {}, "base_row_vals": [None] * 12,
            "plan_row_vals": [None] * 12, "totals_base": {}, "totals_plan": {},
            "max_pos": 1.0, "max_neg_mag": 1.0, "bp_missing": False,
            "label_base": "2025", "label_plan": "2026",
        }
        _VAR_CACHE_TS[cache_key] = time.time()
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_cons.return_value = _VAR_CACHE[cache_key]
        # won't actually use the cache key since model names differ
        result = handle_var_auto_load_grid(
            ["Motrin"], ["PAIN"], "consumption", "IBP",
            "COM-APP-NA-IBP-SELFCARE", None
        )
        assert result is not None

    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_handle_var_auto_load_grid_no_model(self, mock_fiscal, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        from dash.exceptions import PreventUpdate
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        with pytest.raises(PreventUpdate):
            handle_var_auto_load_grid(
                [], [], "consumption", "IBP",
                "COM-APP-NA-IBP-SELFCARE", None
            )

    @patch("callbacks.variance_callbacks.compute_shipment_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_handle_var_auto_load_grid_shipment(self, mock_fiscal, mock_ship):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_ship.return_value = {
            "plan_year": 2026, "base_year": 2025,
            "drivers": {}, "driver_totals": {}, "base_row_vals": [None] * 12,
            "plan_row_vals": [None] * 12, "totals_base": {}, "totals_plan": {},
            "max_pos": 1.0, "max_neg_mag": 1.0, "bp_missing": False,
            "label_base": "2025", "label_plan": "2026",
        }
        result = handle_var_auto_load_grid(
            ["Motrin"], ["PAIN"], "shipment", "IBP",
            "COM-APP-NA-IBP-SELFCARE", None
        )
        assert result is not None


# ==============================================================================
# 14. pages/variance: layout and remaining helpers
# ==============================================================================
class TestVariancePageLayout:
    def test_layout_function_exists(self):
        from pages.variance import layout
        result = layout()
        assert result is not None

    def test_layout_returns_div(self):
        from pages.variance import layout
        result = layout()
        assert hasattr(result, 'children')

    def test_build_ad_switcher_all_personas(self):
        personas = [
            "COM-APP-NA-IBP-SELFCARE",
            "COM-APP-NA-IBP-ESSENTIAL",
            "COM-APP-NA-IBP-SKINHEALTH",
        ]
        for p in personas:
            items = _build_ad_switcher_from_personas(p)
            assert len(items) > 0

    def test_build_mode_menu_items_structure(self):
        items = build_var_mode_menu_items("IBP")
        # header + 2 options
        assert len(items) == 3

    def test_squad_menu_multiple_gbus(self):
        squads = [
            {"squad_name": "A", "display_name": "A", "gbu": "X"},
            {"squad_name": "B", "display_name": "B", "gbu": "Y"},
        ]
        items = build_var_squad_menu_items(squads, active_squad_name=["A"])
        assert len(items) >= 3

    def test_model_menu_multiple_squads(self):
        models = [
            {"model_id": 1, "model_name": "M1", "squad_name": "S1"},
            {"model_id": 2, "model_name": "M2", "squad_name": "S2"},
        ]
        items = build_var_model_menu_items(models, active_model_name=["M1"])
        assert len(items) >= 3

    def test_render_empty_selection_various(self):
        for sel_type in ["squad", "model", "ad"]:
            for domain in ["CONSUMPTION", "SHIPMENT"]:
                card = render_empty_selection_card(sel_type, domain)
                assert card is not None

    def test_render_empty_domain_alert_domains(self):
        for domain in ["consumption", "shipment"]:
            alert = render_empty_domain_alert("Test Model", domain)
            assert alert is not None

    def test_ad_switcher_item_styles(self):
        active = _render_ad_switcher_item("k1", "Name", "Sub", True)
        inactive = _render_ad_switcher_item("k2", "Name", "Sub", False)
        assert active.className != inactive.className

    def test_squad_header_counts(self):
        for selected, total in [(0, 5), (3, 5), (5, 5)]:
            h = _build_var_squad_header(selected == total, selected, total)
            assert h is not None

    def test_model_header_counts(self):
        for selected, total in [(0, 10), (5, 10), (10, 10)]:
            h = _build_var_model_header(selected == total, selected, total)
            assert h is not None

    def test_squad_footer_counts(self):
        for count in [0, 1, 5]:
            f = _build_var_squad_footer(count)
            assert f is not None

    def test_model_footer_counts(self):
        for count in [0, 1, 5]:
            f = _build_var_model_footer(count)
            assert f is not None


# ==============================================================================
# 15. Additional variance_callbacks coverage
# ==============================================================================
class TestVarianceCallbackEdgeCases:
    def test_sync_session_initial_model(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        from dash.exceptions import PreventUpdate
        # already has session data
        with pytest.raises(PreventUpdate):
            sync_variance_initial_model_to_session(
                {"model_id": 1}, ["PAIN"], {"model_id": 1}
            )

    def test_sync_session_initial_model_seeds(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        result = sync_variance_initial_model_to_session(
            {"model_name": "Motrin", "model_id": 1, "squad_name": "PAIN"},
            ["PAIN"], None
        )
        assert result is not None

    def test_sync_session_initial_model_no_model(self):
        from callbacks.variance_callbacks import sync_variance_initial_model_to_session
        from dash.exceptions import PreventUpdate
        with pytest.raises(PreventUpdate):
            sync_variance_initial_model_to_session(None, [], None)

    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    @patch("callbacks.variance_callbacks._safe_get_models_for_squads")
    def test_sync_session_to_variance(self, mock_models, mock_squads):
        from callbacks.variance_callbacks import sync_session_to_variance
        from dash.exceptions import PreventUpdate
        mock_squads.return_value = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin", "squad_name": "PAIN"}]
        # not on variance page
        with pytest.raises(PreventUpdate):
            sync_session_to_variance(
                "/summary", {"model_name": "Motrin"}, None,
                "COM-APP-NA-IBP-SELFCARE", ["PAIN"], ["Motrin"], "consumption"
            )

    @patch("callbacks.variance_callbacks._build_squad_list_from_gbu")
    @patch("callbacks.variance_callbacks._safe_get_models_for_squads")
    def test_sync_session_to_variance_on_page(self, mock_models, mock_squads):
        from callbacks.variance_callbacks import sync_session_to_variance
        mock_squads.return_value = [{"squad_name": "PAIN", "display_name": "Pain", "gbu": "PC"}]
        mock_models.return_value = [{"model_id": 1, "model_name": "Motrin", "squad_name": "PAIN"}]
        result = sync_session_to_variance(
            "/variance",
            {"model_name": "Motrin", "squad_name": "PAIN", "source": "summary"},
            "COM-APP-NA-IBP-SELFCARE",
            "COM-APP-NA-IBP-SELFCARE", ["OLD"], ["OLD_MODEL"], "consumption"
        )
        assert result is not None
