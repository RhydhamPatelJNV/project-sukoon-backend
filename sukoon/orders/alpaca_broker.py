"""
Project Sukoon — Real Alpaca Paper Trading Broker Client
Dispatches real orders to Alpaca Paper Trading API (https://paper-api.alpaca.markets/v2)
and synchronizes account cash, equity, positions, and live order queues with Alpaca.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import httpx
from sukoon.orders.models import OrderAction, OrderType

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


class AlpacaPaperBroker:
    """Live broker client for Alpaca Paper Trading REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> None:
        self.api_key = api_key or os.getenv("ALPACA_PAPER_API_KEY", "")
        self.secret_key = secret_key or os.getenv("ALPACA_PAPER_SECRET_KEY", "")
        self.base_url = (base_url or os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")).rstrip("/")

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.secret_key and not self.api_key.startswith("MOCK"))

    def get_account(self) -> Optional[Dict[str, Any]]:
        """Fetches live paper trading account balance directly from Alpaca."""
        if not self.is_configured:
            return None
        url = f"{self.base_url}/v2/account"
        try:
            resp = httpx.get(url, headers=self.headers, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[AlpacaBroker] get_account error: {e}")
        return None

    def get_positions(self) -> List[Dict[str, Any]]:
        """Fetches open equity positions directly from Alpaca."""
        if not self.is_configured:
            return []
        url = f"{self.base_url}/v2/positions"
        try:
            resp = httpx.get(url, headers=self.headers, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[AlpacaBroker] get_positions error: {e}")
        return []

    def get_orders(self, status: str = "all", limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches live and queued orders directly from Alpaca."""
        if not self.is_configured:
            return []
        url = f"{self.base_url}/v2/orders?status={status}&limit={limit}&direction=desc"
        try:
            resp = httpx.get(url, headers=self.headers, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[AlpacaBroker] get_orders error: {e}")
        return []

    def submit_order(
        self,
        symbol: str,
        qty: int,
        action: OrderAction,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        time_in_force: str = "day"
    ) -> Dict[str, Any]:
        """Submits real order to Alpaca Paper Trading API.
        
        On weekends and outside RTH, Alpaca accepts and queues the order with status 'accepted'.
        During market hours, Alpaca routes to the exchange for execution.
        """
        if not self.is_configured:
            raise RuntimeError("Alpaca Paper Trading API keys are not configured.")

        url = f"{self.base_url}/v2/orders"
        side = "buy" if action == OrderAction.BUY else "sell"
        order_type_str = "limit" if order_type == OrderType.LIMIT else "market"

        payload: Dict[str, Any] = {
            "symbol": symbol.upper(),
            "qty": str(qty),
            "side": side,
            "type": order_type_str,
            "time_in_force": time_in_force
        }

        if order_type == OrderType.LIMIT and limit_price is not None:
            payload["limit_price"] = f"{limit_price:.2f}"

        if client_order_id:
            payload["client_order_id"] = client_order_id

        try:
            resp = httpx.post(url, headers=self.headers, json=payload, timeout=12.0)
            if resp.status_code in (200, 201):
                data = resp.json()
                print(f"[AlpacaBroker] SUCCESS: Dispatched order to Alpaca: {data.get('id')} ({data.get('status')})")
                return data
            else:
                err_msg = resp.text
                print(f"[AlpacaBroker] Order submission rejected by Alpaca ({resp.status_code}): {err_msg}")
                raise RuntimeError(f"Alpaca API rejected order ({resp.status_code}): {err_msg}")
        except httpx.HTTPError as e:
            print(f"[AlpacaBroker] HTTP error communicating with Alpaca: {e}")
            raise RuntimeError(f"Alpaca connection error: {str(e)}")

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an open or queued order on Alpaca."""
        if not self.is_configured:
            return False
        url = f"{self.base_url}/v2/orders/{order_id}"
        try:
            resp = httpx.delete(url, headers=self.headers, timeout=8.0)
            return resp.status_code in (200, 204)
        except Exception as e:
            print(f"[AlpacaBroker] cancel_order error: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancels all open and queued orders on Alpaca."""
        if not self.is_configured:
            return False
        url = f"{self.base_url}/v2/orders"
        try:
            resp = httpx.delete(url, headers=self.headers, timeout=10.0)
            return resp.status_code in (200, 204, 207)
        except Exception as e:
            print(f"[AlpacaBroker] cancel_all_orders error: {e}")
            return False
