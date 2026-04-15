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
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LEVERAGE, MARGIN_MODE

logger = logging.getLogger("TelegramBot")


class TelegramBot:
    def __init__(self, brain=None, engine=None):
        self.brain = brain
        self.engine = engine
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        self.chat_id = TELEGRAM_CHAT_ID

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("pause", self.cmd_pause))
        self.app.add_handler(CommandHandler("resume", self.cmd_resume))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self.app.add_handler(CommandHandler("balance", self.cmd_balance))
        self.app.add_handler(CommandHandler("closeall", self.cmd_closeall))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        if brain:
            brain.set_notify_callback(self.send_notification)

    async def send_notification(self, message: str):
        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Notification error: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.chat_id and str(update.effective_chat.id) != str(self.chat_id):
            await update.message.reply_text("Unauthorized.")
            return
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            reply = await self.brain.chat(update.message.text, engine=self.engine)
            await update.message.reply_text(reply)
        except Exception as e:
            logger.error(f"Message handler error: {e}")
            await update.message.reply_text("Error on my end. Give me a sec.")

    # ── Commands ──────────────────────────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "⚡ *CozyCryptoAI — Futures Edition*\n\n"
            f"I trade USDT-M perpetual contracts on Bitget with *{LEVERAGE}x leverage* ({MARGIN_MODE} margin).\n"
            "I go *Long AND Short* — I make money in both directions.\n\n"
            "Just talk to me naturally. Ask why I traded something, what I'm watching, "
            "or tell me to pause. I'll notify you on every move.\n\n"
            "*Commands:*\n"
            "/status — Trading status + leverage + balance\n"
            "/positions — Open futures positions\n"
            "/balance — Futures account balance\n"
            "/pnl — Total realized PnL\n"
            "/pause — Pause trading\n"
            "/resume — Resume trading\n"
            "/closeall — Emergency close all positions"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            return
        status = await self.engine.get_status()
        state = "⏸ PAUSED" if status["paused"] else "🟢 ACTIVE"
        msg = (
            f"*Status:* {state}\n"
            f"*Leverage:* {status['leverage']}x {status['margin_mode']} margin\n"
            f"*Balance:* ${status['balance_usdt']['available']:.2f} USDT available\n"
            f"*Equity:* ${status['balance_usdt']['total']:.2f} USDT\n"
            f"*Open Positions:* {len(status['open_positions'])}/3\n"
            f"*Total PnL:* {status['total_pnl']:+.4f} USDT\n"
            f"*Watching:* {', '.join(status['watching'])}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            return
        positions = self.engine.open_positions
        if not positions:
            await update.message.reply_text("No open futures positions.")
            return
        lines = ["*Open Futures Positions:*\n"]
        for symbol, pos in positions.items():
            direction = "🟢 LONG" if pos["hold_side"] == "long" else "🔴 SHORT"
            lines.append(
                f"{direction} *{symbol}* ({pos['leverage']}x)\n"
                f"  Entry: ${pos['entry_price']:.4f}\n"
                f"  SL: ${pos['stop_loss']:.4f} | TP: ${pos['take_profit']:.4f}\n"
                f"  Size: {pos['contracts']} contracts\n"
                f"  Reason: {pos['reason']}\n"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            return
        pnl = self.engine.pnl_total
        emoji = "✅" if pnl >= 0 else "❌"
        await update.message.reply_text(f"{emoji} *Session PnL:* {pnl:+.4f} USDT", parse_mode="Markdown")

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            return
        balance = await self.engine.client.get_account_balance()
        msg = (
            f"💰 *Futures Account Balance*\n"
            f"Available: ${balance['available']:.2f} USDT\n"
            f"Frozen: ${balance['frozen']:.2f} USDT\n"
            f"Total Equity: ${balance['total']:.2f} USDT"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_closeall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.engine:
            return
        positions = list(self.engine.open_positions.items())
        if not positions:
            await update.message.reply_text("No open positions to close.")
            return
        await update.message.reply_text("⚠️ Closing all positions now...")
        for symbol, pos in positions:
            try:
                await self.engine.client.close_position(
                    symbol=symbol,
                    hold_side=pos["hold_side"],
                    size=str(pos["contracts"])
                )
                self.engine.open_positions.pop(symbol, None)
            except Exception as e:
                logger.error(f"Close error for {symbol}: {e}")
        await update.message.reply_text("✅ All positions closed.")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.engine:
            self.engine.pause()
        await update.message.reply_text("⏸ Trading paused. Holding existing positions but no new entries.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.engine:
            self.engine.resume()
        await update.message.reply_text("🟢 Back in action. Scanning futures markets now.")

    async def run(self):
        logger.info("Telegram bot starting...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram bot polling...")
        import asyncio
        while True:
            await asyncio.sleep(3600)
