"""
CozyCryptoAI — Institutional Strategy Engine
Analyzes markets the way smart money does:

1. Liquidity         — Where are the stop hunts? Where is liquidity resting?
2. Order Flow        — Are buyers or sellers in control? CVD, delta analysis
3. Footprint Chart   — Buy vs sell volume at each price level
4. Market Structure  — BOS (Break of Structure), CHoCH (Change of Character), HH/HL/LH/LL
5. Accumulation/Dist — Wyckoff phases, absorption, re-accumulation
6. Execution Zones   — OB (Order Blocks), FVG (Fair Value Gaps), premium/discount
7. Volatility Regime — ATR regime, expansion vs contraction, avoid choppy markets
8. Order Book        — Bid/ask imbalance, large wall detection, spoofing filter
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from config import STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT

logger = logging.getLogger("InstitutionalStrategy")


@dataclass
class Signal:
    symbol: str
    action: str             # 'BUY' | 'SELL' | 'HOLD'
    confidence: float       # 0.0 - 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    size_percent: float
    confluence: List[str] = field(default_factory=list)
    regime: str = "unknown"


class InstitutionalStrategy:
    def __init__(self):
        self.sl_pct = STOP_LOSS_PERCENT / 100
        self.tp_pct = TAKE_PROFIT_PERCENT / 100

    def analyze(self, symbol: str, candles: list,
                orderbook: dict = None, direction_bias: str = None) -> Optional[Signal]:
        """
        Full institutional analysis pipeline
        Returns a Signal if conditions align, else None
        """
        try:
            if not candles or len(candles) < 50:
                return None

            closes  = [float(c[4]) for c in candles]
            opens   = [float(c[1]) for c in candles]
            highs   = [float(c[2]) for c in candles]
            lows    = [float(c[3]) for c in candles]
            volumes = [float(c[5]) for c in candles]
            price   = closes[-1]

            if price <= 0:
                return None

            confluence = []
            long_score  = 0
            short_score = 0

            # ── 1. VOLATILITY REGIME ─────────────────────────────────────────
            regime, atr = self._volatility_regime(closes, highs, lows)
            if regime == "choppy":
                return None   # Never trade choppy markets
            if regime == "expanding":
                long_score  += 1
                short_score += 1
                confluence.append(f"Volatility expanding (ATR {atr:.4f})")

            # ── 2. MARKET STRUCTURE ──────────────────────────────────────────
            structure = self._market_structure(highs, lows, closes)
            if structure["trend"] == "bullish":
                long_score += 3
                confluence.append(f"Bullish structure ({structure['pattern']})")
            elif structure["trend"] == "bearish":
                short_score += 3
                confluence.append(f"Bearish structure ({structure['pattern']})")
            if structure["choch_long"]:
                long_score += 2
                confluence.append("CHoCH — potential bullish reversal")
            if structure["choch_short"]:
                short_score += 2
                confluence.append("CHoCH — potential bearish reversal")
            if structure["bos_long"]:
                long_score += 2
                confluence.append("BOS — bullish continuation")
            if structure["bos_short"]:
                short_score += 2
                confluence.append("BOS — bearish continuation")

            # ── 3. LIQUIDITY ANALYSIS ────────────────────────────────────────
            liquidity = self._liquidity_analysis(highs, lows, closes, volumes)
            if liquidity["swept_highs"]:
                short_score += 2
                confluence.append("Liquidity sweep above highs — distribution")
            if liquidity["swept_lows"]:
                long_score += 2
                confluence.append("Liquidity sweep below lows — accumulation")
            if liquidity["equal_highs"]:
                confluence.append(f"Equal highs resting at ${liquidity['equal_highs']:.4f} — target")
            if liquidity["equal_lows"]:
                confluence.append(f"Equal lows resting at ${liquidity['equal_lows']:.4f} — target")

            # ── 4. ORDER FLOW (CVD) ──────────────────────────────────────────
            order_flow = self._order_flow(opens, closes, volumes)
            if order_flow["cvd_trend"] == "bullish" and order_flow["delta"] > 0:
                long_score += 2
                confluence.append(f"Bullish CVD (delta +{order_flow['delta']:.0f})")
            elif order_flow["cvd_trend"] == "bearish" and order_flow["delta"] < 0:
                short_score += 2
                confluence.append(f"Bearish CVD (delta {order_flow['delta']:.0f})")
            if order_flow["absorption"]:
                confluence.append(f"Volume absorption detected — {order_flow['absorption']}")

            # ── 5. FOOTPRINT / DELTA ─────────────────────────────────────────
            footprint = self._footprint_analysis(opens, closes, volumes, highs, lows)
            if footprint["buying_pressure"] > 0.65:
                long_score += 2
                confluence.append(f"Footprint: {footprint['buying_pressure']:.0%} buying pressure")
            elif footprint["buying_pressure"] < 0.35:
                short_score += 2
                confluence.append(f"Footprint: {1 - footprint['buying_pressure']:.0%} selling pressure")
            if footprint["imbalance_long"]:
                long_score += 1
                confluence.append("Footprint bid imbalance stack")
            if footprint["imbalance_short"]:
                short_score += 1
                confluence.append("Footprint ask imbalance stack")

            # ── 6. ACCUMULATION / DISTRIBUTION ──────────────────────────────
            acc_dist = self._accumulation_distribution(opens, closes, highs, lows, volumes)
            if acc_dist["phase"] == "accumulation":
                long_score += 2
                confluence.append(f"Wyckoff accumulation (MFI {acc_dist['mfi']:.0f})")
            elif acc_dist["phase"] == "distribution":
                short_score += 2
                confluence.append(f"Wyckoff distribution (MFI {acc_dist['mfi']:.0f})")
            elif acc_dist["phase"] == "markup":
                long_score += 1
                confluence.append("Wyckoff markup phase")
            elif acc_dist["phase"] == "markdown":
                short_score += 1
                confluence.append("Wyckoff markdown phase")

            # ── 7. EXECUTION ZONES (OB + FVG) ───────────────────────────────
            zones = self._execution_zones(opens, closes, highs, lows)
            in_bullish_ob  = any(z["low"] <= price <= z["high"] for z in zones["bullish_ob"])
            in_bearish_ob  = any(z["low"] <= price <= z["high"] for z in zones["bearish_ob"])
            in_bullish_fvg = any(z["low"] <= price <= z["high"] for z in zones["bullish_fvg"])
            in_bearish_fvg = any(z["low"] <= price <= z["high"] for z in zones["bearish_fvg"])

            if in_bullish_ob:
                long_score += 3
                confluence.append("Price in bullish Order Block")
            if in_bearish_ob:
                short_score += 3
                confluence.append("Price in bearish Order Block")
            if in_bullish_fvg:
                long_score += 2
                confluence.append("Price filling bullish FVG")
            if in_bearish_fvg:
                short_score += 2
                confluence.append("Price filling bearish FVG")

            # Premium/discount check
            pd = self._premium_discount(highs, lows, price)
            if pd["zone"] == "discount":
                long_score += 1
                confluence.append(f"Price in discount zone ({pd['percent']:.0f}% of range)")
            elif pd["zone"] == "premium":
                short_score += 1
                confluence.append(f"Price in premium zone ({pd['percent']:.0f}% of range)")

            # ── 8. ORDER BOOK ANALYSIS ───────────────────────────────────────
            if orderbook and orderbook.get("bids") and orderbook.get("asks"):
                ob_analysis = self._orderbook_analysis(orderbook, price)
                if ob_analysis["imbalance"] == "bid_heavy":
                    long_score += 2
                    confluence.append(f"Order book bid-heavy ({ob_analysis['ratio']:.1f}x)")
                elif ob_analysis["imbalance"] == "ask_heavy":
                    short_score += 2
                    confluence.append(f"Order book ask-heavy ({ob_analysis['ratio']:.1f}x)")
                if ob_analysis["large_bid_wall"]:
                    confluence.append(f"Large bid wall at ${ob_analysis['large_bid_wall']:.4f}")
                if ob_analysis["large_ask_wall"]:
                    confluence.append(f"Large ask wall at ${ob_analysis['large_ask_wall']:.4f}")

            # Direction bias from scanner
            if direction_bias == "long":
                long_score += 1
            elif direction_bias == "short":
                short_score += 1

            # ── SIGNAL DECISION ──────────────────────────────────────────────
            max_score = 18
            action = None
            score = 0

            if long_score >= 6 and long_score > short_score:
                action = "BUY"
                score = long_score
            elif short_score >= 6 and short_score > long_score:
                action = "SELL"
                score = short_score

            if not action:
                return None

            confidence = min(score / max_score, 1.0)
            if confidence < 0.45:
                return None

            # Dynamic SL using ATR — tighter in low vol, wider in expanding
            atr_multiplier = 1.5 if regime == "expanding" else 1.0
            sl_distance = max(atr * atr_multiplier, price * self.sl_pct)
            tp_distance = sl_distance * 2.0   # Always maintain 2:1 R/R minimum

            if action == "BUY":
                stop_loss   = price - sl_distance
                take_profit = price + tp_distance
            else:
                stop_loss   = price + sl_distance
                take_profit = price - tp_distance

            # Size: 5-12% based on confidence
            size_percent = 5 + (confidence * 7)

            top_reasons = confluence[:4]
            reason = " | ".join(top_reasons)

            logger.info(
                f"🎯 {action} {symbol} @ {price:.6g} | "
                f"Confidence: {confidence:.0%} | Regime: {regime} | {reason}"
            )

            return Signal(
                symbol=symbol,
                action=action,
                confidence=confidence,
                entry_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=reason,
                size_percent=size_percent,
                confluence=confluence,
                regime=regime
            )

        except Exception as e:
            logger.error(f"Strategy error for {symbol}: {e}")
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # ANALYSIS MODULES
    # ═════════════════════════════════════════════════════════════════════════

    def _volatility_regime(self, closes: list, highs: list, lows: list,
                            period: int = 14) -> Tuple[str, float]:
        """
        ATR-based volatility regime detection
        Returns: ('trending'|'expanding'|'choppy', atr_value)
        """
        if len(closes) < period + 2:
            return "trending", 0.0

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            trs.append(tr)

        atr = sum(trs[-period:]) / period
        prev_atr = sum(trs[-period * 2:-period]) / period if len(trs) >= period * 2 else atr

        price = closes[-1]
        atr_pct = (atr / price) * 100

        # ATR expanding fast = good for scalping
        if atr > prev_atr * 1.2:
            return "expanding", atr
        # ATR very low relative to price = choppy / no range
        elif atr_pct < 0.3:
            return "choppy", atr
        else:
            return "trending", atr

    def _market_structure(self, highs: list, lows: list, closes: list,
                           lookback: int = 20) -> dict:
        """
        Detect: trend, BOS (Break of Structure), CHoCH (Change of Character)
        """
        result = {
            "trend": "neutral",
            "pattern": "",
            "bos_long": False,
            "bos_short": False,
            "choch_long": False,
            "choch_short": False
        }

        if len(highs) < lookback * 2:
            return result

        # Find swing highs/lows
        swing_highs = self._swing_highs(highs, lookback // 2)
        swing_lows  = self._swing_lows(lows, lookback // 2)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return result

        # Trend via HH/HL or LH/LL
        hh = swing_highs[-1] > swing_highs[-2]
        hl = swing_lows[-1] > swing_lows[-2]
        lh = swing_highs[-1] < swing_highs[-2]
        ll = swing_lows[-1] < swing_lows[-2]

        if hh and hl:
            result["trend"] = "bullish"
            result["pattern"] = "HH/HL"
        elif lh and ll:
            result["trend"] = "bearish"
            result["pattern"] = "LH/LL"

        # BOS: close breaks last swing high/low
        last_sh = swing_highs[-1]
        last_sl = swing_lows[-1]
        price = closes[-1]

        if result["trend"] == "bullish" and price > last_sh:
            result["bos_long"] = True
        elif result["trend"] == "bearish" and price < last_sl:
            result["bos_short"] = True

        # CHoCH: trend was bearish but now breaks above last SH (or vice versa)
        if result["trend"] == "bearish" and price > last_sh:
            result["choch_long"] = True
        elif result["trend"] == "bullish" and price < last_sl:
            result["choch_short"] = True

        return result

    def _liquidity_analysis(self, highs: list, lows: list, closes: list,
                             volumes: list, lookback: int = 20) -> dict:
        """
        Detect liquidity pools, sweeps, equal highs/lows
        Smart money hunts liquidity before reversing
        """
        result = {
            "swept_highs": False,
            "swept_lows": False,
            "equal_highs": None,
            "equal_lows": None
        }

        if len(highs) < lookback + 5:
            return result

        price = closes[-1]
        prev_highs = highs[-lookback - 1:-1]
        prev_lows  = lows[-lookback - 1:-1]

        # Sweep: price exceeded prior high/low but closed back below/above
        prev_high = max(prev_highs)
        prev_low  = min(prev_lows)

        if highs[-1] > prev_high and closes[-1] < prev_high:
            result["swept_highs"] = True
        if lows[-1] < prev_low and closes[-1] > prev_low:
            result["swept_lows"] = True

        # Equal highs/lows (within 0.15%) — untapped liquidity
        tolerance = prev_high * 0.0015
        equal_h = [h for h in prev_highs if abs(h - prev_high) < tolerance]
        if len(equal_h) >= 2:
            result["equal_highs"] = prev_high

        tolerance_l = prev_low * 0.0015
        equal_l = [l for l in prev_lows if abs(l - prev_low) < tolerance_l]
        if len(equal_l) >= 2:
            result["equal_lows"] = prev_low

        return result

    def _order_flow(self, opens: list, closes: list, volumes: list) -> dict:
        """
        CVD (Cumulative Volume Delta) and absorption detection
        Delta = estimated buy volume - sell volume per candle
        """
        result = {"cvd_trend": "neutral", "delta": 0, "absorption": None}

        if len(closes) < 20:
            return result

        # Estimate delta: bullish candles = buying, bearish = selling
        deltas = []
        for i in range(len(closes)):
            body = closes[i] - opens[i]
            vol = volumes[i]
            if body > 0:
                # Bullish — more buy volume
                buy_vol = vol * 0.7
                sell_vol = vol * 0.3
            elif body < 0:
                # Bearish — more sell volume
                buy_vol = vol * 0.3
                sell_vol = vol * 0.7
            else:
                buy_vol = sell_vol = vol * 0.5
            deltas.append(buy_vol - sell_vol)

        recent_deltas = deltas[-20:]
        cumulative = sum(recent_deltas)
        result["delta"] = cumulative

        # CVD trend
        first_half  = sum(recent_deltas[:10])
        second_half = sum(recent_deltas[10:])
        if second_half > first_half * 1.2:
            result["cvd_trend"] = "bullish"
        elif second_half < first_half * 0.8:
            result["cvd_trend"] = "bearish"

        # Absorption: high volume but small body = absorption
        last_vol  = volumes[-1]
        avg_vol   = sum(volumes[-20:]) / 20
        last_body = abs(closes[-1] - opens[-1])
        avg_range = sum(abs(closes[i] - opens[i]) for i in range(-20, -1)) / 20

        if last_vol > avg_vol * 1.8 and last_body < avg_range * 0.4:
            result["absorption"] = "buyers absorbing" if closes[-1] > opens[-1] else "sellers absorbing"

        return result

    def _footprint_analysis(self, opens: list, closes: list, volumes: list,
                             highs: list, lows: list, lookback: int = 10) -> dict:
        """
        Approximated footprint chart analysis
        Estimates buy/sell volume at each price level
        """
        result = {
            "buying_pressure": 0.5,
            "imbalance_long": False,
            "imbalance_short": False
        }

        if len(closes) < lookback:
            return result

        total_buy  = 0
        total_sell = 0

        for i in range(-lookback, 0):
            vol  = volumes[i]
            body = closes[i] - opens[i]
            wick_up   = highs[i] - max(opens[i], closes[i])
            wick_down = min(opens[i], closes[i]) - lows[i]
            full_range = highs[i] - lows[i] if highs[i] != lows[i] else 1

            # Distribute volume: body + wicks
            buy_ratio  = (max(body, 0) + wick_up)  / full_range
            sell_ratio = (max(-body, 0) + wick_down) / full_range

            total_buy  += vol * buy_ratio
            total_sell += vol * sell_ratio

        total = total_buy + total_sell
        result["buying_pressure"] = total_buy / total if total > 0 else 0.5

        # Imbalance: 3+ consecutive same-direction candles with increasing volume
        recent_bodies = [closes[i] - opens[i] for i in range(-5, 0)]
        recent_vols   = volumes[-5:]

        if all(b > 0 for b in recent_bodies) and recent_vols[-1] > recent_vols[-3]:
            result["imbalance_long"] = True
        elif all(b < 0 for b in recent_bodies) and recent_vols[-1] > recent_vols[-3]:
            result["imbalance_short"] = True

        return result

    def _accumulation_distribution(self, opens: list, closes: list,
                                    highs: list, lows: list, volumes: list,
                                    period: int = 14) -> dict:
        """
        Wyckoff-inspired accumulation/distribution detection using MFI + VWAP deviation
        """
        result = {"phase": "neutral", "mfi": 50}

        if len(closes) < period * 2:
            return result

        # Money Flow Index (MFI)
        typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
        money_flows    = [typical_prices[i] * volumes[i] for i in range(len(closes))]

        pos_flow = 0
        neg_flow = 0
        for i in range(-period, -1):
            if typical_prices[i] > typical_prices[i - 1]:
                pos_flow += money_flows[i]
            else:
                neg_flow += money_flows[i]

        if neg_flow == 0:
            mfi = 100
        else:
            mfi = 100 - (100 / (1 + pos_flow / neg_flow))

        result["mfi"] = mfi

        # VWAP deviation for premium/discount context
        vwap = sum(money_flows[-period:]) / sum(volumes[-period:]) if sum(volumes[-period:]) > 0 else closes[-1]
        price = closes[-1]
        vwap_dev = (price - vwap) / vwap * 100

        # Classify phase
        if mfi < 30 and vwap_dev < -1:
            result["phase"] = "accumulation"
        elif mfi > 70 and vwap_dev > 1:
            result["phase"] = "distribution"
        elif mfi > 55 and vwap_dev > 0:
            result["phase"] = "markup"
        elif mfi < 45 and vwap_dev < 0:
            result["phase"] = "markdown"

        return result

    def _execution_zones(self, opens: list, closes: list,
                          highs: list, lows: list, lookback: int = 30) -> dict:
        """
        Identify Order Blocks and Fair Value Gaps (FVG)
        OB: Last bearish candle before a bullish impulse (bullish OB) and vice versa
        FVG: Gap between candle[i-2] high and candle[i] low (unfilled gaps)
        """
        zones = {
            "bullish_ob":  [],
            "bearish_ob":  [],
            "bullish_fvg": [],
            "bearish_fvg": []
        }

        data_len = min(len(closes), lookback)

        # Order Blocks
        for i in range(2, data_len - 1):
            idx = -(data_len - i)

            # Bullish OB: bearish candle followed by strong bullish move
            if (closes[idx] < opens[idx] and                          # bearish candle
                closes[idx + 1] > opens[idx + 1] and                  # next is bullish
                closes[idx + 1] > highs[idx]):                         # strong move up
                zones["bullish_ob"].append({
                    "high": max(opens[idx], closes[idx]),
                    "low":  min(opens[idx], closes[idx])
                })

            # Bearish OB: bullish candle followed by strong bearish move
            if (closes[idx] > opens[idx] and
                closes[idx + 1] < opens[idx + 1] and
                closes[idx + 1] < lows[idx]):
                zones["bearish_ob"].append({
                    "high": max(opens[idx], closes[idx]),
                    "low":  min(opens[idx], closes[idx])
                })

        # Fair Value Gaps (3-candle pattern)
        for i in range(2, data_len):
            idx = -(data_len - i)
            try:
                prev2_high = highs[idx - 2]
                curr_low   = lows[idx]
                prev2_low  = lows[idx - 2]
                curr_high  = highs[idx]

                # Bullish FVG: gap between candle[-2] high and candle[0] low
                if curr_low > prev2_high:
                    zones["bullish_fvg"].append({
                        "high": curr_low,
                        "low":  prev2_high
                    })

                # Bearish FVG: gap between candle[-2] low and candle[0] high
                if curr_high < prev2_low:
                    zones["bearish_fvg"].append({
                        "high": prev2_low,
                        "low":  curr_high
                    })
            except IndexError:
                continue

        # Keep only the 3 most recent zones
        for key in zones:
            zones[key] = zones[key][-3:]

        return zones

    def _premium_discount(self, highs: list, lows: list, price: float,
                           lookback: int = 50) -> dict:
        """
        ICT Premium/Discount model
        Bottom 25% of range = discount (look for longs)
        Top 25% = premium (look for shorts)
        """
        high = max(highs[-lookback:])
        low  = min(lows[-lookback:])
        rng  = high - low

        if rng == 0:
            return {"zone": "equilibrium", "percent": 50}

        percent = (price - low) / rng * 100

        if percent <= 25:
            zone = "discount"
        elif percent >= 75:
            zone = "premium"
        else:
            zone = "equilibrium"

        return {"zone": zone, "percent": percent}

    def _orderbook_analysis(self, orderbook: dict, price: float,
                             depth_levels: int = 20) -> dict:
        """
        Analyze order book for bid/ask imbalance and large walls
        """
        result = {
            "imbalance": "neutral",
            "ratio": 1.0,
            "large_bid_wall": None,
            "large_ask_wall": None
        }

        try:
            bids = orderbook.get("bids", [])[:depth_levels]
            asks = orderbook.get("asks", [])[:depth_levels]

            if not bids or not asks:
                return result

            bid_vol = sum(float(b[1]) for b in bids)
            ask_vol = sum(float(a[1]) for a in asks)

            total = bid_vol + ask_vol
            if total == 0:
                return result

            ratio = bid_vol / ask_vol if ask_vol > 0 else 1.0
            result["ratio"] = ratio

            if ratio > 1.5:
                result["imbalance"] = "bid_heavy"
            elif ratio < 0.67:
                result["imbalance"] = "ask_heavy"

            # Detect large walls (single level > 15% of total depth)
            avg_bid = bid_vol / len(bids) if bids else 0
            avg_ask = ask_vol / len(asks) if asks else 0

            for b in bids:
                if float(b[1]) > avg_bid * 4:
                    result["large_bid_wall"] = float(b[0])
                    break

            for a in asks:
                if float(a[1]) > avg_ask * 4:
                    result["large_ask_wall"] = float(a[0])
                    break

        except Exception as e:
            logger.warning(f"Order book analysis error: {e}")

        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _swing_highs(self, highs: list, window: int = 5) -> list:
        swings = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i - window:i + window + 1]):
                swings.append(highs[i])
        return swings or [max(highs)]

    def _swing_lows(self, lows: list, window: int = 5) -> list:
        swings = []
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[i - window:i + window + 1]):
                swings.append(lows[i])
        return swings or [min(lows)]


# Alias so engine.py import stays clean
AggressiveScalper = InstitutionalStrategy
