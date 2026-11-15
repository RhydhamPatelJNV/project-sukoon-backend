import os
import sys
import unittest

backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from sukoon.guardian.engine import SukoonGuardianEngine
from sukoon.guardian.models import GuardianPolicy
from sukoon.orders.models import Order, OrderAction, OrderType

class TestSukoonGuardian(unittest.TestCase):
    def setUp(self):
        self.guardian = SukoonGuardianEngine()

    def test_clean_order_approved(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="SPY",
            action=OrderAction.BUY,
            quantity=10,
            limit_price=500.0,
            order_type=OrderType.LIMIT,
            environment="PAPER"
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=50000.0,
            portfolio_equity=100000.0,
            current_position_qty=0,
            latest_quote_age_seconds=2.0,
            is_reconciled=True,
            intraday_loss_pct=0.005,
            trailing_drawdown_pct=0.01,
            active_feed="iex"
        )
        self.assertTrue(dec.approved)
        self.assertIsNotNone(dec.pass_token)
        self.assertEqual(dec.reasons[0], "PASSED_ALL_DETERMINISTIC_INTERLOCKS")

    def test_lrs_veto_short_selling(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="AAPL",
            action=OrderAction.SELL,
            quantity=50,  # Trying to sell 50 when holding 10
            limit_price=180.0
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=50000.0,
            portfolio_equity=100000.0,
            current_position_qty=10,
            latest_quote_age_seconds=1.0,
            is_reconciled=True,
            intraday_loss_pct=0.0,
            trailing_drawdown_pct=0.0
        )
        self.assertFalse(dec.approved)
        self.assertIsNone(dec.pass_token)
        self.assertTrue(any("Short selling strictly prohibited" in r for r in dec.reasons))

    def test_lrs_veto_margin_borrowing(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="MSFT",
            action=OrderAction.BUY,
            quantity=100,
            limit_price=400.0 # $40,000 required
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=10000.0, # Only $10,000 cash available
            portfolio_equity=50000.0,
            current_position_qty=0,
            latest_quote_age_seconds=1.0,
            is_reconciled=True,
            intraday_loss_pct=0.0,
            trailing_drawdown_pct=0.0
        )
        self.assertFalse(dec.approved)
        self.assertTrue(any("Margin borrowing prohibited" in r for r in dec.reasons))

    def test_veto_stale_quote(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="SPY",
            action=OrderAction.BUY,
            quantity=5,
            limit_price=500.0
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=50000.0,
            portfolio_equity=100000.0,
            current_position_qty=0,
            latest_quote_age_seconds=45.0, # 45s > 15s limit
            is_reconciled=True,
            intraday_loss_pct=0.0,
            trailing_drawdown_pct=0.0
        )
        self.assertFalse(dec.approved)
        self.assertTrue(any("Stale quote" in r for r in dec.reasons))

    def test_veto_market_order_on_iex(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="SPY",
            action=OrderAction.BUY,
            quantity=5,
            order_type=OrderType.MARKET # Prohibited on IEX Basic
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=50000.0,
            portfolio_equity=100000.0,
            current_position_qty=0,
            latest_quote_age_seconds=1.0,
            is_reconciled=True,
            intraday_loss_pct=0.0,
            trailing_drawdown_pct=0.0,
            active_feed="iex"
        )
        self.assertFalse(dec.approved)
        self.assertTrue(any("MARKET orders prohibited on Alpaca Basic IEX" in r for r in dec.reasons))

    def test_veto_live_trading_default_zero(self):
        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="SPY",
            action=OrderAction.BUY,
            quantity=5,
            limit_price=500.0,
            environment="LIVE"
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=50000.0,
            portfolio_equity=100000.0,
            current_position_qty=0,
            latest_quote_age_seconds=1.0,
            is_reconciled=True,
            intraday_loss_pct=0.0,
            trailing_drawdown_pct=0.0
        )
        self.assertFalse(dec.approved)
        self.assertTrue(any("Live risk budget is $0.00" in r for r in dec.reasons))

    def test_kill_switch_engagement(self):
        self.guardian.kill_switch.engage("Manual operator test panic", triggered_by="TEST")
        self.assertTrue(self.guardian.kill_switch.is_active)

        order = Order.create(
            strategy_id="strat-alpha",
            strategy_version="1.0.0",
            symbol="SPY",
            action=OrderAction.BUY,
            quantity=1,
            limit_price=500.0
        )
        dec = self.guardian.evaluate_order(
            order=order,
            current_cash=50000.0,
            portfolio_equity=100000.0,
            current_position_qty=0,
            latest_quote_age_seconds=1.0,
            is_reconciled=True,
            intraday_loss_pct=0.0,
            trailing_drawdown_pct=0.0
        )
        self.assertFalse(dec.approved)
        self.assertTrue(any("Kill-switch engaged" in r for r in dec.reasons))

        # Reset kill switch
        reset_ok = self.guardian.kill_switch.disengage("AUTH_SECRET_KEY_123456789", "AdminOperator")
        self.assertTrue(reset_ok)
        self.assertFalse(self.guardian.kill_switch.is_active)

if __name__ == "__main__":
    unittest.main()
