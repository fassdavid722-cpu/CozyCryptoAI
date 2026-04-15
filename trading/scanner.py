"""
CozyCryptoAI - Universal Market Scanner
Dynamically discovers ALL futures pairs on Bitget
Filters by volume, price change, and liquidity thresholds
Returns the best opportunities to trade — not just top 5
"""

import asyncio
import logging
from typing import List, Dict
from config import (
    MIN_VOLUME_USDT_24H,
    MIN_PRICE_CHANGE_PERCENT,
    MAX_PAIRS_TO_SCAN,
    BLACKLISTED_PAIRS
)

logger = logging.getLogger("MarketScanner")


class MarketScanner:
    def __init__(self, client):
        self.client = client
        self._all_pairs_cache = []
        self._cache_ts = 0
        self._cache_ttl = 300  # Refresh pair list every 5 minutes

    async def get_all_futures_pairs(self) -> List[str]:
        """Fetch ALL available USDT-M futures pairs from Bitget"""
        import time
        now = time.time()
        if self._all_pairs_cache and (now - self._cache_ts) < self._cache_ttl:
            return self._all_pairs_cache

        try:
            resp = await self.client.get(
                "/api/v2/mix/market/tickers",
                {"productType": "USDT-FUTURES"}
            )
            tickers = resp.get("data", [])
            pairs = [
                t["symbol"] for t in tickers
                if t.get("symbol", "").endswith("USDT")
                and t.get("symbol") not in BLACKLISTED_PAIRS
            ]
            self._all_pairs_cache = pairs
            self._cache_ts = now
            logger.info(f"📡 Found {len(pairs)} USDT-M futures pairs on Bitget")
            return pairs
        except Exception as e:
            logger.error(f"Failed to fetch pairs: {e}")
            return self._all_pairs_cache or []

    async def scan_market(self) -> List[Dict]:
        """
        Scan ALL futures pairs and return those meeting criteria:
        - 24h volume >= MIN_VOLUME_USDT_24H
        - Price change >= MIN_PRICE_CHANGE_PERCENT (momentum)
        - Has enough liquidity to trade

        Returns ranked list of opportunities (best first)
        """
        try:
            resp = await self.client.get(
                "/api/v2/mix/market/tickers",
                {"productType": "USDT-FUTURES"}
            )
            tickers = resp.get("data", [])
        except Exception as e:
            logger.error(f"Scan error: {e}")
            return []

        opportunities = []

        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            if symbol in BLACKLISTED_PAIRS:
                continue

            try:
                volume_24h = float(t.get("usdtVolume", 0) or t.get("quoteVolume", 0) or 0)
                price = float(t.get("lastPr", 0) or t.get("last", 0) or 0)
                change_24h = float(t.get("change24h", 0) or t.get("priceChangePercent", 0) or 0)
                high_24h = float(t.get("high24h", 0) or 0)
                low_24h = float(t.get("low24h", 0) or 0)
                open_interest = float(t.get("holdingAmount", 0) or 0)

                if price <= 0:
                    continue

                # Core filters
                if volume_24h < MIN_VOLUME_USDT_24H:
                    continue

                # Convert change to percentage if needed
                change_pct = change_24h * 100 if abs(change_24h) < 1 else change_24h
                abs_change = abs(change_pct)

                if abs_change < MIN_PRICE_CHANGE_PERCENT:
                    continue

                # Score the opportunity
                score = self._score_opportunity(
                    volume_24h=volume_24h,
                    change_pct=change_pct,
                    abs_change=abs_change,
                    open_interest=open_interest,
                    high_24h=high_24h,
                    low_24h=low_24h,
                    price=price
                )

                opportunities.append({
                    "symbol": symbol,
                    "price": price,
                    "volume_24h": volume_24h,
                    "change_pct": change_pct,
                    "abs_change": abs_change,
                    "high_24h": high_24h,
                    "low_24h": low_24h,
                    "open_interest": open_interest,
                    "score": score,
                    "direction": "long" if change_pct > 0 else "short"
                })

            except (ValueError, TypeError):
                continue

        # Sort by score (best opportunities first)
        opportunities.sort(key=lambda x: x["score"], reverse=True)

        top = opportunities[:MAX_PAIRS_TO_SCAN]
        logger.info(f"🔍 Scanned {len(tickers)} pairs → {len(opportunities)} qualified → top {len(top)} selected")

        if top:
            logger.info("Top opportunities:")
            for o in top[:5]:
                logger.info(f"  {o['symbol']} | Vol: ${o['volume_24h']:,.0f} | Change: {o['change_pct']:+.2f}% | Score: {o['score']:.2f}")

        return top

    def _score_opportunity(self, volume_24h: float, change_pct: float,
                            abs_change: float, open_interest: float,
                            high_24h: float, low_24h: float, price: float) -> float:
        """
        Score an opportunity 0-100
        Weights: volume (40%) + momentum (40%) + range (20%)
        """
        import math

        # Volume score (log scale, caps at 1B)
        vol_score = min(math.log10(max(volume_24h, 1)) / math.log10(1_000_000_000), 1.0) * 40

        # Momentum score (more movement = better, caps at 20%)
        momentum_score = min(abs_change / 20, 1.0) * 40

        # Range score (tight range = breakout potential)
        if high_24h > 0 and low_24h > 0 and price > 0:
            range_pct = (high_24h - low_24h) / price * 100
            range_score = min(range_pct / 10, 1.0) * 20
        else:
            range_score = 0

        return vol_score + momentum_score + range_score

    async def get_surging_pairs(self) -> List[Dict]:
        """
        Find pairs with RAPIDLY increasing volume — early movers
        These are the gems: token starts pumping before everyone notices
        """
        opportunities = await self.scan_market()
        # Focus on highest momentum with good volume
        surging = [o for o in opportunities if o["abs_change"] >= 3.0 and o["volume_24h"] >= MIN_VOLUME_USDT_24H * 2]
        return surging[:10]
