"""
Project Sukoon — Clock Abstraction
Provides deterministic time virtualization for live, paper, and historical replay backtests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class SukoonClock:
    """Clock provider allowing seamless switching between wall-clock UTC and simulated replay time."""

    def __init__(self, simulated_start_utc: Optional[datetime] = None) -> None:
        self._simulated_time: Optional[datetime] = simulated_start_utc
        self._is_simulated = simulated_start_utc is not None

    def now(self) -> datetime:
        if self._is_simulated and self._simulated_time is not None:
            return self._simulated_time
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        return self.now().isoformat()

    def advance_to(self, target_time: datetime) -> None:
        """Advance simulated time monotonically. Rejects backwards jumps."""
        if not self._is_simulated:
            raise RuntimeError("Cannot advance clock when running in live wall-clock mode.")
        if self._simulated_time and target_time < self._simulated_time:
            raise ValueError(f"Clock cannot move backwards from {self._simulated_time} to {target_time}.")
        self._simulated_time = target_time

    def set_live(self) -> None:
        """Return clock to live system UTC time."""
        self._is_simulated = False
        self._simulated_time = None

    @property
    def is_simulated(self) -> bool:
        return self._is_simulated
