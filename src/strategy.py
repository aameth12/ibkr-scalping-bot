import pandas as pd
import ta

class MomentumScalpingStrategy:
    def __init__(self, config):
        self.ema_fast_period = config['strategy_params']['ema_fast']
        self.ema_slow_period = config['strategy_params']['ema_slow']
        self.rsi_period = config['strategy_params']['rsi_period']
        self.rsi_overbought = config['strategy_params']['rsi_overbought']
        self.rsi_oversold = config['strategy_params']['rsi_oversold']
        self.volume_spike_multiplier = config['strategy_params']['volume_spike_multiplier']

    def generate_signals(self, df):
        # Calculate EMAs
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=self.ema_fast_period)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=self.ema_slow_period)

        # Calculate RSI
        df['rsi'] = ta.momentum.rsi(df['close'], window=self.rsi_period)

        # Calculate Volume Spike
        df['volume_ma'] = df['volume'].rolling(window=self.rsi_period).mean()
        df['volume_spike'] = df['volume'] > (df['volume_ma'] * self.volume_spike_multiplier)

        # Generate signals
        df['signal'] = 0
        # Buy signal: EMA fast crosses above EMA slow, RSI is not overbought, and volume spike
        df.loc[(df['ema_fast'].shift(1) < df['ema_slow'].shift(1)) &
               (df['ema_fast'] > df['ema_slow']) &
               (df['rsi'] < self.rsi_overbought) &
               (df['volume_spike'] == True),
               'signal'] = 1

        # Sell signal: EMA fast crosses below EMA slow, RSI is not oversold, and volume spike
        df.loc[(df['ema_fast'].shift(1) > df['ema_slow'].shift(1)) &
               (df['ema_fast'] < df['ema_slow']) &
               (df['rsi'] > self.rsi_oversold) &
               (df['volume_spike'] == True),
               'signal'] = -1

        return df
