"""
Project Sukoon — Finnhub News & Sentiment Adapter (G05 Sentiment & News Intelligence)
Fetches market and company news with prompt-injection defense and rate-limiting.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sukoon.adapters.base import BaseProviderAdapter
from sukoon.core.events import EventEnvelope, EventType


class FinnhubNewsAdapter(BaseProviderAdapter):
    """Finnhub API adapter with prompt-injection defense (G05-R02)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_req_per_sec: float = 30.0 / 60.0 # Finnhub free tier: 30 calls/minute (~0.5 req/sec)
    ) -> None:
        super().__init__(provider_name="finnhub_news", max_requests_per_second=max_req_per_sec)
        self.api_key = api_key or "MOCK_FINNHUB_KEY"

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "OPERATIONAL",
            "api_key_configured": bool(self.api_key and not self.api_key.startswith("MOCK")),
            "free_tier_rpm_limit": 30
        }

    @staticmethod
    def sanitize_news_content(raw_text: str) -> str:
        """
        Prompt-Injection Defense (G05-R02):
        Strips potential prompt-injection delimiters and treats external headlines strictly as untrusted data.
        """
        sanitized = re.sub(r"(ignore previous instructions|system prompt|disregard|override guardian)", "[FILTERED]", raw_text, flags=re.IGNORECASE)
        # Strip control characters
        sanitized = "".join(ch for ch in sanitized if ch.isprintable())
        return sanitized.strip()

    def parse_news_item(
        self,
        headline: str,
        summary: str,
        source: str,
        symbol: str,
        timestamp_utc: Optional[str] = None
    ) -> EventEnvelope:
        self._apply_rate_limit()
        now_str = timestamp_utc or datetime.now(timezone.utc).isoformat()

        clean_headline = self.sanitize_news_content(headline)
        clean_summary = self.sanitize_news_content(summary)

        payload = {
            "symbol": symbol.upper(),
            "headline": clean_headline,
            "summary": clean_summary,
            "news_source": source,
            "provider": "finnhub",
            "untrusted_data": True # Explicitly tagged as untrusted data
        }

        return EventEnvelope.create(
            event_type="market.news.received",
            source="finnhub_news",
            payload=payload,
            environment="PAPER",
            occurred_at_utc=now_str
        )
