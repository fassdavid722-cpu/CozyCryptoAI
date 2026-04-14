"""
CozyCryptoAI Trading Engine
Orchestrates market scanning, signal generation, and order execution
"""

import asyncio
import logging
from typing import Optional
from trading.bitget_client import BitgetClient
from trading.strategy import AggressiveScalper, Signal
from config import (
    TRADING_PAIRS, MAX_POSITION_SIZE_PERCENT,
    MAX_OPEN_POSITIONS, SCALP_INTERVAL_SECONDS,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT
)

logger = logging.getLogger("TradingEngine")


class TradingEngine:
    def __init__(self, brain=None):
        self.client = BitgetClient()
        self.strategy = AggressiveScalper()
        self.brain = brain
        self.active = True
        self.paused = False
        self.trade_history = []
        self.open_positions = {}   # symbol -> entry details
        self.pnl_total = 0.0

    # ── Control ───────────────────────────────────────────────────────────────

    def pause(self):
        self.paused = True
        logger.info("Trading paused")

    def resume(self):
        self.paused = False
        logger.info("Trading resumed")

    def stop(self):
        self.active = False
        logger.info("Trading stopped")

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def run(self):
        logger.info("Trading engine running...")
        while self.active:
            try:
                if not self.paused:
                    await self._scan_and_trade()
            except Exception as e:
                logger.error(f"Engine loop error: {e}")
            await asyncio.sleep(SCALP_INTERVAL_SECONDS)

    async def _scan_and_trade(self):
        balance = await self.client.get_account_balance()
        available_usdt = balance["available"]

        if available_usdt < 5:
            logger.warning("Insufficient USDT balance to trade")
            return

        open_count = len(self.open_positions)
        if open_count >= MAX_OPEN_POSITIONS:
            logger.info(f"Max positions reached ({open_count}), skipping scan")
            await self._check_exits()
            return

        for symbol in TRADING_PAIRS:
            try:
                candles = await self.client.get_candles(symbol, granularity="1m", limit=100)
                if not candles:
                    continue

                signal = self.strategy.analyze(symbol, candles)

                if signal and signal.action == "BUY" and signal.confidence >= 0.6:
                    if symbol not in self.open_positions:
                        await self._execute_buy(signal, available_usdt)

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

        await self._check_exits()

    async def _execute_buy(self, signal: Signal, available_usdt: float):
        try:
            size_usdt = available_usdt * (signal.size_percent / 100)
            size_usdt = min(size_usdt, available_usdt * (MAX_POSITION_SIZE_PERCENT / 100))

            if size_usdt < 5:
                return

            ticker = await self.client.get_ticker(signal.symbol)
            price = float(ticker.get("lastPr", 0))
            if price == 0:
                return

            quantity = round(size_usdt / price, 6)

            result = await self.client.place_order(
                symbol=signal.symbol,
                side="buy",
                order_type="market",
                size=str(quantity)
            )

            if result.get("code") == "00000":
                self.open_positions[signal.symbol] = {
                    "entry_price": price,
                    "quantity": quantity,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "reason": signal.reason,
                    "size_usdt": size_usdt
                }
                logger.info(f"✅ BUY {signal.symbol} @ {price} | Reason: {signal.reason}")

                if self.brain:
                    await self.brain.notify_trade(
                        action="BUY",
                        symbol=signal.symbol,
                        price=price,
                        reason=signal.reason,
                        confidence=signal.confidence
                    )
            else:
                logger.error(f"Order failed: {result}")

        except Exception as e:
            logger.error(f"Execute buy error: {e}")

    async def _check_exits(self):
        """Check all open positions for stop loss / take profit"""
        to_close = []

        for symbol, pos in self.open_positions.items():
            try:
                ticker = await self.client.get_ticker(symbol)
                current_price = float(ticker.get("lastPr", 0))
                if current_price == 0:
                    continue

                should_exit = False
                exit_reason = ""

                if current_price <= pos["stop_loss"]:
                    should_exit = True
                    exit_reason = f"stop loss hit @ {current_price}"
                elif current_price >= pos["take_profit"]:
                    should_exit = True
                    exit_reason = f"take profit hit @ {current_price}"

                if should_exit:
                    result = await self.client.place_order(
                        symbol=symbol,
                        side="sell",
                        order_type="market",
                        size=str(pos["quantity"])
                    )
                    if result.get("code") == "00000":
                        pnl = (current_price - pos["entry_price"]) * pos["quantity"]
                        self.pnl_total += pnl
                        to_close.append(symbol)
                        logger.info(f"{'✅' if pnl > 0 else '❌'} SELL {symbol} | {exit_reason} | PnL: {pnl:.2f} USDT")

                        if self.brain:
                            await self.brain.notify_trade(
                                action="SELL",
                                symbol=symbol,
                                price=current_price,
                                reason=exit_reason,
                                pnl=pnl
                            )

            except Exception as e:
                logger.error(f"Exit check error for {symbol}: {e}")

        for symbol in to_close:
            self.open_positions.pop(symbol, None)

    # ── Status ────────────────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        balance = await self.client.get_account_balance()
        return {
            "active": self.active,
            "paused": self.paused,
            "balance_usdt": balance,
            "open_positions": self.open_positions,
            "total_pnl": round(self.pnl_total, 4),
            "watching": TRADING_PAIRS
        }
