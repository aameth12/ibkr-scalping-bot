import pandas as pd
import numpy as np
import ta

class MultiTimeframeAnalysis:
    def __init__(self, config):
        self.timeframes = config["multi_timeframe_params"]["timeframes"]
        self.sr_window = config["multi_timeframe_params"]["sr_window"]
        self.sr_tolerance_factor = config["multi_timeframe_params"]["sr_tolerance_factor"]

    def _resample_dataframe(self, df, timeframe):
        # Resample OHLCV data to the target timeframe
        ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        return df.resample(timeframe).apply(ohlc_dict).dropna()

    def _identify_support_resistance(self, df):
        # Simple method to identify local peaks and troughs as S/R levels
        df["support"] = np.nan
        df["resistance"] = np.nan

        # Ensure enough data for rolling window
        if len(df) < 2 * self.sr_window + 1:
            return df

        for i in range(self.sr_window, len(df) - self.sr_window):
            # Check for resistance (peak)
            if df["high"].iloc[i] == df["high"].iloc[i - self.sr_window : i + self.sr_window + 1].max():
                df["resistance"].iloc[i] = df["high"].iloc[i]
            # Check for support (trough)
            if df["low"].iloc[i] == df["low"].iloc[i - self.sr_window : i + self.sr_window + 1].min():
                df["support"].iloc[i] = df["low"].iloc[i]
        return df

    def analyze_timeframes(self, data):
        multi_timeframe_data = {}
        for tf in self.timeframes:
            resampled_df = self._resample_dataframe(data.copy(), tf)
            multi_timeframe_data[tf] = self._identify_support_resistance(resampled_df)
        return multi_timeframe_data

    def confirm_signal_with_timeframes(self, current_5min_df, multi_timeframe_data, signal_type):
        current_price = current_5min_df['close'].iloc[-1]
        atr_5min = current_5min_df['atr'].iloc[-1] if 'atr' in current_5min_df.columns else 0.01 # Use ATR for tolerance

        for tf, df_tf in multi_timeframe_data.items():
            if tf == '5min': # Skip 5min as it's the entry timeframe
                continue

            if df_tf.empty:
                return False # No data for this timeframe

            latest_tf_candle = df_tf.iloc[-1]

            tf_is_up_candle = latest_tf_candle['close'] > latest_tf_candle['open']
            tf_is_down_candle = latest_tf_candle['close'] < latest_tf_candle['open']

            # Get recent S/R levels from the higher timeframe
            recent_supports = df_tf['support'].dropna().tail(5).values
            recent_resistances = df_tf['resistance'].dropna().tail(5).values

            if signal_type == 1: # Buy signal
                # Higher timeframe candle should be bullish or neutral-to-bullish
                if not tf_is_up_candle and not (latest_tf_candle['close'] >= latest_tf_candle['open'] and latest_tf_candle['close'] > latest_tf_candle['low'] + (latest_tf_candle['high'] - latest_tf_candle['low']) * 0.25):
                    return False

                # Current price should be above or near a higher timeframe support
                support_aligned = False
                for s_level in recent_supports:
                    if current_price >= s_level - (atr_5min * self.sr_tolerance_factor):
                        support_aligned = True
                        break
                if not support_aligned:
                    return False

            elif signal_type == -1: # Sell signal
                # Higher timeframe candle should be bearish or neutral-to-bearish
                if not tf_is_down_candle and not (latest_tf_candle['close'] <= latest_tf_candle['open'] and latest_tf_candle['close'] < latest_tf_candle['high'] - (latest_tf_candle['high'] - latest_tf_candle['low']) * 0.25):
                    return False

                # Current price should be below or near a higher timeframe resistance
                resistance_aligned = False
                for r_level in recent_resistances:
                    if current_price <= r_level + (atr_5min * self.sr_tolerance_factor):
                        resistance_aligned = True
                        break
                if not resistance_aligned:
                    return False

        return True # All higher timeframes align with the signal
