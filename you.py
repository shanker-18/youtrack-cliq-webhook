    @patch("callbacks.variance_callbacks.compute_consumption_variance_matrix")
    @patch("callbacks.variance_callbacks._get_var_fiscal_context")
    def test_exception_handled(self, mock_fiscal, mock_cons):
        from callbacks.variance_callbacks import handle_var_auto_load_grid
        clear_variance_cache()
        mock_fiscal.return_value = ("Fiscal Dec 2026", "Dec 2026")
        mock_cons.side_effect = Exception("DB error")
        result = handle_var_auto_load_grid(["Motrin"], "consumption", ["PAIN"], "IBP", None)
        assert "Error" in str(result[1])
