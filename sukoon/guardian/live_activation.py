"""
Project Sukoon — Gated Live Activation Protocol (SUK-LIVE-0001)
Requires strategy gate pass, India LRS compliance confirmation, and explicit user cryptographic sign-off.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LiveActivationCertificate:
    account_alias: str
    authorized_strategies: List[str]
    max_capital_allocation_usd: float
    lrs_compliance_acknowledged: bool
    user_identity: str
    signed_at_utc: str
    signature: str


class LiveActivationProtocol:
    """Manages the formal gated protocol for activating live equity trading."""

    @staticmethod
    def issue_activation_certificate(
        account_alias: str,
        authorized_strategies: List[str],
        max_capital_usd: float,
        lrs_confirmed: bool,
        user_identity: str,
        secret_key: str
    ) -> LiveActivationCertificate:
        if not lrs_confirmed:
            raise ValueError("Cannot activate live trading: India RBI LRS cash-only terms must be acknowledged.")
        if max_capital_usd <= 0:
            raise ValueError("Live capital allocation must be greater than $0.00.")
        if not authorized_strategies:
            raise ValueError("Must designate at least one approved strategy for live trading.")

        now_str = datetime.now(timezone.utc).isoformat()
        payload = f"{account_alias}|{','.join(authorized_strategies)}|{max_capital_usd}|{user_identity}|{now_str}"
        sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

        return LiveActivationCertificate(
            account_alias=account_alias,
            authorized_strategies=authorized_strategies,
            max_capital_allocation_usd=max_capital_usd,
            lrs_compliance_acknowledged=lrs_confirmed,
            user_identity=user_identity,
            signed_at_utc=now_str,
            signature=sig
        )
