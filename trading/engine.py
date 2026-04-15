"""
CozyCryptoAI — Institutional Futures Engine
Universal scanner + institutional-grade analysis
Liquidity | Order Flow | Footprint | Market Structure |
Accumulation/Distribution | Execution Zones | Volatility | Order Book
"""

import asyncio
import logging
from trading.bitget_client import BitgetClient
from trading.strategy import InstitutionalStrategy, Signal
from trading.scanner import MarketScanner
from config import (
    MAX_POSITION_SIZE_PERCENT, MAX_OPEN_POSITIONS,
    SCALP_INTERVAL_SECONDS, LEVERAGE, MARGIN_MODE
)

logger = logging.getLogger("TradingEngine")


class TradingEngine:
    def __init__(self, brain=None):
        self.client   = BitgetClient()
        self.strategy = InstitutionalStrategy()
        self.scanner  = MarketScanner(self.client)
        self.brain    = brain

        self.active   = True
        self.paused   = False
        self.open_positions    = {}
        self.pnl_total         = 0.0
        self.initialized_syms  = set()
        self.last_scan_results = []
        self.total_scanned     = 0

    # ── Control ───────────────────────────────────────────────────────────────

    def pause(self):
        self.paused = True
        logger.info("Trading paused")

    def resume(self):
        self.paused = False
        logger.info("Trading resumed")

    def stop(self):
        self.active = False

    # ── Leverage Init ─────────────────────────────────────────────────────────

    async def _init_symbol(self, symbol: str):
        if symbol in self.initialized_syms:
            return
        try:
            await self.client.set_margin_mode(symbol, MARGIN_MODE)
            await self.client.set_leverage(symbol, LEVERAGE, "long")
            await self.client.set_leverage(symbol, LEVERAGE, "short")
            self.initialized_syms.add(symbol)
        except Exception as e:
            logger.warning(f"Init warning {symbol}: {e}")

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def run(self):
        logger.info(f"🚀 Institutional Engine — {LEVERAGE}x | {MARGIN_MODE} margin | Universal scanner")
        while self.active:
            try:
                if not self.paused:
                    await self._scan_and_trade()
                await self._sync_positions()
            except Exception as e:
                logger.error(f"Engine loop error: {e}")
            await asyncio.sleep(SCALP_INTERVAL_SECONDS)

    async def _scan_and_trade(self):
        balance = await self.client.get_account_balance()
        available_usdt = balance["available"]

        if available_usdt < 5:
            logger.warning("Insufficient balance")
            return

        open_count = len(self.open_positions)
        if open_count >= MAX_OPEN_POSITIONS:
            return

        # Universal scan — ranks ALL pairs by score
        opportunities = await self.scanner.scan_market()
        self.last_scan_results = opportunities
        self.total_scanned += 1

        slots = MAX_OPEN_POSITIONS - open_count
        trades_opened = 0

        for opp in opportunities:
            if trades_opened >= slots:
                break

            symbol = opp["symbol"]
            if symbol in self.open_positions:
                continue

            try:
                await self._init_symbol(symbol)

                # Fetch candles + order book concurrently
                candles_task   = asyncio.create_task(
                    self.client.get_candles(symbol, granularity="1m", limit=150)
                )
                orderbook_task = asyncio.create_task(
                    self.client.get_orderbook(symbol, limit=50)
                )
                candles, orderbook = await asyncio.gather(candles_task, orderbook_task)

                if not candles or len(candles) < 50:
                    continue

                # Full institutional analysis
                signal = self.strategy.analyze(
                    symbol=symbol,
                    candles=candles,
                    orderbook=orderbook,
                    direction_bias=opp["direction"]
                )

                if signal and signal.action in ("BUY", "SELL") and signal.confidence >= 0.5:
                    await self._execute_trade(signal, available_usdt)
                    trades_opened += 1
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Analysis error {symbol}: {e}")

    async def _execute_trade(self, signal: Signal, available_usdt: float):
        try:
            symbol = signal.symbol
            ticker = await self.client.get_ticker(symbol)
            price  = float(ticker.get("lastPr", 0) or ticker.get("last", 0) or 0)
            if price == 0:
                return

            size_usdt     = available_usdt * (signal.size_percent / 100)
            size_usdt     = min(size_usdt, available_usdt * (MAX_POSITION_SIZE_PERCENT / 100))
            leveraged_usdt = size_usdt * LEVERAGE
            contracts     = round(leveraged_usdt / price, 4)

            if contracts <= 0:
                return

            side      = "buy"  if signal.action == "BUY"  else "sell"
            hold_side = "long" if signal.action == "BUY"  else "short"

            result = await self.client.place_order(
                symbol=symbol, side=side, trade_side="open",
                order_type="market", size=str(contracts)
            )

            if result.get("code") == "00000":
                await self.client.place_stop_loss(
                    symbol=symbol, hold_side=hold_side,
                    trigger_price=str(round(signal.stop_loss, 8)),
                    size=str(contracts)
                )
                await self.client.place_take_profit(
                    symbol=symbol, hold_side=hold_side,
                    trigger_price=str(round(signal.take_profit, 8)),
                    size=str(contracts)
                )

                self.open_positions[symbol] = {
                    "entry_price": price,
                    "contracts":   contracts,
                    "hold_side":   hold_side,
                    "stop_loss":   signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "reason":      signal.reason,
                    "confluence":  signal.confluence,
                    "size_usdt":   size_usdt,
                    "leverage":    LEVERAGE,
                    "regime":      signal.regime
                }

                logger.info(
                    f"✅ {signal.action} {symbol} @ {price:.6g} | "
                    f"{LEVERAGE}x | {signal.confidence:.0%} confidence | {signal.reason}"
                )

                if self.brain:
                    await self.brain.notify_trade(
                        action=signal.action, symbol=symbol, price=price,
                        reason=signal.reason, confidence=signal.confidence
                    )
            else:
                logger.error(f"Order failed {symbol}: {result}")

        except Exception as e:
            logger.error(f"Execute error: {e}")

    async def _sync_positions(self):
        try:
            live = await self.client.get_all_positions()
            live_syms = {p["symbol"] for p in live if float(p.get("total", 0)) > 0}
            closed = [s for s in list(self.open_positions.keys()) if s not in live_syms]
            for symbol in closed:
                pos = self.open_positions.pop(symbol)
                if self.brain:
                    await self.brain.notify_trade(
                        action="CLOSED", symbol=symbol,
                        price=pos["entry_price"],
                        reason="SL/TP hit or manual close"
                    )
        except Exception as e:
            logger.error(f"Sync error: {e}")

    async def get_status(self) -> dict:
        balance = await self.client.get_account_balance()
        top_opps = [
            f"{o['symbol']} ({o['change_pct']:+.1f}%)"
            for o in self.last_scan_results[:5]
        ]
        return {
            "active":            self.active,
            "paused":            self.paused,
            "leverage":          LEVERAGE,
            "margin_mode":       MARGIN_MODE,
            "balance_usdt":      balance,
            "open_positions":    self.open_positions,
            "total_pnl":         round(self.pnl_total, 4),
            "total_scans":       self.total_scanned,
            "last_opportunities": top_opps,
            "pairs_in_last_scan": len(self.last_scan_results)
        }
