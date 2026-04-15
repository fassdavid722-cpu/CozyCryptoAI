# 🤖 CozyCryptoAI

An aggressive AI futures scalper that trades USDT-M perpetual contracts on Bitget and chats via Telegram. This is NOT a bot — it's a trading AI with its own personality, reasoning, and decision-making.

## What it does

- **Trades futures autonomously** on Bitget USDT-M perpetuals (BTC, ETH, SOL, BNB, XRP)
- **Goes Long AND Short** — profits in both bull and bear markets
- **10x leverage** by default — aggressive account growth focused
- **Chats with you** on Telegram like a real trading partner
- **Explains every trade** — why it entered, direction, what the setup was
- **Responds to commands** — pause it, ask for status, check PnL, debate strategy
- **Auto Stop Loss & Take Profit** — placed on Bitget immediately after every entry

## Strategy

- **Indicators:** EMA 9/21 crossover + RSI 14 + Volume spike detection + Breakout from 20-bar high/low
- **Direction:** Long on bullish signals, Short on bearish signals
- **Risk:** 1.5% stop loss, 3% take profit (2:1 R/R)
- **Leverage:** 10x cross margin (configurable)
- **Position size:** 5-10% of account per trade (pre-leverage)
- **Max open positions:** 3 concurrent futures positions
- **Scan interval:** Every 60 seconds

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/fassdavid722-cpu/CozyCryptoAI
cd CozyCryptoAI
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your keys
```

You need:
- **Bitget API keys** — from Bitget > Profile > API Management (**Futures Read + Futures Trade** permissions)
- **Telegram Bot Token** — create a bot via [@BotFather](https://t.me/BotFather) on Telegram
- **Telegram Chat ID** — your personal Telegram ID (message [@userinfobot](https://t.me/userinfobot))
- **Groq API Key** — from [console.groq.com](https://console.groq.com) (free)

### 4. Run
```bash
python main.py
```

## Talking to it

Once running, open your Telegram bot and just talk:

- *"What are you watching right now?"*
- *"Why did you long SOL?"*
- *"Are you short anything?"*
- *"Be more aggressive today"*
- *"Pause trading"*
- *"What's my PnL?"*
- *"How's BTC looking?"*
- *"Close everything"*

Commands:
| Command | Description |
|---------|-------------|
| `/start` | Introduction + command list |
| `/status` | Trading status + balance + leverage |
| `/positions` | Current open futures positions |
| `/balance` | USDT futures account balance |
| `/pnl` | Total realized PnL |
| `/pause` | Pause new trades |
| `/resume` | Resume trading |

## Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `LEVERAGE` | 10 | Leverage multiplier |
| `MARGIN_MODE` | crossed | `crossed` or `fixed` (isolated) |
| `MAX_OPEN_POSITIONS` | 3 | Max concurrent futures positions |
| `STOP_LOSS_PERCENT` | 1.5% | Stop loss per trade |
| `TAKE_PROFIT_PERCENT` | 3.0% | Take profit per trade |
| `SCALP_INTERVAL_SECONDS` | 60 | How often to scan markets |

## Deployment (Free VPS)

**Recommended: Oracle Cloud Free Tier** (free forever, no expiry)
- Sign up at [cloud.oracle.com](https://cloud.oracle.com)
- Create a free AMD VM (1GB RAM) — more than enough
- SSH in and run:

```bash
# Install Python
sudo apt update && sudo apt install python3 python3-pip -y

# Clone and setup
git clone https://github.com/fassdavid722-cpu/CozyCryptoAI
cd CozyCryptoAI
pip install -r requirements.txt
cp .env.example .env
nano .env  # Add your keys

# Run forever with screen
screen -S cozycryptoai
python main.py
# Press Ctrl+A then D to detach
```

## ⚠️ Risk Warning

This AI trades real leveraged futures. Leverage amplifies both gains AND losses. Start with small capital while observing its behavior. You can adjust leverage in `config.py`. Always trade responsibly.

---
Built by CozyCrypto 🚀
