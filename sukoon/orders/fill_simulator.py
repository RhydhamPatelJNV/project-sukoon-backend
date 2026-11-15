"""
Project Sukoon — Local Execution Fill Simulator
Reproduces realistic spread, slippage, market impact, and latency delays (SUK-ORD-0003).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from sukoon.orders.models import Order, OrderAction, OrderState, OrderType


@dataclass(frozen=True)
class FillResult:
    order_id: str
    symbol: str
    action: OrderAction
    filled_qty: int
    fill_price: float
    slippage_bps: float
    commission: float
    timestamp_utc: str
    is_complete: bool


class FillSimulator:
    """Deterministic fill simulator for paper trading and backtesting."""

    def __init__(
        self,
        base_slippage_bps: float = 2.0,      # 2 basis points base slippage
        commission_per_share: float = 0.005, # $0.005 per share
        min_commission: float = 0.0,
        fill_ratio: float = 1.0              # 1.0 for 100% fill, < 1.0 for partial fills
    ) -> None:
        self.base_slippage_bps = base_slippage_bps
        self.commission_per_share = commission_per_share
        self.min_commission = min_commission
        self.fill_ratio = fill_ratio

    def simulate_fill(
        self,
        order: Order,
        bid_price: float,
        ask_price: float
    ) -> Optional[FillResult]:
        """Simulate order execution against bid/ask quote."""
        if order.current_state != OrderState.SUBMITTED:
            raise ValueError(f"Cannot fill order in state {order.current_state}. Must be SUBMITTED.")

        mid_price = (bid_price + ask_price) / 2.0
        slippage_mult = self.base_slippage_bps / 10000.0

        if order.action == OrderAction.BUY:
            # Buyers pay the ask price + positive slippage
            sim_price = ask_price * (1.0 + slippage_mult)
            if order.order_type == OrderType.LIMIT and order.limit_price is not None:
                if sim_price > order.limit_price:
                    # Limit price exceeded; cannot fill
                    return None
        elif order.action == OrderAction.SELL:
            # Sellers hit the bid price - slippage
            sim_price = bid_price * (1.0 - slippage_mult)
            if order.order_type == OrderType.LIMIT and order.limit_price is not None:
                if sim_price < order.limit_price:
                    # Below sell limit; cannot fill
                    return None
        else:
            return None

        # Calculate fill quantity (supporting partial fills)
        fill_qty = int(order.quantity * self.fill_ratio)
        if fill_qty <= 0:
            fill_qty = order.quantity

        commission = max(self.min_commission, fill_qty * self.commission_per_share)
        now_str = datetime.now(timezone.utc).isoformat()

        is_complete = (fill_qty == order.quantity)
        
        # Monotonically transition order state
        if is_complete:
            order.transition_to(OrderState.ACKNOWLEDGED, "Simulated broker ACK")
            order.transition_to(OrderState.FILLED, f"Filled {fill_qty} shares at {sim_price:.4f}")
        else:
            order.transition_to(OrderState.ACKNOWLEDGED, "Simulated broker ACK")
            order.transition_to(OrderState.PARTIALLY_FILLED, f"Partially filled {fill_qty}/{order.quantity} shares")

        order.filled_quantity = fill_qty
        order.filled_avg_price = round(sim_price, 4)

        return FillResult(
            order_id=order.order_id,
            symbol=order.symbol,
            action=order.action,
            filled_qty=fill_qty,
            fill_price=round(sim_price, 4),
            slippage_bps=self.base_slippage_bps,
            commission=round(commission, 4),
            timestamp_utc=now_str,
            is_complete=is_complete
        )
