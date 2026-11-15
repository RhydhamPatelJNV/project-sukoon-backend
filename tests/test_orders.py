import os
import sys
import unittest

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.orders.models import Order, OrderAction, OrderState, OrderType
from sukoon.orders.fill_simulator import FillSimulator
from sukoon.orders.paper_adapter import PaperPortfolio
from sukoon.orders.reconciliation import OrderReconciler

class TestOrdersAndExecution(unittest.TestCase):
    def test_monotonic_state_transitions(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="SPY",
            action=OrderAction.BUY,
            quantity=10,
            limit_price=510.0
        )
        self.assertEqual(order.current_state, OrderState.CREATED)

        # Valid transitions
        order.transition_to(OrderState.VALIDATED, "Schema validated")
        self.assertEqual(order.current_state, OrderState.VALIDATED)

        order.transition_to(OrderState.GUARDIAN_APPROVED, "Guardian passed")
        self.assertEqual(order.current_state, OrderState.GUARDIAN_APPROVED)

        # Invalid backwards transition should raise ValueError
        with self.assertRaises(ValueError):
            order.transition_to(OrderState.CREATED, "Illegal jump")

    def test_paper_portfolio_and_idempotency(self):
        portfolio = PaperPortfolio(initial_cash=50000.0)
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="AAPL",
            action=OrderAction.BUY,
            quantity=10,
            limit_price=190.0
        )
        order.transition_to(OrderState.VALIDATED)
        order.transition_to(OrderState.GUARDIAN_APPROVED)

        # First submission with key
        fill = portfolio.submit_order(
            order=order,
            idempotency_key="idemp-key-101",
            current_bid=180.0,
            current_ask=180.10
        )
        self.assertIsNotNone(fill)
        self.assertEqual(portfolio.positions.get("AAPL"), 10)
        self.assertLess(portfolio.cash, 50000.0)

        # Resubmission with same idempotency key must raise ValueError
        with self.assertRaises(ValueError):
            portfolio.submit_order(
                order=order,
                idempotency_key="idemp-key-101",
                current_bid=180.0,
                current_ask=180.10
            )

    def test_reconciliation_gap_detection(self):
        reconciler = OrderReconciler(cash_tolerance=0.01)

        # Synchronized state
        report_ok = reconciler.reconcile(
            internal_cash=10000.0,
            broker_cash=10000.0,
            internal_positions={"AAPL": 50},
            broker_positions={"AAPL": 50},
            unacknowledged_orders=[]
        )
        self.assertTrue(report_ok.is_synchronized)
        self.assertEqual(report_ok.action_required, "CONTINUE")

        # Discrepancy in position -> triggers Safe Mode
        report_bad = reconciler.reconcile(
            internal_cash=10000.0,
            broker_cash=10000.0,
            internal_positions={"AAPL": 50},
            broker_positions={"AAPL": 40},
            unacknowledged_orders=[]
        )
        self.assertFalse(report_bad.is_synchronized)
        self.assertEqual(report_bad.action_required, "INVOKE_SAFE_MODE_SUSPEND_TRADING")

if __name__ == "__main__":
    unittest.main()
