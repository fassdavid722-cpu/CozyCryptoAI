"""
CozyCryptoAI - Aggressive Scalping Strategy
Uses: EMA crossover + RSI + Volume spike + Momentum
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("Strategy")


@dataclass
class Signal:
    symbol: str
    action: str          # 'BUY' | 'SELL' | 'HOLD'
    confidence: float    # 0.0 - 1.0
    reason: str
    entry_price: float
    stop_loss: float
    take_profit: float
    size_percent: float  # % of portfolio to use


class AggressiveScalper:
    """
    Aggressive scalping strategy:
    - EMA 9/21 crossover for trend
    - RSI 14 for momentum confirmation
    - Volume spike detection
    - Breakout detection from recent highs/lows
    """

    def __init__(self):
        self.ema_fast = 9
        self.ema_slow = 21
        self.rsi_period = 14
        self.rsi_oversold = 35
        self.rsi_overbought = 65
        self.volume_spike_multiplier = 1.5
        self.stop_loss_pct = 0.015   # 1.5%
        self.take_profit_pct = 0.03  # 3.0%

    def _ema(self, prices: list, period: int) -> np.ndarray:
        prices = np.array(prices, dtype=float)
        ema = np.zeros_like(prices)
        ema[period - 1] = np.mean(prices[:period])
        multiplier = 2 / (period + 1)
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
        return ema

    def _rsi(self, prices: list, period: int = 14) -> float:
        prices = np.array(prices, dtype=float)
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _volume_spike(self, volumes: list) -> bool:
        if len(volumes) < 20:
            return False
        avg_vol = np.mean(volumes[-20:-1])
        current_vol = volumes[-1]
        return current_vol > avg_vol * self.volume_spike_multiplier

    def analyze(self, symbol: str, candles: list) -> Optional[Signal]:
        """
        Analyze candles and return a trading signal
        candles: list of [timestamp, open, high, low, close, volume]
        """
        if len(candles) < 30:
            return None

        try:
            closes = [float(c[4]) for c in candles]
            volumes = [float(c[5]) for c in candles]
            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]

            ema_fast = self._ema(closes, self.ema_fast)
            ema_slow = self._ema(closes, self.ema_slow)
            rsi = self._rsi(closes, self.rsi_period)
            vol_spike = self._volume_spike(volumes)

            current_price = closes[-1]
            prev_fast = ema_fast[-2]
            prev_slow = ema_slow[-2]
            curr_fast = ema_fast[-1]
            curr_slow = ema_slow[-1]

            # Breakout: price above recent 20-bar high
            recent_high = max(highs[-21:-1])
            recent_low = min(lows[-21:-1])
            breakout_up = current_price > recent_high
            breakout_down = current_price < recent_low

            # Golden cross (fast crosses above slow)
            golden_cross = prev_fast <= prev_slow and curr_fast > curr_slow
            # Death cross (fast crosses below slow)
            death_cross = prev_fast >= prev_slow and curr_fast < curr_slow

            # Trend direction
            uptrend = curr_fast > curr_slow
            downtrend = curr_fast < curr_slow

            # ── BUY Signal ────────────────────────────────────────────────
            buy_conditions = []

            if golden_cross and rsi < self.rsi_overbought:
                buy_conditions.append("EMA golden cross")
            if breakout_up and vol_spike:
                buy_conditions.append("volume breakout above resistance")
            if uptrend and rsi < self.rsi_oversold:
                buy_conditions.append("oversold bounce in uptrend")

            if buy_conditions:
                confidence = min(0.5 + 0.15 * len(buy_conditions), 0.95)
                stop = round(current_price * (1 - self.stop_loss_pct), 6)
                tp = round(current_price * (1 + self.take_profit_pct), 6)
                size = 8 if confidence > 0.7 else 5  # % of portfolio

                return Signal(
                    symbol=symbol,
                    action="BUY",
                    confidence=confidence,
                    reason=", ".join(buy_conditions),
                    entry_price=current_price,
                    stop_loss=stop,
                    take_profit=tp,
                    size_percent=size
                )

            # ── SELL Signal ───────────────────────────────────────────────
            sell_conditions = []

            if death_cross and rsi > self.rsi_oversold:
                sell_conditions.append("EMA death cross")
            if breakout_down and vol_spike:
                sell_conditions.append("volume breakdown below support")
            if downtrend and rsi > self.rsi_overbought:
                sell_conditions.append("overbought rejection in downtrend")

            if sell_conditions:
                confidence = min(0.5 + 0.15 * len(sell_conditions), 0.95)
                return Signal(
                    symbol=symbol,
                    action="SELL",
                    confidence=confidence,
                    reason=", ".join(sell_conditions),
                    entry_price=current_price,
                    stop_loss=round(current_price * (1 + self.stop_loss_pct), 6),
                    take_profit=round(current_price * (1 - self.take_profit_pct), 6),
                    size_percent=5
                )

        except Exception as e:
            logger.error(f"Strategy error for {symbol}: {e}")

        return Signal(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            reason="No clear signal",
            entry_price=float(candles[-1][4]) if candles else 0,
            stop_loss=0,
            take_profit=0,
            size_percent=0
        )
