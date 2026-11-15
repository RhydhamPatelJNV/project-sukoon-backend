"""
Project Sukoon — Paper Trading Execution Adapter & Portfolio Tracker
Strictly isolated from live trading credentials and endpoints.
Directly integrated with Alpaca Paper Trading REST API to dispatch real orders,
synchronize live account balances, and display queued weekend orders.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sukoon.orders.models import Order, OrderAction, OrderState, OrderType
from sukoon.orders.fill_simulator import FillResult, FillSimulator
from sukoon.orders.alpaca_broker import AlpacaPaperBroker


class PaperPortfolio:
    """Manages simulated paper account equity, positions, cash balance, and persistent order history
    with live synchronization to Alpaca Paper Trading API."""

    def __init__(
        self,
        initial_cash: float = 100000.0,
        persistence_path: Optional[str] = "data/paper_portfolio.json",
        alpaca_broker: Optional[AlpacaPaperBroker] = None
    ) -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, int] = {}          # symbol -> quantity
        self.cost_basis: Dict[str, float] = {}       # symbol -> avg_cost
        self.orders: Dict[str, Order] = {}           # order_id -> Order
        self.idempotency_keys: Dict[str, str] = {}    # idempotency_key -> order_id
        self.history: List[Dict[str, Any]] = []      # chronological order & execution records
        self.fill_sim = FillSimulator()
        self.persistence_path = persistence_path
        self.alpaca_broker = alpaca_broker or AlpacaPaperBroker()

        # Restore previous state if persistence file exists
        if self.persistence_path:
            self._load_from_disk()

        # Sync with live Alpaca paper account if configured
        if self.alpaca_broker and self.alpaca_broker.is_configured:
            self.sync_with_alpaca()

    def sync_with_alpaca(self) -> None:
        """Pulls real-time equity, cash, and positions from Alpaca Paper Account."""
        if not self.alpaca_broker or not self.alpaca_broker.is_configured:
            return
        try:
            acc = self.alpaca_broker.get_account()
            if acc:
                self.cash = float(acc.get("cash", self.cash))

            pos_list = self.alpaca_broker.get_positions()
            new_positions = {}
            new_cost_basis = {}
            for p in pos_list:
                sym = p.get("symbol")
                qty = int(float(p.get("qty", 0)))
                cost = float(p.get("avg_entry_price", 0.0))
                if sym and qty != 0:
                    new_positions[sym] = qty
                    new_cost_basis[sym] = cost
            self.positions = new_positions
            self.cost_basis = new_cost_basis
            self._save_to_disk()
        except Exception as e:
            print(f"[PaperPortfolio] Alpaca sync error: {e}")

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
                "history": self.history[-500:],
                "last_updated_utc": datetime.now(timezone.utc).isoformat()
            }
            tmp_path = self.persistence_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.persistence_path)
        except Exception as e:
            print(f"[PaperPortfolio] Notice: Failed to persist portfolio state ({e})")

    def reset(self, initial_cash: float = 100000.0) -> None:
        """Resets the paper portfolio back to initial state and cancels open Alpaca orders."""
        if self.alpaca_broker and self.alpaca_broker.is_configured:
            try:
                self.alpaca_broker.cancel_all_orders()
            except Exception as e:
                print(f"[PaperPortfolio] Alpaca cancel_all error: {e}")

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
        """Submit paper order with duplicate-prevention idempotency check and dispatch to Alpaca Paper API."""
        if idempotency_key in self.idempotency_keys:
            existing_id = self.idempotency_keys[idempotency_key]
            raise ValueError(f"Duplicate order submission blocked by idempotency key: {idempotency_key} (Order {existing_id})")

        self.idempotency_keys[idempotency_key] = order.order_id
        self.orders[order.order_id] = order

        # Transition to SUBMITTED
        order.transition_to(OrderState.SUBMITTED, "Dispatched to execution engine")

        alpaca_order = None
        # 1. Dispatch real order to Alpaca Paper Trading API
        if self.alpaca_broker and self.alpaca_broker.is_configured:
            try:
                alpaca_order = self.alpaca_broker.submit_order(
                    symbol=order.symbol,
                    qty=order.quantity,
                    action=order.action,
                    order_type=order.order_type,
                    limit_price=order.limit_price,
                    client_order_id=order.client_order_id,
                    time_in_force="day"
                )
                if alpaca_order:
                    alpaca_id = alpaca_order.get("id")
                    alpaca_status = (alpaca_order.get("status") or "accepted").upper()
                    print(f"[PaperPortfolio] Order successfully placed on Alpaca: {alpaca_id} (Status: {alpaca_status})")
                    
                    if alpaca_id:
                        order.order_id = alpaca_id
                    
                    if alpaca_status in ("ACCEPTED", "PENDING_NEW", "NEW", "HELD"):
                        order.transition_to(OrderState.ACKNOWLEDGED, f"Alpaca Order Queued ({alpaca_status})")
                    elif alpaca_status == "FILLED":
                        order.transition_to(OrderState.ACKNOWLEDGED, "Alpaca broker ACK")
                        order.transition_to(OrderState.FILLED, "Filled on Alpaca Exchange")
            except Exception as e:
                print(f"[PaperPortfolio] Warning: Alpaca dispatch failed, falling back to local fill simulator: {e}")

        # 2. Local simulation fallback if Alpaca is offline or for instant backtest feedback
        fill = None
        if not alpaca_order or order.current_state != OrderState.FILLED:
            try:
                fill = self.fill_sim.simulate_fill(order, current_bid, current_ask)
                if fill:
                    self._update_position(fill)
            except Exception:
                pass

        # 3. Record in persistent history
        action_val = order.action.value if hasattr(order.action, "value") else str(order.action)
        state_val = order.current_state.value if hasattr(order.current_state, "value") else str(order.current_state)
        
        hist_entry = {
            "order_id": order.order_id,
            "strategy_id": order.strategy_id,
            "symbol": order.symbol,
            "action": action_val,
            "quantity": order.quantity,
            "limit_price": order.limit_price,
            "filled_quantity": order.filled_quantity or (order.quantity if state_val == "FILLED" else 0),
            "filled_avg_price": order.filled_avg_price or (order.limit_price if state_val == "FILLED" else 0.0),
            "status": state_val,
            "total_notional": round((order.quantity) * (order.limit_price or 0.0), 2),
            "created_at_utc": order.created_at_utc,
            "filled_at_utc": fill.timestamp_utc if fill else (datetime.now(timezone.utc).isoformat() if state_val == "FILLED" else None)
        }
        self.history.append(hist_entry)
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
        """Returns the order execution history, syncing directly with live Alpaca orders when configured."""
        if self.alpaca_broker and self.alpaca_broker.is_configured:
            try:
                alpaca_orders = self.alpaca_broker.get_orders(status="all", limit=limit)
                if alpaca_orders:
                    alpaca_hist = []
                    for ao in alpaca_orders:
                        filled_qty = int(ao.get("filled_qty") or 0)
                        qty = int(ao.get("qty") or 0)
                        filled_price = float(ao.get("filled_avg_price") or ao.get("limit_price") or 0.0)
                        limit_p = float(ao.get("limit_price") or 0.0)
                        notional = round((filled_qty or qty) * (filled_price or limit_p), 2)
                        
                        alpaca_hist.append({
                            "order_id": ao.get("id"),
                            "strategy_id": "alpaca_broker_order",
                            "symbol": ao.get("symbol"),
                            "action": ao.get("side", "").upper(),
                            "quantity": qty,
                            "limit_price": limit_p,
                            "filled_quantity": filled_qty,
                            "filled_avg_price": filled_price,
                            "status": ao.get("status", "").upper(),
                            "total_notional": notional,
                            "created_at_utc": ao.get("submitted_at") or ao.get("created_at"),
                            "filled_at_utc": ao.get("filled_at")
                        })
                    if alpaca_hist:
                        return alpaca_hist[:limit]
            except Exception as e:
                print(f"[PaperPortfolio] Alpaca orders query notice: {e}")

        return list(reversed(self.history))[:limit]
