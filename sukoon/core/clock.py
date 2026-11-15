"""
Project Sukoon — Clock Abstraction
Provides deterministic time virtualization for live, paper, and historical replay backtests.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional


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


class USMarketCalendar:
    """Accurately calculates US Stock Market (NYSE/NASDAQ) trading status,
    automatically handling Daylight Saving Time (EST vs EDT) and converting
    between US Eastern, UTC, and Indian Standard Time (IST) deterministically."""

    # Regular Trading Hours (RTH): 9:30 AM to 4:00 PM Eastern Time
    RTH_OPEN = time(9, 30)
    RTH_CLOSE = time(16, 0)

    # Pre-market: 4:00 AM to 9:30 AM Eastern
    PRE_OPEN = time(4, 0)
    # Post-market: 4:00 PM to 8:00 PM Eastern
    POST_CLOSE = time(20, 0)

    INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

    @classmethod
    def is_us_dst(cls, dt_utc: datetime) -> bool:
        """Calculates whether US Eastern Time is in Daylight Saving Time (EDT, UTC-4) or Standard Time (EST, UTC-5)."""
        year = dt_utc.year
        # Second Sunday in March at 02:00 local (07:00 UTC)
        mar1 = datetime(year, 3, 1, tzinfo=timezone.utc)
        second_sun_mar = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
        dst_start = datetime(year, 3, second_sun_mar.day, 7, 0, tzinfo=timezone.utc)

        # First Sunday in November at 02:00 local (06:00 UTC)
        nov1 = datetime(year, 11, 1, tzinfo=timezone.utc)
        first_sun_nov = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)
        dst_end = datetime(year, 11, first_sun_nov.day, 6, 0, tzinfo=timezone.utc)

        return dst_start <= dt_utc < dst_end

    @classmethod
    def get_eastern_tz(cls, dt_utc: datetime) -> timezone:
        offset_hours = -4 if cls.is_us_dst(dt_utc) else -5
        return timezone(timedelta(hours=offset_hours))

    @classmethod
    def current_status(cls, at_utc: Optional[datetime] = None) -> Dict[str, Any]:
        dt_utc = at_utc or datetime.now(timezone.utc)
        dst_active = cls.is_us_dst(dt_utc)
        tz_name = "EDT" if dst_active else "EST"
        eastern_tz = cls.get_eastern_tz(dt_utc)

        dt_eastern = dt_utc.astimezone(eastern_tz)
        dt_india = dt_utc.astimezone(cls.INDIA_TZ)

        weekday = dt_eastern.weekday()  # 0 = Monday, 6 = Sunday
        is_weekend = weekday >= 5
        curr_time = dt_eastern.time()

        if is_weekend:
            phase = "WEEKEND_CLOSED"
            is_open = False
        elif cls.RTH_OPEN <= curr_time < cls.RTH_CLOSE:
            phase = "REGULAR_MARKET_OPEN"
            is_open = True
        elif cls.PRE_OPEN <= curr_time < cls.RTH_OPEN:
            phase = "PRE_MARKET"
            is_open = False
        elif cls.RTH_CLOSE <= curr_time < cls.POST_CLOSE:
            phase = "AFTER_HOURS"
            is_open = False
        else:
            phase = "OVERNIGHT_CLOSED"
            is_open = False

        ist_open = "19:00 IST" if dst_active else "20:00 IST"
        ist_close = "01:30 IST" if dst_active else "02:30 IST"

        return {
            "is_regular_market_open": is_open,
            "market_phase": phase,
            "us_eastern_time": f"{dt_eastern.strftime('%Y-%m-%d %H:%M:%S')} {tz_name}",
            "indian_standard_time": dt_india.strftime("%Y-%m-%d %H:%M:%S IST"),
            "utc_time": dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "regular_hours_us": "09:30 - 16:00 Eastern",
            "regular_hours_ist": f"{ist_open} - {ist_close}",
            "is_dst_active": dst_active,
            "time_zone_difference": "India is 10.5 hours ahead of US EST (or 9.5 hours ahead of EDT)"
        }
