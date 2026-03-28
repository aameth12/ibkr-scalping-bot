import logging
import telegram
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio
import datetime
import os

from src.utils import setup_logger

class TelegramBot:
    def __init__(self, config, ibkr_bot_instance=None, analytics_instance=None, scanner_instance=None, risk_manager_instance=None, journal_instance=None):
        self.logger = setup_logger("TelegramBot", "telegram_bot.log")
        self.bot_token = config["telegram_settings"]["bot_token"]
        self.chat_id = config["telegram_settings"]["chat_id"]
        self.watchlist = config["watchlist"]
        self.ibkr_bot = ibkr_bot_instance
        self.analytics = analytics_instance
        self.scanner = scanner_instance
        self.risk_manager = risk_manager_instance
        self.journal = journal_instance
        self.application = Application.builder().token(self.bot_token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("dashboard", self.dashboard_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("positions", self.positions_command))
        self.application.add_handler(CommandHandler("pnl", self.pnl_command))
        self.application.add_handler(CommandHandler("pause", self.pause_bot_command))
        self.application.add_handler(CommandHandler("resume", self.resume_bot_command))
        self.application.add_handler(CommandHandler("watchlist", self.watchlist_command))
        self.application.add_handler(CommandHandler("setparam", self.setparam_command))
        self.application.add_handler(CommandHandler("journal", self.journal_command))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        await update.message.reply_html(
            rf"Hi {user.mention_html()}! I am your IBKR Scalping Bot. Use /help to see available commands.",
            reply_markup=ForceReply(selective=True),
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "Available commands:\n"
            "/dashboard - Show bot dashboard with account summary and open positions\n"
            "/status - Get current bot status\n"
            "/positions - List all open positions\n"
            "/pnl - Show today\"s and total P&L\n"
            "/pause - Pause the trading bot\n"
            "/resume - Resume the trading bot\n"
            "/watchlist - View current watchlist\n"
            "/setparam <param_name> <value> - Change a bot parameter (e.g., /setparam risk_per_trade 0.03)\n"
            "/journal - Get the latest trade journal entries\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(help_text)

    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        
        status = self.ibkr_bot.get_status()
        dashboard_message = self._format_dashboard_message(status)
        await update.message.reply_text(dashboard_message)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        
        status = self.ibkr_bot.get_status()
        status_text = (
            f"Market: {status["market_status"]}\n"
            f"Mode: {status["mode"]} | Engine: {status["engine_status"]}\n"
            f"Account Balance: ${status["account_balance"]:.2f}\n"
            f"Total P&L (All Time): ${status["total_pnl"]:.2f}\n"
            f"Bot Paused: {self.risk_manager.bot_paused if self.risk_manager else False}"
        )
        await update.message.reply_text(status_text)

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        
        positions = self.ibkr_bot.get_open_positions()
        if not positions:
            await update.message.reply_text("No open positions.")
            return
        
        positions_text = "Open Positions:\n"
        for symbol, data in positions.items():
            positions_text += (
                f"  {data["contract"].secType} {symbol} x{data["position"]} @ ${data["average_cost"]:.2f}\n"
                f"    Now: ${data["market_price"]:.2f} | P&L: ${(data["market_price"] - data["average_cost"]) * data["position"]:.2f} ({(data["market_price"] / data["average_cost"] - 1) * 100:.2f}%)\n"
            )
        await update.message.reply_text(positions_text)

    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        
        pnl_summary = self.ibkr_bot.get_pnl_summary()
        pnl_text = (
            f"Today\"s P&L: ${pnl_summary["daily_pnl"]:.2f}\n"
            f"Total P&L (All Time): ${pnl_summary["total_pnl"]:.2f}"
        )
        await update.message.reply_text(pnl_text)

    async def pause_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.risk_manager:
            await update.message.reply_text("Risk Manager not initialized.")
            return
        self.risk_manager.pause_bot()
        await update.message.reply_text("Trading bot paused.")

    async def resume_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.risk_manager:
            await update.message.reply_text("Risk Manager not initialized.")
            return
        self.risk_manager.resume_bot()
        await update.message.reply_text("Trading bot resumed.")

    async def watchlist_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.watchlist:
            await update.message.reply_text("Watchlist is empty.")
            return
        watchlist_text = "Current Watchlist:\n" + ", ".join(self.watchlist)
        await update.message.reply_text(watchlist_text)

    async def setparam_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("Usage: /setparam <param_name> <value>")
            return
        
        param_name = args[0]
        param_value = args[1]

        # This is a simplified example. A robust implementation would need to
        # dynamically update the config object and potentially re-initialize modules.
        # For now, let\"s assume direct access to risk_manager parameters.
        try:
            if hasattr(self.risk_manager, param_name):
                # Attempt to convert value to appropriate type
                if param_name in ["risk_per_trade", "max_daily_loss_pct", "min_rr_ratio", "partial_profit_target_rr", "atr_multiplier_stop_loss", "trailing_stop_atr_multiplier", "trailing_stop_pct"]:
                    setattr(self.risk_manager, param_name, float(param_value))
                elif param_name in ["circuit_breaker_consecutive_losses"]:
                    setattr(self.risk_manager, param_name, int(param_value))
                else:
                    setattr(self.risk_manager, param_name, param_value)
                await update.message.reply_text(f"Parameter {param_name} set to {param_value}")
            else:
                await update.message.reply_text(f"Parameter {param_name} not found or not settable.")
        except ValueError:
            await update.message.reply_text(f"Invalid value for {param_name}. Please check the type.")
        except Exception as e:
            await update.message.reply_text(f"Error setting parameter: {e}")

    async def journal_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.journal:
            await update.message.reply_text("Trade journal not initialized.")
            return
        
        journal_df = self.journal.get_journal()
        if journal_df.empty:
            await update.message.reply_text("Trade journal is empty.")
            return
        
        # Send last 5 trades as a summary
        last_trades = journal_df.tail(5)[["timestamp", "symbol", "direction", "pnl", "rr_achieved", "exit_reason"]]
        journal_text = "*Latest Trade Journal Entries:*\n" + last_trades.to_markdown(index=False)
        await update.message.reply_text(journal_text, parse_mode="Markdown")

    async def send_new_position_notification(self, trade_info):
        # trade_info should contain all necessary details including R:R
        message = f"""
🟢 NEW POSITION
{trade_info["symbol"]} {trade_info["action"]} x{trade_info["quantity"]} @ ${trade_info["entry_price"]:.2f}
Stop:   ${trade_info["stop_loss_price"]:.2f}
Target: ${trade_info["target_price"]:.2f}
Partial Target: ${trade_info["partial_profit_price"]:.2f}
Calculated R:R {trade_info["rr_ratio"]:.2f}:1
"""
        await self.send_message(message)

    async def send_position_closed_notification(self, trade_info):
        # trade_info should contain all necessary details including PnL, R:R, and exit reason
        close_reason_emoji = {
            "Stopped out": "🛑",
            "Target hit": "🎯",
            "Trailing stop": "📈",
            "Partial profit": "💰",
            "Manual close": "✋",
            "Circuit breaker": "⚡",
            "Unknown": "❓"
        }.get(trade_info["exit_reason"], "❓")

        message = f"""
🔴 POSITION CLOSED
{trade_info["symbol"]} {trade_info["direction"]} x{trade_info["quantity"]}
Opened: ${trade_info["entry_price"]:.2f} → Closed: ${trade_info["exit_price"]:.2f}
P&L: ${trade_info["pnl"]:.2f} ({trade_info["pnl_pct"]:.2f}%)
Achieved R:R: {trade_info["rr_achieved"]:.2f}:1
{trade_info["exit_reason"]} {close_reason_emoji}
"""
        await self.send_message(message)

    async def send_circuit_breaker_alert(self, reason):
        message = f"⚡ CIRCUIT BREAKER TRIGGERED! ⚡\nReason: {reason}\nBot paused until next trading day."
        await self.send_message(message)

    async def send_morning_briefing(self):
        if not self.scanner:
            self.logger.warning("Scanner not initialized for morning briefing.")
            return
        movers = self.scanner.scan_pre_market()
        briefing_text = self.scanner.generate_morning_briefing(movers)
        await self.send_message(briefing_text, parse_mode="Markdown")

    async def send_daily_performance_summary(self):
        if not self.analytics or not self.journal:
            self.logger.warning("Analytics or Journal not initialized for daily summary.")
            return
        
        trade_log_df = self.journal.get_journal()
        current_date = datetime.datetime.now()
        summary_text = self.analytics.generate_daily_summary(trade_log_df, current_date)
        await self.send_message(summary_text, parse_mode="Markdown")

        # Generate and send equity curve chart
        equity_chart_path = os.path.join("data", "equity_curve.png")
        if self.analytics.generate_equity_curve_chart(equity_chart_path):
            await self.send_photo(equity_chart_path, caption="Daily Equity Curve")

    async def send_message(self, text, parse_mode=None):
        if self.chat_id:
            try:
                await self.application.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode)
            except telegram.error.TelegramError as e:
                self.logger.error(f"Error sending Telegram message: {e}")
        else:
            self.logger.warning("Telegram chat_id not set. Cannot send messages.")

    async def send_photo(self, photo_path, caption=None):
        if self.chat_id and os.path.exists(photo_path):
            try:
                with open(photo_path, "rb") as photo_file:
                    await self.application.bot.send_photo(chat_id=self.chat_id, photo=photo_file, caption=caption)
            except telegram.error.TelegramError as e:
                self.logger.error(f"Error sending Telegram photo: {e}")
        else:
            self.logger.warning(f"Telegram chat_id not set or photo not found: {photo_path}. Cannot send photo.")

    async def run(self):
        self.logger.info("Telegram bot started polling...")
        await self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Example usage (for testing purposes)
    import yaml
    from src.risk_manager import RiskManager
    from src.scanner import PreMarketScanner
    from src.analytics import Analytics
    from src.journal import TradeJournal

    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    with open("../../config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Mock IBKR bot for testing Telegram features
    class MockIBKRBot:
        def __init__(self, config):
            self.account_balance = 10000.0
            self.total_pnl = 500.0
            self.daily_pnl = 100.0
            self.total_trades = 10
            self.total_wins = 7
            self.mode = "paper"
            self.positions = {
                "AAPL": {
                    "contract": type("obj", (object,), {"symbol": "AAPL", "secType": "STK"})(),
                    "position": 10,
                    "market_price": 170.0,
                    "average_cost": 165.0
                }
            }
            self.journal = TradeJournal(config)

        def get_status(self):
            return {
                "market_status": "OPEN",
                "mode": self.mode,
                "engine_status": "RUNNING",
                "account_balance": self.account_balance,
                "total_pnl": self.total_pnl,
                "today_trades": 2,
                "today_wins": 1,
                "today_pnl": self.daily_pnl,
                "all_time_trades": self.total_trades,
                "all_time_wins": self.total_wins,
                "all_time_win_rate": (self.total_wins / self.total_trades * 100) if self.total_trades > 0 else 0,
                "all_time_profit_factor": 1.5,
                "open_positions": self.positions
            }
        def get_open_positions(self):
            return self.positions
        def get_pnl_summary(self):
            return {"daily_pnl": self.daily_pnl, "total_pnl": self.total_pnl}
        def stop_bot(self): print("Mock IBKR Bot Stopped")
        async def start_bot(self): print("Mock IBKR Bot Started")

    mock_ibkr_bot = MockIBKRBot(config)
    risk_manager = RiskManager(config)
    scanner = PreMarketScanner(config)
    analytics = Analytics(config)
    journal = TradeJournal(config)

    telegram_bot = TelegramBot(config, mock_ibkr_bot, analytics, scanner, risk_manager, journal)
    asyncio.run(telegram_bot.run())
