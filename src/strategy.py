import pandas as pd
import ta

class EnhancedScalpingStrategy:
    def __init__(self, config):
        self.ema_fast_period = config["strategy_params"]["ema_fast"]
        self.ema_slow_period = config["strategy_params"]["ema_slow"]
        self.macd_fast_period = config["strategy_params"]["macd_fast"]
        self.macd_slow_period = config["strategy_params"]["macd_slow"]
        self.macd_signal_period = config["strategy_params"]["macd_signal"]
        self.bb_window = config["strategy_params"]["bb_window"]
        self.bb_std = config["strategy_params"]["bb_std"]
        self.atr_window = config["strategy_params"]["atr_window"]
        self.stoch_k_period = config["strategy_params"]["stoch_k_period"]
        self.stoch_d_period = config["strategy_params"]["stoch_d_period"]
        self.stoch_smooth_period = config["strategy_params"]["stoch_smooth_period"]
        self.rsi_period = config["strategy_params"]["rsi_period"]
        self.rsi_overbought = config["strategy_params"]["rsi_overbought"]
        self.rsi_oversold = config["strategy_params"]["rsi_oversold"]
        self.volume_spike_multiplier = config["strategy_params"]["volume_spike_multiplier"]

    def generate_signals(self, df):
        # Ensure DataFrame is sorted by time
        df = df.sort_index()

        # Calculate EMAs
        df["ema_fast"] = ta.trend.ema_indicator(df["close"], window=self.ema_fast_period)
        df["ema_slow"] = ta.trend.ema_indicator(df["close"], window=self.ema_slow_period)

        # Calculate MACD
        macd = ta.trend.MACD(df["close"], window_fast=self.macd_fast_period, window_slow=self.macd_slow_period, window_sign=self.macd_signal_period)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_diff"] = macd.macd_diff()

        # Calculate Bollinger Bands
        bb = ta.volatility.BollingerBands(df["close"], window=self.bb_window, window_dev=self.bb_std)
        df["bb_bbm"] = bb.bollinger_mavg()
        df["bb_bbh"] = bb.bollinger_hband()
        df["bb_bbl"] = bb.bollinger_lband()

        # Calculate VWAP (requires 'high', 'low', 'close', 'volume' columns)
        # This is a simplified VWAP calculation, a more accurate one would require tick data or specific intraday aggregation
        # For real-time, VWAP needs to be calculated cumulatively from the start of the trading day.
        # Here, we'll calculate a rolling VWAP for demonstration, assuming 'volume' is available.
        # A proper VWAP calculation would involve (price * volume).cumsum() / volume.cumsum() from market open.
        # For historical bars, a simple approximation is often used.
        df["vwap"] = (df["volume"] * (df["high"] + df["low"] + df["close"]) / 3).cumsum() / df["volume"].cumsum()

        # Calculate ATR
        df["atr"] = ta.volatility.average_true_range(df["high"], df["low"], df["close"], window=self.atr_window)

        # Calculate Stochastic Oscillator
        stoch = ta.momentum.StochasticOscillator(df["high"], df["low"], df["close"], window=self.stoch_k_period, smooth_window=self.stoch_d_period)
        df["stoch_k"] = stoch.stoch()
        df["stoch_d"] = stoch.stoch_signal()

        # Calculate RSI (keeping existing)
        df["rsi"] = ta.momentum.rsi(df["close"], window=self.rsi_period)

        # Calculate Volume Spike (keeping existing)
        df["volume_ma"] = df["volume"].rolling(window=self.rsi_period).mean()
        df["volume_spike"] = df["volume"] > (df["volume_ma"] * self.volume_spike_multiplier)

        # Generate signals based on multiple indicator confirmations
        df["signal"] = 0

        # Buy signal conditions:
        # 1. EMA Crossover: EMA fast crosses above EMA slow
        ema_buy_condition = (df["ema_fast"].shift(1) < df["ema_slow"].shift(1)) & (df["ema_fast"] > df["ema_slow"])
        # 2. MACD Confirmation: MACD line crosses above signal line and MACD is positive (or increasing)
        macd_buy_condition = (df["macd"].shift(1) < df["macd_signal"].shift(1)) & (df["macd"] > df["macd_signal"]) & (df["macd"] > 0)
        # 3. Bollinger Band Confirmation: Price is near lower band or crossing above it from below
        bb_buy_condition = (df["close"] < df["bb_bbm"]) & (df["close"] > df["bb_bbl"])
        # 4. Stochastic Confirmation: %K crosses above %D and both are below 20 (oversold)
        stoch_buy_condition = (df["stoch_k"].shift(1) < df["stoch_d"].shift(1)) & (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"] < 20)
        # 5. RSI Confirmation: RSI is not overbought
        rsi_buy_condition = (df["rsi"] < self.rsi_overbought)
        # 6. Volume Spike: Confirm strong interest
        volume_buy_condition = (df["volume_spike"] == True)
        # 7. Price above VWAP
        vwap_buy_condition = (df["close"] > df["vwap"])

        # Combined Buy Signal
        df.loc[ema_buy_condition &
               macd_buy_condition &
               bb_buy_condition &
               stoch_buy_condition &
               rsi_buy_condition &
               volume_buy_condition &
               vwap_buy_condition,
               "signal"] = 1

        # Sell signal conditions:
        # 1. EMA Crossover: EMA fast crosses below EMA slow
        ema_sell_condition = (df["ema_fast"].shift(1) > df["ema_slow"].shift(1)) & (df["ema_fast"] < df["ema_slow"])
        # 2. MACD Confirmation: MACD line crosses below signal line and MACD is negative (or decreasing)
        macd_sell_condition = (df["macd"].shift(1) > df["macd_signal"].shift(1)) & (df["macd"] < df["macd_signal"]) & (df["macd"] < 0)
        # 3. Bollinger Band Confirmation: Price is near upper band or crossing below it from above
        bb_sell_condition = (df["close"] > df["bb_bbm"]) & (df["close"] < df["bb_bbh"])
        # 4. Stochastic Confirmation: %K crosses below %D and both are above 80 (overbought)
        stoch_sell_condition = (df["stoch_k"].shift(1) > df["stoch_d"].shift(1)) & (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"] > 80)
        # 5. RSI Confirmation: RSI is not oversold
        rsi_sell_condition = (df["rsi"] > self.rsi_oversold)
        # 6. Volume Spike: Confirm strong interest
        volume_sell_condition = (df["volume_spike"] == True)
        # 7. Price below VWAP
        vwap_sell_condition = (df["close"] < df["vwap"])

        # Combined Sell Signal
        df.loc[ema_sell_condition &
               macd_sell_condition &
               bb_sell_condition &
               stoch_sell_condition &
               rsi_sell_condition &
               volume_sell_condition &
               vwap_sell_condition,
               "signal"] = -1

        return df
