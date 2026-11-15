"""
Project Sukoon — Deterministic Backtest Engine & Performance Metrics (G09)
Computes Sharpe ratio, Max Drawdown, Win Rate, and Profit Factor.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np


@dataclass(frozen=True)
class BacktestMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return_pct: float
    annualized_return_pct: float
    annualized_volatility_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    profit_factor: float
    skewness: float
    kurtosis: float


class BacktestEngine:
    """Calculates backtest performance metrics deterministically."""

    @staticmethod
    def calculate_metrics(trade_returns: List[float], annualization_factor: float = 252.0) -> BacktestMetrics:
        if not trade_returns or len(trade_returns) < 2:
            return BacktestMetrics(
                total_trades=len(trade_returns),
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_return_pct=0.0,
                annualized_return_pct=0.0,
                annualized_volatility_pct=0.0,
                sharpe_ratio=0.0,
                max_drawdown_pct=0.0,
                profit_factor=0.0,
                skewness=0.0,
                kurtosis=3.0
            )

        returns = np.array(trade_returns, dtype=np.float64)
        total_trades = len(returns)
        winning = int(np.sum(returns > 0))
        losing = int(np.sum(returns < 0))
        win_rate = winning / total_trades if total_trades > 0 else 0.0

        # Cumulative equity curve
        cum_equity = np.cumprod(1.0 + returns)
        total_return = float(cum_equity[-1] - 1.0)

        # Max Drawdown
        running_max = np.maximum.accumulate(cum_equity)
        drawdowns = (cum_equity - running_max) / running_max
        max_dd = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Annualized metrics
        mean_ret = float(np.mean(returns))
        std_ret = float(np.std(returns, ddof=1)) if len(returns) > 1 else 1e-6
        ann_ret = mean_ret * annualization_factor
        ann_vol = std_ret * math.sqrt(annualization_factor)
        sharpe = (ann_ret / ann_vol) if ann_vol > 0 else 0.0

        # Profit factor
        gross_profit = float(np.sum(returns[returns > 0])) if winning > 0 else 0.0
        gross_loss = float(abs(np.sum(returns[returns < 0]))) if losing > 0 else 1e-6
        profit_factor = gross_profit / gross_loss

        # Higher moments (Skewness & Kurtosis for Deflated Sharpe)
        norm_ret = (returns - mean_ret) / std_ret if std_ret > 0 else returns
        skewness = float(np.mean(norm_ret ** 3))
        kurtosis = float(np.mean(norm_ret ** 4))

        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=round(win_rate, 4),
            total_return_pct=round(total_return, 4),
            annualized_return_pct=round(ann_ret, 4),
            annualized_volatility_pct=round(ann_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown_pct=round(abs(max_dd), 4),
            profit_factor=round(profit_factor, 4),
            skewness=round(skewness, 4),
            kurtosis=round(kurtosis, 4)
        )
