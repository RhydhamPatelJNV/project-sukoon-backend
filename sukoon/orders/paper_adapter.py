"""
Project Sukoon — Paper Trading Execution Adapter & Portfolio Tracker
Strictly isolated from live trading credentials and endpoints.
Includes atomic file persistence to survive container restarts on cloud infrastructure.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sukoon.orders.models import Order, OrderAction, OrderState
from sukoon.orders.fill_simulator import FillResult, FillSimulator


class PaperPortfolio:
    """Manages simulated paper account equity, positions, cash balance, and persistent order history."""

    def __init__(self, initial_cash: float = 100000.0, persistence_path: Optional[str] = "data/paper_portfolio.json") -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, int] = {}          # symbol -> quantity
        self.cost_basis: Dict[str, float] = {}       # symbol -> avg_cost
        self.orders: Dict[str, Order] = {}           # order_id -> Order
        self.idempotency_keys: Dict[str, str] = {}    # idempotency_key -> order_id
        self.history: List[Dict[str, Any]] = []      # chronological order & execution records
        self.fill_sim = FillSimulator()
        self.persistence_path = persistence_path

        # Restore previous state if persistence file exists
        if self.persistence_path:
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Restores cash balance, positions, cost basis, and trade history from disk."""
        if not self.persistence_path or not os.path.exists(self.persistence_path):
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cash = float(data.get("cash", self.initial_cash))
            self.positions = {k: int(v) for k, v in data.get("positions", {}).items()}
            self.cost_basis = {k: float(v) for k, v in data.get("cost_basis", {}).items()}
            self.idempotency_keys = data.get("idempotency_keys", {})
            self.history = data.get("history", [])
        except Exception as e:
            print(f"[PaperPortfolio] Notice: Failed to load persistence file ({e}), starting fresh.")

    def _save_to_disk(self) -> None:
        """Atomically saves portfolio state to disk."""
        if not self.persistence_path:
            return
        try:
            os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
            data = {
                "cash": round(self.cash, 2),
                "positions": self.positions,
                "cost_basis": {k: round(v, 4) for k, v in self.cost_basis.items()},
                "idempotency_keys": self.idempotency_keys,
                "history": self.history[-500:],  # preserve last 500 orders
                "last_updated_utc": datetime.now(timezone.utc).isoformat()
            }
            tmp_path = self.persistence_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.persistence_path)
        except Exception as e:
            print(f"[PaperPortfolio] Notice: Failed to persist portfolio state ({e})")

    def reset(self, initial_cash: float = 100000.0) -> None:
        """Resets the paper portfolio back to initial state and persists."""
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}
        self.cost_basis = {}
        self.orders = {}
        self.idempotency_keys = {}
        self.history = []
        self._save_to_disk()

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
        """Submit paper order with duplicate-prevention idempotency check and automatic persistence."""
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

        # Record in persistent history
        action_val = order.action.value if hasattr(order.action, "value") else str(order.action)
        state_val = order.current_state.value if hasattr(order.current_state, "value") else str(order.current_state)
        
        hist_entry = {
            "order_id": order.order_id,
            "strategy_id": order.strategy_id,
            "symbol": order.symbol,
            "action": action_val,
            "quantity": order.quantity,
            "limit_price": order.limit_price,
            "filled_quantity": order.filled_quantity,
            "filled_avg_price": order.filled_avg_price,
            "status": state_val,
            "total_notional": round((order.filled_quantity or order.quantity) * (order.filled_avg_price or order.limit_price or 0.0), 2),
            "created_at_utc": order.created_at_utc,
            "filled_at_utc": fill.timestamp_utc if fill else None
        }
        self.history.append(hist_entry)

        # Persist updated state to disk
        self._save_to_disk()

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

    def get_order_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns the order execution history in reverse chronological order."""
        return list(reversed(self.history))[:limit]
