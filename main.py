"""
CozyCryptoAI - Aggressive Scalping AI Trader
Trades on Bitget, chats via Telegram
"""

import asyncio
import logging
from trading.engine import TradingEngine
from telegram_bot.bot import TelegramBot
from ai.brain import TradingBrain

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("CozyCryptoAI")


async def main():
    logger.info("🚀 CozyCryptoAI starting up...")

    brain = TradingBrain()
    engine = TradingEngine(brain=brain)
    bot = TelegramBot(brain=brain, engine=engine)

    await asyncio.gather(
        engine.run(),
        bot.run()
    )


if __name__ == "__main__":
    asyncio.run(main())
