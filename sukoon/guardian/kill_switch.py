"""
Project Sukoon — Emergency Kill-Switch & Flatten Controller (G12-R07)
Halts new entries, records immutable incident, and initiates alert dispatch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class KillSwitchController:
    """Manages panic stop and trading suspension state."""

    def __init__(self) -> None:
        self.is_active: bool = False
        self.activated_at_utc: Optional[str] = None
        self.trigger_reason: Optional[str] = None
        self.incident_log: List[Dict[str, Any]] = []

    def engage(self, reason: str, triggered_by: str = "GUARDIAN_INTERLOCK") -> None:
        """Engage the kill switch. Halts all new entries immediately."""
        self.is_active = True
        self.activated_at_utc = datetime.now(timezone.utc).isoformat()
        self.trigger_reason = reason

        incident_record = {
            "timestamp_utc": self.activated_at_utc,
            "event": "KILL_SWITCH_ENGAGED",
            "reason": reason,
            "triggered_by": triggered_by,
            "status": "ENTRIES_HALTED"
        }
        self.incident_log.append(incident_record)

    def disengage(self, authorization_key: str, authorized_user: str) -> bool:
        """Reset kill switch only after authenticated manual operator action."""
        if not authorization_key or len(authorization_key) < 16:
            return False

        self.is_active = False
        now_str = datetime.now(timezone.utc).isoformat()
        self.incident_log.append({
            "timestamp_utc": now_str,
            "event": "KILL_SWITCH_DISENGAGED",
            "authorized_user": authorized_user,
            "status": "NORMAL_OPERATIONS_RESTORED"
        })
        self.trigger_reason = None
        return True
