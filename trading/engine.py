"""
CozyCryptoAI Futures Trading Engine
Trades USDT-M perpetual contracts on Bitget
Aggressive scalper — leveraged, fast, focused on account growth
"""

import asyncio
import logging
from trading.bitget_client import BitgetClient
from trading.strategy import AggressiveScalper, Signal
from config import (
    TRADING_PAIRS, MAX_POSITION_SIZE_PERCENT,
    MAX_OPEN_POSITIONS, SCALP_INTERVAL_SECONDS,
    LEVERAGE, MARGIN_MODE
)

logger = logging.getLogger("TradingEngine")


class TradingEngine:
    def __init__(self, brain=None):
        self.client = BitgetClient()
        self.strategy = AggressiveScalper()
        self.brain = brain
        self.active = True
        self.paused = False
        self.open_positions = {}   # symbol -> position details
        self.pnl_total = 0.0
        self.initialized_symbols = set()

    # ── Control ───────────────────────────────────────────────────────────────

    def pause(self):
        self.paused = True
        logger.info("Trading paused")

    def resume(self):
        self.paused = False
        logger.info("Trading resumed")

    def stop(self):
        self.active = False

    # ── Init ──────────────────────────────────────────────────────────────────

    async def _init_symbol(self, symbol: str):
        """Set leverage and margin mode for a symbol"""
        if symbol in self.initialized_symbols:
            return
        try:
            await self.client.set_margin_mode(symbol, MARGIN_MODE)
            await self.client.set_leverage(symbol, LEVERAGE, "long")
            await self.client.set_leverage(symbol, LEVERAGE, "short")
            self.initialized_symbols.add(symbol)
            logger.info(f"✅ {symbol} initialized — {LEVERAGE}x leverage, {MARGIN_MODE} margin")
        except Exception as e:
            logger.error(f"Init error for {symbol}: {e}")

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def run(self):
        logger.info(f"🚀 Futures engine running — {LEVERAGE}x leverage, {MARGIN_MODE} margin")
        # Initialize all symbols
        for symbol in TRADING_PAIRS:
            await self._init_symbol(symbol)

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
            logger.warning("Insufficient balance")
            return

        open_count = len(self.open_positions)
        if open_count >= MAX_OPEN_POSITIONS:
            await self._sync_positions()
            return

        for symbol in TRADING_PAIRS:
            try:
                if symbol in self.open_positions:
                    continue

                candles = await self.client.get_candles(symbol, granularity="1m", limit=100)
                if not candles:
                    continue

                signal = self.strategy.analyze(symbol, candles)

                if signal and signal.action in ("BUY", "SELL") and signal.confidence >= 0.6:
                    await self._execute_trade(signal, available_usdt)

            except Exception as e:
                logger.error(f"Scan error for {symbol}: {e}")

        await self._sync_positions()

    async def _execute_trade(self, signal: Signal, available_usdt: float):
        """Open a leveraged long or short position"""
        try:
            symbol = signal.symbol
            ticker = await self.client.get_ticker(symbol)
            price = float(ticker.get("lastPr", 0))
            if price == 0:
                return

            # Calculate position size in contracts
            size_usdt = available_usdt * (signal.size_percent / 100)
            size_usdt = min(size_usdt, available_usdt * (MAX_POSITION_SIZE_PERCENT / 100))
            leveraged_usdt = size_usdt * LEVERAGE
            contracts = round(leveraged_usdt / price, 4)

            if contracts <= 0:
                return

            # Long on BUY, Short on SELL
            side = "buy" if signal.action == "BUY" else "sell"
            hold_side = "long" if signal.action == "BUY" else "short"

            result = await self.client.place_order(
                symbol=symbol,
                side=side,
                trade_side="open",
                order_type="market",
                size=str(contracts)
            )

            if result.get("code") == "00000":
                # Place SL and TP
                await self.client.place_stop_loss(
                    symbol=symbol,
                    hold_side=hold_side,
                    trigger_price=str(round(signal.stop_loss, 6)),
                    size=str(contracts)
                )
                await self.client.place_take_profit(
                    symbol=symbol,
                    hold_side=hold_side,
                    trigger_price=str(round(signal.take_profit, 6)),
                    size=str(contracts)
                )

                self.open_positions[symbol] = {
                    "entry_price": price,
                    "contracts": contracts,
                    "hold_side": hold_side,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "reason": signal.reason,
                    "size_usdt": size_usdt,
                    "leverage": LEVERAGE
                }

                logger.info(f"✅ {signal.action} {symbol} @ {price} | {LEVERAGE}x | Reason: {signal.reason}")

                if self.brain:
                    await self.brain.notify_trade(
                        action=signal.action,
                        symbol=symbol,
                        price=price,
                        reason=signal.reason,
                        confidence=signal.confidence
                    )
            else:
                logger.error(f"Order failed: {result}")

        except Exception as e:
            logger.error(f"Execute trade error: {e}")

    async def _sync_positions(self):
        """Sync open positions with Bitget — remove closed ones"""
        try:
            live_positions = await self.client.get_all_positions()
            live_symbols = {p["symbol"] for p in live_positions if float(p.get("total", 0)) > 0}

            closed = [s for s in self.open_positions if s not in live_symbols]
            for symbol in closed:
                pos = self.open_positions.pop(symbol)
                logger.info(f"Position closed: {symbol}")
                if self.brain:
                    await self.brain.notify_trade(
                        action="CLOSED",
                        symbol=symbol,
                        price=pos["entry_price"],
                        reason="Position closed (SL/TP hit or manual)"
                    )
        except Exception as e:
            logger.error(f"Sync positions error: {e}")

    # ── Status ────────────────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        balance = await self.client.get_account_balance()
        return {
            "active": self.active,
            "paused": self.paused,
            "leverage": LEVERAGE,
            "margin_mode": MARGIN_MODE,
            "balance_usdt": balance,
            "open_positions": self.open_positions,
            "total_pnl": round(self.pnl_total, 4),
            "watching": TRADING_PAIRS
        }
