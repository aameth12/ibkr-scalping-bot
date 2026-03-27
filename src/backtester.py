import pandas as pd
import yfinance as yf
import numpy as np
from src.strategy import MomentumScalpingStrategy
from src.risk_manager import RiskManager
from src.utils import setup_logger

class Backtester:
    def __init__(self, config):
        self.logger = setup_logger("Backtester", "backtester.log")
        self.config = config
        self.strategy = MomentumScalpingStrategy(config)
        self.risk_manager = RiskManager(config)
        self.initial_balance = 1000.0 # Beginner trader budget
        self.trades = []
        self.account_history = []

    def _get_historical_data(self, symbol, start_date, end_date, interval="1m"):
        try:
            data = yf.download(symbol, start=start_date, end=end_date, interval=interval)
            if data.empty:
                self.logger.warning(f"No data found for {symbol} for interval {interval}")
                return pd.DataFrame()
            data.columns = [col.lower() for col in data.columns]
            return data
        except Exception as e:
            self.logger.error(f"Error downloading data for {symbol}: {e}")
            return pd.DataFrame()

    def run_backtest(self, symbol, start_date, end_date):
        self.logger.info(f"Running backtest for {symbol} from {start_date} to {end_date}")
        df = self._get_historical_data(symbol, start_date, end_date)

        if df.empty:
            self.logger.warning(f"Skipping backtest for {symbol} due to no data.")
            return

        df_with_signals = self.strategy.generate_signals(df.copy())

        self.risk_manager.set_account_balance(self.initial_balance)
        current_balance = self.initial_balance
        position_open = False
        entry_price = 0
        shares = 0

        for i, row in df_with_signals.iterrows():
            self.account_history.append({
                "date": i,
                "balance": current_balance
            })

            if not position_open and row["signal"] == 1: # Buy signal
                shares = self.risk_manager.calculate_position_size(row["close"])
                if shares > 0:
                    entry_price = row["close"]
                    current_balance -= shares * entry_price # Deduct cost of shares
                    position_open = True
                    stop_loss, take_profit = self.risk_manager.calculate_stop_loss_take_profit(entry_price, "long")
                    self.trades.append({
                        "symbol": symbol,
                        "entry_date": i,
                        "entry_price": entry_price,
                        "shares": shares,
                        "action": "BUY",
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "exit_date": None,
                        "exit_price": None,
                        "pnl": 0,
                        "pnl_pct": 0
                    })
                    self.logger.info(f"BUY {shares} of {symbol} at {entry_price:.2f} on {i}")

            elif position_open:
                # Check for stop loss or take profit
                last_trade = self.trades[-1]
                if row["low"] <= last_trade["stop_loss"]:
                    exit_price = last_trade["stop_loss"]
                    pnl = (exit_price - last_trade["entry_price"]) * last_trade["shares"]
                    current_balance += shares * exit_price
                    last_trade.update({
                        "exit_date": i,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": (pnl / (last_trade["entry_price"] * last_trade["shares"])) * 100
                    })
                    position_open = False
                    self.logger.info(f"STOP LOSS for {symbol} at {exit_price:.2f} on {i}. P&L: {pnl:.2f}")

                elif row["high"] >= last_trade["take_profit"]:
                    exit_price = last_trade["take_profit"]
                    pnl = (exit_price - last_trade["entry_price"]) * last_trade["shares"]
                    current_balance += shares * exit_price
                    last_trade.update({
                        "exit_date": i,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": (pnl / (last_trade["entry_price"] * last_trade["shares"])) * 100
                    })
                    position_open = False
                    self.logger.info(f"TAKE PROFIT for {symbol} at {exit_price:.2f} on {i}. P&L: {pnl:.2f}")

                elif row["signal"] == -1: # Sell signal (exit if no SL/TP hit)
                    exit_price = row["close"]
                    pnl = (exit_price - last_trade["entry_price"]) * last_trade["shares"]
                    current_balance += shares * exit_price
                    last_trade.update({
                        "exit_date": i,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": (pnl / (last_trade["entry_price"] * last_trade["shares"])) * 100
                    })
                    position_open = False
                    self.logger.info(f"SELL signal exit for {symbol} at {exit_price:.2f} on {i}. P&L: {pnl:.2f}")

        # If position still open at the end of backtest, close it at last price
        if position_open:
            last_trade = self.trades[-1]
            exit_price = df_with_signals["close"].iloc[-1]
            pnl = (exit_price - last_trade["entry_price"]) * last_trade["shares"]
            current_balance += shares * exit_price
            last_trade.update({
                "exit_date": df_with_signals.index[-1],
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pct": (pnl / (last_trade["entry_price"] * last_trade["shares"])) * 100
            })
            self.logger.info(f"Forced exit for {symbol} at {exit_price:.2f} on {df_with_signals.index[-1]}. P&L: {pnl:.2f}")

        self.logger.info(f"Backtest for {symbol} finished. Final Balance: {current_balance:.2f}")
        return pd.DataFrame(self.trades), pd.DataFrame(self.account_history)

    def analyze_results(self, trades_df, account_history_df):
        if trades_df.empty:
            self.logger.warning("No trades to analyze.")
            return {}

        total_trades = len(trades_df)
        winning_trades = trades_df[trades_df["pnl"] > 0]
        losing_trades = trades_df[trades_df["pnl"] < 0]

        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        total_pnl = trades_df["pnl"].sum()
        gross_profit = winning_trades["pnl"].sum()
        gross_loss = losing_trades["pnl"].sum()
        profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else np.inf

        # Max Drawdown
        if not account_history_df.empty:
            account_history_df["peak"] = account_history_df["balance"].cummax()
            account_history_df["drawdown"] = account_history_df["balance"] - account_history_df["peak"]
            max_drawdown = account_history_df["drawdown"].min()
            max_drawdown_pct = (max_drawdown / self.initial_balance) * 100
        else:
            max_drawdown = 0
            max_drawdown_pct = 0

        # Sharpe Ratio (simplified, needs more data points for proper calculation)
        returns = trades_df["pnl_pct"] / 100 # Convert to decimal returns
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252 * 6.5 * 60) # Assuming 1-min bars, 6.5 trading hours, 252 trading days
        else:
            sharpe_ratio = 0

        metrics = {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "final_balance": account_history_df["balance"].iloc[-1] if not account_history_df.empty else self.initial_balance
        }
        return metrics
