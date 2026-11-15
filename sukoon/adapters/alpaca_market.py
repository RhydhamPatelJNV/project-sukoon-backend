"""
Project Sukoon — Alpaca Market Data Adapter
Complying with G01-R06: Handles IEX vs SIP feeds, timestamps, and Basic plan caveats.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sukoon.adapters.base import BaseProviderAdapter
from sukoon.core.events import EventEnvelope, EventType


class AlpacaMarketDataAdapter(BaseProviderAdapter):
    """Alpaca Market Data API client with strict feed provenance tagging."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        feed: str = "iex",  # "iex" (Free Basic) or "sip" (Paid)
        max_req_per_sec: float = 3.0
    ) -> None:
        super().__init__(provider_name="alpaca_market_data", max_requests_per_second=max_req_per_sec)
        self.api_key = api_key or "MOCK_ALPACA_KEY"
        self.secret_key = secret_key or "MOCK_ALPACA_SECRET"
        self.feed = feed.lower()
        if self.feed not in ("iex", "sip"):
            raise ValueError(f"Invalid Alpaca data feed: {feed}. Must be 'iex' or 'sip'.")

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "feed": self.feed,
            "status": "OPERATIONAL",
            "is_sip": self.feed == "sip",
            "iex_volume_warning": self.feed == "iex"
        }

    def parse_quote(
        self,
        symbol: str,
        bid_price: float,
        ask_price: float,
        bid_size: int,
        ask_size: int,
        exchange: str = "V",  # IEX exchange code
        timestamp_utc: Optional[str] = None
    ) -> EventEnvelope:
        """Normalize raw incoming quote into canonical EventEnvelope."""
        self._apply_rate_limit()
        ts = timestamp_utc or datetime.now(timezone.utc).isoformat()
        
        raw_payload = {
            "symbol": symbol.upper(),
            "bid_price": float(bid_price),
            "ask_price": float(ask_price),
            "bid_size": int(bid_size),
            "ask_size": int(ask_size),
            "exchange": exchange,
            "feed": self.feed,
            "feed_caveat": "IEX_PARTIAL_MARKET_VOLUME" if self.feed == "iex" else "SIP_CONSOLIDATED"
        }

        return EventEnvelope.create(
            event_type=EventType.MARKET_QUOTE_RECEIVED,
            source=f"alpaca_market_data_{self.feed}",
            payload=raw_payload,
            environment="PAPER",
            occurred_at_utc=ts
        )

    def parse_bar(
        self,
        symbol: str,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: int,
        timestamp_utc: Optional[str] = None
    ) -> EventEnvelope:
        """Normalize raw OHLCV bar into canonical EventEnvelope."""
        self._apply_rate_limit()
        ts = timestamp_utc or datetime.now(timezone.utc).isoformat()

        raw_payload = {
            "symbol": symbol.upper(),
            "open": float(open_p),
            "high": float(high_p),
            "low": float(low_p),
            "close": float(close_p),
            "volume": int(volume),
            "feed": self.feed
        }

        return EventEnvelope.create(
            event_type=EventType.MARKET_BAR_RECEIVED,
            source=f"alpaca_market_data_{self.feed}",
            payload=raw_payload,
            environment="PAPER",
            occurred_at_utc=ts
        )
