import time
import yaml
import asyncio
import datetime
import os
import pandas as pd

from ib_insync import IB, Stock, MarketOrder, LimitOrder, Order, Trade, util
from src.strategy import EnhancedScalpingStrategy
from src.risk_manager import RiskManager
from src.multi_timeframe import MultiTimeframeAnalysis
from src.filters import Filters
from src.scanner import PreMarketScanner
from src.telegram_bot import TelegramBot
from src.analytics import Analytics
from src.journal import TradeJournal
from src.ml_optimizer import MLOptimizer
from src.utils import setup_logger

class IBKRBot:
    def __init__(self, config_path="config.yaml"):
        self.logger = setup_logger("IBKRBot", "ibkr_bot.log")
        self.config = self._load_config(config_path)
        self.ib = IB()

        # Initialize modules
        self.strategy = EnhancedScalpingStrategy(self.config)
        self.risk_manager = RiskManager(self.config)
        self.multi_timeframe_analysis = MultiTimeframeAnalysis(self.config)
        self.filters = Filters(self.config)
        self.scanner = PreMarketScanner(self.config)
        self.analytics = Analytics(self.config)
        self.journal = TradeJournal(self.config)
        self.ml_optimizer = MLOptimizer(self.config)

        self.watchlist = [Stock(s, "SMART", "USD") for s in self.config["watchlist"]]
        self.mode = self.config["mode"]
        self.positions = {}
        self.active_trades = {}
        self.bot_running = False
        self.telegram_bot = TelegramBot(self.config, self, self.analytics, self.scanner, self.risk_manager, self.journal)

        util.logToFile("ib_insync.log")

        # Schedule daily tasks
        self.daily_tasks_scheduled = False

    def _load_config(self, config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    async def connect(self):
        host = self.config["ibkr_connection"]["host"]
        port = self.config["ibkr_connection"]["port"]
        client_id = self.config["ibkr_connection"]["client_id"]
        try:
            await self.ib.connect(host, port, client_id)
            self.logger.info(f"Connected to IBKR TWS/Gateway at {host}:{port} with client ID {client_id}")
            self.ib.reqAccountUpdates(True, "") # Request account updates
            self.ib.accountSummaryEnd += self._update_account_summary
            self.ib.updatePortfolio += self._update_portfolio
            self.ib.orderStatusEvent += self._order_status_event
            self.ib.execDetailsEvent += self._exec_details_event

        except Exception as e:
            self.logger.error(f"Could not connect to IBKR: {e}")
            # Optionally, implement retry logic or exit

    async def disconnect(self):
        self.ib.disconnect()
        self.logger.info("Disconnected from IBKR")

    async def _update_account_summary(self, account_summary):
        for item in account_summary:
            if item.tag == "NetLiquidation" and item.currency == "USD":
                self.risk_manager.set_account_balance(float(item.value))
                self.analytics.initial_capital = float(item.value) # Update initial capital for analytics
                self.logger.info(f"Account Balance: {self.risk_manager.account_balance}")

    async def _update_portfolio(self, portfolio_item):
        contract = portfolio_item.contract
        position = portfolio_item.position
        market_price = portfolio_item.marketPrice
        average_cost = portfolio_item.averageCost

        if position == 0:
            if contract.symbol in self.positions:
                del self.positions[contract.symbol]
                self.logger.info(f"Position for {contract.symbol} closed.")
        else:
            self.positions[contract.symbol] = {
                "contract": contract,
                "position": position,
                "market_price": market_price,
                "average_cost": average_cost
            }
            self.logger.info(f"Updated position for {contract.symbol}: {position} shares @ {average_cost}")

    async def _order_status_event(self, trade: Trade):
        self.logger.info(f"Order Status: {trade.contract.symbol} - {trade.orderStatus.status}")
        if trade.orderStatus.status == "Filled":
            self.logger.info(f"Order Filled: {trade.contract.symbol} {trade.order.action} {trade.order.totalQuantity} @ {trade.orderStatus.avgFillPrice}")
            # Update active_trades with fill price and other details
            if trade.order.orderRef == "MainOrder":
                self.active_trades[trade.contract.symbol]["entry_price"] = trade.orderStatus.avgFillPrice
                self.active_trades[trade.contract.symbol]["entry_time"] = datetime.datetime.now()
                # Send Telegram notification for new position
                if self.telegram_bot:
                    await self.telegram_bot.send_new_position_notification(self.active_trades[trade.contract.symbol])

    async def _exec_details_event(self, trade: Trade, fill):
        self.logger.info(f"Execution Details: {trade.contract.symbol} - {fill.execution.side} {fill.execution.shares} @ {fill.execution.avgPrice}")

        symbol = trade.contract.symbol
        if symbol not in self.active_trades:
            self.logger.warning(f"Execution for unknown trade: {symbol}")
            return

        trade_info = self.active_trades[symbol]
        entry_price = trade_info["entry_price"]
        quantity = trade_info["quantity"]
        direction = trade_info["direction"]

        # Calculate P&L for this fill
        pnl = 0.0
        if direction == "LONG" and fill.execution.side == "SLD": # Selling a long position
            pnl = (fill.execution.avgPrice - entry_price) * fill.execution.shares
        elif direction == "SHORT" and fill.execution.side == "BOT": # Buying back a short position
            pnl = (entry_price - fill.execution.avgPrice) * fill.execution.shares

        trade_info["exit_price"] = fill.execution.avgPrice
        trade_info["exit_time"] = datetime.datetime.now()
        trade_info["pnl"] = pnl
        trade_info["pnl_pct"] = (pnl / (entry_price * quantity)) * 100 if entry_price * quantity != 0 else 0

        # Determine exit reason (simplified, needs more robust logic based on orderRef)
        exit_reason = "Unknown"
        if trade.order.orderRef == "StopLoss":
            exit_reason = "Stopped out"
        elif trade.order.orderRef == "TakeProfit":
            exit_reason = "Target hit"
        elif trade.order.orderRef == "TrailingStop":
            exit_reason = "Trailing stop"
        elif trade.order.orderRef == "PartialProfit":
            exit_reason = "Partial profit"
        else:
            # If it\'s a manual close or other exit, we might need more context
            if pnl > 0: exit_reason = "Target hit"
            elif pnl < 0: exit_reason = "Stopped out"
            else: exit_reason = "Manual close"

        trade_info["exit_reason"] = exit_reason

        # Log trade to journal
        self.journal.log_trade(trade_info)

        # Update risk manager for consecutive losses and daily PnL
        self.risk_manager.record_trade_result(pnl)

        # Update analytics equity curve
        current_equity = self.risk_manager.account_balance + self.risk_manager.daily_pnl # Simplified equity
        self.analytics.update_equity_curve(current_equity)

        # Send Telegram notification for closed position
        if self.telegram_bot:
            await self.telegram_bot.send_position_closed_notification(trade_info)

        # Remove from active trades if position is fully closed
        if trade.order.orderRef != "PartialProfit": # If it\'s not a partial profit, assume full close
            if symbol in self.active_trades:
                del self.active_trades[symbol]

    async def start_bot(self):
        await self.connect()
        if not self.ib.isConnected():
            self.logger.error("Bot cannot start without IBKR connection.")
            return

        self.bot_running = True
        self.logger.info(f"Starting bot in {self.mode} mode...")

        # Request market data for watchlist
        for contract in self.watchlist:
            self.ib.reqMktData(contract, "", False, False) # Request generic market data
            self.ib.reqTickByTickData(contract, "Last", 0, False) # Real-time tick data

        self.ib.pendingTickersEvent += self._on_pending_tickers

        # Start Telegram bot polling in a separate task
        asyncio.create_task(self.telegram_bot.run())

        # Initial earnings date update and ML optimizer analysis
        self.filters.update_earnings_dates()
        self.ml_optimizer.analyze_indicator_performance()

        while self.bot_running:
            current_time = datetime.datetime.now().time()
            current_date = datetime.date.today()

            # Daily tasks (morning briefing, daily summary reset)
            if not self.daily_tasks_scheduled and current_time < datetime.time(9, 0):
                # Reset daily PnL and consecutive losses at the start of a new day
                if self.risk_manager.last_trading_day is None or self.risk_manager.last_trading_day < current_date:
                    self.risk_manager.consecutive_losses = 0
                    self.risk_manager.daily_pnl = 0.0
                    self.risk_manager.last_trading_day = current_date
                    self.risk_manager.bot_paused = False # Auto-resume next day
                    self.logger.info("Daily reset performed. Bot resumed if paused by circuit breaker.")

                # Send morning briefing
                await self.telegram_bot.send_morning_briefing()
                self.daily_tasks_scheduled = True

            # Reset daily tasks flag after market close (e.g., after 17:00)
            if self.daily_tasks_scheduled and current_time > datetime.time(17, 0):
                await self.telegram_bot.send_daily_performance_summary()
                self.daily_tasks_scheduled = False

            # Check circuit breaker
            paused, reason = self.risk_manager.check_circuit_breaker(current_date)
            if paused:
                if not self.risk_manager.bot_paused_alert_sent:
                    await self.telegram_bot.send_circuit_breaker_alert(reason)
                    self.risk_manager.bot_paused_alert_sent = True # Prevent spamming alerts
                self.logger.warning(f"Bot paused by circuit breaker: {reason}")
                await self.ib.sleep(60) # Sleep longer if paused
                continue
            else:
                self.risk_manager.bot_paused_alert_sent = False # Reset alert flag

            await self.ib.sleep(1) # Keep the event loop running

    async def _on_pending_tickers(self, tickers):
        if self.risk_manager.bot_paused:
            return # Do not process tickers if bot is paused

        for ticker in tickers:
            contract = ticker.contract
            symbol = contract.symbol

            # Skip if near earnings
            if self.filters.is_near_earnings(symbol, datetime.date.today()):
                self.logger.info(f"Skipping {symbol}: Near earnings date.")
                continue

            # Get historical data for strategy calculation (e.g., 1-min bars)
            # Also fetch for higher timeframes
            data_5min = await self._get_historical_data(contract, "5 min")
            data_15min = await self._get_historical_data(contract, "15 min")
            data_1h = await self._get_historical_data(contract, "1 hour")

            if data_5min.empty or data_15min.empty or data_1h.empty:
                self.logger.warning(f"Not enough historical data for {symbol}.")
                continue

            # Generate signals on 5min timeframe
            df_with_signals_5min = self.strategy.generate_signals(data_5min.copy())
            latest_signal = df_with_signals_5min["signal"].iloc[-1]
            latest_close = df_with_signals_5min["close"].iloc[-1]
            latest_atr = df_with_signals_5min["atr"].iloc[-1]

            if latest_signal == 0:
                continue # No signal

            # Multi-timeframe analysis
            multi_timeframe_data = {
                "5min": df_with_signals_5min,
                "15min": self.strategy.generate_signals(data_15min.copy()), # Apply strategy indicators to higher TFs too
                "1h": self.strategy.generate_signals(data_1h.copy())
            }
            if not self.multi_timeframe_analysis.confirm_signal_with_timeframes(df_with_signals_5min, multi_timeframe_data, latest_signal):
                self.logger.info(f"Signal for {symbol} not confirmed by multi-timeframe analysis.")
                continue

            # ML Optimizer for signal confidence
            current_indicators = {
                "ema_cross": (df_with_signals_5min["ema_fast"].iloc[-1] > df_with_signals_5min["ema_slow"].iloc[-1]) != (df_with_signals_5min["ema_fast"].iloc[-2] > df_with_signals_5min["ema_slow"].iloc[-2]),
                "macd_cross": (df_with_signals_5min["macd"].iloc[-1] > df_with_signals_5min["macd_signal"].iloc[-1]) != (df_with_signals_5min["macd"].iloc[-2] > df_with_signals_5min["macd_signal"].iloc[-2]),
                "stoch_oversold": df_with_signals_5min["stoch_k"].iloc[-1] < 20,
                "stoch_overbought": df_with_signals_5min["stoch_k"].iloc[-1] > 80,
                "bb_lower_band_touch": df_with_signals_5min["close"].iloc[-1] <= df_with_signals_5min["bb_bbl"].iloc[-1],
                "bb_upper_band_touch": df_with_signals_5min["close"].iloc[-1] >= df_with_signals_5min["bb_bbh"].iloc[-1],
            }
            signal_confidence = self.ml_optimizer.get_signal_confidence(symbol, current_indicators)
            latest_signal = self.ml_optimizer.adjust_signal_based_on_confidence(latest_signal, signal_confidence)

            if latest_signal == 0:
                self.logger.info(f"Signal for {symbol} suppressed by ML Optimizer due to low confidence.")
                continue

            # Check correlation filter
            if not self.filters.check_correlation_filter(symbol, self.positions.keys()):
                self.logger.info(f"Skipping {symbol}: Correlation filter triggered.")
                continue

            if latest_signal == 1: # Buy signal
                if symbol not in self.positions: # Only enter if not already in position
                    self.logger.info(f"BUY signal for {symbol} at {latest_close} with ATR {latest_atr:.2f}")
                    await self._place_trade(contract, "BUY", latest_close, latest_atr, signal_confidence, current_indicators, multi_timeframe_data)
            elif latest_signal == -1: # Sell signal (to open short position)
                if symbol not in self.positions: # Only enter if not already in position
                    self.logger.info(f"SELL signal for {symbol} at {latest_close} with ATR {latest_atr:.2f}")
                    await self._place_trade(contract, "SELL", latest_close, latest_atr, signal_confidence, current_indicators, multi_timeframe_data)

            # Trailing stop-loss update for existing positions
            if symbol in self.positions:
                pos_info = self.positions[symbol]
                current_position_size = pos_info["position"]
                entry_price = pos_info["average_cost"]
                current_trailing_stop = pos_info.get("trailing_stop_price")

                new_trailing_stop = self.risk_manager.update_trailing_stop(
                    latest_close, entry_price, pos_info["initial_stop_loss"], 
                    "LONG" if current_position_size > 0 else "SHORT", latest_atr, current_trailing_stop
                )
                if new_trailing_stop != current_trailing_stop:
                    self.positions[symbol]["trailing_stop_price"] = new_trailing_stop
                    self.logger.info(f"Updated trailing stop for {symbol} to {new_trailing_stop:.2f}")
                    # TODO: Update the actual stop order in IBKR

    async def _get_historical_data(self, contract, bar_size):
        bars = await self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 D", # Request enough data for all indicators and timeframes
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            keepUpToDate=True
        )
        if not bars: return pd.DataFrame()

        df = util.df(bars)
        df.columns = [col.lower() for col in df.columns]
        df = df.set_index("date")
        return df

    async def _place_trade(self, contract, action, price, atr_value, signal_confidence, indicators_at_entry, timeframe_alignment_data):
        signal_type = 1 if action == "BUY" else -1
        stop_loss_price, target_1_price, partial_profit_price, rr_ratio, risk_amount, error_msg = \
            self.risk_manager.calculate_risk_reward_levels(price, atr_value, signal_type)

        if error_msg:
            self.logger.warning(f"Trade for {contract.symbol} rejected: {error_msg}")
            if self.telegram_bot:
                await self.telegram_bot.send_message(f"Trade for {contract.symbol} rejected: {error_msg}")
            return

        num_shares = self.risk_manager.calculate_position_size(price, risk_amount)
        if num_shares == 0:
            self.logger.warning(f"Cannot place trade for {contract.symbol}: position size is zero.")
            if self.telegram_bot:
                await self.telegram_bot.send_message(f"Trade for {contract.symbol} rejected: Position size is zero.")
            return

        # Store trade info temporarily for order status/execution events
        trade_id = f"{contract.symbol}_{datetime.datetime.now().timestamp()}"
        self.active_trades[contract.symbol] = {
            "trade_id": trade_id,
            "symbol": contract.symbol,
            "direction": "LONG" if action == "BUY" else "SHORT",
            "quantity": num_shares,
            "entry_price": price, # This will be updated with actual fill price
            "stop_loss_price": stop_loss_price,
            "target_price": target_1_price,
            "partial_profit_price": partial_profit_price,
            "rr_ratio": rr_ratio,
            "initial_stop_loss": stop_loss_price, # For trailing stop calculation
            "signal_confidence": signal_confidence,
            "indicators_at_entry": str(indicators_at_entry), # Store as string for CSV
            "timeframe_alignment": str({tf: df.iloc[-1].to_dict() for tf, df in timeframe_alignment_data.items()}), # Store as string
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "exit_reason": ""
        }

        main_order = MarketOrder(action, num_shares)
        main_order.orderRef = "MainOrder"

        # Place main order
        trade = await self.ib.placeOrder(contract, main_order)
        self.logger.info(f"Placed {action} order for {num_shares} shares of {contract.symbol} at market. R:R {rr_ratio:.2f}:1")

        # Wait for the main order to be filled to get its orderId
        # This is a simplification. In a real bot, you\'d use orderStatusEvent to confirm fill
        # and then place bracket orders. For now, we\'ll assume immediate fill.
        await trade.waitFill()
        if not trade.isDone() or not trade.orderStatus.avgFillPrice:
            self.logger.error(f"Main order for {contract.symbol} not filled. Cancelling bracket orders.")
            if self.telegram_bot:
                await self.telegram_bot.send_message(f"Main order for {contract.symbol} not filled. Trade cancelled.")
            if contract.symbol in self.active_trades: del self.active_trades[contract.symbol]
            return

        filled_price = trade.orderStatus.avgFillPrice
        filled_quantity = trade.orderStatus.filled

        # Update entry price in active_trades with actual fill price
        self.active_trades[contract.symbol]["entry_price"] = filled_price

        # Place bracket orders (Stop Loss, Take Profit, Partial Profit)
        # Stop Loss Order
        stop_loss_order = Order(
            orderId=self.ib.client.getReqId(),
            action="SELL" if action == "BUY" else "BUY",
            totalQuantity=filled_quantity,
            orderType="STP",
            auxPrice=stop_loss_price,
            parentId=trade.order.orderId
        )
        stop_loss_order.orderRef = "StopLoss"
        await self.ib.placeOrder(contract, stop_loss_order)
        self.logger.info(f"Placed Stop Loss order for {contract.symbol} at {stop_loss_price:.2f}")

        # Partial Profit Order (50% at first target)
        partial_quantity = int(filled_quantity * 0.5)
        if partial_quantity > 0:
            partial_profit_order = Order(
                orderId=self.ib.client.getReqId(),
                action="SELL" if action == "BUY" else "BUY",
                totalQuantity=partial_quantity,
                orderType="LMT",
                lmtPrice=partial_profit_price,
                parentId=trade.order.orderId
            )
            partial_profit_order.orderRef = "PartialProfit"
            await self.ib.placeOrder(contract, partial_profit_order)
            self.logger.info(f"Placed Partial Profit order for {contract.symbol} ({partial_quantity} shares) at {partial_profit_price:.2f}")

        # Remaining quantity for full Take Profit or Trailing Stop
        remaining_quantity = filled_quantity - partial_quantity
        if remaining_quantity > 0:
            take_profit_order = Order(
                orderId=self.ib.client.getReqId(),
                action="SELL" if action == "BUY" else "BUY",
                totalQuantity=remaining_quantity,
                orderType="LMT", # Or use a trailing stop order type if available and preferred
                lmtPrice=target_1_price, # Initial target, will be updated by trailing stop logic
                parentId=trade.order.orderId
            )
            take_profit_order.orderRef = "TakeProfit"
            await self.ib.placeOrder(contract, take_profit_order)
            self.logger.info(f"Placed Take Profit order for {contract.symbol} ({remaining_quantity} shares) at {target_1_price:.2f}")

            # Store order ID for trailing stop updates
            self.active_trades[contract.symbol]["trailing_stop_order_id"] = take_profit_order.orderId

    def get_status(self):
        market_status = "OPEN" if self.ib.isConnected() else "CLOSED"
        return {
            "market_status": market_status,
            "mode": self.mode,
            "engine_status": "RUNNING" if self.bot_running else "STOPPED",
            "account_balance": self.risk_manager.account_balance,
            "total_pnl": self.analytics.calculate_performance_metrics(self.journal.get_journal())["total_pnl"],
            "today_trades": len(self.journal.get_trades_by_date(datetime.date.today().isoformat())),
            "today_wins": self.analytics.calculate_performance_metrics(self.journal.get_trades_by_date(datetime.date.today().isoformat()))["winning_trades"],
            "today_pnl": self.risk_manager.daily_pnl,
            "all_time_trades": self.analytics.calculate_performance_metrics(self.journal.get_journal())["total_trades"],
            "all_time_wins": self.analytics.calculate_performance_metrics(self.journal.get_journal())["winning_trades"],
            "all_time_win_rate": self.analytics.calculate_performance_metrics(self.journal.get_journal())["win_rate"],
            "all_time_profit_factor": self.analytics.calculate_performance_metrics(self.journal.get_journal())["profit_factor"],
            "open_positions": self.positions
        }

    def get_open_positions(self):
        return self.positions

    def get_pnl_summary(self):
        return {
            "daily_pnl": self.risk_manager.daily_pnl,
            "total_pnl": self.analytics.calculate_performance_metrics(self.journal.get_journal())["total_pnl"]
        }

    def stop_bot(self):
        self.logger.info("Stopping bot...")
        self.bot_running = False
        # Cancel all open orders
        for trade in self.ib.openTrades():
            self.ib.cancelOrder(trade.order)
            self.logger.info(f"Cancelled order for {trade.contract.symbol}")
        # Disconnect from IBKR
        self.ib.disconnect()
        self.logger.info("Bot stopped.")


if __name__ == "__main__":
    # Example usage (for testing purposes)
    # Create data directory if it\'s not exist
    os.makedirs("data", exist_ok=True)

    bot = IBKRBot()
    asyncio.run(bot.start_bot())
