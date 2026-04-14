"""
CozyCryptoAI Configuration — Futures Edition
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

# Groq (AI Brain)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Futures Trading Config
TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
LEVERAGE = 10                    # 10x leverage (aggressive but controlled)
MARGIN_MODE = "crossed"          # Cross margin (can change to 'fixed' for isolated)
MAX_POSITION_SIZE_PERCENT = 10   # Max 10% of account per trade (before leverage)
MAX_OPEN_POSITIONS = 3           # Max 3 concurrent futures positions (risk control)
STOP_LOSS_PERCENT = 1.5          # 1.5% stop loss
TAKE_PROFIT_PERCENT = 3.0        # 3% take profit (2:1 R/R)
SCALP_INTERVAL_SECONDS = 60      # Scan every 60 seconds

# AI Personality
AI_NAME = "CozyCryptoAI"
AI_PERSONALITY = "aggressive_scalper"
AI_RISK_LEVEL = "aggressive"
