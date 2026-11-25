    def test_tiny_value_shows_zero(self):
        assert fmt_variance_number(0.001) == "0.00"

    def test_very_tiny_value_shows_zero(self):
        assert fmt_variance_number(0.00004) == "0.00"
