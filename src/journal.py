import pandas as pd
import os
import datetime

class TradeJournal:
    def __init__(self, config):
        self.journal_file = config["journal_params"]["journal_file"]
        self.columns = ["timestamp", "symbol", "direction", "entry_price", "exit_price",
                        "shares", "pnl", "rr_achieved", "indicators_at_entry",
                        "timeframe_alignment", "exit_reason", "notes"]
        self._initialize_journal()

    def _initialize_journal(self):
        if not os.path.exists(self.journal_file):
            df = pd.DataFrame(columns=self.columns)
            df.to_csv(self.journal_file, index=False)

    def log_trade(self, trade_data):
        # trade_data should be a dictionary with keys matching self.columns
        # Ensure all columns are present, fill missing with None or default
        for col in self.columns:
            if col not in trade_data:
                trade_data[col] = None
        
        # Convert timestamp to string for CSV storage if it's a datetime object
        if isinstance(trade_data["timestamp"], datetime.datetime):
            trade_data["timestamp"] = trade_data["timestamp"].isoformat()

        df = pd.DataFrame([trade_data], columns=self.columns)
        df.to_csv(self.journal_file, mode=\'a\', header=False, index=False)

    def get_journal(self):
        return pd.read_csv(self.journal_file)

    def get_trades_for_symbol(self, symbol):
        df = self.get_journal()
        return df[df["symbol"].str.upper() == symbol.upper()]

    def get_trades_by_date(self, date_str):
        df = self.get_journal()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df[df["timestamp"].dt.date == pd.to_datetime(date_str).date()]
