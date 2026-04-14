"""
CozyCryptoAI Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Bitget API
BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BITGET_BASE_URL = "https://api.bitget.com"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# OpenAI (AI Brain)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Trading Config
TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
MAX_POSITION_SIZE_PERCENT = 10   # Max 10% of portfolio per trade
MAX_OPEN_POSITIONS = 5
STOP_LOSS_PERCENT = 1.5          # 1.5% stop loss
TAKE_PROFIT_PERCENT = 3.0        # 3% take profit (2:1 R/R)
SCALP_INTERVAL_SECONDS = 60      # Check markets every 60 seconds
MIN_VOLUME_USDT = 1_000_000      # Only trade pairs with >1M USDT volume

# AI Personality
AI_NAME = "CozyCryptoAI"
AI_PERSONALITY = "aggressive_scalper"
AI_RISK_LEVEL = "aggressive"
