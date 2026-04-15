"""
CozyCryptoAI — Main Entry Point
Runs: FastAPI dashboard + Telegram bot + Trading engine — all concurrently
"""

import asyncio
import logging
import os
from trading.engine import TradingEngine
from ai.brain import TradingBrain
from telegram_bot.bot import TelegramBot
from api.server import create_app
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s"
)
logger = logging.getLogger("Main")


async def main():
    logger.info("🚀 CozyCryptoAI starting up...")

    # Init components
    brain  = TradingBrain()
    engine = TradingEngine(brain=brain)
    tg_bot = TelegramBot(brain=brain, engine=engine)

    # FastAPI app
    app = create_app(engine=engine, brain=brain)
    port = int(os.getenv("PORT", 8080))

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning"
    )
    server = uvicorn.Server(config)

    logger.info(f"Dashboard live on port {port}")

    # Run all three concurrently
    await asyncio.gather(
        server.serve(),
        engine.run(),
        tg_bot.run()
    )


if __name__ == "__main__":
    asyncio.run(main())
