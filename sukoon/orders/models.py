"""
Project Sukoon — Broker-Neutral Order Model & Monotonic State Machine
Complying with SUK-ORD-0001, SUK-ORD-0002, and ADR-002.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"


class OrderState(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    GUARDIAN_APPROVED = "GUARDIAN_APPROVED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    UNKNOWN_REQUIRES_RECONCILIATION = "UNKNOWN_REQUIRES_RECONCILIATION"


# Valid monotonic state transitions
ALLOWED_TRANSITIONS: Dict[OrderState, List[OrderState]] = {
    OrderState.CREATED: [OrderState.VALIDATED, OrderState.REJECTED],
    OrderState.VALIDATED: [OrderState.GUARDIAN_APPROVED, OrderState.REJECTED],
    OrderState.GUARDIAN_APPROVED: [OrderState.SUBMITTED, OrderState.CANCELED],
    OrderState.SUBMITTED: [
        OrderState.ACKNOWLEDGED,
        OrderState.REJECTED,
        OrderState.UNKNOWN_REQUIRES_RECONCILIATION
    ],
    OrderState.ACKNOWLEDGED: [
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELED,
        OrderState.EXPIRED,
        OrderState.UNKNOWN_REQUIRES_RECONCILIATION
    ],
    OrderState.PARTIALLY_FILLED: [
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELED,
        OrderState.UNKNOWN_REQUIRES_RECONCILIATION
    ],
    # Terminal states
    OrderState.FILLED: [],
    OrderState.REJECTED: [],
    OrderState.CANCELED: [],
    OrderState.EXPIRED: [],
    OrderState.UNKNOWN_REQUIRES_RECONCILIATION: [OrderState.CANCELED, OrderState.FILLED]
}


@dataclass
class Order:
    order_id: str
    client_order_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    limit_price: Optional[float]
    time_in_force: TimeInForce
    environment: str  # PAPER, LIVE
    created_at_utc: str
    current_state: OrderState = OrderState.CREATED
    filled_quantity: int = 0
    filled_avg_price: float = 0.0
    guardian_token: Optional[str] = None
    state_history: List[Dict[str, Any]] = field(default_factory=list)

    def transition_to(self, new_state: OrderState, reason: str = "") -> None:
        """Enforce monotonic, append-only state transitions."""
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, [])
        if new_state not in allowed:
            raise ValueError(
                f"Illegal state transition from {self.current_state.value} to {new_state.value} "
                f"for order {self.order_id}."
            )
        
        transition_record = {
            "from_state": self.current_state.value,
            "to_state": new_state.value,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "reason": reason
        }
        self.current_state = new_state
        self.state_history.append(transition_record)

    @classmethod
    def create(
        cls,
        strategy_id: str,
        strategy_version: str,
        symbol: str,
        action: OrderAction,
        quantity: int,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        environment: str = "PAPER"
    ) -> Order:
        now_str = datetime.now(timezone.utc).isoformat()
        order_id = f"ord-{uuid.uuid4().hex[:12]}"
        client_order_id = f"clord-{uuid.uuid4().hex[:16]}"
        
        ord_obj = cls(
            order_id=order_id,
            client_order_id=client_order_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            symbol=symbol.upper(),
            action=action,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            time_in_force=time_in_force,
            environment=environment.upper(),
            created_at_utc=now_str
        )
        ord_obj.state_history.append({
            "from_state": None,
            "to_state": OrderState.CREATED.value,
            "timestamp_utc": now_str,
            "reason": "Order instantiated"
        })
        return ord_obj
