import pandas as pd
import numpy as np
import datetime

class RiskManager:
    def __init__(self, config):
        self.risk_per_trade = config["risk_params"]["risk_per_trade"]
        self.max_daily_loss_pct = config["risk_params"]["max_daily_loss_pct"]
        self.min_rr_ratio = config["risk_params"]["min_rr_ratio"]
        self.partial_profit_target_rr = config["risk_params"]["partial_profit_target_rr"]
        self.circuit_breaker_consecutive_losses = config["risk_params"]["circuit_breaker_consecutive_losses"]
        self.atr_multiplier_stop_loss = config["risk_params"]["atr_multiplier_stop_loss"]
        self.trailing_stop_atr_multiplier = config["risk_params"]["trailing_stop_atr_multiplier"]
        self.trailing_stop_pct = config["risk_params"]["trailing_stop_pct"]

        self.account_balance = 0.0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.bot_paused = False
        self.last_trading_day = None
        self.bot_paused_alert_sent = False # To prevent spamming alerts

    def set_account_balance(self, balance):
        self.account_balance = balance

    def update_daily_pnl(self, pnl):
        self.daily_pnl += pnl

    def check_circuit_breaker(self, current_date):
        if self.last_trading_day is None or self.last_trading_day < current_date:
            # New trading day, reset circuit breaker
            self.consecutive_losses = 0
            self.daily_pnl = 0.0
            self.bot_paused = False
            self.last_trading_day = current_date
            self.bot_paused_alert_sent = False

        if self.bot_paused:
            return True, "Bot paused by circuit breaker."

        # Check max daily loss
        if self.account_balance > 0 and self.daily_pnl < -(self.account_balance * self.max_daily_loss_pct):
            self.bot_paused = True
            return True, f"Circuit Breaker: Max daily loss ({self.max_daily_loss_pct*100:.2f}%) hit. Daily PnL: {self.daily_pnl:.2f}"

        # Check consecutive losses (logic for updating consecutive_losses will be in trade execution)
        if self.consecutive_losses >= self.circuit_breaker_consecutive_losses:
            self.bot_paused = True
            return True, f"Circuit Breaker: {self.consecutive_losses} consecutive losses."

        return False, ""

    def record_trade_result(self, pnl):
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        self.update_daily_pnl(pnl)

    def calculate_risk_reward_levels(self, entry_price, atr_value, signal_type):
        if atr_value <= 0:
            return None, None, None, None, None, "ATR value must be positive."

        stop_loss_distance = atr_value * self.atr_multiplier_stop_loss

        if signal_type == 1: # Long position
            stop_loss_price = entry_price - stop_loss_distance
            # Target 1 is min_rr_ratio * stop_loss_distance away
            target_1_price = entry_price + (stop_loss_distance * self.min_rr_ratio)
            # Partial profit target
            partial_profit_price = entry_price + (stop_loss_distance * self.partial_profit_target_rr)
        elif signal_type == -1: # Short position
            stop_loss_price = entry_price + stop_loss_distance
            # Target 1 is min_rr_ratio * stop_loss_distance away
            target_1_price = entry_price - (stop_loss_distance * self.min_rr_ratio)
            # Partial profit target
            partial_profit_price = entry_price - (stop_loss_distance * self.partial_profit_target_rr)
        else:
            return None, None, None, None, None, "Invalid signal type."

        # Ensure stop loss is not too close to entry (e.g., 0 distance)
        if abs(entry_price - stop_loss_price) < 0.01:
            return None, None, None, None, None, "Stop loss too close to entry."

        # Calculate R:R for the first target
        risk_amount = abs(entry_price - stop_loss_price)
        reward_amount = abs(target_1_price - entry_price)
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

        if rr_ratio < self.min_rr_ratio:
            return None, None, None, None, None, f"Risk-to-Reward ratio ({rr_ratio:.2f}) is below minimum required ({self.min_rr_ratio:.2f})."

        return stop_loss_price, target_1_price, partial_profit_price, rr_ratio, risk_amount, None

    def calculate_position_size(self, entry_price, risk_amount):
        if self.account_balance == 0 or risk_amount <= 0:
            return 0

        max_risk_capital = self.account_balance * self.risk_per_trade
        num_shares = int(max_risk_capital / risk_amount)

        return num_shares

    def update_trailing_stop(self, current_price, entry_price, initial_stop_loss, signal_type, atr_value, current_trailing_stop=None):
        if signal_type == 1: # Long position
            if current_trailing_stop is None:
                # Initial trailing stop is the initial stop loss
                new_trailing_stop = initial_stop_loss
            else:
                # Trail by ATR or percentage, whichever is tighter (or configurable)
                atr_trail = current_price - (atr_value * self.trailing_stop_atr_multiplier)
                pct_trail = current_price * (1 - self.trailing_stop_pct)
                new_trailing_stop = max(current_trailing_stop, min(atr_trail, pct_trail))
                # Ensure trailing stop doesn\'t move down once it\'s above initial_stop_loss
                new_trailing_stop = max(new_trailing_stop, initial_stop_loss)

        elif signal_type == -1: # Short position
            if current_trailing_stop is None:
                # Initial trailing stop is the initial stop loss
                new_trailing_stop = initial_stop_loss
            else:
                # Trail by ATR or percentage, whichever is tighter (or configurable)
                atr_trail = current_price + (atr_value * self.trailing_stop_atr_multiplier)
                pct_trail = current_price * (1 + self.trailing_stop_pct)
                new_trailing_stop = min(current_trailing_stop, max(atr_trail, pct_trail))
                # Ensure trailing stop doesn\'t move up once it\'s below initial_stop_loss
                new_trailing_stop = min(new_trailing_stop, initial_stop_loss)
        else:
            return current_trailing_stop

        return new_trailing_stop

    def pause_bot(self):
        self.bot_paused = True

    def resume_bot(self):
        self.bot_paused = False
