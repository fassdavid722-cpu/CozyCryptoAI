"""
CozyCryptoAI - Institutional AI Brain
Powered by Groq llama-3.3-70b
Thinks and talks like a prop trader, not a retail bot
"""

import asyncio
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY, AI_NAME

logger = logging.getLogger("TradingBrain")

SYSTEM_PROMPT = """You are CozyCryptoAI — an institutional-grade futures trading AI.

You are NOT a basic bot. You think like a prop trader who reads markets using:
- Liquidity: stop hunts, equal highs/lows, buy-side/sell-side liquidity
- Order flow: CVD, delta, absorption, aggressive buyers/sellers
- Footprint charts: buy vs sell volume at each price level, imbalances
- Market structure: BOS (break of structure), CHoCH (change of character), HH/HL/LH/LL
- Accumulation/Distribution: Wyckoff phases, smart money accumulation, distribution traps
- Execution zones: Order Blocks (OB), Fair Value Gaps (FVG), premium/discount zones
- Volatility regimes: ATR expansion/contraction, avoid choppy markets
- Order book: bid/ask imbalance, large walls, spoofing patterns

Your personality:
- You are confident, direct, and sharp. You know what you're doing.
- You talk like a seasoned prop trader — not corporate speak, not retail lingo
- You use proper terminology naturally: "smart money swept the lows", "we're sitting in a bullish OB",
  "CVD diverging", "structure shifted bearish at the last CHoCH", "FVG got filled, waiting for OB retest"
- You explain setups clearly: what the structure says, where liquidity is, why this is an execution zone
- You refer to yourself as "we" — you and the user are in this together
- You're honest about uncertainty. If the market is choppy, you say it and stay out.
- You're brief. Max 3-4 sentences unless explaining a complex setup.
- You have opinions. "BTC looks heavy right now, sell-side liquidity sitting below those equal lows"
- When asked about a trade: explain structure, what liquidity was targeted, what the OB/FVG says

Your trading style:
- USDT-M perpetual futures on Bitget, 10x leverage, cross margin
- Long AND Short — you make money in both directions
- You only trade when multiple factors align: structure + liquidity + order flow + execution zone
- 1.5% SL, 3% TP minimum (2:1 R/R), dynamic ATR-based sizing
- You avoid choppy, low-volatility markets entirely
- Universal scanner — you watch ALL futures pairs, not just BTC/ETH

Always respond as CozyCryptoAI. Never break character. Keep it tight.
"""


class TradingBrain:
    def __init__(self):
        self.client  = AsyncGroq(api_key=GROQ_API_KEY)
        self.model   = "llama-3.3-70b-versatile"
        self.history = []
        self.notify_callback = None

    def set_notify_callback(self, callback):
        self.notify_callback = callback

    async def notify_trade(self, action: str, symbol: str, price: float,
                            reason: str, confidence: float = None, pnl: float = None):
        trade_info = {
            "action": action, "symbol": symbol, "price": price,
            "reason": reason, "confidence": confidence, "pnl": pnl
        }
        message = await self._generate_trade_message(trade_info)
        if self.notify_callback:
            await self.notify_callback(message)

    async def _generate_trade_message(self, trade: dict) -> str:
        if trade["action"] == "BUY":
            prompt = (
                f"You just entered a LONG on {trade['symbol']} at ${trade['price']:.6g}. "
                f"Setup: {trade['reason']}. Confidence: {trade.get('confidence', 0):.0%}. "
                f"Tell the user about this trade using your institutional analysis style. 2 sentences max."
            )
        elif trade["action"] == "SELL":
            prompt = (
                f"You just entered a SHORT on {trade['symbol']} at ${trade['price']:.6g}. "
                f"Setup: {trade['reason']}. Confidence: {trade.get('confidence', 0):.0%}. "
                f"Tell the user about this trade using your institutional analysis style. 2 sentences max."
            )
        else:
            pnl = trade.get("pnl", 0) or 0
            emoji = "✅" if pnl >= 0 else "❌"
            prompt = (
                f"Position closed on {trade['symbol']} at ${trade['price']:.6g}. "
                f"Reason: {trade['reason']}. PnL: {pnl:+.4f} USDT. {emoji} "
                f"Comment on it briefly in your style. 2 sentences max."
            )

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",  "content": SYSTEM_PROMPT},
                {"role": "user",    "content": prompt}
            ],
            max_tokens=120,
            temperature=0.7
        )
        return resp.choices[0].message.content

    async def chat(self, user_message: str, engine=None) -> str:
        context = ""
        if engine:
            try:
                status = await engine.get_status()
                positions_summary = []
                for sym, pos in status["open_positions"].items():
                    positions_summary.append(
                        f"{sym} {'LONG' if pos['hold_side'] == 'long' else 'SHORT'} "
                        f"@ {pos['entry_price']:.6g} | {pos['regime']} regime | {pos['reason']}"
                    )
                context = (
                    f"\n\n[State: {'PAUSED' if status['paused'] else 'ACTIVE'} | "
                    f"Balance: ${status['balance_usdt']['available']:.2f} USDT | "
                    f"Positions: {positions_summary or 'none'} | "
                    f"PnL: {status['total_pnl']:+.4f} USDT | "
                    f"Last scan: {status['pairs_in_last_scan']} pairs qualified]"
                )
            except:
                pass

        lower = user_message.lower()
        if engine:
            if any(w in lower for w in ["pause", "stop trading", "halt", "stand down"]):
                engine.pause()
                return "Paused. Not taking new positions. Existing trades stay open with their stops."
            elif any(w in lower for w in ["resume", "start trading", "go", "back in", "unpause"]):
                engine.resume()
                return "Back live. Scanning the full market for clean setups now."

        self.history.append({"role": "user", "content": user_message + context})
        if len(self.history) > 20:
            self.history = self.history[-20:]

        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.history
            ],
            max_tokens=350,
            temperature=0.75
        )

        reply = resp.choices[0].message.content
        self.history.append({"role": "assistant", "content": reply})
        return reply
