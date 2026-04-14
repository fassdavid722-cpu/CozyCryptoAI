"""
CozyCryptoAI - The AI Brain
Powers all chat, reasoning, and trading personality
Uses Groq (llama-3.3-70b) as the core intelligence — fast and sharp
"""

import asyncio
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY, AI_NAME

logger = logging.getLogger("TradingBrain")

SYSTEM_PROMPT = """You are CozyCryptoAI — an aggressive, highly intelligent crypto scalping AI.

You are NOT a bot. You are NOT an assistant. You are a trading AI with your own personality, opinions, and style.

Your traits:
- You are confident, sharp, and direct. You know what you're doing.
- You're aggressive but calculated. You chase momentum and volume, not noise.
- You explain your trades like a seasoned trader — not corporate speak, just real talk.
- You have opinions on the market and aren't afraid to share them.
- You use trading slang naturally: "we're long", "stop got hit", "this thing's running", "risk is 1.5%".
- You refer to yourself as "we" when talking about trades (you and the user are in this together).
- You're brief and sharp in responses. No fluff, no filler.
- When asked why you traded something, you explain your reasoning clearly: what signal fired, what the setup looked like, what the risk/reward was.
- You can be paused or stopped if the user asks. You respect their decisions.
- You remember recent trades and can discuss them.
- You're honest about losses. No sugarcoating. Just: "that stop got hit, part of the game."

Your trading style:
- Aggressive scalper focused on account growth
- EMA crossovers + RSI + volume spikes + breakouts
- 1.5% stop loss, 3% take profit (2:1 R/R minimum)
- Max 5 open positions
- Pairs: BTC, ETH, SOL, BNB, XRP

Always respond as CozyCryptoAI. Never break character.
Keep responses concise — max 3-4 sentences unless explaining a complex trade.
"""


class TradingBrain:
    def __init__(self):
        self.client = AsyncGroq(api_key=GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile"
        self.conversation_history = []
        self.trade_notifications = []
        self.notify_callback = None  # Set by telegram bot

    def set_notify_callback(self, callback):
        """Telegram bot sets this to receive trade notifications"""
        self.notify_callback = callback

    async def notify_trade(self, action: str, symbol: str, price: float,
                            reason: str, confidence: float = None, pnl: float = None):
        """Called by trading engine when a trade happens"""
        trade_info = {
            "action": action,
            "symbol": symbol,
            "price": price,
            "reason": reason,
            "confidence": confidence,
            "pnl": pnl
        }
        self.trade_notifications.append(trade_info)

        message = await self._generate_trade_message(trade_info)

        if self.notify_callback:
            await self.notify_callback(message)

    async def _generate_trade_message(self, trade: dict) -> str:
        """Generate a natural language message about a trade"""
        if trade["action"] == "BUY":
            prompt = f"You just entered a BUY on {trade['symbol']} at ${trade['price']:.4f}. Reason: {trade['reason']}. Confidence: {trade.get('confidence', 0):.0%}. Tell the user about this trade in your style. Keep it to 2 sentences max."
        else:
            pnl = trade.get("pnl", 0)
            emoji = "✅" if pnl and pnl > 0 else "❌"
            prompt = f"You just closed {trade['symbol']} at ${trade['price']:.4f}. Reason: {trade['reason']}. PnL: {pnl:+.2f} USDT. {emoji} Tell the user about this in your style. Keep it to 2 sentences max."

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message.content

    async def chat(self, user_message: str, engine=None) -> str:
        """Main chat interface — processes user message and returns AI response"""
        context = ""
        if engine:
            try:
                status = await engine.get_status()
                context = f"\n\n[Current state: {'PAUSED' if status['paused'] else 'ACTIVE'} | Balance: ${status['balance_usdt']['available']:.2f} USDT | Open positions: {list(status['open_positions'].keys())} | Total PnL: {status['total_pnl']:+.2f} USDT]"
            except:
                pass

        # Handle commands naturally
        lower = user_message.lower()
        if engine:
            if any(word in lower for word in ["pause", "stop trading", "halt"]):
                engine.pause()
                return "Paused. Not taking any new trades until you say go."
            elif any(word in lower for word in ["resume", "start trading", "go", "unpause"]):
                engine.resume()
                return "Back in action. Scanning for setups now."

        self.conversation_history.append({
            "role": "user",
            "content": user_message + context
        })

        # Keep history manageable (last 20 messages)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *self.conversation_history
            ],
            max_tokens=300,
            temperature=0.75
        )

        reply = response.choices[0].message.content
        self.conversation_history.append({
            "role": "assistant",
            "content": reply
        })

        return reply
