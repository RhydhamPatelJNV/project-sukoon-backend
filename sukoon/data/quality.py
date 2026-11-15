"""
Project Sukoon — Data Quality State Machine
Validates quote and bar integrity, flags outliers, and isolates suspect data into quarantine.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


class DataQualityStatus(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    VALIDATED = "VALIDATED"
    SUSPECT = "SUSPECT"
    QUARANTINED = "QUARANTINED"


class DataQualityEngine:
    """Deterministic data quality validator complying with G01 roles."""

    def __init__(
        self,
        max_quote_spread_pct: float = 0.10,  # 10% spread limit
        max_single_tick_jump_pct: float = 0.20,  # 20% single tick anomaly
        stale_threshold_seconds: float = 30.0
    ) -> None:
        self.max_quote_spread_pct = max_quote_spread_pct
        self.max_single_tick_jump_pct = max_single_tick_jump_pct
        self.stale_threshold_seconds = stale_threshold_seconds

    def validate_quote(
        self,
        bid_price: float,
        ask_price: float,
        bid_size: int,
        ask_size: int,
        prev_close: Optional[float] = None
    ) -> tuple[DataQualityStatus, List[str]]:
        reasons: List[str] = []

        if bid_price <= 0 or ask_price <= 0:
            reasons.append("Non-positive bid/ask price")
            return DataQualityStatus.QUARANTINED, reasons

        if bid_price > ask_price:
            reasons.append(f"Inverted market: bid ({bid_price}) > ask ({ask_price})")
            return DataQualityStatus.SUSPECT, reasons

        spread = ask_price - bid_price
        mid = (ask_price + bid_price) / 2.0
        spread_pct = spread / mid

        if spread_pct > self.max_quote_spread_pct:
            reasons.append(f"Excessive spread: {spread_pct:.2%} exceeds {self.max_quote_spread_pct:.2%}")
            return DataQualityStatus.SUSPECT, reasons

        if prev_close and prev_close > 0:
            jump_pct = abs(mid - prev_close) / prev_close
            if jump_pct > self.max_single_tick_jump_pct:
                reasons.append(f"Price discontinuity: {jump_pct:.2%} jump from previous price {prev_close}")
                return DataQualityStatus.SUSPECT, reasons

        if bid_size < 0 or ask_size < 0:
            reasons.append("Negative quote sizes")
            return DataQualityStatus.QUARANTINED, reasons

        return DataQualityStatus.VALIDATED, ["Quote passes all deterministic checks"]

    def validate_bar(
        self,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: int
    ) -> tuple[DataQualityStatus, List[str]]:
        reasons: List[str] = []

        # High must be the highest, Low the lowest
        if not (low_p <= open_p <= high_p and low_p <= close_p <= high_p):
            reasons.append(f"OHLC envelope violation: O={open_p}, H={high_p}, L={low_p}, C={close_p}")
            return DataQualityStatus.QUARANTINED, reasons

        if any(p <= 0 for p in [open_p, high_p, low_p, close_p]):
            reasons.append("Non-positive bar price detected")
            return DataQualityStatus.QUARANTINED, reasons

        if volume < 0:
            reasons.append(f"Negative volume: {volume}")
            return DataQualityStatus.QUARANTINED, reasons

        return DataQualityStatus.VALIDATED, ["Bar passes OHLC integrity check"]
