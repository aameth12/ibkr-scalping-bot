# IBKR Momentum Scalping Bot

This project implements a momentum scalping trading bot for Interactive Brokers (IBKR) using Python. The bot utilizes RSI and EMA crossovers, along with volume spike detection, to identify quick price movements in US stocks and ETFs. It's designed for beginner traders with an aggressive risk tolerance.

## Project Structure

```
ibkr-scalping-bot/
├── README.md
├── requirements.txt
├── config.yaml
├── src/
│   ├── __init__.py
│   ├── bot.py          (main bot logic)
│   ├── strategy.py     (momentum scalping strategy)
│   ├── risk_manager.py (risk management)
│   ├── backtester.py   (backtesting module)
│   ├── telegram_bot.py (telegram notifications)
│   └── utils.py        (helper functions)
├── backtest/
│   └── run_backtest.py (script to run backtests)
└── main.py             (entry point)
```

## Features

- **Momentum Scalping Strategy:** Implements EMA 9/21 crossover, RSI confirmation, and volume spike detection for BUY/SELL signals.
- **Risk Management:** Position sizing based on account balance and risk percentage, max daily loss tracking, and dynamic stop-loss/take-profit calculation.
- **IBKR Integration:** Connects to IBKR TWS/Gateway using `ib_insync` to subscribe to market data, execute trades, and manage positions with bracket orders.
- **Telegram Notifications:** Provides real-time updates on trades, positions, and overall bot status via a Telegram bot.
- **Backtesting Module:** Allows simulation of the strategy using historical data from `yfinance` and calculates key performance metrics.

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
    *   Send any message to your bot (e.g., 
"Hello").
    *   Open your web browser and go to `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` (replace `<YOUR_BOT_TOKEN>` with your bot's API token).
    *   Look for the `"chat"` object in the JSON response. The `"id"` field within this object is your `chat_id`.
3.  **Update `config.yaml`:** Add your `bot_token` and `chat_id` to the `telegram_settings` section in `config.yaml`.

### 4. Configuration (`config.yaml`)

Edit the `config.yaml` file to set up your bot's parameters:

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
risk_params:
  risk_per_trade: 0.05 # 5% of account balance per trade
  max_daily_loss: 0.10 # 10% max daily loss
  stop_loss_pct: 0.02 # 2% stop loss from entry price
  take_profit_pct: 0.04 # 4% take profit from entry price
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
-   `/status`: Provides a concise overview of the bot's operational status.
-   `/positions`: Lists all currently open trading positions.
-   `/pnl`: Displays today's and all-time profit and loss figures.
-   `/start_bot`: Initiates the trading bot if it is currently stopped.
-   `/stop_bot`: Halts all trading activities and attempts to close open orders.
-   `/help`: Shows a list of all available commands and their descriptions.

## Important Notes

-   **Risk Management:** Trading involves significant risk. The provided risk management parameters are examples; adjust them according to your personal risk tolerance and financial situation.
-   **Market Data:** Ensure you have appropriate market data subscriptions with IBKR for the symbols you intend to trade. Without proper subscriptions, the bot may not receive necessary data.
-   **Testing:** Always thoroughly test your bot in paper trading mode before deploying it to a live account.
-   **Disclaimer:** This bot is provided for educational and informational purposes only. Do not use it for live trading without understanding the risks involved and making necessary modifications. The author is not responsible for any financial losses incurred.
