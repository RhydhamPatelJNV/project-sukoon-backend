"""
Project Sukoon — India-Resident LRS & Regulatory Checkpoint (G12-R01)
Programmatically enforces RBI LRS & FEMA restrictions: Cash-only, zero margin borrowing.
"""
from __future__ import annotations

from typing import Tuple
from sukoon.orders.models import Order, OrderAction


class LRSComplianceChecker:
    """Verifies that trades comply with Indian foreign exchange regulations."""

    @staticmethod
    def verify_order_compliance(order: Order, current_cash: float, current_positions_qty: int) -> Tuple[bool, str]:
        # Rule 1: No Short Selling
        if order.action == OrderAction.SELL:
            if order.quantity > current_positions_qty:
                return False, (
                    f"LRS VETO: Short selling strictly prohibited. Attempting to sell {order.quantity} shares "
                    f"with only {current_positions_qty} shares in custody."
                )

        # Rule 2: Cash-Only Basis (No Margin Borrowing)
        if order.action == OrderAction.BUY:
            est_cost = order.quantity * (order.limit_price or 0.0)
            if est_cost > current_cash:
                return False, (
                    f"LRS VETO: Margin borrowing prohibited by RBI LRS. Required cash: ${est_cost:,.2f}, "
                    f"Available cash: ${current_cash:,.2f}."
                )

        return True, "LRS COMPLIANT (Cash-Only)"
