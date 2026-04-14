"""
Bitget API Client
Handles authentication and all API calls
"""

import hmac
import hashlib
import base64
import time
import json
import aiohttp
import logging
from config import BITGET_API_KEY, BITGET_SECRET_KEY, BITGET_PASSPHRASE, BITGET_BASE_URL

logger = logging.getLogger("BitgetClient")


class BitgetClient:
    def __init__(self):
        self.api_key = BITGET_API_KEY
        self.secret_key = BITGET_SECRET_KEY
        self.passphrase = BITGET_PASSPHRASE
        self.base_url = BITGET_BASE_URL
        self.session = None

    async def _get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = f"{timestamp}{method.upper()}{path}{body}"
        mac = hmac.new(
            self.secret_key.encode("utf-8"),
            message.encode("utf-8"),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time() * 1000))
        sign = self._sign(timestamp, method, path, body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": sign,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US"
        }

    async def get(self, path: str, params: dict = None) -> dict:
        session = await self._get_session()
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        full_path = path + query
        headers = self._headers("GET", full_path)
        async with session.get(f"{self.base_url}{full_path}", headers=headers) as resp:
            data = await resp.json()
            if data.get("code") != "00000":
                logger.error(f"Bitget API error: {data}")
            return data

    async def post(self, path: str, body: dict) -> dict:
        session = await self._get_session()
        body_str = json.dumps(body)
        headers = self._headers("POST", path, body_str)
        async with session.post(f"{self.base_url}{path}", headers=headers, data=body_str) as resp:
            data = await resp.json()
            if data.get("code") != "00000":
                logger.error(f"Bitget API error: {data}")
            return data

    # ── Account ──────────────────────────────────────────────────────────────

    async def get_account_balance(self) -> dict:
        """Get USDT spot balance"""
        resp = await self.get("/api/v2/spot/account/assets")
        assets = resp.get("data", [])
        for asset in assets:
            if asset.get("coin") == "USDT":
                return {
                    "available": float(asset.get("available", 0)),
                    "frozen": float(asset.get("frozen", 0)),
                    "total": float(asset.get("available", 0)) + float(asset.get("frozen", 0))
                }
        return {"available": 0, "frozen": 0, "total": 0}

    async def get_all_balances(self) -> list:
        """Get all asset balances"""
        resp = await self.get("/api/v2/spot/account/assets")
        return resp.get("data", [])

    async def get_open_orders(self, symbol: str = None) -> list:
        params = {}
        if symbol:
            params["symbol"] = symbol
        resp = await self.get("/api/v2/spot/trade/unfilled-orders", params)
        return resp.get("data", {}).get("entrustedList", [])

    async def get_positions(self) -> list:
        """Get current open positions"""
        balances = await self.get_all_balances()
        positions = []
        for b in balances:
            if b.get("coin") != "USDT" and float(b.get("available", 0)) > 0:
                positions.append(b)
        return positions

    # ── Market Data ──────────────────────────────────────────────────────────

    async def get_ticker(self, symbol: str) -> dict:
        resp = await self.get("/api/v2/spot/market/tickers", {"symbol": symbol})
        data = resp.get("data", [])
        return data[0] if data else {}

    async def get_candles(self, symbol: str, granularity: str = "1m", limit: int = 100) -> list:
        """Get OHLCV candles"""
        resp = await self.get("/api/v2/spot/market/candles", {
            "symbol": symbol,
            "granularity": granularity,
            "limit": str(limit)
        })
        return resp.get("data", [])

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        resp = await self.get("/api/v2/spot/market/orderbook", {
            "symbol": symbol,
            "limit": str(limit)
        })
        return resp.get("data", {})

    # ── Trading ──────────────────────────────────────────────────────────────

    async def place_order(self, symbol: str, side: str, order_type: str,
                          size: str, price: str = None) -> dict:
        """
        Place a spot order
        side: 'buy' | 'sell'
        order_type: 'limit' | 'market'
        """
        body = {
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "size": size,
            "force": "gtc"
        }
        if price and order_type == "limit":
            body["price"] = price

        logger.info(f"Placing order: {body}")
        return await self.post("/api/v2/spot/trade/place-order", body)

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        return await self.post("/api/v2/spot/trade/cancel-order", {
            "symbol": symbol,
            "orderId": order_id
        })

    async def cancel_all_orders(self, symbol: str) -> dict:
        return await self.post("/api/v2/spot/trade/cancel-symbol-order", {
            "symbol": symbol
        })

    async def close(self):
        if self.session:
            await self.session.close()
