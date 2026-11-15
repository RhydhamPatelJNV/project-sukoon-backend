"""
Project Sukoon — Sukoon Guardian Models & Decision Envelopes
Complying with SUK-RISK-0001, SUK-RISK-0005, and ADR-002.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class GuardianPolicy:
    """User-approved risk thresholds. Cortex CANNOT modify this."""
    max_position_pct: float = 0.10          # Max 10% notional in single stock
    max_drawdown_pct: float = 0.06          # 6% Max drawdown invokes Kill-Switch
    daily_loss_limit_pct: float = 0.02      # 2% Daily loss halts trading
    cash_only_enforced: bool = True         # LRS mandate: Zero margin/shorting
    max_order_notional: float = 25000.0     # Cap on single order dollar size
    quote_freshness_seconds: float = 15.0   # Reject stale quotes
    iex_limit_orders_only: bool = True      # Alpaca Basic: No market orders on IEX
    live_risk_budget: float = 0.0           # Default live risk is ZERO


@dataclass(frozen=True)
class GuardianDecision:
    decision_id: str
    order_id: str
    approved: bool
    mode: str
    reasons: List[str]
    evaluated_at_utc: str
    policy_hash: str
    pass_token: Optional[str] = None

    @classmethod
    def create(
        cls,
        order_id: str,
        approved: bool,
        mode: str,
        reasons: List[str],
        policy: GuardianPolicy,
        secret_signing_key: str
    ) -> GuardianDecision:
        now_str = datetime.now(timezone.utc).isoformat()
        policy_bytes = json.dumps(asdict(policy), sort_keys=True).encode("utf-8")
        pol_hash = hashlib.sha256(policy_bytes).hexdigest()
        
        token = None
        if approved:
            # Deterministic HMAC pass token proving Guardian sign-off
            msg = f"{order_id}|{mode}|{pol_hash}|{now_str}".encode("utf-8")
            token = hmac.new(secret_signing_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        dec_id = f"gdec-{hashlib.sha256(f'{order_id}-{now_str}'.encode()).hexdigest()[:16]}"
        return cls(
            decision_id=dec_id,
            order_id=order_id,
            approved=approved,
            mode=mode,
            reasons=reasons,
            evaluated_at_utc=now_str,
            policy_hash=pol_hash,
            pass_token=token
        )
