"""
Bitget Futures API Client (USDT-M Perpetuals)
Handles authentication and all futures API calls
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
        self.product_type = "USDT-FUTURES"   # USDT-M perpetual contracts

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

    # ── Account ───────────────────────────────────────────────────────────────

    async def get_account_balance(self) -> dict:
        """Get USDT futures account balance"""
        resp = await self.get("/api/v2/mix/account/account", {
            "symbol": "BTCUSDT",
            "productType": self.product_type,
            "marginCoin": "USDT"
        })
        data = resp.get("data", {})
        available = float(data.get("available", 0))
        frozen = float(data.get("frozen", 0))
        equity = float(data.get("accountEquity", 0))
        return {
            "available": available,
            "frozen": frozen,
            "total": equity
        }

    async def get_all_positions(self) -> list:
        """Get all open futures positions"""
        resp = await self.get("/api/v2/mix/position/all-position", {
            "productType": self.product_type,
            "marginCoin": "USDT"
        })
        return resp.get("data", [])

    async def get_open_orders(self, symbol: str = None) -> list:
        params = {"productType": self.product_type}
        if symbol:
            params["symbol"] = symbol
        resp = await self.get("/api/v2/mix/order/orders-pending", params)
        return resp.get("data", {}).get("entrustedList", [])

    # ── Leverage ──────────────────────────────────────────────────────────────

    async def set_leverage(self, symbol: str, leverage: int, hold_side: str = "long") -> dict:
        """Set leverage for a symbol"""
        return await self.post("/api/v2/mix/account/set-leverage", {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": "USDT",
            "leverage": str(leverage),
            "holdSide": hold_side
        })

    async def set_margin_mode(self, symbol: str, mode: str = "crossed") -> dict:
        """Set margin mode: 'crossed' (cross) or 'fixed' (isolated)"""
        return await self.post("/api/v2/mix/account/set-margin-mode", {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": "USDT",
            "marginMode": mode
        })

    # ── Market Data ───────────────────────────────────────────────────────────

    async def get_ticker(self, symbol: str) -> dict:
        resp = await self.get("/api/v2/mix/market/ticker", {
            "symbol": symbol,
            "productType": self.product_type
        })
        data = resp.get("data", [])
        return data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}

    async def get_candles(self, symbol: str, granularity: str = "1m", limit: int = 100) -> list:
        """Get OHLCV candles for futures"""
        resp = await self.get("/api/v2/mix/market/candles", {
            "symbol": symbol,
            "productType": self.product_type,
            "granularity": granularity,
            "limit": str(limit)
        })
        return resp.get("data", [])

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        resp = await self.get("/api/v2/mix/market/merge-depth", {
            "symbol": symbol,
            "productType": self.product_type,
            "limit": str(limit)
        })
        return resp.get("data", {})

    # ── Trading ───────────────────────────────────────────────────────────────

    async def place_order(self, symbol: str, side: str, trade_side: str,
                          order_type: str, size: str, price: str = None,
                          reduce_only: bool = False) -> dict:
        """
        Place a futures order
        side: 'buy' | 'sell'
        trade_side: 'open' | 'close'
        order_type: 'limit' | 'market'
        size: number of contracts
        """
        body = {
            "symbol": symbol,
            "productType": self.product_type,
            "marginMode": "crossed",
            "marginCoin": "USDT",
            "size": size,
            "side": side,
            "tradeSide": trade_side,
            "orderType": order_type,
            "force": "gtc"
        }
        if price and order_type == "limit":
            body["price"] = price
        if reduce_only:
            body["reduceOnly"] = "YES"

        logger.info(f"Placing futures order: {body}")
        return await self.post("/api/v2/mix/order/place-order", body)

    async def place_stop_loss(self, symbol: str, hold_side: str,
                               trigger_price: str, size: str) -> dict:
        """Place a stop loss order"""
        return await self.post("/api/v2/mix/order/place-tpsl-order", {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": "USDT",
            "planType": "loss_plan",
            "triggerPrice": trigger_price,
            "triggerType": "mark_price",
            "executePrice": "0",
            "holdSide": hold_side,
            "size": size
        })

    async def place_take_profit(self, symbol: str, hold_side: str,
                                 trigger_price: str, size: str) -> dict:
        """Place a take profit order"""
        return await self.post("/api/v2/mix/order/place-tpsl-order", {
            "symbol": symbol,
            "productType": self.product_type,
            "marginCoin": "USDT",
            "planType": "profit_plan",
            "triggerPrice": trigger_price,
            "triggerType": "mark_price",
            "executePrice": "0",
            "holdSide": hold_side,
            "size": size
        })

    async def cancel_order(self, symbol: str, order_id: str) -> dict:
        return await self.post("/api/v2/mix/order/cancel-order", {
            "symbol": symbol,
            "productType": self.product_type,
            "orderId": order_id
        })

    async def close_position(self, symbol: str, hold_side: str, size: str) -> dict:
        """Close a futures position"""
        side = "sell" if hold_side == "long" else "buy"
        return await self.place_order(
            symbol=symbol,
            side=side,
            trade_side="close",
            order_type="market",
            size=size,
            reduce_only=True
        )

    async def close(self):
        if self.session:
            await self.session.close()
