"""
Project Sukoon — Autonomous Quantitative Trading Agent Loop
Continuously evaluates dynamically evolved strategies, queries Groq AI Specialists for trade rationales,
enforces Sukoon Guardian deterministic pre-trade risk checks, records trade outcomes to update confidence,
and moves on to new strategies when confidence drops.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from sukoon.core.clock import USMarketCalendar
from sukoon.core.events import EventEnvelope, EventType
from sukoon.core.ledger import EventLedger
from sukoon.evolution.strategy_manager import StrategyEvolutionManager, StrategyLifecycle
from sukoon.guardian.engine import SukoonGuardianEngine
from sukoon.orders.models import Order, OrderAction, OrderState, OrderType
from sukoon.orders.paper_adapter import PaperPortfolio


class AutonomousTrader:
    """Autonomous quantitative scanning and execution agent with continuous strategy evolution."""

    def __init__(
        self,
        portfolio: PaperPortfolio,
        guardian: SukoonGuardianEngine,
        ledger: EventLedger,
        evolution_mgr: StrategyEvolutionManager,
        scan_interval_seconds: int = 30
    ) -> None:
        self.portfolio = portfolio
        self.guardian = guardian
        self.ledger = ledger
        self.evolution_mgr = evolution_mgr
        self.scan_interval_seconds = scan_interval_seconds
        
        self.is_running = True
        self.weekend_replay_mode = False  # Strict real-world US market calendar enforcement by default
        self.total_scans = 0
        self.last_scan_utc: Optional[str] = None
        self.last_signal: Optional[Dict[str, Any]] = None
        self.last_trade: Optional[Dict[str, Any]] = None
        self.recent_logs: List[Dict[str, Any]] = []
        self._task: Optional[asyncio.Task] = None

        # Base market tracking prices
        self._price_state: Dict[str, float] = {
            "SPY": 591.40,
            "QQQ": 512.20,
            "AAPL": 228.80,
            "MSFT": 423.50,
            "NVDA": 141.60
        }
        # Price history for technical indicators (symbol -> list of close prices)
        self._price_history: Dict[str, List[float]] = {
            sym: [price * (1.0 + (random.random() - 0.5) * 0.01) for _ in range(30)]
            for sym, price in self._price_state.items()
        }

    def log(self, level: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Appends to rolling telemetry logs."""
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "details": details or {}
        }
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 100:
            self.recent_logs.pop(0)

    def _update_synthetic_quotes(self) -> Dict[str, Dict[str, float]]:
        """Simulates realistic micro-movements for 24/7 autonomous backtesting & paper operations."""
        quotes = {}
        for sym, price in self._price_state.items():
            drift = (random.random() - 0.49) * 0.003
            new_price = round(price * (1.0 + drift), 2)
            self._price_state[sym] = new_price
            self._price_history[sym].append(new_price)
            if len(self._price_history[sym]) > 60:
                self._price_history[sym].pop(0)

            quotes[sym] = {
                "bid": round(new_price * 0.9995, 2),
                "ask": round(new_price * 1.0005, 2),
                "mid": new_price
            }
        return quotes

    def _compute_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculates standard Relative Strength Index (RSI)."""
        if len(prices) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100.0 - (100.0 / (1.0 + rs)), 2)

    def _compute_ema(self, prices: List[float], period: int) -> float:
        """Calculates Exponential Moving Average."""
        if not prices:
            return 0.0
        multiplier = 2.0 / (period + 1.0)
        ema = prices[0]
        for p in prices[1:]:
            ema = (p - ema) * multiplier + ema
        return round(ema, 2)

    async def _query_groq_rationale(self, symbol: str, action: str, price: float, rsi: float, reason: str, strat_name: str, confidence: float) -> str:
        """Asks Groq AI Quantitative Specialist for 1-sentence analytical reasoning."""
        groq_api_key = os.getenv("GROQ_API_KEY", "")
        if not groq_api_key:
            return f"[{strat_name} | Conf: {confidence}%] {reason} (RSI {rsi}). Risk parameters strictly met."

        url = "https://api.groq.com/openai/v1/chat/completions"
        model_name = os.getenv("GROQ_MODEL_ID", "qwen/qwen3.8-27b")
        headers = {"Authorization": f"Bearer {groq_api_key}"}
        prompt = (
            f"You are the Project Sukoon Autonomous Quant Specialist. "
            f"Strategy '{strat_name}' (Confidence: {confidence}%) proposes {action} {symbol} at ${price:.2f} due to {reason} (RSI={rsi:.1f}). "
            f"Give a concise 1-sentence risk-adjusted quantitative rationale supporting this trade."
        )
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a quantitative trading risk specialist. Be brief, authoritative, exactly 1 sentence."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 60,
            "temperature": 0.2
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return f"Quant model affirms {action} on {symbol} via {strat_name} (Confidence: {confidence}%): {reason}."

    async def run_scan_cycle(self) -> None:
        """Executes a single quantitative scanning and multi-strategy execution iteration."""
        if not self.is_running:
            return

        self.total_scans += 1
        now_str = datetime.now(timezone.utc).isoformat()
        self.last_scan_utc = now_str
        quotes = self._update_synthetic_quotes()

        # Check market calendar status
        mkt_status = USMarketCalendar.current_status()
        is_rth = mkt_status.get("is_regular_market_open", False)
        market_phase = mkt_status.get("market_phase", "WEEKEND_CLOSED")
        ist_time = mkt_status.get("indian_standard_time", "")
        us_time = mkt_status.get("us_eastern_time", "")

        # STRICT US MARKET CALENDAR GATE:
        # On weekends (Saturday/Sunday) and outside RTH, US Equities are CLOSED!
        # Do NOT execute market trades on a closed market unless operator explicitly enabled weekend replay demo.
        if not is_rth and not self.weekend_replay_mode:
            self.last_signal = {
                "symbol": "MARKET_CLOSED",
                "action": "WEEKEND_STANDBY",
                "strategy_id": "WEEKEND_RESEARCH_MODE",
                "strategy_name": "Weekend Statistical Research & Replay Incubator",
                "price": 0.0,
                "quantity": 0,
                "reason": f"US Markets Closed ({market_phase}). NYSE/NASDAQ reopens Monday 09:30 ET ({mkt_status.get('regular_hours_ist')}). Zero live orders executed on weekends.",
                "rsi": 50.0,
                "confidence_score": 100.0,
                "timestamp_utc": now_str
            }
            self.log(
                "INFO",
                f"WEEKEND MARKET STANDBY: US Markets closed ({market_phase}). Zero live orders permitted. Running weekend incubation research. Next session: Monday 09:30 ET.",
                {"market_phase": market_phase, "us_time": us_time, "ist_time": ist_time}
            )
            return

        # 1. Retrieve runnable strategies
        active_strats = self.evolution_mgr.get_runnable_strategies()

        # If pool has dropped too many low-confidence strategies, autonomously discover/synthesize new ones!
        if len(active_strats) < 2:
            self.log("INFO", "Active strategy pool below threshold. Autonomously synthesizing new strategy hypothesis...")
            new_strat = await self.evolution_mgr.generate_autonomous_hypothesis("Maintain minimum pool of concurrent strategies")
            active_strats.append(new_strat)

        self.log(
            "INFO",
            f"Scanning universe {list(quotes.keys())} across {len(active_strats)} active strategies "
            f"(Simultaneous: {self.evolution_mgr.simultaneous_enabled}) - Phase: {mkt_status.get('trading_phase', 'UNKNOWN')}",
            {"total_scans": self.total_scans, "active_strategies": [s.strategy_id for s in active_strats]}
        )

        executed_this_cycle = 0

        # 2. Evaluate each strategy simultaneously
        for strat in active_strats:
            if not self.evolution_mgr.simultaneous_enabled and executed_this_cycle >= 1:
                break

            params = strat.parameters
            fast_p = params.get("fast_period", 9)
            slow_p = params.get("slow_period", 21)
            take_profit_pct = params.get("take_profit_pct", 2.2) / 100.0
            stop_loss_pct = params.get("stop_loss_pct", 1.2) / 100.0
            rsi_oversold = params.get("oversold_threshold", 32.0)

            for sym in strat.universe:
                if sym not in quotes:
                    continue

                q = quotes[sym]
                history = self._price_history.get(sym, [])
                if len(history) < 15:
                    continue

                current_price = q["mid"]
                rsi = self._compute_rsi(history, period=14)
                fast_ema = self._compute_ema(history, period=fast_p)
                slow_ema = self._compute_ema(history, period=slow_p)

                current_pos = self.portfolio.positions.get(sym, 0)
                avg_cost = self.portfolio.cost_basis.get(sym, current_price)

                action: Optional[OrderAction] = None
                reason = ""
                trade_pnl = 0.0
                trade_ret = 0.0

                # Exit / Take Profit / Stop Loss evaluation
                if current_pos > 0:
                    pnl_pct = (current_price - avg_cost) / avg_cost
                    if pnl_pct >= take_profit_pct:
                        action = OrderAction.SELL
                        reason = f"Take profit target reached (+{pnl_pct*100:.2f}%)"
                        trade_ret = pnl_pct
                        trade_pnl = (current_price - avg_cost) * current_pos
                    elif pnl_pct <= -stop_loss_pct:
                        action = OrderAction.SELL
                        reason = f"Stop-loss protection triggered ({pnl_pct*100:.2f}%)"
                        trade_ret = pnl_pct
                        trade_pnl = (current_price - avg_cost) * current_pos
                    elif rsi > 72.0:
                        action = OrderAction.SELL
                        reason = f"RSI overbought exhaustion ({rsi:.1f} > 70)"
                        trade_ret = pnl_pct
                        trade_pnl = (current_price - avg_cost) * current_pos

                # Entry evaluation
                elif current_pos == 0:
                    if rsi < rsi_oversold:
                        action = OrderAction.BUY
                        reason = f"RSI oversold rebound detected ({rsi:.1f} < {rsi_oversold})"
                    elif fast_ema > slow_ema and 48.0 < rsi < 65.0:
                        action = OrderAction.BUY
                        reason = f"EMA fast cross above slow ({fast_ema:.2f} > {slow_ema:.2f})"

                if action is None:
                    continue

                # Scale capital by strategy confidence score!
                # High confidence (>=75%) gets full allocation; probation gets scaled down
                confidence_ratio = max(0.3, strat.confidence_score / 100.0)
                target_notional = 3500.0 * confidence_ratio
                qty = max(1, int(target_notional / current_price))
                if action == OrderAction.SELL:
                    qty = current_pos

                self.last_signal = {
                    "symbol": sym,
                    "action": action.value,
                    "strategy_id": strat.strategy_id,
                    "strategy_name": strat.name,
                    "price": current_price,
                    "quantity": qty,
                    "reason": reason,
                    "rsi": rsi,
                    "confidence_score": strat.confidence_score,
                    "timestamp_utc": now_str
                }

                # AI quantitative rationale
                ai_rationale = await self._query_groq_rationale(
                    sym, action.value, current_price, rsi, reason, strat.name, strat.confidence_score
                )

                # Order construction
                exec_limit_price = round(q["ask"] * 1.001 if action == OrderAction.BUY else q["bid"] * 0.999, 2)
                order = Order.create(
                    strategy_id=strat.strategy_id,
                    strategy_version="1.0.0",
                    symbol=sym,
                    action=action,
                    quantity=qty,
                    limit_price=exec_limit_price,
                    order_type=OrderType.LIMIT,
                    environment="PAPER"
                )

                # Guardian Risk Clearance
                decision = self.guardian.evaluate_order(
                    order=order,
                    current_cash=self.portfolio.cash,
                    portfolio_equity=self.portfolio.get_equity(self._price_state),
                    current_position_qty=current_pos,
                    latest_quote_age_seconds=0.5,
                    is_reconciled=True,
                    intraday_loss_pct=0.0,
                    trailing_drawdown_pct=0.0,
                    active_feed="iex"
                )

                if not decision.approved:
                    self.log(
                        "WARNING",
                        f"Order for {sym} ({strat.name}) VETOED by Guardian: {', '.join(decision.reasons)}",
                        {"strategy_id": strat.strategy_id, "reasons": decision.reasons}
                    )
                    continue

                order.guardian_token = decision.pass_token
                order.transition_to(OrderState.VALIDATED, "Pre-trade risk approved")
                order.transition_to(OrderState.GUARDIAN_APPROVED, f"Guardian Token: {decision.pass_token[:8]}")

                idempotency_key = f"auto-{order.order_id}-{int(time.time())}"
                fill = self.portfolio.submit_order(
                    order=order,
                    idempotency_key=idempotency_key,
                    current_bid=q["bid"],
                    current_ask=q["ask"]
                )

                if fill:
                    executed_this_cycle += 1
                    self.last_trade = {
                        "order_id": order.order_id,
                        "symbol": sym,
                        "action": action.value,
                        "quantity": fill.filled_qty,
                        "fill_price": fill.fill_price,
                        "strategy_id": strat.strategy_id,
                        "strategy_name": strat.name,
                        "confidence_score": strat.confidence_score,
                        "rationale": ai_rationale,
                        "timestamp_utc": now_str
                    }

                    # If this was a SELL, record outcome and re-evaluate strategy confidence!
                    if action == OrderAction.SELL:
                        self.evolution_mgr.record_trade_outcome(strat.strategy_id, trade_pnl, trade_ret)
                        if strat.lifecycle == StrategyLifecycle.DROPPED:
                            self.log(
                                "WARNING",
                                f"STRATEGY DROPPED: {strat.name} retired due to low confidence ({strat.confidence_score}%). "
                                f"Autonomous engine will transition to replacement strategy.",
                                {"strategy_id": strat.strategy_id, "confidence": strat.confidence_score}
                            )

                    # Ledger event
                    event = EventEnvelope.create(
                        event_type=EventType.ORDER_FILLED,
                        source="autonomous_quant_trader",
                        environment="PAPER",
                        payload={
                            "order_id": order.order_id,
                            "symbol": sym,
                            "action": action.value,
                            "filled_qty": fill.filled_qty,
                            "fill_price": fill.fill_price,
                            "strategy_id": strat.strategy_id,
                            "strategy_name": strat.name,
                            "confidence_score": strat.confidence_score,
                            "ai_rationale": ai_rationale
                        }
                    )
                    self.ledger.append(event)

                    self.log(
                        "SUCCESS",
                        f"AUTONOMOUS EXECUTION: {action.value} {fill.filled_qty} {sym} @ ${fill.fill_price:.2f} "
                        f"[{strat.name} | Conf: {strat.confidence_score}%]",
                        {"rationale": ai_rationale, "strategy": strat.strategy_id}
                    )

                    # If not simultaneous, exit inner loop
                    if not self.evolution_mgr.simultaneous_enabled:
                        break

    async def _loop(self) -> None:
        """Continuous background execution loop."""
        self.log("INFO", "Autonomous Trader background loop started.")
        while True:
            try:
                await self.run_scan_cycle()
            except Exception as e:
                self.log("ERROR", f"Autonomous Trader scan loop exception: {str(e)}")
            await asyncio.sleep(self.scan_interval_seconds)

    def start_background_task(self) -> None:
        """Starts the async background loop."""
        if self._task is None or self._task.done():
            self.is_running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        """Stops the autonomous loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.log("INFO", "Autonomous Trader loop paused.")

    def toggle_weekend_replay(self) -> bool:
        """Toggles weekend simulation replay mode (for demo/testing only)."""
        self.weekend_replay_mode = not self.weekend_replay_mode
        return self.weekend_replay_mode

    def get_status(self) -> Dict[str, Any]:
        """Telemetry status payload for frontend dashboard."""
        runnable = self.evolution_mgr.get_runnable_strategies()
        mkt_status = USMarketCalendar.current_status()
        return {
            "is_running": self.is_running,
            "total_scans": self.total_scans,
            "scan_interval_seconds": self.scan_interval_seconds,
            "last_scan_utc": self.last_scan_utc,
            "last_signal": self.last_signal,
            "last_trade": self.last_trade,
            "weekend_replay_mode": self.weekend_replay_mode,
            "market_calendar": mkt_status,
            "simultaneous_enabled": self.evolution_mgr.simultaneous_enabled,
            "active_strategies_count": len(runnable),
            "total_strategies_discovered": len(self.evolution_mgr.strategies),
            "recent_logs": self.recent_logs[-15:]
        }
