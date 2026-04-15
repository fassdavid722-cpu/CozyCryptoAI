"""
CozyCryptoAI - Aggressive Scalping Strategy
Works on ANY futures pair — not hardcoded to specific tokens
Indicators: EMA 9/21 + RSI 14 + Volume Spike + Breakout detection
Supports both Long and Short signals
"""

import logging
from dataclasses import dataclass
from typing import Optional, List
from config import STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT

logger = logging.getLogger("Strategy")


@dataclass
class Signal:
    symbol: str
    action: str          # 'BUY' (long) | 'SELL' (short) | 'HOLD'
    confidence: float    # 0.0 - 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    size_percent: float  # % of available balance to use


class AggressiveScalper:
    def __init__(self):
        self.sl_pct = STOP_LOSS_PERCENT / 100
        self.tp_pct = TAKE_PROFIT_PERCENT / 100
        self.min_candles = 30

    def analyze(self, symbol: str, candles: list,
                direction_bias: str = None) -> Optional[Signal]:
        """
        Analyze candles and return a trade signal or None
        candles: list of [timestamp, open, high, low, close, volume]
        direction_bias: 'long' | 'short' | None (from scanner momentum)
        """
        try:
            if not candles or len(candles) < self.min_candles:
                return None

            # Parse candle data
            closes = [float(c[4]) for c in candles]
            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]
            volumes = [float(c[5]) for c in candles]

            price = closes[-1]
            if price <= 0:
                return None

            # Calculate indicators
            ema9 = self._ema(closes, 9)
            ema21 = self._ema(closes, 21)
            rsi = self._rsi(closes, 14)
            volume_spike = self._volume_spike(volumes)
            breakout_long, breakout_short = self._breakout(closes, highs, lows, 20)

            # Score signals
            long_score = 0
            short_score = 0
            reasons_long = []
            reasons_short = []

            # EMA crossover
            if ema9[-1] > ema21[-1] and ema9[-2] <= ema21[-2]:
                long_score += 2
                reasons_long.append("EMA 9/21 bullish cross")
            elif ema9[-1] < ema21[-1] and ema9[-2] >= ema21[-2]:
                short_score += 2
                reasons_short.append("EMA 9/21 bearish cross")

            # EMA trend
            if ema9[-1] > ema21[-1]:
                long_score += 1
                reasons_long.append("above EMA")
            elif ema9[-1] < ema21[-1]:
                short_score += 1
                reasons_short.append("below EMA")

            # RSI
            if 40 < rsi < 65:
                long_score += 1
                reasons_long.append(f"RSI {rsi:.0f} healthy")
            elif rsi < 35:
                long_score += 2
                reasons_long.append(f"RSI {rsi:.0f} oversold")
            elif rsi > 60:
                short_score += 1
                reasons_short.append(f"RSI {rsi:.0f} elevated")
            elif rsi > 70:
                short_score += 2
                reasons_short.append(f"RSI {rsi:.0f} overbought")

            # Volume spike
            if volume_spike:
                long_score += 1
                short_score += 1  # Volume confirms either direction
                reasons_long.append("volume spike")
                reasons_short.append("volume spike")

            # Breakout
            if breakout_long:
                long_score += 2
                reasons_long.append("20-bar high breakout")
            if breakout_short:
                short_score += 2
                reasons_short.append("20-bar low breakdown")

            # Direction bias from scanner (momentum alignment)
            if direction_bias == "long":
                long_score += 1
            elif direction_bias == "short":
                short_score += 1

            # Decide signal
            max_score = 7  # realistic max
            action = None
            score = 0
            reason = ""

            if long_score >= 3 and long_score >= short_score:
                action = "BUY"
                score = long_score
                reason = " + ".join(reasons_long[:3])
            elif short_score >= 3 and short_score > long_score:
                action = "SELL"
                score = short_score
                reason = " + ".join(reasons_short[:3])

            if not action:
                return None

            confidence = min(score / max_score, 1.0)

            # Size based on confidence (5-10% of account)
            size_percent = 5 + (confidence * 5)

            # Calculate SL/TP
            if action == "BUY":
                stop_loss = price * (1 - self.sl_pct)
                take_profit = price * (1 + self.tp_pct)
            else:
                stop_loss = price * (1 + self.sl_pct)
                take_profit = price * (1 - self.tp_pct)

            logger.info(f"Signal: {action} {symbol} | Confidence: {confidence:.0%} | {reason}")

            return Signal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=reason,
                size_percent=size_percent
            )

        except Exception as e:
            logger.error(f"Strategy error for {symbol}: {e}")
            return None

    # ── Indicators ────────────────────────────────────────────────────────────

    def _ema(self, data: list, period: int) -> list:
        if len(data) < period:
            return [data[-1]] * len(data)
        k = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for price in data[period:]:
            ema.append(price * k + ema[-1] * (1 - k))
        # Pad front
        pad = len(data) - len(ema)
        return [ema[0]] * pad + ema

    def _rsi(self, data: list, period: int = 14) -> float:
        if len(data) < period + 1:
            return 50.0
        deltas = [data[i] - data[i - 1] for i in range(1, len(data))]
        gains = [d for d in deltas[-period:] if d > 0]
        losses = [-d for d in deltas[-period:] if d < 0]
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _volume_spike(self, volumes: list, lookback: int = 20, threshold: float = 1.5) -> bool:
        if len(volumes) < lookback + 1:
            return False
        avg_vol = sum(volumes[-lookback - 1:-1]) / lookback
        return volumes[-1] > avg_vol * threshold if avg_vol > 0 else False

    def _breakout(self, closes: list, highs: list, lows: list, period: int = 20):
        if len(closes) < period + 1:
            return False, False
        recent_high = max(highs[-period - 1:-1])
        recent_low = min(lows[-period - 1:-1])
        breakout_long = closes[-1] > recent_high
        breakout_short = closes[-1] < recent_low
        return breakout_long, breakout_short
