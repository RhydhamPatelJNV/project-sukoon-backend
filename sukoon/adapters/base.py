"""
Project Sukoon — Market Data & External Provider Base Adapter
Provides rate limiting, exponential backoff with jitter, and provenance hashing.
"""
from __future__ import annotations

import abc
import hashlib
import json
import time
from typing import Any, Dict, Optional


class BaseProviderAdapter(abc.ABC):
    """Abstract base adapter for external API integrations."""

    def __init__(self, provider_name: str, max_requests_per_second: float = 5.0) -> None:
        self.provider_name = provider_name
        self.min_interval = 1.0 / max_requests_per_second
        self._last_request_time: float = 0.0

    def _apply_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.monotonic()

    @staticmethod
    def compute_payload_hash(data: Any) -> str:
        serialized = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health and connectivity probe."""
        pass
