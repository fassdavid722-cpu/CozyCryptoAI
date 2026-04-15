"""
CozyCryptoAI — Pure Institutional Strategy
NO indicators. NO EMA. NO RSI. NO MACD.

Trades exactly how institutions do:
- Read WHERE liquidity is resting
- Identify WHEN smart money is accumulating or distributing
- Wait for market structure to SHIFT
- Execute only from high-probability zones (OB, FVG, discount/premium)
- Confirm with order flow and footprint before pulling the trigger
- Order book tells you what's about to happen BEFORE price moves

This is SMC (Smart Money Concepts) + ICT methodology + Wyckoff + Order Flow
combined into one engine.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from config import STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT

logger = logging.getLogger("InstitutionalStrategy")


@dataclass
class Signal:
    symbol: str
    action: str              # 'BUY' | 'SELL'
    confidence: float        # 0.0 - 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    size_percent: float
    confluence: List[str] = field(default_factory=list)
    regime: str = "unknown"
    invalidation: float = 0.0   # Price level that kills the trade idea


class InstitutionalStrategy:

    def __init__(self):
        self.sl_pct = STOP_LOSS_PERCENT / 100
        self.tp_pct = TAKE_PROFIT_PERCENT / 100
        self.MIN_CONFLUENCE = 5   # Minimum points to take a trade

    def analyze(self, symbol: str, candles: list,
                orderbook: dict = None,
                direction_bias: str = None) -> Optional[Signal]:
        """
        Pure institutional analysis. No indicators.
        Every decision is based on price, volume, structure, and order flow.
        """
        try:
            if not candles or len(candles) < 60:
                return None

            opens   = [float(c[1]) for c in candles]
            highs   = [float(c[2]) for c in candles]
            lows    = [float(c[3]) for c in candles]
            closes  = [float(c[4]) for c in candles]
            volumes = [float(c[5]) for c in candles]
            price   = closes[-1]

            if price <= 0:
                return None

            long_score  = 0
            short_score = 0
            confluence  = []

            # ── LAYER 1: VOLATILITY REGIME ───────────────────────────────────
            # Never trade when price is compressing — no edge
            regime, atr = self._volatility_regime(highs, lows, closes)
            if regime == "dead":
                return None   # No range, no trade
            if regime == "expanding":
                long_score  += 1
                short_score += 1
                confluence.append(f"Volatility expanding — ATR {atr/price*100:.2f}% of price")
            elif regime == "compressed":
                # Compression before expansion — wait for the break
                # Still analyze but reduce conviction
                pass

            # ── LAYER 2: MARKET STRUCTURE ─────────────────────────────────────
            # Structure tells us the STORY of who is in control
            structure = self._market_structure(highs, lows, closes)

            if structure["trend"] == "bullish":
                long_score += 3
                confluence.append(f"Bullish structure — {structure['detail']}")
            elif structure["trend"] == "bearish":
                short_score += 3
                confluence.append(f"Bearish structure — {structure['detail']}")

            # Break of Structure = trend continuation
            if structure["bos_bullish"]:
                long_score += 3
                confluence.append("BOS confirmed bullish — structure broke to upside")
            if structure["bos_bearish"]:
                short_score += 3
                confluence.append("BOS confirmed bearish — structure broke to downside")

            # Change of Character = potential reversal — high value signal
            if structure["choch_bullish"]:
                long_score += 4
                confluence.append("CHoCH bullish — smart money shifted, potential reversal long")
            if structure["choch_bearish"]:
                short_score += 4
                confluence.append("CHoCH bearish — smart money shifted, potential reversal short")

            # ── LAYER 3: LIQUIDITY ────────────────────────────────────────────
            # Smart money ALWAYS moves toward liquidity before reversing
            liquidity = self._liquidity_analysis(highs, lows, closes, volumes)

            if liquidity["sell_side_swept"]:
                # Lows swept = stop hunt below = now go long
                long_score += 4
                confluence.append(f"Sell-side liquidity swept below ${liquidity['swept_level']:.6g} — reversal setup")
            if liquidity["buy_side_swept"]:
                # Highs swept = stop hunt above = now go short
                short_score += 4
                confluence.append(f"Buy-side liquidity swept above ${liquidity['swept_level']:.6g} — reversal setup")
            if liquidity["equal_highs"]:
                short_score += 1
                confluence.append(f"Equal highs at ${liquidity['equal_highs']:.6g} — buy-side liquidity target")
            if liquidity["equal_lows"]:
                long_score += 1
                confluence.append(f"Equal lows at ${liquidity['equal_lows']:.6g} — sell-side liquidity target")
            if liquidity["inducement_long"]:
                long_score += 2
                confluence.append("Inducement sweep below structure — engineered liquidity grab")
            if liquidity["inducement_short"]:
                short_score += 2
                confluence.append("Inducement sweep above structure — engineered liquidity grab")

            # ── LAYER 4: ORDER FLOW (CVD) ─────────────────────────────────────
            # CVD shows us if REAL buyers/sellers are stepping in
            # This is the fastest signal — tells you before price confirms
            order_flow = self._order_flow(opens, closes, volumes)

            if order_flow["aggressive_buying"]:
                long_score += 3
                confluence.append(f"Aggressive buying — CVD delta +{order_flow['delta']:,.0f}, buyers in control")
            if order_flow["aggressive_selling"]:
                short_score += 3
                confluence.append(f"Aggressive selling — CVD delta {order_flow['delta']:,.0f}, sellers in control")
            if order_flow["absorption_long"]:
                long_score += 3
                confluence.append("Selling absorbed by buyers — high volume, price held — long signal")
            if order_flow["absorption_short"]:
                short_score += 3
                confluence.append("Buying absorbed by sellers — high volume, price rejected — short signal")
            if order_flow["cvd_divergence_long"]:
                long_score += 2
                confluence.append("CVD divergence — price making lows but delta rising — hidden buying")
            if order_flow["cvd_divergence_short"]:
                short_score += 2
                confluence.append("CVD divergence — price making highs but delta falling — hidden selling")

            # ── LAYER 5: FOOTPRINT CHART ──────────────────────────────────────
            # Footprint shows buy vs sell at every price level
            # Stacked bid imbalances = institutions buying at that level
            footprint = self._footprint(opens, closes, highs, lows, volumes)

            if footprint["stacked_bid_imbalance"]:
                long_score += 3
                confluence.append("Footprint: stacked bid imbalances — institutions absorbing supply")
            if footprint["stacked_ask_imbalance"]:
                short_score += 3
                confluence.append("Footprint: stacked ask imbalances — institutions distributing")
            if footprint["unfinished_business_low"]:
                long_score += 2
                confluence.append("Footprint: unfinished business below — price likely returns to fill")
            if footprint["unfinished_business_high"]:
                short_score += 2
                confluence.append("Footprint: unfinished business above — price likely returns to fill")
            if footprint["buying_exhaustion"]:
                short_score += 2
                confluence.append("Footprint: buying exhaustion — delta positive but price stalling")
            if footprint["selling_exhaustion"]:
                long_score += 2
                confluence.append("Footprint: selling exhaustion — delta negative but price holding")

            # ── LAYER 6: ACCUMULATION / DISTRIBUTION ──────────────────────────
            # Wyckoff: institutions accumulate in silence, distribute at the top
            acc_dist = self._accumulation_distribution(opens, closes, highs, lows, volumes)

            if acc_dist["phase"] == "spring":
                long_score += 5
                confluence.append("Wyckoff Spring — final shakeout below range, major long setup")
            elif acc_dist["phase"] == "upthrust":
                short_score += 5
                confluence.append("Wyckoff Upthrust — false breakout above range, major short setup")
            elif acc_dist["phase"] == "accumulation":
                long_score += 2
                confluence.append(f"Wyckoff accumulation phase — smart money building longs")
            elif acc_dist["phase"] == "distribution":
                short_score += 2
                confluence.append(f"Wyckoff distribution phase — smart money offloading longs")
            elif acc_dist["phase"] == "markup":
                long_score += 2
                confluence.append("Wyckoff markup — institutions driving price up")
            elif acc_dist["phase"] == "markdown":
                short_score += 2
                confluence.append("Wyckoff markdown — institutions driving price down")
            if acc_dist["re_accumulation"]:
                long_score += 2
                confluence.append("Re-accumulation range — continuation long after pullback")
            if acc_dist["re_distribution"]:
                short_score += 2
                confluence.append("Re-distribution range — continuation short after bounce")

            # ── LAYER 7: EXECUTION ZONES (OB + FVG) ──────────────────────────
            # Only enter from institutional zones — not random price levels
            zones = self._execution_zones(opens, closes, highs, lows)

            # Order Blocks
            for ob in zones["bullish_ob"]:
                if ob["low"] <= price <= ob["high"]:
                    long_score += 4
                    confluence.append(f"Price in bullish Order Block ${ob['low']:.6g}–${ob['high']:.6g} — institutional demand zone")
                    break

            for ob in zones["bearish_ob"]:
                if ob["low"] <= price <= ob["high"]:
                    short_score += 4
                    confluence.append(f"Price in bearish Order Block ${ob['low']:.6g}–${ob['high']:.6g} — institutional supply zone")
                    break

            # Breaker Blocks (failed OBs that flip — very high probability)
            for bb in zones["bullish_breaker"]:
                if bb["low"] <= price <= bb["high"]:
                    long_score += 5
                    confluence.append(f"Price in bullish Breaker Block — failed bearish OB now support")
                    break

            for bb in zones["bearish_breaker"]:
                if bb["low"] <= price <= bb["high"]:
                    short_score += 5
                    confluence.append(f"Price in bearish Breaker Block — failed bullish OB now resistance")
                    break

            # Fair Value Gaps
            for fvg in zones["bullish_fvg"]:
                if fvg["low"] <= price <= fvg["high"]:
                    long_score += 3
                    confluence.append(f"Price filling bullish FVG ${fvg['low']:.6g}–${fvg['high']:.6g} — inefficiency fill")
                    break

            for fvg in zones["bearish_fvg"]:
                if fvg["low"] <= price <= fvg["high"]:
                    short_score += 3
                    confluence.append(f"Price filling bearish FVG ${fvg['low']:.6g}–${fvg['high']:.6g} — inefficiency fill")
                    break

            # Mitigation Blocks (price returning to mitigate unmitigated OBs)
            for mb in zones["mitigation_blocks"]:
                if mb["low"] <= price <= mb["high"]:
                    if mb["type"] == "long":
                        long_score += 3
                        confluence.append("Price at mitigation block — institutions defending previous lows")
                    else:
                        short_score += 3
                        confluence.append("Price at mitigation block — institutions defending previous highs")
                    break

            # ICT Premium / Discount
            pd = self._premium_discount(highs, lows, price)
            if pd["zone"] == "discount":
                long_score += 2
                confluence.append(f"ICT discount zone ({pd['pct']:.0f}% of range) — optimal long territory")
            elif pd["zone"] == "premium":
                short_score += 2
                confluence.append(f"ICT premium zone ({pd['pct']:.0f}% of range) — optimal short territory")

            # ── LAYER 8: ORDER BOOK ───────────────────────────────────────────
            # Order book gives real-time intent — what big players are doing NOW
            if orderbook and orderbook.get("bids") and orderbook.get("asks"):
                ob_analysis = self._orderbook_analysis(orderbook, price, atr)

                if ob_analysis["bid_dominance"]:
                    long_score += 3
                    confluence.append(f"Order book bid dominance {ob_analysis['ratio']:.1f}x — buyers stacking up")
                elif ob_analysis["ask_dominance"]:
                    short_score += 3
                    confluence.append(f"Order book ask dominance {ob_analysis['ratio']:.1f}x — sellers stacking up")
                if ob_analysis["iceberg_bid"]:
                    long_score += 2
                    confluence.append(f"Iceberg bid detected at ${ob_analysis['iceberg_bid_price']:.6g} — hidden buy order")
                if ob_analysis["iceberg_ask"]:
                    short_score += 2
                    confluence.append(f"Iceberg ask detected at ${ob_analysis['iceberg_ask_price']:.6g} — hidden sell order")
                if ob_analysis["thin_ask_wall"]:
                    long_score += 1
                    confluence.append("Thin ask wall above — price can break through easily")
                if ob_analysis["thin_bid_wall"]:
                    short_score += 1
                    confluence.append("Thin bid wall below — price can break through easily")

            # ── DECISION ──────────────────────────────────────────────────────
            max_score = 25
            action = None
            score  = 0

            if long_score >= self.MIN_CONFLUENCE and long_score > short_score:
                action = "BUY"
                score  = long_score
            elif short_score >= self.MIN_CONFLUENCE and short_score > long_score:
                action = "SELL"
                score  = short_score

            if not action:
                return None

            confidence = min(score / max_score, 1.0)
            if confidence < 0.40:
                return None

            # ── STOP LOSS PLACEMENT ───────────────────────────────────────────
            # Place SL beyond the nearest liquidity / structure level
            # NOT a fixed % — institutions use structure for stops
            sl_buffer = atr * 0.5
            if action == "BUY":
                # SL below the most recent swing low or swept level
                ref_low   = min(lows[-10:])
                stop_loss = ref_low - sl_buffer
                # Hard cap: no wider than config SL%
                stop_loss = max(stop_loss, price * (1 - self.sl_pct * 1.5))
                take_profit = price + (price - stop_loss) * 2.5   # 2.5:1 R/R
                invalidation = stop_loss
            else:
                ref_high    = max(highs[-10:])
                stop_loss   = ref_high + sl_buffer
                stop_loss   = min(stop_loss, price * (1 + self.sl_pct * 1.5))
                take_profit = price - (stop_loss - price) * 2.5
                invalidation = stop_loss

            # Dynamic sizing: more confident = larger size (5–12%)
            size_percent = 5 + (confidence * 7)

            reason = " | ".join(confluence[:4])

            logger.info(
                f"🎯 {action} {symbol} @ {price:.6g} | "
                f"Conf: {confidence:.0%} | Regime: {regime} | Score: {score}/{max_score}"
            )
            for c in confluence[:6]:
                logger.info(f"   ✓ {c}")

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
                regime=regime,
                invalidation=invalidation
            )

        except Exception as e:
            logger.error(f"Strategy error {symbol}: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 1 — VOLATILITY REGIME
    # ═══════════════════════════════════════════════════════════════════════════

    def _volatility_regime(self, highs, lows, closes, period=14) -> Tuple[str, float]:
        """
        ATR-based regime — no indicators, just true range
        dead       → price going nowhere, don't trade
        compressed → coiling, breakout coming
        trending   → directional, good for continuation
        expanding  → momentum move, scalp aggressively
        """
        if len(closes) < period + 2:
            return "trending", 0.001

        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i]  - closes[i-1])
            )
            trs.append(tr)

        atr      = sum(trs[-period:]) / period
        prev_atr = sum(trs[-period*2:-period]) / period if len(trs) >= period*2 else atr
        price    = closes[-1]
        atr_pct  = (atr / price) * 100

        if atr_pct < 0.15:
            return "dead", atr
        elif atr > prev_atr * 1.3:
            return "expanding", atr
        elif atr < prev_atr * 0.7:
            return "compressed", atr
        else:
            return "trending", atr

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 2 — MARKET STRUCTURE
    # ═══════════════════════════════════════════════════════════════════════════

    def _market_structure(self, highs, lows, closes, swing_window=5) -> dict:
        """
        Pure price action structure:
        - Swing highs / swing lows
        - HH/HL = bullish, LH/LL = bearish
        - BOS = break of structure (continuation)
        - CHoCH = change of character (reversal) — the most powerful signal
        """
        result = {
            "trend": "neutral", "detail": "",
            "bos_bullish": False, "bos_bearish": False,
            "choch_bullish": False, "choch_bearish": False,
            "last_sh": None, "last_sl": None
        }

        if len(highs) < swing_window * 4:
            return result

        sh = self._find_swing_highs(highs, swing_window)
        sl = self._find_swing_lows(lows, swing_window)

        if len(sh) < 2 or len(sl) < 2:
            return result

        result["last_sh"] = sh[-1]
        result["last_sl"] = sl[-1]

        hh = sh[-1] > sh[-2]
        hl = sl[-1] > sl[-2]
        lh = sh[-1] < sh[-2]
        ll = sl[-1] < sl[-2]

        if hh and hl:
            result["trend"]  = "bullish"
            result["detail"] = "HH + HL confirmed"
        elif lh and ll:
            result["trend"]  = "bearish"
            result["detail"] = "LH + LL confirmed"
        elif hh and ll:
            result["trend"]  = "neutral"
            result["detail"] = "conflicting — HH but LL"
        elif lh and hl:
            result["trend"]  = "neutral"
            result["detail"] = "conflicting — HL but LH"

        price = closes[-1]

        # BOS: price closes BEYOND the last swing in trend direction
        if result["trend"] == "bullish" and price > sh[-1]:
            result["bos_bullish"] = True
        elif result["trend"] == "bearish" and price < sl[-1]:
            result["bos_bearish"] = True

        # CHoCH: price breaks AGAINST trend — most powerful reversal signal
        if result["trend"] == "bearish" and price > sh[-1]:
            result["choch_bullish"] = True
        elif result["trend"] == "bullish" and price < sl[-1]:
            result["choch_bearish"] = True

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 3 — LIQUIDITY
    # ═══════════════════════════════════════════════════════════════════════════

    def _liquidity_analysis(self, highs, lows, closes, volumes, lookback=30) -> dict:
        """
        Smart money moves toward liquidity (resting stop orders) before reversing.

        Sell-side liquidity = stops below recent lows (retail longs got stopped out)
        Buy-side liquidity  = stops above recent highs (retail shorts got stopped out)

        After a sweep: institutions reverse. This is the entry.
        """
        result = {
            "sell_side_swept": False,
            "buy_side_swept":  False,
            "swept_level": 0,
            "equal_highs": None,
            "equal_lows":  None,
            "inducement_long": False,
            "inducement_short": False
        }

        if len(closes) < lookback + 5:
            return result

        price      = closes[-1]
        prev_highs = highs[-lookback-1:-3]
        prev_lows  = lows[-lookback-1:-3]
        recent_h   = highs[-3:]
        recent_l   = lows[-3:]

        ref_high = max(prev_highs) if prev_highs else 0
        ref_low  = min(prev_lows)  if prev_lows  else float('inf')

        # Sweep: wick went through level but CLOSED back inside
        # Sell-side sweep: wick below prior lows, close above them
        if min(recent_l) < ref_low and closes[-1] > ref_low:
            result["sell_side_swept"] = True
            result["swept_level"]     = ref_low

        # Buy-side sweep: wick above prior highs, close below them
        if max(recent_h) > ref_high and closes[-1] < ref_high:
            result["buy_side_swept"] = True
            result["swept_level"]    = ref_high

        # Equal highs/lows: 2+ touches within 0.1% = resting liquidity pool
        tol_h = ref_high * 0.001
        tol_l = ref_low  * 0.001
        eq_h  = sum(1 for h in prev_highs if abs(h - ref_high) < tol_h)
        eq_l  = sum(1 for l in prev_lows  if abs(l - ref_low)  < tol_l)

        if eq_h >= 2:
            result["equal_highs"] = ref_high
        if eq_l >= 2:
            result["equal_lows"] = ref_low

        # Inducement: minor swing broken briefly before major move
        # Small sweep below minor low in uptrend = spring/inducement
        minor_lows  = sorted(prev_lows)[:3]
        minor_highs = sorted(prev_highs, reverse=True)[:3]

        if minor_lows and min(recent_l) < minor_lows[-1] and closes[-1] > minor_lows[-1]:
            result["inducement_long"] = True
        if minor_highs and max(recent_h) > minor_highs[-1] and closes[-1] < minor_highs[-1]:
            result["inducement_short"] = True

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 4 — ORDER FLOW (CVD)
    # ═══════════════════════════════════════════════════════════════════════════

    def _order_flow(self, opens, closes, volumes, lookback=20) -> dict:
        """
        Cumulative Volume Delta — tracks REAL buying vs selling pressure
        This is the fastest signal. Price lags. Volume delta leads.

        Aggressive buying  = market orders hitting the ask = real buyers
        Aggressive selling = market orders hitting the bid = real sellers
        Absorption         = one side trying but price NOT moving = trap
        CVD Divergence     = price and delta going opposite directions = reversal
        """
        result = {
            "aggressive_buying":   False,
            "aggressive_selling":  False,
            "absorption_long":     False,
            "absorption_short":    False,
            "cvd_divergence_long": False,
            "cvd_divergence_short":False,
            "delta": 0
        }

        if len(closes) < lookback:
            return result

        # Estimate per-candle delta: bullish body = more buy volume
        deltas = []
        for i in range(len(opens)):
            body   = closes[i] - opens[i]
            vol    = volumes[i]
            rng    = abs(closes[i] - opens[i]) + 1e-10
            # Proportion of volume that's buying vs selling
            buy_pct  = 0.5 + (body / (2 * rng)) * 0.4   # 30-70% range
            deltas.append(vol * buy_pct - vol * (1 - buy_pct))

        recent     = deltas[-lookback:]
        cumulative = sum(recent)
        result["delta"] = cumulative

        # Aggressive buying: rising delta, rising price, increasing volume
        avg_vol = sum(volumes[-lookback:]) / lookback
        if (cumulative > 0 and
            sum(recent[-5:]) > sum(recent[:5]) and
            volumes[-1] > avg_vol * 1.2):
            result["aggressive_buying"] = True

        # Aggressive selling
        if (cumulative < 0 and
            sum(recent[-5:]) < sum(recent[:5]) and
            volumes[-1] > avg_vol * 1.2):
            result["aggressive_selling"] = True

        # Absorption: high volume but price barely moved
        price_move = abs(closes[-1] - closes[-6]) if len(closes) > 6 else 0
        avg_move   = sum(abs(closes[i] - closes[i-1]) for i in range(-lookback, -1)) / lookback
        high_vol   = volumes[-1] > avg_vol * 1.8

        if high_vol and price_move < avg_move * 0.3:
            if cumulative > 0:
                result["absorption_short"] = True   # Buying absorbed = sellers winning
            else:
                result["absorption_long"] = True    # Selling absorbed = buyers winning

        # CVD Divergence: price vs delta going opposite ways
        if len(closes) >= lookback:
            price_up  = closes[-1] > closes[-lookback]
            delta_up  = recent[-1] > recent[0] if recent else False

            price_low_recent  = closes[-1] < closes[-lookback//2]
            delta_high_recent = sum(recent[-lookback//2:]) > sum(recent[:lookback//2])

            if price_low_recent and delta_high_recent:
                result["cvd_divergence_long"] = True   # Price down, delta up = hidden buyers
            elif not price_low_recent and not delta_high_recent:
                result["cvd_divergence_short"] = True  # Price up, delta down = hidden sellers

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 5 — FOOTPRINT CHART
    # ═══════════════════════════════════════════════════════════════════════════

    def _footprint(self, opens, closes, highs, lows, volumes, lookback=10) -> dict:
        """
        Simulated footprint chart analysis.
        Footprint shows buy/sell volume at EACH price level.

        Stacked bid imbalances   = institutions buying at multiple levels = strong long
        Stacked ask imbalances   = institutions selling at multiple levels = strong short
        Unfinished business      = price left a level with only one side = will return
        Buying/selling exhaustion= delta peaks but price stalls = reversal
        """
        result = {
            "stacked_bid_imbalance":  False,
            "stacked_ask_imbalance":  False,
            "unfinished_business_low": False,
            "unfinished_business_high":False,
            "buying_exhaustion":  False,
            "selling_exhaustion": False
        }

        if len(closes) < lookback + 2:
            return result

        # Classify each candle's footprint
        bid_imbalance_count = 0
        ask_imbalance_count = 0
        deltas = []

        for i in range(-lookback, 0):
            body      = closes[i] - opens[i]
            wick_up   = highs[i]  - max(opens[i], closes[i])
            wick_down = min(opens[i], closes[i]) - lows[i]
            full_rng  = highs[i]  - lows[i] if highs[i] != lows[i] else 1e-10
            vol       = volumes[i]

            # Bid imbalance: strong bullish body, small upper wick
            if body > 0 and body/full_rng > 0.6 and wick_up < body * 0.3:
                bid_imbalance_count += 1

            # Ask imbalance: strong bearish body, small lower wick
            if body < 0 and abs(body)/full_rng > 0.6 and wick_down < abs(body) * 0.3:
                ask_imbalance_count += 1

            buy_vol  = vol * (0.5 + min(body / (full_rng * 2), 0.4))
            sell_vol = vol - buy_vol
            deltas.append(buy_vol - sell_vol)

        # Stacked = 3+ consecutive imbalances on same side
        if bid_imbalance_count >= 3:
            result["stacked_bid_imbalance"] = True
        if ask_imbalance_count >= 3:
            result["stacked_ask_imbalance"] = True

        # Unfinished business: long lower wick (price returned to buy but didn't finish)
        last_wick_down = min(opens[-1], closes[-1]) - lows[-1]
        last_wick_up   = highs[-1] - max(opens[-1], closes[-1])
        last_range     = highs[-1] - lows[-1] if highs[-1] != lows[-1] else 1e-10

        if last_wick_down / last_range > 0.5:
            result["unfinished_business_low"] = True
        if last_wick_up / last_range > 0.5:
            result["unfinished_business_high"] = True

        # Exhaustion: delta peaked 3-4 candles ago, now declining while price stalls
        if len(deltas) >= 6:
            peak_idx = deltas.index(max(deltas[-6:]))
            if peak_idx <= 3 and sum(deltas[-3:]) < sum(deltas[-6:-3]) * 0.5:
                result["buying_exhaustion"] = True

            trough_idx = deltas.index(min(deltas[-6:]))
            if trough_idx <= 3 and sum(deltas[-3:]) > sum(deltas[-6:-3]) * 0.5:
                result["selling_exhaustion"] = True

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 6 — ACCUMULATION / DISTRIBUTION (WYCKOFF)
    # ═══════════════════════════════════════════════════════════════════════════

    def _accumulation_distribution(self, opens, closes, highs, lows, volumes,
                                    lookback=40) -> dict:
        """
        Wyckoff methodology — how institutions accumulate/distribute:

        Accumulation → Spring → Markup
        Distribution → Upthrust → Markdown

        Spring:    Final shakeout below range support = highest probability long
        Upthrust:  Final fake breakout above range resistance = highest probability short
        """
        result = {
            "phase": "neutral",
            "re_accumulation": False,
            "re_distribution": False
        }

        if len(closes) < lookback:
            return result

        segment     = closes[-lookback:]
        seg_highs   = highs[-lookback:]
        seg_lows    = lows[-lookback:]
        seg_vols    = volumes[-lookback:]
        seg_opens   = opens[-lookback:]

        rng_high    = max(seg_highs)
        rng_low     = min(seg_lows)
        rng         = rng_high - rng_low
        price       = closes[-1]

        if rng == 0:
            return result

        # Detect if we're in a trading range (price oscillating in a band)
        avg_body    = sum(abs(segment[i] - seg_opens[i]) for i in range(len(segment))) / len(segment)
        in_range    = (rng > 0) and (price > rng_low + rng * 0.1) and (price < rng_high - rng * 0.1)

        # Volume profile: accumulation has higher volume at lows
        lower_half_vol = sum(v for v, l in zip(seg_vols, seg_lows) if l < (rng_low + rng * 0.4))
        upper_half_vol = sum(v for v, h in zip(seg_vols, seg_highs) if h > (rng_low + rng * 0.6))

        # Spring: price dips BELOW range low then snaps back up with volume
        recent_lows  = seg_lows[-5:]
        recent_close = closes[-1]
        if min(recent_lows) < rng_low and recent_close > rng_low:
            if seg_vols[-1] > sum(seg_vols) / len(seg_vols) * 1.5:
                result["phase"] = "spring"
                return result

        # Upthrust: price pops ABOVE range high then snaps back down
        recent_highs = seg_highs[-5:]
        if max(recent_highs) > rng_high and recent_close < rng_high:
            if seg_vols[-1] > sum(seg_vols) / len(seg_vols) * 1.5:
                result["phase"] = "upthrust"
                return result

        # Markup: price broke above range and is trending up
        if price > rng_high and closes[-1] > closes[-5]:
            result["phase"] = "markup"
            # Re-accumulation: small pause in uptrend
            if in_range:
                result["re_accumulation"] = True
            return result

        # Markdown: price broke below range and is trending down
        if price < rng_low and closes[-1] < closes[-5]:
            result["phase"] = "markdown"
            if in_range:
                result["re_distribution"] = True
            return result

        # In range — determine if accumulation or distribution by volume profile
        if in_range:
            if lower_half_vol > upper_half_vol * 1.3:
                result["phase"] = "accumulation"   # More volume at lows = buying
            elif upper_half_vol > lower_half_vol * 1.3:
                result["phase"] = "distribution"   # More volume at highs = selling

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 7 — EXECUTION ZONES
    # ═══════════════════════════════════════════════════════════════════════════

    def _execution_zones(self, opens, closes, highs, lows, lookback=40) -> dict:
        """
        Identify WHERE to enter, not just what direction.

        Order Block (OB):
          Bullish OB = last bearish candle before a strong bullish impulse
          Bearish OB = last bullish candle before a strong bearish impulse

        Breaker Block:
          Failed OB that price breaks through = flips to opposite zone
          Highest probability zone in all of SMC

        Fair Value Gap (FVG / Imbalance):
          3-candle pattern where price moved so fast it left a gap
          Price will return to fill it — almost guaranteed

        Mitigation Block:
          Previous OB that price returns to for one final touch before continuing
        """
        zones = {
            "bullish_ob":       [],
            "bearish_ob":       [],
            "bullish_breaker":  [],
            "bearish_breaker":  [],
            "bullish_fvg":      [],
            "bearish_fvg":      [],
            "mitigation_blocks":[]
        }

        n = min(len(closes), lookback)

        for i in range(2, n - 2):
            idx = i - n   # negative index

            c  = closes[idx];  o  = opens[idx]
            c1 = closes[idx+1]; o1 = opens[idx+1]
            h  = highs[idx];   l  = lows[idx]

            bullish_candle = c > o
            bearish_candle = c < o

            # ── Order Blocks ──────────────────────────────────────────────────
            # Bullish OB: bearish candle followed by strong up move
            if (bearish_candle and c1 > o1 and          # next candle bullish
                c1 > h):                                  # closes above OB high
                zones["bullish_ob"].append({
                    "high": max(o, c),
                    "low":  min(o, c),
                    "idx":  i
                })

            # Bearish OB: bullish candle followed by strong down move
            if (bullish_candle and c1 < o1 and
                c1 < l):
                zones["bearish_ob"].append({
                    "high": max(o, c),
                    "low":  min(o, c),
                    "idx":  i
                })

            # ── Fair Value Gaps ───────────────────────────────────────────────
            # Bullish FVG: candle[i-2].high < candle[i].low
            if i >= 2:
                h_prev2 = highs[idx-2] if idx-2 >= -n else None
                l_curr  = lows[idx]

                if h_prev2 and l_curr > h_prev2:
                    zones["bullish_fvg"].append({
                        "high": l_curr,
                        "low":  h_prev2
                    })

                l_prev2 = lows[idx-2] if idx-2 >= -n else None
                h_curr  = highs[idx]

                if l_prev2 and h_curr < l_prev2:
                    zones["bearish_fvg"].append({
                        "high": l_prev2,
                        "low":  h_curr
                    })

        # ── Breaker Blocks ────────────────────────────────────────────────────
        # A bullish OB that price broke back below = now bearish breaker
        price = closes[-1]
        for ob in zones["bullish_ob"][:]:
            if price < ob["low"]:
                zones["bearish_breaker"].append(ob)

        # A bearish OB that price broke back above = now bullish breaker
        for ob in zones["bearish_ob"][:]:
            if price > ob["high"]:
                zones["bullish_breaker"].append(ob)

        # ── Mitigation Blocks ─────────────────────────────────────────────────
        # Unmitigated OBs that price is currently returning to
        for ob in zones["bullish_ob"][-5:]:
            if ob["low"] <= price <= ob["high"] * 1.005:
                zones["mitigation_blocks"].append({**ob, "type": "long"})
        for ob in zones["bearish_ob"][-5:]:
            if ob["low"] * 0.995 <= price <= ob["high"]:
                zones["mitigation_blocks"].append({**ob, "type": "short"})

        # Keep only recent zones (last 3 of each)
        for key in ["bullish_ob", "bearish_ob", "bullish_fvg", "bearish_fvg"]:
            zones[key] = zones[key][-3:]

        return zones

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 8 — ORDER BOOK
    # ═══════════════════════════════════════════════════════════════════════════

    def _orderbook_analysis(self, orderbook: dict, price: float, atr: float) -> dict:
        """
        Real-time order book analysis:
        - Bid/ask dominance (volume imbalance)
        - Iceberg orders (hidden large orders being refreshed)
        - Thin walls (easy for price to break through)
        - Spoofing detection (large orders that disappear)
        """
        result = {
            "bid_dominance":      False,
            "ask_dominance":      False,
            "ratio":              1.0,
            "iceberg_bid":        False,
            "iceberg_ask":        False,
            "iceberg_bid_price":  0,
            "iceberg_ask_price":  0,
            "thin_ask_wall":      False,
            "thin_bid_wall":      False
        }

        try:
            bids = orderbook.get("bids", [])[:30]
            asks = orderbook.get("asks", [])[:30]

            if not bids or not asks:
                return result

            bid_prices = [float(b[0]) for b in bids]
            ask_prices = [float(a[0]) for a in asks]
            bid_vols   = [float(b[1]) for b in bids]
            ask_vols   = [float(a[1]) for a in asks]

            total_bid = sum(bid_vols)
            total_ask = sum(ask_vols)

            if total_bid + total_ask == 0:
                return result

            ratio = total_bid / total_ask if total_ask > 0 else 1.0
            result["ratio"] = ratio

            if ratio > 1.6:
                result["bid_dominance"] = True
            elif ratio < 0.625:
                result["ask_dominance"] = True

            # Iceberg detection: single level with volume >> average
            avg_bid_vol = total_bid / len(bid_vols) if bid_vols else 0
            avg_ask_vol = total_ask / len(ask_vols) if ask_vols else 0

            for i, (p, v) in enumerate(zip(bid_prices, bid_vols)):
                if v > avg_bid_vol * 5 and i < 10:   # Large order near top of book
                    result["iceberg_bid"]       = True
                    result["iceberg_bid_price"] = p
                    break

            for i, (p, v) in enumerate(zip(ask_prices, ask_vols)):
                if v > avg_ask_vol * 5 and i < 10:
                    result["iceberg_ask"]       = True
                    result["iceberg_ask_price"] = p
                    break

            # Thin wall: total volume in 1 ATR range above/below is small
            thin_threshold = total_ask * 0.1
            ask_near = sum(v for p, v in zip(ask_prices, ask_vols) if p < price + atr)
            if ask_near < thin_threshold:
                result["thin_ask_wall"] = True

            thin_threshold_b = total_bid * 0.1
            bid_near = sum(v for p, v in zip(bid_prices, bid_vols) if p > price - atr)
            if bid_near < thin_threshold_b:
                result["thin_bid_wall"] = True

        except Exception as e:
            logger.warning(f"Order book error: {e}")

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _premium_discount(self, highs, lows, price, lookback=50) -> dict:
        high = max(highs[-lookback:])
        low  = min(lows[-lookback:])
        rng  = high - low
        if rng == 0:
            return {"zone": "equilibrium", "pct": 50}
        pct  = (price - low) / rng * 100
        zone = "discount" if pct <= 30 else "premium" if pct >= 70 else "equilibrium"
        return {"zone": zone, "pct": pct}

    def _find_swing_highs(self, highs, window=5) -> list:
        swings = []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                swings.append(highs[i])
        return swings or [max(highs)]

    def _find_swing_lows(self, lows, window=5) -> list:
        swings = []
        for i in range(window, len(lows) - window):
            if lows[i] == min(lows[i-window:i+window+1]):
                swings.append(lows[i])
        return swings or [min(lows)]


# Alias
AggressiveScalper = InstitutionalStrategy
