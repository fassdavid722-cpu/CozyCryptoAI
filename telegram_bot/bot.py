"""
CozyCryptoAI - Telegram Interface
Chat with the AI, get trade notifications, control the bot
"""

import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("TelegramBot")


class TelegramBot:
    def __init__(self, brain=None, engine=None):
        self.brain = brain
        self.engine = engine
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.chat_id = TELEGRAM_CHAT_ID

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Set brain's notify callback to this bot
        if brain:
            brain.set_notify_callback(self.send_notification)

    async def send_notification(self, message: str):
        """Called by brain when a trade happens"""
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages — route to AI brain"""
        user_msg = update.message.text
        logger.info(f"User: {user_msg}")

        # Only respond to authorized user
        if self.chat_id and str(update.effective_chat.id) != str(self.chat_id):
            await update.message.reply_text("Unauthorized.")
            return

        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="typing"
            )
            reply = await self.brain.chat(user_msg, engine=self.engine)
            await update.message.reply_text(reply)
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            await update.message.reply_text("Something went wrong on my end. Give me a sec.")

    # ── Commands ──────────────────────────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "🤖 *CozyCryptoAI Online*\n\n"
            "I'm your aggressive scalping AI. I trade BTC, ETH, SOL, BNB, XRP on Bitget.\n\n"
            "Just talk to me naturally. Ask me why I made a trade, what I'm watching, "
            "or tell me to pause. I'll keep you updated on every move.\n\n"
            "Commands:\n"
            "/status - Current trading status\n"
            "/positions - Open positions\n"
            "/balance - Account balance\n"
            "/pnl - Total P&L\n"
            "/pause - Pause trading\n"
            "/resume - Resume trading"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            await update.message.reply_text("Engine not connected.")
            return
        status = await self.engine.get_status()
        state = "⏸ PAUSED" if status["paused"] else "🟢 ACTIVE"
        msg = (
            f"*Status:* {state}\n"
            f"*Balance:* ${status['balance_usdt']['available']:.2f} USDT available\n"
            f"*Open Positions:* {len(status['open_positions'])}\n"
            f"*Total PnL:* {status['total_pnl']:+.4f} USDT\n"
            f"*Watching:* {', '.join(status['watching'])}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            await update.message.reply_text("Engine not connected.")
            return
        positions = self.engine.open_positions
        if not positions:
            await update.message.reply_text("No open positions right now.")
            return
        lines = ["*Open Positions:*\n"]
        for symbol, pos in positions.items():
            lines.append(
                f"📈 *{symbol}*\n"
                f"  Entry: ${pos['entry_price']:.4f}\n"
                f"  SL: ${pos['stop_loss']:.4f} | TP: ${pos['take_profit']:.4f}\n"
                f"  Reason: {pos['reason']}\n"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            await update.message.reply_text("Engine not connected.")
            return
        pnl = self.engine.pnl_total
        emoji = "✅" if pnl >= 0 else "❌"
        await update.message.reply_text(f"{emoji} *Total PnL:* {pnl:+.4f} USDT", parse_mode="Markdown")

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            await update.message.reply_text("Engine not connected.")
            return
        balance = await self.engine.client.get_account_balance()
        msg = (
            f"💰 *Balance*\n"
            f"Available: ${balance['available']:.2f} USDT\n"
            f"Frozen: ${balance['frozen']:.2f} USDT\n"
            f"Total: ${balance['total']:.2f} USDT"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.engine:
            self.engine.pause()
        await update.message.reply_text("⏸ Trading paused. I'll hold positions but won't open new ones.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.engine:
            self.engine.resume()
        await update.message.reply_text("🟢 Back in action. Scanning for setups.")

    async def run(self):
        logger.info("Telegram bot starting...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram bot polling...")
        # Keep running
        import asyncio
        while True:
            await asyncio.sleep(3600)
