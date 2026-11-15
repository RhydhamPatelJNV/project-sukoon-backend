import os
import sys
import unittest

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.research.registry import StrategyRegistry, StrategySpec
from sukoon.research.backtest import BacktestEngine
from sukoon.research.validation import ValidationEngine

class TestResearchAndValidation(unittest.TestCase):
    def test_strategy_spec_and_registry_immutability(self):
        registry = StrategyRegistry()
        spec = StrategySpec.create(
            strategy_id="mean_reversion_spy",
            version="1.0.0",
            name="SPY 5m Mean Reversion",
            description="Mean reversion using RSI and Bollinger bands",
            universe=["SPY"],
            timeframe="5m",
            parameters={"period": 14, "std_dev": 2.0},
            source_code="def run_strategy(): pass"
        )
        registry.register(spec)

        retrieved = registry.get_spec("mean_reversion_spy", "1.0.0")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.strategy_id, "mean_reversion_spy")
        self.assertTrue(retrieved.code_hash)

        # Re-registering identical version must raise ValueError (Immutability)
        with self.assertRaises(ValueError):
            registry.register(spec)

    def test_backtest_metrics_calculation(self):
        # 10 trade returns: 7 positive, 3 negative
        returns = [0.015, -0.005, 0.020, 0.010, -0.010, 0.008, 0.012, 0.025, -0.004, 0.018]
        metrics = BacktestEngine.calculate_metrics(returns)

        self.assertEqual(metrics.total_trades, 10)
        self.assertEqual(metrics.winning_trades, 7)
        self.assertEqual(metrics.losing_trades, 3)
        self.assertEqual(metrics.win_rate, 0.70)
        self.assertGreater(metrics.sharpe_ratio, 1.0)
        self.assertGreater(metrics.profit_factor, 1.0)

    def test_walk_forward_evaluation(self):
        # Robust strategy: similar performance in IS and OOS
        is_ret = [0.01, 0.012, -0.004, 0.015, 0.008] * 10
        oos_ret = [0.009, 0.011, -0.005, 0.014, 0.007] * 10

        wf_result = ValidationEngine.evaluate_walk_forward(is_ret, oos_ret, min_wfe_threshold=0.60)
        self.assertTrue(wf_result.is_valid)
        self.assertGreaterEqual(wf_result.walk_forward_efficiency, 0.60)

    def test_deflated_sharpe_ratio_haircut(self):
        # 1 trial vs 100 trials: with 100 trials, DSR reduces significance if Sharpe is moderate
        dsr_1 = ValidationEngine.calculate_deflated_sharpe(
            observed_sharpe=2.5,
            trials_count=1,
            sample_length=252,
            skewness=0.0,
            kurtosis=3.0
        )
        self.assertTrue(dsr_1.is_statistically_significant)
        self.assertGreaterEqual(dsr_1.deflated_sharpe_p_value, 0.95)

        # With 500 trials of data mining, a Sharpe of 1.0 is NOT statistically significant
        dsr_500 = ValidationEngine.calculate_deflated_sharpe(
            observed_sharpe=1.0,
            trials_count=500,
            sample_length=252
        )
        self.assertFalse(dsr_500.is_statistically_significant)
        self.assertLess(dsr_500.haircut_sharpe, 1.0)

if __name__ == "__main__":
    unittest.main()
