import pandas as pd
import numpy as np

class MLOptimizer:
    def __init__(self, config):
        self.journal_file = config["journal_params"]["journal_file"]
        self.min_trades_for_optimization = config["ml_optimizer_params"]["min_trades_for_optimization"]
        self.signal_confidence_threshold = config["ml_optimizer_params"]["signal_confidence_threshold"]
        self.indicator_weights = {}

    def _load_trade_journal(self):
        try:
            return pd.read_csv(self.journal_file)
        except FileNotFoundError:
            return pd.DataFrame()

    def analyze_indicator_performance(self):
        journal_df = self._load_trade_journal()
        if journal_df.empty:
            return

        # Convert 'indicators_at_entry' from string representation of dict to actual dict
        # This assumes indicators_at_entry is stored as a string like "{'ema_cross': True, 'macd_cross': False}"
        # Using literal_eval for safer parsing of string representations of Python literals
        import ast
        journal_df["indicators_at_entry_dict"] = journal_df["indicators_at_entry"].apply(lambda x: ast.literal_eval(x) if pd.notna(x) else {})

        # Flatten the indicator dictionaries into separate columns
        indicators_df = pd.json_normalize(journal_df["indicators_at_entry_dict"])
        combined_df = pd.concat([journal_df, indicators_df], axis=1)

        # Calculate win rate for each indicator combination
        # This is a simplified approach. A more robust method would involve
        # analyzing combinations of indicators.
        for indicator_col in indicators_df.columns:
            # Filter trades where this indicator was active
            trades_with_indicator = combined_df[combined_df[indicator_col] == True]
            if len(trades_with_indicator) >= self.min_trades_for_optimization:
                wins = trades_with_indicator[trades_with_indicator["pnl"] > 0].shape[0]
                total = trades_with_indicator.shape[0]
                win_rate = wins / total if total > 0 else 0
                self.indicator_weights[indicator_col] = win_rate

        # Optionally, store these weights or use them to adjust signal confidence
        print("Indicator Weights:", self.indicator_weights)

    def get_signal_confidence(self, symbol, current_indicators):
        # This method would take the current indicator states and return a confidence score
        # based on historical performance of those indicators for the given symbol.
        # For now, a very basic implementation.
        
        confidence = 0.5 # Default confidence
        active_indicators = [ind for ind, value in current_indicators.items() if value]

        if not active_indicators:
            return confidence

        # Average win rate of active indicators
        total_win_rate = 0
        count = 0
        for ind in active_indicators:
            if ind in self.indicator_weights:
                total_win_rate += self.indicator_weights[ind]
                count += 1
        
        if count > 0:
            confidence = total_win_rate / count

        return confidence

    def adjust_signal_based_on_confidence(self, signal, confidence):
        if confidence < self.signal_confidence_threshold:
            return 0 # Suppress signal if confidence is too low
        return signal
