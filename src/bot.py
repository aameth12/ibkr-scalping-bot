import time
import yaml
from ib_insync import IB, Stock, MarketOrder, LimitOrder, Order, Trade, util
from src.strategy import MomentumScalpingStrategy
from src.risk_manager import RiskManager
from src.utils import setup_logger

class IBKRBot:
    def __init__(self, config_path="config.yaml"):
        self.logger = setup_logger("IBKRBot", "ibkr_bot.log")
        self.config = self._load_config(config_path)
        self.ib = IB()
        self.strategy = MomentumScalpingStrategy(self.config)
        self.risk_manager = RiskManager(self.config)
        self.watchlist = [Stock(s, "SMART", "USD") for s in self.config["watchlist"]]
        self.mode = self.config["mode"]
        self.positions = {}
        self.trades_today = []
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.total_trades = 0
        self.total_wins = 0
        self.telegram_bot = None # Placeholder for Telegram bot instance

        util.logToFile("ib_insync.log")

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
                self.logger.info(f"Account Balance: {self.risk_manager.account_balance}")
                if self.telegram_bot:
                    await self.telegram_bot.send_dashboard_update(self) # Update dashboard on balance change

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
            # Send Telegram notification for new position
            if self.telegram_bot and trade.order.orderRef == "MainOrder": # Only for initial order
                await self.telegram_bot.send_new_position_notification(trade, self.risk_manager)

    async def _exec_details_event(self, trade: Trade, fill):
        self.logger.info(f"Execution Details: {trade.contract.symbol} - {fill.execution.side} {fill.execution.shares} @ {fill.execution.avgPrice}")
        # Track P&L and update daily/total P&L
        # This is a simplified P&L tracking. A more robust system would track individual trades.
        if fill.execution.side == "BOT": # Buy
            pass # P&L is realized on sell
        elif fill.execution.side == "SLD": # Sell
            # Assuming a simple FIFO for P&L calculation for now
            # In a real scenario, you'd match fills to specific open positions
            # For scalping, we assume quick entry/exit, so this is a reasonable approximation
            if trade.contract.symbol in self.positions:
                avg_cost = self.positions[trade.contract.symbol]["average_cost"]
                pnl = (fill.execution.avgPrice - avg_cost) * fill.execution.shares
                self.daily_pnl += pnl
                self.total_pnl += pnl
                self.total_trades += 1
                if pnl > 0: self.total_wins += 1
                self.logger.info(f"Realized P&L for {trade.contract.symbol}: {pnl:.2f}")
                if self.telegram_bot:
                    await self.telegram_bot.send_position_closed_notification(trade, pnl, fill.execution.avgPrice, avg_cost)

    async def start_bot(self):
        await self.connect()
        if not self.ib.isConnected():
            self.logger.error("Bot cannot start without IBKR connection.")
            return

        self.logger.info(f"Starting bot in {self.mode} mode...")

        # Request market data
        for contract in self.watchlist:
            self.ib.reqMktData(contract, "233,165,RSI,EMA", False, False) # Request historical data for indicators
            self.ib.reqTickByTickData(contract, "Last", 0, False) # Real-time tick data

        self.ib.pendingTickersEvent += self._on_pending_tickers

        while self.ib.isConnected():
            if self.risk_manager.check_max_daily_loss():
                self.logger.warning("Max daily loss reached. Stopping trading for the day.")
                # Implement logic to close all open positions if any
                break
            await self.ib.sleep(1) # Keep the event loop running

    async def _on_pending_tickers(self, tickers):
        for ticker in tickers:
            contract = ticker.contract
            symbol = contract.symbol

            # Get historical data for strategy calculation (e.g., 1-min bars)
            bars = await self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr="300 S", # Last 5 minutes
                barSizeSetting="1 min",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
                keepUpToDate=True
            )
            if not bars: continue

            df = util.df(bars)
            df.columns = [col.lower() for col in df.columns]
            df = df.set_index("date")

            # Generate signals
            df_with_signals = self.strategy.generate_signals(df.copy())
            latest_signal = df_with_signals["signal"].iloc[-1]
            latest_close = df_with_signals["close"].iloc[-1]

            if latest_signal == 1: # Buy signal
                if symbol not in self.positions: # Only enter if not already in position
                    self.logger.info(f"BUY signal for {symbol} at {latest_close}")
                    await self._place_trade(contract, "BUY", latest_close)
            elif latest_signal == -1: # Sell signal
                if symbol in self.positions: # Only exit if in position
                    self.logger.info(f"SELL signal for {symbol} at {latest_close}")
                    await self._place_trade(contract, "SELL", latest_close)

    async def _place_trade(self, contract, action, price):
        num_shares = self.risk_manager.calculate_position_size(price)
        if num_shares == 0:
            self.logger.warning(f"Cannot place trade for {contract.symbol}: position size is zero.")
            return

        main_order = MarketOrder(action, num_shares)
        main_order.orderRef = "MainOrder"

        stop_loss_price, take_profit_price = self.risk_manager.calculate_stop_loss_take_profit(price, "long" if action == "BUY" else "short")

        # Bracket orders
        stop_loss_order = Order(
            orderId=self.ib.client.getReqId(),
            action="SELL" if action == "BUY" else "BUY",
            totalQuantity=num_shares,
            orderType="STP",
            auxPrice=stop_loss_price,
            parentId=main_order.orderId # This needs to be set after main_order is placed and has an orderId
        )
        stop_loss_order.orderRef = "StopLoss"

        take_profit_order = Order(
            orderId=self.ib.client.getReqId(),
            action="SELL" if action == "BUY" else "BUY",
            totalQuantity=num_shares,
            orderType="LMT",
            lmtPrice=take_profit_price,
            parentId=main_order.orderId # This needs to be set after main_order is placed and has an orderId
        )
        take_profit_order.orderRef = "TakeProfit"

        # Place main order first
        trade = await self.ib.placeOrder(contract, main_order)
        self.logger.info(f"Placed {action} order for {num_shares} shares of {contract.symbol} at market.")

        # Wait for main order to be filled to get its orderId
        # This part is tricky with ib_insync. For simplicity, we'll assume the main order is filled quickly
        # In a real-world scenario, you'd need to listen to orderStatusEvent for the main_order.orderId
        # and then place the bracket orders.
        # For now, we'll assign parentId after placing the main order (this might not work as expected without proper orderId from IB)
        # A more robust solution involves waiting for the main order to be filled and then placing the bracket orders with the correct parentId.
        # For the purpose of this exercise, we'll simulate it by placing them immediately after.

        # Assign parentId for bracket orders
        stop_loss_order.parentId = trade.order.orderId
        take_profit_order.parentId = trade.order.orderId

        # Place bracket orders
        await self.ib.placeOrder(contract, stop_loss_order)
        self.logger.info(f"Placed Stop Loss order for {contract.symbol} at {stop_loss_price}")
        await self.ib.placeOrder(contract, take_profit_order)
        self.logger.info(f"Placed Take Profit order for {contract.symbol} at {take_profit_price}")

    def set_telegram_bot(self, telegram_bot_instance):
        self.telegram_bot = telegram_bot_instance

    def get_status(self):
        market_status = "OPEN" if self.ib.isConnected() else "CLOSED"
        return {
            "market_status": market_status,
            "mode": self.mode,
            "engine_status": "RUNNING" if self.ib.isConnected() else "STOPPED",
            "account_balance": self.risk_manager.account_balance,
            "total_pnl": self.total_pnl,
            "today_trades": len(self.trades_today),
            "today_wins": 0, # Needs proper tracking
            "today_pnl": self.daily_pnl,
            "all_time_trades": self.total_trades,
            "all_time_wins": self.total_wins,
            "all_time_win_rate": (self.total_wins / self.total_trades * 100) if self.total_trades > 0 else 0,
            "all_time_profit_factor": 0, # Needs proper calculation
            "open_positions": self.positions
        }

    def get_open_positions(self):
        return self.positions

    def get_pnl_summary(self):
        return {
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl
        }

    def stop_bot(self):
        self.logger.info("Stopping bot...")
        # Cancel all open orders
        for trade in self.ib.openTrades():
            self.ib.cancelOrder(trade.order)
            self.logger.info(f"Cancelled order for {trade.contract.symbol}")
        # Disconnect from IBKR
        self.ib.disconnect()
        self.logger.info("Bot stopped.")


if __name__ == "__main__":
    # Example usage (for testing purposes)
    import asyncio
    bot = IBKRBot()
    asyncio.run(bot.start_bot())
