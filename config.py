"""
CozyCryptoAI Configuration — Futures Edition (Universal Scanner)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Credentials ───────────────────────────────────────────────────────────

BITGET_API_KEY = os.getenv("BITGET_API_KEY")
BITGET_SECRET_KEY = os.getenv("BITGET_SECRET_KEY")
BITGET_PASSPHRASE = os.getenv("BITGET_PASSPHRASE")
BITGET_BASE_URL = "https://api.bitget.com"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Universal Scanner Settings ────────────────────────────────────────────────

# Minimum 24h USDT volume to qualify for scanning
# $500K = catches mid-cap movers, $1M = only liquid tokens
MIN_VOLUME_USDT_24H = 500_000          # $500K minimum volume

# Minimum absolute 24h price change % to qualify (momentum filter)
MIN_PRICE_CHANGE_PERCENT = 1.5         # At least 1.5% movement in 24h

# How many top-scored pairs to actually analyze with indicators
MAX_PAIRS_TO_SCAN = 20                 # Top 20 opportunities per scan cycle

# Pairs to always skip (e.g. stablecoins, broken contracts)
BLACKLISTED_PAIRS = [
    "USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDTUSDT",
    "DAIUSDT", "FRAXUSDT", "USTCUSDT"
]

# ── Futures Trading Config ────────────────────────────────────────────────────

LEVERAGE = 10                          # 10x leverage
MARGIN_MODE = "crossed"                # 'crossed' or 'fixed' (isolated)
MAX_POSITION_SIZE_PERCENT = 10         # Max 10% of account per trade (pre-leverage)
MAX_OPEN_POSITIONS = 3                 # Max concurrent futures positions
STOP_LOSS_PERCENT = 1.5                # 1.5% stop loss
TAKE_PROFIT_PERCENT = 3.0              # 3% take profit (2:1 R/R)
SCALP_INTERVAL_SECONDS = 60            # Full market scan every 60 seconds

# ── AI Config ─────────────────────────────────────────────────────────────────

AI_NAME = "CozyCryptoAI"
AI_PERSONALITY = "aggressive_scalper"
AI_RISK_LEVEL = "aggressive"
