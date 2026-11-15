"""
Project Sukoon — Paper Trading Execution Adapter & Portfolio Tracker
Strictly isolated from live trading credentials and endpoints.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from sukoon.orders.models import Order, OrderAction, OrderState
from sukoon.orders.fill_simulator import FillResult, FillSimulator


class PaperPortfolio:
    """Manages simulated paper account equity, positions, and cash balance."""

    def __init__(self, initial_cash: float = 100000.0) -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, int] = {}       # symbol -> quantity
        self.cost_basis: Dict[str, float] = {}    # symbol -> avg_cost
        self.orders: Dict[str, Order] = {}        # order_id -> Order
        self.idempotency_keys: Dict[str, str] = {} # idempotency_key -> order_id
        self.fill_sim = FillSimulator()

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        pos_val = sum(
            qty * current_prices.get(sym, self.cost_basis.get(sym, 0.0))
            for sym, qty in self.positions.items()
        )
        return self.cash + pos_val

    def submit_order(
        self,
        order: Order,
        idempotency_key: str,
        current_bid: float,
        current_ask: float
    ) -> Optional[FillResult]:
        """Submit paper order with duplicate-prevention idempotency check."""
        if idempotency_key in self.idempotency_keys:
            existing_id = self.idempotency_keys[idempotency_key]
            raise ValueError(f"Duplicate order submission blocked by idempotency key: {idempotency_key} (Order {existing_id})")

        self.idempotency_keys[idempotency_key] = order.order_id
        self.orders[order.order_id] = order

        # Transition to SUBMITTED
        order.transition_to(OrderState.SUBMITTED, "Dispatched to paper simulator")

        # Execute fill simulation
        fill = self.fill_sim.simulate_fill(order, current_bid, current_ask)
        if fill:
            self._update_position(fill)
        return fill

    def _update_position(self, fill: FillResult) -> None:
        sym = fill.symbol
        trade_cost = (fill.filled_qty * fill.fill_price) + fill.commission

        if fill.action == OrderAction.BUY:
            self.cash -= trade_cost
            prev_qty = self.positions.get(sym, 0)
            prev_cost = self.cost_basis.get(sym, 0.0)
            new_qty = prev_qty + fill.filled_qty
            new_cost = ((prev_qty * prev_cost) + (fill.filled_qty * fill.fill_price)) / new_qty
            self.positions[sym] = new_qty
            self.cost_basis[sym] = new_cost

        elif fill.action == OrderAction.SELL:
            self.cash += (fill.filled_qty * fill.fill_price) - fill.commission
            prev_qty = self.positions.get(sym, 0)
            new_qty = prev_qty - fill.filled_qty
            if new_qty <= 0:
                self.positions.pop(sym, None)
                self.cost_basis.pop(sym, None)
            else:
                self.positions[sym] = new_qty
