import yfinance as yf
import pandas as pd
import datetime

class Filters:
    def __init__(self, config):
        self.watchlist = config["watchlist"]
        self.max_correlated_positions = config["filter_params"]["max_correlated_positions"]
        self.earnings_avoid_days = config["filter_params"]["earnings_avoid_days"]
        self.sector_data = self._load_sector_data() # A dictionary mapping symbol to sector
        self.earnings_dates = {}

    def _load_sector_data(self):
        # In a real scenario, this would load from a CSV or API
        # For now, a hardcoded example for the watchlist
        sector_map = {
            "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services",
            "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary", "NVDA": "Technology",
            "META": "Communication Services", "AMD": "Technology", "SPY": "ETF", "QQQ": "ETF",
            "SMCI": "Technology", "INTC": "Technology", "T": "Communication Services",
            "SOFI": "Financials", "BAC": "Financials", "NFLX": "Communication Services",
            "F": "Consumer Discretionary", "AAL": "Industrials", "NVO": "Healthcare",
            "DELL": "Technology"
        }
        return sector_map

    def _fetch_earnings_dates(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar
            if calendar is not None and not calendar.empty:
                # Earnings Date is usually the first column, first row
                earnings_date_str = calendar.iloc[0, 0]
                # yfinance returns datetime objects for earnings dates
                return pd.to_datetime(earnings_date_str).date()
        except Exception as e:
            print(f"Error fetching earnings for {symbol}: {e}")
        return None

    def update_earnings_dates(self):
        for symbol in self.watchlist:
            self.earnings_dates[symbol] = self._fetch_earnings_dates(symbol)

    def is_near_earnings(self, symbol, current_date):
        if symbol not in self.earnings_dates or self.earnings_dates[symbol] is None:
            return False

        earnings_date = self.earnings_dates[symbol]
        delta = abs((earnings_date - current_date).days)
        return delta <= self.earnings_avoid_days

    def get_correlated_symbols(self, symbol):
        # This is a simplified correlation. In a real scenario, you would calculate
        # historical price correlation or use a more sophisticated method.
        # For now, we\'ll consider symbols in the same sector as correlated.
        if symbol not in self.sector_data:
            return []
        
        target_sector = self.sector_data[symbol]
        correlated = [s for s, sector in self.sector_data.items() if sector == target_sector and s != symbol]
        return correlated

    def check_correlation_filter(self, symbol, open_positions):
        if symbol not in self.sector_data:
            return True # No sector data, allow trade

        target_sector = self.sector_data[symbol]
        sector_positions_count = 0
        for pos_symbol in open_positions:
            if pos_symbol in self.sector_data and self.sector_data[pos_symbol] == target_sector:
                sector_positions_count += 1
        
        return sector_positions_count < self.max_correlated_positions

    def get_sector_exposure(self, open_positions):
        exposure = {}
        for symbol in open_positions:
            sector = self.sector_data.get(symbol, "Unknown")
            exposure[sector] = exposure.get(sector, 0) + 1
        return exposure
