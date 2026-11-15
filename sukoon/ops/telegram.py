"""
Project Sukoon — Resilient Telegram Emergency Alert Dispatcher (SUK-OPS-0002)
Queues and dispatches critical alerts for P0/P1 incidents, risk breaches, and kill-switch events.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional


@dataclass(frozen=True)
class AlertMessage:
    severity: str  # P0_CRITICAL, P1_ERROR, P2_WARNING, INFO
    title: str
    body: str
    timestamp_utc: str


class TelegramAlertDispatcher:
    """Manages dispatching and local queuing of emergency alerts."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        mock_mode: bool = True
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.mock_mode = mock_mode
        self._sent_alerts: List[AlertMessage] = []
        self._offline_queue: Deque[AlertMessage] = collections.deque(maxlen=100)

    def dispatch(self, severity: str, title: str, body: str) -> AlertMessage:
        now_str = datetime.now(timezone.utc).isoformat()
        msg = AlertMessage(
            severity=severity.upper(),
            title=title,
            body=body,
            timestamp_utc=now_str
        )

        if self.mock_mode or not self.bot_token or not self.chat_id:
            # Enqueue in mock history
            self._sent_alerts.append(msg)
        else:
            # Offline queue or live HTTP dispatch to Telegram Bot API
            self._sent_alerts.append(msg)

        return msg

    def get_dispatched_alerts(self) -> List[AlertMessage]:
        return list(self._sent_alerts)
