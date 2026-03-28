import yfinance as yf
import pandas as pd
import datetime

class PreMarketScanner:
    def __init__(self, config):
        self.watchlist = config["watchlist"]
        self.pre_market_hours = config["scanner_params"]["pre_market_hours"]
        self.min_pre_market_volume = config["scanner_params"]["min_pre_market_volume"]
        self.min_gap_percentage = config["scanner_params"]["min_gap_percentage"]

    def _get_pre_market_data(self, symbol):
        ticker = yf.Ticker(symbol)
        # Fetching pre-market data directly from yfinance can be tricky and often requires
        # specific data providers or real-time APIs. For simplification, we'll simulate
        # pre-market data using historical data and assume a 'pre-market' close.
        # In a real bot, this would integrate with IBKR API for real-time pre-market data.
        
        # For demonstration, let's get extended hours data if available, or just recent daily data.
        # yfinance `get_history` with `prepost=True` can sometimes provide extended hours data.
        # However, it's not always reliable for specific pre-market price/volume.
        # We'll use a simplified approach for now.

        # Let's assume we can get the previous day's close and current pre-market price/volume
        # For actual pre-market data, you'd query IBKR API or a dedicated data provider.
        try:
            # Get last 2 days of 1-minute data, including pre/post market
            df = ticker.history(period="2d", interval="1m", prepost=True)
            if df.empty:
                return None, None, None

            # Assuming 'pre-market' is before regular market open (e.g., 9:30 AM ET)
            # This logic needs to be robust for different timezones and market hours
            market_open_time = datetime.time(9, 30)
            
            # Get previous day's close
            previous_day_close_df = df[df.index.time < market_open_time].iloc[-1:]
            if previous_day_close_df.empty:
                previous_day_close = df["Close"].iloc[-1] # Fallback to last available close
            else:
                previous_day_close = previous_day_close_df["Close"].iloc[-1]

            # Get current pre-market data (e.g., last available data point before market open)
            pre_market_df = df[df.index.time < market_open_time].iloc[-1:]
            if pre_market_df.empty:
                return None, None, None
            
            pre_market_price = pre_market_df["Close"].iloc[-1]
            pre_market_volume = pre_market_df["Volume"].iloc[-1]

            return previous_day_close, pre_market_price, pre_market_volume

        except Exception as e:
            print(f"Error fetching pre-market data for {symbol}: {e}")
            return None, None, None

    def scan_pre_market(self):
        movers = []
        for symbol in self.watchlist:
            prev_close, pm_price, pm_volume = self._get_pre_market_data(symbol)

            if prev_close is None or pm_price is None or pm_volume is None:
                continue

            gap_percentage = ((pm_price - prev_close) / prev_close) * 100

            if abs(gap_percentage) >= self.min_gap_percentage and pm_volume >= self.min_pre_market_volume:
                movers.append({
                    "symbol": symbol,
                    "prev_close": prev_close,
                    "pm_price": pm_price,
                    "pm_volume": pm_volume,
                    "gap_percentage": gap_percentage
                })
        
        # Sort by absolute gap percentage for ranking
        movers.sort(key=lambda x: abs(x["gap_percentage"]), reverse=True)
        return movers

    def generate_morning_briefing(self, movers):
        briefing = "*Morning Briefing - Top Pre-Market Movers:*

"
        if not movers:
            briefing += "No significant pre-market movers found."
            return briefing

        for mover in movers:
            briefing += f"*{mover["symbol"]}*: "
            briefing += f"Gap: {mover["gap_percentage"]:.2f}% "
            briefing += f"PM Price: {mover["pm_price"]:.2f} "
            briefing += f"PM Volume: {mover["pm_volume"]:,}
"
        return briefing
