import argparse
import yaml
from src.backtester import Backtester
from src.utils import setup_logger

def main():
    parser = argparse.ArgumentParser(description="Run backtests for the momentum scalping bot.")
    parser.add_argument("--symbol", type=str, required=True, help="Symbol to backtest (e.g., AAPL)")
    parser.add_argument("--start_date", type=str, required=True, help="Start date for backtest (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, required=True, help="End date for backtest (YYYY-MM-DD)")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to the configuration file")

    args = parser.parse_args()

    logger = setup_logger("RunBacktest", "run_backtest.log")

    try:
        with open(args.config, "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found at {args.config}")
        return

    backtester = Backtester(config)
    trades_df, account_history_df = backtester.run_backtest(args.symbol, args.start_date, args.end_date)

    if not trades_df.empty:
        metrics = backtester.analyze_results(trades_df, account_history_df)
        logger.info("\n--- Backtest Results ---")
        for key, value in metrics.items():
            if isinstance(value, float):
                logger.info(f"{key.replace("_", " ").title()}: {value:.2f}")
            else:
                logger.info(f"{key.replace("_", " ").title()}: {value}")
        
        # Optionally save trades and account history to CSV
        trades_df.to_csv(f"backtest_trades_{args.symbol}.csv", index=False)
        account_history_df.to_csv(f"backtest_account_history_{args.symbol}.csv", index=False)
        logger.info(f"Trades saved to backtest_trades_{args.symbol}.csv")
        logger.info(f"Account history saved to backtest_account_history_{args.symbol}.csv")
    else:
        logger.info("No trades were executed during the backtest.")

if __name__ == "__main__":
    main()
