"""
Project Sukoon — Financial Modeling Prep (FMP) Fundamentals Adapter (G04)
Ingests point-in-time financial statements, balance sheets, and fundamental ratios.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sukoon.adapters.base import BaseProviderAdapter
from sukoon.core.events import EventEnvelope


class FmpFundamentalsAdapter(BaseProviderAdapter):
    """Financial Modeling Prep API adapter for fundamental ratios and financial statements."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_req_per_sec: float = 5.0,
        base_url: str = "https://financialmodelingprep.com/stable"
    ) -> None:
        super().__init__(provider_name="fmp_fundamentals", max_requests_per_second=max_req_per_sec)
        self.api_key = api_key or "MOCK_FMP_KEY"
        self.base_url = base_url

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "OPERATIONAL",
            "api_key_configured": bool(self.api_key and not self.api_key.startswith("MOCK")),
            "rate_limit_rps": 5.0
        }

    def parse_company_profile(
        self,
        symbol: str,
        company_name: str,
        price: float,
        mkt_cap: float,
        beta: float,
        sector: str,
        industry: str
    ) -> EventEnvelope:
        self._apply_rate_limit()
        payload = {
            "symbol": symbol.upper(),
            "company_name": company_name,
            "price": float(price),
            "market_cap": float(mkt_cap),
            "beta": float(beta),
            "sector": sector,
            "industry": industry,
            "provider": "financial_modeling_prep"
        }
        return EventEnvelope.create(
            event_type="market.fundamental.profile_received",
            source="fmp_fundamentals",
            payload=payload,
            environment="RESEARCH"
        )

    def parse_financial_ratios(
        self,
        symbol: str,
        pe_ratio: float,
        pb_ratio: float,
        debt_to_equity: float,
        current_ratio: float,
        roe: float,
        free_cash_flow_yield: float,
        period_date: str
    ) -> EventEnvelope:
        self._apply_rate_limit()
        payload = {
            "symbol": symbol.upper(),
            "pe_ratio": float(pe_ratio),
            "pb_ratio": float(pb_ratio),
            "debt_to_equity": float(debt_to_equity),
            "current_ratio": float(current_ratio),
            "roe": float(roe),
            "free_cash_flow_yield": float(free_cash_flow_yield),
            "period_date": period_date,
            "provider": "financial_modeling_prep"
        }
        return EventEnvelope.create(
            event_type="market.fundamental.ratios_received",
            source="fmp_fundamentals",
            payload=payload,
            environment="RESEARCH"
        )
