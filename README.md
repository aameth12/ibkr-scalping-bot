# IBKR Scalping Bot - Major Upgrade

This project implements an advanced scalping trading bot for Interactive Brokers (IBKR) using Python. This major upgrade introduces a comprehensive suite of features, including enhanced strategy indicators, multi-timeframe analysis, robust risk management, intelligent filters, pre-market scanning, extensive Telegram bot enhancements, performance analytics, automated trade journaling, and a machine learning optimization layer. The bot is designed for traders seeking a sophisticated and automated approach to intraday trading.

## Project Structure

```
ibkr-scalping-bot/
├── README.md
├── requirements.txt
├── config.yaml
├── src/
│   ├── __init__.py
│   ├── bot.py              (Main bot logic and orchestration)
│   ├── strategy.py         (Enhanced scalping strategy with multiple indicators)
│   ├── multi_timeframe.py  (Multi-timeframe analysis and S/R identification)
│   ├── risk_manager.py     (Advanced risk management and circuit breaker)
│   ├── filters.py          (Correlation, news, and earnings filters)
│   ├── scanner.py          (Pre-market scanner for momentum)
│   ├── telegram_bot.py     (Telegram integration for commands and notifications)
│   ├── analytics.py        (Performance tracking and reporting)
│   ├── journal.py          (Automated trade journaling)
│   ├── ml_optimizer.py     (Machine learning optimization layer)
│   └── utils.py            (Helper functions)
├── backtest/
│   └── run_backtest.py     (Script to run backtests)
├── data/
│   └── (trade journal CSVs, equity curve data)
└── main.py                 (Entry point)
```

## Features

-   **Enhanced Strategy with More Indicators:** Builds upon the existing EMA 9/21 crossover by integrating MACD (12, 26, 9) for trend confirmation, Bollinger Bands (20, 2) for volatility and mean reversion signals, VWAP for intraday fair value, ATR (14) for dynamic stop-loss sizing, and Stochastic Oscillator (14, 3, 3) for overbought/oversold conditions. Signals are generated based on multiple indicator confirmations for higher quality entries.
-   **Multi-Timeframe Analysis:** Analyzes 5-minute, 15-minute, and 1-hour timeframes to identify significant support and resistance levels. Trades are only entered when signals align across multiple timeframes, using higher timeframes to confirm key S/R zones and the 5-minute timeframe for precise entry timing.
-   **Risk-to-Reward Management:** Enforces a minimum 1:2 risk-to-reward ratio, rejecting trades that do not meet this criterion. Stop-losses are dynamically calculated based on ATR. A trailing stop-loss mechanism moves up as the price moves favorably. Partial profit-taking closes 50% of the position at the first target (1:2 R:R), allowing the remaining 50% to ride with the trailing stop. The R:R ratio is displayed in all trade notifications.
-   **Circuit Breaker:** Automatically pauses the bot after 3 consecutive losses or when a maximum daily loss (10% of account balance) is hit. Telegram alerts are sent when the circuit breaker triggers, and the bot automatically resumes on the next trading day.
-   **Correlation Filter:** Prevents overexposure to correlated assets by avoiding opening too many positions in the same sector (e.g., limits to 2-3 positions in the same sector). Tracks and manages sector exposure.
-   **News/Earnings Filter:** Integrates with `yfinance` to check for upcoming earnings dates. The bot avoids trading a stock one day before and one day after its earnings announcement to mitigate event-driven volatility. Stocks with upcoming earnings are flagged.
-   **Pre-Market Scanner:** Before market open, the bot scans all watchlist stocks and ranks them by pre-market momentum (gap percentage, volume). A morning briefing with the top movers is automatically sent to Telegram.
-   **Telegram Bot Enhancements:** All existing commands (`/dashboard`, `/positions`, `/pnl`, `/status`, `/help`) are maintained. New commands include `/pause` and `/resume` for temporary bot control, `/watchlist` to view current symbols, and `/setparam` to change risk/strategy settings on the fly (e.g., `/setparam risk_per_trade 0.03`). Automated morning briefings and daily performance summaries are sent at market open and close, respectively. An equity curve chart, generated using `matplotlib`, is also sent to Telegram daily. Position open/close notifications include R:R ratio and clear exit reasons.
-   **Performance Analytics:** Tracks the equity curve over time and calculates key performance metrics such as win rate, profit factor, Sharpe ratio, maximum drawdown, average win/loss, and win/loss streaks. Daily and weekly summary reports are generated.
-   **Auto Trade Journal:** Logs every trade with comprehensive details including symbol, direction, entry price, exit price, P&L, R:R achieved, indicators at entry, timeframe alignment, and reason for exit. All data is saved to a CSV file for later analysis and is accessible via the Telegram `/journal` command.
-   **ML Optimization Layer:** Implements a simple scoring system to track which indicator combinations perform best for each stock over time. This layer learns from historical trade data to adjust signal confidence, potentially suppressing low-confidence signals based on past performance, without relying on heavy ML frameworks.

## Setup Guide

### 1. IBKR TWS/Gateway Setup

To connect your bot to Interactive Brokers, you need to have either the Trader Workstation (TWS) or IB Gateway running.

1.  **Download and Install:** Download and install [Trader Workstation (TWS)](https://www.interactivebrokers.com/en/index.php?f=16040) or [IB Gateway](https://www.interactivebrokers.com/en/index.php?f=16457).
2.  **Configuration in TWS/Gateway:**
    *   Open TWS/Gateway and log in.
    *   Go to `File` -> `Global Configuration`.
    *   Navigate to `API` -> `Settings`.
    *   Ensure `Enable ActiveX and Socket Clients` is checked.
    *   Note down the `Socket Port` (default is 7496 for live, 7497 for paper). This should match the `port` in your `config.yaml`.
    *   Add `127.0.0.1` to `Trusted IP Addresses`.
    *   Uncheck `Read-Only API` if you intend to place trades.

### 2. Python Dependencies

Navigate to the `ibkr-scalping-bot` directory and install the required Python packages:

```bash
cd ibkr-scalping-bot
sudo pip3 install -r requirements.txt
```

### 3. Telegram Bot Setup

To receive notifications and control your bot via Telegram:

1.  **Create a New Bot:**
    *   Open Telegram and search for `@BotFather`.
    *   Start a chat with BotFather and send `/newbot`.
    *   Follow the instructions to choose a name and username for your bot. BotFather will give you an **API Token**.
2.  **Get your Chat ID:**
    *   Start a chat with your newly created bot.
    *   Send any message to your bot (e.g., "Hello").
    *   Open your web browser and go to `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` (replace `<YOUR_BOT_TOKEN>` with your bot's API token).
    *   Look for the `"chat"` object in the JSON response. The `"id"` field within this object is your `chat_id`.
3.  **Update `config.yaml`:** Add your `bot_token` and `chat_id` to the `telegram_settings` section in `config.yaml`.

### 4. Configuration (`config.yaml`)

Edit the `config.yaml` file to set up your bot's parameters. A comprehensive example is provided below, reflecting all new parameters:

```yaml
watchlist:
  - AAPL
  - MSFT
  - GOOGL
  - AMZN
  - TSLA
  - NVDA
  - META
  - AMD
  - SPY
  - QQQ
  - SMCI
  - INTC
  - T
  - SOFI
  - BAC
  - NFLX
  - F
  - AAL
  - NVO
  - DELL
ibkr_connection:
  host: 127.0.0.1
  port: 7497 # 7497 for paper trading, 7496 for live trading
  client_id: 1 # Unique client ID for your connection
strategy_params:
  ema_fast: 9
  ema_slow: 21
  rsi_period: 14
  rsi_overbought: 70
  rsi_oversold: 30
  volume_spike_multiplier: 1.5
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  bb_window: 20
  bb_std: 2
  atr_window: 14
  stoch_k_period: 14
  stoch_d_period: 3
  stoch_smooth_period: 3
multi_timeframe_params:
  timeframes:
    - 5min
    - 15min
    - 1h
  sr_window: 10
  sr_tolerance_factor: 0.5
risk_params:
  risk_per_trade: 0.05 # Percentage of account balance to risk per trade
  max_daily_loss_pct: 0.10 # Maximum percentage of account balance allowed to lose per day
  min_rr_ratio: 2.0 # Minimum Risk-to-Reward ratio required for a trade
  partial_profit_target_rr: 2.0 # R:R ratio for the first partial profit target
  circuit_breaker_consecutive_losses: 3 # Number of consecutive losses to trigger circuit breaker
  atr_multiplier_stop_loss: 2.0 # Multiplier for ATR to set initial stop loss
  trailing_stop_atr_multiplier: 1.0 # Multiplier for ATR to trail stop loss
  trailing_stop_pct: 0.005 # Percentage for trailing stop loss
filter_params:
  max_correlated_positions: 2 # Maximum number of open positions allowed in the same sector
  earnings_avoid_days: 1 # Days before/after earnings to avoid trading
scanner_params:
  pre_market_hours: "04:00-09:30" # Example pre-market hours for scanning
  min_pre_market_volume: 100000 # Minimum pre-market volume for a stock to be considered a mover
  min_gap_percentage: 2.0 # Minimum gap percentage for a stock to be considered a mover
analytics_params:
  trade_log_path: "data/trade_journal.csv"
  equity_curve_path: "data/equity_curve.csv"
  initial_capital: 10000.0 # Initial capital for analytics calculations
journal_params:
  journal_file: "data/trade_journal.csv"
ml_optimizer_params:
  min_trades_for_optimization: 20 # Minimum trades required for ML optimizer to start analyzing
  signal_confidence_threshold: 0.6 # Confidence threshold for ML optimizer to allow a signal
telegram_settings:
  bot_token: "YOUR_TELEGRAM_BOT_TOKEN" # Replace with your Telegram bot token
  chat_id: "YOUR_TELEGRAM_CHAT_ID"   # Replace with your Telegram chat ID
mode: paper # Set to 'paper' for paper trading, 'live' for live trading
```

### 5. Running Backtests

To test your strategy against historical data, use the `run_backtest.py` script:

```bash
python3 ibkr-scalping-bot/backtest/run_backtest.py --symbol AAPL --start_date 2023-01-01 --end_date 2023-03-01
```

This will run a backtest for AAPL between the specified dates and output the results to the console and `backtest_trades_AAPL.csv` and `backtest_account_history_AAPL.csv` files.

### 6. Paper Trading / Going Live

1.  **Ensure TWS/Gateway is running** and configured as described in step 1.
2.  **Set `mode` in `config.yaml`** to `paper` for paper trading or `live` for live trading.
3.  **Run the bot:**

    ```bash
    python3 ibkr-scalping-bot/main.py
    ```

    The bot will connect to IBKR, start monitoring the watchlist, and send notifications to your Telegram chat.

## Telegram Commands

-   `/dashboard`: Shows a summary of the bot's status, account balance, P&L, and open positions.
-   `/status`: Provides a concise overview of the bot's operational status, including whether it's paused by the circuit breaker.
-   `/positions`: Lists all currently open trading positions.
-   `/pnl`: Displays today's and all-time profit and loss figures.
-   `/pause`: Temporarily halts all new trading activities. Existing positions will still be managed.
-   `/resume`: Resumes trading activities if the bot was paused manually.
-   `/watchlist`: Displays the current list of symbols the bot is monitoring.
-   `/setparam <param_name> <value>`: Allows dynamic adjustment of certain bot parameters (e.g., risk settings). Example: `/setparam risk_per_trade 0.03`.
-   `/journal`: Provides a summary of the latest trade journal entries.
-   `/help`: Shows a list of all available commands and their descriptions.

## Important Notes

-   **Risk Management:** Trading involves significant risk. The provided risk management parameters are examples; adjust them according to your personal risk tolerance and financial situation.
-   **Market Data:** Ensure you have appropriate market data subscriptions with IBKR for the symbols you intend to trade. Without proper subscriptions, the bot may not receive necessary data.
-   **Testing:** Always thoroughly test your bot in paper trading mode before deploying it to a live account.
-   **Disclaimer:** This bot is provided for educational and informational purposes only. Do not use it for live trading without understanding the risks involved and making necessary modifications. The author is not responsible for any financial losses incurred.
