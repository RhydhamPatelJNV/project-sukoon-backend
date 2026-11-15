"""
Project Sukoon — Statistical Validation & Promotion Gates (G10)
Walk-Forward Optimization, Deflated Sharpe Ratio, and Haircut Sharpe (SUK-RES-0002, SUK-RES-0003).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass(frozen=True)
class WalkForwardResult:
    is_sharpe: float
    oos_sharpe: float
    walk_forward_efficiency: float  # OOS Sharpe / IS Sharpe (WFE > 0.60 desired)
    is_valid: bool
    rejection_reason: str = ""


@dataclass(frozen=True)
class DeflatedSharpeResult:
    observed_sharpe: float
    deflated_sharpe_p_value: float  # Probability that observed Sharpe is NOT due to data mining
    haircut_sharpe: float
    trials_tested: int
    is_statistically_significant: bool  # p_value >= 0.95


class ValidationEngine:
    """Rigorous statistical validation engine eliminating overfitting and selection bias."""

    @staticmethod
    def evaluate_walk_forward(
        in_sample_returns: List[float],
        out_of_sample_returns: List[float],
        min_wfe_threshold: float = 0.60
    ) -> WalkForwardResult:
        """Evaluate Walk-Forward Efficiency (WFE = OOS_Sharpe / IS_Sharpe)."""
        from sukoon.research.backtest import BacktestEngine

        is_metrics = BacktestEngine.calculate_metrics(in_sample_returns)
        oos_metrics = BacktestEngine.calculate_metrics(out_of_sample_returns)

        is_sr = max(is_metrics.sharpe_ratio, 0.001)
        oos_sr = oos_metrics.sharpe_ratio
        wfe = oos_sr / is_sr

        passed = (wfe >= min_wfe_threshold) and (oos_metrics.sharpe_ratio > 0.5)
        reason = "PASSED_WFE_GATE" if passed else f"WFE {wfe:.2f} below threshold {min_wfe_threshold:.2f}"

        return WalkForwardResult(
            is_sharpe=round(is_metrics.sharpe_ratio, 4),
            oos_sharpe=round(oos_metrics.sharpe_ratio, 4),
            walk_forward_efficiency=round(wfe, 4),
            is_valid=passed,
            rejection_reason=reason
        )

    @staticmethod
    def calculate_deflated_sharpe(
        observed_sharpe: float,
        trials_count: int,
        sample_length: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        annualized: bool = True,
        annualization_factor: float = 252.0
    ) -> DeflatedSharpeResult:
        """
        Bailey & López de Prado (2014) Deflated Sharpe Ratio (DSR).
        Computes the probability that observed Sharpe exceeds expected maximum Sharpe of N random trials.
        """
        if trials_count < 1 or sample_length < 2:
            return DeflatedSharpeResult(
                observed_sharpe=observed_sharpe,
                deflated_sharpe_p_value=0.0,
                haircut_sharpe=0.0,
                trials_tested=trials_count,
                is_statistically_significant=False
            )

        # Convert annualized Sharpe to per-period (daily) Sharpe if necessary
        daily_sr = observed_sharpe / math.sqrt(annualization_factor) if annualized else observed_sharpe

        # Expected maximum Sharpe under null hypothesis of no skill: E[max(SR)]
        # Euler-Mascheroni constant approx 0.57721566
        euler_mascheroni = 0.5772156649
        if trials_count <= 1:
            expected_max_daily_sr = 0.0
        else:
            term = 2.0 * math.log(trials_count)
            expected_max_daily_sr = ((1.0 - euler_mascheroni) * math.sqrt(term) + euler_mascheroni * math.sqrt(term)) / math.sqrt(annualization_factor)

        # Standard error of daily Sharpe ratio
        denom = 1.0 - skewness * daily_sr + ((kurtosis - 1.0) / 4.0) * (daily_sr ** 2)
        sr_std = math.sqrt(max(denom / (sample_length - 1), 1e-6))

        # Z-score for Deflated Sharpe
        z = (daily_sr - expected_max_daily_sr) / sr_std

        # Cumulative normal distribution approximation for p-value
        p_val = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        haircut_sr = max(0.0, (daily_sr - expected_max_daily_sr) * math.sqrt(annualization_factor) if annualized else (daily_sr - expected_max_daily_sr))

        return DeflatedSharpeResult(
            observed_sharpe=round(observed_sharpe, 4),
            deflated_sharpe_p_value=round(p_val, 4),
            haircut_sharpe=round(haircut_sr, 4),
            trials_tested=trials_count,
            is_statistically_significant=p_val >= 0.95
        )
