    def test_no_pathname(self):
        from callbacks.variance_callbacks import sync_session_to_variance
        from dash import no_update
        result = sync_session_to_variance(None, None, None, None, [], [], "consumption")
        assert all(r is no_update for r in result)
