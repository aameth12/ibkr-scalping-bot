class RiskManager:
    def __init__(self, config):
        self.risk_per_trade = config['risk_params']['risk_per_trade']
        self.max_daily_loss = config['risk_params']['max_daily_loss']
        self.stop_loss_pct = config['risk_params']['stop_loss_pct']
        self.take_profit_pct = config['risk_params']['take_profit_pct']
        self.account_balance = 0.0 # This will be updated by the bot
        self.daily_pnl = 0.0

    def set_account_balance(self, balance):
        self.account_balance = balance

    def update_daily_pnl(self, pnl):
        self.daily_pnl += pnl

    def check_max_daily_loss(self):
        return self.daily_pnl < -(self.account_balance * self.max_daily_loss)

    def calculate_position_size(self, price):
        if self.account_balance == 0:
            return 0
        # Calculate the maximum amount to risk per trade
        max_risk_amount = self.account_balance * self.risk_per_trade
        
        # Calculate the stop loss amount in currency based on percentage
        stop_loss_amount = price * self.stop_loss_pct
        
        if stop_loss_amount == 0:
            return 0

        # Calculate the number of shares based on max risk and stop loss amount
        # (max_risk_amount / stop_loss_amount) gives the number of shares if each share's stop loss is stop_loss_amount
        num_shares = int(max_risk_amount / stop_loss_amount)
        
        return num_shares

    def calculate_stop_loss_take_profit(self, entry_price, position_type='long'):
        if position_type == 'long':
            stop_loss_price = entry_price * (1 - self.stop_loss_pct)
            take_profit_price = entry_price * (1 + self.take_profit_pct)
        elif position_type == 'short':
            stop_loss_price = entry_price * (1 + self.stop_loss_pct)
            take_profit_price = entry_price * (1 - self.take_profit_pct)
        else:
            raise ValueError("position_type must be 'long' or 'short'")
        return stop_loss_price, take_profit_price
