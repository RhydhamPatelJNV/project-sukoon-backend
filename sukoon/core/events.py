"""
Project Sukoon — Deterministic Event Core
Canonical Event Envelope, Event Types, and Immutability Enforcers.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    # System Lifecycle
    SYSTEM_STARTED = "system.started"
    SYSTEM_PAUSED = "system.paused"
    SYSTEM_SAFE_MODE = "system.safe_mode"
    KILL_SWITCH_ENGAGED = "system.kill_switch_engaged"

    # Market Data
    MARKET_QUOTE_RECEIVED = "market.quote.received"
    MARKET_BAR_RECEIVED = "market.bar.received"
    MARKET_DATA_QUARANTINED = "market.data.quarantined"
    CORPORATE_ACTION_SPLIT = "market.corporate_action.split"

    # Research & Strategy
    STRATEGY_REGISTERED = "strategy.registered"
    BACKTEST_COMPLETED = "strategy.backtest_completed"
    VALIDATION_PASSED = "strategy.validation_passed"
    VALIDATION_VETOED = "strategy.validation_vetoed"

    # Specialist Intelligence
    SPECIALIST_TASK_SCHEDULED = "specialist.task.scheduled"
    SPECIALIST_OUTPUT_COMPLETED = "specialist.output.completed"
    SPECIALIST_QUARANTINED = "specialist.quarantined"

    # Guardian & Risk
    GUARDIAN_EVALUATION_STARTED = "guardian.evaluation_started"
    GUARDIAN_APPROVED = "guardian.approved"
    GUARDIAN_VETOED = "guardian.vetoed"
    RISK_LIMIT_BREACHED = "guardian.risk_limit_breached"

    # Order & Execution
    ORDER_CREATED = "order.created"
    ORDER_VALIDATED = "order.validated"
    ORDER_SUBMITTED = "order.submitted"
    ORDER_ACKNOWLEDGED = "order.acknowledged"
    ORDER_FILLED = "order.filled"
    ORDER_PARTIALLY_FILLED = "order.partially_filled"
    ORDER_REJECTED = "order.rejected"
    ORDER_CANCELED = "order.canceled"
    ORDER_RECONCILIATION_GAP = "order.reconciliation_gap"


def generate_event_id() -> str:
    """Generate a lexicographically sortable UUIDv7-compatible identifier."""
    # Using uuid4 with current timestamp prefix for predictable ordering
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"{now_ms:012x}-{uuid.uuid4().hex[:20]}"


@dataclass(frozen=True)
class EventEnvelope:
    """Canonical immutable event envelope complying with SUK-DATA-0001."""
    event_id: str
    event_type: str
    schema_version: int
    occurred_at_utc: str
    received_at_utc: str
    processed_at_utc: str
    source: str
    environment: str  # RESEARCH, PAPER, LIVE
    correlation_id: str
    payload: Dict[str, Any]
    payload_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload_bytes = json.dumps(self.payload, sort_keys=True).encode("utf-8")
        computed_hash = hashlib.sha256(payload_bytes).hexdigest()
        object.__setattr__(self, "payload_hash", computed_hash)

    @classmethod
    def create(
        cls,
        event_type: EventType | str,
        source: str,
        payload: Dict[str, Any],
        environment: str = "PAPER",
        correlation_id: Optional[str] = None,
        schema_version: int = 1,
        occurred_at_utc: Optional[str] = None
    ) -> EventEnvelope:
        now_str = datetime.now(timezone.utc).isoformat()
        return cls(
            event_id=generate_event_id(),
            event_type=event_type.value if isinstance(event_type, EventType) else event_type,
            schema_version=schema_version,
            occurred_at_utc=occurred_at_utc or now_str,
            received_at_utc=now_str,
            processed_at_utc=now_str,
            source=source,
            environment=environment.upper(),
            correlation_id=correlation_id or uuid.uuid4().hex,
            payload=payload
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "occurred_at_utc": self.occurred_at_utc,
            "received_at_utc": self.received_at_utc,
            "processed_at_utc": self.processed_at_utc,
            "source": self.source,
            "environment": self.environment,
            "correlation_id": self.correlation_id,
            "payload_hash": self.payload_hash,
            "payload": self.payload
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)
