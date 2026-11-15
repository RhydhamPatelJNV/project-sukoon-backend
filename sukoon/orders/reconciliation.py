"""
Project Sukoon — Real-Time Broker & Position Reconciler (G13-R03)
Detects state drift between internal ledger and broker; triggers safe mode on mismatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class ReconciliationReport:
    is_synchronized: bool
    cash_delta: float
    position_mismatches: List[str]
    unknown_orders: List[str]
    action_required: str


class OrderReconciler:
    """Verifies alignment between internal portfolio state and broker account state."""

    def __init__(self, cash_tolerance: float = 0.05) -> None:
        self.cash_tolerance = cash_tolerance

    def reconcile(
        self,
        internal_cash: float,
        broker_cash: float,
        internal_positions: Dict[str, int],
        broker_positions: Dict[str, int],
        unacknowledged_orders: List[str]
    ) -> ReconciliationReport:
        cash_delta = abs(internal_cash - broker_cash)
        cash_ok = cash_delta <= self.cash_tolerance

        mismatches: List[str] = []
        all_symbols = set(internal_positions.keys()).union(set(broker_positions.keys()))
        for sym in all_symbols:
            int_qty = internal_positions.get(sym, 0)
            brk_qty = broker_positions.get(sym, 0)
            if int_qty != brk_qty:
                mismatches.append(f"{sym}: internal={int_qty}, broker={brk_qty}")

        has_unknown = len(unacknowledged_orders) > 0
        is_synced = cash_ok and (len(mismatches) == 0) and (not has_unknown)

        action = "CONTINUE"
        if not is_synced:
            action = "INVOKE_SAFE_MODE_SUSPEND_TRADING"

        return ReconciliationReport(
            is_synchronized=is_synced,
            cash_delta=round(cash_delta, 4),
            position_mismatches=mismatches,
            unknown_orders=unacknowledged_orders,
            action_required=action
        )
