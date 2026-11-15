"""
Project Sukoon — Symbol Master & Symbology Custodian (G01-R01)
Maintains point-in-time universe, splits, delistings, and extended-hours eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Set


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    asset_class: str  # US_EQUITY, US_ETF
    exchange: str     # NASDAQ, NYSE, ARCA, BATS, IEX
    is_active: bool
    extended_hours_eligible: bool
    lot_size: int = 1
    currency: str = "USD"


class SymbolMaster:
    """Deterministic Symbol Master maintaining approved tradable universe."""

    def __init__(self) -> None:
        self._universe: Dict[str, Instrument] = {}
        self._blacklist: Set[str] = set()
        self._split_history: Dict[str, List[Dict[str, Any]]] = {}
        self._load_baseline_universe()

    def _load_baseline_universe(self) -> None:
        """Seed high-liquidity, large-cap US equities and broad-market ETFs."""
        baseline = [
            Instrument("SPY", "SPDR S&P 500 ETF Trust", "US_ETF", "ARCA", True, False),
            Instrument("QQQ", "Invesco QQQ Trust", "US_ETF", "NASDAQ", True, False),
            Instrument("AAPL", "Apple Inc.", "US_EQUITY", "NASDAQ", True, False),
            Instrument("MSFT", "Microsoft Corporation", "US_EQUITY", "NASDAQ", True, False),
            Instrument("NVDA", "NVIDIA Corporation", "US_EQUITY", "NASDAQ", True, False),
            Instrument("AMZN", "Amazon.com Inc.", "US_EQUITY", "NASDAQ", True, False),
            Instrument("GOOGL", "Alphabet Inc. Class A", "US_EQUITY", "NASDAQ", True, False),
            Instrument("META", "Meta Platforms Inc.", "US_EQUITY", "NASDAQ", True, False),
            Instrument("TSLA", "Tesla Inc.", "US_EQUITY", "NASDAQ", True, False),
            Instrument("BRK.B", "Berkshire Hathaway Inc. Class B", "US_EQUITY", "NYSE", True, False)
        ]
        for inst in baseline:
            self._universe[inst.symbol] = inst

    def get_instrument(self, symbol: str) -> Optional[Instrument]:
        return self._universe.get(symbol.upper())

    def is_tradable(self, symbol: str) -> tuple[bool, str]:
        sym = symbol.upper()
        if sym in self._blacklist:
            return False, f"Symbol {sym} is blacklisted or delisted."
        inst = self._universe.get(sym)
        if not inst:
            return False, f"Symbol {sym} not found in approved Symbol Master universe."
        if not inst.is_active:
            return False, f"Symbol {sym} is marked inactive/halted."
        return True, "Tradable"

    def blacklist_symbol(self, symbol: str, reason: str) -> None:
        self._blacklist.add(symbol.upper())

    def record_split(self, symbol: str, ex_date: str, ratio: float) -> None:
        """Record corporate action stock split ratio (e.g. 2.0 for 2-for-1 split)."""
        sym = symbol.upper()
        if sym not in self._split_history:
            self._split_history[sym] = []
        self._split_history[sym].append({"ex_date": ex_date, "ratio": ratio})

    def adjust_price_for_splits(self, symbol: str, price: float, as_of_date: str) -> float:
        """Point-in-time split adjustment."""
        sym = symbol.upper()
        adj_price = price
        if sym in self._split_history:
            for s in self._split_history[sym]:
                if as_of_date < s["ex_date"]:
                    adj_price = adj_price / s["ratio"]
        return adj_price
