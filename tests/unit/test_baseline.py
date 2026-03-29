from sraosha.drift.baseline import BaselineComputer


class TestBaselineComputer:
    def test_empty_values(self):
        computer = BaselineComputer(window_size=14)
        stats = computer.compute([], breach_threshold=0.05)
        assert stats.mean == 0.0
        assert stats.std_dev == 0.0
        assert stats.trend_slope == 0.0
        assert stats.is_trending_to_breach is False

    def test_stable_values(self):
        values = [0.01, 0.01, 0.01, 0.01, 0.01]
        computer = BaselineComputer(window_size=14)
        stats = computer.compute(values, breach_threshold=0.05)

        assert abs(stats.mean - 0.01) < 0.001
        assert stats.std_dev < 0.001
        assert abs(stats.trend_slope) < 0.001
        assert stats.is_trending_to_breach is False

    def test_rising_trend_detects_breach(self):
        values = [0.01, 0.015, 0.02, 0.025, 0.03]
        computer = BaselineComputer(window_size=14)
        stats = computer.compute(values, breach_threshold=0.05)

        assert stats.trend_slope > 0
        assert stats.is_trending_to_breach is True
        assert stats.estimated_breach_in_runs is not None
        assert stats.estimated_breach_in_runs > 0

    def test_already_breached(self):
        values = [0.04, 0.045, 0.05, 0.055, 0.06]
        computer = BaselineComputer(window_size=14)
        stats = computer.compute(values, breach_threshold=0.05)

        assert stats.is_trending_to_breach is True
        assert stats.estimated_breach_in_runs == 0

    def test_declining_trend_no_breach(self):
        values = [0.04, 0.035, 0.03, 0.025, 0.02]
        computer = BaselineComputer(window_size=14)
        stats = computer.compute(values, breach_threshold=0.05)

        assert stats.trend_slope < 0
        assert stats.is_trending_to_breach is False

    def test_window_size_limits(self):
        values = list(range(20))
        computer = BaselineComputer(window_size=5)
        stats = computer.compute(values)

        assert abs(stats.mean - 17.0) < 0.001  # mean of [15,16,17,18,19]

    def test_compute_for_contract(self):
        computer = BaselineComputer(window_size=14)
        history = {
            "orders.customer_id.null_rate": [0.01, 0.015, 0.02, 0.025, 0.03],
            "orders.null.row_count": [1000, 1010, 1020, 1030, 1040],
        }
        thresholds = {
            "orders.customer_id.null_rate": 0.05,
        }

        results = computer.compute_for_contract(history, thresholds)
        assert "orders.customer_id.null_rate" in results
        assert "orders.null.row_count" in results
        assert results["orders.customer_id.null_rate"].is_trending_to_breach is True
