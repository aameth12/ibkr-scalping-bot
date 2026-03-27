import logging
import telegram
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio

from src.utils import setup_logger

class TelegramBot:
    def __init__(self, config, ibkr_bot_instance=None):
        self.logger = setup_logger("TelegramBot", "telegram_bot.log")
        self.bot_token = config["telegram_settings"]["bot_token"]
        self.chat_id = config["telegram_settings"]["chat_id"]
        self.ibkr_bot = ibkr_bot_instance
        self.application = Application.builder().token(self.bot_token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("dashboard", self.dashboard_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("positions", self.positions_command))
        self.application.add_handler(CommandHandler("pnl", self.pnl_command))
        self.application.add_handler(CommandHandler("stop_bot", self.stop_bot_command))
        self.application.add_handler(CommandHandler("start_bot", self.start_bot_command))

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
            "/pnl - Show today's and total P&L\n"
            "/start_bot - Start the trading bot (if stopped)\n"
            "/stop_bot - Stop the trading bot\n"
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
            f"Market: {status['market_status']}\n"
            f"Mode: {status['mode']} | Engine: {status['engine_status']}\n"
            f"Account Balance: ${status['account_balance']:.2f}\n"
            f"Total P&L (All Time): ${status['total_pnl']:.2f}"
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
                f"  {data['contract'].secType} {symbol} x{data['position']} @ ${data['average_cost']:.2f}\n"
                f"    Now: ${data['market_price']:.2f} | P&L: ${(data['market_price'] - data['average_cost']) * data['position']:.2f} ({(data['market_price'] / data['average_cost'] - 1) * 100:.2f}%)\n"
            )
        await update.message.reply_text(positions_text)

    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        
        pnl_summary = self.ibkr_bot.get_pnl_summary()
        pnl_text = (
            f"Today's P&L: ${pnl_summary['daily_pnl']:.2f}\n"
            f"Total P&L (All Time): ${pnl_summary['total_pnl']:.2f}"
        )
        await update.message.reply_text(pnl_text)

    async def stop_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        await update.message.reply_text("Stopping the trading bot...")
        self.ibkr_bot.stop_bot()
        await update.message.reply_text("Trading bot stopped.")

    async def start_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.ibkr_bot:
            await update.message.reply_text("IBKR bot not initialized.")
            return
        await update.message.reply_text("Starting the trading bot...")
        asyncio.create_task(self.ibkr_bot.start_bot()) # Run in background
        await update.message.reply_text("Trading bot started.")

    def _format_dashboard_message(self, status):
        market_status_emoji = "🟢 OPEN" if status["market_status"] == "OPEN" else "🔴 CLOSED"
        engine_status_emoji = "▶ RUNNING" if status["engine_status"] == "RUNNING" else "■ STOPPED"

        dashboard_text = f"""
==============================
Market: {market_status_emoji}
Mode: {status['mode']} | Engine: {engine_status_emoji}
Account:
  Balance: ${status['account_balance']:.2f}
  Total P&L: ${status['total_pnl']:.2f}
Today
------------------------------
Trades: {status['today_trades']} | Wins: {status['today_wins']} | P&L: ${status['today_pnl']:.2f}
All-Time (Bot Tracked)
------------------------------
Total Trades: {status['all_time_trades']} | Win Rate: {status['all_time_win_rate']:.2f}%
Total P&L: ${status['total_pnl']:.2f}
Profit Factor: {status['all_time_profit_factor']:.2f}
Open Positions ({len(status['open_positions'])})
------------------------------
"""
        if status["open_positions"]:
            for symbol, data in status["open_positions"].items():
                unrealized_pnl = (data['market_price'] - data['average_cost']) * data['position']
                unrealized_pct = (data['market_price'] / data['average_cost'] - 1) * 100
                dashboard_text += (
                    f"  {'LONG' if data['position'] > 0 else 'SHORT'} {symbol} x{abs(data['position'])} @ ${data['average_cost']:.2f}\n"
                    f"    Now: ${data['market_price']:.2f} | P&L: ${unrealized_pnl:.2f} ({unrealized_pct:.2f}%)\n"
                )
            total_unrealized = sum([(p['market_price'] - p['average_cost']) * p['position'] for p in status['open_positions'].values()])
            dashboard_text += f"  Total Unrealized: ${total_unrealized:.2f}"
        else:
            dashboard_text += "  No open positions."

        return dashboard_text

    async def send_new_position_notification(self, trade, risk_manager):
        contract = trade.contract
        order = trade.order
        action = order.action
        quantity = order.totalQuantity
        entry_price = trade.orderStatus.avgFillPrice

        stop_loss_price, take_profit_price = risk_manager.calculate_stop_loss_take_profit(entry_price, "long" if action == "BUY" else "short")
        
        # Calculate risk amount
        risk_amount = abs(entry_price - stop_loss_price) * quantity
        risk_pct = (risk_amount / (entry_price * quantity)) * 100

        # Calculate R:R
        reward = abs(take_profit_price - entry_price) * quantity
        if risk_amount > 0:
            rr_ratio = reward / risk_amount
        else:
            rr_ratio = 0 # Avoid division by zero

        message = f"""
🟢 NEW POSITION
{contract.symbol} {action} x{quantity} @ ${entry_price:.2f}
Stop:   ${stop_loss_price:.2f} ({risk_manager.stop_loss_pct*100:.2f}%)
Target: ${take_profit_price:.2f} ({risk_manager.take_profit_pct*100:.2f}%)
R:R {rr_ratio:.2f}:1 | Risk: ${risk_amount:.2f} ({risk_pct:.2f}%)
"""
        await self.send_message(message)

    async def send_position_closed_notification(self, trade, pnl, close_price, open_price):
        contract = trade.contract
        order = trade.order
        quantity = order.totalQuantity
        
        # Determine if it was stopped out or target hit (simplified, actual logic would be more complex)
        close_reason = "" # Placeholder
        if pnl < 0: close_reason = "Stopped out 🛑"
        elif pnl > 0: close_reason = "Target hit 🎯"
        else: close_reason = "Manual close ✋"

        message = f"""
🔴 POSITION CLOSED
{contract.symbol} {'LONG' if order.action == 'SELL' else 'SHORT'} x{quantity}
Opened: ${open_price:.2f} → Closed: ${close_price:.2f}
P&L: ${pnl:.2f} ({(pnl / (open_price * quantity)) * 100:.2f}%)
{close_reason}
"""
        await self.send_message(message)

    async def send_message(self, text):
        if self.chat_id:
            try:
                await self.application.bot.send_message(chat_id=self.chat_id, text=text)
            except telegram.error.TelegramError as e:
                self.logger.error(f"Error sending Telegram message: {e}")
        else:
            self.logger.warning("Telegram chat_id not set. Cannot send messages.")

    async def run(self):
        self.logger.info("Telegram bot started polling...")
        await self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Example usage (for testing purposes)
    import yaml
    with open("../../config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Mock IBKR bot for testing Telegram features
    class MockIBKRBot:
        def __init__(self):
            self.account_balance = 1000.0
            self.total_pnl = 50.0
            self.daily_pnl = 10.0
            self.total_trades = 10
            self.total_wins = 7
            self.mode = "paper"
            self.positions = {
                "AAPL": {
                    "contract": type('obj', (object,), {'symbol': 'AAPL', 'secType': 'STK'})(),
                    "position": 10,
                    "market_price": 170.0,
                    "average_cost": 165.0
                }
            }
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

    mock_ibkr_bot = MockIBKRBot()
    telegram_bot = TelegramBot(config, mock_ibkr_bot)
    asyncio.run(telegram_bot.run())
