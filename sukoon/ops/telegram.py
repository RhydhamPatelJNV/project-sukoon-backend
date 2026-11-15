"""
Project Sukoon — Live Telegram Alert Dispatcher (SUK-OPS-0002)
Dispatches real-time alerts to the operator's Telegram channel for orders,
Guardian risk evaluations, strategy evolutions, and high-impact breaking news.
"""
from __future__ import annotations

import collections
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

import httpx

try:
    from dotenv import load_dotenv
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_file = os.path.join(backend_root, ".env")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class AlertMessage:
    severity: str  # P0_CRITICAL, P1_ERROR, P2_WARNING, INFO, TRADE_EXECUTION
    title: str
    body: str
    timestamp_utc: str
    telegram_dispatched: bool = False


class TelegramAlertDispatcher:
    """Dispatches live operational and trading alerts directly to Telegram Bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._sent_alerts: List[AlertMessage] = []
        self._offline_queue: Deque[AlertMessage] = collections.deque(maxlen=100)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and not self.bot_token.startswith("change-me"))

    def dispatch(self, severity: str, title: str, body: str) -> AlertMessage:
        """Dispatches real alert message via Telegram Bot API."""
        now_str = datetime.now(timezone.utc).isoformat()
        dispatched = False

        # Format emoji icons based on severity
        severity_clean = severity.upper()
        emoji = "ℹ️"
        if "CRITICAL" in severity_clean or "P0" in severity_clean:
            emoji = "🚨"
        elif "ERROR" in severity_clean or "P1" in severity_clean:
            emoji = "⚠️"
        elif "TRADE" in severity_clean or "ORDER" in severity_clean:
            emoji = "⚡"
        elif "GUARDIAN" in severity_clean:
            emoji = "🛡️"
        elif "NEWS" in severity_clean:
            emoji = "📰"

        formatted_text = f"{emoji} *[Project Sukoon — {title}]*\n\n{body}\n\n_Timestamp: {now_str}_"

        if self.is_configured:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": formatted_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            try:
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        dispatched = True
                    else:
                        print(f"[TelegramDispatcher] Telegram API returned {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[TelegramDispatcher] Notice: Live Telegram dispatch error: {e}")

        msg = AlertMessage(
            severity=severity_clean,
            title=title,
            body=body,
            timestamp_utc=now_str,
            telegram_dispatched=dispatched
        )
        self._sent_alerts.append(msg)
        if len(self._sent_alerts) > 200:
            self._sent_alerts.pop(0)

        return msg

    def dispatch_trade_alert(
        self,
        action: str,
        symbol: str,
        quantity: int,
        price: float,
        strategy_id: str,
        order_id: str,
        status: str,
        alpaca_queued: bool = True
    ) -> AlertMessage:
        """Helper to format and dispatch instant execution & queued order notifications."""
        title = f"Order {status.upper()}: {action} {quantity} {symbol}"
        body = (
            f"• *Symbol:* `{symbol}`\n"
            f"• *Action:* `{action}` ({quantity} shares @ ${price:.2f})\n"
            f"• *Total Notional:* `${(quantity * price):.2f}`\n"
            f"• *Strategy:* `{strategy_id}`\n"
            f"• *Alpaca Order ID:* `{order_id}`\n"
            f"• *Alpaca Gateway Status:* `{status.upper()}`\n"
            f"• *Exchange State:* {'Queued for Monday 09:30 ET Open' if alpaca_queued else 'Filled'}"
        )
        return self.dispatch(severity="TRADE_EXECUTION", title=title, body=body)

    def dispatch_guardian_alert(self, approved: bool, symbol: str, reasons: List[str], cash: float) -> AlertMessage:
        """Helper for Sukoon Guardian pre-trade risk decisions."""
        status_text = "APPROVED" if approved else "VETOED"
        title = f"Sukoon Guardian Decision: {status_text} ({symbol})"
        body = (
            f"• *Pre-Trade Verdict:* `{status_text}`\n"
            f"• *Target Symbol:* `{symbol}`\n"
            f"• *Cash Balance:* `${cash:,.2f}` (LRS Zero-Leverage)\n"
            f"• *Reasons:* {', '.join(reasons) if reasons else 'All pre-trade risk checks passed'}"
        )
        return self.dispatch(severity="GUARDIAN_DECISION", title=title, body=body)

    def get_dispatched_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [
            {
                "severity": a.severity,
                "title": a.title,
                "body": a.body,
                "timestamp_utc": a.timestamp_utc,
                "telegram_dispatched": a.telegram_dispatched
            }
            for a in reversed(self._sent_alerts)
        ][:limit]
