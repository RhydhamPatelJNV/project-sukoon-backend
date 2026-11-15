"""
Project Sukoon — Sukoon Guardian Pre-Trade Risk Engine
Deterministic, isolated, and non-overridable by Cortex or LLMs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from sukoon.data.symbols import SymbolMaster
from sukoon.guardian.kill_switch import KillSwitchController
from sukoon.guardian.lrs_check import LRSComplianceChecker
from sukoon.guardian.models import GuardianDecision, GuardianPolicy
from sukoon.orders.models import Order, OrderAction, OrderType


class SukoonGuardianEngine:
    """The central deterministic risk authority for Project Sukoon."""

    def __init__(
        self,
        policy: Optional[GuardianPolicy] = None,
        signing_key: str = "SECURE_GUARDIAN_SECRET_KEY_32_BYTES_MIN",
        symbol_master: Optional[SymbolMaster] = None
    ) -> None:
        self.policy = policy or GuardianPolicy()
        self.signing_key = signing_key
        self.symbol_master = symbol_master or SymbolMaster()
        self.kill_switch = KillSwitchController()
        self.lrs_checker = LRSComplianceChecker()
        self.veto_count_today: int = 0

    def evaluate_order(
        self,
        order: Order,
        current_cash: float,
        portfolio_equity: float,
        current_position_qty: int,
        latest_quote_age_seconds: float,
        is_reconciled: bool,
        intraday_loss_pct: float,
        trailing_drawdown_pct: float,
        active_feed: str = "iex"
    ) -> GuardianDecision:
        veto_reasons: List[str] = []

        # Interlock 1: Kill-Switch Check
        if self.kill_switch.is_active:
            veto_reasons.append(f"VETO: Kill-switch engaged ({self.kill_switch.trigger_reason}).")

        # Interlock 2: Reconciliation State
        if not is_reconciled:
            veto_reasons.append("VETO: Unreconciled broker state detected. Safe mode active.")

        # Interlock 3: Drawdown Floor & Daily Loss Limit
        if trailing_drawdown_pct >= self.policy.max_drawdown_pct:
            self.kill_switch.engage(f"Trailing drawdown {trailing_drawdown_pct:.2%} breached {self.policy.max_drawdown_pct:.2%}")
            veto_reasons.append(f"VETO: Max drawdown limit breached ({trailing_drawdown_pct:.2%}).")

        if intraday_loss_pct >= self.policy.daily_loss_limit_pct:
            veto_reasons.append(f"VETO: Daily loss limit breached ({intraday_loss_pct:.2%}). Trading halted for day.")

        # Interlock 4: India LRS Compliance (Cash-only, no shorting, no leverage)
        if self.policy.cash_only_enforced:
            lrs_ok, lrs_msg = self.lrs_checker.verify_order_compliance(order, current_cash, current_position_qty)
            if not lrs_ok:
                veto_reasons.append(lrs_msg)

        # Interlock 5: Symbol Tradability & Universe Check
        tradable, sym_msg = self.symbol_master.is_tradable(order.symbol)
        if not tradable:
            veto_reasons.append(f"VETO: {sym_msg}")

        # Interlock 6: Quote Freshness
        if latest_quote_age_seconds > self.policy.quote_freshness_seconds:
            veto_reasons.append(
                f"VETO: Stale quote ({latest_quote_age_seconds:.1f}s > {self.policy.quote_freshness_seconds:.1f}s limit)."
            )

        # Interlock 7: IEX Feed Limit-Order Requirement
        if active_feed == "iex" and self.policy.iex_limit_orders_only:
            if order.order_type == OrderType.MARKET:
                veto_reasons.append("VETO: MARKET orders prohibited on Alpaca Basic IEX feed. Must use LIMIT order.")

        # Interlock 8: Single Order Size / Notional Cap
        est_notional = order.quantity * (order.limit_price or 0.0)
        if est_notional > self.policy.max_order_notional:
            veto_reasons.append(
                f"VETO: Order notional ${est_notional:,.2f} exceeds cap of ${self.policy.max_order_notional:,.2f}."
            )

        # Interlock 9: Single Stock Portfolio Concentration
        if portfolio_equity > 0:
            target_pos_val = (current_position_qty + order.quantity) * (order.limit_price or 0.0)
            concentration_pct = target_pos_val / portfolio_equity
            if order.action == OrderAction.BUY and concentration_pct > self.policy.max_position_pct:
                veto_reasons.append(
                    f"VETO: Position concentration {concentration_pct:.2%} exceeds max limit of {self.policy.max_position_pct:.2%}."
                )

        # Interlock 10: Live Risk Allocation (Strict zero default)
        if order.environment == "LIVE" and self.policy.live_risk_budget <= 0.0:
            veto_reasons.append("VETO: Live risk budget is $0.00. Explicit user activation required.")

        approved = len(veto_reasons) == 0
        if not approved:
            self.veto_count_today += 1

        decision = GuardianDecision.create(
            order_id=order.order_id,
            approved=approved,
            mode=order.environment,
            reasons=veto_reasons if not approved else ["PASSED_ALL_DETERMINISTIC_INTERLOCKS"],
            policy=self.policy,
            secret_signing_key=self.signing_key
        )
        return decision
