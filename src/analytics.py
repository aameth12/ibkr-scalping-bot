import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime

class Analytics:
    def __init__(self, config):
        self.trade_log_path = config["analytics_params"]["trade_log_path"]
        self.equity_curve_path = config["analytics_params"]["equity_curve_path"]
        self.initial_capital = config["analytics_params"]["initial_capital"]
        self.equity_data = [] # List of (timestamp, equity_value)

    def load_trade_log(self):
        try:
            return pd.read_csv(self.trade_log_path, parse_dates=["entry_time", "exit_time"])
        except FileNotFoundError:
            return pd.DataFrame(columns=["symbol", "direction", "entry_time", "exit_time",
                                        "entry_price", "exit_price", "shares", "pnl",
                                        "rr_achieved", "exit_reason", "indicators_at_entry",
                                        "timeframe_alignment"])

    def update_equity_curve(self, current_equity, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.now()
        self.equity_data.append((timestamp, current_equity))
        # Optionally save to a file periodically or at market close

    def calculate_performance_metrics(self, trade_log_df):
        if trade_log_df.empty:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0, # Requires more data (risk-free rate, std dev of returns)
                "max_drawdown": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "max_win_streak": 0,
                "max_loss_streak": 0,
            }

        total_trades = len(trade_log_df)
        winning_trades = len(trade_log_df[trade_log_df["pnl"] > 0])
        losing_trades = len(trade_log_df[trade_log_df["pnl"] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        total_pnl = trade_log_df["pnl"].sum()

        total_profit = trade_log_df[trade_log_df["pnl"] > 0]["pnl"].sum()
        total_loss = abs(trade_log_df[trade_log_df["pnl"] < 0]["pnl"].sum())
        profit_factor = total_profit / total_loss if total_loss > 0 else (1.0 if total_profit > 0 else 0.0)

        # Equity Curve Calculation for Drawdown
        equity_curve = pd.Series([self.initial_capital] + [self.initial_capital + trade_log_df["pnl"].iloc[:i+1].sum() for i in range(len(trade_log_df))])
        peak = equity_curve.expanding(min_periods=1).max()
        drawdown = (equity_curve - peak) / peak
        max_drawdown = drawdown.min() * 100

        avg_win = trade_log_df[trade_log_df["pnl"] > 0]["pnl"].mean() if winning_trades > 0 else 0
        avg_loss = trade_log_df[trade_log_df["pnl"] < 0]["pnl"].mean() if losing_trades > 0 else 0

        largest_win = trade_log_df["pnl"].max()
        largest_loss = trade_log_df["pnl"].min()

        # Streaks
        win_streak = 0
        max_win_streak = 0
        loss_streak = 0
        max_loss_streak = 0
        for pnl in trade_log_df["pnl"]:
            if pnl > 0:
                win_streak += 1
                loss_streak = 0
            elif pnl < 0:
                loss_streak += 1
                win_streak = 0
            else:
                win_streak = 0
                loss_streak = 0
            max_win_streak = max(max_win_streak, win_streak)
            max_loss_streak = max(max_loss_streak, loss_streak)

        metrics = {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "sharpe_ratio": 0.0, # Placeholder
            "max_drawdown": max_drawdown,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
        }
        return metrics

    def generate_equity_curve_chart(self, filename="equity_curve.png"):
        if not self.equity_data:
            print("No equity data to plot.")
            return None

        df_equity = pd.DataFrame(self.equity_data, columns=["timestamp", "equity"])
        df_equity = df_equity.set_index("timestamp")

        plt.figure(figsize=(12, 6))
        plt.plot(df_equity["equity"], label="Equity Curve", color="blue")
        plt.title("Equity Curve")
        plt.xlabel("Time")
        plt.ylabel("Equity Value")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        return filename

    def generate_daily_summary(self, trade_log_df, current_date):
        today_trades = trade_log_df[trade_log_df["exit_time"].dt.date == current_date.date()]
        metrics = self.calculate_performance_metrics(today_trades)
        summary = f"*Daily Performance Summary ({current_date.strftime("%Y-%m-%d")}):*\n\n"
        summary += f"Total PnL: {metrics["total_pnl"]:.2f}\n"
        summary += f"Total Trades: {metrics["total_trades"]}\n"
        summary += f"Win Rate: {metrics["win_rate"]:.2f}%\n"
        summary += f"Profit Factor: {metrics["profit_factor"]:.2f}\n"
        summary += f"Max Drawdown: {metrics["max_drawdown"]:.2f}%\n"
        return summary

    def generate_weekly_summary(self, trade_log_df, current_date):
        # Assuming current_date is a datetime object
        start_of_week = current_date - datetime.timedelta(days=current_date.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=6)

        week_trades = trade_log_df[(trade_log_df["exit_time"].dt.date >= start_of_week.date()) &
                                   (trade_log_df["exit_time"].dt.date <= end_of_week.date())]
        metrics = self.calculate_performance_metrics(week_trades)
        summary = f"*Weekly Performance Summary (Week of {start_of_week.strftime("%Y-%m-%d")}):*\n\n"
        summary += f"Total PnL: {metrics["total_pnl"]:.2f}\n"
        summary += f"Total Trades: {metrics["total_trades"]}\n"
        summary += f"Win Rate: {metrics["win_rate"]:.2f}%\n"
        summary += f"Profit Factor: {metrics["profit_factor"]:.2f}\n"
        summary += f"Max Drawdown: {metrics["max_drawdown"]:.2f}%\n"
        return summary
