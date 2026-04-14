# 🤖 CozyCryptoAI

An aggressive AI scalper that trades on Bitget and chats via Telegram. This is NOT a bot — it's a trading AI with its own personality, reasoning, and decision-making.

## What it does

- **Trades autonomously** on Bitget spot market (BTC, ETH, SOL, BNB, XRP)
- **Chats with you** on Telegram like a real trading partner
- **Explains every trade** — why it bought, why it sold, what the setup was
- **Responds to commands** — pause it, ask for status, check PnL, debate strategy
- **Aggressive scalping** — EMA crossovers, volume spikes, breakout detection

## Strategy

- **Indicators:** EMA 9/21 crossover + RSI 14 + Volume spike detection + Breakout from 20-bar high/low
- **Risk:** 1.5% stop loss, 3% take profit (2:1 R/R)
- **Position size:** 5-8% of portfolio per trade
- **Max open positions:** 5
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
- **Bitget API keys** — from Bitget > Profile > API Management (Read + Trade permissions)
- **Telegram Bot Token** — create a bot via [@BotFather](https://t.me/BotFather) on Telegram
- **Telegram Chat ID** — your personal Telegram ID (message [@userinfobot](https://t.me/userinfobot))
- **OpenAI API Key** — from [platform.openai.com](https://platform.openai.com)

### 4. Run
```bash
python main.py
```

## Talking to it

Once running, open your Telegram bot and just talk:

- *"What are you watching right now?"*
- *"Why did you buy SOL?"*
- *"Be more conservative today"*
- *"Pause trading"*
- *"What's my PnL?"*
- *"How's BTC looking?"*

Commands:
| Command | Description |
|---------|-------------|
| `/start` | Introduction + command list |
| `/status` | Trading status + balance |
| `/positions` | Current open positions |
| `/balance` | USDT balance breakdown |
| `/pnl` | Total realized PnL |
| `/pause` | Pause new trades |
| `/resume` | Resume trading |

## Deployment

Run it on any VPS (DigitalOcean, AWS, etc.):

```bash
# Using screen
screen -S cozycryptoai
python main.py

# Or using systemd / Docker (recommended for production)
```

## ⚠️ Risk Warning

This AI trades real money. Start with small amounts while you observe its behavior. Always set your own risk limits. Past performance does not guarantee future results.

---
Built by CozyCrypto 🚀
